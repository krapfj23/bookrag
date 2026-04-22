# Phase A Stage 2 — Prompt Engineering

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.

**Goal:** Tighten what the LLM extracts. Realis (item 9) filters out hypothetical/counterfactual events; gleaning loop (item 1) recovers missed entities on a cheap second pass.

**Tech:** Pydantic v2, Cognee LLMGateway, existing extraction path.

**Source:** `docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md` § Stage 2.

**Baseline:** 1119 passing tests at start of Stage 2.

---

## Task order

1. **Task 1:** `PlotEvent.realis` field + prompt REJECT/ACCEPT few-shot block.
2. **Task 2:** Retrieval-side filter: skip `realis != "actual"` when assembling spoiler-filtered context.
3. **Task 3:** Gleaning loop on `extract_enriched_graph` with `max_gleanings` config (default 1).

Tasks 1-2 are independent of Task 3. All three ship independently.

---

### Task 1 — Realis field + forbidden-verb prompt constraint

**Why:** ACE 2005's "realis" distinguishes actualized events from hypothetical/counterfactual/planned. Keeping only `actual` events prevents the LLM from extracting "Scrooge wondered if Marley would return" as a plot event.

**Files:**
- Modify: `models/datapoints.py` (`PlotEvent.realis: Literal["actual","generic","other"] = "actual"`; same on `EventExtraction`)
- Modify: `prompts/extraction_prompt.txt` (REJECT/ACCEPT block)
- Test: `tests/test_datapoints.py`

**Acceptance:** 3 negative examples in prompt; LLM labels clearly hypothetical events as `other`.

---

### Task 2 — Retrieval-side realis filter

**Why:** Keep `other`-realis events in the graph (useful for questions like "what does Scrooge fear?") but default-filter them out of canonical plot retrieval.

**Files:**
- Modify: `pipeline/spoiler_filter.py` (new `realis_filter: bool = True` arg; drop `realis != "actual"` from the allowed node set when True)
- Test: `tests/test_spoiler_filter.py`

---

### Task 3 — Gleaning loop

**Why:** GraphRAG's `max_gleanings=1` shows +30–50% relation recall without a proportional cost spike (once prompt caching is on, which Stage 0 set up the concurrency for; OpenAI gives server-side prefix caching automatically).

**Files:**
- Modify: `models/config.py` (add `max_gleanings: int = 1`)
- Modify: `pipeline/cognee_pipeline.py` (`_extract_one` wraps the first LLM call in a gleaning loop: CONTINUE_PROMPT to glean more; LOOP_PROMPT asks yes/no; stop on "N" first char or at `max_gleanings` cap)
- Test: `tests/test_cognee_pipeline.py`

**Acceptance:**
- `max_gleanings=0` preserves current behavior (single LLM call per chunk).
- `max_gleanings=1` produces two LLM calls per chunk; second call returns extra entities that are deduped with the first on `(name, type)` key.
- Loop stops on `LOOP_PROMPT` returning "N"-first-char; stops at cap; never exceeds `max_gleanings + 1` calls.

---

## Out of scope

- Chunk-size ablation (item 3) — separate Stage 3.
- Two-hop spoiler filter (item 10) — Stage 4.
- Cache + strict-mode (items 6/12 deferred from Stage 1) — their own slice.
