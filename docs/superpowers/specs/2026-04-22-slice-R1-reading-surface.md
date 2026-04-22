# Slice R1 — Reading surface + sentence anchors PRD

**Date:** 2026-04-22
**Parent spec:** ../../design_handoff_bookrag_reader/README.md (design handoff)

## Goal

Replace `ReadingScreen.tsx` with a paginated two-page book spread that renders real EPUB text with sentence-addressable anchors and a fog-of-war reading cursor.

## User stories

- As a reader, I can open `/book/{bookId}` and see the chapter rendered as a two-page spread so that it feels like a physical book.
- As a reader, I can press ArrowRight / ArrowLeft to turn pages through a chapter so that I control pacing with the keyboard alone.
- As a reader, I can see text before my cursor rendered crisply and text after my cursor dimmed/blurred so that I am not spoiled by content I have not read.
- As a reader, I can turn a page and have my cursor advance to the last sentence on the new spread so that future-text stays fogged.
- As a future integrator (R2+), I can locate any sentence in the DOM by `data-sid="p{n}.s{m}"` so that annotation anchors resolve deterministically.

## Acceptance criteria

1. `GET /books/{book_id}/chapters/{n}` returns a body in which every paragraph is an ordered list of sentences, each with a stable id of the form `p{n}.s{m}` (n is 1-indexed paragraph within the chapter; m is 1-indexed sentence within that paragraph).
2. When the returned chapter has at least two paragraphs, the response preserves existing `num`, `title`, `has_prev`, `has_next`, `total_chapters` fields unchanged and adds the sentence-anchored structure in a new field (not a breaking rename).
3. Sentence boundaries for a chapter are derived from the BookNLP `.tokens` TSV (`sentence_ID` column) using byte offsets into the cleaned `raw/chapters/chapter_NN.txt` text; when `.tokens` is missing or offsets cannot be reconciled, the endpoint falls back to a regex sentence splitter and sets a boolean `anchors_fallback: true` on the response.
4. Navigating to `/book/{bookId}` without a `#chapter=` hash loads chapter 1; navigating with `#chapter=N` loads chapter N. (Re-uses existing `BookReadingRedirect` semantics.)
5. The reading surface renders a two-page spread: top bar (back · title · action pills), stage grid, and `BookSpread` with left + right pages, matching the design tokens in `design_handoff_bookrag_reader/tokens.css` (`--paper-00`, book shadow, `--serif` body at 15px / line-height 1.72, justified, hyphenated).
6. A client-side DOM paginator measures rendered page boxes and chunks the chapter's sentence-anchored paragraphs into spreads such that no sentence is split across pages and every sentence is present exactly once across the chapter's spreads.
7. Every rendered sentence carries `data-sid="p{n}.s{m}"` on its DOM element.
8. Pressing `ArrowRight` advances one spread; `ArrowLeft` goes back one spread. Arrow keys do nothing past the last/first spread of the chapter (no cross-chapter turn in R1).
9. On any spread, sentences whose anchor is strictly after the cursor's anchor are dimmed (opacity ≤ 0.35) and blurred (`filter: blur(≥2px)`); sentences at or before the cursor are fully opaque and unblurred.
10. Turning forward to a new spread advances the cursor to the last sentence visible on the new spread; turning backward does **not** rewind the cursor.
11. The cursor persists across reloads in `localStorage` under key `bookrag.cursor.{bookId}` as JSON `{ anchor: "p{n}.s{m}", chapter: n }` and is restored on mount.
12. On initial mount with no stored cursor, the cursor is the **first** sentence of the chapter (so only the first spread is fully visible, and all subsequent content is fogged until the reader turns forward).
13. A Playwright spec at `frontend/e2e/slice-R1-reading-surface.spec.ts` exercises: spread renders, `data-sid` present on sentences, ArrowRight advances pages and advances cursor, ArrowLeft goes back without rewinding cursor, post-cursor sentences have opacity < 0.5, reload restores cursor from localStorage.

## UI scope

**In scope (R1):**
- `ReadingScreen.tsx` (replaced in place)
- `BookSpread` (two-page layout, top bar, folio, chapter stave tag, chapter title, drop-cap on first paragraph, spine gradient)
- `Page` (one side of the spread, hosts paginated paragraphs)
- `Paragraph` + `Sentence` render primitives that emit `data-sid`
- Client-side DOM paginator utility (measurement + chunking)
- Keyboard handler (ArrowLeft / ArrowRight only)
- Cursor state + `localStorage` persistence hook
- Fog-of-war sentence styling (dim + blur by cursor comparison)
- `tokens.css` imported once at the app or screen level

