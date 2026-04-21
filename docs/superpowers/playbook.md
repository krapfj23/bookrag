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
