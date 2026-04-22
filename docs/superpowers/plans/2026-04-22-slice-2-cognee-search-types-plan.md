# Slice 2 — Cognee Search Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire three cognee search types (`CHUNKS`, `RAG_COMPLETION`, `GRAPH_COMPLETION_COT`) into `POST /books/{book_id}/query` with chunk-ordinal-based spoiler filtering, while leaving the existing `GRAPH_COMPLETION` implementation untouched.

**Architecture:** A new `pipeline/cognee_search.py` module owns cognee `search()` wrappers, chunk-ordinal post-filtering, and result normalization into `QueryResultItem`. `main.py` computes the reader's `chunk_ordinal_cursor` once per request via the Slice 1 chunk index, then dispatches by `search_type`. Defense in depth: graph-typed searches pass `node_name=[allowed names]` upfront, and every response is post-filtered by ordinal before leaving the server.

**Tech Stack:** Python 3.10, FastAPI, Cognee 0.5.6 (`cognee.search`, `SearchType`), pytest with async support, loguru. Relies on Slice 1 artifacts (`chunks.json`, `chapter_to_chunk_index.json`, `source_chunk_ordinal` on DataPoints).

**Spec:** `docs/superpowers/specs/2026-04-22-slice-2-cognee-search-types.md`
**Depends on:** Slice 1 must be merged.

---

## File structure

**New files:**
- `pipeline/cognee_search.py` — cognee search wrappers + chunk-ordinal filtering.
- `tests/test_cognee_search.py` — unit tests for the new module.

**Modified files:**
- `main.py` — swap `_ALLOWED_SEARCH_TYPES` contents; add `_reader_chunk_ordinal` helper; extend `query_book` to dispatch into `cognee_search` for the three new types; add `CogneeSearchError` → 502 mapping.
- `tests/test_query_endpoint.py` — end-to-end tests for each new type via mocked cognee.

---

## Task 1: Scaffold `pipeline/cognee_search.py` with typed error + helpers

**Files:**
- Create: `pipeline/cognee_search.py`
- Create: `tests/test_cognee_search.py`

- [ ] **Step 1: Write the failing tests (helpers only)**

Create `tests/test_cognee_search.py`:

```python
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _write_chapter_index(tmp_path, book_id):
    d = tmp_path / book_id / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    (d / "chapter_to_chunk_index.json").write_text(json.dumps({
        "1": {"first_ordinal": 0, "last_ordinal": 4, "paragraph_breakpoints": [0, 1, 2, 3, 4]},
        "2": {"first_ordinal": 5, "last_ordinal": 9, "paragraph_breakpoints": [0, 2, 4]},
    }))


def test_chunk_ordinal_from_result_parses_node_set(tmp_path):
    from pipeline.cognee_search import _chunk_ordinal_from_result

    r = SimpleNamespace(
        search_result=SimpleNamespace(
            metadata={"node_set": ["book::chunk_0042"]},
        ),
    )
    assert _chunk_ordinal_from_result(r, "book") == 42


def test_chunk_ordinal_from_result_returns_none_on_missing(tmp_path):
    from pipeline.cognee_search import _chunk_ordinal_from_result
    r = SimpleNamespace(search_result=SimpleNamespace(metadata={}))
    assert _chunk_ordinal_from_result(r, "book") is None


def test_filter_results_by_chunk_ordinal_drops_above_cursor():
    from pipeline.cognee_search import _filter_results_by_chunk_ordinal

    results = [
        SimpleNamespace(search_result=SimpleNamespace(metadata={"node_set": ["book::chunk_0002"]}, text="a")),
        SimpleNamespace(search_result=SimpleNamespace(metadata={"node_set": ["book::chunk_0007"]}, text="b")),
    ]
    filtered = _filter_results_by_chunk_ordinal(results, cursor=5, book_id="book")
    assert len(filtered) == 1
    assert filtered[0].search_result.text == "a"


def test_filter_results_drops_unparseable_chunk_id():
    from pipeline.cognee_search import _filter_results_by_chunk_ordinal

    results = [
        SimpleNamespace(search_result=SimpleNamespace(metadata={}, text="no id")),
    ]
    assert _filter_results_by_chunk_ordinal(results, cursor=100, book_id="book") == []


def test_build_allowed_node_names_caps_at_500(tmp_path):
    from pipeline.cognee_search import _build_allowed_node_names

    # Write 600 fake datapoints
    d = tmp_path / "book" / "batches" / "batch_01"
    d.mkdir(parents=True)
    dps = [
        {"type": "Character", "name": f"char_{i}", "first_chapter": 1,
         "source_chunk_ordinal": i}
        for i in range(600)
    ]
    (d / "extracted_datapoints.json").write_text(json.dumps(dps))
    _write_chapter_index(tmp_path, "book")

    names = _build_allowed_node_names(
        book_id="book", chunk_ordinal_cursor=999,
        processed_dir=tmp_path, cap=500,
    )
    assert len(names) == 500
    # Highest-ordinal preference: names from ordinals 100..599 should dominate
    assert "char_599" in names
    assert "char_0" not in names


def test_build_allowed_node_names_no_cap_needed(tmp_path):
    from pipeline.cognee_search import _build_allowed_node_names

    d = tmp_path / "book" / "batches" / "batch_01"
    d.mkdir(parents=True)
    dps = [{"type": "Character", "name": "only", "first_chapter": 1,
            "source_chunk_ordinal": 0}]
    (d / "extracted_datapoints.json").write_text(json.dumps(dps))
    _write_chapter_index(tmp_path, "book")

    names = _build_allowed_node_names("book", 5, tmp_path, cap=500)
    assert names == ["only"]


def test_cognee_search_error_is_exported():
    from pipeline.cognee_search import CogneeSearchError
    err = CogneeSearchError("CHUNKS", RuntimeError("boom"))
    assert err.search_type == "CHUNKS"
    assert "boom" in str(err)
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cognee_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.cognee_search'`.

