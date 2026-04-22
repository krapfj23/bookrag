"""
Comprehensive tests for pipeline/cognee_pipeline.py

Tests every feature against CLAUDE.md, bookrag_pipeline_plan.md, and
bookrag_deep_research_context.md:

- ChapterChunk: construction, token estimation, chapter provenance
- chunk_with_chapter_awareness: paragraph-respecting, target size, chapter tags,
  single paragraph, empty text, large text
- Prompt rendering: Jinja2 template, all 6 placeholders, text separation,
  BookNLP entity/quote formatting, ontology class/relation formatting
- extract_enriched_graph: ExtractionResult usage, to_datapoints() conversion,
  retry logic, all-fail graceful handling, stats logging
- run_bookrag_pipeline: full 3-stage pipeline, batch artifact saving
  (input_text.txt, annotations.json, extracted_datapoints.json),
  output path spec, empty extraction handling
- Integration: uses models/datapoints.py ExtractionResult (not generic dicts),
  returns actual DataPoint instances
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.datapoints import (
    Character,
    CharacterExtraction,
    EventExtraction,
    ExtractionResult,
    Location,
    LocationExtraction,
    PlotEvent,
    Relationship,
    RelationshipExtraction,
    ThemeExtraction,
)
from pipeline.batcher import Batch
from pipeline.cognee_pipeline import (
    ChapterChunk,
    _format_booknlp_entities,
    _format_booknlp_quotes,
    _format_ontology_classes,
    _format_ontology_relations,
    _save_batch_artifacts,
    chunk_with_chapter_awareness,
    configure_cognee,
    extract_enriched_graph,
    render_prompt,
    run_bookrag_pipeline,
)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def sample_batch() -> Batch:
    """A realistic batch of 3 Christmas Carol chapters."""
    texts = [
        "Marley was dead. Scrooge knew it.\n\nThe counting-house was cold.",
        "The ghost appeared. Scrooge was terrified.\n\nChains rattled loudly.",
        "Christmas morning arrived. Scrooge was transformed.\n\nHe danced with joy.",
    ]
    return Batch(
        chapter_numbers=[1, 2, 3],
        texts=texts,
        combined_text="\n\n".join(texts),
    )


@pytest.fixture
def sample_booknlp() -> dict:
    return {
        "entities_tsv": [
            {"COREF": 0, "prop": "PROP", "cat": "PER", "text": "Scrooge"},
            {"COREF": 1, "prop": "PROP", "cat": "PER", "text": "Marley"},
            {"COREF": 2, "prop": "PROP", "cat": "LOC", "text": "London"},
            {"COREF": 3, "prop": "PRON", "cat": "PER", "text": "he"},
            {"COREF": 4, "prop": "NOM", "cat": "PER", "text": "the ghost"},
        ],
        "quotes": [
            {"speaker": "Scrooge", "text": "Bah! Humbug!"},
            {"speaker": "Marley", "text": "I wear the chain I forged in life."},
        ],
    }


@pytest.fixture
def sample_ontology() -> dict:
    return {
        "discovered_entities": {
            "Character": [{"name": "Scrooge", "count": 150}],
            "Location": [{"name": "London", "count": 3}],
        },
        "discovered_relations": [
            {"name": "employs", "source": "booknlp"},
            {"name": "haunts", "source": "booknlp"},
            {"name": "fears", "source": "tfidf"},
        ],
    }


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    return ExtractionResult(
        characters=[
            CharacterExtraction(name="Scrooge", aliases=["Ebenezer"], first_chapter=1, chapters_present=[1, 2, 3]),
            CharacterExtraction(name="Marley", first_chapter=1),
        ],
        locations=[
            LocationExtraction(name="London", first_chapter=1),
        ],
        events=[
            EventExtraction(description="Ghost appears to Scrooge", chapter=2, participant_names=["Scrooge"]),
        ],
        relationships=[
            RelationshipExtraction(source_name="Scrooge", target_name="Marley", relation_type="fears", first_chapter=2),
        ],
        themes=[
            ThemeExtraction(name="Redemption", first_chapter=1, related_character_names=["Scrooge"]),
        ],
    )


@pytest.fixture
def prompt_file(tmp_path) -> Path:
    """Create a minimal Jinja2 prompt template for tests."""
    prompt = (
        "You are an extraction assistant.\n"
        "Chapters: {{ chapter_numbers }}\n"
        "Classes: {{ ontology_classes }}\n"
        "Relations: {{ ontology_relations }}\n"
        "Entities: {{ booknlp_entities }}\n"
        "Quotes: {{ booknlp_quotes }}\n"
        "Text: {{ text }}\n"
    )
    p = tmp_path / "prompts" / "extraction_prompt.txt"
    p.parent.mkdir(parents=True)
    p.write_text(prompt)
    return p


# ===================================================================
# ChapterChunk
# ===================================================================

class TestConfigureCognee:
    """Plan 1: configure_cognee must propagate temperature+seed to Cognee.

    Without these keys, Cognee defaults to temperature=0.0 but OpenAI
    defaults to 1.0 at call-time — meaning extraction is effectively
    random unless we explicitly set the config. The tests below pin
    the expected key names and values.
    """

    def _make_config(self, **overrides):
        """Minimal config object with the attributes configure_cognee reads."""
        defaults = {
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
            "llm_temperature": 0.0,
            "llm_seed": 42,
        }
        defaults.update(overrides)
        ns = MagicMock()
        for k, v in defaults.items():
            setattr(ns, k, v)
        return ns

    def _install_config_stub(self, monkeypatch):
        """Ensure cognee.config exists with a capturable set_llm_config.

        The conftest mock creates the cognee module skeleton but doesn't add
        `config` — that's fine for existing tests, but configure_cognee()
        calls cognee.config.set_llm_config. We install a simple stub here
        that records the dict it was passed.
        """
        import cognee
        captured: dict = {}
        stub = MagicMock()
        stub.set_llm_config = MagicMock(side_effect=lambda d: captured.update(d))
        monkeypatch.setattr(cognee, "config", stub, raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-stub")
        return captured

    def test_temperature_is_passed_to_set_llm_config(self, monkeypatch):
        """configure_cognee reads llm_temperature from the config and includes
        it in the dict passed to cognee.config.set_llm_config."""
        captured = self._install_config_stub(monkeypatch)
        configure_cognee(self._make_config(llm_temperature=0.0, llm_seed=42))
        assert captured.get("llm_temperature") == 0.0, (
            f"llm_temperature must be forwarded to Cognee; got {captured}"
        )

    def test_non_default_temperature_flows_through(self, monkeypatch):
        """Config with llm_temperature=0.7 reaches Cognee as 0.7."""
        captured = self._install_config_stub(monkeypatch)
        configure_cognee(self._make_config(llm_temperature=0.7, llm_seed=123))
        assert captured["llm_temperature"] == 0.7

    def test_seed_is_not_forwarded_to_cognee_0_5_6(self, monkeypatch):
        """Cognee 0.5.6's LLMConfig does NOT accept llm_seed — sending it
        raises InvalidConfigAttributeError at runtime. We keep the field on
        BookRAGConfig for future use but must NOT send it to Cognee yet."""
        captured = self._install_config_stub(monkeypatch)
        configure_cognee(self._make_config(llm_seed=42))
        assert "llm_seed" not in captured, (
            f"llm_seed must not be forwarded to Cognee 0.5.6; got {captured}"
        )


class TestChapterChunk:
    def test_construction(self):
        c = ChapterChunk(text="Hello world", chapter_numbers=[1, 2], start_char=0, end_char=11)
        assert c.text == "Hello world"
        assert c.chapter_numbers == [1, 2]

    def test_token_estimate(self):
        c = ChapterChunk(text="a" * 400, chapter_numbers=[1], start_char=0, end_char=400)
        assert c.token_estimate == 100  # 400 chars / 4

    def test_token_estimate_minimum_one(self):
        c = ChapterChunk(text="", chapter_numbers=[1], start_char=0, end_char=0)
        assert c.token_estimate == 1


# ===================================================================
# Task 1: chunk_with_chapter_awareness
# ===================================================================

class TestChunkWithChapterAwareness:
    def test_single_paragraph(self):
        chunks = chunk_with_chapter_awareness("One paragraph.", chunk_size=1500)
        assert len(chunks) == 1
        assert chunks[0].text == "One paragraph."

    def test_respects_paragraph_boundaries(self):
        """Chunks should never split mid-paragraph."""
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_with_chapter_awareness(text, chunk_size=2)  # tiny budget forces splits
        source_paragraphs = set(text.split("\n\n"))
        for c in chunks:
            # Every paragraph inside a chunk must be a complete paragraph from source
            for para in c.text.split("\n\n"):
                assert para in source_paragraphs, (
                    f"Chunk contains a paragraph not present in source: {para!r}"
                )

    def test_chapter_numbers_tagged(self):
        chunks = chunk_with_chapter_awareness("Text.", chapter_numbers=[4, 5, 6])
        assert chunks[0].chapter_numbers == [4, 5, 6]

    def test_default_chapter_one(self):
        chunks = chunk_with_chapter_awareness("Text.")
        assert chunks[0].chapter_numbers == [1]

    def test_multiple_chunks_from_large_text(self):
        paragraphs = [f"Paragraph {i} with some content." * 10 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_with_chapter_awareness(text, chunk_size=100)
        assert len(chunks) > 1

    def test_start_end_char_tracking(self):
        text = "First para.\n\nSecond para."
        chunks = chunk_with_chapter_awareness(text, chunk_size=1500)
        if len(chunks) == 1:
            assert chunks[0].start_char == 0
            assert chunks[0].end_char == len(text)

    def test_empty_text(self):
        chunks = chunk_with_chapter_awareness("", chunk_size=1500)
        assert len(chunks) == 1
        assert chunks[0].text == ""

    def test_chunk_size_default_1500(self):
        import inspect
        sig = inspect.signature(chunk_with_chapter_awareness)
        assert sig.parameters["chunk_size"].default == 1500

    def test_all_text_accounted_for(self):
        """No text should be lost during chunking."""
        text = "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4."
        chunks = chunk_with_chapter_awareness(text, chunk_size=3)
        reconstructed = "\n\n".join(c.text for c in chunks)
        assert reconstructed == text


# ===================================================================
# Prompt rendering helpers
# ===================================================================

class TestFormatBookNLPEntities:
    def test_filters_to_prop_and_nom(self):
        entities = [
            {"prop": "PROP", "cat": "PER", "text": "Scrooge"},
            {"prop": "PRON", "cat": "PER", "text": "he"},
            {"prop": "NOM", "cat": "PER", "text": "the ghost"},
        ]
        chunk = ChapterChunk(text="", chapter_numbers=[1], start_char=0, end_char=100)
        result = _format_booknlp_entities(entities, chunk)
        assert "Scrooge" in result
        assert "the ghost" in result
        # "he" as a standalone entity should not appear (PRON filtered).
        # "the ghost" contains "he" as substring so check line-by-line.
        lines = result.strip().split("\n")
        assert not any(line.strip() == "- he (PER)" for line in lines)

    def test_empty_entities(self):
        chunk = ChapterChunk(text="", chapter_numbers=[1], start_char=0, end_char=100)
        result = _format_booknlp_entities([], chunk)
        assert "no entities" in result.lower()

    def test_caps_at_50(self):
        entities = [{"prop": "PROP", "cat": "PER", "text": f"Entity_{i}"} for i in range(100)]
        chunk = ChapterChunk(text="", chapter_numbers=[1], start_char=0, end_char=100)
        result = _format_booknlp_entities(entities, chunk)
        lines = [l for l in result.split("\n") if l.strip().startswith("-")]
        assert len(lines) == 50

    def test_includes_category(self):
        entities = [{"prop": "PROP", "cat": "LOC", "text": "London"}]
        chunk = ChapterChunk(text="", chapter_numbers=[1], start_char=0, end_char=100)
        result = _format_booknlp_entities(entities, chunk)
        assert "LOC" in result


class TestFormatBookNLPQuotes:
    def test_formats_speaker_and_text(self):
        quotes = [{"speaker": "Scrooge", "text": "Bah! Humbug!"}]
        result = _format_booknlp_quotes(quotes)
        assert "Scrooge" in result
        assert "Bah! Humbug!" in result

    def test_empty_quotes(self):
        result = _format_booknlp_quotes([])
        assert "no quotes" in result.lower()

    def test_truncates_long_quotes(self):
        quotes = [{"speaker": "X", "text": "a" * 200}]
        result = _format_booknlp_quotes(quotes)
        assert "..." in result

    def test_caps_at_30(self):
        quotes = [{"speaker": f"S{i}", "text": f"Quote {i}"} for i in range(50)]
        result = _format_booknlp_quotes(quotes)
        lines = [l for l in result.split("\n") if l.strip().startswith("-")]
        assert len(lines) == 30

    def test_handles_quote_key_fallback(self):
        """Some BookNLP formats use 'quote' instead of 'text'."""
        quotes = [{"speaker": "Bob", "quote": "Merry Christmas!"}]
        result = _format_booknlp_quotes(quotes)
        assert "Merry Christmas" in result


class TestFormatOntologyClasses:
    def test_from_discovered_entities(self, sample_ontology):
        result = _format_ontology_classes(sample_ontology)
        assert "Character" in result
        assert "Location" in result

    def test_always_includes_core_classes(self, sample_ontology):
        """PlotEvent, Theme, Relationship must always be in ontology classes."""
        result = _format_ontology_classes(sample_ontology)
        assert "PlotEvent" in result
        assert "Theme" in result
        assert "Relationship" in result

    def test_empty_ontology_fallback(self):
        result = _format_ontology_classes({})
        assert "Character" in result

    def test_custom_entity_type_included(self):
        ontology = {"discovered_entities": {"Weapon": [{"name": "Sword", "count": 5}]}}
        result = _format_ontology_classes(ontology)
        assert "Weapon" in result


class TestFormatOntologyRelations:
    def test_from_discovered_relations(self, sample_ontology):
        result = _format_ontology_relations(sample_ontology)
        assert "employs" in result
        assert "haunts" in result
        assert "fears" in result

    def test_empty_relations_fallback(self):
        result = _format_ontology_relations({})
        assert "snake_case" in result

    def test_caps_at_40(self):
        ontology = {
            "discovered_relations": [{"name": f"rel_{i}"} for i in range(60)]
        }
        result = _format_ontology_relations(ontology)
        assert result.count(",") <= 40


# ===================================================================
# Prompt rendering — full render
# ===================================================================

class TestRenderPrompt:
    def test_returns_tuple(self, prompt_file, sample_booknlp, sample_ontology):
        chunk = ChapterChunk(text="The book text.", chapter_numbers=[1, 2], start_char=0, end_char=14)
        result = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_text_input_is_raw_chunk(self, prompt_file, sample_booknlp, sample_ontology):
        """Per Cognee API: text_input should be the raw text, not embedded in prompt."""
        chunk = ChapterChunk(text="The book text.", chapter_numbers=[1], start_char=0, end_char=14)
        _, text_input = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert text_input == "The book text."

    def test_system_prompt_does_not_contain_raw_text(self, prompt_file, sample_booknlp, sample_ontology):
        """Raw book text should NOT be in the system prompt — it goes in text_input."""
        chunk = ChapterChunk(text="UNIQUE_BOOK_TEXT_12345", chapter_numbers=[1], start_char=0, end_char=21)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "UNIQUE_BOOK_TEXT_12345" not in system_prompt

    def test_chapter_numbers_rendered(self, prompt_file, sample_booknlp, sample_ontology):
        chunk = ChapterChunk(text="x", chapter_numbers=[4, 5], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "4, 5" in system_prompt

    def test_ontology_classes_rendered(self, prompt_file, sample_booknlp, sample_ontology):
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "Character" in system_prompt

    def test_ontology_relations_rendered(self, prompt_file, sample_booknlp, sample_ontology):
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "employs" in system_prompt

    def test_booknlp_entities_rendered(self, prompt_file, sample_booknlp, sample_ontology):
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "Scrooge" in system_prompt

    def test_booknlp_quotes_rendered(self, prompt_file, sample_booknlp, sample_ontology):
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "Humbug" in system_prompt

    def test_text_placeholder_replaced(self, prompt_file, sample_booknlp, sample_ontology):
        """{{ text }} should be replaced with redirect message, not left raw."""
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        assert "{{ text }}" not in system_prompt
        assert "user message" in system_prompt.lower() or "see" in system_prompt.lower()

    def test_missing_prompt_file_raises(self):
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        with pytest.raises(FileNotFoundError, match="Extraction prompt template not found"):
            render_prompt(chunk, {}, {}, prompt_path="/nonexistent/path.txt")

    def test_uses_jinja2_not_string_template(self, prompt_file, sample_booknlp, sample_ontology):
        """Prompt uses {{ }} syntax which requires Jinja2, not string.Template."""
        chunk = ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1)
        system_prompt, _ = render_prompt(chunk, sample_booknlp, sample_ontology, prompt_path=str(prompt_file))
        # If Jinja2 rendered correctly, no {{ }} should remain
        assert "{{" not in system_prompt
        assert "}}" not in system_prompt


# ===================================================================
# Task 2: extract_enriched_graph
# ===================================================================

class TestExtractEnrichedGraph:
    @pytest.fixture
    def mock_llm(self, sample_extraction_result):
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock:
            mock.acreate_structured_output = AsyncMock(return_value=sample_extraction_result)
            yield mock

    @pytest.fixture
    def mock_render(self):
        with patch("pipeline.cognee_pipeline.render_prompt", return_value=("system prompt", "text input")):
            yield

    def test_returns_datapoints(self, mock_llm, mock_render):
        chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.run(
            extract_enriched_graph(chunks)
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_actual_datapoint_instances(self, mock_llm, mock_render):
        """Must return DataPoint instances, NOT dicts."""
        from cognee.infrastructure.engine import DataPoint
        chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.run(
            extract_enriched_graph(chunks)
        )
        for dp in result:
            assert isinstance(dp, DataPoint), f"Expected DataPoint, got {type(dp)}"

    def test_uses_extraction_result_model(self, mock_llm, mock_render):
        """LLMGateway must be called with ExtractionResult as response_model."""
        chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
        asyncio.run(
            extract_enriched_graph(chunks)
        )
        call_kwargs = mock_llm.acreate_structured_output.call_args
        # Check response_model is ExtractionResult
        assert call_kwargs.kwargs.get("response_model") is ExtractionResult

    def test_calls_to_datapoints(self, mock_llm, mock_render):
        """Should call ExtractionResult.to_datapoints() — produces Character, Location etc."""
        chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.run(
            extract_enriched_graph(chunks)
        )
        types = {type(dp).__name__ for dp in result}
        assert "Character" in types

    def test_multiple_chunks_aggregated(self, mock_llm, mock_render):
        chunks = [
            ChapterChunk(text="chunk1", chapter_numbers=[1], start_char=0, end_char=6),
            ChapterChunk(text="chunk2", chapter_numbers=[2], start_char=6, end_char=12),
        ]
        result = asyncio.run(
            extract_enriched_graph(chunks)
        )
        assert mock_llm.acreate_structured_output.call_count == 2
        assert len(result) > 0

    def test_retries_on_failure(self, mock_render, sample_extraction_result):
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm:
            mock_llm.acreate_structured_output = AsyncMock(
                side_effect=[Exception("fail"), sample_extraction_result]
            )
            chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
            result = asyncio.run(
                extract_enriched_graph(chunks, max_retries=3)
            )
            assert len(result) > 0
            assert mock_llm.acreate_structured_output.call_count == 2

    def test_all_retries_fail_gracefully(self, mock_render):
        """Per CLAUDE.md: 3 retries then halt. Failed chunks skipped, not crash."""
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm:
            mock_llm.acreate_structured_output = AsyncMock(
                side_effect=Exception("permanent failure")
            )
            chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
            result = asyncio.run(
                extract_enriched_graph(chunks, max_retries=2)
            )
            assert result == []
            assert mock_llm.acreate_structured_output.call_count == 2

    def test_default_max_retries_is_three(self):
        import inspect
        sig = inspect.signature(extract_enriched_graph)
        assert sig.parameters["max_retries"].default == 3

    def test_empty_chunks(self, mock_render):
        result = asyncio.run(
            extract_enriched_graph([])
        )
        assert result == []

    def test_none_booknlp_handled(self, mock_llm, mock_render):
        chunks = [ChapterChunk(text="test", chapter_numbers=[1], start_char=0, end_char=4)]
        result = asyncio.run(
            extract_enriched_graph(chunks, booknlp=None, ontology=None)
        )
        assert isinstance(result, list)

    def test_separates_system_prompt_and_text_input(self, mock_render, sample_extraction_result):
        """LLMGateway should receive system_prompt and text_input as separate args."""
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm:
            mock_llm.acreate_structured_output = AsyncMock(return_value=sample_extraction_result)
            chunks = [ChapterChunk(text="book text here", chapter_numbers=[1], start_char=0, end_char=14)]
            asyncio.run(
                extract_enriched_graph(chunks)
            )
            call_kwargs = mock_llm.acreate_structured_output.call_args.kwargs
            assert "text_input" in call_kwargs
            assert "system_prompt" in call_kwargs
            assert call_kwargs["text_input"] != call_kwargs["system_prompt"]


# ===================================================================
# Batch artifact saving
# ===================================================================

class TestSaveBatchArtifacts:
    def test_saves_input_text(self, sample_batch, tmp_path):
        _save_batch_artifacts(sample_batch, {}, [], tmp_path)
        input_path = tmp_path / "batch_01" / "input_text.txt"
        assert input_path.exists()
        assert input_path.read_text() == sample_batch.combined_text

    def test_saves_annotations_json(self, sample_batch, sample_booknlp, tmp_path):
        _save_batch_artifacts(sample_batch, sample_booknlp, [], tmp_path)
        ann_path = tmp_path / "batch_01" / "annotations.json"
        assert ann_path.exists()
        data = json.loads(ann_path.read_text())
        assert data["chapter_numbers"] == [1, 2, 3]
        assert "entities" in data
        assert "quotes" in data

    def test_saves_extracted_datapoints_json(self, sample_batch, tmp_path):
        char = Character(name="Scrooge", first_chapter=1)
        _save_batch_artifacts(sample_batch, {}, [char], tmp_path)
        dp_path = tmp_path / "batch_01" / "extracted_datapoints.json"
        assert dp_path.exists()
        data = json.loads(dp_path.read_text())
        assert len(data) == 1

    def test_batch_dir_named_by_first_chapter(self, tmp_path):
        batch = Batch(chapter_numbers=[4, 5, 6], texts=["a"], combined_text="a")
        _save_batch_artifacts(batch, {}, [], tmp_path)
        assert (tmp_path / "batch_04").exists()

    def test_all_three_files_per_spec(self, sample_batch, sample_booknlp, tmp_path):
        """Per CLAUDE.md output structure: input_text.txt, annotations.json, extracted_datapoints.json."""
        char = Character(name="Test", first_chapter=1)
        _save_batch_artifacts(sample_batch, sample_booknlp, [char], tmp_path)
        batch_dir = tmp_path / "batch_01"
        assert (batch_dir / "input_text.txt").exists()
        assert (batch_dir / "annotations.json").exists()
        assert (batch_dir / "extracted_datapoints.json").exists()

    def test_empty_datapoints_saves_empty_list(self, sample_batch, tmp_path):
        _save_batch_artifacts(sample_batch, {}, [], tmp_path)
        dp_path = tmp_path / "batch_01" / "extracted_datapoints.json"
        data = json.loads(dp_path.read_text())
        assert data == []


# ===================================================================
# run_bookrag_pipeline — integration
# ===================================================================

class TestValidateRelationships:
    """Plan 2 — extraction-time triplet validation.

    The LLM occasionally emits relationships whose source or target names
    don't match any extracted Character/Location/Faction in the same
    batch (hallucinated endpoint), or emits the same (src, rel, tgt)
    triple twice with slightly different descriptions. The retrieval-
    time spoiler filter catches the former but near-duplicates still
    reach disk. Validate at extraction time so persisted artifacts stay
    clean.

    Invariants pinned below:
      1. If source_name or target_name doesn't match any extracted
         Character/Location/Faction in the same ExtractionResult, the
         relationship is dropped.
      2. Duplicate (source_name, relation_type, target_name) triples are
         deduplicated; when there's a choice, keep the one with the
         longer description (more information-dense).
    """

    def _make_character(self, name, first_chapter=1):
        from models.datapoints import CharacterExtraction
        return CharacterExtraction(name=name, first_chapter=first_chapter)

    def _make_relationship(self, src, tgt, rel, description=None, first_chapter=1):
        from models.datapoints import RelationshipExtraction
        return RelationshipExtraction(
            source_name=src, target_name=tgt, relation_type=rel,
            description=description, first_chapter=first_chapter,
        )

    def _make_extraction(self, characters=None, relationships=None):
        from models.datapoints import ExtractionResult
        return ExtractionResult(
            characters=characters or [],
            relationships=relationships or [],
        )

    def test_valid_relationship_passes_through(self):
        from pipeline.cognee_pipeline import _validate_relationships

        ext = self._make_extraction(
            characters=[self._make_character("Scrooge"), self._make_character("Marley")],
            relationships=[self._make_relationship("Scrooge", "Marley", "was_partner_of")],
        )
        result = _validate_relationships(ext)
        assert len(result.relationships) == 1

    def test_orphan_source_is_dropped(self):
        from pipeline.cognee_pipeline import _validate_relationships

        ext = self._make_extraction(
            characters=[self._make_character("Marley")],
            # Scrooge is not in the extracted characters — orphan
            relationships=[self._make_relationship("Scrooge", "Marley", "was_partner_of")],
        )
        result = _validate_relationships(ext)
        assert result.relationships == [], (
            f"orphan-source relationship must be dropped; got {result.relationships}"
        )

    def test_orphan_target_is_dropped(self):
        from pipeline.cognee_pipeline import _validate_relationships

        ext = self._make_extraction(
            characters=[self._make_character("Scrooge")],
            # Marley not extracted
            relationships=[self._make_relationship("Scrooge", "Marley", "was_partner_of")],
        )
        result = _validate_relationships(ext)
        assert result.relationships == []

    def test_duplicate_keeps_longest_description(self):
        from pipeline.cognee_pipeline import _validate_relationships

        ext = self._make_extraction(
            characters=[self._make_character("Scrooge"), self._make_character("Marley")],
            relationships=[
                self._make_relationship("Scrooge", "Marley", "was_partner_of",
                                         description="Short desc."),
                self._make_relationship("Scrooge", "Marley", "was_partner_of",
                                         description="A much longer description with more information about this long-time partnership."),
                self._make_relationship("Scrooge", "Marley", "was_partner_of",
                                         description="Medium length description."),
            ],
        )
        result = _validate_relationships(ext)
        assert len(result.relationships) == 1
        assert "longer description" in (result.relationships[0].description or ""), (
            f"must keep the longest description; got {result.relationships[0].description}"
        )

    def test_duplicate_when_all_none_descriptions_keeps_one(self):
        """Edge: if both duplicates have description=None, still dedupe to one."""
        from pipeline.cognee_pipeline import _validate_relationships

        ext = self._make_extraction(
            characters=[self._make_character("A"), self._make_character("B")],
            relationships=[
                self._make_relationship("A", "B", "knows", description=None),
                self._make_relationship("A", "B", "knows", description=None),
            ],
        )
        result = _validate_relationships(ext)
        assert len(result.relationships) == 1

    def test_locations_count_as_valid_endpoints(self):
        """The ontology allows some Relationships between a Character and a
        Location (e.g. Character owns Location). Treat Locations, Factions,
        and Characters as valid endpoints."""
        from pipeline.cognee_pipeline import _validate_relationships
        from models.datapoints import LocationExtraction, ExtractionResult

        ext = ExtractionResult(
            characters=[self._make_character("Scrooge")],
            locations=[LocationExtraction(name="Counting House", first_chapter=1)],
            relationships=[self._make_relationship("Scrooge", "Counting House", "owns")],
        )
        result = _validate_relationships(ext)
        assert len(result.relationships) == 1

    def test_no_relationships_input_is_noop(self):
        from pipeline.cognee_pipeline import _validate_relationships

        ext = self._make_extraction(
            characters=[self._make_character("Scrooge")],
            relationships=[],
        )
        result = _validate_relationships(ext)
        assert result.relationships == []
        assert len(result.characters) == 1, "validator must not touch characters"


class TestRunBookragPipeline:
    @pytest.fixture
    def mock_everything(self, sample_extraction_result):
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
             patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "text")), \
             patch("pipeline.cognee_pipeline.run_pipeline") as mock_pipeline, \
             patch("pipeline.cognee_pipeline.Task"):
            mock_llm.acreate_structured_output = AsyncMock(return_value=sample_extraction_result)

            async def empty_pipeline(**kwargs):
                return
                yield  # make it an async generator

            mock_pipeline.return_value = empty_pipeline()
            yield {"llm": mock_llm, "pipeline": mock_pipeline}

    def test_returns_datapoints(self, mock_everything, sample_batch, sample_booknlp, sample_ontology, tmp_path):
        result = asyncio.run(
            run_bookrag_pipeline(
                batch=sample_batch, booknlp_output=sample_booknlp,
                ontology=sample_ontology, book_id="christmas_carol",
                output_dir=tmp_path / "batches",
            )
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_saves_batch_artifacts(self, mock_everything, sample_batch, sample_booknlp, sample_ontology, tmp_path):
        asyncio.run(
            run_bookrag_pipeline(
                batch=sample_batch, booknlp_output=sample_booknlp,
                ontology=sample_ontology, book_id="christmas_carol",
                output_dir=tmp_path / "batches",
            )
        )
        batch_dir = tmp_path / "batches" / "batch_01"
        assert (batch_dir / "input_text.txt").exists()
        assert (batch_dir / "annotations.json").exists()
        assert (batch_dir / "extracted_datapoints.json").exists()

    def test_default_output_dir(self, mock_everything, sample_batch, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        asyncio.run(
            run_bookrag_pipeline(
                batch=sample_batch, booknlp_output={},
                ontology={}, book_id="test_book",
            )
        )
        expected = tmp_path / "data" / "processed" / "test_book" / "batches" / "batch_01"
        assert expected.exists()

    def test_function_signature(self):
        import inspect
        sig = inspect.signature(run_bookrag_pipeline)
        params = set(sig.parameters.keys())
        for p in ["batch", "booknlp_output", "ontology", "book_id", "chunk_size", "max_retries", "output_dir"]:
            assert p in params, f"Missing parameter: {p}"

    def test_chunk_size_default(self):
        import inspect
        sig = inspect.signature(run_bookrag_pipeline)
        assert sig.parameters["chunk_size"].default == 1500

    def test_max_retries_default(self):
        import inspect
        sig = inspect.signature(run_bookrag_pipeline)
        assert sig.parameters["max_retries"].default == 3

    # --- Plan 2 — triplet embedding wiring ---------------------------

    def test_embed_triplets_param_exists_and_defaults_false(self):
        """Plan 2: run_bookrag_pipeline accepts embed_triplets and it
        defaults to False so existing callers remain backward compatible.
        The orchestrator flips the default via BookRAGConfig.embed_triplets."""
        import inspect
        sig = inspect.signature(run_bookrag_pipeline)
        assert "embed_triplets" in sig.parameters
        assert sig.parameters["embed_triplets"].default is False

    def test_embed_triplets_true_is_forwarded_to_add_data_points_task(
        self, sample_extraction_result, sample_batch, sample_booknlp,
        sample_ontology, tmp_path
    ):
        """When embed_triplets=True is passed, the Task constructor that
        wraps add_data_points must receive embed_triplets=True as a kwarg.

        Verified by patching Task to a recording MagicMock and inspecting
        its call args after run_bookrag_pipeline completes."""
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
             patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "text")), \
             patch("pipeline.cognee_pipeline.run_pipeline") as mock_pipeline, \
             patch("pipeline.cognee_pipeline.Task") as mock_task:
            mock_llm.acreate_structured_output = AsyncMock(return_value=sample_extraction_result)

            async def empty_pipeline(**kwargs):
                return
                yield
            mock_pipeline.return_value = empty_pipeline()

            asyncio.run(
                run_bookrag_pipeline(
                    batch=sample_batch, booknlp_output=sample_booknlp,
                    ontology=sample_ontology, book_id="christmas_carol",
                    output_dir=tmp_path / "batches",
                    embed_triplets=True,
                )
            )

            # Task was called with add_data_points + embed_triplets=True
            assert mock_task.called, "Task constructor must be invoked"
            call_args = mock_task.call_args
            assert call_args.kwargs.get("embed_triplets") is True, (
                f"Task must be constructed with embed_triplets=True; got "
                f"args={call_args.args}, kwargs={call_args.kwargs}"
            )

    def test_embed_triplets_default_false_is_forwarded(
        self, sample_extraction_result, sample_batch, sample_booknlp,
        sample_ontology, tmp_path
    ):
        """When the caller omits embed_triplets, the Task must still
        receive an explicit embed_triplets=False (not absent)."""
        with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
             patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "text")), \
             patch("pipeline.cognee_pipeline.run_pipeline") as mock_pipeline, \
             patch("pipeline.cognee_pipeline.Task") as mock_task:
            mock_llm.acreate_structured_output = AsyncMock(return_value=sample_extraction_result)

            async def empty_pipeline(**kwargs):
                return
                yield
            mock_pipeline.return_value = empty_pipeline()

            asyncio.run(
                run_bookrag_pipeline(
                    batch=sample_batch, booknlp_output=sample_booknlp,
                    ontology=sample_ontology, book_id="christmas_carol",
                    output_dir=tmp_path / "batches",
                )
            )

            call_args = mock_task.call_args
            assert call_args.kwargs.get("embed_triplets") is False


# ===================================================================
# Spec alignment
# ===================================================================

class TestSpecAlignment:
    def test_uses_models_datapoints_extraction_result(self):
        """Must use ExtractionResult from models/datapoints.py, not a local one."""
        from pipeline.cognee_pipeline import ExtractionResult as PipelineER
        from models.datapoints import ExtractionResult as ModelsER
        assert PipelineER is ModelsER

    def test_no_local_entity_node_class(self):
        """The old generic EntityNode/RelationEdge should not exist."""
        import pipeline.cognee_pipeline as mod
        assert not hasattr(mod, "EntityNode")
        assert not hasattr(mod, "RelationEdge")

    def test_pipeline_has_three_stages(self):
        """Per spec: chunk, extract, add_data_points."""
        assert callable(chunk_with_chapter_awareness)
        assert asyncio.iscoroutinefunction(extract_enriched_graph)
        assert asyncio.iscoroutinefunction(run_bookrag_pipeline)

    def test_imports_from_cognee(self):
        """Pipeline must import from cognee for DataPoint, LLMGateway, Task, etc."""
        import pipeline.cognee_pipeline as mod
        source = Path(mod.__file__).read_text()
        assert "from cognee" in source
        assert "LLMGateway" in source
        assert "add_data_points" in source
        assert "DataPoint" in source
