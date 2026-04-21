# Frontend Integration Slice Backlog

Canonical status tracker for the four slices defined in `specs/2026-04-21-frontend-integration-agent-pipeline-design.md`. Update the Status column and Artifacts links at the end of each slice.

| # | Slice | Status | Kickoff | PRD | Plan | Review |
|---|---|---|---|---|---|---|
| 1 | Scaffold + Library screen | generate | 2026-04-21 | [spec](specs/2026-04-21-slice-1-scaffold-library.md) | [plan](plans/2026-04-21-slice-1-scaffold-library-plan.md) | |
| 2 | Upload screen + pipeline status | not started | | | | |
| 3 | Reading screen + chapter serving | not started | | | | |
| 4 | Chat + query wiring | not started | | | | |

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
