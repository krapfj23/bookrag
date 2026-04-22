# Fog-of-War Phase 1: Paragraph-Granular Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend reader progress from chapter-granular to paragraph-granular. When a reader is mid-chapter, the graph allowlist excludes the current chapter entirely; context for the current chapter comes from the raw resolved text, limited to paragraphs 0..cursor. Prior chapters still use the graph.

**Architecture:** Add an optional `current_paragraph` field to `reading_progress.json`. When present, the graph-filter bound becomes `current_chapter - 1` (strict) and a new helper `_load_paragraphs_up_to(book_id, chapter, paragraph)` supplies the raw-text paragraphs for the current chapter. For `GRAPH_COMPLETION`, these paragraphs are interleaved with the allowed-node context passed to the LLM. When `current_paragraph` is absent, Phase 0 behavior is preserved (inclusive chapter filter, no raw-text context) — protecting existing clients that haven't been upgraded.

**Tech Stack:** FastAPI, Pydantic v2, existing `pipeline/spoiler_filter.py`, `_load_chapter` in `main.py` (paragraph splitter), Cognee `LLMGateway`.

## File Structure

**Modified files only** — Phase 1 extends Phase 0, it doesn't add new modules:

- `main.py`
  - `ProgressRequest` / `ProgressResponse` models: add `current_paragraph`
  - `_get_reading_progress`: return `(chapter, paragraph_or_None)` instead of `int`
  - `set_progress`: persist paragraph when given
  - `_answer_from_allowed_nodes`: accept `graph_max_chapter` explicitly (decouples the filter bound from the progress cursor)
  - `query_book`: compute graph bound + paragraph-bounded raw text, combine
  - New helper `_load_paragraphs_up_to(book_id, chapter, paragraph_cursor)`

- `tests/test_main.py` — new tests for paragraph progress, strict filter, raw-text injection; one existing test will be extended (not replaced) to cover both paragraph-less and paragraph-aware modes.

- `CLAUDE.md` — update "Fog-of-War Retrieval" subsection.

**Backward compatibility**: clients that POST only `current_chapter` continue to work. The existing test `test_cursor_5_reveals_chapter_5_nodes` (Phase 0) tests paragraph-less semantics and stays passing.

---

## Task 1: Extend `reading_progress.json` schema and `_get_reading_progress`

**Files:**
- Modify: `main.py` (`_get_reading_progress`, around line 475)
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
class TestReadingProgressParagraph:
    """_get_reading_progress returns (chapter, paragraph) — paragraph may be None."""

    def test_chapter_only_returns_none_paragraph(self, tmp_path, monkeypatch):
        from main import _get_reading_progress, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        (tmp_path / "bk").mkdir()
        (tmp_path / "bk" / "reading_progress.json").write_text(json.dumps({
            "book_id": "bk", "current_chapter": 3,
        }))
        chapter, paragraph = _get_reading_progress("bk")
        assert chapter == 3
        assert paragraph is None

    def test_chapter_and_paragraph(self, tmp_path, monkeypatch):
        from main import _get_reading_progress, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        (tmp_path / "bk").mkdir()
        (tmp_path / "bk" / "reading_progress.json").write_text(json.dumps({
            "book_id": "bk", "current_chapter": 3, "current_paragraph": 7,
        }))
        chapter, paragraph = _get_reading_progress("bk")
        assert chapter == 3
        assert paragraph == 7

    def test_missing_file_defaults(self, tmp_path, monkeypatch):
        from main import _get_reading_progress, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        chapter, paragraph = _get_reading_progress("nonexistent")
        assert chapter == 1
        assert paragraph is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestReadingProgressParagraph -v`
Expected: FAIL — current impl returns an int, not a tuple.

- [ ] **Step 3: Rewrite `_get_reading_progress`**

Replace the body of `_get_reading_progress` in `main.py` with:

```python
def _get_reading_progress(book_id: str) -> tuple[int, int | None]:
    """Load current reading progress. Returns (chapter, paragraph_or_None).

    Paragraph is 0-indexed when present. None means "paragraph cursor not
    recorded" — callers treat that as Phase-0-compatible chapter-only progress.
    """
    progress_path = Path(config.processed_dir) / book_id / "reading_progress.json"
    if not progress_path.exists():
        return 1, None
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1, None
    chapter = int(data.get("current_chapter", 1))
    paragraph = data.get("current_paragraph")
    paragraph = int(paragraph) if paragraph is not None else None
    return chapter, paragraph
