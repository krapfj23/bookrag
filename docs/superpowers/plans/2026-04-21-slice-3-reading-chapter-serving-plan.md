# Slice 3 — reading-chapter-serving Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Generator note — UI tasks 5–8, 11, 12, 13:** when implementing `ChapterRow`, `ProgressiveBlur`, `LockState`, `Highlight`, and the `ReadingScreen` center/left/right columns, invoke the `frontend-design:frontend-design` skill so ported components stay visually faithful to `design-handoff/project/components.jsx`, `components2.jsx`, and `screens.jsx`. The existing TSX conventions in `frontend/src/components/` (inline-style objects driven by `var(--*)` tokens, no CSS modules, no class-based styling, colocated `*.test.tsx`) must be preserved.

**Goal:** Ship the Reading screen end-to-end. Add two new FastAPI endpoints (`GET /books/{id}/chapters`, `GET /books/{id}/chapters/{n}`) that serve raw-chapter paragraphs with a first-line title heuristic. Add two new routes to the frontend (`/books/:bookId/read` redirects to `/books/:bookId/read/:currentChapter`; the latter renders a three-column `ReadingScreen`). Wire clicking a `BookCard` to navigate there, persist progress via the existing `POST /books/{id}/progress` on the "Mark as read" button, and render chapter teasers/locks for unread chapters. Chat shell is a disabled shell only — no bubble wiring.

**Architecture:** Backend is additive. Two new routes are appended to `main.py` next to `set_progress`, sharing a helper `_list_chapter_files(book_id)` that resolves the raw chapters directory and returns a sorted list of paths, plus `_load_chapter(book_id, n)` that reads the raw chapter file, derives the title via first-line heuristic, and paragraph-splits on `\n\n`. Both routes 404 cleanly for unknown book ids, for `ready_for_query == false`, or for out-of-range `n`. `POST /books/{id}/progress` is unchanged — the existing `test_main.py::TestProgressEndpoint::test_set_progress` is the regression already; we add a single sharper assertion ensuring the file contains `{"current_chapter": N}` (shape-only) in a new test file without duplicating coverage.

Frontend threads three new routes through `App.tsx`:
- `/books/:bookId/read` renders a tiny redirect component (`BookReadingRedirect`) that fetches `/books`, finds the matching book, and `<Navigate replace>`s to `/books/:bookId/read/:current_chapter`.
- `/books/:bookId/read/:chapterNum` renders `<ReadingScreen />`.
- Clicking a `BookCard` calls `useNavigate()` to reach `/books/:bookId/read`.

`ReadingScreen` owns three columns: left sidebar (fetches `GET /books/{id}/chapters` + `GET /books` for current_chapter/title once per mount; re-fetches `/books` after a successful progress POST so sidebar state updates without a page reload); center column (fetches `GET /books/{id}/chapters/{n}` on each `chapterNum` change, except when `n > current_chapter + 1` — in that case it renders `LockState` only and skips the fetch); right column (chat shell — disabled textarea + LockState spoilerSafe pill). The NavBar derives active tab from `useLocation().pathname.startsWith("/books/")` → `"reading"`.

A hermetic Playwright suite (`frontend/e2e/reading.spec.ts`) intercepts `/books`, `/books/{id}/chapters`, `/books/{id}/chapters/{n}`, and `/books/{id}/progress` with `page.route()` fixtures so the suite runs against a fresh Vite dev server with no live backend.

**Tech Stack:** React 18, TypeScript, Vite 5, Vitest 2 + jsdom + Testing Library, `react-router-dom@^6`, `@playwright/test` (unchanged from slice 2). Backend: FastAPI, Pydantic, loguru, pytest (unchanged from slice 1 + 2). No new dependencies. No new env vars. No new CSS files — uses existing `tokens.css` and `animations.css`.

---

## File Structure

**Backend — modified:**
- `main.py` — add `ChapterSummary` + `Chapter` Pydantic models, `_list_chapter_files`, `_load_chapter`, and two routes.

**Backend — new:**
- `tests/test_chapters_endpoint.py` — all cases for the two new routes + one shape-check regression for `POST /progress`.

**Frontend — new files:**
- `frontend/src/components/ChapterRow.tsx`, `frontend/src/components/ChapterRow.test.tsx`
- `frontend/src/components/ProgressiveBlur.tsx`, `frontend/src/components/ProgressiveBlur.test.tsx`
- `frontend/src/components/LockState.tsx`, `frontend/src/components/LockState.test.tsx`
- `frontend/src/components/Highlight.tsx`, `frontend/src/components/Highlight.test.tsx`
- `frontend/src/screens/ReadingScreen.tsx`, `frontend/src/screens/ReadingScreen.test.tsx`
- `frontend/src/screens/BookReadingRedirect.tsx`, `frontend/src/screens/BookReadingRedirect.test.tsx`
- `frontend/e2e/reading.spec.ts`

**Frontend — modified files:**
- `frontend/src/lib/api.ts` — add `fetchChapters`, `fetchChapter`, `setProgress`; add `ChapterSummary` + `Chapter` types.
- `frontend/src/lib/api.test.ts` — tests for the three new functions.
- `frontend/src/components/icons.tsx` — add `IcLock`, `IcUnlock`, `IcBookmark`, `IcDot`, `IcChat`, `IcArrowL`, `IcArrowR`.
- `frontend/src/components/NavBar.tsx` — add `Reading` as a real active tab on `/books/*` (no `to`; stays inert as a link target — active display only).
- `frontend/src/components/NavBar.test.tsx` — add an `/books/xxx/read/1` assertion.
- `frontend/src/components/BookCard.tsx` — wire `onClick` to `useNavigate()` for `/books/:bookId/read`.
- `frontend/src/components/BookCard.test.tsx` — add click-navigation test.
- `frontend/src/screens/LibraryScreen.tsx` — pass navigate handler down (or, simpler, let `BookCard` own navigation).
- `frontend/src/App.tsx` — add two routes.
- `frontend/src/App.test.tsx` — add a route assertion for `/books/:bookId/read/1`.

---

## Task 1: Backend — `GET /books/{book_id}/chapters` endpoint

**Files:**
- Modify: `main.py`
- Create: `tests/test_chapters_endpoint.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_chapters_endpoint.py`:

```python
"""Tests for GET /books/{book_id}/chapters and /books/{book_id}/chapters/{n}.

Covers:
- Happy path: 3 raw chapter files → 3 ChapterSummary entries in order.
- ready_for_query=False → 404.
- Unknown book_id → 404.
- Out-of-range n → 404 (n < 1 or n > total).
- Title heuristic: short first line without sentence terminator is used
  (chapter_02.txt 'The Last of the Spirits'); else 'Chapter N'.
- Paragraph split: backend splits raw text on '\\n\\n' and drops empties.
- POST /progress regression: the reading_progress.json file reflects
  the posted current_chapter.

Aligned with:
- docs/superpowers/specs/2026-04-21-slice-3-reading-chapter-serving.md
  acceptance criteria 3, 5, 9, 11, 12.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_mock_modules = {
    "cognee": types.ModuleType("cognee"),
    "cognee.infrastructure": types.ModuleType("cognee.infrastructure"),
    "cognee.infrastructure.llm": types.ModuleType("cognee.infrastructure.llm"),
    "cognee.infrastructure.llm.LLMGateway": types.ModuleType(
        "cognee.infrastructure.llm.LLMGateway"
    ),
    "cognee.modules": types.ModuleType("cognee.modules"),
    "cognee.modules.pipelines": types.ModuleType("cognee.modules.pipelines"),
    "cognee.modules.pipelines.tasks": types.ModuleType(
        "cognee.modules.pipelines.tasks"
    ),
    "cognee.modules.pipelines.tasks.task": types.ModuleType(
        "cognee.modules.pipelines.tasks.task"
    ),
    "cognee.tasks": types.ModuleType("cognee.tasks"),
    "cognee.tasks.storage": types.ModuleType("cognee.tasks.storage"),
}
_mock_modules["cognee.infrastructure.llm.LLMGateway"].LLMGateway = MagicMock()
_mock_modules["cognee.modules.pipelines"].run_pipeline = MagicMock()
_mock_modules["cognee.modules.pipelines.tasks.task"].Task = MagicMock()
_mock_modules["cognee.tasks.storage"].add_data_points = MagicMock()
for name, mod in _mock_modules.items():
    sys.modules.setdefault(name, mod)

from fastapi.testclient import TestClient

from models.pipeline_state import PipelineState, save_state


CH1_BODY = (
    "The Project Gutenberg eBook header line.\n\n"
    "Marley was dead: to begin with.\n\n"
    "Oh! But he was a tight-fisted hand at the grindstone, Scrooge!\n\n"
    "External heat and cold had little influence on Scrooge."
)

CH2_BODY = (
    "The Last of the Spirits\n\n"
    "\u201cAm I that man who lay upon the bed?\u201d he cried, upon his knees.\n\n"
    "The finger pointed from the grave to him, and back again."
)

CH3_BODY = (
    "*** END OF THE PROJECT GUTENBERG EBOOK ***\n\n"
    "Updated editions will replace the previous one."
)


def _write_ready_carol(processed_dir: Path, book_id: str, current_chapter: int = 1) -> None:
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text(CH1_BODY, encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_02.txt").write_text(CH2_BODY, encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_03.txt").write_text(CH3_BODY, encoding="utf-8")
    state = PipelineState.new(book_id, ["parse_epub", "validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    (book_dir / "reading_progress.json").write_text(
        json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
        encoding="utf-8",
    )


def _write_not_ready(processed_dir: Path, book_id: str) -> None:
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text("c1", encoding="utf-8")
    state = PipelineState.new(book_id, ["parse_epub"])
    state.status = "processing"
    state.ready_for_query = False
    save_state(state, book_dir / "pipeline_state.json")


@pytest.fixture
def client(tmp_path, monkeypatch):
    import importlib
    import models.config
    importlib.reload(models.config)
    config = models.config.BookRAGConfig(
        data_dir=tmp_path / "data",
        books_dir=tmp_path / "data" / "books",
        processed_dir=tmp_path / "data" / "processed",
    )
    (tmp_path / "data" / "processed").mkdir(parents=True, exist_ok=True)

    with patch("main.load_config", return_value=config), patch(
        "main.config", config
    ), patch("main.PipelineOrchestrator") as MockOrch:
        mock_orch = MockOrch.return_value
        mock_orch.run_in_background = MagicMock()
        mock_orch.get_state = MagicMock(return_value=None)

        import main as main_module
        main_module.config = config
        main_module.orchestrator = mock_orch

        yield TestClient(main_module.app), config, mock_orch


class TestListChapters:
    def test_happy_path_three_chapters(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3
        assert [c["num"] for c in body] == [1, 2, 3]
        assert body[1]["title"] == "The Last of the Spirits"
        assert body[0]["title"] == "Chapter 1"
        assert body[2]["title"] == "Chapter 3"
        assert all("word_count" in c and c["word_count"] > 0 for c in body)

    def test_unknown_book_returns_404(self, client):
        test_client, _, _ = client
        resp = test_client.get("/books/nosuch_book/chapters")
        assert resp.status_code == 404

    def test_not_ready_book_returns_404(self, client):
        test_client, config, _ = client
        _write_not_ready(Path(config.processed_dir), "wip_book_11111111")
        resp = test_client.get("/books/wip_book_11111111/chapters")
        assert resp.status_code == 404


class TestLoadChapter:
    def test_happy_path_chapter_one(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["num"] == 1
        assert body["title"] == "Chapter 1"  # first line too long + non-terminator-check fails
        assert len(body["paragraphs"]) == 4
        assert body["paragraphs"][1].startswith("Marley was dead")
        assert body["has_prev"] is False
        assert body["has_next"] is True
        assert body["total_chapters"] == 3

    def test_happy_path_chapter_two_title_heuristic(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["num"] == 2
        assert body["title"] == "The Last of the Spirits"
        assert body["has_prev"] is True
        assert body["has_next"] is True

    def test_chapter_three_has_next_false(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_prev"] is True
        assert body["has_next"] is False

    def test_n_zero_returns_404(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/0")
        assert resp.status_code == 404

    def test_n_too_large_returns_404(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/99")
        assert resp.status_code == 404

    def test_unknown_book_returns_404(self, client):
        test_client, _, _ = client
        resp = test_client.get("/books/nosuch_book/chapters/1")
        assert resp.status_code == 404


class TestProgressFileShape:
    """Regression for POST /progress — confirm the persisted JSON shape."""

    def test_progress_write_shape(self, client):
        test_client, config, mock_orch = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        mock_orch.get_state.return_value = PipelineState.new(
            "christmas_carol_e6ddcd76", ["validate"]
        )
        resp = test_client.post(
            "/books/christmas_carol_e6ddcd76/progress",
            json={"current_chapter": 2},
        )
        assert resp.status_code == 200
        path = (
            Path(config.processed_dir)
            / "christmas_carol_e6ddcd76"
            / "reading_progress.json"
        )
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["current_chapter"] == 2
        assert saved["book_id"] == "christmas_carol_e6ddcd76"
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/test_chapters_endpoint.py -v --tb=short
```

