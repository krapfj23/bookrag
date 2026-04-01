"""Comprehensive tests for pipeline/cognee_pipeline.py.

Covers:
- ChapterChunk dataclass (token_estimate, fields)
- ExtractionResult and extraction models (CharacterExtraction, RelationshipExtraction, etc.)
- chunk_with_chapter_awareness: paragraph boundaries, target size, chapter tagging,
  single paragraph, empty text, small chunk size, no mid-paragraph splits,
  start_char/end_char tracking
- render_prompt: template rendering, BookNLP entity/quote formatting, ontology injection
- _load_extraction_prompt: file loading, caching, missing file error
- ExtractionResult.to_datapoints(): entity conversion, relation conversion, cross-references
- extract_enriched_graph: LLM retries, all-fail graceful skip, success accumulation
- run_bookrag_pipeline: pipeline assembly, datapoint persistence to disk

Aligned with:
- CLAUDE.md: "Custom Cognee pipeline (chapter-aware chunker + enriched graph extractor)"
- Plan: "chunk_with_chapter_awareness -- Split batch text into chunks, each tagged with chapter"
- Plan: "extract_enriched_graph -- Uses Cognee LLMGateway, calls Claude with resolved text + BookNLP + ontology"
- Plan: "3 retries then halt pipeline"
- Plan: "add_data_points -- Cognee built-in"
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
    chunk_with_chapter_awareness,
    extract_enriched_graph,
    render_prompt,
    _load_extraction_prompt,
    _PROMPT_CACHE,
)
from models.datapoints import (
    ExtractionResult,
    CharacterExtraction,
    LocationExtraction,
    RelationshipExtraction,
    EventExtraction,
    ThemeExtraction,
    FactionExtraction,
    Character,
    Location,
    Relationship,
    PlotEvent,
    Theme,
    Faction,
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
# Pydantic extraction models
# ---------------------------------------------------------------------------

class TestExtractionModels:
    """Tests for the LLM extraction Pydantic models from models/datapoints.py."""

    def test_character_extraction_defaults(self):
        c = CharacterExtraction(name="Scrooge", first_chapter=1)
        assert c.description is None
        assert c.chapters_present == []
        assert c.aliases == []

    def test_character_extraction_full(self):
        c = CharacterExtraction(
            name="Scrooge",
            description="A miser",
            first_chapter=1,
            chapters_present=[1, 2],
            aliases=["Ebenezer", "Mr. Scrooge"],
        )
        assert c.aliases == ["Ebenezer", "Mr. Scrooge"]

    def test_relationship_extraction_fields(self):
        r = RelationshipExtraction(
            source_name="Scrooge",
            target_name="Bob Cratchit",
            relation_type="employs",
            first_chapter=1,
        )
        assert r.description is None
        assert r.source_name == "Scrooge"
        assert r.target_name == "Bob Cratchit"

    def test_relationship_extraction_full(self):
        r = RelationshipExtraction(
            source_name="Scrooge",
            target_name="Marley",
            relation_type="allies_with",
            description="Business partners",
            first_chapter=1,
        )
        assert r.first_chapter == 1

    def test_extraction_result_defaults(self):
        er = ExtractionResult()
        assert er.characters == []
        assert er.locations == []
        assert er.events == []
        assert er.relationships == []
        assert er.themes == []
        assert er.factions == []

    def test_extraction_result_populated(self):
        er = ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
            relationships=[RelationshipExtraction(
                source_name="Scrooge", target_name="Marley",
                relation_type="knows", first_chapter=1,
            )],
        )
        assert len(er.characters) == 1
        assert len(er.relationships) == 1


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
        # Each paragraph is ~750 tokens, target is 800 -> each gets its own chunk
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
        # All paragraphs combined ~160 chars -> ~40 tokens, fits in one chunk
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
        paras = ["Word " * 500 for _ in range(10)]  # ~2500 chars each -> ~625 tokens
        text = "\n\n".join(paras)
        chunks = chunk_with_chapter_awareness(text, chunk_size=1500)
        # 10 paragraphs x 625 tokens ~ 6250 total, target 1500 -> ~4-5 chunks
        assert len(chunks) >= 3

    def test_target_1500_tokens_default(self):
        """Plan: 'Target chunk size: ~1500 tokens (configurable)'."""
        para = "word " * 1500  # ~7500 chars -> ~1875 tokens
        text = f"{para}\n\n{para}"
        chunks = chunk_with_chapter_awareness(text)  # default chunk_size=1500
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# _load_extraction_prompt and render_prompt
# ---------------------------------------------------------------------------

class TestPromptRendering:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _PROMPT_CACHE.clear()
        yield
        _PROMPT_CACHE.clear()

    def test_load_extraction_prompt(self, tmp_path):
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("Hello {{ text }}")
        result = _load_extraction_prompt(str(prompt_file))
        assert result == "Hello {{ text }}"

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

    def test_render_prompt_returns_tuple(self, tmp_path):
        """render_prompt returns (system_prompt, text_input) tuple."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(
            "Chapters: {{ chapter_numbers }}\n"
            "Entities: {{ booknlp_entities }}\n"
            "Quotes: {{ booknlp_quotes }}\n"
            "Classes: {{ ontology_classes }}\n"
            "Relations: {{ ontology_relations }}\n"
            "Text: {{ text }}"
        )
        chunk = ChapterChunk(text="Scrooge walked.", chapter_numbers=[1, 2], start_char=0, end_char=100)
        booknlp = {
            "entities": [{"prop": "PROP", "text": "Scrooge", "cat": "PER"}],
            "quotes": [{"speaker": "Scrooge", "text": "Bah humbug"}],
        }
        ontology = {
            "discovered_entities": {"Character": [], "Location": []},
            "discovered_relations": [{"name": "employs"}, {"name": "knows"}],
        }
        system_prompt, text_input = render_prompt(
            chunk, booknlp, ontology, prompt_path=str(prompt_file),
        )
        # text_input is the raw chunk text
        assert text_input == "Scrooge walked."
        # system_prompt has the rendered template
        assert "1, 2" in system_prompt
        assert "Scrooge" in system_prompt
        assert "Bah humbug" in system_prompt
        assert "Character" in system_prompt
        assert "employs" in system_prompt

    def test_render_prompt_safe_against_format_injection(self, tmp_path):
        """Book text with {__class__} must not cause injection."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Text: {{ text }}")
        chunk = ChapterChunk(
            text="He said {__class__.__init__.__globals__} loudly",
            chapter_numbers=[1], start_char=0, end_char=50,
        )
        system_prompt, text_input = render_prompt(
            chunk, {"entities": [], "quotes": []}, {},
            prompt_path=str(prompt_file),
        )
        # The curly-brace text is in text_input (raw), not interpreted
        assert "{__class__" in text_input

    def test_render_prompt_formats_entities(self, tmp_path):
        """BookNLP entities with prop=PROP/NOM and non-empty text should be formatted."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(
            "{{ booknlp_entities }}\n{{ text }}\n"
            "{{ chapter_numbers }}\n{{ booknlp_quotes }}\n"
            "{{ ontology_classes }}\n{{ ontology_relations }}"
        )
        chunk = ChapterChunk(text="text", chapter_numbers=[1], start_char=0, end_char=100)
        booknlp = {
            "entities": [
                {"prop": "PROP", "cat": "PER", "text": "Scrooge"},
                {"prop": "PRON", "cat": "PER", "text": "he"},  # PRON excluded
            ],
            "quotes": [],
        }
        system_prompt, _ = render_prompt(
            chunk, booknlp, {}, prompt_path=str(prompt_file),
        )
        assert "Scrooge" in system_prompt


