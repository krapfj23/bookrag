# Slice 2 — upload-pipeline-status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Generator note — UI tasks 3–6:** when implementing `Dropzone`, `StatusBadge`, `PipelineRow`, and `UploadScreen` (Tasks 3, 4, 5, 6), invoke the `frontend-design:frontend-design` skill so the ported components stay visually faithful to `design-handoff/project/components2.jsx` and `design-handoff/project/screens.jsx`. The existing TSX conventions in `frontend/src/components/` (inline-style objects driven by `var(--*)` tokens, no CSS modules, no class-based styling) must be preserved.

**Goal:** Ship the Upload screen end-to-end — a drag-and-drop EPUB dropzone that POSTs to `/books/upload`, polls `GET /books/{id}/status` every 2 seconds, renders the 7 pipeline stages with real status badges, and returns the user to a refreshed Library after `ready_for_query: true`.

**Architecture:** Extends the slice-1 frontend without touching the backend. Adds `react-router-dom@6` with two routes (`/` → `LibraryScreen`, `/upload` → `UploadScreen`). Extends `lib/api.ts` with `uploadBook` (multipart POST with typed error mapping) and `fetchStatus` (single GET). Ports three new components — `Dropzone`, `StatusBadge`, `PipelineRow` — and a new `UploadScreen` that drives the upload state machine and polls status on a 2 s `setInterval`, halting on `ready_for_query === true` or any stage `status === "failed"`. A hermetic Playwright suite (`frontend/e2e/`) intercepts `/books/upload` and `/books/{id}/status` with `page.route()` fixtures so the E2E tests need no live backend.

**Tech Stack:** React 18, TypeScript, Vite 5, Vitest 2 + jsdom + Testing Library (unchanged from slice 1). New: `react-router-dom@6`, `@playwright/test`. CSS via raw `var(--*)` tokens plus one added `@keyframes brPulse` in a new `frontend/src/styles/animations.css`.

---

## File Structure

**Frontend — new files:**
- `frontend/src/screens/UploadScreen.tsx`, `frontend/src/screens/UploadScreen.test.tsx`
- `frontend/src/components/Dropzone.tsx`, `frontend/src/components/Dropzone.test.tsx`
- `frontend/src/components/StatusBadge.tsx`, `frontend/src/components/StatusBadge.test.tsx`
- `frontend/src/components/PipelineRow.tsx`, `frontend/src/components/PipelineRow.test.tsx`
- `frontend/src/styles/animations.css`
- `frontend/playwright.config.ts`
- `frontend/e2e/upload.spec.ts`

**Frontend — modified files:**
- `frontend/package.json` (add `react-router-dom`, `@playwright/test`, `test:e2e` script)
- `frontend/src/main.tsx` (wrap `App` in `<BrowserRouter>`; import `animations.css`)
- `frontend/src/App.tsx` (declare routes)
- `frontend/src/App.test.tsx` (route-based assertions using `MemoryRouter`)
- `frontend/src/components/NavBar.tsx` (replace `<a>` with `<Link>`, derive `active` from `useLocation()`)
- `frontend/src/components/NavBar.test.tsx` (wrap renders in `<MemoryRouter>`)
- `frontend/src/components/icons.tsx` (add `IcUpload`, `IcCheck`, `IcClose`)
- `frontend/src/lib/api.ts` (add `uploadBook`, `fetchStatus`, new types)
- `frontend/src/lib/api.test.ts` (add tests for the new functions)
- `frontend/src/screens/LibraryScreen.tsx` (refetch on route entry)
- `frontend/src/screens/LibraryScreen.test.tsx` (wrap in `<MemoryRouter>`; add refetch test)

**Backend:** no changes. The three endpoints `POST /books/upload`, `GET /books/{book_id}/status`, `GET /books` already satisfy this slice.

---

## Task 1: Router introduction

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/components/NavBar.tsx`
- Modify: `frontend/src/components/NavBar.test.tsx`
- Modify: `frontend/src/screens/LibraryScreen.test.tsx`

- [ ] **Step 1.1: Install `react-router-dom@6`**

From `frontend/`:

```bash
npm install react-router-dom@^6.26.0
```

Expected: `package.json` `dependencies` gains `"react-router-dom": "^6.26.x"`; `package-lock.json` updates.

- [ ] **Step 1.2: Update the failing NavBar test to use MemoryRouter**

Replace the entire content of `frontend/src/components/NavBar.test.tsx` with:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { NavBar } from "./NavBar";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <NavBar />
    </MemoryRouter>
  );
}

describe("NavBar", () => {
  it("renders the three tabs and the wordmark", () => {
    renderAt("/");
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText(/book/i)).toBeInTheDocument();
  });

  it("marks Library active when the route is /", () => {
    renderAt("/");
    const active = screen.getByText("Library");
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active).toHaveAttribute("data-active", "true");
    expect(screen.getByText("Upload")).toHaveAttribute("data-active", "false");
  });

  it("marks Upload active when the route is /upload", () => {
    renderAt("/upload");
    expect(screen.getByText("Upload")).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Library")).toHaveAttribute("data-active", "false");
  });

  it("Reading stays inert — clicking it does not throw and does not change the active tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderAt("/");
    await user.click(screen.getByText("Reading"));
    expect(screen.getByText("Library")).toHaveAttribute("aria-current", "page");
  });

  it("Library and Upload are real links with href attributes", () => {
    renderAt("/");
    expect(screen.getByText("Library").closest("a")).toHaveAttribute("href", "/");
    expect(screen.getByText("Upload").closest("a")).toHaveAttribute("href", "/upload");
  });
});
```

- [ ] **Step 1.3: Run NavBar test and confirm failures**

From `frontend/`:

```bash
npm test -- NavBar
```

Expected: multiple failures — the current `NavBar` renders plain `<a href="#">` so the `href="/upload"` assertion fails, and the `aria-current` test for the `/upload` route fails because `active` is a prop, not route-derived.

- [ ] **Step 1.4: Rewrite `NavBar.tsx` to use `Link` + `useLocation`**

Replace the entire content of `frontend/src/components/NavBar.tsx` with:

```tsx
import { Link, useLocation } from "react-router-dom";
import { Row } from "./layout";
import { Wordmark } from "./Wordmark";
import { IconBtn } from "./IconBtn";
import { IcMoon, IcSun, IcSettings } from "./icons";

export type NavTab = "library" | "reading" | "upload";

type NavBarProps = {
  theme?: "light" | "dark";
  onThemeToggle?: () => void;
};

type Item =
  | { id: NavTab; label: string; to: string; inert?: false }
  | { id: NavTab; label: string; to?: undefined; inert: true };

const ITEMS: Item[] = [
  { id: "library", label: "Library", to: "/" },
  { id: "reading", label: "Reading", inert: true },
  { id: "upload", label: "Upload", to: "/upload" },
];

function tabForPath(pathname: string): NavTab {
  if (pathname === "/upload" || pathname.startsWith("/upload/")) return "upload";
  return "library";
}

export function NavBar({ theme = "light", onThemeToggle }: NavBarProps) {
  const { pathname } = useLocation();
  const active = tabForPath(pathname);

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
            const baseStyle: React.CSSProperties = {
              padding: "6px 12px",
              fontSize: "var(--t-sm)",
              color: isActive ? "var(--ink-0)" : "var(--ink-2)",
              borderRadius: "var(--r-sm)",
              fontWeight: isActive ? 500 : 400,
              background: isActive ? "var(--paper-1)" : "transparent",
              textDecoration: "none",
              cursor: it.inert ? "default" : "pointer",
              transition:
                "color var(--dur) var(--ease), background var(--dur) var(--ease)",
            };

            if (it.inert) {
              return (
                <a
                  key={it.id}
                  href="#"
                  aria-disabled="true"
                  data-active={isActive ? "true" : "false"}
                  onClick={(e) => e.preventDefault()}
                  style={baseStyle}
                >
                  {it.label}
                </a>
              );
            }

            return (
              <Link
                key={it.id}
                to={it.to}
                aria-current={isActive ? "page" : undefined}
                data-active={isActive ? "true" : "false"}
                style={baseStyle}
              >
                {it.label}
              </Link>
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

- [ ] **Step 1.5: Update `LibraryScreen.test.tsx` to wrap in `MemoryRouter`**

Replace the entire content of `frontend/src/screens/LibraryScreen.test.tsx` with:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LibraryScreen } from "./LibraryScreen";

const CC = {
  book_id: "christmas_carol_e6ddcd76",
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 1,
  ready_for_query: true,
};

function renderLib() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <LibraryScreen />
    </MemoryRouter>
  );
}

describe("LibraryScreen", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("shows a loading state before the response arrives", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    renderLib();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders one BookCard per returned book after success", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([CC]),
    }) as unknown as typeof fetch;

    renderLib();

    await waitFor(() => {
      expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    renderLib();

    await waitFor(() => {
      expect(screen.getByText(/couldn.?t load your books/i)).toBeInTheDocument();
    });
  });

  it("renders the 'Your shelf' header and NavBar", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;

    renderLib();

    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
  });
});
```

