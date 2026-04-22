# Slice R1b review — fit-and-finish

**Date:** 2026-04-22
**Reviewer:** Evaluator agent
**Verdict:** APPROVE
**Range reviewed:** `c83d1c8..HEAD` (`c999a55..113af53` + T7 at `d7942bc..39c3ab1`)
**Spec:** `docs/superpowers/specs/2026-04-22-slice-R1b-fit-and-finish.md`
**Plan:** `docs/superpowers/plans/2026-04-22-slice-R1b-fit-and-finish-plan.md`

## Summary

The three fit-and-finish fixes (fixed spread dims, spread-scoped `visibleSids`, arrow-key chapter advance) landed cleanly with TDD-style red/green commit pairs per task. All R1b acceptance criteria are demonstrably satisfied by the per-slice Playwright gate (5/5 green), the regression sweep against R1/R2/R3 (41 additional specs green), and a new end-to-end flow spec that exercises library → chapter 1 → Ask → Note → page-turn → next chapter → ArrowLeft back to previous chapter's last spread.

## Per-AC verification

| AC | Requirement | Evidence | Status |
|----|-------------|----------|--------|
| 1 | Fixed outer width + min-height on `BookSpread`; width identical between turns | `BookSpread.tsx` sets `width: 920, minHeight: 780` on `.rr-book`. `slice-R1b AC1` asserts `boundingBox().width` equality + `height ≥ baseline` across ArrowRight. Flow-spec step 5 also asserts width stability across every spread observed in ch.1. | PASS |
| 2 | `MarginColumn` only receives current-spread sids; cards outside the current spread not rendered; S7 prefix intra-spread only | `ReadingScreen.tsx` rewrites `visibleSids` as union of current spread's left/right sids. `sidToFolio` map removed. `MarginColumn.tsx` drops the previous-spread fallback and only emits cross-page when anchor ∈ `leftSids`. `slice-R1b AC2` + `AC5` cover both paths. | PASS |
| 3 | ArrowRight on last spread of ch. N (N < total) → `/read/{N+1}` spread 0; ArrowLeft on spread 0 of ch. N (N > 1) → `/read/{N-1}` landing on last spread | `ReadingScreen.tsx` `turnForward` calls `navigate(…/{num+1})`. `turnBackward` navigates with `state.landOnLastSpread: true`; mount-time `useEffect` reads `location.state` and seeds `spreadIdx = spreads.length - 1`. `slice-R1b AC3`+`AC4` + flow-spec steps 5-7 all green. | PASS |
| 4 | Boundary no-ops: last spread of last chapter ArrowRight no-op; spread 0 of ch. 1 ArrowLeft no-op | `turnForward` else-branch is a fall-through (no-op); `turnBackward` guarded by `body.chapter.num > 1`. `slice-R1b AC3` + `AC4` assert URL unchanged on boundaries. | PASS |
| 5 | All R1, R2, R3 Playwright specs remain green | `npx playwright test slice-R1 slice-R2 slice-R3 slice-R1b` → 46/46 passed. T6 commit (`113af53`) updated R3 AC7 expectations to match the new intra-spread S7 semantics, which is consistent with AC 2's narrowed contract. | PASS |

## Gate results

- Backend `pytest tests/` → **1250 passed** in 14.9s. 3 pre-existing Pydantic/coroutine warnings unchanged by this slice.
- Frontend `npm test -- --run` → 247 passed, 6 failed + 10 failed test files. All failures trace to pre-existing slice-R4 TDD-red tests introduced at commit `cf0013f` (`test: add failing tests for slice R4 (reading-mode)`) before R1b began. No R1b-introduced regressions. Re-verified by locating the offending assertions (`data-reading-mode`, `NotePeekPopover`, etc.) in files whose last modification is the R4 red commit.
- Per-slice gate `npx playwright test slice-R1b` → **5/5 passed** (`slice-R1b-fit-and-finish.spec.ts`).
- Regression sweep `slice-R1 slice-R2 slice-R3 slice-R1b` → **46/46 passed**.
- End-to-end flow gate `npx playwright test flow-reader-end-to-end` → **1/1 passed** in 2.5s (`flow-reader-end-to-end.spec.ts`).

