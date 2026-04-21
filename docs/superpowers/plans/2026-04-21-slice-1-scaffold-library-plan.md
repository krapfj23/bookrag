# Slice 1 — Scaffold + Library Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `GET /books` FastAPI endpoint that enumerates ready books from `data/processed/*/pipeline_state.json`, then stand up a Vite + React + TypeScript frontend under `frontend/` that ports the design tokens and renders a Library screen consuming that endpoint.

**Architecture:** Backend change is additive — a single route in `main.py` that iterates `config.processed_dir`, filters by `ready_for_query`, derives `title` from `book_id` by stripping the trailing `_<8-hex>` suffix and title-casing the rest, counts `raw/chapters/chapter_*.txt`, and reads `reading_progress.json`. Frontend is a fresh Vite `react-ts` scaffold at `frontend/` with the handoff JSX ported component-by-component to TypeScript under `frontend/src/components/`. A single page `LibraryScreen` fetches `/books` on mount and renders a `BookCard` grid. No router; the other nav tabs are visible but inert. `BookCover` derives a stable two-tone mood from the `book_id` via a simple hash modulo 6, keeping mood out of the API.

**Tech Stack:** Backend: FastAPI, Pydantic, loguru, pytest (existing conftest + fixtures). Frontend: Vite `react-ts` template, React 18, TypeScript, Vitest, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`. No CSS framework — raw CSS custom properties from the ported `tokens.css`.

---

## File Structure

**Backend changes (additive only):**
- Modify: `main.py` — add `BookSummary` Pydantic model, a `_derive_title` helper, a `_list_ready_books` helper, and a `GET /books` route near the other book routes.
- Create: `tests/test_books_endpoint.py` — covers the empty case and the one-ready-book case.

**Frontend (all new):**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/.gitignore`, `frontend/vitest.setup.ts`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`
- Create: `frontend/src/styles/tokens.css` (verbatim copy of `design-handoff/project/tokens.css`)
- Create: `frontend/src/lib/api.ts`, `frontend/src/lib/api.test.ts`
- Create: `frontend/src/lib/mood.ts`, `frontend/src/lib/mood.test.ts`
- Create: `frontend/src/components/layout.tsx` (Stack, Row, Divider)
- Create: `frontend/src/components/Wordmark.tsx`
- Create: `frontend/src/components/NavBar.tsx`, `frontend/src/components/NavBar.test.tsx`
- Create: `frontend/src/components/IconBtn.tsx`
- Create: `frontend/src/components/icons.tsx` (Icon + IcSearch, IcPlus, IcSun, IcMoon, IcSettings)
- Create: `frontend/src/components/Button.tsx`
- Create: `frontend/src/components/TextInput.tsx`
- Create: `frontend/src/components/ProgressPill.tsx`, `frontend/src/components/ProgressPill.test.tsx`
- Create: `frontend/src/components/BookCover.tsx`, `frontend/src/components/BookCover.test.tsx`
- Create: `frontend/src/components/BookCard.tsx`, `frontend/src/components/BookCard.test.tsx`
- Create: `frontend/src/screens/LibraryScreen.tsx`, `frontend/src/screens/LibraryScreen.test.tsx`

---

## Task 1: Backend — `GET /books` endpoint

**Files:**
- Modify: `main.py`
- Create: `tests/test_books_endpoint.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_books_endpoint.py`:

```python
"""Tests for GET /books.

Covers:
- Empty processed_dir → returns [].
- One ready book on disk → returns a Book record with derived title,
  chapter count from raw/chapters/chapter_*.txt, and current_chapter
  from reading_progress.json (defaulting to 1 if missing).
- Books whose pipeline_state.json has ready_for_query=false are excluded.
- Directories missing or with corrupt pipeline_state.json are skipped
  (endpoint never 500s) and a warning is logged.

Aligned with:
- docs/superpowers/specs/2026-04-21-slice-1-scaffold-library.md acceptance
  criteria 5, 7, 8, 9.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mirror the cognee mock setup used by tests/test_main.py so importing
# main.py does not fail when cognee is absent.
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


def _write_ready_book(
    processed_dir: Path,
    book_id: str,
    *,
    chapter_count: int,
    current_chapter: int | None = None,
) -> None:
    """Write a pipeline_state.json with ready_for_query=true plus chapter files."""
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    for i in range(1, chapter_count + 1):
        (book_dir / "raw" / "chapters" / f"chapter_{i:02d}.txt").write_text(
            f"chapter {i} body", encoding="utf-8"
        )
    state = PipelineState.new(book_id, ["parse_epub", "validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    if current_chapter is not None:
        (book_dir / "reading_progress.json").write_text(
            json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
            encoding="utf-8",
        )


def _write_in_progress_book(processed_dir: Path, book_id: str) -> None:
    """Write a pipeline_state.json with ready_for_query=false."""
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text(
        "c1", encoding="utf-8"
    )
    state = PipelineState.new(book_id, ["parse_epub"])
    state.status = "processing"
    state.ready_for_query = False
    save_state(state, book_dir / "pipeline_state.json")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fresh TestClient pointing main.config at tmp_path."""
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

        yield TestClient(main_module.app), config


