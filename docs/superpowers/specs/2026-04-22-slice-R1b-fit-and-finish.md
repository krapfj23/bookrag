# Slice R1b — Reader fit-and-finish PRD

**Date:** 2026-04-22
**Parent:** `design_handoff_bookrag_reader/README.md`

## Goal

Close three visual/interaction gaps that surfaced in manual QA of R1–R3 and bring behavior into alignment with the handoff.

## User stories

- As a reader, I can page through an entire book without the spread visibly resizing between pages.
- As a reader, I only see the annotation cards that belong to what's currently on screen.
- As a reader, when I reach the last page of a chapter and press ArrowRight, the reader advances to the next chapter instead of dead-ending.

## Acceptance criteria

1. `BookSpread` has a fixed outer width and min-height (both in CSS pixels). Turning between any two spreads within a chapter produces zero measurable change in the spread's bounding rect width and min-height (Playwright asserts `boundingBox()` width equal across 2+ spreads, height equal or >= baseline).
2. `MarginColumn` receives `visibleSids` equal to only the sids of the *current spread* (left + right). Cards anchored outside the current spread are not rendered (neither as full cards nor as cross-page prefixed cards). The `← FROM p. {n} ·` prefix for R3 S7 remains reachable only when a card's anchor is on the *opposite page of the current spread* (left vs right within the same spread), never across spreads.
3. Pressing `ArrowRight` on the last spread of chapter N, when chapter N+1 exists (N < total_chapters), navigates to `/books/:bookId/read/{N+1}` and restores spread index 0 of the new chapter. Pressing `ArrowLeft` on spread 0 of chapter N, when N > 1, navigates to `/books/:bookId/read/{N-1}` and jumps to the *last* spread of chapter N-1.
4. On the last spread of the last chapter, ArrowRight is a no-op (no navigation, no error). On spread 0 of chapter 1, ArrowLeft is a no-op.
5. All R1, R2, R3 Playwright specs remain green.

## UI scope

- Modify: `frontend/src/components/reader/BookSpread.tsx` (fixed width + min-height via CSS vars).
- Modify: `frontend/src/screens/ReadingScreen.tsx`:
  - Revert `visibleSids` to current-spread-only.
  - Add end-of-chapter ArrowRight/ArrowLeft navigation using React Router's `useNavigate`.
- Modify: `frontend/src/components/reader/MarginColumn.tsx` (and/or `ReadingScreen`) so cards' cross-page prefix is computed *within* the current spread only, not across spreads.
- Rewrite S7 Playwright test to cover the real scenario: card anchored on the left page of a spread, viewed alongside the right page's visible anchors — the card shows `← FROM p. {leftFolio} ·` when the margin is conceptually associated with the right page.

## Backend scope

None. No API changes.

## Data contracts

Unchanged.

## Out of scope

- Chapter TOC drawer / top-bar chapter chevrons (only key-driven advance is in scope for this slice).
- URL persistence of spread index across chapter boundaries (we land on spread 0 going forward, last spread going backward — simple and deterministic).
- Cross-chapter card persistence — cards continue to live in the same `bookrag.cards.{bookId}` localStorage key; only visibility changes.

## Open questions

None.
