# Slice R4 — Ambitious reading mode PRD

**Date:** 2026-04-22
**Parent:** ../../design_handoff_bookrag_reader/README.md

## Goal
Add a persisted, per-book "Ambitious" reading mode toggle that hides the margin column and reframes the spread with ambient paper, pacing label, edge arrows, progress hairline, legend, and hover note-peek — all frontend-only.

## User stories
1. As a reader, I can toggle reading mode on/off from a top-right pill so I can immerse without margin cards.
2. As a reader, reading mode persists per-book across reloads so returning to a book preserves my chosen mode.
3. As a reader, reading mode shows a stave pacing label so I know where I am in the book's overall structure.
4. As a reader, a bottom hairline shows progress through the book at paragraph granularity.
5. As a reader, hovering a noted phrase in reading mode surfaces the note body in a peek popover without navigating to margin cards.

## Acceptance criteria
1. A toggle pill with accessible name "Reading mode" is visible in the top bar's right cluster. Off state has `data-state="off"`; on state has `data-state="on"` and label includes a checkmark and text "Reading".
2. Clicking the pill toggles `data-reading-mode` on the reader root between `"off"` and `"on"`.
3. When on: the top bar receives `opacity: 0.55`; the margin column element is removed from the accessibility tree (or `aria-hidden="true"`) and its computed `opacity` is `0`.
4. When on: an element with `data-testid="pacing-label"` is present whose text matches `/^stave (one|two|three|four|five|six|seven|eight|nine|ten|\d+) · of \w+$/i` derived from `GET /books/{id}/chapters`.
5. When on: elements `data-testid="page-arrow-left"` and `data-testid="page-arrow-right"` are visible at opposite edges.
6. When on: `data-testid="progress-hairline"` is present; its foreground child has inline `width` equal to `Math.round(progress * 10000) / 100 + "%"` where `progress = (cumulativeParagraphsBeforeSpread + currentSpreadLastParagraphIdx + 1) / totalParagraphs`, clamped `[0, 1]`.
7. When on: `data-testid="reading-mode-legend"` contains the text `ASKED`, `NOTED`, and `ENTITY`.
8. When off: elements 4–7 are absent from the DOM (or `hidden`), and the margin column is visible again.
9. Reloading the page restores the prior reading-mode state for the same `bookId` from `localStorage.getItem("bookrag.reading-mode.{bookId}")`.
10. Two different books have independent reading-mode state (toggling book A does not toggle book B).
11. With reading mode on, hovering an element with `data-kind="note"` for ≥150ms causes `data-testid="note-peek"` to appear; `mouseleave` hides it. The peek contains the note body text.
12. Toggling the pill twice returns the DOM to its pre-toggle structure (no leaked listeners or duplicated legends).

## UI scope
- New: `ReadingModeToggle` (top-bar pill), `PacingLabel`, `PageTurnArrow` (left/right), `ProgressHairline`, `ReadingModeLegend`, `NotePeekPopover`.
- New: `useReadingMode(bookId)` hook wrapping the localStorage key.
- Modified: `frontend/src/screens/ReadingScreen.tsx` — mount toggle, apply `data-reading-mode` attribute + conditional renders, pass dimming class to top bar, pass `aria-hidden` + transition class to `MarginColumn`.
- Modified: `frontend/src/components/reader/MarginColumn.tsx` — accept `hidden` prop driving opacity/translate transition (260ms, `translateX(40px)`).
- Reused: existing chapters fetch and paginator output for pacing + hairline math.
- Untouched: R1/R2/R3 components (BookSpread, cards, selection toolbar, overflow collapse, streaming, follow-ups, etc.).

## Backend scope
None. R4 is purely a frontend slice. No new endpoints, no schema changes, no pipeline work. Confirmed.

## Data contracts

### localStorage
- **Key:** `bookrag.reading-mode.{bookId}`
- **Value:** JSON-encoded `"on" | "off"` (string literal, double-quoted). Absent key → default `"off"`.
- **Write:** on every toggle.
- **Read:** on `ReadingScreen` mount for the current `bookId`.

### Ordinal map (client-side constant)
```ts
const ORDINALS = ["One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten"];
// stave(n, total) -> `Stave ${ORDINALS[n-1] ?? n} · of ${ORDINALS[total-1] ?? total}`
```

### Progress computation
```ts
progress = clamp(
  (cumulativeParagraphsBeforeSpread + currentSpreadLastParagraphIdx + 1) / totalParagraphs,
  0, 1
);
```
Inputs come from existing paginator state; no new API fields.

## Out of scope
- Card detail / edit / delete (R5, blocked on design).
- Touch / keyboard fallback for note-peek (desktop hover only for v1).
- Entity link popovers or interactions (legend shows the color sample only).
- Changes to card rendering, card schema, streaming, overflow, or selection flow.
- Reading-mode-specific changes to the fog-of-war cursor or page-turn keyboard handling (existing R1 arrow-key behavior carries over).
- Cross-device sync of reading-mode state.

## Open questions
None.
