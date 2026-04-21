# Frontend Integration via 5-Agent Pipeline — Design Spec

**Date:** 2026-04-21
**Owner:** Jeffrey Krapf
**Status:** Approved design; ready for implementation plan

## Problem

The BookRAG backend is complete through 7 pipeline stages and exposes a FastAPI surface (`/upload`, `/status`, `/query`, `/graph`, etc.). A Claude-designed frontend handoff lives in the repo at `design-handoff/project/` as unbuilt React JSX + `tokens.css` with three screens (Library, Reading+Chat, Upload); `design-handoff/README.md` is the handoff instructions from Claude Design (read pixel-perfect, don't render in browser unless asked). No frontend scaffold exists in the repo. A thin set of new backend endpoints is also missing (`GET /books`, chapter serving).

The goal is to integrate the handoff into a working app, end-to-end, without accumulating scope drift or skipping verification.

## Solution: 5-agent pipeline, run once per vertical slice

Each pipeline run delivers one shippable, merge-able slice. The pipeline runs four times total, in the order listed in §4.

### 1. Agent map

| Role | Subagent type | Input | Output artifact |
|---|---|---|---|
| Spec/PRD | `general-purpose` (prompted as PRD writer) | Slice goal, handoff files, backend snapshot | `docs/superpowers/specs/YYYY-MM-DD-slice-N-<name>.md` |
| Planner | `Plan` | PRD | `docs/superpowers/plans/YYYY-MM-DD-slice-N-<name>-plan.md` |
| Tester | `general-purpose` + TDD skill injected | Plan + PRD | Failing tests committed to repo |
| Generator | `voltagent-core-dev:fullstack-developer` | Plan + PRD + failing tests | Code that makes tests pass, committed |
| Evaluator | `superpowers:code-reviewer` | PRD + Plan + diff | `docs/superpowers/reviews/YYYY-MM-DD-slice-N-review.md` + verdict (APPROVE / REVISE / REJECT) |

`YYYY-MM-DD` is the slice's kickoff date, not necessarily the project kickoff date.

Rationale: `Plan`, `fullstack-developer`, and `code-reviewer` map cleanly to their roles. No dedicated "PRD writer" or "test-first writer" agent exists, so `general-purpose` is used for those, with strong prompts and skill injection.

### 2. Artifact contract between agents

Each agent reads prior artifacts from disk rather than inheriting conversation context. This keeps context windows clean and makes any step replayable.

```
docs/superpowers/
├── specs/YYYY-MM-DD-slice-N-<name>.md      ← Spec agent writes
├── plans/YYYY-MM-DD-slice-N-<name>-plan.md ← Planner writes, references spec
└── reviews/YYYY-MM-DD-slice-N-review.md    ← Evaluator writes verdict

<repo>/
├── frontend/**/*.test.tsx   ← Tester commits failing tests
├── tests/test_*.py           ← Tester commits failing Python tests
└── <code changes>            ← Generator commits passing implementation
```

### 3. Orchestration and checkpoints

The orchestrator (me, the main Claude session) chains the five agents per slice:

1. Dispatch Spec agent → wait → **user checkpoint** (approve PRD before proceeding)
2. Dispatch Planner → wait → **user checkpoint** (approve plan before proceeding)
3. Dispatch Tester → wait → surface the committed failing tests
4. Dispatch Generator → wait → surface the passing implementation
5. Dispatch Evaluator → wait → surface verdict

Loop handling:
- Evaluator returns REVISE → loop back to Generator with review findings attached
- Evaluator returns REJECT → loop back to Planner with review findings attached
- Evaluator returns APPROVE → slice is done, commit and move to next slice

Checkpoints land only after Spec and Plan. The Test / Generate / Evaluate steps chain through autonomously; the user is surfaced only on verdicts, not on every handoff.

### 4. Slice order (four runs total)

| # | Slice | New backend work | Why this order |
|---|---|---|---|
| 1 | Scaffold + Library screen | `GET /books` (list from `data/processed/*/pipeline_state.json`) | Vite/React/TS setup, `tokens.css` port, and API client stub are prerequisites for everything. Library is the natural landing page; the already-ingested Christmas Carol proves the loop end-to-end. |
| 2 | Upload screen + pipeline status | None — reuses existing `POST /books/upload` and `GET /status` | Low backend risk, exercises polling + real-time UI. Lets the user ingest a new book. |
| 3 | Reading screen + chapter serving | `GET /books/{id}/chapters`, `GET /books/{id}/chapters/{n}` (from `data/processed/{id}/resolved/`); wires `POST /progress` | Biggest UI piece (spoiler blur, margin chat shell). Needs the scaffold and a way to navigate in from Library. |
| 4 | Chat + query wiring | Optional SSE streaming for `/query`; otherwise reuses existing `POST /query` | Builds on the Reading-screen container. Streaming is optional polish. |

Each slice should land in 1–2 hours of agent time and end with a working, merge-able commit.

### 5. Evaluator acceptance rubric

Evaluator approves a slice only if all five hold:

1. All new tests pass; no existing tests regress (`pytest -v` clean + frontend test command clean).
2. Dev server starts and the target screen renders without console errors.
3. No new backend CORS or auth configuration drift; any new env vars are documented.
4. Every acceptance criterion in the slice's PRD is visibly satisfied in the built UI.
5. No scope creep vs the slice's PRD — extra features, refactors, or abstractions are grounds for REVISE.

### 6. Out of scope

- Authentication, multi-user, persistence of progress across devices (single-user M4 Pro Mac per CLAUDE.md).
- Mobile responsive layouts — desktop-first only; mobile is a future slice if needed.
- SSR, Next.js, or any framework beyond Vite + React + TS.
- Dark mode polish beyond what `tokens.css` already provides.
- Any changes to the ingestion pipeline itself (locked decisions per CLAUDE.md).

### 7. Success criteria for the whole project

- A new user can: open the dev server → see Library (Christmas Carol visible) → upload a new EPUB → watch pipeline stages complete → open the book → read → ask chat questions constrained by reading progress.
- All four slices merged to `main` with passing tests.
- Every slice has an approved PRD, plan, and evaluator verdict on disk.

## Open risks

- **Cognee pre-1.0 flakiness** — the existing `add_data_points` is best-effort and query falls back to disk. If the Generator or Evaluator surfaces a Cognee regression on slice 4, we defer SSE streaming and ship the non-streaming path.
- **Handoff JSX has no build config** — Generator in slice 1 must port, not copy, the JSX into a TS/Vite-compatible form. Tester catches this by asserting the dev server starts.
- **Agent context windows** — large slices may exceed a single agent's useful context. Mitigation: slice boundaries in §4 are deliberately small; if a PRD exceeds ~2k words, decompose further before dispatching the Planner.

## Next step

Invoke the `superpowers:writing-plans` skill to produce the implementation plan for this pipeline design — specifically, the orchestrator logic and the per-slice artifact templates.