- [ ] **Step 1.6: Update `App.test.tsx` for route-based assertions**

Replace the entire content of `frontend/src/App.test.tsx` with:

```tsx
import { render, screen } from "@testing-library/react";
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
});
```

- [ ] **Step 1.7: Write a placeholder `UploadScreen.tsx` and wire `App.tsx` routes**

Create `frontend/src/screens/UploadScreen.tsx`:

```tsx
import { NavBar } from "../components/NavBar";

export function UploadScreen() {
  return (
    <div className="br" style={{ minHeight: "100vh", background: "var(--paper-0)" }}>
      <NavBar />
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "64px 32px 80px" }}>
        <div
          style={{
            fontFamily: "var(--sans)",
            fontSize: 11,
            letterSpacing: 1.6,
            textTransform: "uppercase",
            color: "var(--ink-3)",
            marginBottom: 10,
          }}
        >
          Add a book
        </div>
        <h1
          style={{
            margin: "0 0 8px",
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: 38,
            letterSpacing: -0.8,
            color: "var(--ink-0)",
          }}
        >
          Upload an EPUB.
        </h1>
      </div>
    </div>
  );
}
```

Replace the entire content of `frontend/src/App.tsx` with:

```tsx
import { Routes, Route } from "react-router-dom";
import { LibraryScreen } from "./screens/LibraryScreen";
import { UploadScreen } from "./screens/UploadScreen";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryScreen />} />
      <Route path="/upload" element={<UploadScreen />} />
    </Routes>
  );
}
```

Also remove the now-unused `active="library"` prop from inside `LibraryScreen.tsx` — the NavBar no longer accepts it. Replace the single line `<NavBar active="library" />` in `frontend/src/screens/LibraryScreen.tsx` with:

```tsx
<NavBar />
```

- [ ] **Step 1.8: Wrap `<App />` in `<BrowserRouter>` in `main.tsx`**

Replace the entire content of `frontend/src/main.tsx` with:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles/tokens.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 1.9: Run all frontend tests**

From `frontend/`:

```bash
npm test
```

Expected: all tests pass — NavBar (5), App (2), LibraryScreen (4), api (2), mood (4), BookCover (2), ProgressPill (3), BookCard (2). The single `npm test` output should report ≥24 tests passing.

- [ ] **Step 1.10: Commit**

From the repo root:

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/NavBar.tsx frontend/src/components/NavBar.test.tsx frontend/src/screens/LibraryScreen.tsx frontend/src/screens/LibraryScreen.test.tsx frontend/src/screens/UploadScreen.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): introduce react-router-dom with /, /upload routes

Wraps App in BrowserRouter and declares two routes. NavBar swaps the
inert <a href="#"> items for <Link> (Library, Upload) and derives the
active tab from useLocation(). Reading stays as an aria-disabled
anchor that no-ops on click. Adds a stub UploadScreen with the page
header so route tests can assert it renders.
EOF
)"
```

---

## Task 2: API client extensions — `uploadBook` and `fetchStatus`

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api.test.ts`

- [ ] **Step 2.1: Write the failing tests**

Replace the entire content of `frontend/src/lib/api.test.ts` with:

```ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchBooks,
  uploadBook,
  fetchStatus,
  UploadError,
  type PipelineState,
} from "./api";

describe("fetchBooks", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => vi.resetAllMocks());
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

describe("uploadBook", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  function makeFile(name = "a-christmas-carol.epub"): File {
    return new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, {
      type: "application/epub+zip",
    });
  }

  it("POSTs multipart/form-data to /books/upload and returns the body", async () => {
    const body = { book_id: "a_christmas_carol_a1b2c3d4", message: "Pipeline started" };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await uploadBook(makeFile());

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/books/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("file")).toBeInstanceOf(File);
    expect((form.get("file") as File).name).toBe("a-christmas-carol.epub");
    expect(result).toEqual(body);
  });

  it("maps 400 to 'Only .epub files are accepted'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: "Only .epub files are accepted" }),
    }) as unknown as typeof fetch;

    await expect(uploadBook(makeFile("foo.txt"))).rejects.toBeInstanceOf(UploadError);
    try {
      await uploadBook(makeFile("foo.txt"));
    } catch (err) {
      expect(err).toBeInstanceOf(UploadError);
      expect((err as UploadError).status).toBe(400);
      expect((err as UploadError).message).toBe("Only .epub files are accepted");
    }
  });

  it("maps 413 to 'File too large (max 500 MB)'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 413,
      json: () => Promise.resolve({ detail: "too big" }),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect(err).toBeInstanceOf(UploadError);
      expect((err as UploadError).status).toBe(413);
      expect((err as UploadError).message).toBe("File too large (max 500 MB)");
    }
  });

  it("maps 429 to 'Too many pipelines running, try again later'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ detail: "5/5 running" }),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect((err as UploadError).message).toBe(
        "Too many pipelines running, try again later"
      );
    }
  });

  it("falls back to backend detail text on other non-2xx", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "Failed to save uploaded file" }),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect((err as UploadError).status).toBe(500);
      expect((err as UploadError).message).toBe("Failed to save uploaded file");
    }
  });

  it("uses a generic message when JSON parsing fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error("not json")),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect((err as UploadError).status).toBe(502);
      expect((err as UploadError).message).toMatch(/upload failed/i);
    }
  });
});

describe("fetchStatus", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs /books/{id}/status and returns PipelineState", async () => {
    const state: PipelineState = {
      book_id: "a_christmas_carol_a1b2c3d4",
      status: "processing",
      stages: {
        parse_epub: { status: "complete", duration_seconds: 0.4 },
        run_booknlp: { status: "running" },
        resolve_coref: { status: "pending" },
        discover_ontology: { status: "pending" },
        review_ontology: { status: "pending" },
        run_cognee_batches: { status: "pending" },
        validate: { status: "pending" },
      },
      current_batch: null,
      total_batches: null,
      ready_for_query: false,
    };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(state),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await fetchStatus("a_christmas_carol_a1b2c3d4");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books/a_christmas_carol_a1b2c3d4/status"
    );
    expect(result).toEqual(state);
  });

  it("throws on non-OK responses", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;
    await expect(fetchStatus("missing_book")).rejects.toThrow(/404/);
  });
});
```

- [ ] **Step 2.2: Run tests and verify they fail**

From `frontend/`:

```bash
npm test -- api
```

Expected: the new tests fail with `UploadError`, `uploadBook`, `fetchStatus`, and `PipelineState` not exported from `./api`. The two pre-existing `fetchBooks` tests continue to pass.

- [ ] **Step 2.3: Extend `lib/api.ts`**

Replace the entire content of `frontend/src/lib/api.ts` with:

```ts
export type Book = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  ready_for_query: boolean;
};

export type StageName =
  | "parse_epub"
  | "run_booknlp"
  | "resolve_coref"
  | "discover_ontology"
  | "review_ontology"
  | "run_cognee_batches"
  | "validate";

export type StageStatus = "pending" | "running" | "complete" | "failed";

export type PipelineStage = {
  status: StageStatus;
  duration_seconds?: number;
  error?: string;
};

export type PipelineOverall = "pending" | "processing" | "complete" | "failed";

export type PipelineState = {
  book_id: string;
  status: PipelineOverall;
  stages: Record<StageName, PipelineStage>;
  current_batch: number | null;
  total_batches: number | null;
  ready_for_query: boolean;
};

export type UploadResponse = {
  book_id: string;
  message: string;
};

export class UploadError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "UploadError";
    this.status = status;
  }
}

const BASE_URL = "http://localhost:8000";

export async function fetchBooks(): Promise<Book[]> {
  const resp = await fetch(`${BASE_URL}/books`);
  if (!resp.ok) {
    throw new Error(`GET /books failed: ${resp.status}`);
  }
  return (await resp.json()) as Book[];
}

export async function uploadBook(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);

  const resp = await fetch(`${BASE_URL}/books/upload`, {
    method: "POST",
    body: form,
  });

  if (resp.ok) {
    return (await resp.json()) as UploadResponse;
  }

  let detail = "";
  try {
    const body = (await resp.json()) as { detail?: string };
    detail = body.detail ?? "";
  } catch {
    detail = "";
  }

  const message = mapUploadError(resp.status, detail);
  throw new UploadError(resp.status, message);
}

function mapUploadError(status: number, detail: string): string {
  if (status === 400) return "Only .epub files are accepted";
  if (status === 413) return "File too large (max 500 MB)";
  if (status === 429) return "Too many pipelines running, try again later";
  if (detail) return detail;
  return `Upload failed (${status})`;
}

export async function fetchStatus(book_id: string): Promise<PipelineState> {
  const resp = await fetch(`${BASE_URL}/books/${book_id}/status`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/status failed: ${resp.status}`);
  }
  return (await resp.json()) as PipelineState;
}
```

- [ ] **Step 2.4: Run tests and verify they pass**

From `frontend/`:

```bash
npm test -- api
```

Expected: all api tests pass — 2 `fetchBooks`, 6 `uploadBook`, 2 `fetchStatus` = 10 passed.

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add uploadBook and fetchStatus API clients

uploadBook POSTs multipart/form-data to /books/upload and throws an
UploadError with the exact error strings mandated by the slice PRD:
400 → "Only .epub files are accepted", 413 → "File too large (max 500
MB)", 429 → "Too many pipelines running, try again later", other →
backend detail or a generic fallback. fetchStatus GETs the sanitized
PipelineState for polling. Exports PipelineState, PipelineStage,
StageName, and UploadResponse for use by UploadScreen.
EOF
)"
```

---

## Task 3: `Dropzone` component

**Files:**
- Modify: `frontend/src/components/icons.tsx`
- Create: `frontend/src/components/Dropzone.tsx`
- Create: `frontend/src/components/Dropzone.test.tsx`

> **Generator:** invoke `frontend-design:frontend-design` for this task to preserve visual fidelity to `design-handoff/project/components2.jsx` lines 207–238.

- [ ] **Step 3.1: Add `IcUpload`, `IcCheck`, `IcClose` to `icons.tsx`**

Append (inside `frontend/src/components/icons.tsx`, after the existing `IcSettings` export) the following:

```tsx
export const IcUpload = (p: Props) => (
  <Icon {...p} d="M8 11V3m0 0L5 6m3-3l3 3M3 13h10" />
);
export const IcCheck = (p: Props) => (
  <Icon {...p} d="M3 8.5L6.5 12 13 5" />
);
export const IcClose = (p: Props) => (
  <Icon {...p} d="M4 4l8 8M12 4l-8 8" />
);
```

- [ ] **Step 3.2: Write the failing test**

Create `frontend/src/components/Dropzone.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Dropzone } from "./Dropzone";

function makeFile(name = "a.epub"): File {
  return new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, {
    type: "application/epub+zip",
  });
}

describe("Dropzone", () => {
  it("renders idle copy by default", () => {
    render(<Dropzone state="idle" onFile={() => {}} />);
    expect(screen.getByText(/drop your epub/i)).toBeInTheDocument();
    expect(screen.getByText(/browse files/i)).toBeInTheDocument();
    expect(screen.getByText(/epub up to 500/i)).toBeInTheDocument();
  });

  it("renders hover copy when state='hover'", () => {
    render(<Dropzone state="hover" onFile={() => {}} />);
    expect(screen.getByText(/drop it here/i)).toBeInTheDocument();
  });

  it("renders the filename when state='uploading'", () => {
    render(<Dropzone state="uploading" filename="a-christmas-carol.epub" onFile={() => {}} />);
    expect(screen.getByText("a-christmas-carol.epub")).toBeInTheDocument();
    expect(screen.getByText(/uploading/i)).toBeInTheDocument();
  });

  it("renders the filename and a done marker when state='done'", () => {
    render(<Dropzone state="done" filename="a-christmas-carol.epub" onFile={() => {}} />);
    expect(screen.getByText("a-christmas-carol.epub")).toBeInTheDocument();
    expect(screen.getByText(/uploaded/i)).toBeInTheDocument();
  });

  it("renders errorMessage when state='error'", () => {
    render(
      <Dropzone
        state="error"
        errorMessage="Only .epub files are accepted"
        onFile={() => {}}
      />
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /only \.epub files are accepted/i
    );
  });

  it("calls onFile when a file is dropped", () => {
    const onFile = vi.fn();
    render(<Dropzone state="idle" onFile={onFile} />);
    const zone = screen.getByTestId("dropzone");
    fireEvent.drop(zone, {
      dataTransfer: { files: [makeFile("x.epub")] },
    });
    expect(onFile).toHaveBeenCalledTimes(1);
    expect(onFile.mock.calls[0][0].name).toBe("x.epub");
  });

  it("calls onFile when a file is selected via the hidden input", () => {
    const onFile = vi.fn();
    render(<Dropzone state="idle" onFile={onFile} />);
    const input = screen.getByTestId("dropzone-input") as HTMLInputElement;
    const file = makeFile("b.epub");
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("does not call onFile on drop when state is 'uploading'", () => {
    const onFile = vi.fn();
    render(<Dropzone state="uploading" filename="x.epub" onFile={onFile} />);
    const zone = screen.getByTestId("dropzone");
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile("y.epub")] } });
    expect(onFile).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3.3: Run test to verify it fails**

From `frontend/`:

```bash
npm test -- Dropzone
```

Expected: `Failed to resolve import "./Dropzone"`.

- [ ] **Step 3.4: Implement `Dropzone.tsx`**

Create `frontend/src/components/Dropzone.tsx`:

```tsx
import { useRef, useState, type CSSProperties, type DragEvent, type ChangeEvent } from "react";
import { IcUpload, IcCheck, IcClose } from "./icons";

export type DropzoneState = "idle" | "hover" | "uploading" | "done" | "error";

type DropzoneProps = {
  state: DropzoneState;
  filename?: string;
  errorMessage?: string;
  onFile: (file: File) => void;
};

