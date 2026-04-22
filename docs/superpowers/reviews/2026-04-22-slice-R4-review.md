# Slice R4 — Ambitious reading mode — Review

**Date:** 2026-04-22
**Spec:** `docs/superpowers/specs/2026-04-22-slice-R4-reading-mode.md`
**Plan:** `docs/superpowers/plans/2026-04-22-slice-R4-reading-mode-plan.md`
**Diff:** `84a9a4b..HEAD` (T1–T10 + pre-committed failing tests `cf0013f`)

## Verdict: REVISE

Core toggle, chrome, hover-peek, and persistence all land. Playwright AC gate (12/12) is green; vitest (275 tests) + pytest (1250 tests) pass. Two gaps block approval:

1. **Ambient paper gradient is not implemented.** Design handoff §4 specifies `radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)` applied on mode-on with a 420ms transition, and the evaluator prompt explicitly requires this be verified in the end-to-end flow spec. The stage background stays at flat `var(--paper-0)` regardless of mode. Grep for `radial-gradient`/`ambient` across `frontend/src/` returns nothing.
2. **End-to-end flow spec (T11) is missing.** Evaluator required `frontend/e2e/flow-reader-reading-mode.spec.ts` (or an extension of `flow-reader-end-to-end.spec.ts`) that drives the full reading-mode arc — toggle ON, hover peek, edge-arrow and ArrowRight paging, reload persistence, toggle OFF — with per-step screenshots saved to `docs/superpowers/reviews/assets/2026-04-22-slice-R4/flow-<step>.png`. Current asset folder contains only T10's `reading-mode-off.png` and `reading-mode-on.png`.

A regression nit is flagged below; it does not on its own block approval but should be fixed alongside the above.

## Rubric