**Out of scope (deferred to R2–R4):**
- `reader-var-*` variants
- Selection toolbar / Ask / Note flow
- Margin cards (V3 Inline column), card persistence, card states S1–S7, O2 overflow
- Reading mode toggle and ambient-paper transition
- Note-peek hover popover
- Card detail / edit / delete view
- Streaming answers, chat animations
- Entity link underlines
- Cross-chapter page turns, touch/mobile, bookmark/search pill actions (render as disabled affordances or omit)

## Backend scope

**Existing (unchanged):**
- `GET /books` — list ready books
- `GET /books/{book_id}/chapters` — chapter summaries
- `GET /books/{book_id}/chapters/{n}` — single chapter

**Added in R1:**
Sentence-anchor emission on `GET /books/{book_id}/chapters/{n}`. The response gains a new `paragraphs_anchored` field: an ordered list of paragraphs, each containing an ordered list of sentences with `sid` and `text`. The legacy `paragraphs: string[]` field is retained for backward compatibility with any current consumer until R2 removes it.

**Why nested (paragraphs → sentences) rather than a flat `sentences[]`:** the paginator needs paragraph boundaries for visual layout (drop-caps, block spacing), and sentence spoiler-gating needs paragraph context. A flat list would force the client to re-group by `paragraphIdx`, duplicating information already known to the server. Nested also keeps each sentence's `sid` self-explanatory without an auxiliary `paragraphIdx` field.

**Anchor derivation:** For each chapter, walk `.tokens` rows whose token byte range intersects the chapter's slice of the cleaned book text. Group tokens by `sentence_ID`; group sentences by `paragraph_ID` (relative to chapter start). Emit `p{1-indexed-paragraph}.s{1-indexed-sentence-within-paragraph}`. If reconciliation fails (missing `.tokens`, mismatched offsets, or cleaned-text divergence), fall back to splitting each existing `paragraphs[i]` string on a sentence-ending regex and set `anchors_fallback: true`.

## Data contracts

```ts
// Response of GET /books/{bookId}/chapters/{n}
interface ChapterResponse {
  num: number;                       // 1-indexed chapter number
  title: string;
  total_chapters: number;
  has_prev: boolean;
  has_next: boolean;
  paragraphs: string[];              // legacy; kept for R1 back-compat
  paragraphs_anchored: AnchoredParagraph[];
  anchors_fallback: boolean;         // true when BookNLP tokens could not be used
}

interface AnchoredParagraph {
  paragraph_idx: number;             // 1-indexed within the chapter
  sentences: AnchoredSentence[];
}

interface AnchoredSentence {
  sid: string;                       // "p{paragraph_idx}.s{sentence_idx}", both 1-indexed
  text: string;                      // exact sentence text as it should be rendered
}

// Frontend-only state
interface ReadingCursor {
  bookId: string;
  chapter: number;                   // 1-indexed
  anchor: string;                    // e.g. "p3.s2"
}

// localStorage key: `bookrag.cursor.{bookId}`
// localStorage value: JSON.stringify({ chapter, anchor })
```

## Out of scope

- Persisting cards, notes, or annotations to a backend store
- Any change to `POST /books/{id}/progress` or the existing chapter-level spoiler filter
- Cross-chapter navigation from within the reader surface
- Touch gestures, mobile layout, print styles
- Reading-mode ambient-paper toggle
- Selection, highlights, underlines, entity dotted underlines
- Streaming SSE or WebSocket endpoints
- Removing the legacy `paragraphs: string[]` field (deferred to R2 cleanup)

## Open questions

- Should the paginator be deterministic for Playwright (e.g. fixed viewport + font-load wait) or should the E2E spec assert only on anchor presence and cursor advancement without pinning exact sentences-per-page? Recommendation: the latter, to avoid flakiness from font metrics.
- When `anchors_fallback: true`, are regex-split sentence ids acceptable as stable annotation anchors in R2, or must R2 block until BookNLP reconciliation succeeds? (Affects whether R2 can ship against older books that were ingested before anchor derivation existed.)
