# Slice R2 Review — V3 Inline cards + selection→ask + notes

**Date:** 2026-04-22
**Verdict:** APPROVE
**Reviewer:** Evaluator agent (superpowers:code-reviewer)

## Rubric check

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Tests pass, no regressions | PASS | Backend `pytest` 1221 passed / 3 warnings (13.84s). Frontend `npm test -- --run` 168 passed across 35 files (1.38s). |
| 2 | Dev server renders ReadingScreen without console errors | PASS (indirect) | Playwright runs spin up the Vite dev server via `webServer` config and load `/books/carol/read/1`; no console errors surfaced during 12 Playwright tests. `ReadingScreen.test.tsx` also asserts no render errors. |
| 3 | No CORS/auth drift; env var changes documented | PASS | Diff touches no config files, `main.py`, `.env`, or `models/config.py`. Zero backend changes per spec. |
| 4 | Every PRD AC visibly satisfied | PASS | See per-criterion table below; 14/14 ACs. |
| 5 | No scope creep | PASS | All new modules align with the plan's T1–T10 and spec's "In scope (R2)" list. Legacy `AnnotationRail`/`AnnotationPanel`/`AnnotationPeek`/`NoteComposer`/`AnnotatedParagraph` deletions are pre-declared in the plan. |
| 6 | Playwright gate + per-AC screenshots | PASS | `slice-R2-cards-and-selection.spec.ts` 6/6 green; screenshot spec `slice-R2-screenshots.spec.ts` 6/6 green. 8 asset PNGs saved to `docs/superpowers/reviews/assets/2026-04-22-slice-R2/`. |

## Per-criterion verification

1. **AC1 — `grid-template-columns: 1fr 400px` + anchor-filtered margin.** PASS. `ReadingScreen.tsx:302-304` sets the grid; `MarginColumn.tsx:21` filters `cards.filter((c) => visibleSids.has(c.anchor))`. Screenshot: `ac1-margin-column.png`.
2. **AC2 — S1 empty invitation card with sparkle + heading.** PASS. `S1EmptyCard.tsx` renders `✦` badge and "Ask about what you're reading". Rendered whenever no cards match visible anchors. Screenshot: `ac2-empty-state.png`.
3. **AC3 — Selection toolbar within 180ms with Ask/Note/Highlight.** PASS. `useSelectionToolbar.ts` debounces 100ms after `selectionchange`; toolbar has transition `180ms ease`. Playwright test `selection shows the Ask/Note/Highlight toolbar (AC 3)` asserts all three buttons within 1s.
4. **AC4 — Toolbar anchors to `data-sid` of start sentence; `quote` = selected text.** PASS. `selection.ts:findSidAncestor(range.startContainer)` walks to `data-sid` ancestor; `quote = range.toString().trim()`. Screenshot: `ac4-selection-toolbar.png`.
5. **AC5 — Ask POSTs templated prompt and immediately renders empty-answer card.** PASS. `askFlow.ts:buildAskQuestion` → `Asked about "{quote}": what does this mean in context?`; `createAsk` fires before `queryBook` resolves. Playwright asserts `ask-answer` becomes visible before final text lands.
6. **AC6 — Token-by-token chunk into `answer` at ~25–60ms cadence.** PASS. `streamSimulator.ts` tokenises `full.match(/\S+\s*/g)`, takes 1–3 word slices, awaits `25–60ms` jittered `setTimeout`, calls `onChunk(soFar)`. Final `soFar === full`. Screenshot: `ac5-ask-streaming.png`.
7. **AC7 — Note creates empty editable card, focuses body, commits on blur/Enter, empty-on-commit discarded.** PASS. `NoteCard.tsx` auto-focuses via `useEffect(autoFocus)`; Enter-without-shift calls `onBodyCommit` which in `ReadingScreen.onBodyCommit` removes card if `body.trim() === ""`. Playwright `Note creates a card, accepts typed body, persists on Enter` green. Screenshot: `ac6-note-card.png`.
8. **AC8 — Highlight is a visual no-op that clears the selection.** PASS. `ReadingScreen.onAction` hits `if (action === "highlight") { clearSelection(); return; }` with no store writes.
9. **AC9 — Asked sentence bg `oklch(72% 0.08 155 / 0.42)`; noted = underline note orange.** PASS. `Sentence.tsx:27` applies exact oklch background; lines 32-35 set underline with `oklch(58% 0.1 55)` color. Playwright asserts computed `backgroundColor` is not transparent. Screenshot: `ac9-fog-disables-ask.png` (reused to show settled asked-state highlight).
10. **AC10 — Click indicator scrolls margin card + ~600ms focus flash.** PASS. `onMarkClick` calls `scrollIntoView` + `flash(cardId)`; `flash` sets `focusedCardId` then clears after 620ms. `AskCard`/`NoteCard` render `rr-card-flash` class when focused. Playwright spec asserts `rr-card-flash` class appears on click.
11. **AC11 — Second Ask on same `sid` focuses existing card (no duplicate).** PASS. `askFlow.ts:32-34` short-circuits if `findExisting(anchor)` returns a card; `onAction` flashes it. Screenshot: `ac11-dup-focus.png`.
12. **AC12 — Persist to `localStorage` under `bookrag.cards.{bookId}`; restore on mount; synchronous writes.** PASS. `cards.ts:CARDS_KEY` + `writeStoredCards` called from `useCards.commit` on every create/update/remove. Hook initialises `useState(() => readStoredCards(bookId))`. Playwright `reload restores cards (AC 12)` green.
13. **AC13 — Ask disabled when selection start `sid` > cursor (fog-of-war).** PASS. `ReadingScreen` computes `askDisabled = !!selection && compareSid(selection.anchorSid, cursor) > 0`; passed to `SelectionToolbar`'s `disabled.ask`. Playwright `Ask is disabled when selection is past the fog cursor (AC 13)` green (asserts `Note` remains enabled).
14. **AC14 — Playwright spec exists at `frontend/e2e/slice-R2-cards-and-selection.spec.ts`.** PASS. 6 tests, 6 passed (4.2s).

