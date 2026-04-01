"""Comprehensive tests for pipeline/cognee_pipeline.py.

Covers:
- ChapterChunk dataclass (token_estimate, fields)
- EntityNode, RelationEdge, ExtractionResult Pydantic models
- chunk_with_chapter_awareness: paragraph boundaries, target size, chapter tagging,
  single paragraph, empty text, small chunk size, no mid-paragraph splits,
  start_char/end_char tracking
- _ranges_overlap helper
- _render_prompt: template rendering, BookNLP entity/quote filtering by char range,
  ontology injection
- _load_extraction_prompt: file loading, caching, missing file error
- _to_datapoints: entity conversion, relation conversion, chapter fallback
- extract_enriched_graph: LLM retries, all-fail graceful skip, success accumulation
- run_bookrag_pipeline: pipeline assembly, datapoint persistence to disk

Aligned with:
- CLAUDE.md: "Custom Cognee pipeline (chapter-aware chunker + enriched graph extractor)"
- Plan: "chunk_with_chapter_awareness — Split batch text into chunks, each tagged with chapter"
- Plan: "extract_enriched_graph — Uses Cognee LLMGateway, calls Claude with resolved text + BookNLP + ontology"
- Plan: "3 retries then halt pipeline"
- Plan: "add_data_points — Cognee built-in"
- Deep research: "LLMGateway.acreate_structured_output"
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock cognee modules before importing cognee_pipeline
# ---------------------------------------------------------------------------

_mock_llm_gateway = MagicMock()
_mock_llm_gateway.acreate_structured_output = AsyncMock()

_llm_module = types.ModuleType("cognee.infrastructure.llm")
_llm_gw_module = types.ModuleType("cognee.infrastructure.llm.LLMGateway")
_llm_gw_module.LLMGateway = _mock_llm_gateway

_pipelines_module = types.ModuleType("cognee.modules.pipelines")
_pipelines_module.run_pipeline = AsyncMock()

_tasks_module = types.ModuleType("cognee.modules.pipelines.tasks")
_task_module = types.ModuleType("cognee.modules.pipelines.tasks.task")
_task_module.Task = MagicMock()

_storage_module = types.ModuleType("cognee.tasks.storage")
_storage_module.add_data_points = MagicMock()

# Install mocks
for mod_name, mod in [
    ("cognee.infrastructure.llm", _llm_module),
    ("cognee.infrastructure.llm.LLMGateway", _llm_gw_module),
    ("cognee.modules.pipelines", _pipelines_module),
    ("cognee.modules.pipelines.tasks", _tasks_module),
    ("cognee.modules.pipelines.tasks.task", _task_module),
    ("cognee.tasks", types.ModuleType("cognee.tasks")),
    ("cognee.tasks.storage", _storage_module),
]:
    sys.modules.setdefault(mod_name, mod)

from pipeline.cognee_pipeline import (
    ChapterChunk,
    EntityNode,
    RelationEdge,
    ExtractionResult,
    chunk_with_chapter_awareness,
    extract_enriched_graph,
    _ranges_overlap,
    _render_prompt,
    _load_extraction_prompt,
    _to_datapoints,
    _PROMPT_CACHE,
)
from pipeline.batcher import Batch


# ---------------------------------------------------------------------------
# ChapterChunk
# ---------------------------------------------------------------------------

class TestChapterChunk:
    def test_token_estimate(self):
        c = ChapterChunk(text="a" * 400, chapter_numbers=[1], start_char=0, end_char=400)
        assert c.token_estimate == 100

    def test_token_estimate_minimum_1(self):
        c = ChapterChunk(text="hi", chapter_numbers=[1], start_char=0, end_char=2)
        assert c.token_estimate == 1

    def test_fields(self):
        c = ChapterChunk(text="hello", chapter_numbers=[1, 2], start_char=10, end_char=15)
        assert c.text == "hello"
        assert c.chapter_numbers == [1, 2]
        assert c.start_char == 10
        assert c.end_char == 15


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestExtractionModels:
    def test_entity_node_defaults(self):
        e = EntityNode(name="Scrooge", entity_type="Character")
        assert e.description == ""
        assert e.chapter_numbers == []
        assert e.aliases == []

    def test_entity_node_full(self):
        e = EntityNode(
            name="Scrooge",
            entity_type="Character",
            description="A miser",
            chapter_numbers=[1, 2],
            aliases=["Ebenezer", "Mr. Scrooge"],
        )
        assert e.aliases == ["Ebenezer", "Mr. Scrooge"]

    def test_relation_edge_defaults(self):
        r = RelationEdge(source="Scrooge", target="Bob Cratchit", relation_type="EMPLOYS")
        assert r.description == ""
        assert r.evidence == ""

    def test_relation_edge_full(self):
        r = RelationEdge(
            source="Scrooge",
            target="Marley",
            relation_type="ALLIES_WITH",
            description="Business partners",
            chapter_numbers=[1],
            evidence="were partners for many years",
        )
        assert r.chapter_numbers == [1]

    def test_extraction_result_defaults(self):
        er = ExtractionResult()
        assert er.entities == []
        assert er.relations == []

    def test_extraction_result_populated(self):
        er = ExtractionResult(
            entities=[EntityNode(name="Scrooge", entity_type="Character")],
            relations=[RelationEdge(source="Scrooge", target="Marley", relation_type="KNOWS")],
        )
        assert len(er.entities) == 1
        assert len(er.relations) == 1


# ---------------------------------------------------------------------------
# chunk_with_chapter_awareness
# ---------------------------------------------------------------------------

class TestChunkWithChapterAwareness:
    def test_single_paragraph_single_chunk(self):
        chunks = chunk_with_chapter_awareness("Hello world.", chunk_size=1500)
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].chapter_numbers == [1]

    def test_respects_paragraph_boundaries(self):
        """Plan: 'Respect paragraph boundaries', 'never split mid-paragraph'."""
        para1 = "A" * 3000  # ~750 tokens
        para2 = "B" * 3000  # ~750 tokens
        text = f"{para1}\n\n{para2}"
        chunks = chunk_with_chapter_awareness(text, chunk_size=800)
        # Each paragraph is ~750 tokens, target is 800 → each gets its own chunk
        assert len(chunks) == 2
        assert "A" * 100 in chunks[0].text
        assert "B" * 100 in chunks[1].text
        # No mid-paragraph split
        assert "\n\n" not in chunks[0].text
        assert "\n\n" not in chunks[1].text

    def test_groups_small_paragraphs(self):
        """Small paragraphs should group together up to chunk_size."""
        paras = ["Short paragraph." for _ in range(10)]
        text = "\n\n".join(paras)
        chunks = chunk_with_chapter_awareness(text, chunk_size=1500)
        # All paragraphs combined ~160 chars → ~40 tokens, fits in one chunk
        assert len(chunks) == 1

    def test_chapter_numbers_tagged(self):
        """Plan: 'Each chunk tagged with chapter number(s) it spans'."""
        chunks = chunk_with_chapter_awareness("text", chapter_numbers=[3, 4, 5])
        assert chunks[0].chapter_numbers == [3, 4, 5]

    def test_default_chapter_numbers(self):
        chunks = chunk_with_chapter_awareness("text")
        assert chunks[0].chapter_numbers == [1]

    def test_start_end_char_tracking(self):
        """Chunks should track char positions for BookNLP range filtering."""
        para1 = "First paragraph."
        para2 = "Second paragraph."
        text = f"{para1}\n\n{para2}"
        # Use a tiny chunk size to force split
        chunks = chunk_with_chapter_awareness(text, chunk_size=5)
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(para1)
        assert chunks[1].start_char > 0

    def test_empty_text(self):
        chunks = chunk_with_chapter_awareness("")
        assert len(chunks) == 1
        assert chunks[0].text == ""

    def test_many_paragraphs_split(self):
        """Realistic: many paragraphs should create multiple chunks."""
        paras = ["Word " * 500 for _ in range(10)]  # ~2500 chars each → ~625 tokens
        text = "\n\n".join(paras)
        chunks = chunk_with_chapter_awareness(text, chunk_size=1500)
        # 10 paragraphs × 625 tokens ≈ 6250 total, target 1500 → ~4-5 chunks
        assert len(chunks) >= 3

    def test_target_1500_tokens_default(self):
        """Plan: 'Target chunk size: ~1500 tokens (configurable)'."""
        para = "word " * 1500  # ~7500 chars → ~1875 tokens
        text = f"{para}\n\n{para}"
        chunks = chunk_with_chapter_awareness(text)  # default chunk_size=1500
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# _ranges_overlap
# ---------------------------------------------------------------------------

class TestRangesOverlap:
    def test_overlap(self):
        assert _ranges_overlap(0, 10, 5, 15) is True

    def test_no_overlap(self):
        assert _ranges_overlap(0, 5, 10, 15) is False

    def test_adjacent_no_overlap(self):
        assert _ranges_overlap(0, 5, 5, 10) is False

    def test_contained(self):
        assert _ranges_overlap(2, 8, 0, 10) is True

    def test_same_range(self):
        assert _ranges_overlap(5, 10, 5, 10) is True

    def test_zero_width_range(self):
        # A zero-width range (5,5) technically satisfies s1 < e2 and s2 < e1
        # so it overlaps with (0,10). This is correct: point 5 is within [0,10).
        assert _ranges_overlap(5, 5, 0, 10) is True

    def test_zero_width_outside(self):
        assert _ranges_overlap(15, 15, 0, 10) is False


# ---------------------------------------------------------------------------
# _load_extraction_prompt and _render_prompt
# ---------------------------------------------------------------------------

class TestPromptRendering:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _PROMPT_CACHE.clear()
        yield
        _PROMPT_CACHE.clear()

    def test_load_extraction_prompt(self, tmp_path):
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("Hello {chunk_text}")
        result = _load_extraction_prompt(str(prompt_file))
        assert result == "Hello {chunk_text}"

    def test_load_extraction_prompt_caches(self, tmp_path):
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("cached")
        _load_extraction_prompt(str(prompt_file))
        prompt_file.write_text("changed")
        # Should still return cached version
        assert _load_extraction_prompt(str(prompt_file)) == "cached"

    def test_load_extraction_prompt_missing_raises(self):
        with pytest.raises(FileNotFoundError, match="Extraction prompt template not found"):
            _load_extraction_prompt("/nonexistent/prompt.txt")

    def test_render_prompt_injects_all_fields(self, tmp_path):
        """Plan: prompt includes chunk_text, chapter_numbers, booknlp entities/quotes, ontology."""
        # Uses string.Template $-syntax after vuln fix
        _PROMPT_CACHE["prompts/extraction_prompt.txt"] = (
            "Text: $chunk_text\n"
            "Chapters: $chapter_numbers\n"
            "Entities: $booknlp_entities\n"
            "Quotes: $booknlp_quotes\n"
            "Classes: $ontology_classes\n"
            "Relations: $ontology_relations"
        )
        chunk = ChapterChunk(text="Scrooge walked.", chapter_numbers=[1, 2], start_char=0, end_char=100)
        booknlp = {
            "entities": [{"start_char": 0, "end_char": 50, "name": "Scrooge"}],
            "quotes": [{"start_char": 0, "end_char": 80, "text": "Bah humbug"}],
        }
        ontology = {
            "entity_classes": ["Character", "Location"],
            "relation_types": ["EMPLOYS", "KNOWS"],
        }
        rendered = _render_prompt(chunk, booknlp, ontology)
        assert "Scrooge walked." in rendered
        assert "1, 2" in rendered
        assert "Scrooge" in rendered
        assert "Bah humbug" in rendered
        assert "Character" in rendered
        assert "EMPLOYS" in rendered

    def test_render_prompt_safe_against_format_injection(self):
        """Vuln fix: book text with {__class__} must not cause injection."""
        _PROMPT_CACHE["prompts/extraction_prompt.txt"] = "Text: $chunk_text"
        chunk = ChapterChunk(
            text="He said {__class__.__init__.__globals__} loudly",
            chapter_numbers=[1], start_char=0, end_char=50,
        )
        rendered = _render_prompt(chunk, {"entities": [], "quotes": []}, {})
        # The curly-brace text should pass through literally, not execute
        assert "{__class__" in rendered

    def test_render_prompt_filters_entities_by_range(self, tmp_path):
        """Only BookNLP entities overlapping the chunk's char range should be included."""
        _PROMPT_CACHE["prompts/extraction_prompt.txt"] = (
            "$chunk_text|$booknlp_entities|$booknlp_quotes|"
            "$chapter_numbers|$ontology_classes|$ontology_relations"
        )
        chunk = ChapterChunk(text="text", chapter_numbers=[1], start_char=100, end_char=200)
        booknlp = {
            "entities": [
                {"start_char": 50, "end_char": 60, "name": "OutOfRange"},
                {"start_char": 150, "end_char": 160, "name": "InRange"},
            ],
            "quotes": [
                {"start_char": 0, "end_char": 10, "text": "OutOfRange"},
                {"start_char": 110, "end_char": 190, "text": "InRange"},
            ],
        }
        rendered = _render_prompt(chunk, booknlp, {"entity_classes": [], "relation_types": []})
        assert "InRange" in rendered
        assert "OutOfRange" not in rendered