class TestListBooksEndpoint:
    def test_empty_returns_empty_list(self, client):
        test_client, _ = client
        resp = test_client.get("/books")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_one_ready_book(self, client):
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir),
            "christmas_carol_e6ddcd76",
            chapter_count=3,
            current_chapter=2,
        )
        resp = test_client.get("/books")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        book = body[0]
        assert book["book_id"] == "christmas_carol_e6ddcd76"
        assert book["title"] == "Christmas Carol"
        assert book["total_chapters"] == 3
        assert book["current_chapter"] == 2
        assert book["ready_for_query"] is True

    def test_current_chapter_defaults_to_one(self, client):
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir),
            "red_rising_abc12345",
            chapter_count=5,
        )
        resp = test_client.get("/books")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["current_chapter"] == 1

    def test_excludes_not_ready_books(self, client):
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir),
            "done_book_deadbeef",
            chapter_count=2,
        )
        _write_in_progress_book(Path(config.processed_dir), "wip_book_12345678")
        resp = test_client.get("/books")
        ids = [b["book_id"] for b in resp.json()]
        assert ids == ["done_book_deadbeef"]

    def test_skips_directory_without_pipeline_state(self, client):
        test_client, config = client
        (Path(config.processed_dir) / "orphan_dir").mkdir(parents=True)
        _write_ready_book(
            Path(config.processed_dir),
            "ok_book_11111111",
            chapter_count=1,
        )
        resp = test_client.get("/books")
        assert resp.status_code == 200
        ids = [b["book_id"] for b in resp.json()]
        assert ids == ["ok_book_11111111"]

    def test_skips_corrupt_pipeline_state(self, client):
        test_client, config = client
        bad_dir = Path(config.processed_dir) / "bad_book_22222222"
        bad_dir.mkdir(parents=True)
        (bad_dir / "pipeline_state.json").write_text(
            "{this is not valid json", encoding="utf-8"
        )
        _write_ready_book(
            Path(config.processed_dir),
            "ok_book_33333333",
            chapter_count=1,
        )
        resp = test_client.get("/books")
        assert resp.status_code == 200
        ids = [b["book_id"] for b in resp.json()]
        assert ids == ["ok_book_33333333"]

    def test_title_preserves_ids_without_hex_suffix(self, client):
        """book_id 'christmas_carol' (no suffix) should keep all parts in the title."""
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir), "christmas_carol", chapter_count=1
        )
        body = test_client.get("/books").json()
        assert body[0]["title"] == "Christmas Carol"

    def test_title_only_strips_8_hex_suffix(self, client):
        """'_demo' (4 chars) is not a hex suffix — the title should keep 'Demo'."""
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir), "christmas_carol_demo", chapter_count=1
        )
        body = test_client.get("/books").json()
        assert body[0]["title"] == "Christmas Carol Demo"
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `python -m pytest tests/test_books_endpoint.py -v --tb=short`
Expected: Every test fails with `assert 404 == 200` (FastAPI returns 404 for the unregistered `/books` route).

- [ ] **Step 1.3: Write minimal implementation**

Modify `main.py`. Add a new Pydantic model next to the other response models (after `HealthResponse`, before the `QueryRequest` block around line 137). Insert the following:

```python
class BookSummary(BaseModel):
    book_id: str
    title: str
    total_chapters: int
    current_chapter: int
    ready_for_query: bool
```

Add two private helpers near the other module-level helpers (e.g. just above `_get_reading_progress` around line 290):

```python
_BOOK_ID_HEX_SUFFIX_RE = re.compile(r"_[0-9a-f]{8}$")


def _derive_title(book_id: str) -> str:
    """Strip an optional trailing _<8-hex> id and title-case the remaining slug."""
    slug = _BOOK_ID_HEX_SUFFIX_RE.sub("", book_id)
    words = [w for w in slug.split("_") if w]
    return " ".join(w.capitalize() for w in words) if words else book_id


def _list_ready_books() -> list["BookSummary"]:
    """Scan processed_dir for books ready for query.

    Skips directories whose pipeline_state.json is missing or unreadable
    and logs a warning; never raises.
    """
    from models.pipeline_state import load_state  # local import — avoid cycles

    processed_dir = Path(config.processed_dir)
    if not processed_dir.exists():
        return []

    books: list[BookSummary] = []
    for child in sorted(processed_dir.iterdir()):
        if not child.is_dir():
            continue
        state_path = child / "pipeline_state.json"
        if not state_path.exists():
            logger.warning("Skipping {}: pipeline_state.json missing", child.name)
            continue
        try:
            state = load_state(state_path)
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Skipping {}: cannot load pipeline state ({})", child.name, exc)
            continue
        if not state.ready_for_query:
            continue
        chapters_dir = child / "raw" / "chapters"
        total_chapters = (
            len(list(chapters_dir.glob("chapter_*.txt"))) if chapters_dir.exists() else 0
        )
        current_chapter = _get_reading_progress(child.name)
        books.append(
            BookSummary(
                book_id=child.name,
                title=_derive_title(child.name),
                total_chapters=total_chapters,
                current_chapter=current_chapter,
                ready_for_query=True,
            )
        )
    return books
```

Add the route just above the `@app.get("/books/{book_id}/status")` decorator (around line 228):

```python
@app.get("/books", response_model=list[BookSummary])
async def list_books() -> list[BookSummary]:
    """List every book whose pipeline has completed and is ready for query."""
    return _list_ready_books()
```

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `python -m pytest tests/test_books_endpoint.py -v --tb=short`
Expected: 8 passed.

Also verify nothing regresses: `python -m pytest tests/ -v --tb=short -x`
Expected: all prior tests still pass.

- [ ] **Step 1.5: Commit**