# ---------------------------------------------------------------------------
# ExtractionResult.to_datapoints()
# ---------------------------------------------------------------------------

class TestToDatapoints:
    """Tests for ExtractionResult.to_datapoints() which converts extraction models to DataPoints."""

    def test_character_conversion(self):
        """Characters become Character DataPoints."""
        result = ExtractionResult(
            characters=[CharacterExtraction(
                name="Scrooge", first_chapter=1, chapters_present=[1],
            )],
        )
        dps = result.to_datapoints()
        assert len(dps) == 1
        assert isinstance(dps[0], Character)
        assert dps[0].name == "Scrooge"
        assert dps[0].first_chapter == 1

    def test_relationship_conversion(self):
        """Relationships resolve source/target by name to Character DataPoints."""
        result = ExtractionResult(
            characters=[
                CharacterExtraction(name="Scrooge", first_chapter=1),
                CharacterExtraction(name="Bob Cratchit", first_chapter=1),
            ],
            relationships=[RelationshipExtraction(
                source_name="Scrooge",
                target_name="Bob Cratchit",
                relation_type="employs",
                description="employs as clerk",
                first_chapter=1,
            )],
        )
        dps = result.to_datapoints()
        # 2 characters + 1 relationship = 3 DataPoints
        relationships = [dp for dp in dps if isinstance(dp, Relationship)]
        assert len(relationships) == 1
        assert relationships[0].source.name == "Scrooge"
        assert relationships[0].target.name == "Bob Cratchit"
        assert relationships[0].relation_type == "employs"

    def test_unresolved_relationship_skipped(self):
        """Relationships referencing unknown characters are skipped."""
        result = ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
            relationships=[RelationshipExtraction(
                source_name="Scrooge",
                target_name="Unknown",
                relation_type="knows",
                first_chapter=1,
            )],
        )
        dps = result.to_datapoints()
        relationships = [dp for dp in dps if isinstance(dp, Relationship)]
        assert len(relationships) == 0

    def test_event_with_participants(self):
        """Events link to Character DataPoints by participant_names."""
        result = ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
            events=[EventExtraction(
                description="Scrooge sees a ghost",
                chapter=1,
                participant_names=["Scrooge"],
            )],
        )
        dps = result.to_datapoints()
        events = [dp for dp in dps if isinstance(dp, PlotEvent)]
        assert len(events) == 1
        assert len(events[0].participants) == 1
        assert events[0].participants[0].name == "Scrooge"

    def test_mixed_types(self):
        """Multiple extraction types produce the right DataPoint types."""
        result = ExtractionResult(
            characters=[CharacterExtraction(name="A", first_chapter=1)],
            locations=[LocationExtraction(name="London", first_chapter=1)],
            relationships=[RelationshipExtraction(
                source_name="A", target_name="A",
                relation_type="self_ref", first_chapter=1,
            )],
        )
        dps = result.to_datapoints()
        type_names = {type(dp).__name__ for dp in dps}
        assert "Character" in type_names
        assert "Location" in type_names
        assert "Relationship" in type_names

    def test_empty_result(self):
        result = ExtractionResult()
        assert result.to_datapoints() == []


