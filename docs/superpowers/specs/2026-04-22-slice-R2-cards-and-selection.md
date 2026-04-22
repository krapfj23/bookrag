# Slice R2 — V3 Inline cards + selection→ask + notes PRD

**Date:** 2026-04-22
**Parent:** ../../design_handoff_bookrag_reader/README.md

## Goal

Render a V3 Inline margin column beside the two-page spread so readers can select text on the page, ask a RAG question or capture a note, and see the resulting card persist locally anchored to a sentence `sid`.

## User stories

- As a reader, I can select a phrase on the page and see a small Ask/Note/Highlight toolbar so that I can act on my selection without leaving the text.
- As a reader, I can tap Ask and watch an answer appear token-by-token in a new margin card so that the response feels live.
- As a reader, I can tap Note, type a body inline, and save it as a margin card so that I can capture my own thoughts.
- As a reader, I can reload the page and still see all my previously-created cards in the margin so that my annotations persist.
- As a reader, I can tap an on-page indicator (green highlight or orange underline) for an existing card and see the margin card visually focus so that I can find my way back to an annotation.

## Acceptance criteria

1. Stage layout is `grid-template-columns: 1fr 400px` with a right column that renders only cards whose `anchor` matches a sentence `sid` currently visible on the spread.
2. When no cards exist for the visible anchors, the right column renders the S1 empty-state invitation card (sparkle badge + heading "Ask about what you're reading"). S2–S7 atomic states are **not** required in R2.
3. Selecting text spanning one or more sentences on the page shows a selection toolbar above the selection within 180ms, containing `Ask`, `Note`, and `Highlight` buttons. The toolbar disappears when the selection is cleared.
4. The toolbar anchors the selection to the `data-sid` of the sentence containing the selection's start; this `sid` becomes the card's `anchor`, and the exact selected text becomes `card.quote`.
5. Tapping `Ask` POSTs `{ question, max_chapter }` to `POST /books/{book_id}/query` with `question` set to a templated prompt that embeds `quote` (e.g., `Asked about "{quote}": what does this mean?` — final wording lives in the plan), creates a card with `kind: "ask"`, empty `answer`, and immediately renders it in the margin.
6. While the ask response resolves, the card's `answer` field is populated token-by-token by chunking the non-streaming response body into ~1–3 word chunks at ~25–60ms cadence; by the time chunking completes, `card.answer` equals the full server response.
7. Tapping `Note` creates a card with `kind: "note"`, renders it in the margin with an empty editable body, focuses the body, and commits the note on blur or Enter; an empty note on commit is discarded.
8. Tapping `Highlight` creates no card; it only marks the selection with the asked-phrase highlight style (green) without a question. (Highlights are stored as a card with `kind: "note"` and empty body? No — Highlight in R2 is a no-op visual: it clears the selection and does not persist. See Out of scope.)
9. Asked phrases on the page render with `background: oklch(72% 0.08 155 / 0.42)`; noted phrases render with `text-decoration: underline` in the note orange. Indicators are driven by the cards in localStorage matched against sentence `sid`s.
10. Clicking an on-page asked/noted indicator scrolls the corresponding margin card into view and applies a brief focus flash (CSS class for ~600ms).
11. Asking about a phrase whose `sid` already has a card of the same `kind` focuses that existing card instead of creating a duplicate (follow-up composer wiring is deferred to R3 threads; focus alone is sufficient for R2).
12. Cards persist to `localStorage` under `bookrag.cards.{bookId}` as a JSON array matching the `Card[]` schema below, and are restored on mount. Writes are synchronous after each create/update.
13. Cards whose anchor falls on a sentence strictly **after** the reading cursor are not requestable: the Ask button in the toolbar is disabled when the selection start `sid` is past the cursor, enforcing fog-of-war.
14. A Playwright spec at `frontend/e2e/slice-R2-cards-and-selection.spec.ts` exercises: selection shows toolbar; Ask creates a card whose answer grows over time and ends non-empty; Note creates a card, accepts typed body, persists; reload restores both cards; on-page green highlight appears for asked sentence; clicking the highlight focuses the margin card.