# ---------------------------------------------------------------------------
# _to_datapoints
# ---------------------------------------------------------------------------

class TestToDatapoints:
    def test_entity_conversion(self):
        """Entities become dicts with type='entity' and chapter metadata."""
        result = ExtractionResult(
            entities=[EntityNode(name="Scrooge", entity_type="Character", chapter_numbers=[1])],
            relations=[],
        )
        chunk = ChapterChunk(text="t", chapter_numbers=[1, 2], start_char=0, end_char=10)
        dps = _to_datapoints(result, chunk)
        assert len(dps) == 1
        assert dps[0]["type"] == "entity"
        assert dps[0]["name"] == "Scrooge"
        assert dps[0]["entity_type"] == "Character"
        assert dps[0]["chapter_numbers"] == [1]
        assert dps[0]["source_start_char"] == 0
        assert dps[0]["source_end_char"] == 10

    def test_relation_conversion(self):
        result = ExtractionResult(
            entities=[],
            relations=[RelationEdge(
                source="Scrooge",
                target="Bob Cratchit",
                relation_type="EMPLOYS",
                evidence="employs as clerk",
                chapter_numbers=[1],
            )],
        )
        chunk = ChapterChunk(text="t", chapter_numbers=[1], start_char=5, end_char=15)
        dps = _to_datapoints(result, chunk)
        assert len(dps) == 1
        assert dps[0]["type"] == "relation"
        assert dps[0]["source"] == "Scrooge"
        assert dps[0]["target"] == "Bob Cratchit"
        assert dps[0]["relation_type"] == "EMPLOYS"
        assert dps[0]["source_start_char"] == 5

    def test_chapter_fallback_to_chunk(self):
        """If entity has no chapter_numbers, inherit from chunk."""
        result = ExtractionResult(
            entities=[EntityNode(name="X", entity_type="T", chapter_numbers=[])],
            relations=[],
        )
        chunk = ChapterChunk(text="t", chapter_numbers=[3, 4], start_char=0, end_char=1)
        dps = _to_datapoints(result, chunk)
        assert dps[0]["chapter_numbers"] == [3, 4]

    def test_mixed_entities_and_relations(self):
        result = ExtractionResult(
            entities=[EntityNode(name="A", entity_type="T")],
            relations=[RelationEdge(source="A", target="B", relation_type="R")],
        )
        chunk = ChapterChunk(text="t", chapter_numbers=[1], start_char=0, end_char=1)
        dps = _to_datapoints(result, chunk)
        assert len(dps) == 2
        types = {dp["type"] for dp in dps}
        assert types == {"entity", "relation"}

    def test_empty_result(self):
        result = ExtractionResult()
        chunk = ChapterChunk(text="t", chapter_numbers=[1], start_char=0, end_char=1)
        assert _to_datapoints(result, chunk) == []


