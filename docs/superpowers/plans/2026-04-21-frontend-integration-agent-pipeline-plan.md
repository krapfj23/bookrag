# Frontend Integration Agent Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 5-agent pipeline infrastructure (prompt templates, orchestrator playbook, slice backlog, directory skeleton) needed to execute the four frontend-integration slices defined in `docs/superpowers/specs/2026-04-21-frontend-integration-agent-pipeline-design.md`.

**Architecture:** Markdown-driven artifact pipeline. The main Claude session is the orchestrator; it dispatches five subagents sequentially per slice via the Agent tool. Every handoff between agents is a committed markdown file on disk (spec → plan → tests → code → review), so nothing relies on inherited chat context and every step is replayable. Agent prompts are parameterized templates living in `docs/superpowers/templates/`.

**Tech Stack:** Markdown, the Agent tool (with `subagent_type` selectors `general-purpose`, `Plan`, `voltagent-core-dev:fullstack-developer`, `superpowers:code-reviewer`), git, Python/FastAPI on the backend, Vite + React + TS on the frontend (introduced in slice 1).

---

## File Structure

Everything created by this plan is documentation or directory scaffolding — no production code. Each file has one purpose:

- `docs/superpowers/plans/.gitkeep` — keeps the plans directory tracked before any plan lands in it.
- `docs/superpowers/reviews/.gitkeep` — same, for evaluator verdicts.
- `docs/superpowers/templates/.gitkeep` — same, for prompt templates.
- `docs/superpowers/slices.md` — canonical backlog: four slices, status, links to artifacts, updated once per slice.
- `docs/superpowers/templates/01-prd-agent-prompt.md` — parameterized prompt for the Spec/PRD agent.
- `docs/superpowers/templates/02-planner-agent-prompt.md` — parameterized prompt for the Planner agent.
- `docs/superpowers/templates/03-tester-agent-prompt.md` — parameterized prompt for the Tester agent.
- `docs/superpowers/templates/04-generator-agent-prompt.md` — parameterized prompt for the Generator agent.
- `docs/superpowers/templates/05-evaluator-agent-prompt.md` — parameterized prompt for the Evaluator agent.
- `docs/superpowers/playbook.md` — the orchestrator's runbook: per-slice loop, checkpoint rules, failure handling, pre/post-slice tasks.

No existing files are modified.

---

### Task 1: Create directory skeleton

**Files:**
- Create: `docs/superpowers/plans/.gitkeep`
- Create: `docs/superpowers/reviews/.gitkeep`
- Create: `docs/superpowers/templates/.gitkeep`

- [ ] **Step 1: Create the three directories with placeholder files**

Run:
```bash
mkdir -p docs/superpowers/plans docs/superpowers/reviews docs/superpowers/templates
touch docs/superpowers/plans/.gitkeep docs/superpowers/reviews/.gitkeep docs/superpowers/templates/.gitkeep
```

- [ ] **Step 2: Verify the structure**

Run: `ls docs/superpowers/`
Expected output includes: `plans  reviews  specs  templates`

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/.gitkeep docs/superpowers/reviews/.gitkeep docs/superpowers/templates/.gitkeep
git commit -m "Scaffold docs/superpowers directories for agent pipeline"
```

---

### Task 2: Write slice backlog

**Files:**
- Create: `docs/superpowers/slices.md`

- [ ] **Step 1: Write the backlog file**

Write this exact content to `docs/superpowers/slices.md`:

```markdown
# Frontend Integration Slice Backlog

Canonical status tracker for the four slices defined in `specs/2026-04-21-frontend-integration-agent-pipeline-design.md`. Update the Status column and Artifacts links at the end of each slice.