Expected: all nine new cases fail with 404 on the two new routes (routes are not yet registered). `TestProgressFileShape::test_progress_write_shape` passes because `POST /progress` already exists.

- [ ] **Step 1.3: Add `ChapterSummary` model + helper + route**

Modify `main.py`. Add the Pydantic models immediately after `class BookSummary(BaseModel):` (around line 144):

```python
class ChapterSummary(BaseModel):
    num: int
    title: str
    word_count: int


class Chapter(BaseModel):
    num: int
    title: str
    paragraphs: list[str]
    has_prev: bool
    has_next: bool
    total_chapters: int
```

Add helpers just above `_get_reading_progress` (around line 358):

```python
def _list_chapter_files(book_id: str) -> list[Path]:
    """Return sorted chapter_*.txt paths for a ready book.

    Prefers raw/chapters/ (which preserves \\n\\n paragraph breaks).
    Returns [] if the book dir is missing OR ready_for_query is false.
    """
    from models.pipeline_state import load_state  # local import — avoid cycles

    book_dir = Path(config.processed_dir) / book_id
    state_path = book_dir / "pipeline_state.json"
    if not state_path.exists():
        return []
    try:
        state = load_state(state_path)
    except (json.JSONDecodeError, KeyError, OSError):
        return []
    if not state.ready_for_query:
        return []
    chapters_dir = book_dir / "raw" / "chapters"
    if not chapters_dir.exists():
        return []
    return sorted(chapters_dir.glob("chapter_*.txt"))


_TITLE_TERMINATORS = ".!?:"


def _derive_chapter_title(raw_text: str, n: int) -> str:
    """First non-empty stripped line if short + not sentence-terminated, else 'Chapter N'."""
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < 80 and stripped[-1] not in _TITLE_TERMINATORS:
            return stripped
        break
    return f"Chapter {n}"


def _load_chapter(book_id: str, n: int) -> Chapter | None:
    """Load a single chapter. Returns None if the book isn't ready or n is out of range."""
    files = _list_chapter_files(book_id)
    if not files:
        return None
    if n < 1 or n > len(files):
        return None
    raw_text = files[n - 1].read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    title = _derive_chapter_title(raw_text, n)
    return Chapter(
        num=n,
        title=title,
        paragraphs=paragraphs,
        has_prev=n > 1,
        has_next=n < len(files),
        total_chapters=len(files),
    )
```

Add the two routes just above `@app.post("/books/{book_id}/progress"` (around line 265):

```python
@app.get("/books/{book_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(book_id: SafeBookId) -> list[ChapterSummary]:
    """List chapter metadata for a ready book."""
    files = _list_chapter_files(book_id)
    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"Book '{book_id}' not found or not ready for query",
        )
    summaries: list[ChapterSummary] = []
    for idx, path in enumerate(files, start=1):
        raw_text = path.read_text(encoding="utf-8")
        summaries.append(
            ChapterSummary(
                num=idx,
                title=_derive_chapter_title(raw_text, idx),
                word_count=len(raw_text.split()),
            )
        )
    return summaries


@app.get("/books/{book_id}/chapters/{n}", response_model=Chapter)
async def get_chapter(book_id: SafeBookId, n: int) -> Chapter:
    """Load a single chapter's body as paragraph-split text."""
    chapter = _load_chapter(book_id, n)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {n} not found for book '{book_id}'",
        )
    return chapter
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/test_chapters_endpoint.py -v --tb=short
```

Expected: 10 passed.

- [ ] **Step 1.5: Confirm no regressions**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/ -v --tb=short -x
```

Expected: all prior backend tests still pass (existing 906+ plus 10 new).

- [ ] **Step 1.6: Commit**

```bash
git add main.py tests/test_chapters_endpoint.py
git commit -m "$(cat <<'EOF'
feat(api): add GET /books/{id}/chapters and /chapters/{n} endpoints

Both routes read from data/processed/{book_id}/raw/chapters/chapter_*.txt,
derive titles via a first-line heuristic (short line without sentence
terminator, else 'Chapter N'), and paragraph-split on \\n\\n. 404s are
returned for unknown books, not-ready books, and out-of-range n.
EOF
)"
```

---

## Task 2: Frontend — extend `lib/api.ts` with chapter + progress calls

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api.test.ts`

- [ ] **Step 2.1: Write failing tests**

Append to `frontend/src/lib/api.test.ts` (above the final `});` that closes the last describe block, or in a new describe appended at end — both work). Add new imports to the top import statement: `fetchChapters`, `fetchChapter`, `setProgress`, `type Chapter`, `type ChapterSummary`. Then append:

```ts
describe("fetchChapters", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs /books/{id}/chapters and returns the JSON array", async () => {
    const body: ChapterSummary[] = [
      { num: 1, title: "Chapter 1", word_count: 3000 },
      { num: 2, title: "The Last of the Spirits", word_count: 2000 },
    ];
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    const result = await fetchChapters("christmas_carol_e6ddcd76");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books/christmas_carol_e6ddcd76/chapters"
    );
    expect(result).toEqual(body);
  });

  it("throws on 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;
    await expect(fetchChapters("missing")).rejects.toThrow(/404/);
  });
});

describe("fetchChapter", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs /books/{id}/chapters/{n} and returns Chapter", async () => {
    const body: Chapter = {
      num: 2,
      title: "The Last of the Spirits",
      paragraphs: ["Am I that man who lay upon the bed?", "The finger pointed..."],
      has_prev: true,
      has_next: true,
      total_chapters: 3,
    };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    const result = await fetchChapter("christmas_carol_e6ddcd76", 2);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books/christmas_carol_e6ddcd76/chapters/2"
    );
    expect(result).toEqual(body);
  });

  it("throws on 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;
    await expect(fetchChapter("bk", 99)).rejects.toThrow(/404/);
  });
});

describe("setProgress", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("POSTs {current_chapter: n} to /books/{id}/progress", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ book_id: "bk", current_chapter: 3 }),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    const result = await setProgress("bk", 3);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/books/bk/progress");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(init.body).toBe(JSON.stringify({ current_chapter: 3 }));
    expect(result).toEqual({ book_id: "bk", current_chapter: 3 });
  });

  it("throws on non-2xx", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
    }) as unknown as typeof fetch;
    await expect(setProgress("bk", 0)).rejects.toThrow(/400/);
  });
});
```

- [ ] **Step 2.2: Run — confirm failure**

```bash
cd frontend && npm test -- api
```

Expected: three new describe blocks fail because the functions and types are not exported.

- [ ] **Step 2.3: Add the new types and functions to `lib/api.ts`**

Append to `frontend/src/lib/api.ts`:

