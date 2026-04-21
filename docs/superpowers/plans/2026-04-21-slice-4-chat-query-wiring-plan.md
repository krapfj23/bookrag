# Slice 4 — chat-query-wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Generator note — UI tasks 3, 4, 5, 6:** when implementing `UserBubble`, `AssistantBubble`, `ChatInput`, and the `ReadingScreen` right-column rewrite, invoke the `frontend-design:frontend-design` skill so ported components stay visually faithful to `design-handoff/project/components2.jsx` and `design-handoff/project/screens.jsx`. The existing TSX conventions in `frontend/src/components/` (inline-style objects driven by `var(--*)` tokens, no CSS modules, colocated `*.test.tsx`, no class-based styling) must be preserved.

**Goal:** Wire the right-column chat shell in `ReadingScreen` to the live `POST /books/{book_id}/query` endpoint. Add `max_chapter: int | None = None` to the backend `QueryRequest` so the client can pass `book.current_chapter` and the server clamps it against disk. Port `UserBubble`, `AssistantBubble`, `ChatInput` from the handoff. Extend `frontend/src/lib/api.ts` with a typed `queryBook` helper. Replace the disabled placeholder + textarea with a live transcript + empty state + live input. Cover the flow with component tests and a hermetic Playwright spec. No SSE, no typewriter fake-streaming, no chat persistence.

**Architecture:** Backend is one additive field on `QueryRequest`. `query_book` reads disk progress as `disk_max = _get_reading_progress(book_id)`; the effective ceiling becomes `min(req.max_chapter or disk_max, disk_max)` — never higher than disk. The rest of `query_book` stays unchanged (disk + Cognee paths already take an `int`). This is purely additive and keeps every existing caller (slice 1–3 tests) passing.

Frontend's `ReadingScreen` right column becomes the chat panel:
- Transcript lives in `ChatMessage[]` React state. Each message is `{ id, role, status, text, sources? }`.
- Empty state: centered serif "Ask about what you've read." when the transcript is empty.
- Submit path: append a user message → append a thinking assistant message (`status: "thinking"`) → call `queryBook(bookId, question, book.current_chapter)` → on resolve, replace the thinking message with either (a) assembled answer + sources or (b) a one-line error bubble.
- Thinking UI uses `AssistantBubble` with `thinking={true}`, rendering "Thinking…" + the blinking accent cursor already present in the handoff (`br-cursor` animation).
- `queryBook` throws typed `QueryError` subclasses (`QueryRateLimitError`, `QueryServerError`, `QueryNetworkError`) so the screen can map them to exact error copy without string-sniffing.
- Auto-scroll the latest message into view after each state change via `useEffect` + `scrollIntoView({ block: "end" })` on a sentinel `<div>` at the transcript tail.
- The `safe through ch. {current_chapter}` pill from slice 3 stays — it reads from the same `book.current_chapter` we send as `max_chapter`, so by construction they never drift.

The Playwright spec intercepts `POST /books/{id}/query` with `page.route()` for three scenarios (happy path with sources, empty results, 429) so the E2E runs against a fresh Vite dev server with no live backend.

**Tech Stack:** React 18, TypeScript, Vite 5, Vitest 2 + jsdom + Testing Library, `@playwright/test` (unchanged from slice 3). Backend: FastAPI, Pydantic, pytest (unchanged from slice 1 + 2 + 3). No new dependencies. No new env vars. No new CSS files. Uses existing `tokens.css` and `animations.css` (`brBlink` keyframe for the cursor).

---

## File Structure

**Backend — modified:**
- `main.py` — add `max_chapter: int | None = None` to `QueryRequest`; apply clamp in `query_book`.

**Backend — new:**
- `tests/test_query_endpoint.py` — all cases for the clamp logic + a shape regression for existing callers.

**Frontend — new files:**
- `frontend/src/components/UserBubble.tsx`, `frontend/src/components/UserBubble.test.tsx`
- `frontend/src/components/AssistantBubble.tsx`, `frontend/src/components/AssistantBubble.test.tsx`
- `frontend/src/components/ChatInput.tsx`, `frontend/src/components/ChatInput.test.tsx`
- `frontend/e2e/chat.spec.ts`

**Frontend — modified files:**
- `frontend/src/lib/api.ts` — add `QueryRequest`, `QueryResponse`, `QueryResult`, `QueryError` + subclasses, `queryBook`.
- `frontend/src/lib/api.test.ts` — tests for `queryBook` (happy path + typed errors + max_chapter propagation).
- `frontend/src/components/icons.tsx` — add `IcSend`.
- `frontend/src/screens/ReadingScreen.tsx` — replace right-column placeholder + disabled textarea with live chat panel; add transcript state, submit handler, empty state, auto-scroll.
- `frontend/src/screens/ReadingScreen.test.tsx` — extend with right-column chat tests.

---

## Task 1: Backend — add optional `max_chapter` to `QueryRequest`, clamp at disk

**Files:**
- Modify: `main.py`
- Create: `tests/test_query_endpoint.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_query_endpoint.py`:

```python
"""Tests for POST /books/{book_id}/query — the additive max_chapter field.

Covers:
- Backward compat: request without max_chapter still uses disk progress.
- Client can lower the ceiling (smaller max_chapter is respected).
- Server clamps at disk: a request with max_chapter > disk is reduced to disk.
- Invalid search_type still returns 400.
- Unknown book_id still returns 404.

Aligned with:
- docs/superpowers/specs/2026-04-21-slice-4-chat-query-wiring.md
  acceptance criteria 4, 9, 13 and "Backend scope" section.
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


BOOK_ID = "christmas_carol_e6ddcd76"


def _write_ready_book(processed_dir: Path, book_id: str, current_chapter: int) -> None:
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text("c1 body", encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_02.txt").write_text("c2 body", encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_03.txt").write_text("c3 body", encoding="utf-8")
    state = PipelineState.new(book_id, ["validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    (book_dir / "reading_progress.json").write_text(
        json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
        encoding="utf-8",
    )


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
        # Force disk-fallback path; Cognee disabled so search hits _search_datapoints_on_disk.
        main_module.COGNEE_AVAILABLE = False

        yield TestClient(main_module.app), config, mock_orch


class TestQueryMaxChapter:
    def test_omitted_max_chapter_uses_disk(self, client):
        """AC (backend scope): when max_chapter is omitted, behavior matches slice-3."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "Who is Marley?", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 2

    def test_client_smaller_max_chapter_respected(self, client):
        """AC 4 + 9: client lowering the ceiling is honored."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=3)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={
                "question": "Who is Marley?",
                "search_type": "GRAPH_COMPLETION",
                "max_chapter": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Response echoes the clamped effective chapter (min of disk and client).
        assert body["current_chapter"] == 1

    def test_client_larger_max_chapter_is_clamped_to_disk(self, client):
        """AC 9: client cannot raise the ceiling above disk; server clamps down."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={
                "question": "Who is Marley?",
                "search_type": "GRAPH_COMPLETION",
                "max_chapter": 99,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 2

    def test_equal_max_chapter_is_passthrough(self, client):
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={
                "question": "Who is Marley?",
                "search_type": "GRAPH_COMPLETION",
                "max_chapter": 2,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["current_chapter"] == 2

    def test_invalid_search_type_still_400(self, client):
        """Existing behavior unchanged."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=1)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "x", "search_type": "NONSENSE"},
        )
        assert resp.status_code == 400

    def test_unknown_book_still_404(self, client):
        """Existing behavior unchanged."""
        test_client, _, _ = client
        resp = test_client.post(
            "/books/nosuch_book/query",
            json={"question": "x", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 404

    def test_response_shape_has_all_fields(self, client):
        """Regression: QueryResponse shape is preserved."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "empty search", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["book_id"] == BOOK_ID
        assert body["question"] == "empty search"
        assert body["search_type"] == "GRAPH_COMPLETION"
        assert isinstance(body["current_chapter"], int)
        assert isinstance(body["results"], list)
        assert body["result_count"] == len(body["results"])
```

- [ ] **Step 1.2: Run — confirm failure**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/test_query_endpoint.py -v --tb=short
```

Expected: `test_client_smaller_max_chapter_respected` fails (server ignores the field); `test_client_larger_max_chapter_is_clamped_to_disk` fails (same reason — response echoes disk value regardless, may coincidentally pass, that's fine); `test_omitted_max_chapter_uses_disk` may pass today. Any failure is sufficient to drive implementation.

- [ ] **Step 1.3: Add `max_chapter` to `QueryRequest`**

In `main.py`, modify the `QueryRequest` class (around line 161):

```python
class QueryRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    search_type: str = "GRAPH_COMPLETION"
    max_chapter: int | None = Field(default=None, ge=1)
```

- [ ] **Step 1.4: Apply clamp in `query_book`**

In `main.py`, update the `query_book` function body. Replace the line:

```python
    current_chapter = _get_reading_progress(book_id)
```

with:

```python
    disk_max = _get_reading_progress(book_id)
    current_chapter = (
        min(req.max_chapter, disk_max) if req.max_chapter is not None else disk_max
    )
```

No other changes to `query_book` are needed. The disk search path and the Cognee filter both already use `current_chapter` as an `int`. The response echoes `current_chapter`, which per spec reports the effective ceiling.

- [ ] **Step 1.5: Run — confirm pass**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/test_query_endpoint.py tests/test_main.py tests/test_chapters_endpoints.py -v --tb=short
```

Expected: all new 7 cases pass; no existing tests regress.

- [ ] **Step 1.6: Commit**

```bash
git add main.py tests/test_query_endpoint.py
git commit -m "$(cat <<'EOF'
feat(backend): add optional max_chapter to QueryRequest, clamp at disk

Clients may now pass max_chapter on POST /books/{id}/query so the frontend
controls the spoiler ceiling per request. Server clamps it against the
on-disk reading_progress.json — a client cannot raise the ceiling above
what it has actually read. Omitting the field keeps slice-3 behavior.
EOF
)"
```

---

## Task 2: Frontend — `queryBook` in `lib/api.ts`

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api.test.ts`

- [ ] **Step 2.1: Write the failing tests**

Append to `frontend/src/lib/api.test.ts`:

```ts
import {
  queryBook,
  QueryError,
  QueryRateLimitError,
  QueryServerError,
  QueryNetworkError,
  type QueryResponse,
} from "./api";

describe("queryBook", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const BOOK_ID = "christmas_carol_e6ddcd76";

  const sampleResponse: QueryResponse = {
    book_id: BOOK_ID,
    question: "Who is Marley?",
    search_type: "GRAPH_COMPLETION",
    current_chapter: 2,
    results: [
      {
        content: "Marley was dead: to begin with.",
        entity_type: "Character",
        chapter: 1,
      },
    ],
    result_count: 1,
  };

  it("POSTs JSON to /books/{id}/query with question, search_type, max_chapter", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(sampleResponse),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await queryBook(BOOK_ID, "Who is Marley?", 2);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`http://localhost:8000/books/${BOOK_ID}/query`);
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      max_chapter: 2,
    });
    expect(result).toEqual(sampleResponse);
  });

  it("throws QueryRateLimitError on 429", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ detail: "too many" }),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(
      QueryRateLimitError
    );
    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(QueryError);
  });

  it("throws QueryServerError on 500", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "boom" }),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(
      QueryServerError
    );
  });

  it("throws QueryServerError on 503", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({}),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(
      QueryServerError
    );
  });

  it("throws QueryServerError on 4xx other than 429", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: "nope" }),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(
      QueryServerError
    );
  });

  it("throws QueryNetworkError when fetch itself rejects", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("network down")) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(
      QueryNetworkError
    );
  });

  it("sets status property on thrown errors for the UI to branch on", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({}),
    }) as unknown as typeof fetch;

    try {
      await queryBook(BOOK_ID, "q", 1);
    } catch (err) {
      expect((err as QueryRateLimitError).status).toBe(429);
    }
  });
});
```

- [ ] **Step 2.2: Run — confirm failure**

```bash
cd frontend && npm test -- api
```

Expected: `queryBook` describe block fails — import resolves to undefined for `queryBook`, `QueryError`, etc.

- [ ] **Step 2.3: Extend `lib/api.ts`**

Append to `frontend/src/lib/api.ts`:

```ts
// ---------------------------------------------------------------------------
// Query endpoint (slice 4)
// ---------------------------------------------------------------------------