## End-to-end flow spec — step-by-step

Backend mocked per the `slice-R3-card-states-and-overflow.spec.ts` pattern (no running FastAPI required; mock surface covers `GET /books`, `GET /books/:id/chapters/:n`, `POST /books/:id/query`). Book id: `christmas_carol_e6ddcd76`. Three-chapter, 60-sentence-per-chapter fixture to force multi-spread pagination.

| Step | What is verified | Screenshot |
|------|------------------|------------|
| 1 | Library renders, "A Christmas Carol" card visible | `docs/superpowers/reviews/assets/2026-04-22-slice-R1b/flow-01-library.png` |
| 2 | Click card → `/books/:id/read/1`, BookSpread visible, baseline width/height captured | `.../flow-02-chapter1-spread0.png` |
| 3 | Select phrase on p1.s1 → Ask → streamed synthesized answer lands in margin | `.../flow-03-ask-card.png` |
| 4 | Select phrase on p1.s2 → Note "flow note" persists in margin | `.../flow-04-note-card.png` |
| 5 | ArrowRight through every spread of chapter 1 — width stable at baseline on every spread | `.../flow-05-chapter-pageturn.png` |
| 6 | Final ArrowRight on last spread of ch.1 advances URL to `/read/2`, BookSpread still renders | `.../flow-06-chapter2-spread0.png` |
| 7 | ArrowLeft on ch.2 spread 0 → URL returns to `/read/1` AND spread counter shows last-spread equality (`cur == tot`) | `.../flow-07-chapter1-last-spread.png` |

Console-error filter asserts no unexpected errors across the flow (allowlist: `favicon`, `DevTools`).

### Finding flagged during flow construction (out-of-scope for R1b)

Card anchors are stored in `bookrag.cards.{bookId}` keyed by bare sid (e.g. `p1.s1`). The sid namespace is per-chapter, so `p1.s1` exists in every chapter. When paging forward from ch.1 to ch.2, the card anchored to `p1.s1` in ch.1 re-matches to ch.2's `p1.s1` and re-renders. This is consistent with the R1b spec's *Out of scope* note ("Cross-chapter card persistence — cards continue to live in the same `bookrag.cards.{bookId}` localStorage key; only visibility changes") but is worth capturing explicitly as a follow-up — the visibility semantics AC2 aims for break down at chapter boundaries because the sid space is not globally unique. Recommend a future slice qualify anchors with chapter number (e.g. `c2.p1.s1`) or otherwise scope cards per chapter.

## Scope discipline

No scope creep. All changes live in `BookSpread.tsx`, `MarginColumn.tsx`, `ReadingScreen.tsx`, their unit tests, one new e2e spec for the gate, one e2e spec update (`slice-R3` AC7 expectations), and the new flow spec. No backend, config, or env changes — consistent with the spec's "Backend scope: None" and "Data contracts: Unchanged."

## Code quality observations

- `ReadingScreen.tsx` `currentSpreadSids = visibleSids` assignment is a harmless alias but could be simplified — the `currentSpreadSids` prop on `MarginColumn` could now be removed or unified with `visibleSids` since they carry the same set. Low-priority cleanup, not blocking.
- `landOnLastSpread` navigation state is read once on chapter-load effect and not cleared. If the reader ArrowLefts into ch. N-1 then manually refreshes the page, `location.state` persists and they'd still land on the last spread of that chapter. Probably desirable, but worth a one-line comment.
- `MarginColumn.tsx` comment was updated to match the new intra-spread semantics. Good.

None of these rise to blocking. Logging as T7 follow-up suggestions only.

## Verdict

**APPROVE.** The three stated fixes are correct, tested at unit + e2e levels, and survive the full R1/R2/R3 regression sweep plus a new end-to-end flow. Slice R1b status may move to `done`.
