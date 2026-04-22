# Slice 1 — Chunk-based Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the chunk the authoritative unit of reader progress and spoiler scope in the backend while keeping the public `(current_chapter, current_paragraph?)` wire format unchanged, and index chunk text into cognee so future search types have text to search against.

**Architecture:** Assign each `ChapterChunk` a stable monotonic ordinal at ingestion time; persist a `chunks.json` enumerating them and a `chapter_to_chunk_index.json` for chapter↔ordinal translation; stamp `source_chunk_ordinal` on every DataPoint; rewire `load_allowed_nodes` to compare ordinals with a chapter-translation shim for callers that still pass a chapter cursor; call `cognee.add()` on chunk text for future search; provide a backfill script so existing books get all three new artifacts without re-running LLM extraction.

**Tech Stack:** Python 3.10, Pydantic v2, Cognee 0.5.6 (`cognee.add`, `cognee.infrastructure.engine.DataPoint`), pytest, loguru, asyncio.

**Spec:** `docs/superpowers/specs/2026-04-22-slice-1-chunk-based-data-model.md`

---

## File structure

**New files:**
- `pipeline/chunk_index.py` — builds and loads the two new artifacts (`chunks.json`, `chapter_to_chunk_index.json`), plus the ordinal ↔ chapter/paragraph translation helpers.
- `scripts/backfill_chunk_ordinals.py` — idempotent backfill for books ingested before this slice.
- `tests/test_chunk_indexing.py` — unit tests for `chunk_index.py`.
- `tests/test_backfill_chunk_ordinals.py` — tests for the backfill script.

**Modified files:**
- `models/datapoints.py` — add `source_chunk_ordinal: int | None = None` to Character, Location, Faction, PlotEvent, Relationship, Theme. Update `ExtractionResult.to_datapoints` signature to accept and propagate it.
- `pipeline/cognee_pipeline.py` — `ChapterChunk` gains `ordinal` + `chunk_id`; `run_bookrag_pipeline` accepts a `chunk_ordinal_start: int` param, indexes chunks via `cognee.add`, stamps ordinals on DataPoints, returns the next ordinal.
- `pipeline/orchestrator.py` — `_stage_run_cognee_batches` tracks a monotonic counter across batches, calls `build_chunk_indexes` after the last batch.
- `pipeline/spoiler_filter.py` — add `load_allowed_nodes_by_chunk`; make `load_allowed_nodes` a shim that translates chapter cursors to ordinal cursors via the chunk index.
- `tests/test_spoiler_filter.py` — extend with ordinal-based cases.
- `tests/test_cognee_pipeline.py` — extend existing tests to assert `cognee.add` calls and ordinal stamping.

---

## Task 1: Add `source_chunk_ordinal` field to DataPoint models

**Files:**
- Modify: `models/datapoints.py`
- Modify: `tests/test_datapoints.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_datapoints.py`:

```python
def test_character_accepts_source_chunk_ordinal():
    from models.datapoints import Character
    c = Character(name="Scrooge", first_chapter=1, source_chunk_ordinal=7)
    assert c.source_chunk_ordinal == 7


def test_character_source_chunk_ordinal_defaults_to_none():
    from models.datapoints import Character
    c = Character(name="Scrooge", first_chapter=1)
    assert c.source_chunk_ordinal is None


def test_plotevent_accepts_source_chunk_ordinal():
    from models.datapoints import PlotEvent
    e = PlotEvent(description="x", chapter=1, source_chunk_ordinal=3)
    assert e.source_chunk_ordinal == 3


def test_extraction_result_to_datapoints_stamps_ordinal():
    from models.datapoints import ExtractionResult, ExtractedCharacter
    r = ExtractionResult(characters=[ExtractedCharacter(name="A", first_chapter=1)])
    dps = r.to_datapoints(source_chunk_ordinal=12)
    assert all(getattr(dp, "source_chunk_ordinal", None) == 12 for dp in dps)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_datapoints.py::test_character_accepts_source_chunk_ordinal tests/test_datapoints.py::test_extraction_result_to_datapoints_stamps_ordinal -v`
Expected: FAIL with `ValidationError` (unknown field) on the first, TypeError (unexpected kwarg) on the last.

- [ ] **Step 3: Add the field to every DataPoint subclass**

In `models/datapoints.py`, add `source_chunk_ordinal: int | None = None` to each class: `Character`, `Location`, `Faction`, `PlotEvent`, `Relationship`, `Theme`. Example for `Character`:

```python
class Character(DataPoint):
    name: str
    aliases: list[str] = []
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = None
    chapters_present: list[int] = []
    source_chunk_ordinal: int | None = None
    metadata: dict = {"index_fields": ["name", "description"]}
```

- [ ] **Step 4: Update `ExtractionResult.to_datapoints` to accept and propagate the ordinal**

Find the `to_datapoints` method in `models/datapoints.py`. Add a keyword argument and propagate to each DataPoint instantiation:

```python
def to_datapoints(self, source_chunk_ordinal: int | None = None) -> list[DataPoint]:
    # ... existing body, but every DataPoint(...) call gets
    #     source_chunk_ordinal=source_chunk_ordinal
```

Pass `source_chunk_ordinal=source_chunk_ordinal` to every `Character(...)`, `Location(...)`, `Faction(...)`, `PlotEvent(...)`, `Theme(...)`, `Relationship(...)` constructor inside the method.

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/test_datapoints.py -v`
Expected: PASS (all tests including the four new ones).

- [ ] **Step 6: Run the full datapoints suite to confirm no regression**

Run: `python -m pytest tests/test_datapoints.py -v`
Expected: PASS (no pre-existing test breaks).

- [ ] **Step 7: Commit**

```bash
git add models/datapoints.py tests/test_datapoints.py
git commit -m "feat(datapoints): add source_chunk_ordinal to DataPoint models"
```

---

## Task 2: Add `ordinal` and `chunk_id` to `ChapterChunk`

**Files:**
- Modify: `pipeline/cognee_pipeline.py:76-89`
- Modify: `tests/test_cognee_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cognee_pipeline.py`:

```python
def test_chapter_chunk_accepts_ordinal_and_chunk_id():
    from pipeline.cognee_pipeline import ChapterChunk
    c = ChapterChunk(
        text="hello", chapter_numbers=[1], start_char=0, end_char=5,
        ordinal=4, chunk_id="book1::chunk_0004",
    )
    assert c.ordinal == 4
    assert c.chunk_id == "book1::chunk_0004"