export type QuerySearchType =
  | "GRAPH_COMPLETION"
  | "CHUNKS"
  | "SUMMARIES"
  | "RAG_COMPLETION";

export type QueryResult = {
  content: string;
  entity_type: string | null;
  chapter: number | null;
};

export type QueryResponse = {
  book_id: string;
  question: string;
  search_type: string;
  current_chapter: number;
  results: QueryResult[];
  result_count: number;
};

export class QueryError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "QueryError";
    this.status = status;
  }
}

export class QueryRateLimitError extends QueryError {
  constructor(message = "Too many requests, slow down.") {
    super(429, message);
    this.name = "QueryRateLimitError";
  }
}

export class QueryServerError extends QueryError {
  constructor(status: number, message = "Something went wrong. Try again.") {
    super(status, message);
    this.name = "QueryServerError";
  }
}

export class QueryNetworkError extends QueryError {
  constructor(message = "Something went wrong. Try again.") {
    super(0, message);
    this.name = "QueryNetworkError";
  }
}

export async function queryBook(
  book_id: string,
  question: string,
  max_chapter: number,
  search_type: QuerySearchType = "GRAPH_COMPLETION"
): Promise<QueryResponse> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}/books/${book_id}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, search_type, max_chapter }),
    });
  } catch {
    throw new QueryNetworkError();
  }

  if (resp.ok) {
    return (await resp.json()) as QueryResponse;
  }

  if (resp.status === 429) {
    throw new QueryRateLimitError();
  }
  throw new QueryServerError(resp.status);
}
```

- [ ] **Step 2.4: Run — confirm pass**

```bash
cd frontend && npm test -- api
```

Expected: 7 new `queryBook` cases pass, plus existing api tests continue to pass.

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add queryBook + typed QueryError classes

Posts {question, search_type, max_chapter} to /books/{id}/query. Throws
QueryRateLimitError on 429, QueryServerError on any other non-2xx, and
QueryNetworkError when fetch itself rejects. Callers branch on class,
not string.
EOF
)"
```

---

## Task 3: `UserBubble` component

**Files:**
- Create: `frontend/src/components/UserBubble.tsx`
- Create: `frontend/src/components/UserBubble.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 3.1: Write the failing test**

Create `frontend/src/components/UserBubble.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { UserBubble } from "./UserBubble";