```

- [ ] **Step 4: Update every caller of `_get_reading_progress`**

In `main.py`, search for every call to `_get_reading_progress(...)`. Each caller currently treats the return value as an int. For each callsite, adapt to tuple unpacking. Specifically:

In `query_book`, replace:
```python
disk_max = _get_reading_progress(book_id)
```
with:
```python
disk_max, _ = _get_reading_progress(book_id)
```

(Later tasks will use the paragraph half; Task 1 only fixes existing callers to not break.)

In `_list_books` (the handler for `GET /books`), do the same tuple-unpack replacement at its call site.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all PASS (existing + 3 new). If any pre-existing test fails because it asserted `_get_reading_progress` returned an int, do NOT modify the test — stop and report the test name in DONE_WITH_CONCERNS.

- [ ] **Step 6: Commit**

```bash
cd /Users/jeffreykrapf/Documents/thefinalbookrag
git add main.py tests/test_main.py
git commit -m "feat(progress): reading_progress now returns (chapter, paragraph)"
```

---

## Task 2: Extend `ProgressRequest` / `ProgressResponse` and `set_progress`

**Files:**
- Modify: `main.py` (`ProgressRequest`, `ProgressResponse`, `set_progress`)
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
class TestSetProgressWithParagraph:
    """POST /books/{id}/progress accepts optional current_paragraph."""

    def _seed(self, tmp_path, book_id="bk"):
        (tmp_path / book_id).mkdir(parents=True, exist_ok=True)
        (tmp_path / book_id / "pipeline_state.json").write_text(json.dumps({
            "book_id": book_id, "ready_for_query": True,
            "current_stage": "complete", "stages": {},
        }))

    def test_accepts_paragraph(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        client = TestClient(app)
        resp = client.post("/books/bk/progress", json={
            "current_chapter": 3, "current_paragraph": 12,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 3
        assert body["current_paragraph"] == 12

    def test_paragraph_optional(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        client = TestClient(app)
        resp = client.post("/books/bk/progress", json={"current_chapter": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 2
        assert body["current_paragraph"] is None

    def test_paragraph_persisted_to_disk(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        client = TestClient(app)
        client.post("/books/bk/progress", json={
            "current_chapter": 3, "current_paragraph": 12,
        })
        on_disk = json.loads((tmp_path / "bk" / "reading_progress.json").read_text())
        assert on_disk["current_chapter"] == 3
        assert on_disk["current_paragraph"] == 12

    def test_rejects_negative_paragraph(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        client = TestClient(app)
        resp = client.post("/books/bk/progress", json={
            "current_chapter": 3, "current_paragraph": -1,
        })
        assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestSetProgressWithParagraph -v`
Expected: FAIL.

- [ ] **Step 3: Extend the Pydantic models**

In `main.py`, find the `ProgressRequest` class (around line 125) and add `current_paragraph`:

```python
class ProgressRequest(BaseModel):
    current_chapter: int
    current_paragraph: int | None = None
```

Find `ProgressResponse` (around line 130) and add the same field:

```python
class ProgressResponse(BaseModel):
    book_id: str
    current_chapter: int
    current_paragraph: int | None = None
```

- [ ] **Step 4: Update `set_progress`**

Replace the body of `set_progress` (around line 316) with:

```python
@app.post("/books/{book_id}/progress", response_model=ProgressResponse)
async def set_progress(book_id: SafeBookId, req: ProgressRequest) -> ProgressResponse:
    """Set the reader's current chapter + optional paragraph cursor."""
    if req.current_chapter < 1:
        raise HTTPException(status_code=400, detail="current_chapter must be >= 1")
    if req.current_paragraph is not None and req.current_paragraph < 0:
        raise HTTPException(status_code=400, detail="current_paragraph must be >= 0")

    progress_path = Path(config.processed_dir) / book_id / "reading_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"book_id": book_id, "current_chapter": req.current_chapter}
    if req.current_paragraph is not None:
        payload["current_paragraph"] = req.current_paragraph
    progress_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info(
        "Updated reading progress: book_id={}, chapter={}, paragraph={}",
        book_id, req.current_chapter, req.current_paragraph,
    )

    return ProgressResponse(
        book_id=book_id,
        current_chapter=req.current_chapter,
        current_paragraph=req.current_paragraph,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py::TestSetProgressWithParagraph -v`
Expected: 4/4 PASS. Then `pytest tests/test_main.py -v` to confirm no regressions.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(progress): POST /progress accepts optional current_paragraph"
```

---

## Task 3: Add `_load_paragraphs_up_to` helper

**Files:**
- Modify: `main.py` (add helper near `_load_chapter`)
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
class TestLoadParagraphsUpTo:
    """_load_paragraphs_up_to returns paragraphs 0..cursor from the requested chapter."""

    def _seed_chapter(self, tmp_path, book_id, chapter_n, paragraphs: list[str]):
        chapters = tmp_path / book_id / "raw" / "chapters"
        chapters.mkdir(parents=True, exist_ok=True)
        text = "\n\n".join(paragraphs)
        (chapters / f"chapter_{chapter_n:02d}.txt").write_text(text, encoding="utf-8")
        (tmp_path / book_id / "pipeline_state.json").write_text(json.dumps({
            "book_id": book_id, "ready_for_query": True,
            "current_stage": "complete", "stages": {},
        }))

    def test_returns_paragraphs_through_cursor_inclusive(self, tmp_path, monkeypatch):
        from main import _load_paragraphs_up_to, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed_chapter(tmp_path, "bk", 3, ["p0", "p1", "p2", "p3", "p4"])

        assert _load_paragraphs_up_to("bk", 3, 2) == ["p0", "p1", "p2"]

    def test_cursor_past_end_clamps(self, tmp_path, monkeypatch):
        from main import _load_paragraphs_up_to, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed_chapter(tmp_path, "bk", 1, ["p0", "p1"])

        assert _load_paragraphs_up_to("bk", 1, 99) == ["p0", "p1"]

    def test_cursor_zero_returns_single(self, tmp_path, monkeypatch):
        from main import _load_paragraphs_up_to, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed_chapter(tmp_path, "bk", 1, ["p0", "p1"])

        assert _load_paragraphs_up_to("bk", 1, 0) == ["p0"]

    def test_missing_chapter_returns_empty(self, tmp_path, monkeypatch):
        from main import _load_paragraphs_up_to, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        assert _load_paragraphs_up_to("missing", 1, 0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestLoadParagraphsUpTo -v`
Expected: FAIL — helper doesn't exist.

- [ ] **Step 3: Implement**

In `main.py`, add this helper directly after `_load_chapter` (around line 475):

```python
def _load_paragraphs_up_to(
    book_id: str,
    chapter: int,
    paragraph_cursor: int,
) -> list[str]:
    """Return paragraphs 0..paragraph_cursor (inclusive) from `chapter`.

    Empty list if the book/chapter doesn't exist. Cursor values past the last
    paragraph are clamped. Reuses _load_chapter's paragraph splitting.
    """
    ch = _load_chapter(book_id, chapter)
    if ch is None:
        return []
    return ch.paragraphs[: max(paragraph_cursor + 1, 0)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py::TestLoadParagraphsUpTo -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(query): add _load_paragraphs_up_to helper"
```