```bash
git add main.py tests/test_books_endpoint.py
git commit -m "$(cat <<'EOF'
feat(api): add GET /books endpoint listing ready books

Scans data/processed/*/pipeline_state.json, skips directories with
missing or corrupt state, and derives title by stripping a trailing
_<8-hex> book_id suffix and title-casing the rest.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Frontend scaffold — Vite + React + TS + Vitest

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`, `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/.gitignore`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/styles/tokens.css`

- [ ] **Step 2.1: Create `frontend/package.json`**

```json
{
  "name": "bookrag-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.8",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^24.1.1",
    "typescript": "^5.5.3",
    "vite": "^5.3.4",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2.2: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false,
  },
});
```

- [ ] **Step 2.3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vitest.setup.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 2.4: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 2.5: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BookRAG</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Lora:ital,wght@0,400;0,500;1,400;1,500&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2.6: Create `frontend/.gitignore`**

```
node_modules
dist
.vite
*.local
coverage
```

- [ ] **Step 2.7: Create `frontend/vitest.setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2.8: Port `tokens.css` verbatim**

Copy the entire content of `/Users/jeffreykrapf/Documents/thefinalbookrag/design-handoff/project/tokens.css` into `frontend/src/styles/tokens.css`. Do not modify it.

- [ ] **Step 2.9: Write the failing test**

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the BookRAG wordmark", () => {
    render(<App />);
    expect(screen.getByText(/book/i)).toBeInTheDocument();
    expect(screen.getByText("rag")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2.10: Run test to verify it fails**

Run (from `frontend/`): `npm install && npm test`
Expected: `Cannot find module './App'` or equivalent — the file does not exist yet.

- [ ] **Step 2.11: Create `frontend/src/App.tsx` (stub)**

```tsx
export function App() {
  return (
    <div className="br">
      <span style={{ fontFamily: "var(--serif)", fontSize: 20, fontWeight: 500 }}>
        Book<span style={{ fontStyle: "italic", color: "var(--accent)" }}>rag</span>
      </span>
    </div>
  );
}
```

- [ ] **Step 2.12: Create `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles/tokens.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 2.13: Run test to verify it passes**

Run (from `frontend/`): `npm test`
Expected: 1 passed.

- [ ] **Step 2.14: Manual sanity check the dev server starts**

Run (from `frontend/`): `npm run dev`
Expected: Vite prints `Local: http://localhost:5173/` with no errors. Stop with Ctrl-C once confirmed.

- [ ] **Step 2.15: Commit**

```bash
git add frontend/
git commit -m "$(cat <<'EOF'
feat(frontend): scaffold Vite + React + TS + Vitest at frontend/

Adds the Vite react-ts template, Vitest with jsdom, and Testing Library
wired through vitest.setup.ts. Ports design-handoff/project/tokens.css
verbatim to frontend/src/styles/tokens.css and imports it once from
main.tsx. App renders the Bookrag wordmark stub as a smoke test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Layout primitives, icons, Wordmark, IconBtn, NavBar

**Files:**
- Create: `frontend/src/components/layout.tsx`
- Create: `frontend/src/components/icons.tsx`
- Create: `frontend/src/components/Wordmark.tsx`
- Create: `frontend/src/components/IconBtn.tsx`
- Create: `frontend/src/components/NavBar.tsx`
- Create: `frontend/src/components/NavBar.test.tsx`

- [ ] **Step 3.1: Write the failing NavBar test**

Create `frontend/src/components/NavBar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NavBar } from "./NavBar";

describe("NavBar", () => {
  it("renders the three tabs and the wordmark", () => {
    render(<NavBar active="library" />);
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText(/book/i)).toBeInTheDocument();
  });

  it("marks the active tab with aria-current and a data attribute", () => {
    render(<NavBar active="library" />);
    const active = screen.getByText("Library");
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active).toHaveAttribute("data-active", "true");
  });

  it("non-active tabs are inert but do not throw when clicked", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(<NavBar active="library" />);
    await user.click(screen.getByText("Reading"));
    await user.click(screen.getByText("Upload"));
    expect(screen.getByText("Library")).toHaveAttribute("aria-current", "page");
  });
});
```

- [ ] **Step 3.2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- NavBar`
Expected: `Failed to resolve import "./NavBar"` — file does not exist.

- [ ] **Step 3.3: Implement the layout primitives**

Create `frontend/src/components/layout.tsx`:

```tsx
import type { CSSProperties, PropsWithChildren } from "react";

type StackProps = PropsWithChildren<{ gap?: number; style?: CSSProperties }>;
export function Stack({ gap = 16, children, style }: StackProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap, ...style }}>
      {children}
    </div>
  );
}

type RowProps = PropsWithChildren<{
  gap?: number;
  align?: CSSProperties["alignItems"];
  style?: CSSProperties;
}>;
export function Row({ gap = 12, align = "center", children, style }: RowProps) {
  return (
    <div style={{ display: "flex", alignItems: align, gap, ...style }}>
      {children}
    </div>
  );
}

export function Divider({ style }: { style?: CSSProperties }) {
  return (
    <div
      style={{
        height: 1,
        background: "var(--paper-2)",
        width: "100%",
        ...style,
      }}
    />
  );
}
```

- [ ] **Step 3.4: Implement the icon set**

Create `frontend/src/components/icons.tsx`:

```tsx
import type { CSSProperties, PropsWithChildren } from "react";

type IconProps = PropsWithChildren<{
  d?: string;
  size?: number;
  stroke?: number;
  fill?: string;
  viewBox?: string;
  style?: CSSProperties;
}>;

export function Icon({
  d,
  size = 16,
  stroke = 1.5,
  fill = "none",
  viewBox = "0 0 16 16",
  style,
  children,
}: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill={fill}
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}
    >
      {d ? <path d={d} /> : children}
    </svg>
  );
}

type Props = Omit<IconProps, "d" | "children" | "viewBox">;

export const IcSearch = (p: Props) => (
  <Icon {...p} d="M7.5 12.5a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm3.5-1.5l2.5 2.5" />
);
export const IcPlus = (p: Props) => <Icon {...p} d="M8 3v10M3 8h10" />;
export const IcSun = (p: Props) => (
  <Icon {...p}>
    <circle cx="8" cy="8" r="3" />
    <path d="M8 1.5v1.5M8 13v1.5M1.5 8h1.5M13 8h1.5M3.3 3.3l1 1M11.7 11.7l1 1M12.7 3.3l-1 1M3.3 12.7l1-1" />
  </Icon>
);
export const IcMoon = (p: Props) => (
  <Icon {...p}>
    <path d="M13 9a5 5 0 0 1-6-6 5 5 0 1 0 6 6z" />
  </Icon>
);
export const IcSettings = (p: Props) => (
  <Icon {...p}>
    <circle cx="8" cy="8" r="1.8" />
    <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.3 3.3l1.5 1.5M11.2 11.2l1.5 1.5M12.7 3.3l-1.5 1.5M4.8 11.2l-1.5 1.5" />
  </Icon>
);
```

- [ ] **Step 3.5: Implement the Wordmark**

Create `frontend/src/components/Wordmark.tsx`:

```tsx
export function Wordmark({ size = 20 }: { size?: number }) {
  return (
    <span
      style={{
        fontFamily: "var(--serif)",
        fontSize: size,
        fontWeight: 500,
        letterSpacing: -0.3,
        color: "var(--ink-0)",
      }}
    >
      Book
      <span style={{ fontStyle: "italic", color: "var(--accent)" }}>rag</span>
    </span>
  );
}
```

- [ ] **Step 3.6: Implement IconBtn**

Create `frontend/src/components/IconBtn.tsx`:

```tsx
import type { PropsWithChildren } from "react";

type IconBtnProps = PropsWithChildren<{
  onClick?: () => void;
  title?: string;
  active?: boolean;
}>;

export function IconBtn({ children, onClick, title, active }: IconBtnProps) {
  return (
    <button
      onClick={onClick}
      title={title}
      type="button"
      style={{
        width: 30,
        height: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--r-sm)",
        color: active ? "var(--ink-0)" : "var(--ink-2)",
        background: active ? "var(--paper-1)" : "transparent",
        border: 0,
        cursor: "pointer",
        transition:
          "background var(--dur) var(--ease), color var(--dur) var(--ease)",
      }}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 3.7: Implement NavBar**

Create `frontend/src/components/NavBar.tsx`:

```tsx
import { Row } from "./layout";
import { Wordmark } from "./Wordmark";
import { IconBtn } from "./IconBtn";
import { IcMoon, IcSun, IcSettings } from "./icons";

export type NavTab = "library" | "reading" | "upload";

type NavBarProps = {
  active?: NavTab;
  theme?: "light" | "dark";
  onThemeToggle?: () => void;
};

const ITEMS: Array<{ id: NavTab; label: string }> = [
  { id: "library", label: "Library" },
  { id: "reading", label: "Reading" },
  { id: "upload", label: "Upload" },
];

export function NavBar({
  active = "library",
  theme = "light",
  onThemeToggle,
}: NavBarProps) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "14px 28px",
        borderBottom: "var(--hairline)",
        background: "color-mix(in oklab, var(--paper-0) 80%, transparent)",
        backdropFilter: "saturate(140%) blur(12px)",
        fontFamily: "var(--sans)",
        height: 56,
        boxSizing: "border-box",
      }}
    >
      <Row gap={32}>
        <Wordmark />
        <nav style={{ display: "flex", gap: 4 }}>
          {ITEMS.map((it) => {
            const isActive = active === it.id;
            return (
              <a
                key={it.id}
                href="#"
                aria-current={isActive ? "page" : undefined}
                data-active={isActive ? "true" : "false"}
                onClick={(e) => e.preventDefault()}
                style={{
                  padding: "6px 12px",
                  fontSize: "var(--t-sm)",
                  color: isActive ? "var(--ink-0)" : "var(--ink-2)",
                  borderRadius: "var(--r-sm)",
                  fontWeight: isActive ? 500 : 400,
                  background: isActive ? "var(--paper-1)" : "transparent",
                  textDecoration: "none",
                  cursor: "pointer",
                  transition:
                    "color var(--dur) var(--ease), background var(--dur) var(--ease)",
                }}
              >
                {it.label}
              </a>
            );
          })}
        </nav>
      </Row>
      <Row gap={8}>
        <IconBtn onClick={onThemeToggle} title="Toggle theme">
          {theme === "dark" ? <IcSun size={15} /> : <IcMoon size={15} />}
        </IconBtn>
        <IconBtn title="Settings">
          <IcSettings size={15} />
        </IconBtn>
      </Row>
    </header>
  );
}
```

- [ ] **Step 3.8: Run test to verify it passes**

Run (from `frontend/`): `npm test -- NavBar`
Expected: 3 passed.

- [ ] **Step 3.9: Commit**

```bash
git add frontend/src/components/
git commit -m "$(cat <<'EOF'
feat(frontend): add layout primitives, icons, Wordmark, IconBtn, NavBar

Ports Stack/Row/Divider, the icon primitive plus the five icons the
Library screen needs, the Wordmark, IconBtn, and NavBar from the
design handoff. NavBar.test.tsx verifies the active-tab logic uses
aria-current and that inert tabs do not throw when clicked.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Mood hash, BookCover, ProgressPill, BookCard

