# Slice 3 — reading-chapter-serving PRD

**Date:** 2026-04-21
**Parent spec:** ../specs/2026-04-21-frontend-integration-agent-pipeline-design.md

## Goal

Ship the Reading screen end-to-end: clicking a `BookCard` in Library navigates to `/books/:bookId/read`, rendering the three-column layout (chapter nav, reading text, chat-shell) with working chapter-to-chapter navigation, a persisted reading-progress update, and a spoiler lock that hides unread chapters.

## User stories

- As a reader, I can click a book in the Library so that I land on its Reading screen at the chapter I last left.
- As a reader, I can see every chapter in the left sidebar with its read/current/locked state so that I know where I am in the book.
- As a reader, I can read the body text of the current chapter, and click prev/next (or a sidebar row) to move between chapters I have unlocked.
- As a reader, I can mark the current chapter as read so that my progress persists across reloads and chapters ahead unlock one at a time.
- As a reader, chapters past my progress are hidden (padlock or blurred preview) so that I cannot be spoiled.

## Acceptance criteria

1. Clicking a `BookCard` on `/` navigates to `/books/:bookId/read`, which redirects to `/books/:bookId/read/:currentChapter` (the `current_chapter` returned from `GET /books`). The page renders without console errors.
2. The NavBar's *Reading* tab is active on any `/books/:bookId/read*` route and inactive elsewhere; clicking *Library* returns to `/`.
3. The left sidebar fetches `GET /books/{book_id}/chapters` once on mount and renders one `ChapterRow` per returned chapter, with `state` derived as: `num < current_chapter` → `read`, `num == current_chapter` → `current`, `num > current_chapter` → `locked`. The book title, author (may be blank for now), and a `ProgressPill` render above the list.
4. Clicking a `ChapterRow` whose state is `read` or `current` navigates to `/books/:bookId/read/:num` and the center column rerenders with that chapter's text. Clicking a `locked` row is a no-op (cursor `not-allowed`).
5. The center column calls `GET /books/{book_id}/chapters/{n}` on every chapter change, shows a loading state while pending, and renders the chapter title as an `<h2>` followed by one `<p>` per paragraph. Paragraph fidelity: the number of `<p>` elements equals the number of non-empty paragraphs in the backend response's `paragraphs` array.
6. Prev/Next buttons appear below the reading text. Prev is disabled on chapter 1; Next is disabled when the current chapter is equal to `current_chapter` (user hasn't unlocked the next one yet) OR when `n == total_chapters`. Clicking them navigates to `/books/:bookId/read/:n±1`.
7. A "Mark as read" button is visible above/below the text when and only when the viewed chapter `n == current_chapter` AND `n < total_chapters`. Clicking it POSTs `{current_chapter: n + 1}` to `/books/{book_id}/progress`; on 2xx the left sidebar updates (the clicked chapter becomes `read`, the next becomes `current`) and the user is navigated to `/books/:bookId/read/:n+1`. No full page reload.
8. Reloading the page at `/books/:bookId/read/:n` preserves progress: the sidebar reflects the server-side `reading_progress.json`, not an in-memory optimistic value. After step 7, reloading must show the new `current_chapter`.
9. A chapter whose `num == current_chapter + 1` renders as a teaser: backend returns the first paragraph only, the client overlays `ProgressiveBlur` with `locked` set, and no other paragraphs are present in the DOM. Chapters where `num > current_chapter + 1` render `LockState` with the chapter title and nothing else (no body text fetched or shown).
10. The right column renders a chat-shell: header ("Margin notes" label, `LockState` `spoilerSafe` pill reading `"safe through ch. {current_chapter}"`), a centered empty-state placeholder ("Chat coming soon — available in the next release"), and a disabled `ChatInput`-shaped element or plain disabled `<input>` with the same tooltip string. No `UserBubble` / `AssistantBubble` / send-button wiring. Layout matches the 260px / 1fr / 440px grid from `screens.jsx`.
11. `curl http://localhost:8000/books/christmas_carol_e6ddcd76/chapters` returns a JSON array matching the `ChapterSummary[]` contract; `curl http://localhost:8000/books/christmas_carol_e6ddcd76/chapters/1` returns the `Chapter` contract. Out-of-range `n` returns 404 with a JSON `detail`. Unknown `book_id` returns 404.
12. `curl -X POST -H 'Content-Type: application/json' -d '{"current_chapter":2}' http://localhost:8000/books/christmas_carol_e6ddcd76/progress` returns 200 and `cat data/processed/christmas_carol_e6ddcd76/reading_progress.json` reflects `2`.
13. `pytest -v` and `npm run test` pass. No existing tests regress.

## UI scope

**NEW — port from `design-handoff/project/*.jsx` to `frontend/src/components/` (and one screen to `frontend/src/screens/`):**

- `components.jsx` → `ChapterRow`
- `components2.jsx` → `Highlight` (visual-only; renders static children, no selection logic)
- `components2.jsx` → `ProgressiveBlur`
- `components2.jsx` → `LockState`
- `icons.jsx` → `IcDot`, `IcCheck`, `IcLock`, `IcUnlock`, `IcBookmark`, `IcChat` (whatever is missing from slice 1/2)
- `screens.jsx` → `ReadingScreen` at `frontend/src/screens/ReadingScreen.tsx`, wired to real data

**REUSED — from prior slices:**

- `NavBar`, `Wordmark`, `Row`, `Stack`, `Button`, `IconBtn`, `ProgressPill`, `LibraryScreen` (adds `onClick` navigation on `BookCard`)
- `lib/api.ts` — extend with `fetchChapters`, `fetchChapter`, `setProgress`; keep existing exports

**OUT OF SCOPE — do not port:**

- `UserBubble`, `AssistantBubble`, `ChatInput` wiring (slice 4). The chat input may be rendered visually disabled or omitted entirely; pick "disabled input with tooltip 'Available in the next release'".
- Query endpoint wiring, SSE, source citations.
- Text selection, margin-note creation, entity click-through on `Highlight`.
- Inline entity highlighting — render the chapter text as plain paragraphs this slice. `Highlight` is only ported so it is in the component kit for slice 4; it is not used in `ReadingScreen`.
- Dark-mode wiring, accent switcher, density switcher.

**Router additions (`App.tsx`):**

- `/books/:bookId/read` → redirect to `/books/:bookId/read/:currentChapter`
- `/books/:bookId/read/:chapterNum` → `<ReadingScreen />`

## Backend scope

**Existing endpoints this slice consumes:**

- `GET /books` — unchanged (slice 1).
- `POST /books/{book_id}/progress` — already exists in `main.py`. This slice wires it.

**New endpoints added to `main.py`:**

- **`GET /books/{book_id}/chapters`** — returns `ChapterSummary[]`.
  - Data source: scan `data/processed/{book_id}/resolved/chapters/chapter_*.txt` if that directory exists; otherwise fall back to `data/processed/{book_id}/raw/chapters/chapter_*.txt`. File naming is `chapter_{NN}.txt` (zero-padded, confirmed against `christmas_carol_e6ddcd76`).
  - `title` for now is `f"Chapter {num}"` (no title extraction this slice; see Open questions).
  - `word_count` is `len(text.split())`.
  - `current_chapter` is the book-level value returned from the progress file; it is NOT per-chapter state. The frontend derives per-chapter state.
  - 404 if the `book_id` directory doesn't exist OR `ready_for_query` is false in `pipeline_state.json`.

- **`GET /books/{book_id}/chapters/{n}`** — returns `Chapter`.
  - Data source precedence: `data/processed/{book_id}/resolved/chapters/chapter_{n:02d}.txt` if it exists; else `data/processed/{book_id}/raw/chapters/chapter_{n:02d}.txt`. If the resolved copy is served, **strip parenthetical-coref brackets** from the text before returning it (regex: `\s*\[[^\]]+\]`) so the reader sees natural prose. The bracket-stripped copy may optionally be cached to disk; simplest correct implementation is strip-on-read.
  - Paragraph splitting: split the stripped text on `\n\n`, strip each element, drop empties. If the source is resolved (one continuous line, no paragraph breaks), fall back to `raw/chapters/chapter_{n:02d}.txt` for the paragraph split and then apply any available resolved-text override paragraph-by-paragraph only if trivial; otherwise just serve the raw paragraphs. The planner may simplify to "always paragraph-split from raw, always use resolved for coref-stripped text only if trivial to align" — default for this slice is **serve raw-file paragraphs** with a comment that a later slice can switch to resolved once its line breaks are preserved upstream.
  - `title`: first non-empty stripped line if it is short (<80 chars) and does not end in a sentence-terminator, else `f"Chapter {n}"`. For Christmas Carol, chapter 2 begins with the line "The Last of the Spirits" which qualifies.
  - `has_prev` = `n > 1`; `has_next` = `n < total_chapters`.
  - 404 if `n < 1` or `n > total_chapters` or `book_id` not found.

- `POST /books/{book_id}/progress` — **unchanged**. Already validates `current_chapter >= 1` and writes `reading_progress.json`. This slice wires the frontend and adds a regression test asserting the written file shape.

CORS unchanged. No new env vars.

## Data contracts

```ts
// GET /books/{book_id}/chapters response
interface ChapterSummary {
  num: number;          // 1-indexed
  title: string;        // "Chapter 1" or first-line heuristic
  word_count: number;
}

// GET /books/{book_id}/chapters/{n} response
interface Chapter {
  num: number;
  title: string;
  paragraphs: string[];  // in reading order; no trailing empties
  has_prev: boolean;
  has_next: boolean;
  total_chapters: number;
}

// POST /books/{book_id}/progress request — wire-up only; shape already exists
interface ProgressUpdate {
  current_chapter: number;  // >= 1
}
```

## Out of scope

- Chat input wiring, `/query` calls, SSE streaming, source citations (slice 4).
- Margin-note creation, selection highlighting, entity click-through on `Highlight`.
- Real chapter titles from EPUB TOC (pipeline change — frozen).
- Reading analytics, reading-time estimates, auto-advance on scroll.
- Mobile or tablet layouts.
- Multiple books open simultaneously.
- Dark-mode polish.

## Open questions

- **When does `POST /progress` fire?** Proposed default: **once, on the "Mark as read" button click** for the chapter whose `num == current_chapter`. Not on arrival, not on scroll, not on nav away. Reversible later.
- **What do locked chapters show?** Proposed default: chapters where `num == current_chapter + 1` show the first paragraph under `ProgressiveBlur` with the "advance to reveal" pill (teaser). Chapters where `num > current_chapter + 1` show `LockState` with only the padlock + chapter title; no text fetched.
- **Chat sidebar shell shape.** Proposed default: render the right-column structure, disabled textarea with tooltip "Available in the next release", no send button. Header shows "Margin notes" label and a `LockState spoilerSafe` pill reading `"safe through ch. {current_chapter}"`. No bubble list, no suggested-question chips.
- **Resolved vs raw source for body text.** Proposed default: **serve raw-file paragraphs** (raw preserves `\n\n`, resolved is one long line). A future slice can switch to resolved once upstream preserves paragraph boundaries; coref brackets are a Phase 2 concern, not a reader concern.
- **Chapter titles.** Proposed default: `f"Chapter {n}"`. First-line heuristic is nice-to-have and may be deferred to the Planner.