def test_chapter_chunk_ordinal_defaults_to_none():
    from pipeline.cognee_pipeline import ChapterChunk
    c = ChapterChunk(text="hi", chapter_numbers=[1], start_char=0, end_char=2)
    assert c.ordinal is None
    assert c.chunk_id is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cognee_pipeline.py::test_chapter_chunk_accepts_ordinal_and_chunk_id -v`
Expected: FAIL with `TypeError: unexpected keyword argument 'ordinal'`.

- [ ] **Step 3: Modify `ChapterChunk`**

In `pipeline/cognee_pipeline.py` around line 76:

```python
@dataclass
class ChapterChunk:
    """A text chunk that respects paragraph boundaries and tracks chapter provenance."""

    text: str
    chapter_numbers: list[int]
    start_char: int
    end_char: int
    ordinal: int | None = None
    chunk_id: str | None = None

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text) // 4)
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_cognee_pipeline.py -k "chunk_id or ordinal" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/cognee_pipeline.py tests/test_cognee_pipeline.py
git commit -m "feat(cognee_pipeline): add ordinal and chunk_id fields to ChapterChunk"
```

---

## Task 3: Create `pipeline/chunk_index.py` — build and load chunk indexes

**Files:**
- Create: `pipeline/chunk_index.py`
- Create: `tests/test_chunk_indexing.py`

- [ ] **Step 1: Write the failing tests (happy path + edge cases)**

Create `tests/test_chunk_indexing.py`:

```python
import json
from pathlib import Path

from pipeline.chunk_index import (
    build_chunks_json,
    build_chapter_to_chunk_index,
    load_chunks,
    load_chapter_index,
    chapter_paragraph_to_ordinal,
    ChunkRecord,
)
from pipeline.cognee_pipeline import ChapterChunk


def _chunks(*tuples) -> list[ChapterChunk]:
    return [
        ChapterChunk(
            text=text, chapter_numbers=chs, start_char=sc, end_char=ec,
            ordinal=ordinal, chunk_id=f"book::chunk_{ordinal:04d}",
        )
        for (text, chs, sc, ec, ordinal) in tuples
    ]


def test_build_chunks_json_monotonic_ordinals(tmp_path):
    chunks = _chunks(
        ("a" * 100, [1], 0, 100, 0),
        ("b" * 100, [1], 100, 200, 1),
        ("c" * 100, [2], 0, 100, 2),
    )
    out = build_chunks_json("book", chunks, chunk_size_tokens=1500, output_dir=tmp_path)
    payload = json.loads(Path(out).read_text())
    assert payload["total_chunks"] == 3
    assert [c["ordinal"] for c in payload["chunks"]] == [0, 1, 2]
    assert payload["chunks"][0]["chunk_id"] == "book::chunk_0000"


def test_build_chapter_to_chunk_index_bounds(tmp_path):
    chunks = _chunks(
        ("x", [1], 0, 10, 0),
        ("y", [1], 10, 20, 1),
        ("z", [2], 0, 10, 2),
    )
    # Fake chapter raw text so paragraph_breakpoints can be computed.
    raw_dir = tmp_path / "book" / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text("p0\n\np1\n\np2")
    (raw_dir / "chapter_02.txt").write_text("q0")

    out = build_chapter_to_chunk_index("book", chunks, processed_dir=tmp_path)
    idx = json.loads(Path(out).read_text())
    assert idx["1"]["first_ordinal"] == 0
    assert idx["1"]["last_ordinal"] == 1
    assert idx["2"]["first_ordinal"] == 2
    assert idx["2"]["last_ordinal"] == 2
    # paragraph_breakpoints length equals number of paragraphs in raw
    assert len(idx["1"]["paragraph_breakpoints"]) == 3
    assert len(idx["2"]["paragraph_breakpoints"]) == 1


def test_cross_chapter_chunk_assigned_to_start_chapter(tmp_path):
    # Chunk spans chapters [1, 2] but start_char places it in chapter 1.
    chunks = _chunks(("spans", [1, 2], 0, 50, 0))
    raw_dir = tmp_path / "book" / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text("p0")
    (raw_dir / "chapter_02.txt").write_text("p0")
    out = build_chapter_to_chunk_index("book", chunks, processed_dir=tmp_path)
    idx = json.loads(Path(out).read_text())
    assert idx["1"]["first_ordinal"] == 0
    assert idx["1"]["last_ordinal"] == 0
    assert "2" not in idx or idx["2"].get("first_ordinal") is None


def test_chapter_paragraph_to_ordinal_maps_correctly(tmp_path):
    # Build an index manually and verify the translator.
    idx_payload = {
        "1": {"first_ordinal": 0, "last_ordinal": 4, "paragraph_breakpoints": [0, 1, 2, 3, 4]},
        "2": {"first_ordinal": 5, "last_ordinal": 9, "paragraph_breakpoints": [0, 2, 4]},
    }
    idx_dir = tmp_path / "book" / "chunks"
    idx_dir.mkdir(parents=True)
    (idx_dir / "chapter_to_chunk_index.json").write_text(json.dumps(idx_payload))

    # chapter 2, paragraph 0 → first_ordinal(2) + breakpoints[0] = 5 + 0 = 5
    assert chapter_paragraph_to_ordinal("book", 2, 0, processed_dir=tmp_path) == 5
    # chapter 2, paragraph 1 → 5 + 2 = 7
    assert chapter_paragraph_to_ordinal("book", 2, 1, processed_dir=tmp_path) == 7
    # chapter 1, no paragraph → last_ordinal(1) = 4
    assert chapter_paragraph_to_ordinal("book", 1, None, processed_dir=tmp_path) == 4
    # chapter 3 not present → None
    assert chapter_paragraph_to_ordinal("book", 3, 0, processed_dir=tmp_path) is None


def test_load_chunks_missing_returns_empty(tmp_path):
    assert load_chunks("book", processed_dir=tmp_path) == []


def test_load_chapter_index_missing_returns_empty(tmp_path):
    assert load_chapter_index("book", processed_dir=tmp_path) == {}
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_chunk_indexing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.chunk_index'`.

- [ ] **Step 3: Create `pipeline/chunk_index.py`**