**Files:**
- Create: `frontend/src/lib/mood.ts`
- Create: `frontend/src/lib/mood.test.ts`
- Create: `frontend/src/components/BookCover.tsx`
- Create: `frontend/src/components/BookCover.test.tsx`
- Create: `frontend/src/components/ProgressPill.tsx`
- Create: `frontend/src/components/ProgressPill.test.tsx`
- Create: `frontend/src/components/BookCard.tsx`
- Create: `frontend/src/components/BookCard.test.tsx`

- [ ] **Step 4.1: Write the failing mood-hash test**

Create `frontend/src/lib/mood.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { moodForBookId, MOODS } from "./mood";

describe("moodForBookId", () => {
  it("returns one of the 6 moods", () => {
    expect(MOODS).toEqual(["sage", "amber", "slate", "rose", "charcoal", "paper"]);
    expect(MOODS).toContain(moodForBookId("christmas_carol_e6ddcd76"));
  });

  it("is stable — same input → same output across calls", () => {
    const a = moodForBookId("christmas_carol_e6ddcd76");
    const b = moodForBookId("christmas_carol_e6ddcd76");
    expect(a).toBe(b);
  });

  it("is deterministic across different inputs", () => {
    expect(moodForBookId("red_rising_abc12345")).toBe(
      moodForBookId("red_rising_abc12345")
    );
  });

  it("handles empty string", () => {
    expect(MOODS).toContain(moodForBookId(""));
  });
});
```

- [ ] **Step 4.2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- mood`
Expected: `Failed to resolve import "./mood"`.

- [ ] **Step 4.3: Implement the mood hash**

Create `frontend/src/lib/mood.ts`:

```ts
export const MOODS = ["sage", "amber", "slate", "rose", "charcoal", "paper"] as const;
export type Mood = (typeof MOODS)[number];

/** Stable mood picker: sum char codes modulo MOODS.length. */
export function moodForBookId(bookId: string): Mood {
  let sum = 0;
  for (let i = 0; i < bookId.length; i++) sum += bookId.charCodeAt(i);
  return MOODS[sum % MOODS.length];
}
```

- [ ] **Step 4.4: Run it to verify it passes**

Run: `npm test -- mood`
Expected: 4 passed.

- [ ] **Step 4.5: Write the failing BookCover test**

Create `frontend/src/components/BookCover.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BookCover } from "./BookCover";

describe("BookCover", () => {
  it("renders the title", () => {
    render(<BookCover book_id="christmas_carol_e6ddcd76" title="Christmas Carol" />);
    expect(screen.getByText("Christmas Carol")).toBeInTheDocument();
  });

  it("derives a stable mood attribute from book_id", () => {
    const { container, rerender } = render(
      <BookCover book_id="abc_12345678" title="X" />
    );
    const first = container.querySelector("[data-mood]")?.getAttribute("data-mood");
    rerender(<BookCover book_id="abc_12345678" title="X" />);
    const second = container.querySelector("[data-mood]")?.getAttribute("data-mood");
    expect(first).toBe(second);
    expect(first).toMatch(/^(sage|amber|slate|rose|charcoal|paper)$/);
  });
});
```

- [ ] **Step 4.6: Run it to verify it fails**

Run: `npm test -- BookCover`
Expected: `Failed to resolve import "./BookCover"`.

- [ ] **Step 4.7: Implement BookCover**

Create `frontend/src/components/BookCover.tsx`:

```tsx
import type { CSSProperties } from "react";
import { moodForBookId, type Mood } from "../lib/mood";

type BookCoverProps = {
  book_id: string;
  title: string;
  mood?: Mood;
  style?: CSSProperties;
};

const PALETTE: Record<Mood, { bg: string; ink: string }> = {
  sage: { bg: "oklch(78% 0.04 145)", ink: "oklch(22% 0.03 145)" },
  amber: { bg: "oklch(82% 0.06 70)", ink: "oklch(26% 0.05 70)" },
  slate: { bg: "oklch(74% 0.03 240)", ink: "oklch(22% 0.03 240)" },
  rose: { bg: "oklch(80% 0.04 20)", ink: "oklch(24% 0.04 20)" },
  charcoal: { bg: "oklch(30% 0.01 50)", ink: "oklch(94% 0.01 70)" },
  paper: { bg: "oklch(92% 0.01 70)", ink: "oklch(22% 0.02 70)" },
};

export function BookCover({ book_id, title, mood, style }: BookCoverProps) {
  const chosen: Mood = mood ?? moodForBookId(book_id);
  const colors = PALETTE[chosen];
  return (
    <div
      data-mood={chosen}
      style={{
        position: "relative",
        background: colors.bg,
        color: colors.ink,
        aspectRatio: "2 / 3",
        borderRadius: "var(--r-xs)",
        padding: "18px 16px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.06), 2px 2px 0 rgba(0,0,0,0.04)",
        overflow: "hidden",
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 8,
          border: "0.5px solid currentColor",
          opacity: 0.3,
          borderRadius: 1,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          opacity: 0.65,
        }}
      >
        a novel
      </div>
      <div>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 500,
            fontStyle: "italic",
            fontSize: 19,
            lineHeight: 1.15,
            letterSpacing: -0.3,
          }}
        >
          {title}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4.8: Run it to verify it passes**

Run: `npm test -- BookCover`
Expected: 2 passed.

- [ ] **Step 4.9: Write the failing ProgressPill test**