export function Dropzone({ state, filename, errorMessage, onFile }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const busy = state === "uploading";
  const isHover = state === "hover" || dragOver;
  const isDone = state === "done";
  const isError = state === "error";

  const border = isError
    ? "1.5px dashed var(--err)"
    : `1.5px dashed ${isHover ? "var(--accent)" : "var(--paper-3)"}`;

  const bg = isError
    ? "color-mix(in oklab, var(--err) 8%, var(--paper-00))"
    : isHover
    ? "var(--accent-softer)"
    : "var(--paper-00)";

  const iconBg = isDone
    ? "var(--ok)"
    : isError
    ? "var(--err)"
    : isHover || busy
    ? "var(--accent)"
    : "var(--paper-1)";

  const iconFg = isDone || isError || isHover || busy ? "var(--paper-00)" : "var(--ink-2)";

  const primaryCopy = (() => {
    if (isError) return filename ?? "Something went wrong";
    if (isDone) return filename ?? "Upload complete";
    if (busy) return filename ?? "Uploading…";
    if (isHover) return "Drop it here";
    return "Drop your EPUB";
  })();

  const secondaryCopy = (() => {
    if (isError) return null;
    if (isDone) return "Uploaded";
    if (busy) return "Uploading…";
    return null;
  })();

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (!busy) setDragOver(true);
  }
  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
  }
  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (busy) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  }
  function handleClick() {
    if (busy) return;
    inputRef.current?.click();
  }
  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) onFile(f);
    // allow the same file to be picked again later
    e.target.value = "";
  }

  const rootStyle: CSSProperties = {
    border,
    background: bg,
    borderRadius: "var(--r-lg)",
    padding: "56px 40px",
    textAlign: "center",
    fontFamily: "var(--sans)",
    color: "var(--ink-1)",
    transition: "all var(--dur) var(--ease)",
    cursor: busy ? "progress" : "pointer",
  };

  return (
    <div
      data-testid="dropzone"
      data-state={state}
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={rootStyle}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 44,
          height: 44,
          borderRadius: 999,
          background: iconBg,
          color: iconFg,
          marginBottom: 16,
          transition: "all var(--dur) var(--ease)",
        }}
      >
        {isDone ? <IcCheck size={18} /> : isError ? <IcClose size={18} /> : <IcUpload size={18} />}
      </div>

      <div
        style={{
          fontFamily: "var(--serif)",
          fontSize: 20,
          color: "var(--ink-0)",
          letterSpacing: -0.3,
          marginBottom: 6,
        }}
      >
        {primaryCopy}
      </div>

      {isError ? (
        <div role="alert" style={{ fontSize: 13, color: "var(--err)" }}>
          {errorMessage ?? "Something went wrong"}
        </div>
      ) : secondaryCopy ? (
        <div style={{ fontSize: 13, color: "var(--ink-2)" }}>{secondaryCopy}</div>
      ) : (
        <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
          or{" "}
          <span
            style={{
              color: "var(--accent)",
              textDecoration: "underline",
              textUnderlineOffset: 3,
            }}
          >
            browse files
          </span>{" "}
          · EPUB up to 500&nbsp;MB
        </div>
      )}

      <input
        ref={inputRef}
        data-testid="dropzone-input"
        type="file"
        accept=".epub,application/epub+zip"
        onChange={handleChange}
        style={{ display: "none" }}
      />
    </div>
  );
}
```

- [ ] **Step 3.5: Run test to verify it passes**

From `frontend/`:

```bash
npm test -- Dropzone
```

Expected: 8 passed.

- [ ] **Step 3.6: Commit**

```bash
git add frontend/src/components/icons.tsx frontend/src/components/Dropzone.tsx frontend/src/components/Dropzone.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port Dropzone component from design handoff

Controlled component with idle/hover/uploading/done/error states,
drag-and-drop plus click-to-browse triggering a hidden file input.
Exposes onFile(file) and keeps visual parity with
design-handoff/project/components2.jsx lines 207–238. Adds IcUpload,
IcCheck, IcClose icons needed by the dropzone and later pipeline rows.
EOF
)"
```

---

## Task 4: `StatusBadge` + `brPulse` keyframe

**Files:**
- Create: `frontend/src/styles/animations.css`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/components/StatusBadge.tsx`
- Create: `frontend/src/components/StatusBadge.test.tsx`

> **Generator:** invoke `frontend-design:frontend-design` for this task. The source of truth is `design-handoff/project/components2.jsx` lines 244–270, and the `brPulse` keyframe is defined verbatim in `design-handoff/project/BookRAG Design System.html` line 13.

- [ ] **Step 4.1: Create `animations.css` with the `brPulse` keyframe**

Create `frontend/src/styles/animations.css`:

```css
/* ─────────────────────────────────────────────────────────
   Animations — ported from design-handoff/project
   ───────────────────────────────────────────────────────── */

@keyframes brPulse {
  0%   { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
  70%  { box-shadow: 0 0 0 6px transparent; opacity: 0.65; }
  100% { box-shadow: 0 0 0 0 transparent; opacity: 1; }
}
```

- [ ] **Step 4.2: Import `animations.css` from `main.tsx`**

Edit `frontend/src/main.tsx`. Add a new import line directly below the existing `import "./styles/tokens.css";` so the top of the file reads:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles/tokens.css";
import "./styles/animations.css";
```

- [ ] **Step 4.3: Write the failing test**

Create `frontend/src/components/StatusBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders 'idle' with the idle label", () => {
    render(<StatusBadge state="idle" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "idle");
    expect(badge).toHaveTextContent(/idle/i);
  });

  it("renders 'queued' with the queued label", () => {
    render(<StatusBadge state="queued" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "queued");
    expect(badge).toHaveTextContent(/queued/i);
  });

  it("renders 'running' with a pulsing indicator", () => {
    render(<StatusBadge state="running" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "running");
    expect(badge).toHaveTextContent(/running/i);
    const dot = badge.querySelector("[data-pulse='true']");
    expect(dot).toBeTruthy();
  });

  it("renders 'done'", () => {
    render(<StatusBadge state="done" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "done");
    expect(badge).toHaveTextContent(/done/i);
  });

  it("renders 'error' with the 'failed' label", () => {
    render(<StatusBadge state="error" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "failed");
    expect(badge).toHaveTextContent(/failed/i);
  });

  it("honors a custom label override", () => {
    render(<StatusBadge state="running" label="building — 3 of 7" />);
    expect(screen.getByRole("status")).toHaveTextContent(/building — 3 of 7/);
  });
});
```

- [ ] **Step 4.4: Run test to verify it fails**

From `frontend/`:

```bash
npm test -- StatusBadge
```

Expected: `Failed to resolve import "./StatusBadge"`.

- [ ] **Step 4.5: Implement `StatusBadge.tsx`**

Create `frontend/src/components/StatusBadge.tsx`:

```tsx
import type { CSSProperties } from "react";

export type BadgeState = "idle" | "queued" | "running" | "done" | "error";

type StatusBadgeProps = {
  state: BadgeState;
  label?: string;
};

type Variant = {
  bg: string;
  fg: string;
  dot: string;
  pulse?: boolean;
};

const VARIANTS: Record<BadgeState, Variant> = {
  idle:    { bg: "var(--paper-1)",     fg: "var(--ink-2)",      dot: "var(--ink-3)" },
  queued:  { bg: "var(--paper-1)",     fg: "var(--ink-1)",      dot: "var(--ink-3)" },
  running: { bg: "var(--accent-softer)", fg: "var(--accent-ink)", dot: "var(--accent)", pulse: true },
  done:    { bg: "var(--accent-softer)", fg: "var(--accent-ink)", dot: "var(--ok)" },
  error:   {
    bg: "color-mix(in oklab, var(--err) 12%, var(--paper-0))",
    fg: "var(--err)",
    dot: "var(--err)",
  },
};

const DEFAULT_LABELS: Record<BadgeState, string> = {
  idle: "idle",
  queued: "queued",
  running: "running",
  done: "done",
  error: "failed",
};

export function StatusBadge({ state, label }: StatusBadgeProps) {
  const v = VARIANTS[state];
  const ariaLabel = DEFAULT_LABELS[state];
  const text = label ?? DEFAULT_LABELS[state];

  const rootStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    height: 22,
    padding: "0 10px",
    borderRadius: "var(--r-pill)",
    background: v.bg,
    color: v.fg,
    fontFamily: "var(--sans)",
    fontSize: 11,
    fontWeight: 500,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  };

  const dotStyle: CSSProperties = {
    width: 6,
    height: 6,
    borderRadius: 999,
    background: v.dot,
    boxShadow: v.pulse ? "0 0 0 0 currentColor" : "none",
    animation: v.pulse ? "brPulse 1.6s var(--ease-out) infinite" : "none",
  };

  return (
    <span role="status" aria-label={ariaLabel} style={rootStyle}>
      <span data-pulse={v.pulse ? "true" : "false"} style={dotStyle} />
      {text}
    </span>
  );
}
```

- [ ] **Step 4.6: Run test to verify it passes**

From `frontend/`:

```bash
npm test -- StatusBadge
```

Expected: 6 passed.

- [ ] **Step 4.7: Commit**

```bash
git add frontend/src/styles/animations.css frontend/src/main.tsx frontend/src/components/StatusBadge.tsx frontend/src/components/StatusBadge.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add StatusBadge with the brPulse keyframe

Ports the 5-state StatusBadge from the design handoff and introduces a
dedicated animations.css that defines the brPulse keyframe once and is
imported from main.tsx so every badge/pipeline dot can reference it.
aria-label uses 'failed' for the 'error' state to match the default
visual label and the PRD's stage status vocabulary.
EOF
)"
```

---

## Task 5: `PipelineRow` component

**Files:**
- Create: `frontend/src/components/PipelineRow.tsx`
- Create: `frontend/src/components/PipelineRow.test.tsx`

> **Generator:** invoke `frontend-design:frontend-design` for this task. Source is `design-handoff/project/components2.jsx` lines 272–297.

- [ ] **Step 5.1: Write the failing test**

Create `frontend/src/components/PipelineRow.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PipelineRow } from "./PipelineRow";