- [ ] **Step 3: Create `pipeline/cognee_search.py` with helpers + error class only**

```python
"""Cognee search wrappers with chunk-ordinal spoiler filtering.

Public entry points:
    search_chunks(book_id, question, chunk_ordinal_cursor, ...)
    search_rag_completion(book_id, question, chunk_ordinal_cursor, ...)
    search_graph_completion_cot(book_id, question, chunk_ordinal_cursor, ...)

All three:
  - short-circuit to (empty_fallback_answer, []) on empty allowed-node set
  - pass node_name=[allowed names, capped at 500] for graph-typed queries
  - post-filter every returned result by source_chunk_ordinal <= cursor
  - convert cognee exceptions to CogneeSearchError (caller maps to HTTP 502)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from pipeline.spoiler_filter import load_allowed_nodes_by_chunk

CHUNK_ID_ORDINAL_RE = re.compile(r"::chunk_(\d+)$")

EMPTY_ANSWER = "I don't have information about that yet based on your reading progress."
DEFAULT_TOP_K = 15
NODE_NAME_CAP = 500


class CogneeSearchError(RuntimeError):
    """Raised when cognee.search() fails; caller maps to HTTP 502."""

    def __init__(self, search_type: str, cause: Exception) -> None:
        super().__init__(f"cognee search failed for {search_type}: {cause}")
        self.search_type = search_type
        self.cause = cause


def _extract_metadata(result: Any) -> dict:
    sr = getattr(result, "search_result", result)
    meta = getattr(sr, "metadata", None)
    if isinstance(meta, dict):
        return meta
    return {}


def _chunk_ordinal_from_result(result: Any, book_id: str) -> int | None:
    """Parse the chunk ordinal out of a cognee SearchResult.

    Looks for node_set entries shaped like ``{book_id}::chunk_NNNN``. Returns
    None if no such entry is found; callers drop the result.
    """
    meta = _extract_metadata(result)
    node_set = meta.get("node_set") or []
    if not isinstance(node_set, list):
        return None
    for entry in node_set:
        if not isinstance(entry, str):
            continue
        if not entry.startswith(f"{book_id}::chunk_"):
            # Accept any ::chunk_NNNN suffix (book_id prefix may differ if cognee
            # normalizes dataset names). Fall through to regex match.
            pass
        m = CHUNK_ID_ORDINAL_RE.search(entry)
        if m:
            return int(m.group(1))
    # Fall back: check metadata for an explicit "source_chunk_ordinal" (for
    # DataPoint-typed results from GRAPH_COMPLETION_COT).
    ord_val = meta.get("source_chunk_ordinal")
    if isinstance(ord_val, int):
        return ord_val
    return None


def _filter_results_by_chunk_ordinal(
    results: list[Any],
    cursor: int,
    book_id: str,
) -> list[Any]:
    """Keep results whose chunk ordinal <= cursor. Drop unparseable."""
    kept = []
    for r in results:
        ord_ = _chunk_ordinal_from_result(r, book_id)
        if ord_ is None:
            logger.debug("Dropping cognee result with unparseable chunk id")
            continue
        if ord_ > cursor:
            continue
        kept.append(r)
    return kept


def _build_allowed_node_names(
    book_id: str,
    chunk_ordinal_cursor: int,
    processed_dir: Path | str,
    cap: int = NODE_NAME_CAP,
) -> list[str]:
    """Return the names of DataPoints visible at the cursor, capped.

    When capped, prefers highest-ordinal entries (closest to reader position).
    """
    nodes = load_allowed_nodes_by_chunk(
        book_id=book_id,
        chunk_ordinal_cursor=chunk_ordinal_cursor,
        processed_dir=processed_dir,
    )
    named = [
        (int(n.get("source_chunk_ordinal") or 0), n["name"])
        for n in nodes
        if n.get("name") and n.get("_type") != "Relationship"
    ]
    # Sort descending by ordinal so the cap keeps the most recent.
    named.sort(key=lambda t: t[0], reverse=True)
    if len(named) > cap:
        logger.warning(
            "Allowed node set ({}) exceeds cap — truncating to {}",
            len(named), cap,
        )
        named = named[:cap]
    return [n for _, n in named]
```

