# Overnight Extraction Ablation — Design Doc

**Date:** 2026-04-23
**Author:** overnight autonomous run
**Source:** `docs/research/2026-04-22-book-to-kg-sota.md` (Phase A + Phase B items)

## Goal

Run eight sandboxed A/B experiments overnight, each implementing one
recommended contribution from the research doc, and measure impact on
three axes: **node quality**, **node quantity**, **searchability**.
Deliver by morning: per-experiment branch + `metrics.json` + `diffstat.md`,
and a root `SUMMARY.md` with ranked recommendations.

## Scope — 8 experiments

| ID | Branch | Research item | Axis |
|---|---|---|---|
| E1 | `exp/gleaning` | Phase A #1 — gleaning loop with logit-biased yes/no | quantity, quality |
| E2 | `exp/quote-provenance` | Phase A #2 — `source_quote` field + substring validator | quality (faithfulness) |
| E3 | `exp/chunk-750` | Phase A #3 — chunk_size 1500→750, re-ablate | quantity |
| E4 | `exp/booknlp-cluster-id` | Phase A #5 — propagate BookNLP cluster_id into Character DataPoints | quality (dedup) |
| E5 | `exp/forbidden-verb` | Phase A #6 — realis + forbidden-verb constraint in prompt | quality (precision) |
| E6 | `exp/relationship-enum` | Phase A #8 — signed valence + 7-type enum on Relationship | quality (schema) |
| E7 | `exp/two-hop-retrieval` | Phase A #10 — two-hop neighbor fetch in spoiler_filter | searchability |
| E8 | `exp/bundle-A123` | Fresh worktree combining E1 + E2 + E3 | all three |

Out of scope (and reason each): prompt caching / async / strict JSON (no
quality signal); extractor-version cache and Kuzu upstream (infra, not
measurable); reranker and PPR (Phase B, want Phase A base graph first);
structured PlotEvent args (schema change needs more design).

## Per-experiment agent pipeline

Each experiment runs this pipeline; all subagents dispatched from the
orchestrator on host; all code execution happens inside a Docker
sandbox.

```
Research (Explore) → Plan (Plan) → Tests (general-purpose)
  → Generate (python-pro or fullstack-developer)
  → Review (code-reviewer)  [≤2 REVISE loops, then review_failed]
  → Ingest + Eval (orchestrator, inside container)
  → metrics.json + diffstat.md
```

- Research: read affected files, the research doc's section, Cognee
  0.5.6 source when relevant. Produces `research.md`.
- Plan: converts research into numbered tasks with failing-test specs.
  Produces `plan.md`.
- Tests: commits failing unit/integration tests.
- Generate: implements until tests pass. If generator reports "plan is
  wrong", loop back to Plan once (max); if still failing, abort with
  `status: plan_rejected`.
- Review: approves when tests pass AND implementation matches the plan.
  Reviewer does NOT second-guess eval metrics — the eval harness is the
  quality judge.
- Ingest + Eval: runs in container on Christmas Carol (no Red Rising).

## Sandbox (Docker) strategy

Claude Code subagents cannot run inside containers (architectural
constraint — they spawn as host siblings of the orchestrator). So the
hybrid model:

- **Host:** orchestrator, subagent dispatch, generator file edits into
  the worktree.
- **Container (per experiment):** pytest, ingestion pipeline (BookNLP,
  Cognee, LLM calls), eval harness, any generated scripts.

This contains the real risk surface — arbitrary code execution via
ingestion subprocesses, test runners, or generator-authored scripts —
while keeping the agent layer unchanged.

### Container hardening

- `--memory=8g --memory-swap=8g --cpus=4 --pids-limit=1024`
- `--read-only --tmpfs /tmp --tmpfs /home/app/.cache`
- `--cap-drop=ALL --security-opt=no-new-privileges`
- `--user 1000:1000` (non-root inside)
- `--network=bridge` (egress for OpenAI; no inbound)
- Bind mounts scoped: `<worktree>:/app:rw` + `<data-dir>:/app/data/processed/cc:rw`
- Secrets via `-e OPENAI_API_KEY=...` (not mounted `.env`)
- Image pinned: `python:3.10-slim-bookworm@sha256:<digest>`
- Docker Desktop on macOS runs containers in a Linux VM — extra layer

## Gold fixtures (committed to `main` before kickoff)

- `tests/golden/christmas_carol_qa.json` — 15 hand-written Q/A, 5 each of
  (entity-centric, relationship, thematic). Each item has
  `{question, reference_answer, cursor_chapter, must_not_mention}`
  where `must_not_mention` catches spoilers past the cursor.