describe("PipelineRow", () => {
  it("renders title, description, and a StatusBadge", () => {
    render(
      <PipelineRow title="Parse EPUB" description="Split into chapter-segmented text" state="idle" />
    );
    expect(screen.getByText("Parse EPUB")).toBeInTheDocument();
    expect(screen.getByText(/split into chapter-segmented text/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "idle");
  });

  it("shows meta when state is 'done'", () => {
    render(
      <PipelineRow
        title="Parse EPUB"
        description="Split into chapter-segmented text"
        state="done"
        meta="0.4s"
      />
    );
    expect(screen.getByText("0.4s")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "done");
  });

  it("shows meta when state is 'error'", () => {
    render(
      <PipelineRow
        title="Validate"
        description="Spoiler-safety + spot checks"
        state="error"
        meta="OOM killed"
      />
    );
    expect(screen.getByText(/oom killed/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "failed");
  });

  it("does not render meta when state is 'idle' and meta is omitted", () => {
    const { container } = render(
      <PipelineRow
        title="Review ontology"
        description="Optional refinement"
        state="idle"
      />
    );
    expect(container.querySelector("[data-pipeline-meta]")).toBeNull();
  });
});
```

- [ ] **Step 5.2: Run test to verify it fails**

From `frontend/`:

```bash
npm test -- PipelineRow
```

Expected: `Failed to resolve import "./PipelineRow"`.

- [ ] **Step 5.3: Implement `PipelineRow.tsx`**

Create `frontend/src/components/PipelineRow.tsx`:

```tsx
import type { CSSProperties } from "react";
import { StatusBadge, type BadgeState } from "./StatusBadge";
import { IcCheck, IcClose } from "./icons";

type PipelineRowProps = {
  title: string;
  description: string;
  state: BadgeState;
  meta?: string;
};

export function PipelineRow({ title, description, state, meta }: PipelineRowProps) {
  const indicatorColor =
    state === "done"
      ? "var(--ok)"
      : state === "running"
      ? "var(--accent)"
      : state === "error"
      ? "var(--err)"
      : "var(--ink-4)";

  const indicatorBg =
    state === "done"
      ? "color-mix(in oklab, var(--ok) 18%, var(--paper-0))"
      : state === "running"
      ? "var(--accent-softer)"
      : "transparent";

  const rootStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "24px 1fr auto auto",
    alignItems: "center",
    gap: 16,
    padding: "14px 4px",
    borderBottom: "var(--hairline)",
    fontFamily: "var(--sans)",
    opacity: state === "idle" ? 0.55 : 1,
    transition: "opacity var(--dur) var(--ease)",
  };

  return (
    <div style={rootStyle}>
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: 999,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: indicatorColor,
          background: indicatorBg,
          border: state === "idle" ? "1px solid var(--paper-3)" : "none",
        }}
      >
        {state === "done" ? (
          <IcCheck size={12} />
        ) : state === "error" ? (
          <IcClose size={11} />
        ) : state === "running" ? (
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: "currentColor",
              animation: "brPulse 1.6s var(--ease-out) infinite",
            }}
          />
        ) : null}
      </div>

      <div>
        <div
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: "var(--ink-0)",
            fontFamily: "var(--sans)",
            letterSpacing: 0.1,
          }}
        >
          {title}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 2 }}>
          {description}
        </div>
      </div>

      {meta ? (
        <div
          data-pipeline-meta
          style={{
            fontSize: 11,
            color: state === "error" ? "var(--err)" : "var(--ink-3)",
            fontVariantNumeric: "tabular-nums",
            maxWidth: 260,
            textAlign: "right",
          }}
        >
          {meta}
        </div>
      ) : (
        <span />
      )}

      <StatusBadge state={state} />
    </div>
  );
}
```

- [ ] **Step 5.4: Run test to verify it passes**

From `frontend/`:

```bash
npm test -- PipelineRow
```

Expected: 4 passed.

- [ ] **Step 5.5: Commit**

```bash
git add frontend/src/components/PipelineRow.tsx frontend/src/components/PipelineRow.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): port PipelineRow component

Renders a single pipeline stage with title, description, optional meta
column (duration or sanitized error), a check/cross/pulse indicator,
and a StatusBadge. Opacity drops to 0.55 for idle rows to telegraph
queued stages, matching the design handoff.
EOF
)"
```

---

## Task 6: `UploadScreen` — wire upload + polling

**Files:**
- Modify: `frontend/src/screens/UploadScreen.tsx`
- Create: `frontend/src/screens/UploadScreen.test.tsx`

> **Generator:** invoke `frontend-design:frontend-design` for this task. The visual reference is `design-handoff/project/screens.jsx` lines 158–207; the hard-coded book metadata from the handoff must be removed and replaced with real upload + polling state.

- [ ] **Step 6.1: Write the failing test**

Create `frontend/src/screens/UploadScreen.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { UploadScreen } from "./UploadScreen";
import * as api from "../lib/api";
import type { PipelineState, StageName } from "../lib/api";

const BOOK_ID = "a_christmas_carol_a1b2c3d4";

function stagesWith(overrides: Partial<Record<StageName, api.PipelineStage>> = {}): PipelineState["stages"] {
  const base: PipelineState["stages"] = {
    parse_epub: { status: "pending" },
    run_booknlp: { status: "pending" },
    resolve_coref: { status: "pending" },
    discover_ontology: { status: "pending" },
    review_ontology: { status: "pending" },
    run_cognee_batches: { status: "pending" },
    validate: { status: "pending" },
  };
  return { ...base, ...overrides };
}

function mkState(over: Partial<PipelineState> = {}): PipelineState {
  return {
    book_id: BOOK_ID,
    status: "processing",
    stages: stagesWith(),
    current_batch: null,
    total_batches: null,
    ready_for_query: false,
    ...over,
  };
}

function makeEpub(name = "a-christmas-carol.epub"): File {
  return new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, {
    type: "application/epub+zip",
  });
}

function renderScreen() {
  return render(
    <MemoryRouter initialEntries={["/upload"]}>
      <UploadScreen />
    </MemoryRouter>
  );
}