- [ ] **Step 4: Run the helper tests**

Run: `python -m pytest tests/test_cognee_search.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/cognee_search.py tests/test_cognee_search.py
git commit -m "feat(cognee_search): scaffold helpers for chunk-ordinal filtering"
```

---

## Task 2: `search_chunks` — CHUNKS search with post-filter

**Files:**
- Modify: `pipeline/cognee_search.py`
- Modify: `tests/test_cognee_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cognee_search.py`:

```python
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_search_chunks_filters_by_ordinal(tmp_path):
    from pipeline.cognee_search import search_chunks

    # Cognee returns 3 results; 2 above cursor should be dropped
    fake_results = [
        SimpleNamespace(search_result=SimpleNamespace(
            metadata={"node_set": ["book::chunk_0001"]},
            text="keep me — chunk 1 text",
        )),
        SimpleNamespace(search_result=SimpleNamespace(
            metadata={"node_set": ["book::chunk_0008"]},
            text="drop me — chunk 8 text",
        )),
        SimpleNamespace(search_result=SimpleNamespace(
            metadata={"node_set": ["book::chunk_0003"]},
            text="keep me — chunk 3 text",
        )),
    ]

    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=fake_results)

        items = await search_chunks(
            book_id="book", question="Where is Marley?",
            chunk_ordinal_cursor=5, processed_dir=tmp_path,
        )

    assert len(items) == 2
    assert all("keep me" in i.content for i in items)
    assert all(i.entity_type == "Chunk" for i in items)


@pytest.mark.asyncio
async def test_search_chunks_raises_on_cognee_failure(tmp_path):
    from pipeline.cognee_search import search_chunks, CogneeSearchError

    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(CogneeSearchError) as exc_info:
            await search_chunks("book", "q?", 5, tmp_path)
    assert exc_info.value.search_type == "CHUNKS"
```

Also add `pytest-asyncio` to the test dependencies if not present. Check with:

```bash
grep -r "pytest-asyncio\|asyncio_mode" pyproject.toml pytest.ini setup.cfg 2>/dev/null | head
```

If missing, add a `tests/conftest.py` snippet (or extend existing) — the project's existing conftest already mocks cognee; ensure it has:

```python
# At top of tests/conftest.py if not already present
pytest_plugins = ["pytest_asyncio"]
```

And in `pyproject.toml` under `[tool.pytest.ini_options]`, ensure `asyncio_mode = "auto"` OR use the `@pytest.mark.asyncio` decorator on each async test (as above).

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cognee_search.py::test_search_chunks_filters_by_ordinal -v`
Expected: FAIL — `ImportError: cannot import name 'search_chunks'`.

- [ ] **Step 3: Implement `search_chunks`**

Append to `pipeline/cognee_search.py` (add `import cognee` at the top first):

```python
import cognee
from cognee.modules.search.types import SearchType

# Light-weight result shape to avoid importing QueryResultItem (which lives in main.py).
# Callers adapt this to their own response model.
from dataclasses import dataclass


@dataclass
class SearchItem:
    content: str
    entity_type: str | None = None
    chapter: int | None = None


def _result_text(result: Any) -> str:
    sr = getattr(result, "search_result", result)
    text = getattr(sr, "text", None) or getattr(sr, "content", None) or ""
    return str(text)[:800]


def _result_chapter(result: Any, book_id: str, processed_dir: Path | str) -> int | None:
    ord_ = _chunk_ordinal_from_result(result, book_id)
    if ord_ is None:
        return None
    from pipeline.chunk_index import ordinal_to_chapter
    return ordinal_to_chapter(book_id, ord_, processed_dir)