## UI scope

**In scope (R2):**
- Right margin column on `ReadingScreen` (400px, `padding-top: 40px`, `gap: 14px`).
- `MarginColumn` container that filters `Card[]` by `visibleAnchors`.
- `AskCard` and `NoteCard` components (V3 Inline visuals: paper bg, left border accent, 10px radius, subtle rotation, header strip, italic question, serif answer/body).
- `S1EmptyCard` invitation state.
- `SelectionToolbar` (dark pill, Ask / Note / Highlight, 180ms fade+slide).
- On-page asked/noted indicator styling layered over `Sentence`.
- Client-side streaming simulator utility (chunker over the `query` response string).
- `useCards` hook: load/save to `localStorage`, create/update card APIs.

**Out of scope (R2):** reading-mode toggle (R4), O2 overflow collapse (R3), S3 streaming skeleton + blinking cursor (R3), S4 long-answer internal scroll (R3), S5 follow-up thread composer (R3), S6 off-screen anchor prefix + jump CTA (R3), S7 cross-page prefix (R3), card detail / edit / delete view, entity dotted underlines, card-to-span SVG connector, chat open animation (AN3 flip-in + phrase pulse), Highlight persistence, note-peek hover popover.

## Backend scope

No backend changes. After auditing `main.py` and `api/query/synthesis.py`, the existing `POST /books/{book_id}/query` returns a synthesized answer as a JSON response — no SSE, no WebSocket, no token-by-token HTTP streaming. R2 consumes this endpoint as-is and simulates streaming client-side by chunking the returned string. `max_chapter` for the query is the cursor's `chapter` (honoring fog-of-war via the existing spoiler filter).

## Data contracts

```ts
interface BaseCard {
  id: string;                    // uuid v4, generated client-side
  bookId: string;
  anchor: string;                // "p{n}.s{m}", matches Sentence data-sid from R1
  quote: string;                 // exact selected text
  chapter: number;               // 1-indexed chapter the anchor belongs to
  createdAt: string;             // ISO8601
  updatedAt: string;             // ISO8601
}

interface AskCard extends BaseCard {
  kind: "ask";
  question: string;              // prompt sent to /query (embeds quote)
  answer: string;                // grows during simulated streaming; final = server response
  followups: { question: string; answer: string }[]; // empty [] in R2
}

interface NoteCard extends BaseCard {
  kind: "note";
  body: string;                  // user-typed; never empty after commit
}

type Card = AskCard | NoteCard;

// localStorage
// key:   `bookrag.cards.{bookId}`
// value: JSON.stringify({ version: 1, cards: Card[] })
interface CardStore {
  version: 1;
  cards: Card[];
}
```

Schema is additive; future slices may bump `version` and migrate.

## Out of scope

- Server-side card persistence (kuzudb sync) — local-only per locked decisions.
- Real SSE/WebSocket streaming from `/query`.
- Edit / delete of existing cards (requires unscoped card-detail view).
- Highlight-only annotations persisting to storage.
- Card-to-phrase dashed SVG connector.
- Entity dotted underlines.
- Reading-mode affordances (dimmed top bar, margin slide-out, ambient paper gradient).
- Overflow collapse when >2 cards per spread.

## Open questions

- Confirm the exact templated Ask prompt wording (spec leaves this to the implementation plan).
- Should the Ask button in the toolbar be hidden or visibly disabled when the selection is past the fog cursor? Recommendation: visibly disabled with a tooltip to preserve affordance discoverability.
- Should a Note created on a sentence past the cursor be allowed (no LLM involved, so fog-of-war does not strictly apply)? Recommendation: allow, since notes do not leak future content.