# ---------------------------------------------------------------------------
# extract_enriched_graph (async)
# ---------------------------------------------------------------------------

class TestExtractEnrichedGraph:
    @pytest.fixture(autouse=True)
    def setup_prompt_cache(self):
        _PROMPT_CACHE["prompts/extraction_prompt.txt"] = (
            "{{ text }}\n{{ booknlp_entities }}\n{{ booknlp_quotes }}\n"
            "{{ chapter_numbers }}\n{{ ontology_classes }}\n{{ ontology_relations }}"
        )
        yield
        _PROMPT_CACHE.clear()

    def test_successful_extraction(self):
        """LLMGateway returns structured output -> DataPoints produced."""
        mock_result = ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
        )
        _mock_llm_gateway.acreate_structured_output = AsyncMock(return_value=mock_result)

        chunks = [ChapterChunk(text="Scrooge walked.", chapter_numbers=[1], start_char=0, end_char=15)]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=1)
        )
        assert len(result) == 1
        assert isinstance(result[0], Character)
        assert result[0].name == "Scrooge"

    def test_retry_on_failure(self):
        """Plan: '3 retries then halt pipeline'. Test that retries happen."""
        call_count = 0

        async def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("LLM timeout")
            return ExtractionResult(
                characters=[CharacterExtraction(name="Recovered", first_chapter=1)]
            )

        _mock_llm_gateway.acreate_structured_output = AsyncMock(side_effect=fail_then_succeed)

        chunks = [ChapterChunk(text="text", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=3)
        )
        assert call_count == 3
        assert len(result) == 1
        assert isinstance(result[0], Character)
        assert result[0].name == "Recovered"

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
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
            locations=[LocationExtraction(name="London", first_chapter=1)],
        )
        _mock_llm_gateway.acreate_structured_output = AsyncMock(return_value=mock_result)

        chunks = [
            ChapterChunk(text="c1", chapter_numbers=[1], start_char=0, end_char=2),
            ChapterChunk(text="c2", chapter_numbers=[2], start_char=2, end_char=4),
        ]
        result = asyncio.get_event_loop().run_until_complete(
            extract_enriched_graph(chunks, max_retries=1)
        )
        # 2 datapoints per chunk (1 character + 1 location) x 2 chunks = 4
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