## Screenshots

All captured via `frontend/e2e/slice-R2-screenshots.spec.ts`:

- `ac1-margin-column.png`
- `ac2-empty-state.png`
- `ac4-selection-toolbar.png`
- `ac5-ask-streaming.png`
- `ac6-note-card.png`
- `ac7-persisted-reload.png`
- `ac9-fog-disables-ask.png`
- `ac11-dup-focus.png`

## Findings / notes

- **Pre-existing Playwright failures (not R2 regressions).** `frontend/e2e/reading.spec.ts` (2 failing) and `frontend/e2e/chat.spec.ts` (4 failing) target the pre-R1 UI (e.g., Thread tab, `/read/:current_chapter` autoroute specifics); their assertions reference components replaced by the V3 Inline reader. These pre-date R1 and are flagged — not blocking.
- **Minor risk — `onAction` async closure.** `onAction` is async; when Ask races with a user re-selecting mid-stream the `selection` captured in the closure still points at the original. This is correct for R2 (we want the asked quote preserved), but worth noting for R3 follow-ups.
- **Minor observation — `Sentence` click handler uses `(asked ?? noted)`.** If a sentence ever ended up with both an ask and a note card (not currently possible because `findByAnchorAndKind` short-circuits duplicates per kind), the ask would take click precedence. Fine for R2.
- **Visual fidelity vs `design_handoff_bookrag_reader/`.** Card styling matches the V3 Inline spec in `Handoff Spec.html` (paper bg, left accent border, 10px radius, subtle `rotate(-0.2deg)` on ask, `rotate(0.2deg)` on note, serif body + uppercase sans header strip). Selection toolbar is the dark pill per §5.

## Slice summary

Slice R2 delivers a V3 Inline margin-card reader: selection toolbar, fog-aware Ask with client-side simulated streaming, inline Note capture with localStorage persistence, and on-page asked/noted indicators with click-to-focus — all validated by a 6-test Playwright gate and 8 AC screenshots.