---

## Task 4: Decouple graph-filter bound from cursor in `_answer_from_allowed_nodes`

**Files:**
- Modify: `main.py` (`_answer_from_allowed_nodes` signature)
- Test: `tests/test_main.py`

Rationale: Phase 0's helper takes `cursor` and filters `effective_latest_chapter <= cursor`. Phase 1 needs to call it with a DIFFERENT bound depending on whether a paragraph cursor is set. Refactor to accept `graph_max_chapter` explicitly — existing callers pass the same value they used before, new caller in Phase 1 passes `current_chapter - 1` when paragraph is present.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
class TestAnswerFromAllowedNodesExplicitBound:
    """_answer_from_allowed_nodes accepts graph_max_chapter kwarg."""

    def _seed(self, tmp_path, book_id="bk"):
        batches = tmp_path / book_id / "batches"
        batches.mkdir(parents=True)
        (batches / "b1.json").write_text(json.dumps({
            "characters": [
                {"id": "c1", "name": "Early", "description": "ch1",
                 "first_chapter": 1, "last_known_chapter": 1},
                {"id": "c3", "name": "Later", "description": "ch3",
                 "first_chapter": 1, "last_known_chapter": 3},
            ],
        }))

    def test_bound_2_excludes_chapter_3(self, tmp_path, monkeypatch):
        from main import _answer_from_allowed_nodes, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        items = _answer_from_allowed_nodes("bk", "later", graph_max_chapter=2)
        assert not any("ch3" in i.content for i in items)

    def test_bound_3_includes_chapter_3(self, tmp_path, monkeypatch):
        from main import _answer_from_allowed_nodes, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        items = _answer_from_allowed_nodes("bk", "later", graph_max_chapter=3)
        assert any("ch3" in i.content for i in items)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestAnswerFromAllowedNodesExplicitBound -v`
Expected: FAIL — function takes `cursor`, not `graph_max_chapter`.

- [ ] **Step 3: Rename the parameter**

In `main.py`, find `_answer_from_allowed_nodes`. Change the signature from:

```python
def _answer_from_allowed_nodes(
    book_id: str,
    question: str,
    cursor: int,
) -> list[QueryResultItem]:
```

to:

```python
def _answer_from_allowed_nodes(
    book_id: str,
    question: str,
    graph_max_chapter: int,
) -> list[QueryResultItem]:
```

In the body, replace `cursor` with `graph_max_chapter` everywhere (should be 1-2 spots — the `load_allowed_nodes` call).

- [ ] **Step 4: Update the existing caller in `query_book`**

In `query_book`, change the call site:

```python
results = _answer_from_allowed_nodes(book_id, req.question, current_chapter)
```

to:

```python
results = _answer_from_allowed_nodes(book_id, req.question, graph_max_chapter=current_chapter)
```

(Keyword arg; Task 5 will change the value.)

- [ ] **Step 5: Update Phase 0 tests that used positional `cursor`**

The Phase 0 `TestAnswerFromAllowedNodes` class called `_answer_from_allowed_nodes("bk", question="...", cursor=2)`. Search for `cursor=` in test_main.py and change each hit inside calls to `_answer_from_allowed_nodes` to `graph_max_chapter=`. Do NOT change the `cursor=` parameter on `load_allowed_nodes` (different function) or on `QueryRequest` / elsewhere.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_main.py -v`
Expected: all PASS, including the two new tests from step 1 and the Phase 0 tests under their renamed kwarg.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "refactor(query): rename cursor to graph_max_chapter for Phase 1 reuse"
```

---

## Task 5: Rewire `query_book` to use paragraph-aware bounds + raw-text injection

**Files:**
- Modify: `main.py` (`query_book`)
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_main.py`:

```python
class TestQueryEndpointParagraphGate:
    """/books/{id}/query respects current_paragraph for raw-text context."""

    def _seed(self, tmp_path, book_id="bk"):
        # Graph nodes: one safe in ch1, one spoiler tagged ch3.
        batches = tmp_path / book_id / "batches"
        batches.mkdir(parents=True)
        (batches / "b1.json").write_text(json.dumps({
            "characters": [
                {"id": "c1", "name": "Marley", "description": "dead partner",
                 "first_chapter": 1, "last_known_chapter": 1},
                {"id": "c3", "name": "Future", "description": "GRAPH_SPOILER",
                 "first_chapter": 1, "last_known_chapter": 3},
            ],
        }))
        # Current chapter 3 has 5 paragraphs. Reader is at paragraph 1.
        chapters = tmp_path / book_id / "raw" / "chapters"
        chapters.mkdir(parents=True)
        (chapters / "chapter_03.txt").write_text(
            "READ_P0\n\nREAD_P1\n\nUNREAD_P2\n\nUNREAD_P3\n\nUNREAD_P4",
            encoding="utf-8",
        )
        (tmp_path / book_id / "pipeline_state.json").write_text(json.dumps({
            "book_id": book_id, "ready_for_query": True,
            "current_stage": "complete", "stages": {},
        }))
        (tmp_path / book_id / "reading_progress.json").write_text(json.dumps({
            "book_id": book_id, "current_chapter": 3, "current_paragraph": 1,
        }))

    def test_paragraph_cursor_excludes_current_chapter_graph_nodes(self, tmp_path, monkeypatch):
        """Chapter-3 graph nodes are hidden because reader is mid-chapter."""
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        client = TestClient(app)
        resp = client.post("/books/bk/query", json={
            "question": "Future",
            "search_type": "RAG_COMPLETION",  # skip LLM call
        })
        assert resp.status_code == 200
        body = resp.json()
        for r in body["results"]:
            assert "GRAPH_SPOILER" not in r["content"], f"leaked: {r}"

    def test_paragraph_cursor_injects_raw_read_paragraphs(self, tmp_path, monkeypatch):
        """Current chapter paragraphs 0..cursor appear as context items."""
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        import main as main_mod

        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))

        captured: dict = {}

        async def fake_complete(question, context):
            captured["context"] = context
            return "ok"

        monkeypatch.setattr(main_mod, "_complete_over_context", fake_complete)
        self._seed(tmp_path)
        client = TestClient(app)
        resp = client.post("/books/bk/query", json={
            "question": "Marley",
            "search_type": "GRAPH_COMPLETION",
        })
        assert resp.status_code == 200
        combined = " ".join(captured["context"])
        assert "READ_P0" in combined
        assert "READ_P1" in combined
        assert "UNREAD_P2" not in combined
        assert "UNREAD_P3" not in combined
        assert "UNREAD_P4" not in combined

    def test_no_paragraph_preserves_phase0_inclusive(self, tmp_path, monkeypatch):
        """Client sending only current_chapter: graph includes that chapter (Phase 0 behavior)."""
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path)
        # Overwrite progress to drop paragraph.
        (tmp_path / "bk" / "reading_progress.json").write_text(json.dumps({
            "book_id": "bk", "current_chapter": 3,
        }))
        client = TestClient(app)
        resp = client.post("/books/bk/query", json={
            "question": "Future",
            "search_type": "RAG_COMPLETION",
        })
        assert resp.status_code == 200
        body = resp.json()
        # Without paragraph cursor, chapter-3 graph nodes ARE visible.
        assert any("GRAPH_SPOILER" in r["content"] for r in body["results"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestQueryEndpointParagraphGate -v`
Expected: FAILs — paragraph-aware logic doesn't exist.

- [ ] **Step 3: Rewrite `query_book`**

In `main.py`, replace the body of `query_book` with:

```python
@app.post("/books/{book_id}/query", response_model=QueryResponse)
async def query_book(book_id: SafeBookId, req: QueryRequest) -> QueryResponse:
    """Query the knowledge graph with reader-progress fog-of-war.

    Filter semantics:
    - If current_paragraph is set, the graph is filtered to chapters
      STRICTLY BEFORE current_chapter, and paragraphs 0..current_paragraph
      of the current chapter are loaded from raw text and injected as
      additional context.
    - If current_paragraph is not set, Phase 0 behavior applies:
      graph is filtered INCLUSIVE of current_chapter, no raw-text injection.
    """
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

    # Paragraph-aware fog-of-war: exclude current chapter from graph when
    # a paragraph cursor exists; otherwise fall back to Phase 0 inclusive.
    if disk_paragraph is not None:
        graph_max_chapter = max(current_chapter - 1, 0)
        current_chapter_paragraphs = _load_paragraphs_up_to(
            book_id, current_chapter, disk_paragraph
        )
    else:
        graph_max_chapter = current_chapter
        current_chapter_paragraphs = []

    results = _answer_from_allowed_nodes(
        book_id, req.question, graph_max_chapter=graph_max_chapter
    )

    # For GRAPH_COMPLETION, combine graph context + raw-text paragraphs and
    # pass ONLY that to the LLM. Non-completion searches return the graph
    # results list as-is (no raw paragraphs added to results to avoid
    # cluttering keyword-score rankings; they're LLM-context only).
    answer = ""
    if req.search_type == "GRAPH_COMPLETION":
        graph_context = [r.content for r in results[:15]]
        combined = graph_context + current_chapter_paragraphs
        answer = await _complete_over_context(req.question, combined)

    return QueryResponse(
        book_id=book_id,
        question=req.question,
        search_type=req.search_type,
        current_chapter=current_chapter,
        answer=answer,
        results=results,
        result_count=len(results),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_main.py::TestQueryEndpointParagraphGate -v`
Expected: 3/3 PASS.

Run: `pytest tests/test_main.py -v` — full file green.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(query): paragraph-granular fog-of-war with raw-text injection"
```

---

## Task 6: Make `QueryResponse` surface the paragraph cursor

**Files:**
- Modify: `main.py` (`QueryResponse`, `query_book` return)
- Test: `tests/test_main.py`

This is UX wiring: when the frontend gets a query response it may want to display "answering based on chapter 3 paragraph 12" to reassure the reader. Keep the field optional for backward compatibility.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
class TestQueryResponseIncludesParagraph:
    def _seed(self, tmp_path, book_id="bk", with_paragraph=True):
        batches = tmp_path / book_id / "batches"
        batches.mkdir(parents=True)
        (batches / "b1.json").write_text(json.dumps({"characters": []}))
        (tmp_path / book_id / "pipeline_state.json").write_text(json.dumps({
            "book_id": book_id, "ready_for_query": True,
            "current_stage": "complete", "stages": {},
        }))
        progress = {"book_id": book_id, "current_chapter": 3}
        if with_paragraph:
            progress["current_paragraph"] = 7
        (tmp_path / book_id / "reading_progress.json").write_text(json.dumps(progress))

    def test_response_includes_paragraph_when_set(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path, with_paragraph=True)
        client = TestClient(app)
        resp = client.post("/books/bk/query", json={
            "question": "anything", "search_type": "RAG_COMPLETION",
        })
        assert resp.status_code == 200
        assert resp.json()["current_paragraph"] == 7

    def test_response_paragraph_null_when_unset(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path, with_paragraph=False)
        client = TestClient(app)
        resp = client.post("/books/bk/query", json={
            "question": "anything", "search_type": "RAG_COMPLETION",
        })
        assert resp.status_code == 200
        assert resp.json()["current_paragraph"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestQueryResponseIncludesParagraph -v`
Expected: FAIL — `current_paragraph` not in response.

- [ ] **Step 3: Add field to `QueryResponse`**

Find `QueryResponse` in `main.py` (around line 175) and add:

```python
    current_paragraph: int | None = None
```

right after `current_chapter: int`.

- [ ] **Step 4: Populate it in `query_book`**