| # | Slice | Status | Kickoff | PRD | Plan | Review |
|---|---|---|---|---|---|---|
| 1 | Scaffold + Library screen | not started | | | | |
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/slices.md
git commit -m "Add slice backlog tracker"
```

---

### Task 3: Write PRD agent prompt template

**Files:**
- Create: `docs/superpowers/templates/01-prd-agent-prompt.md`

- [ ] **Step 1: Write the template**

Write this exact content to `docs/superpowers/templates/01-prd-agent-prompt.md`:

````markdown
# PRD Agent Prompt Template

> Template for the Spec/PRD agent (Agent role 1 of 5). Orchestrator substitutes `{{slice_number}}`, `{{slice_name}}`, `{{slice_goal}}`, and `{{kickoff_date}}` before dispatch. Agent is `general-purpose`.

---

You are the **Spec/PRD agent** for BookRAG slice {{slice_number}}: **{{slice_name}}**.

## Your job

Produce a short, concrete PRD that the Planner agent can turn directly into an implementation plan. No prose bloat, no re-stating architecture — reference documents instead of quoting them.

## Inputs — read these in order

1. `docs/superpowers/specs/2026-04-21-frontend-integration-agent-pipeline-design.md` — the overall pipeline and slice definitions. You are writing the slice-{{slice_number}} PRD.
2. `docs/superpowers/slices.md` — backlog with backend work required per slice.
3. `design-handoff/README.md` — the design-handoff instructions from Claude Design.
4. `design-handoff/project/` — all JSX, tokens.css, and HTML files. Focus on the JSX and tokens.css. The HTML files are reference only.
5. `main.py` — current FastAPI routes relevant to this slice.
6. `CLAUDE.md` — project constraints (locked decisions section especially).

## Slice goal

{{slice_goal}}

## Deliverable

Write to `docs/superpowers/specs/{{kickoff_date}}-slice-{{slice_number}}-{{slice_name}}.md` with this exact structure:

```markdown
# Slice {{slice_number}} — {{slice_name}} PRD

**Date:** {{kickoff_date}}
**Parent spec:** ../specs/2026-04-21-frontend-integration-agent-pipeline-design.md

## Goal
One sentence.

## User stories
Bullet list. Each story is "As a reader, I can X so that Y." Max 5.

## Acceptance criteria
Numbered list. Each item is a verifiable assertion (e.g., "The Library page lists Christmas Carol with its cover, title, author, and page progress"). The Evaluator will check these one-by-one.