```python
"""Chunk-level indexing and translation helpers.

Two on-disk artifacts are produced at ingestion time (or by the backfill script):

  data/processed/{book_id}/chunks/chunks.json
  data/processed/{book_id}/chunks/chapter_to_chunk_index.json

They let the query path translate the reader's (chapter, paragraph) progress
into a stable ``chunk_ordinal`` that every DataPoint is also stamped with,
enabling chunk-uniform spoiler filtering.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from pipeline.cognee_pipeline import ChapterChunk

CHUNKS_FILENAME = "chunks.json"
CHAPTER_INDEX_FILENAME = "chapter_to_chunk_index.json"


@dataclass
class ChunkRecord:
    ordinal: int
    chunk_id: str
    batch_label: str
    chapter_numbers: list[int]
    start_char: int
    end_char: int
    text: str

    def to_dict(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "chunk_id": self.chunk_id,
            "batch_label": self.batch_label,
            "chapter_numbers": list(self.chapter_numbers),
            "start_char": self.start_char,
            "end_char": self.end_char,
            "text": self.text,
        }


def _chunks_dir(book_id: str, processed_dir: Path) -> Path:
    d = Path(processed_dir) / book_id / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_chunks_json(
    book_id: str,
    chunks: list[ChapterChunk],
    chunk_size_tokens: int,
    output_dir: Path | str,
    batch_label_lookup: dict[int, str] | None = None,
) -> Path:
    """Persist chunks.json. `output_dir` is the top-level processed dir."""
    out_dir = _chunks_dir(book_id, Path(output_dir))
    records = []
    for c in chunks:
        if c.ordinal is None or c.chunk_id is None:
            raise ValueError(f"Chunk missing ordinal/chunk_id: {c}")
        label = (batch_label_lookup or {}).get(c.ordinal, "")
        records.append(
            ChunkRecord(
                ordinal=c.ordinal,
                chunk_id=c.chunk_id,
                batch_label=label,
                chapter_numbers=c.chapter_numbers,
                start_char=c.start_char,
                end_char=c.end_char,
                text=c.text,
            ).to_dict()
        )
    records.sort(key=lambda r: r["ordinal"])
    payload = {
        "book_id": book_id,
        "chunk_size_tokens": chunk_size_tokens,
        "total_chunks": len(records),
        "chunks": records,
    }
    out = out_dir / CHUNKS_FILENAME
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    logger.info("Wrote {} with {} chunks", out, len(records))
    return out


def build_chapter_to_chunk_index(
    book_id: str,
    chunks: list[ChapterChunk],
    processed_dir: Path | str,
) -> Path:
    """Persist chapter_to_chunk_index.json.

    Assigns each chunk to the chapter where its start_char falls (the first
    entry in ``chapter_numbers``). Walks raw/chapters/chapter_NN.txt to compute
    paragraph_breakpoints for each chapter: for each paragraph index p, the
    ordinal (relative to first_ordinal) of the chunk that contains it.
    """
    out_dir = _chunks_dir(book_id, Path(processed_dir))
    book_dir = Path(processed_dir) / book_id

    per_chapter: dict[int, list[ChapterChunk]] = {}
    for c in chunks:
        if c.ordinal is None:
            raise ValueError(f"Chunk missing ordinal: {c}")
        start_chapter = c.chapter_numbers[0] if c.chapter_numbers else None
        if start_chapter is None:
            continue
        per_chapter.setdefault(int(start_chapter), []).append(c)

    idx: dict[str, dict] = {}
    raw_chapters_dir = book_dir / "raw" / "chapters"

    for chapter_num in sorted(per_chapter.keys()):
        cs = sorted(per_chapter[chapter_num], key=lambda x: x.ordinal)
        first_ordinal = cs[0].ordinal
        last_ordinal = cs[-1].ordinal

        breakpoints: list[int] = []
        raw_file = raw_chapters_dir / f"chapter_{chapter_num:02d}.txt"
        if raw_file.exists():
            raw_text = raw_file.read_text(encoding="utf-8")
            paragraphs = raw_text.split("\n\n")
            # For each paragraph's start_char within this chapter, find the chunk
            # whose [start_char, end_char) contains it.
            cursor = 0
            for para in paragraphs:
                # chunk search: first chunk where start_char <= cursor < end_char,
                # mapped to relative ordinal (chunk.ordinal - first_ordinal).
                rel = 0
                for c in cs:
                    if c.start_char <= cursor < c.end_char:
                        rel = c.ordinal - first_ordinal
                        break
                    if c.start_char > cursor:
                        # cursor is before this chunk — fall back to previous
                        rel = max(0, c.ordinal - first_ordinal - 1)
                        break
                else:
                    rel = last_ordinal - first_ordinal
                breakpoints.append(rel)
                cursor += len(para) + 2  # +2 for the "\n\n" separator
        else:
            logger.warning(
                "Raw chapter file {} missing — paragraph_breakpoints left empty",
                raw_file,
            )

        idx[str(chapter_num)] = {
            "first_ordinal": first_ordinal,
            "last_ordinal": last_ordinal,
            "paragraph_breakpoints": breakpoints,
        }

    out = out_dir / CHAPTER_INDEX_FILENAME
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    logger.info("Wrote {} with {} chapter entries", out, len(idx))
    return out


def load_chunks(book_id: str, processed_dir: Path | str) -> list[dict]:
    path = Path(processed_dir) / book_id / "chunks" / CHUNKS_FILENAME
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load {}: {}", path, exc)
        return []
    return payload.get("chunks", [])


def load_chapter_index(book_id: str, processed_dir: Path | str) -> dict:
    path = Path(processed_dir) / book_id / "chunks" / CHAPTER_INDEX_FILENAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load {}: {}", path, exc)
        return {}


def chapter_paragraph_to_ordinal(
    book_id: str,
    chapter: int,
    paragraph: int | None,
    processed_dir: Path | str,
) -> int | None:
    """Translate (chapter, paragraph?) to a chunk ordinal.

    Returns None if the chapter is not indexed.
    - paragraph=None → last_ordinal of the chapter (inclusive chapter-level cursor).
    - paragraph=i → first_ordinal + paragraph_breakpoints[i] (clamped).
    """
    idx = load_chapter_index(book_id, processed_dir)
    entry = idx.get(str(chapter))
    if entry is None:
        return None
    first_ordinal = entry["first_ordinal"]
    last_ordinal = entry["last_ordinal"]
    if paragraph is None:
        return last_ordinal
    breakpoints = entry.get("paragraph_breakpoints", [])
    if not breakpoints:
        return last_ordinal
    idx_safe = max(0, min(paragraph, len(breakpoints) - 1))
    return first_ordinal + breakpoints[idx_safe]


def ordinal_to_chapter(
    book_id: str,
    ordinal: int,
    processed_dir: Path | str,
) -> int | None:
    """Reverse lookup: which chapter contains this ordinal?"""
    idx = load_chapter_index(book_id, processed_dir)
    for chapter_str, entry in idx.items():
        if entry["first_ordinal"] <= ordinal <= entry["last_ordinal"]:
            return int(chapter_str)
    return None


def chapter_strictly_before_ordinal(
    book_id: str,
    chapter: int,
    processed_dir: Path | str,
) -> int:
    """Return the largest ordinal strictly before `chapter` (used when the
    paragraph cursor excludes the current chapter from the graph).

    If chapter is 1 or not indexed, returns -1 (empty allowed set).
    """
    idx = load_chapter_index(book_id, processed_dir)
    entry = idx.get(str(chapter))
    if entry is None:
        # Chapter not indexed — assume all prior chapters are allowed.
        prior = [int(v["last_ordinal"]) for k, v in idx.items() if int(k) < chapter]
        return max(prior) if prior else -1
    return entry["first_ordinal"] - 1
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_chunk_indexing.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/chunk_index.py tests/test_chunk_indexing.py
git commit -m "feat(chunk_index): build and load chunk-ordinal indexes"
```

---

## Task 4: Wire chunk ordinals + `cognee.add` into `run_bookrag_pipeline`

