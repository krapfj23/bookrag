# Slice 1 — scaffold-library PRD

**Date:** 2026-04-21
**Parent spec:** ../specs/2026-04-21-frontend-integration-agent-pipeline-design.md

## Goal

Stand up a Vite + React + TypeScript frontend at `frontend/`, port the design tokens, and render a Library screen that lists every processed book returned by a new `GET /books` endpoint.

## User stories

- As a reader, I can visit `http://localhost:5173` and land on the Library screen so that I see my shelf of books.
- As a reader, I can see the already-ingested *A Christmas Carol* in the Library so that I know the pipeline output is actually wired to the UI.
- As a reader, I can tell at a glance which books are available so that I know which ones I could open to read.

## Acceptance criteria

1. Running `npm run dev` (or equivalent) inside `frontend/` starts the Vite dev server on port 5173 without console errors.
2. Navigating to `http://localhost:5173/` renders the Library screen: top NavBar with the *Book*/*rag* wordmark, "Your shelf" header, and a grid of book cards.
3. The Library fetches `GET http://localhost:8000/books` on mount and renders one `BookCard` per returned book. A loading state is visible before the response arrives; a readable error state is visible if the fetch fails.
4. *A Christmas Carol* (book_id `christmas_carol_e6ddcd76`) appears as a card with: a generated two-tone cover (via `BookCover`), a title, a progress pill or bar, and chapter progress text (e.g. "1 of 3").
5. Only books whose `pipeline_state.json` has `ready_for_query: true` appear in the Library — in-progress or failed ingestions are excluded.
6. The design tokens from `design-handoff/project/tokens.css` are loaded globally and the page visibly uses the linen paper palette and Lora/IBM Plex Sans typography.
7. The backend endpoint `GET /books` is callable directly (e.g. `curl http://localhost:8000/books`) and returns a JSON array matching the `Book` contract below. Each entry comes from scanning `data/processed/*/pipeline_state.json`.
8. `pytest -v` passes with at least one test covering `GET /books` (empty case and a case with one ready book on disk).
9. No existing backend tests regress.
10. The NavBar shows *Library* as the active item; the *Reading* and *Upload* tabs are visible but do nothing (no routing yet) and clicking them does not throw.

## UI scope

**In scope — port to TSX under `frontend/src/components/`:**

- `tokens.css` (copy verbatim into `frontend/src/styles/tokens.css`, imported once at app root)
- From `components.jsx`: `Stack`, `Row`, `Divider`, `Wordmark`, `NavBar`, `IconBtn`, `Button`, `ProgressPill`, `BookCover`, `BookCard`
- From `icons.jsx`: at minimum `IcSearch`, `IcPlus`, `IcSun`, `IcMoon`, `IcSettings` (plus the base `Icon` primitive)
- From `components2.jsx`: `TextInput` (only because the Library header uses it for the search field)
- From `screens.jsx`: `LibraryScreen` — ported to a route/page component that fetches real data instead of using the hardcoded `BOOKS` array

**Out of scope — do not port in this slice:**

- `ReadingScreen`, `UploadScreen`, and every component only used by them (`ChapterRow`, `Highlight`, `LockState`, `UserBubble`, `AssistantBubble`, `ChatInput`, `ProgressiveBlur`, `Dropzone`, `StatusBadge`, `PipelineRow`, all icons not listed above).
- Dark-mode toggle wiring, accent switcher, density switcher. The theme toggle button may be visually present but can be a no-op.
- Router. A single page at `/` is sufficient. If a router is added, only the Library route is implemented.
- Search input interactivity — render it but the `onChange` handler can be a no-op.

## Backend scope

**Existing endpoints (unchanged):**

- `POST /books/upload`
- `GET /books/{book_id}/status`
- `GET /books/{book_id}/validation`
- `POST /books/{book_id}/progress`
- `POST /books/{book_id}/query`
- `GET /books/{book_id}/graph`, `GET /books/{book_id}/graph/data`
- `GET /health`

**New endpoint — must be added to `main.py`:**

- **Path:** `GET /books`
- **Method:** `GET`
- **Request:** no parameters, no body
- **Response:** JSON array of `Book` objects (see Data contracts)
- **Data source:** iterate subdirectories of `config.processed_dir` (`data/processed/*`); for each one, load `pipeline_state.json` (via `models.pipeline_state.load_state`); include the book only if `ready_for_query` is `true`. Chapter count is derived by counting files matching `raw/chapters/chapter_*.txt` in the book's processed dir. Current chapter is read from `reading_progress.json` if present, otherwise `1`.
- **Errors:** missing or corrupt `pipeline_state.json` for a directory → skip that directory and log a warning; never 500 the whole endpoint. Empty response `[]` is valid.

No other backend changes. CORS config already allows `http://localhost:5173`.

## Data contracts

```ts
// Response of GET /books — the full payload the Library consumes
interface Book {
  book_id: string;          // e.g. "christmas_carol_e6ddcd76"
  title: string;            // display title; for now, prettified from book_id (see Open questions)
  total_chapters: number;   // count of raw/chapters/chapter_*.txt files
  current_chapter: number;  // from reading_progress.json, defaults to 1
  ready_for_query: boolean; // always true in this response (filter applied server-side)
}

// The BookCard component accepts this shape directly; missing design-only
// fields (author, mood, lastRead) are optional and may be omitted until
// later slices expose them from the backend.
interface BookCardProps {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  author?: string;   // not available this slice
  mood?: string;     // not available this slice
  lastRead?: string; // not available this slice
}
```

## Out of scope

- Author metadata. The EPUB parser does not currently capture it; adding that is a separate change and not required to prove the loop.
- Cover `mood` selection. Pass a stable default (e.g. `"sage"`) or derive deterministically from `book_id` hash; do not add it to the API.
- Opening a book. Clicking a `BookCard` has no effect in this slice.
- Uploading a new book from the Library ("Add book" button is visible but a no-op).
- Pagination or filtering of the library list.
- Mobile layouts and responsive tweaks.

## Open questions

- **Title rendering:** the backend has no real title for *A Christmas Carol*; the directory is `christmas_carol_e6ddcd76`. For this slice, should the frontend prettify the `book_id` (strip the hex suffix, replace underscores with spaces, Title Case) or should the backend do it? Proposed default: **backend** derives `title` by stripping the trailing `_<hex>` suffix and title-casing the rest, so the frontend stays dumb.