```ts
export type ChapterSummary = {
  num: number;
  title: string;
  word_count: number;
};

export type Chapter = {
  num: number;
  title: string;
  paragraphs: string[];
  has_prev: boolean;
  has_next: boolean;
  total_chapters: number;
};

export type ProgressResponse = {
  book_id: string;
  current_chapter: number;
};

export async function fetchChapters(book_id: string): Promise<ChapterSummary[]> {
  const resp = await fetch(`${BASE_URL}/books/${book_id}/chapters`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/chapters failed: ${resp.status}`);
  }
  return (await resp.json()) as ChapterSummary[];
}

export async function fetchChapter(book_id: string, n: number): Promise<Chapter> {
  const resp = await fetch(`${BASE_URL}/books/${book_id}/chapters/${n}`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/chapters/${n} failed: ${resp.status}`);
  }
  return (await resp.json()) as Chapter;
}

export async function setProgress(
  book_id: string,
  current_chapter: number
): Promise<ProgressResponse> {
  const resp = await fetch(`${BASE_URL}/books/${book_id}/progress`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_chapter }),
  });
  if (!resp.ok) {
    throw new Error(`POST /books/${book_id}/progress failed: ${resp.status}`);
  }
  return (await resp.json()) as ProgressResponse;
}
```

- [ ] **Step 2.4: Run — confirm pass**

```bash
cd frontend && npm test -- api
```

Expected: all api tests pass (6 new + existing).

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add fetchChapters, fetchChapter, setProgress API clients

All three helpers mirror the existing fetchBooks/fetchStatus pattern:
typed fetch, throw-on-non-OK with a status-bearing message. Adds
ChapterSummary and Chapter types that match the backend contract.
EOF
)"
```

---

## Task 3: Icons — add `IcLock`, `IcUnlock`, `IcBookmark`, `IcDot`, `IcChat`, `IcArrowL`, `IcArrowR`

**Files:**
- Modify: `frontend/src/components/icons.tsx`

- [ ] **Step 3.1: Add the seven missing icons**

Append to `frontend/src/components/icons.tsx` after the existing `IcClose` export:

```tsx
export const IcLock = (p: Props) => (
  <Icon {...p}>
    <path d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 4 0v2.5" />
    <circle cx="8" cy="10.5" r="0.7" fill="currentColor" stroke="none" />
  </Icon>
);
export const IcUnlock = (p: Props) => (
  <Icon {...p}>
    <path d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 3.8-.8" />
  </Icon>
);
export const IcBookmark = (p: Props) => (
  <Icon {...p}>
    <path d="M4 2.5h8v11l-4-2.5-4 2.5v-11z" />
  </Icon>
);
export const IcDot = (p: Props) => (
  <Icon {...p}>
    <circle cx="8" cy="8" r="3" fill="currentColor" stroke="none" />
  </Icon>
);
export const IcChat = (p: Props) => (
  <Icon {...p}>
    <path d="M3 4a1.5 1.5 0 0 1 1.5-1.5h7A1.5 1.5 0 0 1 13 4v5a1.5 1.5 0 0 1-1.5 1.5H7l-3 3v-3h-1A1.5 1.5 0 0 1 3 9V4z" />
  </Icon>
);
export const IcArrowL = (p: Props) => (
  <Icon {...p} d="M12.5 8h-9m3-3l-3 3 3 3" />
);
export const IcArrowR = (p: Props) => (
  <Icon {...p} d="M3.5 8h9m-3-3l3 3-3 3" />
);
```

- [ ] **Step 3.2: Verify imports still compile**

```bash
cd frontend && npm run build
```

Expected: `tsc -b` reports 0 errors. (No new tests for icons; existing conventions don't test them individually.)

- [ ] **Step 3.3: Commit**

```bash
git add frontend/src/components/icons.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add IcLock, IcUnlock, IcBookmark, IcDot, IcChat, IcArrowL, IcArrowR

Ports the seven icons used by ChapterRow, LockState, ProgressiveBlur,
and ReadingScreen prev/next controls from design-handoff/project/icons.jsx.
EOF
)"
```

---

## Task 4: `ChapterRow` component

**Files:**
- Create: `frontend/src/components/ChapterRow.tsx`
- Create: `frontend/src/components/ChapterRow.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 4.1: Write the failing test**

Create `frontend/src/components/ChapterRow.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ChapterRow } from "./ChapterRow";

describe("ChapterRow", () => {
  it("renders the zero-padded number and title", () => {
    render(<ChapterRow num={2} title="The Last of the Spirits" state="current" />);
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("The Last of the Spirits")).toBeInTheDocument();
  });

  it("marks state='current' with aria-current and accent styling", () => {
    render(<ChapterRow num={3} title="Now Reading" state="current" />);
    const row = screen.getByRole("button");
    expect(row).toHaveAttribute("aria-current", "true");
    expect(row).toHaveAttribute("data-state", "current");
  });

  it("marks state='read' with the check icon and non-current aria", () => {
    render(<ChapterRow num={1} title="Already Read" state="read" />);
    const row = screen.getByRole("button");
    expect(row).toHaveAttribute("data-state", "read");
    expect(row).not.toHaveAttribute("aria-current");
  });

  it("marks state='locked' as disabled with cursor not-allowed", () => {
    render(<ChapterRow num={4} title="Future" state="locked" />);
    const row = screen.getByRole("button");
    expect(row).toHaveAttribute("data-state", "locked");
    expect(row).toHaveAttribute("aria-disabled", "true");
    expect(row).toHaveStyle({ cursor: "not-allowed" });
  });

  it("calls onClick when state is 'read' or 'current'", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ChapterRow num={1} title="Go" state="read" onClick={onClick} />);
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onClick when state is 'locked'", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ChapterRow num={5} title="No" state="locked" onClick={onClick} />);
    await user.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 4.2: Run — confirm failure**

```bash
cd frontend && npm test -- ChapterRow
```

Expected: module not found / file missing.

- [ ] **Step 4.3: Create `ChapterRow.tsx`**

Create `frontend/src/components/ChapterRow.tsx`:

```tsx
import type { CSSProperties } from "react";
import { IcDot, IcCheck, IcLock } from "./icons";

export type ChapterRowState = "read" | "current" | "locked";

type ChapterRowProps = {
  num: number;
  title: string;
  state: ChapterRowState;
  onClick?: () => void;
};

export function ChapterRow({ num, title, state, onClick }: ChapterRowProps) {
  const isLocked = state === "locked";
  const isCurrent = state === "current";
  const isRead = state === "read";

  const rootStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "42px 1fr auto",
    alignItems: "center",
    gap: 14,
    padding: "14px 20px",
    width: "100%",
    textAlign: "left",
    border: 0,
    borderBottom: "var(--hairline)",
    fontFamily: "var(--sans)",
    background: isCurrent ? "var(--accent-softer)" : "transparent",
    color: isLocked ? "var(--ink-3)" : "var(--ink-1)",
    cursor: isLocked ? "not-allowed" : "pointer",
    transition: "background var(--dur) var(--ease)",
  };

  return (
    <button
      type="button"
      role="button"
      onClick={() => {
        if (!isLocked) onClick?.();
      }}
      aria-current={isCurrent ? "true" : undefined}
      aria-disabled={isLocked ? "true" : undefined}
      data-state={state}
      style={rootStyle}
    >
      <span
        style={{
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 14,
          color: isCurrent
            ? "var(--accent)"
            : isLocked
            ? "var(--ink-4)"
            : "var(--ink-3)",
          fontVariantNumeric: "tabular-nums",
          letterSpacing: 0.3,
        }}
      >
        {num.toString().padStart(2, "0")}
      </span>
      <span
        style={{
          fontFamily: "var(--serif)",
          fontSize: 16,
          fontWeight: isCurrent ? 500 : 400,
          color: isLocked
            ? "var(--ink-3)"
            : isRead
            ? "var(--ink-2)"
            : "var(--ink-0)",
          letterSpacing: -0.2,
        }}
      >
        {title}
      </span>
      <span
        style={{ width: 20, display: "inline-flex", justifyContent: "flex-end" }}
      >
        {isCurrent && (
          <span style={{ color: "var(--accent)" }}>
            <IcDot size={10} />
          </span>
        )}
        {isRead && (
          <span style={{ color: "var(--ink-3)" }}>
            <IcCheck size={13} />
          </span>
        )}
        {isLocked && (
          <span style={{ color: "var(--ink-4)" }}>
            <IcLock size={13} />
          </span>
        )}
      </span>
    </button>
  );
}
```

- [ ] **Step 4.4: Run — confirm pass**

```bash
cd frontend && npm test -- ChapterRow
```

Expected: 6 passed.

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/components/ChapterRow.tsx frontend/src/components/ChapterRow.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port ChapterRow component

Three states: read (check icon), current (accent bg, dot, aria-current),
locked (padlock, aria-disabled, not-allowed cursor). Clicks on locked
rows are a no-op; clicks on read/current call onClick.
EOF
)"
```

---

## Task 5: `ProgressiveBlur`, `LockState`, `Highlight` components

**Files:**
- Create: `frontend/src/components/ProgressiveBlur.tsx`, `ProgressiveBlur.test.tsx`
- Create: `frontend/src/components/LockState.tsx`, `LockState.test.tsx`
- Create: `frontend/src/components/Highlight.tsx`, `Highlight.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 5.1: Write failing `ProgressiveBlur` test**

Create `frontend/src/components/ProgressiveBlur.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProgressiveBlur } from "./ProgressiveBlur";