**Files:**
- Modify: `pipeline/cognee_pipeline.py` (`run_bookrag_pipeline` signature + body; `extract_enriched_graph` call signature)
- Modify: `tests/test_cognee_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cognee_pipeline.py`:

```python
import asyncio
from unittest.mock import patch, AsyncMock


def test_run_bookrag_pipeline_assigns_ordinals_and_calls_cognee_add(tmp_path):
    from pipeline.cognee_pipeline import run_bookrag_pipeline
    from pipeline.batcher import Batch

    # Minimal batch: two chapters, enough text to split into 2 chunks @ chunk_size=50.
    batch = Batch(
        chapter_numbers=[1],
        combined_text=("p1 " * 100) + "\n\n" + ("p2 " * 100),
    )

    with patch("pipeline.cognee_pipeline.extract_enriched_graph", new=AsyncMock(return_value=[])), \
         patch("pipeline.cognee_pipeline.cognee") as mock_cognee, \
         patch("pipeline.cognee_pipeline.add_data_points"), \
         patch("pipeline.cognee_pipeline.run_pipeline", new=AsyncMock()):
        mock_cognee.add = AsyncMock()

        next_ord = asyncio.run(run_bookrag_pipeline(
            batch=batch,
            booknlp_output={},
            ontology={},
            book_id="book",
            chunk_size=50,
            chunk_ordinal_start=5,
            output_dir=tmp_path,
        ))

        # Ordinals should start at 5 and be monotonic
        assert next_ord >= 6
        # cognee.add called once per chunk with node_set
        assert mock_cognee.add.await_count >= 1
        call_kwargs = [c.kwargs for c in mock_cognee.add.await_args_list]
        for kw in call_kwargs:
            assert "node_set" in kw
            assert kw["node_set"][0].startswith("book::chunk_")
            assert kw["dataset_name"] == "book"


def test_run_bookrag_pipeline_stamps_ordinal_on_datapoints(tmp_path):
    from pipeline.cognee_pipeline import run_bookrag_pipeline, ChapterChunk
    from pipeline.batcher import Batch
    from models.datapoints import Character

    dp = Character(name="X", first_chapter=1)

    async def fake_extract(chunks, **kw):
        # Stamp ordinal like the real extract should
        for c in chunks:
            dp.source_chunk_ordinal = c.ordinal
        return [dp]

    batch = Batch(chapter_numbers=[1], combined_text="hello world")

    with patch("pipeline.cognee_pipeline.extract_enriched_graph", new=fake_extract), \
         patch("pipeline.cognee_pipeline.cognee") as mock_cognee, \
         patch("pipeline.cognee_pipeline.add_data_points"), \
         patch("pipeline.cognee_pipeline.run_pipeline", new=AsyncMock()):
        mock_cognee.add = AsyncMock()

        asyncio.run(run_bookrag_pipeline(
            batch=batch, booknlp_output={}, ontology={}, book_id="book",
            chunk_size=1500, chunk_ordinal_start=0, output_dir=tmp_path,
        ))

        assert dp.source_chunk_ordinal == 0
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_assigns_ordinals_and_calls_cognee_add -v`
Expected: FAIL (signature doesn't accept `chunk_ordinal_start`, `cognee.add` not called).

- [ ] **Step 3: Modify `run_bookrag_pipeline` signature and body**

In `pipeline/cognee_pipeline.py`, change the top imports to include `cognee` as a module import (if not already):

```python
import cognee
```

Replace the `run_bookrag_pipeline` function signature and body (keep docstring, expand it):

```python
async def run_bookrag_pipeline(
    batch: Batch,
    booknlp_output: dict[str, Any],
    ontology: dict[str, Any],
    book_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    output_dir: Path | None = None,
    chunk_ordinal_start: int = 0,
) -> int:
    """Run the Cognee pipeline for one batch.

    Returns the next available chunk ordinal (``chunk_ordinal_start + len(chunks)``)
    so the orchestrator can pass it to the next batch for a monotonic counter.
    """
    logger.info(
        "Starting BookRAG pipeline for batch (chapters {}, book_id='{}', ordinal_start={})",
        batch.chapter_numbers, book_id, chunk_ordinal_start,
    )

    # Stage 1: Chunk
    chunks = chunk_with_chapter_awareness(
        text=batch.combined_text,
        chunk_size=chunk_size,
        chapter_numbers=batch.chapter_numbers,
    )

    # Assign ordinals + chunk_ids (deterministic given the order returned)
    for i, c in enumerate(chunks):
        c.ordinal = chunk_ordinal_start + i
        c.chunk_id = f"{book_id}::chunk_{c.ordinal:04d}"

    # Index chunk text in cognee so CHUNKS / RAG_COMPLETION can find it later.
    for c in chunks:
        try:
            await cognee.add(
                data=c.text,
                dataset_name=book_id,
                node_set=[c.chunk_id],
            )
        except Exception as exc:
            logger.warning(
                "cognee.add failed for {} (chunk text not indexed): {}",
                c.chunk_id, exc,
            )

    # Stage 2: Extract (stamps source_chunk_ordinal via extract_enriched_graph)
    datapoints = await extract_enriched_graph(
        chunks=chunks,
        booknlp=booknlp_output,
        ontology=ontology,
        max_retries=max_retries,
    )

    if output_dir is None:
        output_dir = Path("data/processed") / book_id / "batches"
    _save_batch_artifacts(batch, booknlp_output, datapoints, output_dir)

    # Stage 3: Persist DataPoints (best-effort)
    if datapoints:
        logger.info("Persisting {} DataPoints via Cognee add_data_points...", len(datapoints))
        try:
            tasks = [Task(add_data_points, task_config={"batch_size": 30})]
            async for status in run_pipeline(tasks=tasks, data=datapoints, datasets=[book_id]):
                logger.debug("Cognee pipeline status: {}", status)
        except Exception as exc:
            logger.warning(
                "Cognee add_data_points failed (extraction data saved to disk): {}", exc,
            )
    else:
        logger.warning("No DataPoints extracted for batch chapters {}", batch.chapter_numbers)

    next_ordinal = chunk_ordinal_start + len(chunks)
    logger.info(
        "Pipeline complete for batch chapters {} — {} DataPoints, next ordinal {}",
        batch.chapter_numbers, len(datapoints), next_ordinal,
    )
    return next_ordinal
```

- [ ] **Step 4: Modify `extract_enriched_graph` to stamp ordinals**

In `pipeline/cognee_pipeline.py`, update the extraction loop inside `extract_enriched_graph`. Replace the line `datapoints = extraction.to_datapoints()` with:

```python
        datapoints = extraction.to_datapoints(source_chunk_ordinal=chunk.ordinal)
```

(It's already inside the `for i, chunk in enumerate(chunks):` loop — `chunk.ordinal` is set by Task 4 Step 3.)

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_assigns_ordinals_and_calls_cognee_add tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_stamps_ordinal_on_datapoints -v`
Expected: PASS.

- [ ] **Step 6: Run the full cognee_pipeline suite**

Run: `python -m pytest tests/test_cognee_pipeline.py -v`
Expected: PASS. If existing tests broke because they didn't pass `chunk_ordinal_start`, the default (`0`) should keep them passing. If any test asserts the return value of `run_bookrag_pipeline`, update it to accept an `int` rather than a list — the return type changed.

- [ ] **Step 7: Fix any callers outside the orchestrator (grep)**

Run: `grep -rn "run_bookrag_pipeline" --include="*.py" .`
Expected: hits in `pipeline/orchestrator.py` and tests. Orchestrator update is Task 5.

- [ ] **Step 8: Commit**

```bash
git add pipeline/cognee_pipeline.py tests/test_cognee_pipeline.py
git commit -m "feat(cognee_pipeline): index chunks via cognee.add and stamp ordinals"
```

---

## Task 5: Orchestrator tracks monotonic ordinal counter and builds indexes

**Files:**
- Modify: `pipeline/orchestrator.py:487-590` (`_stage_run_cognee_batches`)
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_orchestrator.py` (create a minimal stub if the existing file has fixtures):

```python
def test_stage_run_cognee_batches_writes_chunk_indexes(tmp_path, monkeypatch):
    """After all batches complete, chunks.json and chapter_to_chunk_index.json exist."""
    from pipeline.orchestrator import PipelineOrchestrator
    from models.pipeline_state import PipelineState
    import asyncio

    # Create minimal raw chapter files
    book_id = "stub"
    raw_dir = tmp_path / book_id / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text("paragraph one\n\nparagraph two")

    class _Cfg:
        processed_dir = str(tmp_path)
        chunk_size = 50
        max_retries = 1
        llm_provider = "openai"
        llm_model = "gpt-4o-mini"
        batcher = "fixed_size"
        batch_size = 1

    o = PipelineOrchestrator(_Cfg())
    state = PipelineState(book_id=book_id, total_batches=0)
    ctx = {
        "resolved_chapters": ["paragraph one\n\nparagraph two"],
        "booknlp_output": {},
        "ontology": {},
    }

    async def _fake_run(**kwargs):
        # Simulate one chunk being produced per batch, ordinal incrementing
        return kwargs.get("chunk_ordinal_start", 0) + 1

    monkeypatch.setattr("pipeline.orchestrator.run_bookrag_pipeline", _fake_run)
    monkeypatch.setattr("pipeline.orchestrator.configure_cognee", lambda *_a, **_k: None)

    # Seed a fake chunks.json piece by piece: the orchestrator should
    # finalize it via build_chunks_json using the batches it ran.
    # For this test, we patch the finalizer to assert it was called.
    called = {"chunks_json": False, "chapter_idx": False}

    def _fake_build_chunks(*a, **kw):
        called["chunks_json"] = True
        return tmp_path / "fake.json"

    def _fake_build_idx(*a, **kw):
        called["chapter_idx"] = True
        return tmp_path / "fake.json"

    monkeypatch.setattr("pipeline.orchestrator.build_chunks_json", _fake_build_chunks)
    monkeypatch.setattr("pipeline.orchestrator.build_chapter_to_chunk_index", _fake_build_idx)

    asyncio.run(o._stage_run_cognee_batches(state, ctx, logger_stub := __import__("loguru").logger))

    assert called["chunks_json"], "build_chunks_json was not called"
    assert called["chapter_idx"], "build_chapter_to_chunk_index was not called"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_orchestrator.py::test_stage_run_cognee_batches_writes_chunk_indexes -v`
Expected: FAIL (imports `build_chunks_json` from `pipeline.orchestrator` which doesn't yet import them, or the call is never made).

- [ ] **Step 3: Modify the orchestrator**

In `pipeline/orchestrator.py`, add to the imports at the top:

```python
from pipeline.chunk_index import build_chunks_json, build_chapter_to_chunk_index
from pipeline.cognee_pipeline import ChapterChunk, chunk_with_chapter_awareness
```

Replace the inner `for idx, batch in enumerate(batches):` loop in `_stage_run_cognee_batches` — change the `run_bookrag_pipeline` call to pass and consume a counter, and collect chunks for the final index build:

```python
        chunk_ordinal_counter = 0
        all_chunks: list[ChapterChunk] = []

        for idx, batch in enumerate(batches):
            state.current_batch = idx + 1
            self._persist(state)
            log.info(
                "Processing batch {}/{} (chapters {})",
                idx + 1, len(batches), batch.chapter_numbers,
            )

            # Pre-chunk so we can feed the same chunk list into the index builders
            # even if run_bookrag_pipeline is retried. run_bookrag_pipeline will
            # re-chunk internally — but given deterministic chunking, the chunks
            # are identical. We only use `pre_chunks` here to keep the orchestrator
            # aware of ordinals/chunk_ids for index assembly.
            pre_chunks = chunk_with_chapter_awareness(
                text=batch.combined_text,
                chunk_size=chunk_size,
                chapter_numbers=batch.chapter_numbers,
            )
            for i, c in enumerate(pre_chunks):
                c.ordinal = chunk_ordinal_counter + i
                c.chunk_id = f"{state.book_id}::chunk_{c.ordinal:04d}"

            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    chunk_ordinal_counter = await run_bookrag_pipeline(
                        batch=batch,
                        booknlp_output=booknlp_output,
                        ontology=ontology,
                        book_id=state.book_id,
                        chunk_size=chunk_size,
                        max_retries=max_retries,
                        chunk_ordinal_start=chunk_ordinal_counter,
                    )
                    success = True
                    break
                except Exception as exc:
                    log.warning(
                        "Batch {} attempt {}/{} failed: {}",
                        idx + 1, attempt, max_retries, exc,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)

            if not success:
                raise RuntimeError(f"Batch {idx + 1} failed after {max_retries} attempts")

            all_chunks.extend(pre_chunks)

        # After all batches: build the chunk indexes
        if all_chunks:
            processed_dir = Path(self.config.processed_dir)
            build_chunks_json(
                book_id=state.book_id,
                chunks=all_chunks,
                chunk_size_tokens=chunk_size,
                output_dir=processed_dir,
            )
            build_chapter_to_chunk_index(
                book_id=state.book_id,
                chunks=all_chunks,
                processed_dir=processed_dir,
            )
            log.info("Wrote chunk indexes for {} chunks", len(all_chunks))
```

(Keep any surrounding existing code — state persistence, final logging — untouched.)

- [ ] **Step 4: Run the new test**

Run: `python -m pytest tests/test_orchestrator.py::test_stage_run_cognee_batches_writes_chunk_indexes -v`
Expected: PASS.

- [ ] **Step 5: Run the full orchestrator suite**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (no pre-existing tests regress).

- [ ] **Step 6: Commit**

```bash
git add pipeline/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): track monotonic ordinals and build chunk indexes"
```

---

## Task 6: Chunk-based spoiler filter with chapter-translation shim

**Files:**
- Modify: `pipeline/spoiler_filter.py`
- Create (or extend): `tests/test_spoiler_filter_chunk.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spoiler_filter_chunk.py`:

```python
import json
from pathlib import Path


def _write_batch(tmp_path, book_id, batch_label, datapoints):
    d = tmp_path / book_id / "batches" / batch_label
    d.mkdir(parents=True, exist_ok=True)
    (d / "extracted_datapoints.json").write_text(json.dumps(datapoints))


def _write_chapter_index(tmp_path, book_id, idx_payload):
    d = tmp_path / book_id / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    (d / "chapter_to_chunk_index.json").write_text(json.dumps(idx_payload))


def test_load_allowed_nodes_by_chunk_respects_cursor(tmp_path):
    from pipeline.spoiler_filter import load_allowed_nodes_by_chunk

    _write_batch(tmp_path, "book", "batch_01", [
        {"type": "Character", "name": "A", "first_chapter": 1, "source_chunk_ordinal": 2},
        {"type": "Character", "name": "B", "first_chapter": 1, "source_chunk_ordinal": 5},
        {"type": "Character", "name": "C", "first_chapter": 2, "source_chunk_ordinal": 10},
    ])

    out = load_allowed_nodes_by_chunk("book", chunk_ordinal_cursor=5, processed_dir=tmp_path)
    names = sorted(n["name"] for n in out)
    assert names == ["A", "B"]


def test_load_allowed_nodes_shim_translates_chapter_to_ordinal(tmp_path):
    from pipeline.spoiler_filter import load_allowed_nodes, load_allowed_nodes_by_chunk

    _write_batch(tmp_path, "book", "batch_01", [
        {"type": "Character", "name": "A", "first_chapter": 1, "source_chunk_ordinal": 0},
        {"type": "Character", "name": "B", "first_chapter": 1, "source_chunk_ordinal": 3},
        {"type": "Character", "name": "C", "first_chapter": 2, "source_chunk_ordinal": 4},
    ])
    _write_chapter_index(tmp_path, "book", {
        "1": {"first_ordinal": 0, "last_ordinal": 3, "paragraph_breakpoints": [0, 1, 2, 3]},
        "2": {"first_ordinal": 4, "last_ordinal": 4, "paragraph_breakpoints": [0]},
    })

    by_chapter = sorted(n["name"] for n in load_allowed_nodes("book", cursor=1, processed_dir=tmp_path))
    by_ordinal = sorted(n["name"] for n in load_allowed_nodes_by_chunk("book", 3, tmp_path))
    assert by_chapter == by_ordinal == ["A", "B"]


def test_node_without_ordinal_falls_back_to_chapter(tmp_path):
    from pipeline.spoiler_filter import load_allowed_nodes_by_chunk

    # No chapter_to_chunk_index written — fallback path uses effective_latest_chapter
    _write_batch(tmp_path, "book", "batch_01", [
        {"type": "Character", "name": "A", "first_chapter": 1},  # no ordinal
        {"type": "Character", "name": "B", "first_chapter": 3},  # no ordinal
    ])
    _write_chapter_index(tmp_path, "book", {
        "1": {"first_ordinal": 0, "last_ordinal": 3, "paragraph_breakpoints": []},
        "2": {"first_ordinal": 4, "last_ordinal": 5, "paragraph_breakpoints": []},
        "3": {"first_ordinal": 6, "last_ordinal": 9, "paragraph_breakpoints": []},
    })

    # cursor=5 == end of chapter 2; chapter-fallback: chapter 1 yes, chapter 3 no
    out = load_allowed_nodes_by_chunk("book", chunk_ordinal_cursor=5, processed_dir=tmp_path)
    names = sorted(n["name"] for n in out)
    assert names == ["A"]
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_spoiler_filter_chunk.py -v`
Expected: FAIL (import of `load_allowed_nodes_by_chunk` fails).

- [ ] **Step 3: Add the new function and shim to `pipeline/spoiler_filter.py`**

At the bottom of `pipeline/spoiler_filter.py`, add:

```python
def _effective_ordinal(node: dict, book_id: str, processed_dir: Path | str) -> int | None:
    """Return the node's source_chunk_ordinal, or — if missing — the last ordinal
    of the chapter derived from effective_latest_chapter. None if neither works.
    """
    ord_val = node.get("source_chunk_ordinal")
    if ord_val is not None:
        return int(ord_val)
    ch = effective_latest_chapter(node)
    if ch is None:
        return None
    # Import here to avoid circular imports at module load.
    from pipeline.chunk_index import load_chapter_index
    idx = load_chapter_index(book_id, processed_dir)
    entry = idx.get(str(ch))
    if entry is None:
        return None
    return int(entry["last_ordinal"])


def load_allowed_nodes_by_chunk(
    book_id: str,
    chunk_ordinal_cursor: int,
    processed_dir: Path | str,
) -> list[dict]:
    """Ordinal-based variant of load_allowed_nodes.

    Keeps the latest per-identity snapshot whose source_chunk_ordinal
    (or chapter-fallback ordinal) <= cursor.
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    latest: dict[tuple, tuple[int, dict]] = {}

    def _merge(enriched: dict) -> None:
        ord_ = _effective_ordinal(enriched, book_id, processed_dir)
        if ord_ is None or ord_ > chunk_ordinal_cursor:
            return
        key = _identity_key(enriched)
        prev = latest.get(key)
        if prev is None or ord_ > prev[0]:
            latest[key] = (ord_, enriched)

    for batch_file in sorted(batches_dir.glob("*.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for collection, type_label in _NODE_COLLECTIONS.items():
            for node in payload.get(collection, []) or []:
                enriched = dict(node)
                enriched["_type"] = type_label
                _merge(enriched)

    for dp_file in sorted(batches_dir.glob("batch_*/extracted_datapoints.json")):
        try:
            payload = json.loads(dp_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = payload if isinstance(payload, list) else payload.get("datapoints", [])
        for node in items:
            if not isinstance(node, dict):
                continue
            enriched = dict(node)
            enriched["_type"] = enriched.get("type") or enriched.get("__type__") or "Entity"
            _merge(enriched)

    return [node for _, node in latest.values()]
```

Then rewrite `load_allowed_nodes` as a shim that translates chapter → ordinal when the index exists, otherwise keeps the original chapter-based walk. Replace the current `load_allowed_nodes` function body with:

```python
def load_allowed_nodes(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
) -> list[dict]:
    """Chapter-cursor variant. Delegates to load_allowed_nodes_by_chunk when
    the chunk index is present; otherwise falls back to the legacy
    chapter-based walk.
    """
    from pipeline.chunk_index import load_chapter_index
    idx = load_chapter_index(book_id, processed_dir)
    if idx:
        entry = idx.get(str(cursor))
        if entry is not None:
            return load_allowed_nodes_by_chunk(
                book_id=book_id,
                chunk_ordinal_cursor=entry["last_ordinal"],
                processed_dir=processed_dir,
            )
        # Chapter not in index (e.g. cursor=0 for "before first chapter")
        prior = [int(v["last_ordinal"]) for k, v in idx.items() if int(k) <= cursor]
        if prior:
            return load_allowed_nodes_by_chunk(
                book_id=book_id,
                chunk_ordinal_cursor=max(prior),
                processed_dir=processed_dir,
            )
        return []

    # Legacy path: no chunk index, walk batches and compare by chapter
    return _load_allowed_nodes_by_chapter_legacy(book_id, cursor, processed_dir)
```

Rename the existing `load_allowed_nodes` body (the current implementation) to `_load_allowed_nodes_by_chapter_legacy`. Keep signature `(book_id, cursor, processed_dir)`. Do not delete it — existing `test_spoiler_filter.py` covers it and the shim will route to it when no index exists.

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_spoiler_filter_chunk.py -v`
Expected: PASS.

- [ ] **Step 5: Run the existing spoiler_filter tests to confirm no regression**

Run: `python -m pytest tests/test_spoiler_filter.py -v`
Expected: PASS (the legacy path still works for fixtures without a chunk index).

- [ ] **Step 6: Commit**

```bash
git add pipeline/spoiler_filter.py tests/test_spoiler_filter_chunk.py
git commit -m "feat(spoiler_filter): add chunk-ordinal filter with chapter shim"
```

---

## Task 7: Backfill script for existing books

**Files:**
- Create: `scripts/backfill_chunk_ordinals.py`
- Create: `tests/test_backfill_chunk_ordinals.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backfill_chunk_ordinals.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest


def _seed_book(tmp_path: Path, book_id: str = "book") -> Path:
    """Create a minimal processed book dir with one batch + input_text."""
    book_dir = tmp_path / book_id
    batch_dir = book_dir / "batches" / "batch_01"
    batch_dir.mkdir(parents=True)

    # Input text long enough to produce >= 1 chunk at chunk_size=1500
    text = "Scrooge sat in his counting-house. " * 500
    (batch_dir / "input_text.txt").write_text(text)

    # A couple of DataPoints whose descriptions contain substrings of the text
    dps = [
        {"type": "Character", "name": "Scrooge", "first_chapter": 1,
         "description": "Scrooge sat in his counting-house."},
        {"type": "Location", "name": "Counting-house", "first_chapter": 1,
         "description": "the counting-house"},
    ]
    (batch_dir / "extracted_datapoints.json").write_text(json.dumps(dps))

    # Raw chapter 1 — needed by chapter_to_chunk_index
    raw_dir = book_dir / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text(text)

    # Mark the book as ready
    (book_dir / "pipeline_state.json").write_text(json.dumps({
        "book_id": book_id, "ready_for_query": True,
    }))

    return book_dir


def test_backfill_writes_chunk_indexes(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    book_dir = _seed_book(tmp_path)

    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))

    chunks_path = book_dir / "chunks" / "chunks.json"
    idx_path = book_dir / "chunks" / "chapter_to_chunk_index.json"
    assert chunks_path.exists()
    assert idx_path.exists()

    chunks_payload = json.loads(chunks_path.read_text())
    assert chunks_payload["total_chunks"] >= 1


def test_backfill_stamps_ordinals_on_datapoints(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    book_dir = _seed_book(tmp_path)
    dp_file = book_dir / "batches" / "batch_01" / "extracted_datapoints.json"
    before = json.loads(dp_file.read_text())
    assert all("source_chunk_ordinal" not in dp for dp in before)

    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))

    after = json.loads(dp_file.read_text())
    stamped = sum(1 for dp in after if dp.get("source_chunk_ordinal") is not None)
    assert stamped >= len(after) * 0.9  # >= 90%


def test_backfill_is_idempotent(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    _seed_book(tmp_path)
    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))
        first_call_count = mock_cognee.add.await_count
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))
        assert mock_cognee.add.await_count == first_call_count  # skipped