- `tests/golden/wikidata_snapshot.json` — cached Wikidata Q62879
  characters + locations, pinned to 2026-04-23 retrieval (so queries
  don't flake if Wikidata is down overnight).
- `scripts/overnight/judge.py` — LLM-judge rubric prompt + Claude API
  call; calibrated by running 3 calibration items on `main` before
  kickoff and confirming judge output is stable.

## Three-axis metrics (same across all experiments)

### Quantity
- `unique_entities_per_type`: dict[type, int]
- `total_extraction_count`: int
- `dedup_rate`: 1 − unique/total
- `entity_refs_per_chapter`: float (GraphRAG comparison metric)

### Quality
- `wikidata_char_recall`: matched / 8
- `wikidata_loc_recall`: matched / 1
- `quote_provenance_pass_rate`: optional, only for E2 and E8
- `llm_judge_faithfulness`: dict[category, (yes, partial, no)] over a
  20-DataPoint sample
- `alias_duplicate_pairs`: count of (Fred, Scrooge's nephew)-style
  same-entity-different-name pairs (detected by SBERT cosine ≥ 0.85 on
  name + description)

### Searchability
- Per-question score via LLM-judge: Correct / Partial / Wrong / Spoiler
- `answer_accuracy`: (Correct + 0.5 × Partial) / 15
- `precision_at_3`: average over questions — fraction of top-3 returned
  nodes that are judged relevant
- `spoiler_leak_rate`: count(Spoiler verdicts) / 15, with cursor at
  chapter 2

## Orchestration

### Pre-flight (runs once, blocks kickoff on failure)
1. Verify Docker daemon, caffeinate, `.env` with `OPENAI_API_KEY`, main
   branch clean, full Playwright suite green (we're not touching
   frontend but regressions matter).
2. Build `bookrag-exp:overnight` image.
3. Commit gold fixtures + judge script + Dockerfile to main.
4. Run baseline experiment end-to-end — baseline ingest on main,
   baseline eval, produce `baseline/metrics.json`. If any metric is
   `NaN` or the script crashes, abort before any real experiment runs.

### Per-experiment execution
```
1. git worktree add ../bookrag-E<n> -b exp/<name>
2. write research.md via Explore agent
3. write plan.md via Plan agent
4. write failing tests via general-purpose agent, commit
5. loop: generate → test-in-container → review
   - max 2 REVISE cycles
   - max 1 plan-rejection loop (back to Plan)
6. docker run <image> ingest.sh on CC
7. docker run <image> eval.sh → metrics.json
8. write diffstat.md (git diff main..HEAD --stat + 200-word summary)
9. git commit; do NOT merge to main
10. update overnight_status.json
```

### Hard caps
- Per-stage timeouts: Research 10m, Plan 5m, Tests 10m, Generate 30m,
  Review 10m, Ingest 15m, Eval 10m (total ≤ 90m per experiment)
- Per-experiment cost cap: $3 OpenAI
- Global cost cap: $20 OpenAI (kill switch via `scripts/overnight/kill.sh`)
- Sleep prevention: orchestrator launched under `caffeinate -dis`

### Order (smallest-first to validate harness early)
baseline → E3 → E1 → E2 → E8 → E6 → E5 → E4 → E7

## Failure policy

- Any stage timeout: abort experiment, mark `status: <stage>_timeout`,
  preserve worktree, move to next.
- Generator exhausts REVISE loops: `status: review_failed`.
- Plan rejected twice: `status: plan_rejected`.
- OpenAI infra failure (5xx, rate limit): retry with exponential
  backoff (3 attempts); if still failing, `status: infra_failure`.
- Cost cap hit: abort remaining experiments, write SUMMARY.md with
  partial results, mark skipped experiments `status: budget_exhausted`.
- Docker daemon crash: abort, write SUMMARY.md noting infra failure.

All failures preserve the worktree so morning inspection is possible.

## Deliverables (morning)

- `SUMMARY.md` on `main` with:
  - Experiment comparison matrix (rows = experiments, cols = key metrics)
  - Ranking per axis
  - **Recommendation section** — which subset to ship, which to defer,
    which to re-run with larger gold set
  - Per-experiment links
- Per-experiment worktree with:
  - `research.md`
  - `plan.md`
  - `metrics.json`
  - `diffstat.md` (git diff summary + 200-word prose)
  - Generator commits
  - Container logs in `overnight_logs/E<n>/`
- Root: `overnight_status.json` (final status)
- Root: `overnight_logs/` directory with per-stage logs

## Not doing

- Auto-merge anything to main. User decides morning-of.
- Red Rising ablation. CC only for overnight; RR is next sprint.
- Slack/email notifications. Single-machine run; user checks on wake.
- Phase B / Phase C items. Out of scope for overnight.
- Full regression test suite per experiment. Each experiment's gated
  tests must pass; whole-suite regressions flagged in SUMMARY.md but
  don't block write-up.

## Open questions

None. Proceeding with implementation.