async def search_chunks(
    book_id: str,
    question: str,
    chunk_ordinal_cursor: int,
    processed_dir: Path | str,
    top_k: int = DEFAULT_TOP_K,
) -> list[SearchItem]:
    """CHUNKS search: return text passages whose source chunk <= cursor."""
    try:
        raw = await cognee.search(
            query_text=question,
            query_type=SearchType.CHUNKS,
            datasets=[book_id],
            top_k=top_k,
        )
    except Exception as exc:
        raise CogneeSearchError("CHUNKS", exc) from exc

    filtered = _filter_results_by_chunk_ordinal(raw, chunk_ordinal_cursor, book_id)
    return [
        SearchItem(
            content=_result_text(r),
            entity_type="Chunk",
            chapter=_result_chapter(r, book_id, processed_dir),
        )
        for r in filtered
    ]
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_cognee_search.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/cognee_search.py tests/test_cognee_search.py
git commit -m "feat(cognee_search): implement CHUNKS search with ordinal filter"
```

---

## Task 3: `search_rag_completion` — filtered chunks + our own synthesis

**Files:**
- Modify: `pipeline/cognee_search.py`
- Modify: `tests/test_cognee_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cognee_search.py`:

```python
@pytest.mark.asyncio
async def test_search_rag_completion_synthesizes_answer(tmp_path):
    from pipeline.cognee_search import search_rag_completion

    fake_results = [
        SimpleNamespace(search_result=SimpleNamespace(
            metadata={"node_set": ["book::chunk_0001"]},
            text="Marley was dead: to begin with.",
        )),
        SimpleNamespace(search_result=SimpleNamespace(
            metadata={"node_set": ["book::chunk_0002"]},
            text="Old Marley was as dead as a door-nail.",
        )),
    ]

    with patch("pipeline.cognee_search.cognee") as mock_cognee, \
         patch("pipeline.cognee_search._synthesize_answer", new=AsyncMock(return_value="Marley is dead.")):
        mock_cognee.search = AsyncMock(return_value=fake_results)
        answer, items = await search_rag_completion(
            book_id="book", question="Is Marley alive?",
            chunk_ordinal_cursor=5, processed_dir=tmp_path,
        )

    assert answer == "Marley is dead."
    assert len(items) == 2


@pytest.mark.asyncio
async def test_search_rag_completion_empty_allowed_set_short_circuits(tmp_path):
    from pipeline.cognee_search import search_rag_completion, EMPTY_ANSWER

    # No batches, no index → allowed set is empty
    (tmp_path / "book").mkdir()
    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=[])
        answer, items = await search_rag_completion(
            "book", "q?", chunk_ordinal_cursor=-1, processed_dir=tmp_path,
        )
    assert answer == EMPTY_ANSWER
    assert items == []
    mock_cognee.search.assert_not_awaited()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cognee_search.py -k rag_completion -v`
Expected: FAIL (function doesn't exist yet).

- [ ] **Step 3: Implement `search_rag_completion` + synthesis helper**

Append to `pipeline/cognee_search.py`:

```python
from cognee.infrastructure.llm.LLMGateway import LLMGateway
from pydantic import BaseModel, Field


class _SpoilerSafeAnswer(BaseModel):
    answer: str = Field(..., description="Spoiler-free answer grounded in the provided context.")


async def _synthesize_answer(
    question: str,
    context_blocks: list[str],
    extra_paragraphs: list[str] | None = None,
) -> str:
    """Same LLM synthesis path as GRAPH_COMPLETION in main.py — kept local so
    this module is self-contained.
    """
    blocks = list(context_blocks)
    if extra_paragraphs:
        blocks.extend(extra_paragraphs)
    if not blocks:
        return EMPTY_ANSWER

    system = (
        "You are a spoiler-free literary assistant. Answer the user's question "
        "using ONLY the provided context from the reader's reading progress. "
        "If the context does not contain the answer, say you don't know yet. "
        "Never invent events or use prior knowledge of the book."
    )
    user = (
        f"Question: {question}\n\n"
        "Context:\n" + "\n".join(f"- {c}" for c in blocks)
    )
    response = await LLMGateway.acreate_structured_output(
        text_input=user,
        system_prompt=system,
        response_model=_SpoilerSafeAnswer,
    )
    return response.answer