describe("ProgressiveBlur", () => {
  it("renders its children", () => {
    render(
      <ProgressiveBlur locked={false}>
        <p>Visible paragraph</p>
      </ProgressiveBlur>
    );
    expect(screen.getByText("Visible paragraph")).toBeInTheDocument();
  });

  it("when locked, overlays a blur + CTA pill", () => {
    render(
      <ProgressiveBlur locked>
        <p>Hidden-ish</p>
      </ProgressiveBlur>
    );
    expect(screen.getByText(/advance to reveal/i)).toBeInTheDocument();
    expect(screen.getByText("Hidden-ish")).toBeInTheDocument();
  });

  it("when unlocked, omits the CTA pill", () => {
    render(
      <ProgressiveBlur locked={false}>
        <p>Open</p>
      </ProgressiveBlur>
    );
    expect(screen.queryByText(/advance to reveal/i)).toBeNull();
  });
});
```

- [ ] **Step 5.2: Write failing `LockState` test**

Create `frontend/src/components/LockState.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LockState } from "./LockState";

describe("LockState", () => {
  it("renders spoilerSafe pill with label", () => {
    render(<LockState variant="spoilerSafe" label="safe through ch. 3" />);
    expect(screen.getByText(/safe through ch\. 3/i)).toBeInTheDocument();
  });

  it("spoilerSafe is a small pill (role status)", () => {
    render(<LockState variant="spoilerSafe" label="x" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders chapterLock full panel with title and padlock", () => {
    render(
      <LockState
        variant="chapterLock"
        chapterTitle="The Last of the Spirits"
        chapterNum={4}
      />
    );
    expect(screen.getByText("The Last of the Spirits")).toBeInTheDocument();
    expect(screen.getByText(/locked/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 5.3: Write failing `Highlight` test**

Create `frontend/src/components/Highlight.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Highlight } from "./Highlight";

describe("Highlight", () => {
  it("renders children inline as a <mark>/<span> with default styling", () => {
    render(<Highlight>Scrooge</Highlight>);
    expect(screen.getByText("Scrooge")).toBeInTheDocument();
  });

  it("accepts a variant prop", () => {
    const { container } = render(
      <Highlight variant="entity">Marley</Highlight>
    );
    expect(container.querySelector("[data-variant='entity']")).toBeTruthy();
  });
});
```

- [ ] **Step 5.4: Run — confirm all three fail**

```bash
cd frontend && npm test -- ProgressiveBlur LockState Highlight
```

Expected: module not found for all three.

- [ ] **Step 5.5: Create `ProgressiveBlur.tsx`**

Port from `design-handoff/project/components2.jsx`. Because the JSX source renders blur as an absolutely-positioned overlay with `{ position: absolute, inset 0, bottom }`, our TypeScript version wraps children in a `position: relative` container and adds the blur overlay as an absolute child when `locked`:

```tsx
import type { PropsWithChildren } from "react";
import { IcLock } from "./icons";

type ProgressiveBlurProps = PropsWithChildren<{
  locked: boolean;
  height?: number;
}>;

export function ProgressiveBlur({
  locked,
  height = 260,
  children,
}: ProgressiveBlurProps) {
  return (
    <div style={{ position: "relative", overflow: "hidden" }}>
      {children}
      {locked && (
        <>
          <div
            aria-hidden="true"
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 0,
              height,
              pointerEvents: "none",
              background: `linear-gradient(to bottom,
                transparent 0%,
                color-mix(in oklab, var(--paper-0) 25%, transparent) 27.5%,
                color-mix(in oklab, var(--paper-0) 65%, transparent) 58.5%,
                var(--paper-0) 100%)`,
              backdropFilter: "blur(6px)",
              maskImage:
                "linear-gradient(to bottom, transparent 0%, #000 33%, #000 100%)",
              WebkitMaskImage:
                "linear-gradient(to bottom, transparent 0%, #000 33%, #000 100%)",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 40,
              left: 0,
              right: 0,
              display: "flex",
              justifyContent: "center",
              pointerEvents: "none",
            }}
          >
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 14px",
                borderRadius: "var(--r-pill)",
                background: "var(--paper-00)",
                color: "var(--ink-1)",
                boxShadow: "var(--shadow-1)",
                border: "var(--hairline)",
                fontFamily: "var(--sans)",
                fontSize: 12,
                pointerEvents: "auto",
                letterSpacing: 0.2,
              }}
            >
              <IcLock size={12} /> beyond your page — advance to reveal
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5.6: Create `LockState.tsx`**

Per PRD, two variants: `spoilerSafe` (used in the chat column) and `chapterLock` (used in the reading column for `n > current_chapter + 1`). The source JSX has four variants — we port the two actually used this slice and keep the discriminated-union shape in case slice 4 wants more.

```tsx
import { IcLock, IcBookmark, IcUnlock } from "./icons";

type CommonLabel = { label: string };
type LockStateProps =
  | ({ variant: "spoilerSafe" } & CommonLabel)
  | ({ variant: "locked" } & Partial<CommonLabel>)
  | ({ variant: "unlocked" } & Partial<CommonLabel>)
  | ({ variant: "current" } & Partial<CommonLabel>)
  | {
      variant: "chapterLock";
      chapterNum: number;
      chapterTitle: string;
    };

export function LockState(props: LockStateProps) {
  if (props.variant === "chapterLock") {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "80px 40px",
          gap: 16,
          color: "var(--ink-3)",
          fontFamily: "var(--sans)",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 999,
            background: "var(--paper-1)",
            color: "var(--ink-2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <IcLock size={18} />
        </div>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 22,
            color: "var(--ink-0)",
            letterSpacing: -0.3,
            textAlign: "center",
          }}
        >
          {props.chapterTitle}
        </div>
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
          Locked — reach chapter {props.chapterNum} to unlock
        </div>
      </div>
    );
  }

  const { variant } = props;
  const label =
    "label" in props && props.label
      ? props.label
      : variant === "locked"
      ? "Locked"
      : variant === "unlocked"
      ? "Unlocked"
      : variant === "current"
      ? "You're here"
      : "Spoiler-safe";
  const Icon =
    variant === "spoilerSafe" || variant === "locked"
      ? IcLock
      : variant === "current"
      ? IcBookmark
      : IcUnlock;
  const color =
    variant === "locked" ? "var(--ink-3)" : "var(--accent)";

  return (
    <span
      role="status"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--sans)",
        fontSize: 12,
        color,
        letterSpacing: 0.2,
      }}
    >
      <Icon size={12} />
      {label}
    </span>
  );
}
```

- [ ] **Step 5.7: Create `Highlight.tsx`**

```tsx
import type { PropsWithChildren, CSSProperties } from "react";

export type HighlightVariant = "mark" | "selection" | "entity" | "quote";

type HighlightProps = PropsWithChildren<{
  variant?: HighlightVariant;
}>;

const STYLES: Record<HighlightVariant, CSSProperties> = {
  mark: {
    background:
      "color-mix(in oklab, var(--accent-soft) 70%, transparent)",
    color: "var(--ink-0)",
  },
  selection: { background: "var(--accent)", color: "var(--paper-00)" },
  entity: { borderBottom: "1.5px solid var(--accent)", color: "var(--ink-0)" },
  quote: { background: "var(--accent-softer)", color: "var(--ink-0)" },
};

export function Highlight({ variant = "mark", children }: HighlightProps) {
  return (
    <span
      data-variant={variant}
      style={{ padding: "0 2px", borderRadius: "var(--r-xs)", ...STYLES[variant] }}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 5.8: Run — confirm pass**

```bash
cd frontend && npm test -- ProgressiveBlur LockState Highlight
```

Expected: 3 + 3 + 2 = 8 passed.

- [ ] **Step 5.9: Commit**

```bash
git add frontend/src/components/ProgressiveBlur.tsx frontend/src/components/ProgressiveBlur.test.tsx frontend/src/components/LockState.tsx frontend/src/components/LockState.test.tsx frontend/src/components/Highlight.tsx frontend/src/components/Highlight.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port ProgressiveBlur, LockState, Highlight components

ProgressiveBlur wraps children in position:relative and overlays a blur
+ 'advance to reveal' pill when locked. LockState ships the spoilerSafe
inline pill and the chapterLock full panel used by ReadingScreen's
unreached chapters. Highlight is visual-only (no selection logic).
EOF
)"
```

---

## Task 6: Wire `BookCard` click to navigate to `/books/:bookId/read`

**Files:**
- Modify: `frontend/src/components/BookCard.tsx`
- Modify: `frontend/src/components/BookCard.test.tsx`

- [ ] **Step 6.1: Update test to assert navigation**

Replace the entire content of `frontend/src/components/BookCard.test.tsx` with:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { BookCard } from "./BookCard";

describe("BookCard", () => {
  it("renders title, progress pill, and chapter-progress text", () => {
    render(
      <MemoryRouter>
        <BookCard
          book_id="christmas_carol_e6ddcd76"
          title="Christmas Carol"
          total_chapters={3}
          current_chapter={1}
        />
      </MemoryRouter>
    );
    expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("renders a BookCover with a stable mood", () => {
    const { container } = render(
      <MemoryRouter>
        <BookCard
          book_id="christmas_carol_e6ddcd76"
          title="Christmas Carol"
          total_chapters={3}
          current_chapter={1}
        />
      </MemoryRouter>
    );
    expect(container.querySelector("[data-mood]")).toBeTruthy();
  });

  it("navigates to /books/:bookId/read on click", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={
              <BookCard
                book_id="christmas_carol_e6ddcd76"
                title="Christmas Carol"
                total_chapters={3}
                current_chapter={1}
              />
            }
          />
          <Route
            path="/books/:bookId/read"
            element={<div>READING-LANDING</div>}
          />
        </Routes>
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /christmas carol/i }));
    expect(await screen.findByText("READING-LANDING")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6.2: Run — confirm failure on the navigation test**

```bash
cd frontend && npm test -- BookCard
```

Expected: the two existing tests still pass, the new navigation test fails because `BookCard` has no `role="button"` and does not call `useNavigate()`.

- [ ] **Step 6.3: Rewrite `BookCard.tsx`**

Replace `frontend/src/components/BookCard.tsx` with:

```tsx
import { useNavigate } from "react-router-dom";
import { BookCover } from "./BookCover";
import { ProgressPill } from "./ProgressPill";

export type BookCardProps = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
};

export function BookCard({
  book_id,
  title,
  total_chapters,
  current_chapter,
}: BookCardProps) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => navigate(`/books/${book_id}/read`)}
      aria-label={`${title}, continue reading`}
      style={{
        display: "block",
        textAlign: "left",
        fontFamily: "var(--sans)",
        cursor: "pointer",
        width: 200,
        padding: 0,
        background: "transparent",
        border: 0,
      }}
    >
      <BookCover book_id={book_id} title={title} />
      <div style={{ marginTop: 14 }}>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 16,
            fontWeight: 500,
            color: "var(--ink-0)",
            lineHeight: 1.25,
            letterSpacing: -0.2,
          }}
        >
          {title}
        </div>
        <div style={{ marginTop: 10 }}>
          <ProgressPill current={current_chapter} total={total_chapters} />
        </div>
      </div>
    </button>
  );
}
```

- [ ] **Step 6.4: Run — confirm pass**

```bash
cd frontend && npm test -- BookCard
```

Expected: 3 passed.

- [ ] **Step 6.5: Commit**

```bash
git add frontend/src/components/BookCard.tsx frontend/src/components/BookCard.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): wire BookCard click to navigate to /books/:bookId/read

BookCard becomes a <button> (for a11y + keyboard support) that calls
useNavigate() on click. LibraryScreen no longer needs to pass onClick —
BookCard owns the destination internally.
EOF
)"
```

---

## Task 7: Router — add `/books/:bookId/read` redirect + `/books/:bookId/read/:chapterNum` route

**Files:**
- Create: `frontend/src/screens/BookReadingRedirect.tsx`, `frontend/src/screens/BookReadingRedirect.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/components/NavBar.tsx`
- Modify: `frontend/src/components/NavBar.test.tsx`

- [ ] **Step 7.1: Write failing `BookReadingRedirect` test**

Create `frontend/src/screens/BookReadingRedirect.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { BookReadingRedirect } from "./BookReadingRedirect";

const CC = {
  book_id: "christmas_carol_e6ddcd76",
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 2,
  ready_for_query: true,
};

describe("BookReadingRedirect", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetches /books and <Navigate>s to /books/:bookId/read/:current_chapter", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([CC]),
    }) as unknown as typeof fetch;

    render(
      <MemoryRouter initialEntries={["/books/christmas_carol_e6ddcd76/read"]}>
        <Routes>
          <Route
            path="/books/:bookId/read"
            element={<BookReadingRedirect />}
          />
          <Route
            path="/books/:bookId/read/:chapterNum"
            element={<div data-testid="landed">LANDED</div>}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("landed")).toBeInTheDocument();
    });
  });

  it("shows a loading state before the books call resolves", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/books/christmas_carol_e6ddcd76/read"]}>
        <Routes>
          <Route path="/books/:bookId/read" element={<BookReadingRedirect />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText(/opening/i)).toBeInTheDocument();
  });

  it("shows an error when the book is not found in /books", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/books/missing_book/read"]}>
        <Routes>
          <Route path="/books/:bookId/read" element={<BookReadingRedirect />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 7.2: Write updated `App.test.tsx`**

Replace the entire content of `frontend/src/App.test.tsx` with:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";

describe("App router", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("renders LibraryScreen at /", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
  });

  it("renders UploadScreen placeholder at /upload", () => {
    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/add a book/i)).toBeInTheDocument();
  });

  it("mounts ReadingScreen at /books/:bookId/read/:chapterNum", async () => {
    // The ReadingScreen's own data fetches will fail against the stub, but
    // the route-level assertion is that the NavBar Reading tab becomes active.
    render(
      <MemoryRouter
        initialEntries={["/books/christmas_carol_e6ddcd76/read/1"]}
      >
        <App />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("Reading")).toHaveAttribute("data-active", "true");
    });
  });
});
```

- [ ] **Step 7.3: Write updated `NavBar.test.tsx`**

Append one more test inside the `describe("NavBar"` block of `frontend/src/components/NavBar.test.tsx`:

```tsx
  it("marks Reading active on /books/:bookId/read/:n", () => {
    renderAt("/books/christmas_carol_e6ddcd76/read/2");
    expect(screen.getByText("Reading")).toHaveAttribute("data-active", "true");
    expect(screen.getByText("Library")).toHaveAttribute("data-active", "false");
    expect(screen.getByText("Upload")).toHaveAttribute("data-active", "false");
  });
```

- [ ] **Step 7.4: Run tests — confirm failures**

```bash
cd frontend && npm test -- App NavBar BookReadingRedirect
```

Expected: `BookReadingRedirect` fails (file missing). `App` fails (route not registered). The new `NavBar` case fails because `tabForPath` doesn't yet match `/books/:id/read`.

- [ ] **Step 7.5: Update `NavBar.tsx` to recognize `/books/...` as the Reading tab**

In `frontend/src/components/NavBar.tsx`, replace the `tabForPath` function with:

```tsx
function tabForPath(pathname: string): NavTab {
  if (pathname === "/upload" || pathname.startsWith("/upload/")) return "upload";
  if (pathname.startsWith("/books/")) return "reading";
  return "library";
}
```

No other NavBar changes are needed — `Reading` stays inert (it has no `to`).

- [ ] **Step 7.6: Create `BookReadingRedirect.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { fetchBooks, type Book } from "../lib/api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "redirect"; to: string };

export function BookReadingRedirect() {
  const { bookId } = useParams<{ bookId: string }>();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    if (!bookId) {
      setState({ kind: "error", message: "Missing book id" });
      return;
    }
    fetchBooks()
      .then((books: Book[]) => {
        if (cancelled) return;
        const match = books.find((b) => b.book_id === bookId);
        if (!match) {
          setState({ kind: "error", message: `Book '${bookId}' not found` });
          return;
        }
        setState({
          kind: "redirect",
          to: `/books/${bookId}/read/${match.current_chapter}`,
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  if (state.kind === "redirect") {
    return <Navigate replace to={state.to} />;
  }
  if (state.kind === "error") {
    return (
      <div
        role="alert"
        style={{
          padding: 40,
          fontFamily: "var(--sans)",
          color: "var(--err)",
          textAlign: "center",
        }}
      >
        {state.message}
      </div>
    );
  }
  return (
    <div
      role="status"
      style={{
        padding: 40,
        fontFamily: "var(--sans)",
        fontSize: 14,
        color: "var(--ink-2)",
        textAlign: "center",
      }}
    >
      Opening your book…
    </div>
  );
}
```

- [ ] **Step 7.7: Update `App.tsx` to register the routes**

Replace `frontend/src/App.tsx` with:

```tsx
import { Routes, Route } from "react-router-dom";
import { LibraryScreen } from "./screens/LibraryScreen";
import { UploadScreen } from "./screens/UploadScreen";
import { ReadingScreen } from "./screens/ReadingScreen";
import { BookReadingRedirect } from "./screens/BookReadingRedirect";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryScreen />} />
      <Route path="/upload" element={<UploadScreen />} />
      <Route path="/books/:bookId/read" element={<BookReadingRedirect />} />
      <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
    </Routes>
  );
}
```

The `ReadingScreen` import will be unresolved until Task 9; leaving it here means the file won't compile until then. To keep tests green, add a minimal `ReadingScreen` stub now — it will be fleshed out in Task 9. Create `frontend/src/screens/ReadingScreen.tsx` as a two-line stub:

```tsx
export function ReadingScreen() {
  return <div data-testid="reading-screen-stub">Reading…</div>;
}
```

- [ ] **Step 7.8: Run — confirm pass**

```bash
cd frontend && npm test -- App NavBar BookReadingRedirect
```

Expected: all pass (App: 3, NavBar: 6, BookReadingRedirect: 3).

- [ ] **Step 7.9: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/NavBar.tsx frontend/src/components/NavBar.test.tsx frontend/src/screens/BookReadingRedirect.tsx frontend/src/screens/BookReadingRedirect.test.tsx frontend/src/screens/ReadingScreen.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add /books/:bookId/read routes + Reading tab activation

/books/:bookId/read resolves current_chapter via a tiny fetch-and-Navigate
component; /books/:bookId/read/:chapterNum renders ReadingScreen (stubbed
for now, filled in next commit). NavBar marks Reading active on any
/books/* path.
EOF
)"
```

---

## Task 8: `ReadingScreen` — left sidebar + center reading column (happy path)

**Files:**
- Modify: `frontend/src/screens/ReadingScreen.tsx` (replace stub)
- Create: `frontend/src/screens/ReadingScreen.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 8.1: Write the failing tests**

Create `frontend/src/screens/ReadingScreen.test.tsx`:

```tsx
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ReadingScreen } from "./ReadingScreen";
import * as api from "../lib/api";

const BOOK_ID = "christmas_carol_e6ddcd76";

function mockApi({
  books = [
    {
      book_id: BOOK_ID,
      title: "Christmas Carol",
      total_chapters: 3,
      current_chapter: 2,
      ready_for_query: true,
    },
  ],
  chapters = [
    { num: 1, title: "Chapter 1", word_count: 3000 },
    { num: 2, title: "The Last of the Spirits", word_count: 2000 },
    { num: 3, title: "Chapter 3", word_count: 500 },
  ],
  chapter2 = {
    num: 2,
    title: "The Last of the Spirits",
    paragraphs: [
      "Am I that man who lay upon the bed?",
      "The finger pointed from the grave to him.",
    ],
    has_prev: true,
    has_next: true,
    total_chapters: 3,
  },
}: Partial<{
  books: api.Book[];
  chapters: api.ChapterSummary[];
  chapter2: api.Chapter;
}> = {}) {
  vi.spyOn(api, "fetchBooks").mockResolvedValue(books);
  vi.spyOn(api, "fetchChapters").mockResolvedValue(chapters);
  vi.spyOn(api, "fetchChapter").mockImplementation(
    async (_id, n) =>
      ({
        num: n,
        title: n === 2 ? "The Last of the Spirits" : `Chapter ${n}`,
        paragraphs:
          n === 2
            ? chapter2.paragraphs
            : [`Paragraph for chapter ${n}`],
        has_prev: n > 1,
        has_next: n < 3,
        total_chapters: 3,
      }) as api.Chapter
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ReadingScreen", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the book title, chapter list, and current-chapter body", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);

    await waitFor(() => {
      expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    });
    expect(
      screen.getAllByText("The Last of the Spirits").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/am i that man/i)).toBeInTheDocument();
    expect(screen.getByText(/finger pointed/i)).toBeInTheDocument();
  });

  it("renders one <p> per paragraph in the response", async () => {
    mockApi();
    const { container } = renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => {
      expect(container.querySelectorAll("article p").length).toBe(2);
    });
  });

  it("clicking prev/next buttons navigates", async () => {
    mockApi();
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /previous chapter/i }));
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument()
    );
  });

  it("Next is disabled when current_chapter equals n (not yet unlocked)", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    const nextBtn = screen.getByRole("button", { name: /next chapter/i });
    expect(nextBtn).toBeDisabled();
  });

  it("Prev is disabled on chapter 1", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument()
    );
    const prevBtn = screen.getByRole("button", { name: /previous chapter/i });
    expect(prevBtn).toBeDisabled();
  });

  it("Mark as read POSTs {current_chapter: n+1} when n == current_chapter", async () => {
    mockApi();
    const setProgressSpy = vi
      .spyOn(api, "setProgress")
      .mockResolvedValue({ book_id: BOOK_ID, current_chapter: 3 });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);

    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    const mark = screen.getByRole("button", { name: /mark as read/i });
    await user.click(mark);

    await waitFor(() =>
      expect(setProgressSpy).toHaveBeenCalledWith(BOOK_ID, 3)
    );
  });

  it("Mark as read is hidden when n != current_chapter", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /mark as read/i })).toBeNull();
  });

  it("Mark as read is hidden when n == total_chapters", async () => {
    mockApi({
      books: [
        {
          book_id: BOOK_ID,
          title: "Christmas Carol",
          total_chapters: 3,
          current_chapter: 3,
          ready_for_query: true,
        },
      ],
    });
    renderAt(`/books/${BOOK_ID}/read/3`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 3/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /mark as read/i })).toBeNull();
  });

  it("shows a loading state while the chapter body is pending", async () => {
    vi.spyOn(api, "fetchBooks").mockResolvedValue([
      {
        book_id: BOOK_ID,
        title: "Christmas Carol",
        total_chapters: 3,
        current_chapter: 2,
        ready_for_query: true,
      },
    ]);
    vi.spyOn(api, "fetchChapters").mockResolvedValue([
      { num: 1, title: "Chapter 1", word_count: 100 },
      { num: 2, title: "The Last of the Spirits", word_count: 100 },
      { num: 3, title: "Chapter 3", word_count: 100 },
    ]);
    // Never-resolving promise for the chapter body
    vi.spyOn(api, "fetchChapter").mockImplementation(
      () => new Promise(() => {}) as Promise<api.Chapter>
    );

    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => {
      expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText(/loading chapter/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 8.2: Run — confirm failure**

```bash
cd frontend && npm test -- ReadingScreen
```

Expected: every test fails because `ReadingScreen` is still the two-line stub.

- [ ] **Step 8.3: Implement `ReadingScreen.tsx` (sidebar + center + stub right column)**

Replace `frontend/src/screens/ReadingScreen.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { ChapterRow, type ChapterRowState } from "../components/ChapterRow";
import { ProgressPill } from "../components/ProgressPill";
import { ProgressiveBlur } from "../components/ProgressiveBlur";
import { LockState } from "../components/LockState";
import { Button } from "../components/Button";
import { Row } from "../components/layout";
import { IcArrowL, IcArrowR, IcChat } from "../components/icons";
import {
  fetchBooks,
  fetchChapter,
  fetchChapters,
  setProgress,
  type Book,
  type Chapter,
  type ChapterSummary,
} from "../lib/api";

type BodyState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter };

export function ReadingScreen() {
  const { bookId = "", chapterNum = "1" } = useParams<{
    bookId: string;
    chapterNum: string;
  }>();
  const n = Number.parseInt(chapterNum, 10) || 1;
  const navigate = useNavigate();

  const [book, setBook] = useState<Book | null>(null);
  const [chapterList, setChapterList] = useState<ChapterSummary[] | null>(null);
  const [body, setBody] = useState<BodyState>({ kind: "idle" });

  // Fetch the book record + chapter list once
  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchBooks(), fetchChapters(bookId)])
      .then(([books, chapters]) => {
        if (cancelled) return;
        setBook(books.find((b) => b.book_id === bookId) ?? null);
        setChapterList(chapters);
      })
      .catch(() => {
        // sidebar stays empty; center column error-states will show separately
      });
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  // Fetch the chapter body every time n changes — unless the chapter is
  // >= current_chapter + 2 (fully locked, no fetch per PRD AC 9).
  useEffect(() => {
    if (!book) return;
    if (n > book.current_chapter + 1) {
      setBody({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setBody({ kind: "loading" });
    fetchChapter(bookId, n)
      .then((chapter) => {
        if (cancelled) return;
        setBody({ kind: "ok", chapter });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setBody({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [bookId, n, book?.current_chapter]);

  function rowStateFor(num: number): ChapterRowState {
    if (!book) return "locked";
    if (num < book.current_chapter) return "read";
    if (num === book.current_chapter) return "current";
    return "locked";
  }

  async function handleMarkAsRead() {
    if (!book) return;
    const next = n + 1;
    await setProgress(bookId, next);
    // Optimistically refetch the book record so the sidebar reflects new progress
    const fresh = await fetchBooks();
    setBook(fresh.find((b) => b.book_id === bookId) ?? null);
    navigate(`/books/${bookId}/read/${next}`);
  }

  const canPrev = n > 1;
  const canNext =
    body.kind === "ok" &&
    body.chapter.has_next &&
    book !== null &&
    n < book.current_chapter;
  const showMarkAsRead =
    book !== null && n === book.current_chapter && n < book.total_chapters;

  const lockedStrictly = book !== null && n > book.current_chapter + 1;
  const isTeaser = book !== null && n === book.current_chapter + 1;

  return (
    <div
      className="br"
      style={{ minHeight: "100vh", background: "var(--paper-0)" }}
    >
      <NavBar />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "260px 1fr 440px",
          minHeight: "calc(100vh - 56px)",
        }}
      >
        {/* LEFT */}
        <aside
          style={{
            borderRight: "var(--hairline)",
            padding: "32px 0",
            fontFamily: "var(--sans)",
          }}
        >
          <div style={{ padding: "0 24px 20px" }}>
            <div
              style={{
                fontFamily: "var(--serif)",
                fontStyle: "italic",
                fontSize: 20,
                letterSpacing: -0.3,
                color: "var(--ink-0)",
              }}
            >
              {book?.title ?? "…"}
            </div>
            <div style={{ marginTop: 14 }}>
              <ProgressPill
                current={book?.current_chapter ?? 1}
                total={book?.total_chapters ?? 1}
                variant="soft"
              />
            </div>
          </div>
          <div>
            {(chapterList ?? []).map((c) => (
              <ChapterRow
                key={c.num}
                num={c.num}
                title={c.title}
                state={rowStateFor(c.num)}
                onClick={() => navigate(`/books/${bookId}/read/${c.num}`)}
              />
            ))}
          </div>
        </aside>

        {/* CENTER */}
        <main
          style={{
            padding: "56px 56px 80px",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              maxWidth: 620,
              margin: "0 auto",
              position: "relative",
            }}
          >
            {lockedStrictly && body.kind === "idle" && (
              <LockState
                variant="chapterLock"
                chapterNum={n}
                chapterTitle={
                  chapterList?.find((c) => c.num === n)?.title ??
                  `Chapter ${n}`
                }
              />
            )}

            {body.kind === "loading" && (
              <div role="status" style={{ fontFamily: "var(--sans)", fontSize: 14, color: "var(--ink-2)" }}>
                Loading chapter…
              </div>
            )}
            {body.kind === "error" && (
              <div role="alert" style={{ color: "var(--err)" }}>
                Couldn't load the chapter. ({body.message})
              </div>
            )}
            {body.kind === "ok" && (
              <article>
                <div
                  style={{
                    fontFamily: "var(--sans)",
                    fontSize: 11,
                    letterSpacing: 1.6,
                    textTransform: "uppercase",
                    color: "var(--ink-3)",
                    marginBottom: 12,
                  }}
                >
                  Chapter {body.chapter.num} of {body.chapter.total_chapters}
                </div>
                <h2
                  style={{
                    margin: "0 0 28px",
                    fontFamily: "var(--serif)",
                    fontWeight: 400,
                    fontSize: 30,
                    letterSpacing: -0.5,
                    color: "var(--ink-0)",
                    lineHeight: 1.15,
                  }}
                >
                  {body.chapter.title}
                </h2>
                {isTeaser ? (
                  <ProgressiveBlur locked height={280}>
                    <div
                      style={{
                        fontFamily: "var(--serif)",
                        fontSize: 17,
                        lineHeight: 1.7,
                        color: "var(--ink-0)",
                      }}
                    >
                      <p style={{ margin: "0 0 22px", textWrap: "pretty" }}>
                        {body.chapter.paragraphs[0]}
                      </p>
                    </div>
                  </ProgressiveBlur>
                ) : (
                  <div
                    style={{
                      fontFamily: "var(--serif)",
                      fontSize: 17,
                      lineHeight: 1.7,
                      color: "var(--ink-0)",
                    }}
                  >
                    {body.chapter.paragraphs.map((p, i) => (
                      <p
                        key={i}
                        style={{ margin: "0 0 22px", textWrap: "pretty" }}
                      >
                        {p}
                      </p>
                    ))}
                  </div>
                )}

                <Row
                  gap={12}
                  style={{
                    marginTop: 48,
                    paddingTop: 24,
                    borderTop: "var(--hairline)",
                    justifyContent: "space-between",
                  }}
                >
                  <button
                    type="button"
                    disabled={!canPrev}
                    onClick={() => navigate(`/books/${bookId}/read/${n - 1}`)}
                    aria-label="Previous chapter"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "7px 14px",
                      height: 34,
                      fontSize: 14,
                      fontFamily: "var(--sans)",
                      fontWeight: 500,
                      borderRadius: "var(--r-md)",
                      background: "transparent",
                      color: "var(--ink-1)",
                      border: 0,
                      cursor: canPrev ? "pointer" : "not-allowed",
                      opacity: canPrev ? 1 : 0.4,
                    }}
                  >
                    <IcArrowL size={14} /> Previous
                  </button>
                  {showMarkAsRead && (
                    <Button variant="primary" onClick={handleMarkAsRead}>
                      Mark as read
                    </Button>
                  )}
                  <button
                    type="button"
                    disabled={!canNext}
                    onClick={() => navigate(`/books/${bookId}/read/${n + 1}`)}
                    aria-label="Next chapter"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "7px 14px",
                      height: 34,
                      fontSize: 14,
                      fontFamily: "var(--sans)",
                      fontWeight: 500,
                      borderRadius: "var(--r-md)",
                      background: "transparent",
                      color: "var(--ink-1)",
                      border: 0,
                      cursor: canNext ? "pointer" : "not-allowed",
                      opacity: canNext ? 1 : 0.4,
                    }}
                  >
                    Next <IcArrowR size={14} />
                  </button>
                </Row>
              </article>
            )}
          </div>
        </main>

        {/* RIGHT */}
        <aside
          style={{
            borderLeft: "var(--hairline)",
            display: "flex",
            flexDirection: "column",
            background:
              "color-mix(in oklab, var(--paper-0) 92%, var(--paper-1))",
          }}
        >
          <div
            style={{
              padding: "20px 24px",
              borderBottom: "var(--hairline)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Row gap={8}>
              <IcChat size={14} style={{ color: "var(--ink-2)" }} />
              <span
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--ink-0)",
                  letterSpacing: 0.2,
                }}
              >
                Margin notes
              </span>
            </Row>
            <LockState
              variant="spoilerSafe"
              label={`safe through ch. ${book?.current_chapter ?? 1}`}
            />
          </div>
          <div
            style={{
              flex: 1,
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
              color: "var(--ink-3)",
              fontFamily: "var(--sans)",
              fontSize: 13,
            }}
          >
            Chat coming soon — available in the next release.
          </div>
          <div style={{ padding: "16px 20px 20px" }}>
            <textarea
              disabled
              aria-disabled="true"
              title="Available in the next release"
              placeholder="Available in the next release"
              rows={1}
              style={{
                width: "100%",
                resize: "none",
                padding: "10px 12px",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--paper-2)",
                background: "var(--paper-1)",
                fontFamily: "var(--serif)",
                fontSize: 14,
                color: "var(--ink-3)",
                cursor: "not-allowed",
              }}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