In `query_book`, modify the `return QueryResponse(...)` statement to include `current_paragraph=disk_paragraph,`:

```python
    return QueryResponse(
        book_id=book_id,
        question=req.question,
        search_type=req.search_type,
        current_chapter=current_chapter,
        current_paragraph=disk_paragraph,
        answer=answer,
        results=results,
        result_count=len(results),
    )
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_main.py::TestQueryResponseIncludesParagraph -v`
Expected: 2/2 PASS.

Run: `pytest tests/test_main.py -v` — no regressions.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(query): include current_paragraph in QueryResponse"
```

---

## Task 7: Full sweep + CLAUDE.md Phase 1 docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Full test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: all tests pass; new test count should be previous-total + ~12 from Phase 1. If anything fails, STOP and report.

- [ ] **Step 2: Update CLAUDE.md**

Find the existing `### Fog-of-War Retrieval (Phase 0)` subsection in `CLAUDE.md`. Replace its content (keep the heading; rename it) with:

```markdown
### Fog-of-War Retrieval (Phases 0 + 1)

Reader progress is persisted per book in `reading_progress.json` as `{current_chapter, current_paragraph?}`. Paragraph is 0-indexed and optional — clients that send only `current_chapter` get Phase-0-compatible chapter-inclusive filtering.

At query time, `pipeline/spoiler_filter.py` walks `data/processed/{book_id}/batches/*.json` and builds an allowlist of nodes whose `effective_latest_chapter` (= max of `first_chapter`, `last_known_chapter`, `chapter`) is ≤ a chapter bound. The bound is:
- `current_chapter` (inclusive) when `current_paragraph` is None
- `current_chapter - 1` (strict) when `current_paragraph` is set — the current chapter is excluded from the graph and comes from raw text instead.

When a paragraph cursor is set, `_load_paragraphs_up_to(book_id, current_chapter, current_paragraph)` loads paragraphs 0..cursor from `raw/chapters/chapter_NN.txt` and, for `GRAPH_COMPLETION`, those paragraphs are concatenated with the allowed-node context and passed to the LLM via `_complete_over_context`.

Limitations (addressed in Phase 2):
- Node descriptions are still chapter-granular. A Character with `last_known_chapter=4` may have had its description influenced by chapter-5 content the LLM saw during batch extraction, even if the reader is at chapter-4 paragraph-3. Phase 2 introduces per-paragraph node snapshots.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document Phase 1 paragraph-granular fog-of-war"
```

---

## Self-Review Checklist

- [ ] `_get_reading_progress` returns `tuple[int, int | None]`; every caller is a tuple-unpacking callsite.
- [ ] `ProgressRequest` / `ProgressResponse` / `QueryResponse` all have `current_paragraph: int | None = None`.
- [ ] `_answer_from_allowed_nodes` uses the kwarg `graph_max_chapter` (not `cursor`).
- [ ] When `current_paragraph` is None, `query_book` behaves exactly like Phase 0 (tests `TestQueryEndpointFogOfWar` still pass unchanged, and `test_no_paragraph_preserves_phase0_inclusive` covers the regression).
- [ ] When `current_paragraph` is set, chapter-N graph nodes are hidden and chapter-N paragraphs 0..cursor are injected into GRAPH_COMPLETION context.
- [ ] Full `pytest tests/` passes.
- [ ] CLAUDE.md reflects Phase 1 semantics.

## Out of Scope (Phase 2 Plan)

- Per-paragraph node snapshots. Requires extraction at paragraph granularity, a new versioned schema (`CharacterSnapshot` linked to a stable `CharacterIdentity`, etc.), and retrieval scoped to the latest snapshot with `window_end <= cursor`. Multiplies LLM cost by ~1-2 orders of magnitude and reshapes the batcher. Not scoped here.
- Frontend work to actually send `current_paragraph` to the progress endpoint. Phase 1 exposes the API; the React side is a separate slice.