async def search_rag_completion(
    book_id: str,
    question: str,
    chunk_ordinal_cursor: int,
    processed_dir: Path | str,
    top_k: int = DEFAULT_TOP_K,
    extra_paragraphs: list[str] | None = None,
) -> tuple[str, list[SearchItem]]:
    """Retrieve filtered chunks (CHUNKS path), then synthesize an answer locally.

    We do NOT use cognee.search(RAG_COMPLETION) directly because it would
    synthesize over unfiltered chunks. We filter first, then synthesize.
    """
    if chunk_ordinal_cursor < 0:
        return EMPTY_ANSWER, []

    items = await search_chunks(
        book_id=book_id, question=question,
        chunk_ordinal_cursor=chunk_ordinal_cursor,
        processed_dir=processed_dir, top_k=top_k,
    )
    if not items:
        return EMPTY_ANSWER, []

    context = [i.content for i in items]
    answer = await _synthesize_answer(question, context, extra_paragraphs=extra_paragraphs)
    return answer, items
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_cognee_search.py -k rag_completion -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/cognee_search.py tests/test_cognee_search.py
git commit -m "feat(cognee_search): implement RAG_COMPLETION with local synthesis"
```

---

## Task 4: `search_graph_completion_cot` — node_name-constrained CoT

**Files:**
- Modify: `pipeline/cognee_search.py`
- Modify: `tests/test_cognee_search.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cognee_search.py`:

```python
@pytest.mark.asyncio
async def test_search_graph_completion_cot_passes_node_name(tmp_path):
    from pipeline.cognee_search import search_graph_completion_cot

    _write_chapter_index(tmp_path, "book")
    d = tmp_path / "book" / "batches" / "batch_01"
    d.mkdir(parents=True)
    (d / "extracted_datapoints.json").write_text(json.dumps([
        {"type": "Character", "name": "Scrooge", "first_chapter": 1,
         "source_chunk_ordinal": 0},
        {"type": "Character", "name": "Marley", "first_chapter": 1,
         "source_chunk_ordinal": 1},
    ]))

    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=[
            SimpleNamespace(
                search_result=SimpleNamespace(
                    metadata={"node_set": ["book::chunk_0001"], "source_chunk_ordinal": 1},
                    text="Scrooge — a squeezing, wrenching, grasping, clutching, covetous old sinner.",
                    answer="Scrooge is a miser.",
                ),
            ),
        ])

        answer, items = await search_graph_completion_cot(
            book_id="book", question="Who is Scrooge?",
            chunk_ordinal_cursor=4, processed_dir=tmp_path,
        )

    call_kwargs = mock_cognee.search.await_args.kwargs
    assert "node_name" in call_kwargs
    assert sorted(call_kwargs["node_name"]) == ["Marley", "Scrooge"]
    assert call_kwargs["node_name_filter_operator"] == "OR"
    assert answer  # non-empty — from the mocked response
    assert len(items) == 1


@pytest.mark.asyncio
async def test_graph_cot_empty_allowed_set_short_circuits(tmp_path):
    from pipeline.cognee_search import search_graph_completion_cot, EMPTY_ANSWER

    (tmp_path / "book").mkdir()
    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock()
        answer, items = await search_graph_completion_cot(
            "book", "q?", chunk_ordinal_cursor=-1, processed_dir=tmp_path,
        )
    assert answer == EMPTY_ANSWER
    assert items == []
    mock_cognee.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_cot_raises_on_cognee_failure(tmp_path):
    from pipeline.cognee_search import search_graph_completion_cot, CogneeSearchError

    _write_chapter_index(tmp_path, "book")
    d = tmp_path / "book" / "batches" / "batch_01"
    d.mkdir(parents=True)
    (d / "extracted_datapoints.json").write_text(json.dumps([
        {"type": "Character", "name": "X", "first_chapter": 1, "source_chunk_ordinal": 0},
    ]))

    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(CogneeSearchError) as exc_info:
            await search_graph_completion_cot("book", "q?", 4, tmp_path)
    assert exc_info.value.search_type == "GRAPH_COMPLETION_COT"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cognee_search.py -k graph_completion_cot -v`
Expected: FAIL (function missing).

- [ ] **Step 3: Implement `search_graph_completion_cot`**

Append to `pipeline/cognee_search.py`:

```python
def _result_answer(result: Any) -> str:
    """Pull the synthesized answer out of a cognee completion result."""
    sr = getattr(result, "search_result", result)
    for attr in ("answer", "response", "text", "content"):
        val = getattr(sr, attr, None)
        if val:
            return str(val)
    return ""