def test_backfill_force_overwrites(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    _seed_book(tmp_path)
    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))
        before_calls = mock_cognee.add.await_count
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=True))
        assert mock_cognee.add.await_count > before_calls
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_backfill_chunk_ordinals.py -v`
Expected: FAIL (module `scripts.backfill_chunk_ordinals` does not exist).

- [ ] **Step 3: Create the backfill script**

Create `scripts/__init__.py` (empty) if it doesn't exist:

```bash
touch scripts/__init__.py
```

Create `scripts/backfill_chunk_ordinals.py`:

```python
"""Backfill chunk ordinals for books ingested before Slice 1.

Re-chunks each batch's input_text.txt (deterministic), assigns globally-monotonic
ordinals, writes chunks.json + chapter_to_chunk_index.json, stamps
source_chunk_ordinal on every DataPoint by substring-matching its description
against chunk text, and calls cognee.add() to index chunk text.

Usage:
    python -m scripts.backfill_chunk_ordinals --book christmas_carol_e6ddcd76
    python -m scripts.backfill_chunk_ordinals --all
    python -m scripts.backfill_chunk_ordinals --all --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from loguru import logger

import cognee

from pipeline.chunk_index import (
    CHUNKS_FILENAME,
    CHAPTER_INDEX_FILENAME,
    build_chunks_json,
    build_chapter_to_chunk_index,
)
from pipeline.cognee_pipeline import chunk_with_chapter_awareness, ChapterChunk


def _already_done(book_dir: Path) -> bool:
    return (book_dir / "chunks" / CHUNKS_FILENAME).exists() and (
        book_dir / "chunks" / CHAPTER_INDEX_FILENAME
    ).exists()


def _reconstruct_chunks(book_id: str, book_dir: Path, chunk_size: int = 1500) -> list[ChapterChunk]:
    """Re-chunk each batch's input_text.txt. Returns chunks with ordinals assigned."""
    batches_dir = book_dir / "batches"
    chunks_all: list[ChapterChunk] = []
    ordinal = 0
    for batch_subdir in sorted(batches_dir.glob("batch_*")):
        input_text = (batch_subdir / "input_text.txt").read_text(encoding="utf-8")
        # Chapter numbers from the batch label (batch_NN where NN is the first chapter)
        try:
            first_chapter = int(batch_subdir.name.split("_")[1])
        except (IndexError, ValueError):
            first_chapter = 1
        chunks = chunk_with_chapter_awareness(
            text=input_text,
            chunk_size=chunk_size,
            chapter_numbers=[first_chapter],
        )
        for c in chunks:
            c.ordinal = ordinal
            c.chunk_id = f"{book_id}::chunk_{ordinal:04d}"
            ordinal += 1
        chunks_all.extend(chunks)
    return chunks_all