```

- [ ] **Step 8.4: Run — confirm pass**

```bash
cd frontend && npm test -- ReadingScreen
```

Expected: all 9 tests pass.

- [ ] **Step 8.5: Commit**

```bash
git add frontend/src/screens/ReadingScreen.tsx frontend/src/screens/ReadingScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): implement ReadingScreen three-column layout

Left sidebar renders ChapterRow per chapter with read/current/locked
state derived from GET /books' current_chapter. Center column fetches
GET /books/{id}/chapters/{n} on every nav and renders the title + one
<p> per paragraph. Prev/Next are disabled at boundaries (next also
disabled when n == current_chapter — next chapter isn't unlocked yet).
Mark-as-read POSTs {current_chapter: n+1} and refetches /books so the
sidebar reflects the new progress without a full reload.
EOF
)"
```

---

## Task 9: `ReadingScreen` — teaser + strict-lock rendering

**Files:**
- Modify: `frontend/src/screens/ReadingScreen.test.tsx` (append tests)

The implementation for teaser (`n == current_chapter + 1`) and strict lock (`n > current_chapter + 1`) was already added in Task 8's impl. This task verifies it with explicit tests.

- [ ] **Step 9.1: Append the failing spoiler-lock tests**

Append inside the `describe("ReadingScreen"` block:

```tsx
  it("renders a teaser (first paragraph + ProgressiveBlur) when n == current_chapter + 1", async () => {
    // current_chapter = 2, we render chapter 3 → teaser mode
    vi.spyOn(api, "fetchBooks").mockResolvedValue([
      {
        book_id: BOOK_ID,
        title: "Christmas Carol",
        total_chapters: 5,
        current_chapter: 2,
        ready_for_query: true,
      },
    ]);
    vi.spyOn(api, "fetchChapters").mockResolvedValue([
      { num: 1, title: "Chapter 1", word_count: 100 },
      { num: 2, title: "Chapter 2", word_count: 100 },
      { num: 3, title: "Chapter 3", word_count: 100 },
      { num: 4, title: "Chapter 4", word_count: 100 },
      { num: 5, title: "Chapter 5", word_count: 100 },
    ]);
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 3,
      title: "Chapter 3",
      paragraphs: ["First teaser paragraph.", "Hidden paragraph."],
      has_prev: true,
      has_next: true,
      total_chapters: 5,
    });

    const { container } = renderAt(`/books/${BOOK_ID}/read/3`);
    await waitFor(() =>
      expect(screen.getByText(/first teaser paragraph/i)).toBeInTheDocument()
    );
    // Only one <p> in the article, not two
    expect(container.querySelectorAll("article p").length).toBe(1);
    // Progressive blur CTA is present
    expect(screen.getByText(/advance to reveal/i)).toBeInTheDocument();
  });

  it("renders LockState chapterLock and does NOT fetch when n > current_chapter + 1", async () => {
    vi.spyOn(api, "fetchBooks").mockResolvedValue([
      {
        book_id: BOOK_ID,
        title: "Christmas Carol",
        total_chapters: 5,
        current_chapter: 2,
        ready_for_query: true,
      },
    ]);
    vi.spyOn(api, "fetchChapters").mockResolvedValue([
      { num: 1, title: "Chapter 1", word_count: 100 },
      { num: 2, title: "Chapter 2", word_count: 100 },
      { num: 3, title: "Chapter 3", word_count: 100 },
      { num: 4, title: "Chapter 4", word_count: 100 },
      { num: 5, title: "Chapter 5", word_count: 100 },
    ]);
    const chapterSpy = vi.spyOn(api, "fetchChapter").mockResolvedValue(
      {} as api.Chapter
    );

    renderAt(`/books/${BOOK_ID}/read/5`);
    await waitFor(() =>
      expect(screen.getByText(/locked — reach chapter 5/i)).toBeInTheDocument()
    );
    expect(chapterSpy).not.toHaveBeenCalled();
  });