async def search_graph_completion_cot(
    book_id: str,
    question: str,
    chunk_ordinal_cursor: int,
    processed_dir: Path | str,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[str, list[SearchItem]]:
    """GRAPH_COMPLETION_COT with node_name constraint + post-filter."""
    if chunk_ordinal_cursor < 0:
        return EMPTY_ANSWER, []

    allowed = _build_allowed_node_names(
        book_id=book_id,
        chunk_ordinal_cursor=chunk_ordinal_cursor,
        processed_dir=processed_dir,
        cap=NODE_NAME_CAP,
    )
    if not allowed:
        return EMPTY_ANSWER, []

    try:
        raw = await cognee.search(
            query_text=question,
            query_type=SearchType.GRAPH_COMPLETION_COT,
            datasets=[book_id],
            node_name=allowed,
            node_name_filter_operator="OR",
            top_k=top_k,
        )
    except Exception as exc:
        raise CogneeSearchError("GRAPH_COMPLETION_COT", exc) from exc

    filtered = _filter_results_by_chunk_ordinal(raw, chunk_ordinal_cursor, book_id)

    # Pick the first filtered result's answer; aggregate the rest as sources.
    answer = _result_answer(filtered[0]) if filtered else EMPTY_ANSWER

    items = [
        SearchItem(
            content=_result_text(r),
            entity_type="Node",
            chapter=_result_chapter(r, book_id, processed_dir),
        )
        for r in filtered
    ]
    return answer, items
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_cognee_search.py -v`
Expected: PASS (all CHUNKS / RAG_COMPLETION / GRAPH_COMPLETION_COT tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/cognee_search.py tests/test_cognee_search.py
git commit -m "feat(cognee_search): implement GRAPH_COMPLETION_COT with node_name filter"
```

---

## Task 5: Wire the three new search types into `main.py` `/query`

**Files:**
- Modify: `main.py` (`_ALLOWED_SEARCH_TYPES` at line 362; `query_book` at line 658)
- Modify: `tests/test_query_endpoint.py`

- [ ] **Step 1: Write the failing end-to-end tests**

Append to `tests/test_query_endpoint.py` (adapt fixtures to whatever pattern the file already uses; the snippet below assumes a `client` fixture and a seeded book):

```python
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace


def _result(chunk_ord: int, text: str, answer: str | None = None):
    sr = SimpleNamespace(
        metadata={"node_set": [f"book::chunk_{chunk_ord:04d}"],
                  "source_chunk_ordinal": chunk_ord},
        text=text,
    )
    if answer is not None:
        sr.answer = answer
    return SimpleNamespace(search_result=sr)


def test_query_chunks_returns_filtered_passages(client, seeded_book_id):
    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=[
            _result(0, "chapter 1 passage"),
            _result(99, "chapter 5 spoiler"),
        ])
        r = client.post(
            f"/books/{seeded_book_id}/query",
            json={"question": "what?", "search_type": "CHUNKS"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["result_count"] == 1
    assert body["answer"] == ""
    assert "chapter 1 passage" in body["results"][0]["content"]


def test_query_rag_completion_returns_answer_and_sources(client, seeded_book_id):
    with patch("pipeline.cognee_search.cognee") as mock_cognee, \
         patch("pipeline.cognee_search._synthesize_answer", new=AsyncMock(return_value="Synth.")):
        mock_cognee.search = AsyncMock(return_value=[_result(0, "passage")])
        r = client.post(
            f"/books/{seeded_book_id}/query",
            json={"question": "what?", "search_type": "RAG_COMPLETION"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Synth."
    assert body["result_count"] == 1


def test_query_graph_completion_cot_returns_answer_and_sources(client, seeded_book_id):
    with patch("pipeline.cognee_search.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=[
            _result(0, "evidence", answer="CoT answer."),
        ])
        r = client.post(
            f"/books/{seeded_book_id}/query",
            json={"question": "why?", "search_type": "GRAPH_COMPLETION_COT"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "CoT answer."
    assert body["result_count"] == 1


def test_query_summaries_now_rejected(client, seeded_book_id):
    r = client.post(
        f"/books/{seeded_book_id}/query",
        json={"question": "?", "search_type": "SUMMARIES"},
    )
    assert r.status_code == 400
    assert "SUMMARIES" in r.json()["detail"] or "Invalid" in r.json()["detail"]


def test_cognee_unavailable_returns_502_for_new_types(client, seeded_book_id, monkeypatch):
    import main as main_module
    monkeypatch.setattr(main_module, "COGNEE_AVAILABLE", False)
    r = client.post(
        f"/books/{seeded_book_id}/query",
        json={"question": "?", "search_type": "CHUNKS"},
    )
    assert r.status_code == 502
    assert "cognee search failed" in r.json()["detail"].lower()


def test_graph_completion_unaffected_by_cognee_unavailable(client, seeded_book_id, monkeypatch):
    import main as main_module
    monkeypatch.setattr(main_module, "COGNEE_AVAILABLE", False)
    r = client.post(
        f"/books/{seeded_book_id}/query",
        json={"question": "?", "search_type": "GRAPH_COMPLETION"},
    )
    # GRAPH_COMPLETION does not depend on cognee.search — should still succeed (200).
    assert r.status_code == 200
```

(The `seeded_book_id` fixture should produce a book directory with a minimal `chunks/chapter_to_chunk_index.json` and `batches/batch_01/extracted_datapoints.json` matching Slice 1's output. If the existing conftest doesn't provide this, extend the existing fixture setup to include the two Slice 1 artifacts.)

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_query_endpoint.py -k "chunks or rag_completion or graph_completion_cot or summaries_now_rejected or cognee_unavailable" -v`
Expected: FAIL — the new types aren't dispatched; `SUMMARIES` is still allowed (returns 200).

- [ ] **Step 3: Update `_ALLOWED_SEARCH_TYPES` in `main.py`**

In `main.py` at line 362, replace:

```python
_ALLOWED_SEARCH_TYPES = {
    "GRAPH_COMPLETION", "CHUNKS", "SUMMARIES", "RAG_COMPLETION",
}
```

with:

```python
_ALLOWED_SEARCH_TYPES = {
    "GRAPH_COMPLETION", "CHUNKS", "RAG_COMPLETION", "GRAPH_COMPLETION_COT",
}
```

- [ ] **Step 4: Add the reader-chunk-ordinal helper to `main.py`**

Just above `query_book` (before the `@app.post("/books/{book_id}/query", ...)` decorator at line 658), add:

```python
def _reader_chunk_ordinal(
    book_id: str,
    current_chapter: int,
    current_paragraph: int | None,
) -> int:
    """Translate the reader's (chapter, paragraph?) progress to a chunk ordinal.

    - paragraph is None → inclusive chapter cursor (last ordinal of that chapter)
    - paragraph is int → ordinal of the chunk holding paragraph P in current_chapter
    - chapter not indexed (e.g. chunk_index missing) → fall back to cursor=-1
    """
    from pipeline.chunk_index import chapter_paragraph_to_ordinal
    ordinal = chapter_paragraph_to_ordinal(
        book_id=book_id,
        chapter=current_chapter,
        paragraph=current_paragraph,
        processed_dir=Path(config.processed_dir),
    )
    return ordinal if ordinal is not None else -1
```

- [ ] **Step 5: Extend `query_book` to dispatch new types**

Find `query_book` starting around line 658. Replace the body from the top of the function down through `answer = ""; if req.search_type == "GRAPH_COMPLETION": ...` with a dispatch:

```python
@app.post("/books/{book_id}/query", response_model=QueryResponse)
async def query_book(book_id: SafeBookId, req: QueryRequest) -> QueryResponse:
    if req.search_type not in _ALLOWED_SEARCH_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search_type '{req.search_type}'. Allowed: {sorted(_ALLOWED_SEARCH_TYPES)}",
        )

    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    disk_chapter, disk_paragraph = _get_reading_progress(book_id)
    current_chapter = (
        min(req.max_chapter, disk_chapter) if req.max_chapter is not None else disk_chapter
    )

    if disk_paragraph is not None:
        graph_max_chapter = max(current_chapter - 1, 0)
        current_chapter_paragraphs = _load_paragraphs_up_to(
            book_id, current_chapter, disk_paragraph
        )
    else:
        graph_max_chapter = current_chapter
        current_chapter_paragraphs = []

    # GRAPH_COMPLETION keeps its existing disk-based path (unchanged).
    if req.search_type == "GRAPH_COMPLETION":
        results = _answer_from_allowed_nodes(
            book_id, req.question, graph_max_chapter=graph_max_chapter,
        )
        graph_context = [r.content for r in results[:15]]
        combined = graph_context + current_chapter_paragraphs
        answer = await _complete_over_context(req.question, combined)
        return QueryResponse(
            book_id=book_id, question=req.question, search_type=req.search_type,
            current_chapter=current_chapter, current_paragraph=disk_paragraph,
            answer=answer, results=results, result_count=len(results),
        )

    # New cognee-backed types
    if not COGNEE_AVAILABLE:
        raise HTTPException(
            status_code=502,
            detail=f"cognee search failed for {req.search_type}: cognee not available",
        )

    from pipeline.cognee_search import (
        CogneeSearchError,
        search_chunks,
        search_rag_completion,
        search_graph_completion_cot,
    )

    reader_ord = _reader_chunk_ordinal(book_id, current_chapter, disk_paragraph)
    processed = Path(config.processed_dir)

    try:
        if req.search_type == "CHUNKS":
            items = await search_chunks(
                book_id=book_id, question=req.question,
                chunk_ordinal_cursor=reader_ord, processed_dir=processed,
            )
            answer = ""
            results = [
                QueryResultItem(content=i.content, entity_type=i.entity_type, chapter=i.chapter)
                for i in items
            ]

        elif req.search_type == "RAG_COMPLETION":
            answer, items = await search_rag_completion(
                book_id=book_id, question=req.question,
                chunk_ordinal_cursor=reader_ord, processed_dir=processed,
                extra_paragraphs=current_chapter_paragraphs,
            )
            results = [
                QueryResultItem(content=i.content, entity_type=i.entity_type, chapter=i.chapter)
                for i in items
            ]

        elif req.search_type == "GRAPH_COMPLETION_COT":
            answer, items = await search_graph_completion_cot(
                book_id=book_id, question=req.question,
                chunk_ordinal_cursor=reader_ord, processed_dir=processed,
            )
            results = [
                QueryResultItem(content=i.content, entity_type=i.entity_type, chapter=i.chapter)
                for i in items
            ]

        else:  # pragma: no cover — guarded by _ALLOWED_SEARCH_TYPES
            raise HTTPException(status_code=400, detail=f"Unhandled: {req.search_type}")

    except CogneeSearchError as exc:
        logger.warning("Cognee search failed: {}", exc)
        raise HTTPException(
            status_code=502,
            detail=f"cognee search failed for {exc.search_type}: {exc.cause}",
        ) from exc

    return QueryResponse(
        book_id=book_id, question=req.question, search_type=req.search_type,
        current_chapter=current_chapter, current_paragraph=disk_paragraph,
        answer=answer, results=results, result_count=len(results),
    )