Create `frontend/src/components/ProgressPill.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProgressPill } from "./ProgressPill";

describe("ProgressPill", () => {
  it("renders '<current> of <total>'", () => {
    render(<ProgressPill current={2} total={3} />);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("clamps width to 100% when current exceeds total", () => {
    const { container } = render(<ProgressPill current={10} total={3} />);
    const bar = container.querySelector("[data-pill-fill]") as HTMLElement;
    expect(bar).toBeTruthy();
    expect(bar.style.width).toBe("100%");
  });

  it("renders 0% width when current is 0", () => {
    const { container } = render(<ProgressPill current={0} total={3} />);
    const bar = container.querySelector("[data-pill-fill]") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });
});
```

- [ ] **Step 4.10: Run it to verify it fails**

Run: `npm test -- ProgressPill`
Expected: `Failed to resolve import`.

- [ ] **Step 4.11: Implement ProgressPill**

Create `frontend/src/components/ProgressPill.tsx`:

```tsx
type ProgressPillProps = {
  current: number;
  total: number;
  variant?: "default" | "soft";
};

export function ProgressPill({ current, total, variant = "default" }: ProgressPillProps) {
  const safeTotal = Math.max(1, total);
  const pct = Math.min(100, Math.max(0, (current / safeTotal) * 100));
  const isSoft = variant === "soft";
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: 28,
        padding: "0 12px",
        borderRadius: "var(--r-pill)",
        background: isSoft ? "var(--accent-softer)" : "var(--paper-1)",
        color: isSoft ? "var(--accent-ink)" : "var(--ink-1)",
        fontFamily: "var(--sans)",
        fontSize: 12,
        fontWeight: 500,
        fontVariantNumeric: "tabular-nums",
        letterSpacing: 0.2,
      }}
    >
      <span>{current}</span>
      <span
        style={{
          flexShrink: 0,
          width: 36,
          height: 3,
          borderRadius: 999,
          background: isSoft
            ? "color-mix(in oklab, var(--accent) 20%, transparent)"
            : "var(--paper-3)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          data-pill-fill
          style={{
            position: "absolute",
            inset: 0,
            width: `${pct}%`,
            background: isSoft ? "var(--accent)" : "var(--ink-2)",
            transition: "width var(--dur-slow) var(--ease-out)",
          }}
        />
      </span>
      <span style={{ opacity: 0.6 }}>of {total}</span>
    </div>
  );
}
```

- [ ] **Step 4.12: Run it to verify it passes**

Run: `npm test -- ProgressPill`
Expected: 3 passed.

- [ ] **Step 4.13: Write the failing BookCard test**

Create `frontend/src/components/BookCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BookCard } from "./BookCard";

describe("BookCard", () => {
  it("renders title, progress pill, and chapter-progress text", () => {
    render(
      <BookCard
        book_id="christmas_carol_e6ddcd76"
        title="Christmas Carol"
        total_chapters={3}
        current_chapter={1}
      />
    );
    expect(screen.getByText("Christmas Carol")).toHaveLength;
    // the chapter-progress label "1 of 3"
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("renders a BookCover with a stable mood", () => {
    const { container } = render(
      <BookCard
        book_id="christmas_carol_e6ddcd76"
        title="Christmas Carol"
        total_chapters={3}
        current_chapter={1}
      />
    );
    expect(container.querySelector("[data-mood]")).toBeTruthy();
  });
});
```

- [ ] **Step 4.14: Run it to verify it fails**

Run: `npm test -- BookCard`
Expected: `Failed to resolve import`.

- [ ] **Step 4.15: Implement BookCard**

Create `frontend/src/components/BookCard.tsx`:

```tsx
import { BookCover } from "./BookCover";
import { ProgressPill } from "./ProgressPill";

export type BookCardProps = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  onClick?: () => void;
};

export function BookCard({
  book_id,
  title,
  total_chapters,
  current_chapter,
  onClick,
}: BookCardProps) {
  return (
    <div
      onClick={onClick}
      style={{
        fontFamily: "var(--sans)",
        cursor: onClick ? "pointer" : "default",
        width: 200,
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
    </div>
  );
}
```

- [ ] **Step 4.16: Run it to verify it passes**

Run: `npm test -- BookCard`
Expected: 2 passed.

- [ ] **Step 4.17: Commit**

```bash
git add frontend/src/lib/ frontend/src/components/
git commit -m "$(cat <<'EOF'
feat(frontend): add BookCover, ProgressPill, BookCard with mood hash

BookCover derives a stable mood from book_id via a sum-of-char-codes
hash modulo the 6 moods (sage/amber/slate/rose/charcoal/paper) ported
from the handoff — keeping mood out of the API contract. ProgressPill
renders "<current> of <total>" and clamps the fill bar width. BookCard
composes the two with the serif title.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: API client + TextInput + Button + LibraryScreen

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/api.test.ts`
- Create: `frontend/src/components/TextInput.tsx`
- Create: `frontend/src/components/Button.tsx`
- Create: `frontend/src/screens/LibraryScreen.tsx`
- Create: `frontend/src/screens/LibraryScreen.test.tsx`

- [ ] **Step 5.1: Write the failing api test**

Create `frontend/src/lib/api.test.ts`:

```ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { fetchBooks } from "./api";

describe("fetchBooks", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs http://localhost:8000/books and returns the JSON body", async () => {
    const body = [
      {
        book_id: "christmas_carol_e6ddcd76",
        title: "Christmas Carol",
        total_chapters: 3,
        current_chapter: 1,
        ready_for_query: true,
      },
    ];
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await fetchBooks();

    expect(mockFetch).toHaveBeenCalledWith("http://localhost:8000/books");
    expect(result).toEqual(body);
  });

  it("throws on non-OK responses", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;
    await expect(fetchBooks()).rejects.toThrow(/500/);
  });
});
```

- [ ] **Step 5.2: Run it to verify it fails**

Run: `npm test -- api`
Expected: `Failed to resolve import "./api"`.

