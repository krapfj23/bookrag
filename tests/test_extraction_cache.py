"""Content-addressed extraction cache — Phase A Stage 1.5 / Item 12.

Unit tests for the cache helpers + integration tests that prove:
- Cache hit skips the LLM call entirely
- Any input change invalidates the cached entry
- Cache write is atomic and non-fatal on failure
- Cache disabled preserves current behavior exactly
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# -------------------------------------------------------------------------
# Unit tests on the pure key-computation and I/O helpers
# -------------------------------------------------------------------------


def test_compute_cache_key_deterministic():
    from pipeline.cognee_pipeline import _compute_cache_key
    args = dict(
        prompt_hash="a", model_id="m", schema_version="v1",
        ontology_hash="o", chunk_text_hash="t", max_gleanings=0,
    )
    assert _compute_cache_key(**args) == _compute_cache_key(**args)


@pytest.mark.parametrize("field", [
    "prompt_hash", "model_id", "schema_version",
    "ontology_hash", "chunk_text_hash",
])
def test_compute_cache_key_sensitive_to_each_field(field):
    from pipeline.cognee_pipeline import _compute_cache_key
    base = dict(
        prompt_hash="a", model_id="m", schema_version="v1",
        ontology_hash="o", chunk_text_hash="t", max_gleanings=0,
    )
    mutated = dict(base); mutated[field] = base[field] + "-changed"
    assert _compute_cache_key(**base) != _compute_cache_key(**mutated)


def test_compute_cache_key_sensitive_to_max_gleanings():
    from pipeline.cognee_pipeline import _compute_cache_key
    base = dict(
        prompt_hash="a", model_id="m", schema_version="v1",
        ontology_hash="o", chunk_text_hash="t", max_gleanings=0,
    )
    mutated = dict(base); mutated["max_gleanings"] = 1
    assert _compute_cache_key(**base) != _compute_cache_key(**mutated)


def test_cache_read_missing_returns_none(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import _cache_read
    monkeypatch.setenv("BOOKRAG_EXTRACTION_CACHE_DIR", str(tmp_path))
    assert _cache_read("nonexistent") is None


def test_cache_write_then_read_roundtrip(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import _cache_read, _cache_write
    from models.datapoints import ExtractionResult, CharacterExtraction
    monkeypatch.setenv("BOOKRAG_EXTRACTION_CACHE_DIR", str(tmp_path))

    original = ExtractionResult(
        characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
        cache_key="abc",
    )
    _cache_write("abc", original)
    loaded = _cache_read("abc")
    assert loaded is not None
    assert loaded.characters[0].name == "Scrooge"
    assert loaded.cache_key == "abc"


def test_cache_write_is_atomic_uses_rename(tmp_path, monkeypatch):
    """No partial file should be visible if a write fails mid-flush."""
    from pipeline.cognee_pipeline import _cache_write
    from models.datapoints import ExtractionResult
    monkeypatch.setenv("BOOKRAG_EXTRACTION_CACHE_DIR", str(tmp_path))

    _cache_write("good", ExtractionResult(cache_key="good"))
    final_path = tmp_path / "good.json"
    assert final_path.exists()
    # No .tmp leftover
    assert list(tmp_path.glob("*.tmp")) == []


def test_cache_write_failure_is_swallowed(tmp_path, monkeypatch):
    """Cache failures must never break extraction."""
    from pipeline.cognee_pipeline import _cache_write
    from models.datapoints import ExtractionResult

    # Point cache dir at a file (not a dir) so mkdir/write fails.
    bad = tmp_path / "not_a_dir"
    bad.write_text("x")
    monkeypatch.setenv("BOOKRAG_EXTRACTION_CACHE_DIR", str(bad))
    # Should not raise
    _cache_write("x", ExtractionResult(cache_key="x"))


def test_cache_read_unparseable_returns_none(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import _cache_read
    monkeypatch.setenv("BOOKRAG_EXTRACTION_CACHE_DIR", str(tmp_path))
    (tmp_path / "corrupt.json").write_text("not json")
    assert _cache_read("corrupt") is None


def test_hash_ontology_order_independent():
    from pipeline.cognee_pipeline import _hash_ontology
    a = {"entities": ["A", "B"], "relations": ["x"]}
    b = {"relations": ["x"], "entities": ["A", "B"]}
    assert _hash_ontology(a) == _hash_ontology(b)


def test_stamp_extraction_metadata_fills_fields():
    from pipeline.cognee_pipeline import _stamp_extraction_metadata
    from models.datapoints import ExtractionResult
    er = ExtractionResult()
    _stamp_extraction_metadata(er, prompt_hash="p", model_id="m", cache_key="k")
    assert er.prompt_hash == "p"
    assert er.model_id == "m"
    assert er.cache_key == "k"
    assert er.schema_version == "v1"
    assert er.extractor_version.startswith("phase-a@")
    assert er.created_at is not None


# -------------------------------------------------------------------------
# Integration: cache hit skips the LLM
# -------------------------------------------------------------------------


def _setup_cache_env(tmp_path, monkeypatch, enabled: bool = True):
    """Point cache at tmp_path + force config flag on/off."""
    monkeypatch.setenv("BOOKRAG_EXTRACTION_CACHE_DIR", str(tmp_path))

    class _Cfg:
        llm_provider = "openai"
        llm_model = "gpt-4o-mini"
        extraction_cache_enabled = enabled

    import models.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load_config", lambda: _Cfg())


def test_cache_hit_skips_llm(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk
    from models.datapoints import ExtractionResult, CharacterExtraction

    _setup_cache_env(tmp_path, monkeypatch, enabled=True)

    chunks = [
        ChapterChunk(text="hello", chapter_numbers=[1], start_char=0, end_char=5, ordinal=0),
    ]
    llm_call_count = 0

    async def fake_llm(*args, **kwargs):
        nonlocal llm_call_count
        llm_call_count += 1
        return ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
        )

    with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
         patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "user")):
        mock_llm.acreate_structured_output = fake_llm
        # First call — cache miss, LLM invoked once.
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={}))
        # Second call — cache hit, LLM must not be invoked again.
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={}))

    assert llm_call_count == 1, f"expected 1 LLM call (second was cached), got {llm_call_count}"


def test_cache_disabled_always_calls_llm(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk
    from models.datapoints import ExtractionResult

    _setup_cache_env(tmp_path, monkeypatch, enabled=False)

    chunks = [
        ChapterChunk(text="hello", chapter_numbers=[1], start_char=0, end_char=5, ordinal=0),
    ]
    call_count = 0

    async def fake_llm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ExtractionResult()

    with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
         patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "user")):
        mock_llm.acreate_structured_output = fake_llm
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={}))
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={}))

    assert call_count == 2


def test_cache_invalidated_by_chunk_text_change(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk
    from models.datapoints import ExtractionResult

    _setup_cache_env(tmp_path, monkeypatch, enabled=True)

    call_count = 0

    async def fake_llm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ExtractionResult()

    chunk_v1 = ChapterChunk(text="original", chapter_numbers=[1], start_char=0, end_char=8, ordinal=0)
    chunk_v2 = ChapterChunk(text="changed", chapter_numbers=[1], start_char=0, end_char=7, ordinal=0)

    with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
         patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "user")):
        mock_llm.acreate_structured_output = fake_llm
        asyncio.run(extract_enriched_graph(chunks=[chunk_v1], booknlp={}, ontology={}))
        asyncio.run(extract_enriched_graph(chunks=[chunk_v2], booknlp={}, ontology={}))

    assert call_count == 2


def test_cache_invalidated_by_ontology_change(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk
    from models.datapoints import ExtractionResult

    _setup_cache_env(tmp_path, monkeypatch, enabled=True)

    call_count = 0

    async def fake_llm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ExtractionResult()

    chunks = [ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1, ordinal=0)]

    with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
         patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "user")):
        mock_llm.acreate_structured_output = fake_llm
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={"v": 1}))
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={"v": 2}))

    assert call_count == 2


def test_cache_invalidated_by_max_gleanings_change(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk
    from models.datapoints import ExtractionResult

    _setup_cache_env(tmp_path, monkeypatch, enabled=True)
    call_count = 0

    async def fake_llm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return ExtractionResult()

    chunks = [ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1, ordinal=0)]

    with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
         patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "user")):
        mock_llm.acreate_structured_output = fake_llm
        # max_gleanings=0 → 1 call
        asyncio.run(extract_enriched_graph(
            chunks=chunks, booknlp={}, ontology={}, max_gleanings=0,
        ))
        # max_gleanings=1 → cache miss + 2 calls (first + 1 gleaning)
        asyncio.run(extract_enriched_graph(
            chunks=chunks, booknlp={}, ontology={}, max_gleanings=1,
        ))

    assert call_count == 3


def test_cache_stamps_metadata_on_write(tmp_path, monkeypatch):
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk
    from models.datapoints import ExtractionResult

    _setup_cache_env(tmp_path, monkeypatch, enabled=True)

    async def fake_llm(*args, **kwargs):
        return ExtractionResult()

    chunks = [ChapterChunk(text="x", chapter_numbers=[1], start_char=0, end_char=1, ordinal=0)]

    with patch("pipeline.cognee_pipeline.LLMGateway") as mock_llm, \
         patch("pipeline.cognee_pipeline.render_prompt", return_value=("sys", "user")):
        mock_llm.acreate_structured_output = fake_llm
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={}))

    # Exactly one cache file; inspect its metadata.
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["cache_key"]
    assert payload["prompt_hash"]
    assert payload["model_id"] == "openai/gpt-4o-mini"
    assert payload["schema_version"] == "v1"
    assert payload["extractor_version"].startswith("phase-a@")
    assert payload["created_at"] is not None