```

- [ ] **Step 6: Run the end-to-end tests**

Run: `python -m pytest tests/test_query_endpoint.py -v`
Expected: PASS on the 7 new cases plus all existing cases. Fix any assertions in existing tests that pinned `SUMMARIES` as valid — they need to either be removed or updated to expect 400.

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: PASS. 923 original + Slice 1 additions (+~18) + Slice 2 additions (~17) = ~958 tests.

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_query_endpoint.py
git commit -m "feat(query): dispatch CHUNKS, RAG_COMPLETION, GRAPH_COMPLETION_COT"
```

---

## Task 6: Smoke test against a real book

**Files:**
- No new files. Manual verification.

- [ ] **Step 1: Ensure Slice 1 artifacts exist**

Run: `ls data/processed/*/chunks/chunks.json 2>/dev/null | head`
Expected: at least one hit. If missing, run:
```bash
python -m scripts.backfill_chunk_ordinals --all
```

- [ ] **Step 2: Start the server**

```bash
python main.py &
SERVER_PID=$!
sleep 3
```

- [ ] **Step 3: Smoke-test each new type**

```bash
BOOK=$(ls data/processed | grep -E "(christmas_carol|red_rising)" | head -1)

# Set progress to chapter 2 to have a non-empty allowed set
curl -s -X POST "http://127.0.0.1:8000/books/$BOOK/progress" \
  -H 'Content-Type: application/json' -d '{"current_chapter": 2}'

for T in CHUNKS RAG_COMPLETION GRAPH_COMPLETION_COT; do
  echo "---- $T ----"
  curl -s -X POST "http://127.0.0.1:8000/books/$BOOK/query" \
    -H 'Content-Type: application/json' \
    -d "{\"question\":\"Who is Scrooge?\",\"search_type\":\"$T\"}" | python -m json.tool | head -30
done

kill $SERVER_PID
```

