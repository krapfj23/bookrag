# Frontend Integration Slice Backlog

Canonical status tracker for the four slices defined in `specs/2026-04-21-frontend-integration-agent-pipeline-design.md`. Update the Status column and Artifacts links at the end of each slice.

| # | Slice | Status | Kickoff | PRD | Plan | Review |
|---|---|---|---|---|---|---|
| 1 | Scaffold + Library screen | done | 2026-04-21 | [spec](specs/2026-04-21-slice-1-scaffold-library.md) | [plan](plans/2026-04-21-slice-1-scaffold-library-plan.md) | [review](reviews/2026-04-21-slice-1-review.md) |
| 2 | Upload screen + pipeline status | done | 2026-04-21 | [spec](specs/2026-04-21-slice-2-upload-pipeline-status.md) | [plan](plans/2026-04-21-slice-2-upload-pipeline-status-plan.md) | [review](reviews/2026-04-21-slice-2-review.md) ([early](reviews/2026-04-21-slice-2-early-review.md)) |
| 3 | Reading screen + chapter serving | done | 2026-04-21 | [spec](specs/2026-04-21-slice-3-reading-chapter-serving.md) | [plan](plans/2026-04-21-slice-3-reading-chapter-serving-plan.md) | [review](reviews/2026-04-21-slice-3-review.md) |
| 4 | Chat + query wiring | done | 2026-04-21 | [spec](specs/2026-04-21-slice-4-chat-query-wiring.md) | [plan](plans/2026-04-21-slice-4-chat-query-wiring-plan.md) | [review](reviews/2026-04-21-slice-4-review.md) |

## Audit follow-up slices (2026-04-22)

Driven by the backend + security + test + frontend audit. Each slice stands alone; execute in priority order (1 → 4) or in parallel where scope doesn't overlap.

| # | Slice | Status | Kickoff | Spec | Plan |
|---|---|---|---|---|---|
| 1 | Critical security hardening | done | 2026-04-22 | [spec](specs/2026-04-22-slice-1-security-hardening.md) | [plan](plans/2026-04-22-slice-1-security-hardening.md) |
| 2 | Backend refactor (split god-modules) | done | 2026-04-22 | [spec](specs/2026-04-22-slice-2-backend-refactor.md) | [plan](plans/2026-04-22-slice-2-backend-refactor.md) |
| 3 | Test quality uplift | done | 2026-04-22 | [spec](specs/2026-04-22-slice-3-test-quality-uplift.md) | [plan](plans/2026-04-22-slice-3-test-quality-uplift.md) |
| 4 | Frontend refactor + hardening | spec | 2026-04-22 | [spec](specs/2026-04-22-slice-4-frontend-hardening.md) | [plan](plans/2026-04-22-slice-4-frontend-hardening.md) |

## Reader rebuild slices (2026-04-22)

Driven by `design_handoff_bookrag_reader/README.md` (V3 Inline margin cards, ambitious reading mode). Replaces `ReadingScreen.tsx` in place. Cards persist in localStorage only. Pagination is client-side DOM-measured. Evaluator gates on Playwright (see template 05 rubric item 6). The audit slice 4 (frontend-hardening) is deferred until after this rebuild.

| # | Slice | Status | Kickoff | Spec | Plan | Review |
|---|---|---|---|---|---|---|
| R1 | Reading surface + sentence anchors | done | 2026-04-22 | [spec](specs/2026-04-22-slice-R1-reading-surface.md) | [plan](plans/2026-04-22-slice-R1-reading-surface-plan.md) | [review](reviews/2026-04-22-slice-R1-review.md) |
| R1b | Reader fit-and-finish (fixed spread, current-spread cards, chapter advance) | done | 2026-04-22 | [spec](specs/2026-04-22-slice-R1b-fit-and-finish.md) | [plan](plans/2026-04-22-slice-R1b-fit-and-finish-plan.md) | [review](reviews/2026-04-22-slice-R1b-review.md) |
| R2 | V3 Inline margin cards + selection→ask + notes | done | 2026-04-22 | [spec](specs/2026-04-22-slice-R2-cards-and-selection.md) | [plan](plans/2026-04-22-slice-R2-cards-and-selection-plan.md) | [review](reviews/2026-04-22-slice-R2-review.md) |
| R3 | Card states (S1–S7) + O2 overflow | done | 2026-04-22 | [spec](specs/2026-04-22-slice-R3-card-states-and-overflow.md) | [plan](plans/2026-04-22-slice-R3-card-states-and-overflow-plan.md) | [review](reviews/2026-04-22-slice-R3-review.md) |
| R4 | Ambitious reading mode | not started | — | — | — | — |
| R5 | Card detail (edit/delete) | blocked | — | — | — | — |

R5 is blocked pending a design pass (README §2 "Edit/delete cards" flagged as undesigned).

## Status values

- `not started` — no agent has been dispatched yet
- `spec` — PRD agent running or awaiting user checkpoint
- `plan` — Planner running or awaiting user checkpoint
- `test` — Tester running
- `generate` — Generator running
- `review` — Evaluator running
- `revise` — looped back to Generator after REVISE verdict
- `reject` — looped back to Planner after REJECT verdict
- `done` — Evaluator APPROVE, slice merged

## Backend additions per slice

| # | New endpoints | Notes |
|---|---|---|
| 1 | `GET /books` | Lists every directory in `data/processed/` whose `pipeline_state.json` has `ready_for_query: true`. |
| 2 | (none) | Reuses `POST /books/upload` and `GET /books/{id}/status`. |
| 3 | `GET /books/{id}/chapters`, `GET /books/{id}/chapters/{n}` | Serves resolved text from `data/processed/{id}/resolved/`. Wires `POST /books/{id}/progress`. |
| 4 | SSE streaming for `/query` (optional) | Deferred if Cognee regressions surface — ship non-streaming `POST /books/{id}/query`. |