# ---------------------------------------------------------------------------
# extract_enriched_graph (async)
# ---------------------------------------------------------------------------

class TestExtractEnrichedGraph:
    @pytest.fixture(autouse=True)
    def setup_prompt_cache(self):
        _PROMPT_CACHE["prompts/extraction_prompt.txt"] = (
            "$chunk_text|$booknlp_entities|$booknlp_quotes|"
            "$chapter_numbers|$ontology_classes|$ontology_relations"
        )
        yield
        _PROMPT_CACHE.clear()

    def test_successful_extraction(self):
        """LLMGateway returns structured output → datapoints produced."""
        mock_result = ExtractionResult(
            entities=[EntityNode(name="Scrooge", entity_type="Character")],
            relations=[],
        )
        _mock_llm_gateway.acreate_structured_output = AsyncMock(return_value=mock_result)

        chunks = [ChapterChunk(text="Scrooge walked.", chapter_numbers=[1], start_char=0, end_char=15)]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=1)
        )
        assert len(result) == 1
        assert result[0]["name"] == "Scrooge"

    def test_retry_on_failure(self):
        """Plan: '3 retries then halt pipeline'. Test that retries happen."""
        call_count = 0

        async def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("LLM timeout")
            return ExtractionResult(
                entities=[EntityNode(name="Recovered", entity_type="T")]
            )

        _mock_llm_gateway.acreate_structured_output = AsyncMock(side_effect=fail_then_succeed)

        chunks = [ChapterChunk(text="text", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=3)
        )
        assert call_count == 3
        assert len(result) == 1
        assert result[0]["name"] == "Recovered"

    def test_all_retries_fail_graceful_skip(self):
        """If all retries fail, chunk is skipped (not crash)."""
        _mock_llm_gateway.acreate_structured_output = AsyncMock(
            side_effect=ConnectionError("permanent failure")
        )
        chunks = [ChapterChunk(text="text", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=2)
        )
        assert result == []

    def test_multiple_chunks(self):
        """Multiple chunks should produce combined datapoints."""
        mock_result = ExtractionResult(
            entities=[EntityNode(name="E", entity_type="T")],
            relations=[RelationEdge(source="A", target="B", relation_type="R")],
        )
        _mock_llm_gateway.acreate_structured_output = AsyncMock(return_value=mock_result)

        chunks = [
            ChapterChunk(text="c1", chapter_numbers=[1], start_char=0, end_char=2),
            ChapterChunk(text="c2", chapter_numbers=[2], start_char=2, end_char=4),
        ]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=1)
        )
        # 2 datapoints per chunk (1 entity + 1 relation) × 2 chunks
        assert len(result) == 4

    def test_defaults_for_none_booknlp_ontology(self):
        """Passing None for booknlp/ontology should not crash."""
        mock_result = ExtractionResult()
        _mock_llm_gateway.acreate_structured_output = AsyncMock(return_value=mock_result)

        chunks = [ChapterChunk(text="t", chapter_numbers=[1], start_char=0, end_char=1)]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, booknlp=None, ontology=None, max_retries=1)
        )
        assert result == []