describe("UploadScreen", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders the header, tagline, and idle Dropzone", () => {
    renderScreen();
    expect(screen.getByText(/add a book/i)).toBeInTheDocument();
    expect(screen.getByText(/upload an epub\./i)).toBeInTheDocument();
    expect(screen.getByText(/we'll parse the chapters/i)).toBeInTheDocument();
    expect(screen.getByText(/drop your epub/i)).toBeInTheDocument();
  });

  it("uploads the dropped file, then polls and renders the 7 stages", async () => {
    const uploadSpy = vi.spyOn(api, "uploadBook").mockResolvedValue({
      book_id: BOOK_ID,
      message: "Pipeline started",
    });
    const statusSpy = vi.spyOn(api, "fetchStatus").mockResolvedValue(
      mkState({
        stages: stagesWith({
          parse_epub: { status: "complete", duration_seconds: 0.4 },
          run_booknlp: { status: "running" },
        }),
      })
    );

    renderScreen();

    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub()] } });
    });

    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));

    // Filename and book_id appear
    await waitFor(() => {
      expect(screen.getAllByText("a-christmas-carol.epub").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(BOOK_ID)).toBeInTheDocument();
    });

    // Let polling fire once
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(statusSpy).toHaveBeenCalled();
    expect(screen.getByText("Parse EPUB")).toBeInTheDocument();
    expect(screen.getByText("Run BookNLP")).toBeInTheDocument();
    expect(screen.getByText("Resolve coref")).toBeInTheDocument();
    expect(screen.getByText("Discover ontology")).toBeInTheDocument();
    expect(screen.getByText("Review ontology")).toBeInTheDocument();
    expect(screen.getByText("Cognee batches")).toBeInTheDocument();
    expect(screen.getByText("Validate")).toBeInTheDocument();
  });

  it("stops polling and renders 'Back to Library' when ready_for_query becomes true", async () => {
    vi.spyOn(api, "uploadBook").mockResolvedValue({
      book_id: BOOK_ID,
      message: "Pipeline started",
    });
    const statusSpy = vi
      .spyOn(api, "fetchStatus")
      .mockResolvedValueOnce(
        mkState({
          stages: stagesWith({ parse_epub: { status: "running" } }),
        })
      )
      .mockResolvedValueOnce(
        mkState({
          status: "complete",
          ready_for_query: true,
          stages: stagesWith({
            parse_epub: { status: "complete", duration_seconds: 0.4 },
            run_booknlp: { status: "complete", duration_seconds: 38 },
            resolve_coref: { status: "complete", duration_seconds: 12 },
            discover_ontology: { status: "complete" },
            review_ontology: { status: "complete" },
            run_cognee_batches: { status: "complete" },
            validate: { status: "complete" },
          }),
        })
      );

    renderScreen();
    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub()] } });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /back to library/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /back to library/i })).toHaveAttribute(
      "href",
      "/"
    );

    const callsAtReady = statusSpy.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(statusSpy.mock.calls.length).toBe(callsAtReady);
  });

  it("stops polling and shows an error banner when any stage fails", async () => {
    vi.spyOn(api, "uploadBook").mockResolvedValue({
      book_id: BOOK_ID,
      message: "Pipeline started",
    });
    const statusSpy = vi.spyOn(api, "fetchStatus").mockResolvedValue(
      mkState({
        status: "failed",
        stages: stagesWith({
          parse_epub: { status: "complete", duration_seconds: 0.4 },
          run_booknlp: { status: "failed", error: "OOM killed" },
        }),
      })
    );

    renderScreen();
    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub()] } });
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/pipeline failed/i);
    });
    expect(screen.getByText(/oom killed/i)).toBeInTheDocument();

    const callsAtFail = statusSpy.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(statusSpy.mock.calls.length).toBe(callsAtFail);
  });

  it("shows the mapped error in the Dropzone when uploadBook rejects", async () => {
    vi.spyOn(api, "uploadBook").mockRejectedValue(
      new api.UploadError(400, "Only .epub files are accepted")
    );

    renderScreen();
    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub("nope.txt")] } });
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /only \.epub files are accepted/i
      );
    });
  });
});
```

- [ ] **Step 6.2: Run test to verify it fails**

From `frontend/`:

```bash
npm test -- UploadScreen
```

Expected: numerous failures — the `UploadScreen` stub from Task 1 lacks the dropzone, pipeline panel, and polling logic.

- [ ] **Step 6.3: Implement the real `UploadScreen.tsx`**

Replace the entire content of `frontend/src/screens/UploadScreen.tsx` with:

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { Dropzone, type DropzoneState } from "../components/Dropzone";
import { PipelineRow } from "../components/PipelineRow";
import { Button } from "../components/Button";
import {
  uploadBook,
  fetchStatus,
  UploadError,
  type PipelineStage,
  type PipelineState,
  type StageName,
} from "../lib/api";
import type { BadgeState } from "../components/StatusBadge";

type StageDisplay = { key: StageName; label: string; desc: string };

const STAGE_DISPLAY: StageDisplay[] = [
  { key: "parse_epub",          label: "Parse EPUB",        desc: "Split into chapter-segmented text" },
  { key: "run_booknlp",         label: "Run BookNLP",       desc: "Entities, coreference, quotes" },
  { key: "resolve_coref",       label: "Resolve coref",     desc: "Parenthetical insertion pass" },
  { key: "discover_ontology",   label: "Discover ontology", desc: "BERTopic + TF-IDF → OWL" },
  { key: "review_ontology",     label: "Review ontology",   desc: "Optional refinement" },
  { key: "run_cognee_batches",  label: "Cognee batches",    desc: "Claude extracts structured entities" },
  { key: "validate",            label: "Validate",          desc: "Spoiler-safety + spot checks" },
];

type Phase =
  | { kind: "idle" }
  | { kind: "uploading"; filename: string }
  | { kind: "error"; filename?: string; message: string }
  | { kind: "tracking"; filename: string; book_id: string; state: PipelineState | null };

function badgeFor(stage: PipelineStage | undefined): BadgeState {
  if (!stage) return "idle";
  switch (stage.status) {
    case "pending":  return "idle";
    case "running":  return "running";
    case "complete": return "done";
    case "failed":   return "error";
  }
}

function metaFor(stage: PipelineStage | undefined): string | undefined {
  if (!stage) return undefined;
  if (stage.status === "complete" && typeof stage.duration_seconds === "number") {
    return formatSeconds(stage.duration_seconds);
  }
  if (stage.status === "failed") {
    return stage.error ?? "Failed";
  }
  return undefined;
}

function formatSeconds(s: number): string {
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s - m * 60);
  return `${m}m ${rem}s`;
}

function dropzoneState(phase: Phase): DropzoneState {
  switch (phase.kind) {
    case "idle":      return "idle";
    case "uploading": return "uploading";
    case "error":     return "error";
    case "tracking":  return "done";
  }
}

function firstFailedStage(state: PipelineState | null): { name: StageName; stage: PipelineStage } | null {
  if (!state) return null;
  for (const d of STAGE_DISPLAY) {
    const s = state.stages[d.key];
    if (s && s.status === "failed") return { name: d.key, stage: s };
  }
  return null;
}

export function UploadScreen() {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const stopRef = useRef(false);

  const handleFile = useCallback(async (file: File) => {
    stopRef.current = false;
    setPhase({ kind: "uploading", filename: file.name });
    try {
      const resp = await uploadBook(file);
      setPhase({
        kind: "tracking",
        filename: file.name,
        book_id: resp.book_id,
        state: null,
      });
    } catch (err) {
      const message =
        err instanceof UploadError
          ? err.message
          : err instanceof Error
          ? err.message
          : "Upload failed";
      setPhase({ kind: "error", filename: file.name, message });
    }
  }, []);

  // Polling effect
  useEffect(() => {
    if (phase.kind !== "tracking") return;
    const book_id = phase.book_id;
    stopRef.current = false;

    let cancelled = false;

    const tick = async () => {
      try {
        const next = await fetchStatus(book_id);
        if (cancelled) return;
        setPhase((prev) => {
          if (prev.kind !== "tracking" || prev.book_id !== book_id) return prev;
          return { ...prev, state: next };
        });
        if (next.ready_for_query || Object.values(next.stages).some((s) => s.status === "failed")) {
          stopRef.current = true;
        }
      } catch {
        // transient poll failure — keep ticking; a definitive error will surface
        // as a failed stage or eventual ready_for_query.
      }
    };

    void tick();
    const id = window.setInterval(() => {
      if (stopRef.current) {
        window.clearInterval(id);
        return;
      }
      void tick();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [phase.kind === "tracking" ? phase.book_id : null]);

  const trackingState = phase.kind === "tracking" ? phase.state : null;
  const failed = firstFailedStage(trackingState);
  const ready = trackingState?.ready_for_query === true;

  return (
    <div className="br" style={{ minHeight: "100vh", background: "var(--paper-0)" }}>
      <NavBar />
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "64px 32px 80px" }}>
        <div
          style={{
            fontFamily: "var(--sans)",
            fontSize: 11,
            letterSpacing: 1.6,
            textTransform: "uppercase",
            color: "var(--ink-3)",
            marginBottom: 10,
          }}
        >
          Add a book
        </div>
        <h1
          style={{
            margin: "0 0 8px",
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: 38,
            letterSpacing: -0.8,
            color: "var(--ink-0)",
          }}
        >
          Upload an EPUB.
        </h1>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 17,
            lineHeight: 1.55,
            color: "var(--ink-2)",
            maxWidth: 520,
            marginBottom: 36,
          }}
        >
          We'll parse the chapters, learn the characters, and build a spoiler-aware index —
          so you can ask anything, and we'll answer only from what you've already read.
        </div>

        <Dropzone
          state={dropzoneState(phase)}
          filename={
            phase.kind === "uploading" || phase.kind === "tracking" || phase.kind === "error"
              ? phase.filename
              : undefined
          }
          errorMessage={phase.kind === "error" ? phase.message : undefined}
          onFile={handleFile}
        />

        {phase.kind === "tracking" && (
          <>
            {failed && (
              <div
                role="alert"
                style={{
                  marginTop: 24,
                  padding: "12px 16px",
                  border: "1px solid var(--err)",
                  background: "color-mix(in oklab, var(--err) 8%, var(--paper-0))",
                  borderRadius: "var(--r-md)",
                  color: "var(--err)",
                  fontFamily: "var(--sans)",
                  fontSize: 13,
                }}
              >
                Pipeline failed at <strong>{failed.name}</strong>
                {failed.stage.error ? `: ${failed.stage.error}` : "."}
              </div>
            )}

            <div
              style={{
                marginTop: failed ? 16 : 40,
                padding: "24px 24px 8px",
                background: "var(--paper-00)",
                border: "var(--hairline)",
                borderRadius: "var(--r-lg)",
              }}
            >
              <div style={{ marginBottom: 16 }}>
                <div
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: 13,
                    color: "var(--ink-2)",
                    letterSpacing: 0.2,
                  }}
                >
                  {phase.book_id}
                </div>
              </div>

              {STAGE_DISPLAY.map((d) => (
                <PipelineRow
                  key={d.key}
                  title={d.label}
                  description={d.desc}
                  state={badgeFor(trackingState?.stages[d.key])}
                  meta={metaFor(trackingState?.stages[d.key])}
                />
              ))}
            </div>

            {ready && (
              <div
                style={{
                  marginTop: 20,
                  display: "flex",
                  justifyContent: "flex-end",
                }}
              >
                <Link to="/" style={{ textDecoration: "none" }}>
                  <Button variant="primary">Back to Library</Button>
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6.4: Run test to verify it passes**

From `frontend/`:

```bash
npm test -- UploadScreen
```

Expected: 5 passed.

- [ ] **Step 6.5: Run the full frontend suite**

From `frontend/`:

```bash
npm test
```

Expected: all tests pass across the board (NavBar 5, App 2, LibraryScreen ≥4, api 10, mood 4, BookCover 2, ProgressPill 3, BookCard 2, Dropzone 8, StatusBadge 6, PipelineRow 4, UploadScreen 5).

- [ ] **Step 6.6: Commit**

```bash
git add frontend/src/screens/UploadScreen.tsx frontend/src/screens/UploadScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): wire UploadScreen upload + 2s status polling