## UI scope
Which components from design-handoff/project/*.jsx are in scope for this slice? Name them explicitly. Mark anything out of scope.

## Backend scope
Which endpoints exist already (reference by METHOD /path)? Which must be added? For each new endpoint, give: path, method, request shape, response shape, data source.

## Data contracts
TypeScript-style interfaces for every payload the frontend will consume in this slice. Include only fields actually used.

## Out of scope
Bullet list of things deliberately not in this slice.

## Open questions
Bullet list. If none, write "None."
```

## Rules

- Do NOT write implementation steps. That is the Planner's job.
- Do NOT invent endpoints or data that don't exist in the backend. If you need new data, put it under **Backend scope**.
- Keep the PRD under 500 words excluding the data-contract block.
- Acceptance criteria must be observable without reading code — the Evaluator will run the app and check each one.
- When in doubt, prefer fewer features in scope. YAGNI.

## Output

After writing the file, report back a one-paragraph summary of what's in scope and what's deferred. Do not paste the PRD content into your response; the orchestrator will read the file.
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/templates/01-prd-agent-prompt.md
git commit -m "Add PRD agent prompt template"
```

---

### Task 4: Write Planner agent prompt template

**Files:**
- Create: `docs/superpowers/templates/02-planner-agent-prompt.md`

- [ ] **Step 1: Write the template**

Write this exact content to `docs/superpowers/templates/02-planner-agent-prompt.md`:

````markdown
# Planner Agent Prompt Template

> Template for the Planner agent (Agent role 2 of 5). Orchestrator substitutes `{{slice_number}}`, `{{slice_name}}`, `{{kickoff_date}}`, and `{{prd_path}}` before dispatch. Agent is `Plan`.

---

You are the **Planner agent** for BookRAG slice {{slice_number}}: **{{slice_name}}**.

## Your job

Turn the PRD into a bite-sized, TDD implementation plan. Output must conform to the writing-plans skill standards: exact file paths, exact code in every step, exact shell commands with expected output, frequent commits.

## Inputs — read these in order

1. `{{prd_path}}` — the slice PRD.
2. `docs/superpowers/specs/2026-04-21-frontend-integration-agent-pipeline-design.md` — pipeline design for context.
3. `design-handoff/project/*.jsx` and `design-handoff/project/tokens.css` — source of truth for the UI.
4. `main.py`, `models/`, `pipeline/` — backend layout for any backend additions.
5. `CLAUDE.md` — project constraints.

## Deliverable

Write to `docs/superpowers/plans/{{kickoff_date}}-slice-{{slice_number}}-{{slice_name}}-plan.md` using the writing-plans skill format. Each task must have:

- Exact file paths (`Create:`, `Modify:`, `Test:`)
- A failing-test step with the full test code
- A run-the-test step with the expected failure message
- A minimal-implementation step with the full code
- A run-the-test step with expected PASS
- A commit step with the exact commit command and message

## Rules

- Scope is strictly the PRD acceptance criteria. No extras.
- Split into tasks of 30–90 minutes of work each. The Generator will execute one task at a time.
- Tests first, every time. Backend uses pytest; frontend uses Vitest + React Testing Library.
- For the frontend scaffold task (slice 1 only): use Vite with the `react-ts` template. Install `vitest`, `@testing-library/react`, `@testing-library/jest-dom`. Port `design-handoff/project/tokens.css` verbatim into `frontend/src/styles/tokens.css`.
- Never duplicate a JSX file verbatim. Port to TypeScript and split into per-component files under `frontend/src/components/`.
- Every task ends with a commit.

## Output

After writing the plan, report back: total task count, which backend files are touched, which frontend files are created. One paragraph.
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/templates/02-planner-agent-prompt.md
git commit -m "Add Planner agent prompt template"
```

---

### Task 5: Write Tester agent prompt template

**Files:**
- Create: `docs/superpowers/templates/03-tester-agent-prompt.md`

- [ ] **Step 1: Write the template**

Write this exact content to `docs/superpowers/templates/03-tester-agent-prompt.md`:

````markdown
# Tester Agent Prompt Template

> Template for the Tester agent (Agent role 3 of 5). Orchestrator substitutes `{{slice_number}}`, `{{slice_name}}`, `{{prd_path}}`, and `{{plan_path}}` before dispatch. Agent is `general-purpose` with TDD discipline.

---

You are the **Tester agent** for BookRAG slice {{slice_number}}: **{{slice_name}}**.

## Your job

Read the plan. Extract every test from every task. Write those tests to disk. Run them. Commit the failing tests. Do NOT write any implementation code.

## Inputs — read these in order

1. `{{plan_path}}` — the slice implementation plan. Source of truth for what tests to write.
2. `{{prd_path}}` — the slice PRD. Cross-reference acceptance criteria.
3. `CLAUDE.md` — test conventions (pytest, loguru).
4. `tests/conftest.py` — existing test fixtures (for backend tests).

## What to do

1. For each task in the plan that defines a test, create the test file at the exact path specified in the plan's `Test:` field.
2. Copy the test code verbatim from the plan — do not improvise.
3. Run the full test suite to confirm only the new tests fail (existing tests must still pass).
4. Commit all new test files in a single commit.

## Rules

- Never write production code. If the plan is missing a test for an acceptance criterion, flag it in your report — do not write the test yourself.
- Never modify existing tests unless the plan explicitly says to.
- Never skip tests. A skipped test is a missing test.
- Commit message: `test: add failing tests for slice {{slice_number}} ({{slice_name}})`.

## Verification before reporting done

Run the test suites:

**Backend:**
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: every pre-existing test still passes; new tests fail with the error message the plan predicted.

**Frontend** (only if slice touches the frontend):
```bash
cd frontend && npm test -- --run 2>&1 | tail -30
```
Expected: new tests fail; previously passing tests still pass.

## Output

Report back:
1. Count of new test files created.
2. Count of new test cases added.
3. The failing test names.
4. Any acceptance criteria in the PRD that had NO corresponding test in the plan (flag, don't fix).
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/templates/03-tester-agent-prompt.md
git commit -m "Add Tester agent prompt template"
```

---

### Task 6: Write Generator agent prompt template

**Files:**
- Create: `docs/superpowers/templates/04-generator-agent-prompt.md`

- [ ] **Step 1: Write the template**

Write this exact content to `docs/superpowers/templates/04-generator-agent-prompt.md`:

````markdown
# Generator Agent Prompt Template

> Template for the Generator agent (Agent role 4 of 5). Orchestrator substitutes `{{slice_number}}`, `{{slice_name}}`, `{{prd_path}}`, and `{{plan_path}}` before dispatch. Agent is `voltagent-core-dev:fullstack-developer`.

---

You are the **Generator agent** for BookRAG slice {{slice_number}}: **{{slice_name}}**.

## Your job

Execute the plan task-by-task. Write the minimal code needed to make each task's failing tests pass. Commit after every task. Stop when every task in the plan is done and every test passes.

## Inputs — read these in order

1. `{{plan_path}}` — the slice plan. Your source of truth for what to build.
2. `{{prd_path}}` — the slice PRD. For acceptance criteria context only.
3. `design-handoff/project/*.jsx` and `design-handoff/project/tokens.css` — source of truth for visual fidelity when porting components.
4. `CLAUDE.md` — project constraints. Respect locked decisions.

## Rules

- One task at a time. Finish a task fully — tests passing, committed — before moving to the next.
- Follow the plan verbatim. If a step says to write specific code, write that code.
- Do not add features, validation, error handling, or abstractions beyond what the plan specifies.
- Do not modify files outside the `Files:` block of the current task.
- When porting JSX to TS: match visual output pixel-perfectly, but don't copy the prototype's structure if a cleaner TS component fits. Split components into per-file modules under `frontend/src/components/`.
- Run tests after every implementation step. If they fail, fix the implementation — do not modify the test.
- Commit with the exact message given in the plan's commit step.

## Verification before reporting done

Run every test suite:

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
cd frontend && npm test -- --run 2>&1 | tail -30   # if frontend exists
```

Expected: ALL tests pass, no collection errors, no regressions.

Start the dev server (foreground verification, do not leave running):
- Backend: `python main.py` — should start without error, GET `/health` should return `{"status": "ok", ...}`.
- Frontend: `cd frontend && npm run dev` — should start without error on port 5173.

## Output

Report back:
1. Every task's commit hash.
2. Final test counts: passing / failing / skipped.
3. Any deviation from the plan and why (should be zero).
4. One screenshot-equivalent description of the built UI per slice (what the user sees when they open the target page).
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/templates/04-generator-agent-prompt.md
git commit -m "Add Generator agent prompt template"
```

---

### Task 7: Write Evaluator agent prompt template

**Files:**
- Create: `docs/superpowers/templates/05-evaluator-agent-prompt.md`

- [ ] **Step 1: Write the template**

Write this exact content to `docs/superpowers/templates/05-evaluator-agent-prompt.md`:

````markdown
# Evaluator Agent Prompt Template

> Template for the Evaluator agent (Agent role 5 of 5). Orchestrator substitutes `{{slice_number}}`, `{{slice_name}}`, `{{prd_path}}`, `{{plan_path}}`, `{{kickoff_date}}`, and `{{diff_ref}}` before dispatch. Agent is `superpowers:code-reviewer`.

---

You are the **Evaluator agent** for BookRAG slice {{slice_number}}: **{{slice_name}}**.

## Your job

Decide whether the Generator's output meets the PRD. Return one of: APPROVE, REVISE, or REJECT. Write your verdict to disk.

## Inputs — read these in order

1. `{{prd_path}}` — the PRD. The acceptance criteria are your rubric.
2. `{{plan_path}}` — the plan. For scope reference only; the PRD binds.
3. `git diff {{diff_ref}}..HEAD` — the code the Generator produced. Read it top to bottom.
4. `docs/superpowers/specs/2026-04-21-frontend-integration-agent-pipeline-design.md` — the rubric in §5.

## Rubric (must all hold for APPROVE)

1. All new tests pass, no regressions (`pytest -v` clean + frontend test command clean — verify yourself).
2. Dev server starts and the target screen renders without console errors.
3. No new CORS / auth config drift; any new env vars are documented.
4. Every PRD acceptance criterion is visibly satisfied in the built UI or verifiable via curl.
5. No scope creep vs the PRD.

## Verdict semantics

- **APPROVE** — all 5 rubric items hold. Slice is done.
- **REVISE** — minor fixes needed (test gap, missed acceptance criterion, small bug). Orchestrator loops back to Generator with your findings.
- **REJECT** — structural issue (plan was wrong, PRD was wrong, slice needs decomposition). Orchestrator loops back to Planner.

## Deliverable

Write to `docs/superpowers/reviews/{{kickoff_date}}-slice-{{slice_number}}-review.md`:

```markdown
# Slice {{slice_number}} Review — {{slice_name}}

**Date:** {{kickoff_date}}
**Verdict:** APPROVE | REVISE | REJECT
**Reviewer:** Evaluator agent (superpowers:code-reviewer)

## Rubric check

1. Tests: PASS | FAIL — <details>
2. Dev server: PASS | FAIL — <details>
3. Config drift: PASS | FAIL — <details>
4. Acceptance criteria: PASS | FAIL — per-criterion check
5. Scope: PASS | FAIL — <details>

## Per-criterion verification

For each acceptance criterion in the PRD, quote it, state PASS/FAIL, and give one-line evidence.

## Findings

If verdict is REVISE or REJECT: numbered list of specific issues and what must change. Each item must be actionable — no "improve quality" vagueness.

## If APPROVE

One-sentence slice summary for the slice backlog.
```

## Rules

- Actually run the tests yourself. Do not trust the Generator's report.
- Actually start the dev server and load the target page yourself (backend: `python main.py` in one terminal; frontend: `cd frontend && npm run dev` in another). If you cannot verify visually from this environment, state that explicitly in finding 2 and base your verdict on test output + diff reading.
- Base verdict on observable behavior, not code style. Style is not a rubric item.
- Be strict on scope creep. If Generator added a feature not in the PRD, verdict is at least REVISE.

## Output

Report back: the verdict, the path of the review file, and the one-sentence summary.
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/templates/05-evaluator-agent-prompt.md
git commit -m "Add Evaluator agent prompt template"
```

---

### Task 8: Write orchestrator playbook

**Files:**
- Create: `docs/superpowers/playbook.md`

- [ ] **Step 1: Write the playbook**

Write this exact content to `docs/superpowers/playbook.md`:

````markdown
# Agent Pipeline Orchestrator Playbook

> Runbook for the main Claude session (the orchestrator) when executing a slice. Read this every time a slice kicks off.

## Pre-slice setup

1. Confirm previous slice (if any) is marked `done` in `docs/superpowers/slices.md`.
2. Set today's date as `{{kickoff_date}}` in all substitutions below.
3. Update `slices.md`: set this slice's Status to `spec`, Kickoff to today.
4. Commit the status change: `git commit -m "Start slice {{slice_number}}: {{slice_name}}"`.

## Per-slice loop

### Step 1 — Dispatch Spec agent

Load `docs/superpowers/templates/01-prd-agent-prompt.md`, substitute `{{slice_number}}`, `{{slice_name}}`, `{{slice_goal}}`, `{{kickoff_date}}`. Dispatch with `subagent_type: general-purpose`.

When the agent returns: read the generated PRD at `docs/superpowers/specs/{{kickoff_date}}-slice-{{slice_number}}-{{slice_name}}.md`. Surface a one-paragraph summary plus the acceptance criteria to the user. **Wait for user approval.**

If approved: update slices.md status to `plan`, commit, proceed. If not approved: loop back, re-dispatch Spec agent with user's feedback appended to the prompt.

### Step 2 — Dispatch Planner agent

Load `02-planner-agent-prompt.md`, substitute `{{slice_number}}`, `{{slice_name}}`, `{{kickoff_date}}`, `{{prd_path}}` (the file the Spec agent wrote). Dispatch with `subagent_type: Plan`.

When the agent returns: read the generated plan. Surface task count + file list to user. **Wait for user approval.**

If approved: update slices.md status to `test`, commit, proceed. If not: re-dispatch with feedback.

### Step 3 — Dispatch Tester agent

Record the current HEAD: `git rev-parse HEAD` — save as `{{diff_ref}}` for later.

Load `03-tester-agent-prompt.md`, substitute `{{slice_number}}`, `{{slice_name}}`, `{{prd_path}}`, `{{plan_path}}`. Dispatch with `subagent_type: general-purpose`.

When the agent returns: verify via `git log --oneline` that only test files were committed. Surface the failing-test names to user. Update slices.md status to `generate`. Proceed without user checkpoint.

### Step 4 — Dispatch Generator agent

Load `04-generator-agent-prompt.md`, substitute `{{slice_number}}`, `{{slice_name}}`, `{{prd_path}}`, `{{plan_path}}`. Dispatch with `subagent_type: voltagent-core-dev:fullstack-developer`.

When the agent returns: verify all tests pass via `pytest tests/ -v` and `cd frontend && npm test -- --run`. Update slices.md status to `review`. Proceed without user checkpoint.

### Step 5 — Dispatch Evaluator agent

Load `05-evaluator-agent-prompt.md`, substitute `{{slice_number}}`, `{{slice_name}}`, `{{prd_path}}`, `{{plan_path}}`, `{{kickoff_date}}`, `{{diff_ref}}`. Dispatch with `subagent_type: superpowers:code-reviewer`.

When the agent returns: read the verdict from the review file.

### Step 6 — Handle verdict

- **APPROVE**: update slices.md Status to `done`, Artifacts links filled in. Commit. Surface the slice summary to user. Done.
- **REVISE**: update slices.md Status to `revise`. Re-dispatch Generator with the review findings appended to its prompt. When Generator returns, loop back to Step 5.
- **REJECT**: update slices.md Status to `reject`. Re-dispatch Planner with the review findings appended. When Planner returns, loop back to Step 3 (tests may need rewriting).

## Loop caps

- Max 2 REVISE iterations before escalating to user. If exceeded, pause and surface the state.
- Max 1 REJECT iteration before escalating. A second REJECT means the slice itself is wrong — decompose.

## Cross-slice rules

- Do not start slice N+1 until slice N is `done`.
- If the Evaluator flagged a regression in an earlier slice's behavior, file it as a fix in the current slice's REVISE loop, not a new slice.
- After all four slices are `done`, write a one-paragraph project summary to `docs/superpowers/reviews/{{final_date}}-project-complete.md` and commit.

## Commit conventions

- Spec agent commit: `docs: slice {{slice_number}} PRD`.
- Planner commit: `docs: slice {{slice_number}} implementation plan`.
- Tester commit: `test: add failing tests for slice {{slice_number}} ({{slice_name}})`.
- Generator per-task commits: use the exact message from the plan's commit step.
- Evaluator commit: `docs: slice {{slice_number}} review verdict ({{verdict}})`.
- Slice-status updates: `chore: slice {{slice_number}} status → {{new_status}}`.

## Never

- Never run two agents in parallel for the same slice. The pipeline is strictly sequential.
- Never skip a checkpoint.
- Never let the Generator modify tests to pass them.
- Never promote a REVISE to APPROVE without re-running the Evaluator.
- Never commit the user's uncommitted work as part of a slice commit. Use `git add <specific files>`, not `git add -A`.
````

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/playbook.md
git commit -m "Add orchestrator playbook"
```

---

### Task 9: Verification sweep

**Files:** none (verification only).

- [ ] **Step 1: Confirm every artifact exists**

Run:
```bash
ls -la docs/superpowers/templates/ docs/superpowers/plans/ docs/superpowers/reviews/ docs/superpowers/specs/ docs/superpowers/playbook.md docs/superpowers/slices.md
```

Expected: five template files (`01-` through `05-`), the playbook, the slices backlog, and the design spec. Plans and reviews directories are empty (`.gitkeep` only).

- [ ] **Step 2: Grep for placeholder leaks**

Run:
```bash
grep -rn "TODO\|TBD\|FIXME\|XXX" docs/superpowers/ 2>&1 | grep -v ".gitkeep"
```

Expected: no matches (empty output). If any match appears, fix the offending template inline and re-commit before proceeding.

- [ ] **Step 3: Verify every template references real paths**

Run:
```bash
grep -n "design-handoff\|main\.py\|CLAUDE\.md" docs/superpowers/templates/
```

Expected: each template references at least one real path. Cross-check with `ls design-handoff/ main.py CLAUDE.md` that those paths exist.

- [ ] **Step 4: Verify templates are internally consistent**

Run:
```bash
grep -n "{{.*}}" docs/superpowers/templates/
```

Expected output lists every placeholder across all five templates. Confirm the playbook's Step-1-through-Step-5 substitution lists cover every `{{...}}` you see.

- [ ] **Step 5: Final commit (marker only)**

```bash
git commit --allow-empty -m "Pipeline infrastructure ready — slice 1 can start"
```

---

## Self-review checklist

Ran this after writing the plan:

1. **Spec coverage** — every section of the design spec is addressed: agent map (Tasks 3–7), artifact contract (Task 1 creates dirs, Task 2 creates backlog), orchestration (Task 8 playbook), slice order (Task 2 backlog), rubric (Task 7 template), out of scope (inherited from spec, not re-stated). No gaps.
2. **Placeholder scan** — no TBD/TODO/FIXME in the plan body. The `{{...}}` tokens in templates are intentional (substituted at dispatch time by the playbook).
3. **Type consistency** — agent role numbering matches across templates (01–05), playbook step numbers match template role numbers, file path conventions (`{{kickoff_date}}-slice-{{slice_number}}-*`) are consistent in specs, plans, reviews, and the playbook.
4. **Scope** — no production code written; this plan only builds the pipeline infrastructure. Each slice produces its own spec, plan, tests, code, and review as downstream artifacts.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-frontend-integration-agent-pipeline-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
