# Slice 2 — upload-pipeline-status PRD

**Date:** 2026-04-21
**Parent spec:** ../specs/2026-04-21-frontend-integration-agent-pipeline-design.md

## Goal

Ship the Upload screen end-to-end: a drag-and-drop EPUB dropzone that POSTs to `/books/upload`, polls `GET /books/{id}/status` every 2 seconds, and renders the 7 pipeline stages with real status badges until the book lands in the Library.

## User stories

- As a reader, I can click the *Upload* tab from the NavBar so that I navigate to the upload screen without reloading.
- As a reader, I can drop or browse for an EPUB so that the ingestion pipeline starts without any extra configuration.
- As a reader, I can watch each of the 7 pipeline stages light up in real time so that I know my book is being processed.
- As a reader, I can see a clear error message if a stage fails so that I know the run is stuck and not just slow.
- As a reader, once the pipeline completes I can navigate back to *Library* and see my newly added book without reloading the page.

## Acceptance criteria

1. Clicking the *Upload* tab in the NavBar navigates to `/upload` and renders the Upload screen; clicking *Library* returns to `/` and re-renders the Library. Neither reloads the page. The *Reading* tab remains inert (no route wired this slice) and clicking it does not throw.
2. The Upload screen renders: page header ("Add a book" eyebrow + "Upload an EPUB." title + tagline), the `Dropzone` component in its `idle` state, and an empty area below reserved for the pipeline panel.
3. Dragging a valid `.epub` onto the `Dropzone` updates its visual state to `hover`; dropping it, OR selecting a file via the hidden file input, POSTs the file as `multipart/form-data` to `http://localhost:8000/books/upload` and the UI transitions to `uploading`.
4. On a successful upload response (`{ book_id, message }`), the Dropzone shows `done` with the filename, and a pipeline panel appears below showing the book's `book_id` (as a monospace subtitle) and 7 `PipelineRow`s labelled in this order: Parse EPUB, Run BookNLP, Resolve coref, Discover ontology, Review ontology, Cognee batches, Validate.
5. Immediately after the upload resolves, the frontend begins polling `GET http://localhost:8000/books/{book_id}/status` every 2000 ms. Each poll updates every `PipelineRow`'s state badge from the corresponding entry in `stages` using the mapping in Data contracts.
6. Polling stops as soon as the response has `ready_for_query: true` OR any stage has `status: "failed"`. No further network calls to `/status` are made after that.
7. When `ready_for_query` becomes true, a "Back to Library" action is rendered; clicking it navigates to `/` and the Library re-fetches `GET /books` so the new book is visible in the grid. Refreshing the page is not required.
8. If any stage returns `status: "failed"`, the corresponding `PipelineRow` renders with `state="error"` and shows the sanitized `error` string as the row's `meta` or as a secondary line; polling halts; and an inline error banner is rendered above the pipeline panel. Other stages retain their last-known state.
9. Upload errors surface in-place without crashing the screen: HTTP 400 (non-EPUB) shows "Only .epub files are accepted"; 413 shows "File too large (max 500 MB)"; 429 shows "Too many pipelines running, try again later"; any other non-2xx shows the backend detail text. The Dropzone enters `error` state displaying the mapped message (an explicit error visual tied to the user's action) and the user can drop or browse again to retry.
10. `npm run test` and `pytest -v` both pass. No existing tests regress. No new backend endpoints are introduced.

## UI scope

**NEW in this slice — port from `design-handoff/project/*.jsx` to `frontend/src/components/` and `frontend/src/screens/`:**

- `components2.jsx` → `Dropzone` (drag/drop + file-input trigger; accepts real handler props, not just visual state)
- `components2.jsx` → `StatusBadge` (all 5 visual states, plus the `brPulse` keyframe added once to `tokens.css` or a small global stylesheet)
- `components2.jsx` → `PipelineRow`
- `icons.jsx` → `IcUpload`, `IcCheck`, `IcClose` (and `IcClock` if the "Notify me" affordance ships; otherwise skip)
- `screens.jsx` → `UploadScreen` (ported; hard-coded book metadata removed; wired to real upload + polling)

**REUSED from slice 1 — import as-is:**

- `NavBar`, `Wordmark`, `Row`, `Stack`, `Divider`, `Button`, `IconBtn`
- `icons.tsx` primitives already present (`IcSun`, `IcMoon`, `IcSettings`, `IcPlus`, `IcSearch`)
- `LibraryScreen` (no changes except re-triggering `fetchBooks` on route entry)
- `lib/api.ts` — extend with `uploadBook(file)` and `fetchStatus(book_id)`; keep existing `fetchBooks` exported

**OUT OF SCOPE — do not port:**

- Reading screen, ChapterRow, Highlight, LockState, UserBubble, AssistantBubble, ChatInput, ProgressiveBlur
- Dark-mode wiring, density/accent switchers
- "Cancel" and "Notify me when done" buttons in the mocked `UploadScreen` — visual stubs only, or omit entirely
- Optimistic/skeleton Library entries; the book appears only after `ready_for_query: true` via a real `GET /books` refetch

**Router decision:**

- Add `react-router-dom@6` to `frontend/package.json`.
- `main.tsx` wraps `<App />` in `<BrowserRouter>`.
- `App.tsx` declares two routes: `/` → `<LibraryScreen />`, `/upload` → `<UploadScreen />`. No route for Reading this slice.
- `NavBar` item links become `<Link>`s driven by an `active` prop derived from `useLocation()`. The *Reading* item stays rendered but is a no-op anchor.

## Backend scope

No new endpoints. This slice consumes:

- `POST /books/upload` — `multipart/form-data` with field `file`. Returns `UploadResponse { book_id, message }` synchronously; the pipeline runs in the background. Quirks: 400 if not `.epub` or bad ZIP magic; 413 if > 500 MB; 429 if 5+ pipelines are already running.
- `GET /books/{book_id}/status` — returns sanitized `PipelineState` JSON. Sanitization strips stack traces from `stages[*].error` down to the last line. Returns 404 if the orchestrator has no state for that `book_id`.
- `GET /books` — already shipped in slice 1; called once more after pipeline completion so the new book appears in the Library.

CORS already allows `http://localhost:5173`. No config changes.

## Data contracts

```ts
// POST /books/upload response
interface UploadResponse {
  book_id: string;   // e.g. "my_book_a1b2c3d4"
  message: string;   // "Pipeline started"
}

// GET /books/{book_id}/status response — mirror of models.pipeline_state.PipelineState.to_dict(sanitize=True)
interface PipelineStage {
  status: "pending" | "running" | "complete" | "failed";
  duration_seconds?: number;
  error?: string;              // sanitized — last line only
}

interface PipelineState {
  book_id: string;
  status: "pending" | "processing" | "complete" | "failed";
  stages: Record<StageName, PipelineStage>;
  current_batch: number | null;
  total_batches: number | null;
  ready_for_query: boolean;
}

type StageName =
  | "parse_epub"
  | "run_booknlp"
  | "resolve_coref"
  | "discover_ontology"
  | "review_ontology"
  | "run_cognee_batches"
  | "validate";

// Frontend-only badge state derived from PipelineStage.status
// mapping: pending → "idle", running → "running", complete → "done", failed → "error"
// "queued" is reserved for any stage whose preceding stage is still pending/running;
// implementation may simply render all non-running pending stages as "idle".
type BadgeState = "idle" | "queued" | "running" | "done" | "error";

// Per-row display config, colocated in UploadScreen.tsx
interface StageDisplay {
  key: StageName;
  label: string;  // e.g. "Parse EPUB"
  desc: string;   // e.g. "Split into chapter-segmented text"
}
```

## Out of scope

- Reading screen, chapter serving, progress endpoint wiring (slice 3).
- Chat input, query endpoint wiring, SSE streaming (slice 4).
- Resuming an in-progress upload after a page reload. If the user reloads, the current `book_id` is lost and the Upload screen resets to `idle`. The pipeline itself keeps running in the backend.
- Cancel or "notify when done" affordances.
- Upload progress percentage during the HTTP POST (the FastAPI endpoint buffers the whole file before responding anyway).
- Mobile layouts, dark-mode polish, accent switcher.

## Open questions

- None.