| # | Item | Result |
|---|---|---|
| 1 | pytest + vitest green, no regressions | PASS (1250 backend / 275 frontend) — with caveat: unhandled exception surfaces during `App.test` mount via the permissive `fetch=[]` stub because the new `progress` useMemo dereferences `body.chapter.paragraphs_anchored.length` without the `?? []` guard used elsewhere. Tests still pass (Vitest doesn't fail on unhandled errors), but it's a real defensive regression vs. the pre-R4 `paragraphs_anchored ?? []` pattern at line 51. |
| 2 | Dev-server renders reader without console errors in both modes | PASS (AC Playwright tests don't report console errors; flow-reader-end-to-end.spec.ts still asserts no console errors on prior flows) |
| 3 | No env/config drift | PASS (frontend-only, no backend/config touched) |
| 4 | Every PRD AC visibly satisfied | PASS in DOM/behavior; PARTIAL on visual fidelity — ambient gradient omitted (see Finding 1) |
| 5 | No scope creep | PASS |
| 6 | Per-slice Playwright gate green | PASS — `cd frontend && npx playwright test slice-R4-reading-mode` → 12/12 in 5.6s |
| 7 | End-to-end flow spec with step screenshots | FAIL — not present |

## Per-AC verification

All 12 PRD acceptance criteria are covered by `frontend/e2e/slice-R4-reading-mode.spec.ts` and pass:

- **AC1** pill accessible name, `data-state` off→on, on state contains `Reading` + `✓` — PASS
- **AC2** click flips `data-reading-mode` on `[data-testid="reading-screen"]` between `off`/`on` — PASS
- **AC3** top bar opacity 0.55, margin-column `aria-hidden="true"` + computed opacity 0 — PASS
- **AC4** pacing label matches `/^stave (one|…|ten|\d+) · of …$/i` — PASS
- **AC5** `page-arrow-left` + `page-arrow-right` visible — PASS
- **AC6** progress-hairline inner width is numeric `%` — PASS
- **AC7** legend contains `ASKED` / `NOTED` / `ENTITY` — PASS
- **AC8** chrome testids absent when off; margin visible — PASS
- **AC9** reload restores per-book on-state — PASS
- **AC10** two books isolated under route change — PASS
- **AC11** hover `[data-kind="note"]` ≥150ms → `note-peek` with body; mouseleave hides — PASS
- **AC12** toggle twice leaves no residual chrome and no peek on hover (listeners torn down) — PASS

## Design-fidelity cross-check (handoff §4)

| Handoff detail | Status |
|---|---|
| Top bar dims to 0.55 | Implemented |
| Margin column slides out (opacity 0, translateX 40px, 260ms) | Implemented (`MarginColumn` `hidden` prop) |
| Book widens (max-width 1100 → 1240) and centers | Partial — stage width already `min(1240px, 100%)` unconditionally; no transition between two widths |
| **Ambient paper radial gradient + 420ms transition** | **Missing** |
| Stave pacing label, italic serif, uppercase, letter-spacing 1.4px | Implemented (`PacingLabel.tsx`) |
| Edge page-turn arrows, faint circular, 48px | Implemented (`PageTurnArrow.tsx`) |
| Thin 3px progress hairline at bottom, accent foreground | Implemented (`ProgressHairline.tsx`) |
| Legend `ASKED · NOTED · ENTITY` with color samples | Implemented (`ReadingModeLegend.tsx`) |
| Note-peek popover beneath spread | Implemented (`NotePeekPopover.tsx`) |
| Toggle pill shape + colors | Implemented (`ReadingModeToggle.tsx`) |

## Findings

### Blocker 1 — Ambient gradient not applied
`frontend/src/screens/ReadingScreen.tsx` sets the outer `<div className="br">` background to `var(--paper-0)` unconditionally (line ~400) and never alters the stage background based on `mode`. Handoff §4 mandates the radial gradient on mode-on with a 420ms `cubic-bezier(.2,.7,.2,1)` transition. Fix: gate `background` on `mode` (or drive via a CSS class toggled on `[data-reading-mode="on"]`) and add a transition on `background`.

Suggested fix (illustrative):
```tsx
style={{
  minHeight: "100vh",
  background: mode === "on"
    ? "radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)"
    : "var(--paper-0)",
  transition: "background 420ms cubic-bezier(.2,.7,.2,1)",
}}
```

### Blocker 2 — End-to-end flow spec missing (T11)
Create `frontend/e2e/flow-reader-reading-mode.spec.ts` that follows the evaluator-specified steps and writes `flow-01-mode-off.png` … `flow-06-mode-off.png` into `docs/superpowers/reviews/assets/2026-04-22-slice-R4/`. Must verify:
- ambient gradient applied (post-fix — computed `background-image` contains `radial-gradient`);
- pacing label, both arrows, progress hairline, legend visible; margin `aria-hidden="true"`;
- hover noted sentence → peek appears after 150ms, hides on mouseleave;
- left/right arrow button clicks + `ArrowRight` key both advance the spread and update hairline width;
- reload persists state per bookId;
- toggle OFF removes chrome and margin `aria-hidden` clears.

Commit as `Slice R4 T11: end-to-end flow validation`.

### Nit — Defensive guard regression in `progress` useMemo
`ReadingScreen.tsx:325` reads `body.chapter.paragraphs_anchored.length` without the `?? []` guard used elsewhere at line 51 (`paginate(chapter.paragraphs_anchored ?? [], box)`). When the chapter object is malformed (e.g., `App.test.tsx` stubs `fetch` to return `[]`), this throws an unhandled React render error. Vitest logs:

```
TypeError: Cannot read properties of undefined (reading 'length')
  at ReadingScreen (src/screens/ReadingScreen.tsx:325:62)
```

Tests don't fail (Vitest treats unhandled errors as warnings), but this is a real regression vs. the pre-R4 defensive pattern. Fix: `const totalParagraphs = (body.chapter.paragraphs_anchored ?? []).length;` and guard `current.right ?? []` / `current.left ?? []`.

## Strengths

- Clean separation: hook, 6 presentational components, minimal integration surface in `ReadingScreen`.
- `useReadingMode` is tight — per-book key, malformed-JSON tolerance, cross-bookId re-read on effect, all covered by unit tests.
- Hover delegation is properly torn down on mode-off (AC12 proves no leak).
- Playwright gate is 1:1 with PRD ACs and runs in under 6 s.
- Tests colocate with components; naming is consistent with R1–R3.

## Screenshots

T10's `reading-mode-off.png` and `reading-mode-on.png` captured at `docs/superpowers/reviews/assets/2026-04-22-slice-R4/`. Full per-step flow screenshots are pending T11.

## Required for APPROVE re-review

1. Implement ambient paper gradient on mode-on with 420ms transition (design handoff §4).
2. Add T11 end-to-end flow spec + per-step screenshots per evaluator instructions; run green.
3. (Nice) Restore `?? []` defensive guards in the new `progress` useMemo to match the pre-R4 pattern.

Re-run the Playwright R4 gate and the new flow spec, confirm backend + frontend unit suites remain green, then request re-review.

---

## REVISE re-evaluation — 2026-04-22

**Verdict:** APPROVE

### Fix verification
- Ambient gradient: PASS — `ReadingScreen.tsx:399` applies `radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)` when reading-mode is on and `none` when off; `ReadingScreen.tsx:408` sets `transition: "background 420ms cubic-bezier(.2,.7,.2,1)"`, matching the README §4 spec exactly.
- Flow spec: PASS — `frontend/e2e/flow-reader-reading-mode.spec.ts` T11 passes (15/15 Playwright tests green including slice-R4 + flow-reader suites; 275/275 Vitest). Screenshots present at `docs/superpowers/reviews/assets/2026-04-22-slice-R4/`: `flow-01-toggled-on.png`, `flow-02-note-peek.png`, `flow-03-page-turned.png`, `flow-04-toggled-off.png`.
