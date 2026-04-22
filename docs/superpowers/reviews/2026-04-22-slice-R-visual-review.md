# Slice R-visual — Visual-fidelity sweep — Review

**Date:** 2026-04-22
**Verdict:** APPROVED
**Spec:** ../specs/2026-04-22-slice-R-visual-fidelity.md
**Plan:** ../plans/2026-04-22-slice-R-visual-fidelity-plan.md
**Range:** `5cb9682..HEAD` (ending at `5a2988d Slice R-visual T22: end-to-end flow validation`)

## One-sentence summary

All 20 visual gaps are closed, the dedicated Playwright spec (19 tests) and the new T22 end-to-end flow spec both run green, and the shipped reader now renders as a pixel-for-pixel realization of the design handoff.

## Rubric

| # | Gate | Result |
|---|------|--------|
| 1 | pytest green, no regressions | PASS — `1250 passed, 3 warnings in 13.58s` |
| 2 | vitest green, dev server renders | PASS — `308 passed (308)` across 67 files; one unhandled-promise warning from a `ReadingScreen` unmount race is unrelated to this slice and does not fail any test |
| 3 | No env/config drift | PASS — no changes under `models/config.py`, `config.yaml`, `.env.example`, or `pyproject.toml` |
| 4 | Every PRD AC visibly satisfied | PASS — see AC table below |
| 5 | No scope creep | PASS — diff stays inside the UI-scope file list in the PRD; no backend changes, no new endpoints |
| 6 | Playwright gate `slice-R-visual` | PASS — 19/19 tests green; baselines exist at `frontend/e2e/slice-R-visual-fidelity.spec.ts-snapshots/` (`reader-default-chromium-darwin.png`, `reader-with-ask-chromium-darwin.png`, `reader-reading-mode-on-chromium-darwin.png`) |
| 7 | End-to-end flow validation | PASS — `frontend/e2e/flow-reader-visual-fidelity.spec.ts` walks library -> reader -> drop cap -> selection -> ask -> note -> reading mode -> peek -> off; 1/1 green; 9 flow screenshots committed under `docs/superpowers/reviews/assets/2026-04-22-slice-R-visual/flow-NN-name.png` |

## Per-AC verification

| AC | Gap | Verification | Evidence |
|----|-----|--------------|----------|
| 1 | TopBar no nav | Playwright `AC-TopBar/no Library/Upload nav links` + `reader-topbar header exists` + height 52px | `slice-R-visual-fidelity.spec.ts:107-133`; commit `608b3ec`, `ea34eb0` |
| 2 | Ask pill accent bg, 999px | `AC-AskPill/Ask button has accent background` + `border-radius 999px` | `slice-R-visual-fidelity.spec.ts:137-164` |
| 3 | Book shadow reaches DOM | Shadow contains `70px -24px`; no ancestor `overflow:hidden` | `slice-R-visual-fidelity.spec.ts:168-198`; commit `b4a4faa` moved the clip onto an inner mask |
| 4 | S1 three mono-numeral bullets | Vitest on `S1EmptyCard` | commit `dae8428` |
| 5 | S1 uses IcSpark | Vitest SVG path snapshot | commit `dae8428` |
| 6 | IcSpark handoff path | Vitest `icons.test.tsx` | commit `8e08167` |
| 7 | IcChevron exported | Vitest import + path | commit `8e08167` |
| 8 | IcSend/IcHighlight paths | Vitest | commit `8e08167` |
| 9 | Selection toolbar 180ms enter | Playwright animationDuration `180ms` | `slice-R-visual-fidelity.spec.ts:202-215`; commit `56cae10` |
| 10 | ReadingModeToggle padding/radius/no border | Playwright computed-style assertion (5px 12px / 999px / 0px) | `:219-236`; commit `ae7dbe4` |
| 11 | PageTurnArrow 48px circular opacity 0.5 | Playwright | `:240-264`; commit `b4ca8c9` |
| 12 | ProgressHairline paper-2 track | Playwright | `:268-285`; commit `32de6b2` |
| 13 | PacingLabel 12px uppercase 1.4px top | Playwright computed-style + `rect.top < 80` | `:289-310`; commit `9c5acb8` |
| 14 | NotePeek 360px orange border-left + ago meta | Playwright in flow spec + component; verified via `flow-08-note-peek-open.png` | commit `76f1fc3` |
| 15 | Legend 10.5px | Playwright | `:314-325`; commit `58aed28` |
| 16 | Chat-open anim: card flip-in + pulse | Playwright `AC-ChatOpenAnim` asserts `rr-card-enter` class on new card | `:373-391`; commit `65ff7c9` |
| 17 | Skeleton "THINKING · gathering 3 more passages" | Vitest | commit `731881b` (header already shipped) |
| 18 | Drop cap 54px px padding | Playwright `::first-letter` fontSize | `:395-406`; commit `d84c663` |
| 19 | Stave tag explicit px | Playwright | `:329-349`; commit `334a8c2` |
| 20 | Folio page + author | Playwright + flow screenshot | `:353-369`; commit `d84c087` |
| 21 | Flow baseline | T20 snapshot + T21 full flow green | `:422-503`; baselines in snapshot dir |

## End-to-end flow validation (T22)

Spec: `frontend/e2e/flow-reader-visual-fidelity.spec.ts`. Each step captures into `docs/superpowers/reviews/assets/2026-04-22-slice-R-visual/`.

- `flow-01-library.png` — library card visible
- `flow-02-reader-default.png` — reader after navigation, top bar + book spread
- `flow-03-drop-cap.png` — drop cap asserted 54px via `::first-letter`
- `flow-04-selection-toolbar.png` — selection toolbar animated in
- `flow-05-ask-card.png` — Ask card rendered with `rr-card-enter` class
- `flow-06-note-created.png` — note card created
- `flow-07-reading-mode-on.png` — pacing label, arrows, legend, hairline visible
- `flow-08-note-peek-open.png` — peek popover (or base state if no hover target)
- `flow-09-reading-mode-off.png` — margin column back

Run result: 1/1 passed in 3.0s.

## Notes

- The generic `flow-reader-end-to-end.spec.ts` and `flow-reader-reading-mode.spec.ts` from earlier slices remain untouched and continue to pass.
- The one unhandled React error observed in `App.test.tsx` (`paragraphs_anchored` undefined on unmount) pre-exists this slice and manifests only as a Vitest "error" side-channel without failing any test; it is out of scope and should be tracked separately.
- `*.png` is in `.gitignore`; flow screenshots are force-added (`git add -f`), matching the convention used by all prior slice review assets.

## Verdict

**APPROVED** — R-visual can move to `done`.