```

- [ ] **Step 9.2: Run — confirm pass immediately**

```bash
cd frontend && npm test -- ReadingScreen
```

Expected: 11 tests pass (9 from Task 8 + 2 new). Since Task 8's impl already handles these paths, the tests verify behavior, not drive new code.

- [ ] **Step 9.3: Commit**

```bash
git add frontend/src/screens/ReadingScreen.test.tsx
git commit -m "$(cat <<'EOF'
test(frontend): add coverage for ReadingScreen teaser + strict-lock paths

Pins AC 9: chapters where n == current_chapter + 1 render exactly the
first paragraph wrapped in ProgressiveBlur; chapters where n is
strictly beyond that render LockState chapterLock without fetching the
chapter body.
EOF
)"
```

---

## Task 10: Playwright — hermetic E2E for Library → Reading → Mark as read

**Files:**
- Create: `frontend/e2e/reading.spec.ts`

- [ ] **Step 10.1: Write the hermetic spec**

Create `frontend/e2e/reading.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const BOOK_ID = "christmas_carol_e6ddcd76";

type Books = Array<{
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  ready_for_query: boolean;
}>;

async function mockBooks(page: Page, current_chapter: number) {
  const books: Books = [
    {
      book_id: BOOK_ID,
      title: "Christmas Carol",
      total_chapters: 3,
      current_chapter,
      ready_for_query: true,
    },
  ];
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(books),
    });
  });
}