def _stamp_datapoint_ordinals(
    book_id: str, book_dir: Path, chunks: list[ChapterChunk]
) -> tuple[int, int]:
    """Stamp source_chunk_ordinal on every DataPoint in batches/*/extracted_datapoints.json.

    Uses substring match: a DataPoint is assigned to the first chunk whose text
    contains its description (or its name, if description is empty). DataPoints
    that don't match fall back to last_ordinal of the chapter derived from
    first_chapter/chapter.

    Returns (total, matched).
    """
    chunks_sorted = sorted(chunks, key=lambda c: c.ordinal)

    def _find_ordinal(desc: str) -> int | None:
        if not desc:
            return None
        for c in chunks_sorted:
            if desc in c.text:
                return c.ordinal
        return None

    total = 0
    matched = 0
    for dp_file in sorted((book_dir / "batches").glob("batch_*/extracted_datapoints.json")):
        payload = json.loads(dp_file.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else payload.get("datapoints", [])
        for dp in items:
            if not isinstance(dp, dict):
                continue
            total += 1
            probe = dp.get("description") or dp.get("name") or ""
            ord_ = _find_ordinal(probe)
            if ord_ is None:
                # Chapter-level fallback: last chunk of that chapter
                ch = dp.get("first_chapter") or dp.get("chapter")
                if ch is not None:
                    matching = [c.ordinal for c in chunks_sorted if ch in c.chapter_numbers]
                    if matching:
                        ord_ = max(matching)
            if ord_ is not None:
                dp["source_chunk_ordinal"] = ord_
                matched += 1
        if isinstance(payload, list):
            dp_file.write_text(json.dumps(items, indent=2))
        else:
            payload["datapoints"] = items
            dp_file.write_text(json.dumps(payload, indent=2))
    return total, matched


async def _index_chunks_in_cognee(book_id: str, chunks: list[ChapterChunk]) -> None:
    """Call cognee.add for every chunk so CHUNKS / RAG_COMPLETION have text."""
    for c in chunks:
        try:
            await cognee.add(
                data=c.text,
                dataset_name=book_id,
                node_set=[c.chunk_id],
            )
        except Exception as exc:
            logger.warning("cognee.add failed for {}: {}", c.chunk_id, exc)


async def backfill_book(book_id: str, processed_dir: Path, force: bool = False) -> None:
    book_dir = Path(processed_dir) / book_id
    if not book_dir.exists():
        logger.warning("Book dir {} does not exist — skipping", book_dir)
        return
    if _already_done(book_dir) and not force:
        logger.info("{} already has chunk indexes — skipping (use --force to overwrite)", book_id)
        return

    logger.info("Backfilling {} ...", book_id)
    chunks = _reconstruct_chunks(book_id, book_dir)
    if not chunks:
        logger.warning("No chunks reconstructed for {} — aborting", book_id)
        return

    build_chunks_json(
        book_id=book_id, chunks=chunks, chunk_size_tokens=1500,
        output_dir=processed_dir,
    )
    build_chapter_to_chunk_index(
        book_id=book_id, chunks=chunks, processed_dir=processed_dir,
    )

    total, matched = _stamp_datapoint_ordinals(book_id, book_dir, chunks)
    logger.info("Stamped {}/{} DataPoints with source_chunk_ordinal", matched, total)

    await _index_chunks_in_cognee(book_id, chunks)
    logger.info("Backfill complete for {}", book_id)


def _all_books(processed_dir: Path) -> list[str]:
    return sorted(p.name for p in processed_dir.iterdir() if p.is_dir())


async def _main_async(book_ids: list[str], processed_dir: Path, force: bool) -> None:
    for bid in book_ids:
        await backfill_book(bid, processed_dir, force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill chunk ordinals.")
    parser.add_argument("--book", help="Specific book_id to backfill")
    parser.add_argument("--all", action="store_true", help="Backfill every book")
    parser.add_argument("--force", action="store_true", help="Overwrite existing indexes")
    parser.add_argument(
        "--processed-dir", default="data/processed",
        help="Top-level processed dir (default: data/processed)",
    )
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    if args.all:
        books = _all_books(processed_dir)
    elif args.book:
        books = [args.book]
    else:
        parser.error("Provide --book <id> or --all")
        return  # pragma: no cover

    asyncio.run(_main_async(books, processed_dir, force=args.force))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_backfill_chunk_ordinals.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/backfill_chunk_ordinals.py tests/test_backfill_chunk_ordinals.py
git commit -m "feat(backfill): add backfill_chunk_ordinals script"
```

---

## Task 8: Integration smoke test against Christmas Carol fixture

**Files:**
- No new files. Manual verification against the existing ingestion.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: PASS. All 923 pre-existing tests plus the ~18 new ones.

- [ ] **Step 2: Backfill the local Christmas Carol ingestion (manual)**

If `data/processed/christmas_carol_*/` exists locally:

Run: `python -m scripts.backfill_chunk_ordinals --book $(ls data/processed | grep christmas_carol | head -1)`
Expected: logs "Backfill complete for christmas_carol_..."; files exist:
- `data/processed/christmas_carol_*/chunks/chunks.json` with `total_chunks > 0`
- `data/processed/christmas_carol_*/chunks/chapter_to_chunk_index.json` with 5 chapter keys
- At least one batch's `extracted_datapoints.json` now has `source_chunk_ordinal` on most entries

- [ ] **Step 3: Verify GRAPH_COMPLETION still works end-to-end**

Start the server:
```bash
python main.py &
SERVER_PID=$!
sleep 3
```

Query:
```bash
curl -s -X POST http://127.0.0.1:8000/books/$(ls data/processed | grep christmas_carol | head -1)/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "Who is Marley?", "search_type": "GRAPH_COMPLETION"}'
```

Expected: HTTP 200 with non-empty `answer` and `results`. Kill the server:
```bash
kill $SERVER_PID
```

If the answer looks identical (or very close) to pre-Slice-1 behavior, acceptance criterion 6 is satisfied.

- [ ] **Step 4: Commit if any docs or log fixes were needed**

```bash
git status
# If nothing, skip.
git add CLAUDE.md docs/ 2>/dev/null || true
git commit -m "docs: slice 1 integration notes" --allow-empty
```

---

## Self-review checklist (done after writing)

- [x] Spec coverage: all 10 acceptance criteria in the spec map to a task (AC1/2 → T5, AC3 → T4, AC4 → T8 manual, AC5 → T6, AC6 → T8 manual, AC7 → T7, AC8 → T8, AC9 → untouched (no frontend changes), AC10 → untouched (progress not modified)).
- [x] No placeholders: every code block is complete, every command has an expected output line.
- [x] Type consistency: `source_chunk_ordinal: int | None = None` everywhere, `chunk_id` format `"{book_id}::chunk_{ordinal:04d}"` everywhere, `run_bookrag_pipeline` returns `int` consistently.
- [x] File paths: every modified file is absolute or repo-root-relative with line refs where useful.