UploadScreen now drives the full state machine — drop or browse an
EPUB → uploadBook → poll fetchStatus on a 2 s setInterval → render the
7-stage pipeline panel with a monospace book_id subtitle. Polling
halts on ready_for_query or any stage failure. On success a
'Back to Library' link appears; on failure an inline alert shows the
sanitized error above the pipeline panel. Upload errors (400/413/429
/other) appear in-place in the Dropzone without crashing the screen.
EOF
)"
```

---

## Task 7: Playwright E2E scaffolding

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/tsconfig.json`
- Modify: `frontend/.gitignore`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/upload.spec.ts`

- [ ] **Step 7.1: Install `@playwright/test` and add the `test:e2e` script**

From `frontend/`:

```bash
npm install --save-dev @playwright/test@^1.47.0
npx playwright install chromium
```

Expected: `package.json` gains `"@playwright/test": "^1.47.x"`; the Chromium browser downloads.

Then edit `frontend/package.json` to add a new `test:e2e` script. The `scripts` block should read exactly:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "test": "vitest run",
  "test:watch": "vitest",
  "test:e2e": "playwright test"
}
```

- [ ] **Step 7.2: Exclude Playwright artifacts from the Vitest tsconfig and from git**

Edit `frontend/tsconfig.json` and change the `"include"` array to exclude the `e2e/` directory (Playwright files use a different test runner and would fail Vitest's type-check). Replace the `"include"` line with:

```json
"include": ["src", "vitest.setup.ts"],
"exclude": ["e2e"],
```

Edit `frontend/.gitignore` and append:

```
test-results
playwright-report
.playwright
```

- [ ] **Step 7.3: Create `frontend/playwright.config.ts`**

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
```

- [ ] **Step 7.4: Write the failing E2E spec**

Create `frontend/e2e/upload.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import type { Route } from "@playwright/test";

const BOOK_ID = "a_christmas_carol_a1b2c3d4";

const STAGE_KEYS = [
  "parse_epub",
  "run_booknlp",
  "resolve_coref",
  "discover_ontology",
  "review_ontology",
  "run_cognee_batches",
  "validate",
] as const;

function pendingStages() {
  return Object.fromEntries(STAGE_KEYS.map((k) => [k, { status: "pending" }]));
}

async function mockBooksEmpty(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

async function mockUploadSuccess(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/books/upload", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ book_id: BOOK_ID, message: "Pipeline started" }),
    });
  });
}

async function mockUpload400(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/books/upload", async (route: Route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Only .epub files are accepted" }),
    });
  });
}

async function mockStatusRunning(page: import("@playwright/test").Page) {
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/status`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          status: "processing",
          stages: {
            ...pendingStages(),
            parse_epub: { status: "complete", duration_seconds: 0.4 },
            run_booknlp: { status: "running" },
          },
          current_batch: null,
          total_batches: null,
          ready_for_query: false,
        }),
      });
    }
  );
}

test.describe("upload flow (hermetic)", () => {
  test("navigates from Library → Upload → Library without reloading", async ({ page }) => {
    await mockBooksEmpty(page);
    await page.goto("/");
    await expect(page.getByText(/your shelf/i)).toBeVisible();

    await page.getByRole("link", { name: "Upload" }).click();
    await expect(page).toHaveURL(/\/upload$/);
    await expect(page.getByRole("heading", { name: /upload an epub\./i })).toBeVisible();

    await page.getByRole("link", { name: "Library" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByText(/your shelf/i)).toBeVisible();
  });

  test("Upload screen renders the idle Dropzone", async ({ page }) => {
    await mockBooksEmpty(page);
    await page.goto("/upload");
    await expect(page.getByRole("heading", { name: /upload an epub\./i })).toBeVisible();
    await expect(page.getByText(/drop your epub/i)).toBeVisible();
    await expect(page.getByText(/browse files/i)).toBeVisible();
  });

  test("rejecting a non-epub shows the 400 error in the Dropzone", async ({ page }) => {
    await mockBooksEmpty(page);
    await mockUpload400(page);
    await page.goto("/upload");

    // Provide a file via the hidden input (bypassing the native drag)
    await page.setInputFiles('[data-testid="dropzone-input"]', {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("hello"),
    });

    const alert = page.getByRole("alert");
    await expect(alert).toContainText(/only \.epub files are accepted/i);
  });

  test("a successful upload renders the 7 pipeline stages", async ({ page }) => {
    await mockBooksEmpty(page);
    await mockUploadSuccess(page);
    await mockStatusRunning(page);
    await page.goto("/upload");

    await page.setInputFiles('[data-testid="dropzone-input"]', {
      name: "a-christmas-carol.epub",
      mimeType: "application/epub+zip",
      buffer: Buffer.from([0x50, 0x4b, 0x03, 0x04]),
    });

    await expect(page.getByText(BOOK_ID)).toBeVisible();
    await expect(page.getByText("Parse EPUB")).toBeVisible();
    await expect(page.getByText("Run BookNLP")).toBeVisible();
    await expect(page.getByText("Resolve coref")).toBeVisible();
    await expect(page.getByText("Discover ontology")).toBeVisible();
    await expect(page.getByText("Review ontology")).toBeVisible();
    await expect(page.getByText("Cognee batches")).toBeVisible();
    await expect(page.getByText("Validate")).toBeVisible();
  });
});
```

- [ ] **Step 7.5: Run the E2E suite**

From `frontend/`:

```bash
npm run test:e2e
```

Expected: 4 passed in chromium. Playwright auto-starts `npm run dev` via `webServer` and tears it down after the suite.

- [ ] **Step 7.6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/.gitignore frontend/playwright.config.ts frontend/e2e/upload.spec.ts
git commit -m "$(cat <<'EOF'
test(frontend): add hermetic Playwright E2E suite for upload flow

Introduces @playwright/test with a webServer config that auto-runs
npm run dev. Specs use page.route() to intercept /books/upload and
/books/{id}/status with fixture responses so the suite runs without a
live backend. Covers AC 1 (Library ↔ Upload navigation), AC 2 (idle
Dropzone), AC 4 (7 pipeline stages rendered), and AC 9 (the 400 error
copy 'Only .epub files are accepted'). Excludes the e2e/ directory
from the Vitest tsconfig and the Playwright artifacts from git.
EOF
)"
```

---

## Task 8: Library refetch on route entry

**Files:**
- Modify: `frontend/src/screens/LibraryScreen.tsx`
- Modify: `frontend/src/screens/LibraryScreen.test.tsx`

- [ ] **Step 8.1: Write the failing refetch test**

Append a new test to `frontend/src/screens/LibraryScreen.test.tsx`. Replace the final `});` closing the `describe` block with:

```tsx
  it("re-fetches /books when the route is re-entered (pathname changes)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { rerender } = render(
      <MemoryRouter initialEntries={["/upload", "/"]} initialIndex={0}>
        <LibraryScreen />
      </MemoryRouter>
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    rerender(
      <MemoryRouter initialEntries={["/"]}>
        <LibraryScreen />
      </MemoryRouter>
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
```

Note: the `rerender` with a different `<MemoryRouter>` forces React to remount, which is fine because production navigation (via `<Link>`) also changes `location.pathname`; we will depend on `useLocation().pathname` in the implementation so the real app re-fires the effect on navigation.

- [ ] **Step 8.2: Run the test and confirm it fails**

From `frontend/`:

```bash
npm test -- LibraryScreen
```

Expected: the new case fails because the current effect dependency list is `[]` and never re-runs. (The four previous tests still pass.)

- [ ] **Step 8.3: Update `LibraryScreen.tsx` to depend on `location.pathname`**

Edit `frontend/src/screens/LibraryScreen.tsx`. Add `useLocation` to the imports and change the `useEffect` dependency list. The top of the file should become:

```tsx
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { BookCard } from "../components/BookCard";
import { TextInput } from "../components/TextInput";
import { Button } from "../components/Button";
import { Row } from "../components/layout";
import { IcPlus, IcSearch } from "../components/icons";
import { fetchBooks, type Book } from "../lib/api";
```

Then replace the `useEffect(...)` block with:

```tsx
  const { pathname } = useLocation();

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
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
  }, [pathname]);