async function mockChapters(page: Page) {
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/chapters`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { num: 1, title: "Chapter 1", word_count: 3000 },
          { num: 2, title: "The Last of the Spirits", word_count: 2000 },
          { num: 3, title: "Chapter 3", word_count: 500 },
        ]),
      });
    }
  );
}

async function mockChapter(page: Page) {
  await page.route(
    new RegExp(
      `^http://localhost:8000/books/${BOOK_ID}/chapters/(\\d+)$`
    ),
    async (route: Route) => {
      const url = route.request().url();
      const n = Number.parseInt(url.split("/").pop() ?? "1", 10);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          num: n,
          title: n === 2 ? "The Last of the Spirits" : `Chapter ${n}`,
          paragraphs: [
            `Opening paragraph of chapter ${n}.`,
            `Second paragraph of chapter ${n}.`,
          ],
          has_prev: n > 1,
          has_next: n < 3,
          total_chapters: 3,
        }),
      });
    }
  );
}

async function mockProgress(page: Page) {
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/progress`,
    async (route: Route) => {
      const body = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          current_chapter: body.current_chapter,
        }),
      });
    }
  );
}

test.describe("reading flow (hermetic)", () => {
  test("Library → BookCard click → lands on /books/:id/read/current_chapter", async ({
    page,
  }) => {
    await mockBooks(page, 2);
    await mockChapters(page);
    await mockChapter(page);

    await page.goto("/");
    await expect(page.getByText(/your shelf/i)).toBeVisible();

    await page.getByRole("button", { name: /christmas carol/i }).click();

    await expect(page).toHaveURL(
      new RegExp(`/books/${BOOK_ID}/read/2$`)
    );
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    // Sidebar renders the three ChapterRows with current on 2
    await expect(
      page.getByRole("button", { name: /01 chapter 1/i })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /02 the last of the spirits/i })
    ).toBeVisible();
  });

  test("Mark as read POSTs progress and sidebar advances to the next chapter", async ({
    page,
  }) => {
    let currentChapter = 2;
    await page.route("http://localhost:8000/books", async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            book_id: BOOK_ID,
            title: "Christmas Carol",
            total_chapters: 3,
            current_chapter: currentChapter,
            ready_for_query: true,
          },
        ]),
      });
    });
    await mockChapters(page);
    await mockChapter(page);
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/progress`,
      async (route: Route) => {
        const body = JSON.parse(route.request().postData() ?? "{}");
        currentChapter = body.current_chapter;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            current_chapter: body.current_chapter,
          }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();

    await page.getByRole("button", { name: /mark as read/i }).click();

    await expect(page).toHaveURL(
      new RegExp(`/books/${BOOK_ID}/read/3$`)
    );
    // Sidebar: chapter 2 row becomes read (check icon, data-state='read'),
    // chapter 3 row becomes current (data-state='current')
    await expect(
      page
        .getByRole("button", { name: /02 the last of the spirits/i })
    ).toHaveAttribute("data-state", "read");
    await expect(
      page.getByRole("button", { name: /03 chapter 3/i })
    ).toHaveAttribute("data-state", "current");
  });
});
```

- [ ] **Step 10.2: Run the E2E suite**

```bash
cd frontend && npm run test:e2e -- reading
```

Expected: 2 passed in chromium. Playwright auto-starts `npm run dev` on port 5173 via `webServer` config from slice 2.

- [ ] **Step 10.3: Commit**

```bash
git add frontend/e2e/reading.spec.ts
git commit -m "$(cat <<'EOF'
test(frontend): add hermetic Playwright E2E for reading flow