Expected:
- `CHUNKS` → 200 with `result_count > 0`, `answer == ""`.
- `RAG_COMPLETION` → 200 with non-empty `answer` and `result_count > 0`.
- `GRAPH_COMPLETION_COT` → 200 with non-empty `answer` and `result_count > 0`.

If any returns 502: inspect `logs/bookrag.log` for the cognee failure and diagnose. Common issues: `cognee.add` never ran for this book (re-run backfill with `--force`), or the `node_set` format disagrees with what cognee stores (feature-detect by dumping `raw[0].search_result.metadata` in a debug log line).

- [ ] **Step 4: Spoiler-safety sanity check**

```bash
# Reset to chapter 1 — later chapters should be excluded
curl -s -X POST "http://127.0.0.1:8000/books/$BOOK/progress" \
  -H 'Content-Type: application/json' -d '{"current_chapter": 1}'

curl -s -X POST "http://127.0.0.1:8000/books/$BOOK/query" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Who is the ghost of Christmas future?","search_type":"CHUNKS"}' \
  | python -m json.tool
```

Expected: no result references Chapter 4+ content. For Christmas Carol, the Ghost of Christmas Yet to Come (chapter 4) must NOT appear in results. If it does, the post-filter has a bug — inspect `_chunk_ordinal_from_result` with the actual cognee response metadata.

- [ ] **Step 5: Commit any doc updates**

```bash
git status
git add CLAUDE.md 2>/dev/null || true
git commit -m "docs: slice 2 — document new search types in CLAUDE.md" --allow-empty
```

If the smoke test revealed a metadata-shape bug, commit the fix as its own commit referencing the observed shape in the message.

---

## Self-review checklist (done after writing)

- [x] Spec coverage: AC1 → T2+T5, AC2 → T3+T5, AC3 → T4+T5, AC4 → T5 (`_reader_chunk_ordinal` uses `chapter_paragraph_to_ordinal`), AC5 → T3+T4 empty-allowed short-circuits, AC6 → T1+T2 (`_filter_results_by_chunk_ordinal` in every path), AC7 → T5 (502 mapping + COGNEE_AVAILABLE guard), AC8 → T1 (500-cap + warning), AC9 → T5 (`_ALLOWED_SEARCH_TYPES` swap), AC10 → T5 final run.
- [x] No placeholders: all code blocks complete, every step has concrete commands and expected output.
- [x] Type consistency: `SearchItem` fields, `CogneeSearchError(search_type, cause)` signature, `(answer, items)` tuple return for completion types, `list[SearchItem]` for CHUNKS — used the same way everywhere.
- [x] Dependency on Slice 1: calls `load_allowed_nodes_by_chunk`, `chapter_paragraph_to_ordinal`, `ordinal_to_chapter` from Slice 1 modules.