```

- [ ] **Step 8.4: Run the test and confirm it passes**

From `frontend/`:

```bash
npm test -- LibraryScreen
```

Expected: all 5 LibraryScreen tests pass.

- [ ] **Step 8.5: Commit**

```bash
git add frontend/src/screens/LibraryScreen.tsx frontend/src/screens/LibraryScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): refetch GET /books when the Library route becomes active

Keys the fetch effect to useLocation().pathname so navigating from
/upload back to / triggers a fresh fetch and the newly ingested book
appears without a page reload.
EOF
)"
```

---

## Task 9: Wire-up and final verification

**Files:** no code changes. This task runs the full verification matrix and commits any build artifacts if needed.

- [ ] **Step 9.1: Run the frontend test suite**

From `frontend/`:

```bash
npm test
```

Expected: all tests pass. The final report should include NavBar (5), App (2), LibraryScreen (5), api (10), mood (4), BookCover (2), ProgressPill (3), BookCard (2), Dropzone (8), StatusBadge (6), PipelineRow (4), UploadScreen (5). Total: ≥56 unit tests.

- [ ] **Step 9.2: Run the TypeScript build**

From `frontend/`:

```bash
npm run build
```

Expected: `tsc -b` reports 0 errors and `vite build` produces a fresh `dist/`. No new files are committed from this step (`dist/` is already in `.gitignore`).

- [ ] **Step 9.3: Run the Playwright E2E suite**

From `frontend/`:

```bash
npm run test:e2e
```

Expected: 4 passed in chromium.

- [ ] **Step 9.4: Run the backend test suite**

From the repo root:

```bash
/Users/jeffreykrapf/anaconda3/bin/pytest tests/ -v --tb=short
```

Expected: all existing tests still pass. No backend files changed in slice 2.

- [ ] **Step 9.5: Manual smoke against the live backend**

Terminal 1 (repo root):

```bash
python main.py
```

Expected: uvicorn starts on `127.0.0.1:8000`.

Terminal 2 (`frontend/`):

```bash
npm run dev
```

Expected: Vite reports `Local: http://localhost:5173/`.

Open `http://localhost:5173/` in a browser and verify:
- Library screen renders with the shelf header.
- Clicking **Upload** navigates to `/upload` with no full-page reload. Clicking **Library** returns. Clicking **Reading** does nothing and logs no console errors.
- On `/upload`, the page shows "Add a book" / "Upload an EPUB." / tagline and an idle Dropzone.
- Dragging a valid `.epub` file highlights the dropzone (hover state), dropping it POSTs to `/books/upload`, and the 7 stages appear with the real `book_id` as a monospace subtitle.
- Stages update every ~2 s; once `ready_for_query` flips true the "Back to Library" button appears.
- Clicking it returns to `/` and the new book appears in the grid without a refresh.
- Dropping a `.txt` file shows "Only .epub files are accepted" inline; the screen does not crash.

- [ ] **Step 9.6: Final commit (if any untracked artifacts remain)**

```bash
git status
```

Expected: clean working tree. If any stray files from Playwright install appear outside `.gitignore`, either add them to `.gitignore` and commit, or remove them — do not commit generated artifacts.

---

## Self-Review Checklist

**Spec coverage — every acceptance criterion maps to at least one task:**

| AC | Covered by |
|----|------------|
| 1. Nav tabs route without reload; Reading inert | Task 1 (router + NavBar), Task 7 E2E test "navigates…", Task 9 Step 9.5 |
| 2. Upload screen renders header, idle Dropzone, pipeline area reserved | Task 6 Step 6.1 test "renders the header", Task 7 spec "idle Dropzone" |
| 3. Drag/drop + file input → `multipart/form-data` POST + uploading state | Task 2 `uploadBook` test, Task 3 drop/change tests, Task 6 "uploads the dropped file…" |
| 4. On success, Dropzone `done` + pipeline panel with book_id + 7 rows | Task 6 Step 6.1 tests "uploads the dropped file…" and "a successful upload renders the 7 pipeline stages" (Task 7 E2E) |
| 5. Polling every 2000 ms updates row badges | Task 6 test using `vi.useFakeTimers()` + `advanceTimersByTimeAsync(2000)` |
| 6. Polling halts on `ready_for_query` OR any `status: "failed"` | Task 6 tests "stops polling and renders 'Back to Library'" and "stops polling and shows an error banner" |
| 7. "Back to Library" navigates to `/` and Library re-fetches | Task 6 "Back to Library" test, Task 8 refetch test |
| 8. Failed stage → error row + sanitized message + inline banner + polling halt | Task 5 PipelineRow "shows meta when state is 'error'", Task 6 "stops polling and shows an error banner" |
| 9. Upload errors (400/413/429/other) show exact PRD copy in-place; no crash | Task 2 api error-mapping tests (4 cases), Task 6 "shows the mapped error in the Dropzone", Task 7 E2E 400 spec |
| 10. `npm test` and `pytest -v` both pass; no regressions; no new backend endpoints | Task 9 Steps 9.1 and 9.4 |

**Placeholder scan:** no "TODO", "TBD", or "fill in" strings. Every function called in a test has a concrete implementation in the same or an earlier task.

**Type consistency:** `PipelineState`, `PipelineStage`, `StageName`, `UploadResponse`, and `UploadError` are defined in Task 2 (`lib/api.ts`) and consumed verbatim in Tasks 6 and 7. `BadgeState` is defined in Task 4 (`StatusBadge.tsx`) and consumed by Task 5 (`PipelineRow`) and Task 6 (`UploadScreen`). `DropzoneState` is defined in Task 3 and consumed in Task 6. The `StageName` union values match the backend `Pipeline Stages (in order)` list in `CLAUDE.md` and the orchestrator's stage keys exactly: `parse_epub`, `run_booknlp`, `resolve_coref`, `discover_ontology`, `review_ontology`, `run_cognee_batches`, `validate`.

**Scope guards:** no Reading screen work, no chat components, no progress endpoint, no Cancel/Notify-me buttons, no optimistic library rendering, no dark-mode wiring, no backend changes. The `BookSummary`/`Book` contract from slice 1 is unchanged.

---