Two specs. (1) Clicking a BookCard lands on /books/:id/read/:current_chapter
with sidebar + body rendered. (2) Mark-as-read POSTs progress and
advances the sidebar state without a full page reload. Both mock every
backend call via page.route() — no live backend required.
EOF
)"
```

---

## Task 11: Final verification

**Files:** no code changes. Runs the full matrix.

- [ ] **Step 11.1: Run the backend test suite**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/ -v --tb=short
```

Expected: all prior 906 tests + 10 new `test_chapters_endpoint.py` cases pass (≥ 916 total).

- [ ] **Step 11.2: Run the frontend unit suite**

```bash
cd frontend && npm test
```

Expected: all tests pass. New counts: api (+6), ChapterRow (6), ProgressiveBlur (3), LockState (3), Highlight (2), BookCard (+1), NavBar (+1), App (+1), BookReadingRedirect (3), ReadingScreen (11) — ≥ 37 new, no regressions.

- [ ] **Step 11.3: Run the TypeScript build**

```bash
cd frontend && npm run build
```

Expected: `tsc -b` reports 0 errors, `vite build` produces `dist/` cleanly.

- [ ] **Step 11.4: Run the Playwright E2E suite**

```bash
cd frontend && npm run test:e2e
```

Expected: 4 (slice-2) + 2 (slice-3) = 6 passed in chromium.

- [ ] **Step 11.5: Manual smoke against the live backend**

Terminal 1 (repo root): `python main.py`
Terminal 2 (`frontend/`): `npm run dev`
Open `http://localhost:5173/`.

Verify end-to-end:

1. The Library renders the Christmas Carol card.
2. Click the card → URL becomes `/books/christmas_carol_e6ddcd76/read/N` (whatever `reading_progress.json` says).
3. The left sidebar shows three chapters: chapters before current are `read` (check icon), the current is highlighted + dotted, chapters beyond are either `locked` (padlock) or padlock-on-teaser per PRD.
4. The center column shows the chapter title as an `<h2>` and one `<p>` per paragraph.
5. Prev/Next buttons navigate without a full reload; Prev is disabled on chapter 1; Next is disabled when you're on the current chapter.
6. Click "Mark as read" on the current chapter. A network request fires to `POST /books/{id}/progress` with body `{"current_chapter": N+1}`. The sidebar advances one chapter and the URL becomes `/books/{id}/read/{N+1}`.
7. Reload the page. The sidebar reflects the new `current_chapter` from the persisted `reading_progress.json`.
8. Navigate to the chapter exactly one ahead of current — a single paragraph is visible with a blur overlay and "advance to reveal" pill.
9. Navigate to a chapter two or more ahead of current — only the padlock panel with the chapter title renders; no body fetch.
10. The right column shows "Margin notes" header + `safe through ch. N` pill + "Chat coming soon — available in the next release" placeholder + a disabled textarea.
11. Navigate to `/` and `/upload` — both still work.
12. `curl http://localhost:8000/books/christmas_carol_e6ddcd76/chapters | python -m json.tool` returns an array of 3 chapter summaries.
13. `curl http://localhost:8000/books/christmas_carol_e6ddcd76/chapters/2 | python -m json.tool` returns `{num: 2, title: "The Last of the Spirits", paragraphs: [...], has_prev: true, has_next: true, total_chapters: 3}`.
14. `curl http://localhost:8000/books/christmas_carol_e6ddcd76/chapters/99` returns 404 JSON.
15. `curl -X POST -H 'Content-Type: application/json' -d '{"current_chapter":2}' http://localhost:8000/books/christmas_carol_e6ddcd76/progress` returns 200 and `cat data/processed/christmas_carol_e6ddcd76/reading_progress.json` shows `2`.

- [ ] **Step 11.6: Confirm clean working tree**

```bash
git status
```

Expected: clean working tree (or only `dist/` / `playwright-report/` / `test-results/` which are already `.gitignore`d).

---

## Self-Review Checklist

| AC | Covered by |
|----|------------|
| 1. BookCard click → /books/:id/read → redirect to /read/:current_chapter | Task 6 (BookCard test), Task 7 (BookReadingRedirect), Task 10 spec 1 |
| 2. NavBar Reading tab active on /books/* | Task 7 (NavBar update + test) |
| 3. Sidebar fetches /books/{id}/chapters + renders ChapterRow with derived state | Task 8 (sidebar rendering test), Task 4 (ChapterRow states) |
| 4. Clicking a read/current row navigates, locked row is no-op | Task 4 (ChapterRow click tests), Task 8 (implicit via navigate) |
| 5. Center column fetches /chapters/{n} + renders `<h2>` + `<p>` per paragraph | Task 8 (body render + paragraph count tests) |
| 6. Prev/Next disabled logic | Task 8 ("Next is disabled when current_chapter equals n" + "Prev is disabled on chapter 1") |
| 7. Mark as read POSTs + sidebar updates + navigates | Task 8 (setProgress test), Task 10 spec 2 |
| 8. Reload preserves progress (server-side) | Task 11 Step 11.5 manual smoke step 7 |
| 9. Teaser + strict-lock rendering | Task 9 (tests) + Task 8 (impl) |
| 10. Right column chat shell | Task 8 (impl — disabled textarea + spoilerSafe pill + placeholder copy) |
| 11. curl contract for chapter endpoints | Task 1 (backend tests) + Task 11 Step 11.5 steps 12–14 |
| 12. curl POST /progress writes reading_progress.json | Task 1 (TestProgressFileShape) + Task 11 Step 11.5 step 15 |
| 13. pytest + npm test both pass | Task 11 Steps 11.1–11.2 |

**Placeholder scan:** no "TODO", "TBD", "fill in" strings. Every function referenced in a test is implemented in the same or an earlier task.

**Type consistency:** `ChapterSummary`, `Chapter`, `ProgressResponse` are defined in Task 2 (`lib/api.ts`) and consumed in Tasks 7, 8, 10. `ChapterRowState` is defined in Task 4 (`ChapterRow.tsx`) and consumed in Task 8 (`ReadingScreen` imports). `HighlightVariant` is defined in Task 5 and unused in slice 3 (ported for slice 4). `LockState` variants: `spoilerSafe` consumed by Task 8, `chapterLock` consumed by Task 8 (strict-lock branch).

**Scope guards:** no chat wiring, no `/query` endpoint, no SSE, no source citations, no margin-note creation, no entity click-through, no inline `Highlight` usage in reading body, no dark-mode, no mobile layouts. Backend additions are two routes + helpers; no stage changes, no new config keys, no new env vars. CORS unchanged. `CLAUDE.md` is not modified.

---

Total task count: **11** (Task 1 backend, Tasks 2–10 frontend incl. E2E, Task 11 verification). Backend files touched: `main.py` plus new `tests/test_chapters_endpoint.py`. Frontend files created: `ChapterRow.tsx/.test.tsx`, `ProgressiveBlur.tsx/.test.tsx`, `LockState.tsx/.test.tsx`, `Highlight.tsx/.test.tsx`, `BookReadingRedirect.tsx/.test.tsx`, `ReadingScreen.test.tsx`, `e2e/reading.spec.ts` (13 new files). Frontend files modified: `lib/api.ts/.test.ts`, `components/icons.tsx`, `components/NavBar.tsx/.test.tsx`, `components/BookCard.tsx/.test.tsx`, `screens/ReadingScreen.tsx` (replacing the stub), `App.tsx/.test.tsx` (9 modified). Playwright spec count: **2** new specs (total 6 E2E). The plan explicitly references `frontend-design:frontend-design` in the header generator note and again in the task-opening lines for Tasks 4, 5, and 8 (the UI-heavy tasks).

### Critical Files for Implementation
- /Users/jeffreykrapf/Documents/thefinalbookrag/main.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/screens/ReadingScreen.tsx
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/lib/api.ts
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/App.tsx
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/components/ChapterRow.tsx