- [ ] **Step 5.3: Implement the API client**

Create `frontend/src/lib/api.ts`:

```ts
export type Book = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  ready_for_query: boolean;
};

const BASE_URL = "http://localhost:8000";

export async function fetchBooks(): Promise<Book[]> {
  const resp = await fetch(`${BASE_URL}/books`);
  if (!resp.ok) {
    throw new Error(`GET /books failed: ${resp.status}`);
  }
  return (await resp.json()) as Book[];
}
```

- [ ] **Step 5.4: Run it to verify it passes**

Run: `npm test -- api`
Expected: 2 passed.

- [ ] **Step 5.5: Implement TextInput (no test — inert)**

Create `frontend/src/components/TextInput.tsx`:

```tsx
import type { ReactNode } from "react";
import { useState } from "react";

type TextInputProps = {
  placeholder?: string;
  value?: string;
  onChange?: (v: string) => void;
  icon?: ReactNode;
  size?: "sm" | "md" | "lg";
};

const HEIGHTS = { sm: 30, md: 38, lg: 44 } as const;

export function TextInput({
  placeholder,
  value,
  onChange,
  icon,
  size = "md",
}: TextInputProps) {
  const [focus, setFocus] = useState(false);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        height: HEIGHTS[size],
        padding: "0 12px",
        background: "var(--paper-00)",
        color: "var(--ink-0)",
        border: `1px solid ${focus ? "var(--accent)" : "var(--paper-2)"}`,
        boxShadow: focus ? "0 0 0 3px var(--accent-softer)" : "none",
        borderRadius: "var(--r-md)",
        transition:
          "border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)",
        fontFamily: "var(--sans)",
      }}
    >
      {icon && <span style={{ color: "var(--ink-3)" }}>{icon}</span>}
      <input
        value={value ?? ""}
        onChange={(e) => onChange?.(e.target.value)}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        placeholder={placeholder}
        style={{
          flex: 1,
          border: 0,
          outline: "none",
          background: "transparent",
          fontFamily: "var(--sans)",
          fontSize: 14,
          color: "var(--ink-0)",
        }}
      />
    </div>
  );
}
```

- [ ] **Step 5.6: Implement Button (no test — inert button)**

Create `frontend/src/components/Button.tsx`:

```tsx
import type { PropsWithChildren, ReactNode } from "react";

type ButtonProps = PropsWithChildren<{
  variant?: "primary" | "secondary" | "ghost";
  icon?: ReactNode;
  onClick?: () => void;
  title?: string;
}>;

const VARIANTS = {
  primary: { bg: "var(--ink-0)", color: "var(--paper-0)" },
  secondary: { bg: "var(--paper-1)", color: "var(--ink-0)" },
  ghost: { bg: "transparent", color: "var(--ink-1)" },
} as const;

export function Button({
  variant = "secondary",
  icon,
  children,
  onClick,
  title,
}: ButtonProps) {
  const v = VARIANTS[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
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
        background: v.bg,
        color: v.color,
        border: 0,
        cursor: "pointer",
      }}
    >
      {icon}
      {children}
    </button>
  );
}
```

- [ ] **Step 5.7: Write the failing LibraryScreen test**

Create `frontend/src/screens/LibraryScreen.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { LibraryScreen } from "./LibraryScreen";

const CC = {
  book_id: "christmas_carol_e6ddcd76",
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 1,
  ready_for_query: true,
};

describe("LibraryScreen", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("shows a loading state before the response arrives", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    render(<LibraryScreen />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders one BookCard per returned book after success", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([CC]),
    }) as unknown as typeof fetch;

    render(<LibraryScreen />);

    await waitFor(() => {
      expect(screen.getByText("Christmas Carol")).toBeInTheDocument();
    });
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    render(<LibraryScreen />);

    await waitFor(() => {
      expect(screen.getByText(/couldn.?t load your books/i)).toBeInTheDocument();
    });
  });

  it("renders the 'Your shelf' header and NavBar", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;

    render(<LibraryScreen />);

    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
    // NavBar's three tabs
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5.8: Run it to verify it fails**

Run: `npm test -- LibraryScreen`
Expected: `Failed to resolve import`.

- [ ] **Step 5.9: Implement LibraryScreen**

Create `frontend/src/screens/LibraryScreen.tsx`:

```tsx
import { useEffect, useState } from "react";
import { NavBar } from "../components/NavBar";
import { BookCard } from "../components/BookCard";
import { TextInput } from "../components/TextInput";
import { Button } from "../components/Button";
import { Row } from "../components/layout";
import { IcPlus, IcSearch } from "../components/icons";
import { fetchBooks, type Book } from "../lib/api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; books: Book[] };