describe("UserBubble", () => {
  it("renders its text content", () => {
    render(<UserBubble text="Who is Marley?" />);
    expect(screen.getByText("Who is Marley?")).toBeInTheDocument();
  });

  it("renders as a right-aligned bubble (data-role='user')", () => {
    const { container } = render(<UserBubble text="Hello" />);
    const bubble = container.querySelector("[data-role='user']");
    expect(bubble).toBeTruthy();
  });

  it("does not render the page-at footer when pageAt is omitted", () => {
    render(<UserBubble text="no footer" />);
    expect(screen.queryByText(/asked at p\./i)).toBeNull();
  });

  it("renders the page-at footer when pageAt is provided", () => {
    render(<UserBubble text="with footer" pageAt={54} />);
    expect(screen.getByText(/asked at p\.\s*54/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3.2: Run — confirm failure**

```bash
cd frontend && npm test -- UserBubble
```

Expected: module not found.

- [ ] **Step 3.3: Create `UserBubble.tsx`**

Port from `design-handoff/project/components2.jsx` (lines 7–22). Typed + TSX-adapted:

```tsx
type UserBubbleProps = {
  text: string;
  pageAt?: number;
};

export function UserBubble({ text, pageAt }: UserBubbleProps) {
  return (
    <div
      data-role="user"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: 4,
        marginLeft: 48,
      }}
    >
      <div
        style={{
          background: "var(--paper-1)",
          color: "var(--ink-0)",
          padding: "12px 16px",
          borderRadius: "var(--r-lg)",
          borderBottomRightRadius: "var(--r-xs)",
          fontFamily: "var(--serif)",
          fontSize: 15,
          lineHeight: 1.55,
          maxWidth: "100%",
        }}
      >
        {text}
      </div>
      {pageAt != null && (
        <div
          style={{
            fontFamily: "var(--sans)",
            fontSize: 11,
            color: "var(--ink-3)",
            letterSpacing: 0.2,
            marginRight: 4,
          }}
        >
          asked at p. {pageAt}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3.4: Run — confirm pass**

```bash
cd frontend && npm test -- UserBubble
```

Expected: 4 passed.

- [ ] **Step 3.5: Commit**

```bash
git add frontend/src/components/UserBubble.tsx frontend/src/components/UserBubble.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port UserBubble component

Right-aligned chat bubble from design-handoff/project/components2.jsx.
Optional pageAt footer ("asked at p. N") — unused this slice but ported
for parity with the handoff.
EOF
)"
```

---

## Task 4: `AssistantBubble` component

**Files:**
- Create: `frontend/src/components/AssistantBubble.tsx`
- Create: `frontend/src/components/AssistantBubble.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 4.1: Write the failing test**

Create `frontend/src/components/AssistantBubble.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AssistantBubble, type AssistantSource } from "./AssistantBubble";

describe("AssistantBubble", () => {
  it("renders its text content", () => {
    render(<AssistantBubble text="Marley is Scrooge's dead partner." />);
    expect(
      screen.getByText(/marley is scrooge's dead partner/i)
    ).toBeInTheDocument();
  });

  it("renders with data-role='assistant' for the transcript", () => {
    const { container } = render(<AssistantBubble text="x" />);
    expect(container.querySelector("[data-role='assistant']")).toBeTruthy();
  });

  it("renders the avatar disc", () => {
    render(<AssistantBubble text="x" />);
    expect(screen.getByText("r")).toBeInTheDocument();
  });

  it("does not render sources when sources is undefined", () => {
    const { container } = render(<AssistantBubble text="no sources" />);
    expect(container.querySelector("[data-source-index]")).toBeNull();
  });

  it("does not render sources when sources is empty", () => {
    const { container } = render(<AssistantBubble text="empty" sources={[]} />);
    expect(container.querySelector("[data-source-index]")).toBeNull();
  });

  it("renders up to 5 sources, truncated to 200 chars + ellipsis", () => {
    const longText = "x".repeat(400);
    const sources: AssistantSource[] = [
      { text: "Short one.", chapter: 1 },
      { text: "Second.", chapter: 2 },
      { text: "Third.", chapter: 3 },
      { text: "Fourth.", chapter: 4 },
      { text: "Fifth.", chapter: 5 },
      { text: "Sixth — should be dropped.", chapter: 6 },
      { text: longText, chapter: 7 }, // should not appear (past 5)
    ];
    const { container } = render(
      <AssistantBubble text="answer" sources={sources} />
    );
    const rendered = container.querySelectorAll("[data-source-index]");
    expect(rendered.length).toBe(5);
    expect(screen.queryByText(/sixth/i)).toBeNull();
  });

  it("truncates individual source text longer than 200 chars", () => {
    const longText = "A".repeat(250);
    render(
      <AssistantBubble
        text="answer"
        sources={[{ text: longText, chapter: 1 }]}
      />
    );
    // The rendered text should contain the ellipsis and be shorter than 250.
    const el = screen.getByText(/A{10,}…/);
    expect(el.textContent!.length).toBeLessThan(250);
    expect(el.textContent!.endsWith("…")).toBe(true);
  });

  it("renders Ch. {n} label per source", () => {
    render(
      <AssistantBubble
        text="answer"
        sources={[
          { text: "from ch 1", chapter: 1 },
          { text: "from ch 3", chapter: 3 },
        ]}
      />
    );
    expect(screen.getByText("Ch. 1")).toBeInTheDocument();
    expect(screen.getByText("Ch. 3")).toBeInTheDocument();
  });

  it("when thinking=true, renders the blinking cursor", () => {
    const { container } = render(
      <AssistantBubble text="Thinking…" thinking />
    );
    expect(container.querySelector(".br-cursor")).toBeTruthy();
  });

  it("when thinking=false (default), omits the cursor", () => {
    const { container } = render(<AssistantBubble text="done" />);
    expect(container.querySelector(".br-cursor")).toBeNull();
  });
});
```

- [ ] **Step 4.2: Run — confirm failure**

```bash
cd frontend && npm test -- AssistantBubble
```

Expected: module not found.

- [ ] **Step 4.3: Create `AssistantBubble.tsx`**

Port from `design-handoff/project/components2.jsx` (lines 24–70). Typed and slimmed to the props this slice needs (no `spoilerSafe` inline label — the right-column header already carries that).

```tsx
export type AssistantSource = {
  text: string;
  chapter: number;
};

type AssistantBubbleProps = {
  text: string;
  sources?: AssistantSource[];
  thinking?: boolean;
};

const MAX_SOURCES = 5;
const MAX_SOURCE_CHARS = 200;

function truncate(s: string, limit: number): string {
  return s.length > limit ? `${s.slice(0, limit)}…` : s;
}

export function AssistantBubble({
  text,
  sources,
  thinking = false,
}: AssistantBubbleProps) {
  const visibleSources = (sources ?? []).slice(0, MAX_SOURCES);
  return (
    <div
      data-role="assistant"
      style={{ display: "flex", gap: 12, marginRight: 48 }}
    >
      <div
        aria-hidden="true"
        style={{
          flexShrink: 0,
          width: 28,
          height: 28,
          borderRadius: 999,
          background: "var(--accent-softer)",
          color: "var(--accent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 13,
          fontWeight: 500,
          marginTop: 2,
        }}
      >
        r
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 15.5,
            lineHeight: 1.65,
            color: "var(--ink-0)",
          }}
        >
          {text}
          {thinking && (
            <span
              className="br-cursor"
              style={{
                display: "inline-block",
                width: 7,
                height: 15,
                background: "var(--accent)",
                marginLeft: 2,
                verticalAlign: -2,
                animation: "brBlink 1s steps(2) infinite",
              }}
            />
          )}
        </div>
        {visibleSources.length > 0 && (
          <div
            style={{
              marginTop: 12,
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {visibleSources.map((s, i) => (
              <div
                key={i}
                data-source-index={i}
                style={{
                  padding: "8px 12px",
                  borderLeft: "2px solid var(--accent)",
                  background: "var(--accent-softer)",
                  fontFamily: "var(--serif)",
                  fontSize: 13.5,
                  fontStyle: "italic",
                  lineHeight: 1.5,
                  color: "var(--ink-1)",
                }}
              >
                <span>{truncate(s.text, MAX_SOURCE_CHARS)}</span>
                <span
                  style={{
                    display: "inline-block",
                    marginLeft: 8,
                    fontFamily: "var(--sans)",
                    fontStyle: "normal",
                    fontSize: 11,
                    color: "var(--ink-2)",
                    letterSpacing: 0.2,
                  }}
                >
                  Ch. {s.chapter}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4.4: Run — confirm pass**

```bash
cd frontend && npm test -- AssistantBubble
```

Expected: 10 passed.

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/components/AssistantBubble.tsx frontend/src/components/AssistantBubble.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port AssistantBubble component

Left-aligned bubble with an 'r' avatar disc. Supports optional sources
(capped at 5, each truncated to 200 chars + ellipsis, labeled "Ch. N")
and an optional thinking flag that appends the existing brBlink cursor.
EOF
)"
```

---

## Task 5: `ChatInput` component + `IcSend` icon

**Files:**
- Modify: `frontend/src/components/icons.tsx`
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/components/ChatInput.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 5.1: Add `IcSend` to `icons.tsx`**

Append to `frontend/src/components/icons.tsx`:

```tsx
export const IcSend = (p: Props) => (
  <Icon {...p} d="M2.5 13.5L13.5 8 2.5 2.5v4.5L10 8l-7.5 1.5v4z" fill="currentColor" stroke="none" />
);
```

- [ ] **Step 5.2: Write the failing test**

Create `frontend/src/components/ChatInput.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("renders the placeholder when value is empty", () => {
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
      />
    );
    expect(
      screen.getByPlaceholderText(/ask about what you've read/i)
    ).toBeInTheDocument();
  });

  it("calls onChange as the user types", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="" onChange={onChange} onSubmit={() => {}} />
    );
    await user.type(screen.getByRole("textbox"), "Hi");
    // uncontrolled per-keystroke updates; the last call matches final char
    expect(onChange).toHaveBeenCalled();
  });

  it("disables the send button when the trimmed value is empty", () => {
    render(
      <ChatInput value="   " onChange={() => {}} onSubmit={() => {}} />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("enables the send button when value is non-empty", () => {
    render(
      <ChatInput value="hello" onChange={() => {}} onSubmit={() => {}} />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeEnabled();
  });

  it("clicking send calls onSubmit", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="Who is Marley?" onChange={() => {}} onSubmit={onSubmit} />
    );
    await user.click(screen.getByRole("button", { name: /send/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("Enter (without Shift) calls onSubmit and prevents default", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="q" onChange={() => {}} onSubmit={onSubmit} />
    );
    const ta = screen.getByRole("textbox");
    ta.focus();
    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("Shift+Enter does NOT call onSubmit", async () => {
    const onSubmit = vi.fn();
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="line one" onChange={onChange} onSubmit={onSubmit} />
    );
    const ta = screen.getByRole("textbox");
    ta.focus();
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("Enter on an empty value does NOT call onSubmit", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="   " onChange={() => {}} onSubmit={onSubmit} />
    );
    const ta = screen.getByRole("textbox");
    ta.focus();
    await user.keyboard("{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("when disabled, send is disabled regardless of value", () => {
    render(
      <ChatInput
        value="non-empty"
        onChange={() => {}}
        onSubmit={() => {}}
        disabled
      />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
```

- [ ] **Step 5.3: Run — confirm failure**

```bash
cd frontend && npm test -- ChatInput
```

Expected: module not found.

- [ ] **Step 5.4: Create `ChatInput.tsx`**

Port from `design-handoff/project/components2.jsx` (lines 150–181). Controlled, with Enter/Shift+Enter handling added:

```tsx
import { useState, type KeyboardEvent } from "react";
import { IcSend } from "./icons";

type ChatInputProps = {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  disabled?: boolean;
};

export function ChatInput({
  value,
  onChange,
  onSubmit,
  placeholder = "Ask about what you've read…",
  disabled = false,
}: ChatInputProps) {
  const [focus, setFocus] = useState(false);
  const canSend = !disabled && value.trim().length > 0;

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSubmit();
    }
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 8,
        padding: "10px 10px 10px 16px",
        background: "var(--paper-00)",
        border: `1px solid ${focus ? "var(--accent)" : "var(--paper-2)"}`,
        boxShadow: focus
          ? "0 0 0 3px var(--accent-softer), var(--shadow-1)"
          : "var(--shadow-1)",
        borderRadius: "var(--r-lg)",
        transition:
          "border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)",
        fontFamily: "var(--serif)",
      }}
    >
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        aria-label="Ask about what you've read"
        style={{
          flex: 1,
          border: 0,
          outline: "none",
          background: "transparent",
          resize: "none",
          fontFamily: "var(--serif)",
          fontSize: 15.5,
          lineHeight: 1.5,
          color: "var(--ink-0)",
          padding: "6px 0",
          minHeight: 24,
          maxHeight: 160,
        }}
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSend}
        aria-label="Send"
        style={{
          width: 34,
          height: 34,
          borderRadius: "var(--r-md)",
          background: canSend ? "var(--accent)" : "var(--paper-1)",
          color: canSend ? "var(--paper-00)" : "var(--ink-3)",
          border: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: canSend ? "pointer" : "not-allowed",
          transition:
            "background var(--dur) var(--ease), color var(--dur) var(--ease)",
        }}
      >
        <IcSend size={15} />
      </button>
    </div>
  );
}
```

- [ ] **Step 5.5: Run — confirm pass**

```bash
cd frontend && npm test -- ChatInput
```

Expected: 9 passed.

- [ ] **Step 5.6: Commit**

```bash
git add frontend/src/components/icons.tsx frontend/src/components/ChatInput.tsx frontend/src/components/ChatInput.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port ChatInput + add IcSend icon

Controlled textarea with a send button. Enter submits (and preventDefault),
Shift+Enter inserts a newline, trimmed-empty disables send. disabled prop
locks the whole composite regardless of value.
EOF
)"
```

---

## Task 6: Wire `ReadingScreen` right column to the live chat panel

**Files:**
- Modify: `frontend/src/screens/ReadingScreen.tsx`
- Modify: `frontend/src/screens/ReadingScreen.test.tsx`

Invoke the `frontend-design:frontend-design` skill for this task.

- [ ] **Step 6.1: Write the failing tests**

Append a new `describe` block to `frontend/src/screens/ReadingScreen.test.tsx` (do NOT remove the existing slice-3 blocks — all prior tests must keep passing):

```tsx
import { UserBubble } from "../components/UserBubble";
import { AssistantBubble } from "../components/AssistantBubble";
// (imports already in the file; add these only if missing)

describe("ReadingScreen — chat panel (slice 4)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // HTMLElement.prototype.scrollIntoView is not implemented in jsdom; stub it.
    Element.prototype.scrollIntoView = vi.fn();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the empty state before any messages are sent", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    expect(
      screen.getByText(/ask about what you've read/i, {
        selector: "p, div, span",
      })
    ).toBeInTheDocument();
  });

  it("header 'safe through ch. N' matches current_chapter", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/safe through ch\. 2/i)).toBeInTheDocument()
    );
  });

  it("submitting a question appends a UserBubble and a thinking AssistantBubble", async () => {
    mockApi();
    const querySpy = vi
      .spyOn(api, "queryBook")
      .mockImplementation(
        () => new Promise(() => {}) as Promise<api.QueryResponse>
      );
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);

    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    const input = screen.getByLabelText(/ask about what you've read/i);
    await user.type(input, "Who is Marley?");
    await user.keyboard("{Enter}");

    // User bubble appears
    expect(screen.getByText("Who is Marley?")).toBeInTheDocument();
    // Thinking bubble: text "Thinking…" with the blinking cursor
    expect(screen.getByText(/thinking…/i)).toBeInTheDocument();
    // queryBook was called with book.current_chapter as max_chapter
    expect(querySpy).toHaveBeenCalledWith(BOOK_ID, "Who is Marley?", 2);
  });

  it("on 2xx replaces thinking with an AssistantBubble + sources", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      results: [
        {
          content: "Marley is Scrooge's dead business partner.",
          entity_type: "Character",
          chapter: 1,
        },
        {
          content: "Another ref",
          entity_type: null,
          chapter: null, // should NOT render as a source
        },
      ],
      result_count: 2,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    const input = screen.getByLabelText(/ask about what you've read/i);
    await user.type(input, "Who is Marley?");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/marley is scrooge's dead business partner/i)
      ).toBeInTheDocument()
    );
    // "Thinking…" has been replaced
    expect(screen.queryByText(/thinking…/i)).toBeNull();
    // Ch. 1 source is visible
    expect(screen.getByText("Ch. 1")).toBeInTheDocument();
  });

  it("on empty results renders the fallback line and no sources", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      results: [],
      result_count: 0,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    await user.type(
      screen.getByLabelText(/ask about what you've read/i),
      "obscure question"
    );
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/i don't have anything in your read-so-far/i)
      ).toBeInTheDocument()
    );
  });

  it("on QueryRateLimitError shows 'Too many requests, slow down.'", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockRejectedValue(
      new api.QueryRateLimitError()
    );
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    await user.type(
      screen.getByLabelText(/ask about what you've read/i),
      "q"
    );
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/too many requests, slow down\./i)
      ).toBeInTheDocument()
    );
  });

  it("on QueryServerError shows 'Something went wrong. Try again.'", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockRejectedValue(
      new api.QueryServerError(500)
    );
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    await user.type(
      screen.getByLabelText(/ask about what you've read/i),
      "q"
    );
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong\. try again\./i)
      ).toBeInTheDocument()
    );
  });

  it("on QueryNetworkError shows 'Something went wrong. Try again.'", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockRejectedValue(
      new api.QueryNetworkError()
    );
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    await user.type(
      screen.getByLabelText(/ask about what you've read/i),
      "q"
    );
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong\. try again\./i)
      ).toBeInTheDocument()
    );
  });

  it("the input clears after submission", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "x",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      results: [],
      result_count: 0,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    const input = screen.getByLabelText(
      /ask about what you've read/i
    ) as HTMLTextAreaElement;
    await user.type(input, "x");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(input.value).toBe(""));
  });

  it("does NOT render the slice-3 disabled textarea + 'Chat coming soon' placeholder", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/chat coming soon/i)).toBeNull();
    expect(
      screen.queryByPlaceholderText(/available in the next release/i)
    ).toBeNull();
  });
});
```

- [ ] **Step 6.2: Run — confirm failure**

```bash
cd frontend && npm test -- ReadingScreen
```

Expected: new chat-panel tests fail because the right column still renders the slice-3 placeholder + disabled textarea. Slice-3 tests in the same file continue to pass.

- [ ] **Step 6.3: Replace the right-column body + footer**

In `frontend/src/screens/ReadingScreen.tsx`:

Add these imports at the top (alongside existing imports):

```tsx
import { useRef } from "react";
import { UserBubble } from "../components/UserBubble";
import { AssistantBubble, type AssistantSource } from "../components/AssistantBubble";
import { ChatInput } from "../components/ChatInput";
import {
  queryBook,
  QueryRateLimitError,
  QueryError,
} from "../lib/api";
```

Add the chat message type and error-copy constants just below the existing `BodyState` type:

```tsx
type ChatMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      status: "thinking" | "ok" | "error";
      text: string;
      sources?: AssistantSource[];
    };

const ERR_GENERIC = "Something went wrong. Try again.";
const ERR_RATELIMIT = "Too many requests, slow down.";
const EMPTY_RESULT_TEXT =
  "I don't have anything in your read-so-far that answers that. Try rephrasing, or read further.";
```

Inside `ReadingScreen`, add state + handlers just after the existing `useEffect` that fetches the chapter body:

```tsx
  // Chat transcript state (React-only; not persisted)
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the latest message after each state change
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function handleChatSubmit() {
    const trimmed = draft.trim();
    if (!trimmed || !book || submitting) return;

    const userId = crypto.randomUUID();
    const thinkingId = crypto.randomUUID();
    const maxChapter = book.current_chapter;

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text: trimmed },
      {
        id: thinkingId,
        role: "assistant",
        status: "thinking",
        text: "Thinking…",
      },
    ]);
    setDraft("");
    setSubmitting(true);

    try {
      const resp = await queryBook(bookId, trimmed, maxChapter);
      const hasResults = resp.result_count > 0 && resp.results.length > 0;
      const answerText = hasResults
        ? resp.results.map((r) => r.content).join("\n\n")
        : EMPTY_RESULT_TEXT;
      const sources: AssistantSource[] = hasResults
        ? resp.results
            .filter((r): r is typeof r & { chapter: number } =>
              r.chapter != null
            )
            .map((r) => ({ text: r.content, chapter: r.chapter }))
        : [];

      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? {
                id: thinkingId,
                role: "assistant",
                status: "ok",
                text: answerText,
                sources: sources.length > 0 ? sources : undefined,
              }
            : m
        )
      );
    } catch (err) {
      const copy =
        err instanceof QueryRateLimitError
          ? ERR_RATELIMIT
          : err instanceof QueryError
          ? ERR_GENERIC
          : ERR_GENERIC;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? {
                id: thinkingId,
                role: "assistant",
                status: "error",
                text: copy,
              }
            : m
        )
      );
    } finally {
      setSubmitting(false);
    }
  }
```

Replace the right-column body and footer (the two `<div>`s that currently render "Chat coming soon" and the disabled `<textarea>`) with:

```tsx
          <div
            style={{
              flex: 1,
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: 24,
              overflow: "auto",
            }}
          >
            {messages.length === 0 && (
              <div
                role="status"
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  textAlign: "center",
                  fontFamily: "var(--serif)",
                  fontStyle: "italic",
                  fontSize: 15,
                  color: "var(--ink-3)",
                  padding: "40px 24px",
                }}
              >
                Ask about what you've read.
              </div>
            )}
            {messages.map((m) =>
              m.role === "user" ? (
                <UserBubble key={m.id} text={m.text} />
              ) : (
                <AssistantBubble
                  key={m.id}
                  text={m.text}
                  sources={m.status === "ok" ? m.sources : undefined}
                  thinking={m.status === "thinking"}
                />
              )
            )}
            <div ref={transcriptEndRef} />
          </div>
          <div style={{ padding: "16px 20px 20px" }}>
            <ChatInput
              value={draft}
              onChange={setDraft}
              onSubmit={handleChatSubmit}
              disabled={submitting}
            />
          </div>
```

The header row (Margin notes label + `safe through ch. {current_chapter}` pill) is unchanged.

- [ ] **Step 6.4: Run — confirm pass**

```bash
cd frontend && npm test -- ReadingScreen
```

Expected: all prior slice-3 tests pass, plus the 10 new chat-panel tests. Total for `ReadingScreen.test.tsx` is prior count + 10.

- [ ] **Step 6.5: Commit**

```bash
git add frontend/src/screens/ReadingScreen.tsx frontend/src/screens/ReadingScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): wire ReadingScreen chat panel to POST /query

Replaces the disabled textarea + 'Chat coming soon' placeholder with a
live chat transcript. Submitting appends a UserBubble + a thinking
AssistantBubble, calls queryBook(bookId, question, book.current_chapter),
and replaces the thinking bubble with either the assembled answer +
sources or a one-line error bubble ('Too many requests, slow down.' for
429, 'Something went wrong. Try again.' for 5xx/network). Empty-results
path renders the 'read-so-far' fallback line. Auto-scrolls to latest.
EOF
)"
```

---

## Task 7: Playwright — hermetic E2E for the chat flow

**Files:**
- Create: `frontend/e2e/chat.spec.ts`

- [ ] **Step 7.1: Write the hermetic spec**

Create `frontend/e2e/chat.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const BOOK_ID = "christmas_carol_e6ddcd76";

async function mockReadingBackend(page: Page) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "Christmas Carol",
          total_chapters: 3,
          current_chapter: 2,
          ready_for_query: true,
        },
      ]),
    });
  });
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

test.describe("chat flow (hermetic)", () => {
  test("empty state is visible on fresh Reading screen", async ({ page }) => {
    await mockReadingBackend(page);
    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    await expect(
      page.getByText(/ask about what you've read\./i)
    ).toBeVisible();
  });

  test("typing a question and pressing Enter renders user bubble + thinking, then a successful response with a source", async ({
    page,
  }) => {
    await mockReadingBackend(page);

    // Delayed query response so we can observe the thinking state
    let bodySent: unknown = null;
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/query`,
      async (route: Route) => {
        bodySent = JSON.parse(route.request().postData() ?? "{}");
        await new Promise((r) => setTimeout(r, 300));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            question: "Who is Marley?",
            search_type: "GRAPH_COMPLETION",
            current_chapter: 2,
            results: [
              {
                content: "Marley is Scrooge's dead business partner.",
                entity_type: "Character",
                chapter: 1,
              },
            ],
            result_count: 1,
          }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();

    const input = page.getByLabel(/ask about what you've read/i);
    await input.fill("Who is Marley?");
    await input.press("Enter");

    // User bubble shows
    await expect(page.getByText("Who is Marley?")).toBeVisible();
    // Thinking bubble is visible while the request is in flight
    await expect(page.getByText(/thinking…/i)).toBeVisible();
    // Response lands
    await expect(
      page.getByText(/marley is scrooge's dead business partner/i)
    ).toBeVisible();
    await expect(page.getByText("Ch. 1")).toBeVisible();
    // Thinking has been replaced
    await expect(page.getByText(/thinking…/i)).toHaveCount(0);
    // The request carried max_chapter == current_chapter (2)
    expect(bodySent).toMatchObject({
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      max_chapter: 2,
    });
  });

  test("empty results render the read-so-far fallback", async ({ page }) => {
    await mockReadingBackend(page);
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/query`,
      async (route: Route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            question: "obscure",
            search_type: "GRAPH_COMPLETION",
            current_chapter: 2,
            results: [],
            result_count: 0,
          }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();

    const input = page.getByLabel(/ask about what you've read/i);
    await input.fill("obscure question");
    await input.press("Enter");

    await expect(
      page.getByText(/i don't have anything in your read-so-far/i)
    ).toBeVisible();
  });

  test("429 renders 'Too many requests, slow down.'", async ({ page }) => {
    await mockReadingBackend(page);
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/query`,
      async (route: Route) => {
        await route.fulfill({
          status: 429,
          contentType: "application/json",
          body: JSON.stringify({ detail: "rate-limited" }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();

    const input = page.getByLabel(/ask about what you've read/i);
    await input.fill("Hello");
    await input.press("Enter");

    await expect(
      page.getByText(/too many requests, slow down\./i)
    ).toBeVisible();
  });
});
```

- [ ] **Step 7.2: Run the E2E suite**

```bash
cd frontend && npm run test:e2e -- chat
```

Expected: 4 passed in chromium.

- [ ] **Step 7.3: Commit**

```bash
git add frontend/e2e/chat.spec.ts
git commit -m "$(cat <<'EOF'
test(frontend): add hermetic Playwright E2E for chat flow

Four specs covering (1) empty-state visibility on fresh Reading screen,
(2) happy path with a source citation and max_chapter==current_chapter
on the wire, (3) empty-results fallback copy, (4) 429 rate-limit copy.
All backends mocked via page.route() — no live backend required.
EOF
)"
```

---

## Task 8: Final verification

**Files:** no code changes. Runs the full matrix.

- [ ] **Step 8.1: Run the backend test suite**

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/ -v --tb=short
```

Expected: slice-1/2/3 tests plus the 7 new `test_query_endpoint.py` cases pass, 0 regressions.

- [ ] **Step 8.2: Run the frontend unit suite**

```bash
cd frontend && npm test
```

Expected: all tests pass. New counts: api (+7), UserBubble (4), AssistantBubble (10), ChatInput (9), ReadingScreen (+10). No regressions in slice-1/2/3 component tests.

- [ ] **Step 8.3: Run the TypeScript build**

```bash
cd frontend && npm run build
```

Expected: `tsc -b` reports 0 errors, `vite build` produces `dist/` cleanly.

- [ ] **Step 8.4: Run the full Playwright E2E suite**

```bash
cd frontend && npm run test:e2e
```

Expected: slice-2 (upload) + slice-3 (reading, 2 specs) + slice-4 (chat, 4 specs) all pass.

- [ ] **Step 8.5: Manual smoke against the live backend**

Terminal 1 (repo root): `python main.py`
Terminal 2 (`frontend/`): `npm run dev`
Open `http://localhost:5173/`.

Verify:

1. Library → click the Christmas Carol card → land on `/books/christmas_carol_e6ddcd76/read/N`.
2. Right column shows the empty-state "Ask about what you've read." in italic serif, vertically centered.
3. Type "Who is Marley?" and press Enter. The user bubble appears immediately on the right, a thinking bubble appears on the left with "Thinking…" and the blinking cursor.
4. Response lands — the thinking bubble is replaced by an assistant bubble with the answer text; sources render as italic serif blocks with left accent border and a "Ch. N" label.
5. In devtools Network tab: the `POST /books/christmas_carol_e6ddcd76/query` request body includes `"max_chapter": N` where `N == current_chapter` from `/books`.
6. The header pill "safe through ch. N" matches.
7. Click the send icon with an empty input — it is disabled, nothing happens.
8. Type a question, Shift+Enter — a newline is inserted; press Enter — submits.
9. Ask a nonsense question. If `results` is empty, the fallback line appears: "I don't have anything in your read-so-far that answers that. Try rephrasing, or read further."
10. Stop the backend, submit a question → the error line reads "Something went wrong. Try again."
11. Navigate between chapters via the sidebar — the chat transcript persists (same mount).
12. Reload the page — transcript clears (React state only).
13. Navigate to Library and back — transcript clears (screen unmount).
14. `curl -X POST http://localhost:8000/books/christmas_carol_e6ddcd76/query -H 'Content-Type: application/json' -d '{"question":"Who is Marley?","search_type":"GRAPH_COMPLETION","max_chapter":1}'` returns 200, `current_chapter: 1` in the response body.
15. Same curl with `"max_chapter": 99` returns 200 with `current_chapter` equal to the disk value (clamped).

- [ ] **Step 8.6: Confirm clean working tree**

```bash
git status
```

Expected: clean working tree (or only `dist/` / `playwright-report/` / `test-results/` which are already `.gitignore`d).

---

## Self-Review Checklist

| AC | Covered by |
|----|------------|
| 1. Empty-state copy "Ask about what you've read." replaces slice-3 placeholder | Task 6 (test: "shows the empty state"), Task 7 (E2E: "empty state is visible") |
| 2. `ChatInput` live; send disabled on trimmed-empty | Task 5 (disabled/enabled tests) |
| 3. Enter submits, Shift+Enter newline, send-click also submits | Task 5 (three keyboard/click tests) |
| 4. Submit appends UserBubble + thinking bubble + fires request with `max_chapter: current_chapter` | Task 6 (test: "submitting a question appends..."), Task 7 (E2E: body includes max_chapter) |
| 5. 2xx replaces thinking, joins `results[].content`, renders Ch.-labeled sources | Task 6 ("on 2xx replaces thinking...") + Task 4 (AssistantBubble truncation test) |
| 6. Empty results render fallback line | Task 6 ("on empty results...") + Task 7 (E2E: "empty results render") |
| 7. Network/5xx → "Something went wrong. Try again." | Task 6 (QueryServerError + QueryNetworkError tests) + Task 2 (error-class tests) |
| 8. 429 → "Too many requests, slow down." | Task 6 (QueryRateLimitError test) + Task 7 (E2E: 429) |
| 9. `max_chapter` equals `book.current_chapter` on the wire | Task 6 (spy assertion) + Task 7 (E2E: toMatchObject max_chapter: 2) + Task 1 (clamp logic) |
| 10. "safe through ch. N" pill matches `max_chapter` sent | Task 6 (header pill test), preserved from slice 3 |
| 11. Chat history preserved within same mount; cleared on route change | Task 6 (state model: React state only, no persistence), manual smoke step 12–13 |
| 12. Auto-scroll to latest after each change | Task 6 (`transcriptEndRef` + `useEffect` on `messages`) |
| 13. curl contract | Task 1 (tests) + Task 8 manual smoke step 14–15 |
| 14. No regressions in slice-1/2/3 | Task 8 Step 8.1–8.4 |

**Placeholder scan:** no "TODO", "TBD", "fill in" strings. Every function referenced in a test is implemented in the same or an earlier task.

**Type consistency:** `QueryResponse`, `QueryResult`, `QueryError`, `QueryRateLimitError`, `QueryServerError`, `QueryNetworkError` are defined in Task 2 (`lib/api.ts`) and consumed in Tasks 6 and 7. `AssistantSource` is defined in Task 4 (`AssistantBubble.tsx`) and consumed in Task 6 (ReadingScreen transcript typing). `ChatMessage` is local to `ReadingScreen.tsx` per PRD (React-only, not persisted).

**Scope guards:** no SSE, no client-side typewriter, no chat persistence (React state only, cleared on unmount/reload), no margin-note records, no per-message "asked at p. X" footer (prop exists on `UserBubble` but is unused), no entity click-through, no selection-to-question, no suggested-question chips, no thread switching, no mobile/tablet layouts, no regenerating/copying/rating responses. Backend addition is a single optional field on `QueryRequest` and a `min()` clamp in `query_book` — no new endpoints, no new env vars, CORS unchanged. `CLAUDE.md` is not modified.

---