export function LibraryScreen() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchBooks()
      .then((books) => {
        if (!cancelled) setState({ kind: "ok", books });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : String(err),
          });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="br" style={{ minHeight: "100vh", background: "var(--paper-0)" }}>
      <NavBar active="library" />
      <div style={{ maxWidth: 1040, margin: "0 auto", padding: "48px 32px 80px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: 40,
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--sans)",
                fontSize: 12,
                letterSpacing: 1.6,
                textTransform: "uppercase",
                color: "var(--ink-3)",
                marginBottom: 10,
              }}
            >
              Your shelf
            </div>
            <h1
              style={{
                margin: 0,
                fontFamily: "var(--serif)",
                fontWeight: 400,
                fontSize: 44,
                letterSpacing: -0.8,
                color: "var(--ink-0)",
                lineHeight: 1.1,
              }}
            >
              Your library.
            </h1>
          </div>
          <Row gap={10}>
            <div style={{ width: 240 }}>
              <TextInput size="sm" icon={<IcSearch size={13} />} placeholder="Search your books" />
            </div>
            <Button variant="secondary" icon={<IcPlus size={13} />}>
              Add book
            </Button>
          </Row>
        </div>

        {state.kind === "loading" && (
          <div
            role="status"
            style={{ fontFamily: "var(--sans)", fontSize: 14, color: "var(--ink-2)" }}
          >
            Loading your books…
          </div>
        )}

        {state.kind === "error" && (
          <div
            role="alert"
            style={{
              fontFamily: "var(--sans)",
              fontSize: 14,
              color: "var(--err)",
              padding: 16,
              border: "1px solid var(--paper-2)",
              borderRadius: "var(--r-md)",
              background: "var(--paper-00)",
            }}
          >
            Couldn’t load your books. ({state.message})
          </div>
        )}

        {state.kind === "ok" && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 40,
              rowGap: 56,
            }}
          >
            {state.books.map((b) => (
              <BookCard
                key={b.book_id}
                book_id={b.book_id}
                title={b.title}
                total_chapters={b.total_chapters}
                current_chapter={b.current_chapter}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5.10: Run it to verify it passes**

Run: `npm test -- LibraryScreen`
Expected: 4 passed.

- [ ] **Step 5.11: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts frontend/src/components/TextInput.tsx frontend/src/components/Button.tsx frontend/src/screens/
git commit -m "$(cat <<'EOF'
feat(frontend): add fetchBooks client and LibraryScreen page

LibraryScreen fetches http://localhost:8000/books on mount and renders
a loading state, an error state, and a BookCard grid on success.
TextInput and Button are ported from the handoff but inert as noted in
the slice PRD (search onChange is a no-op, Add book does nothing).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Wire `LibraryScreen` into `App`, run full verification

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 6.1: Update App test to assert the shelf header**

Replace the entire content of `frontend/src/App.test.tsx` with:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
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

  it("renders the Library screen at /", () => {
    render(<App />);
    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6.2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- App`
Expected: FAIL — `App` still renders only the wordmark stub; it does not render the "Your shelf" text yet.

- [ ] **Step 6.3: Replace App to render LibraryScreen**

Replace `frontend/src/App.tsx` with:

```tsx
import { LibraryScreen } from "./screens/LibraryScreen";

export function App() {
  return <LibraryScreen />;
}
```

- [ ] **Step 6.4: Run the full frontend test suite**

Run (from `frontend/`): `npm test`
Expected: all tests pass (App, NavBar, BookCover, ProgressPill, BookCard, LibraryScreen, api, mood).

- [ ] **Step 6.5: Manual verification against the real backend**

In one terminal (project root): `python main.py`
In another terminal (`frontend/`): `npm run dev`
Open `http://localhost:5173/`.
Expected:
- NavBar with the Bookrag wordmark and three tabs (Library active, Reading and Upload present).
- "Your shelf" caption and heading.
- A single `BookCard` for Christmas Carol with the serif italic title, a two-tone generative cover, and a progress pill reading "3 of 3" (or whatever `reading_progress.json` says).
- Clicking "Reading" or "Upload" changes nothing and throws no errors in the console.
- The page uses the linen paper palette and serif/sans typography.

Also verify the endpoint directly: `curl -s http://localhost:8000/books | python -m json.tool`
Expected: a JSON array containing the Christmas Carol record.

- [ ] **Step 6.6: Run the full backend test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests pass (including the new `tests/test_books_endpoint.py`, no regressions in `test_main.py` or elsewhere).

- [ ] **Step 6.7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): mount LibraryScreen as the root route in App

The App component now renders LibraryScreen directly. No router is
added — a single page at / is sufficient for slice 1 per the PRD.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

**Spec coverage — every acceptance criterion maps to at least one task:**

| AC | Covered by |
|----|------------|
| 1. `npm run dev` on port 5173 without console errors | Task 2 Step 2.14, Task 6 Step 6.5 |
| 2. NavBar wordmark + "Your shelf" + card grid | Task 3 (NavBar), Task 5 (LibraryScreen), Task 6 |
| 3. Fetches `/books` on mount with loading/error states | Task 5 Step 5.7–5.11 |
| 4. Christmas Carol card with cover, title, progress pill, chapter text | Task 1, Task 4, Task 5, Task 6 Step 6.5 |
| 5. Only `ready_for_query: true` books appear | Task 1 Step 1.1 (`test_excludes_not_ready_books`) |
| 6. Tokens loaded globally, Lora + IBM Plex visible | Task 2 Step 2.5 (fonts link), Step 2.8 (tokens.css), Step 2.12 (import in main.tsx) |
| 7. `GET /books` returns JSON array from scan | Task 1 Step 1.3 |
| 8. `pytest -v` passes with empty + one-book cases | Task 1 Step 1.1–1.4 |
| 9. No existing backend tests regress | Task 1 Step 1.4, Task 6 Step 6.6 |
| 10. NavBar active=Library, inert Reading/Upload don't throw | Task 3 Step 3.1 (the user-event test) |

**Placeholder scan:** no "TODO", "TBD", "fill in" or undefined references. Every function called in a test has a corresponding implementation step. Every type used is defined.

**Type consistency:** `Book` is defined in `lib/api.ts` and used in `LibraryScreen.tsx`. `BookSummary` (backend) has the same fields as `Book` (frontend). `BookCardProps` on the frontend takes `book_id`, `title`, `total_chapters`, `current_chapter` — same as the API. `moodForBookId` returns `Mood`, consumed by `BookCover` via `PALETTE`.
