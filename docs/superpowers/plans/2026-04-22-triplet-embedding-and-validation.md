# Plan 2 — Triplet embedding at ingestion + extraction-time triplet validation

**Priority:** HIGH — highest-impact low-blast-radius idea from the pipeline research.
**Blocked by:** Plan 1 (extraction determinism). Without deterministic baselines this slice's eval deltas are unreadable.
**Date:** 2026-04-22
**Branch target:** fresh branch off main after Plan 1 merges
**Estimated effort:** 3–4 hours
**Status:** ready to execute once Plan 1 is merged

## Problem

Two separate issues identified in the research pass (`docs/research/cognify-pipeline.md`):

1. **Keyword-match retrieval misses relationships.** Our current triplet path in `main.py:_answer_from_allowed_nodes` scores relationships by keyword overlap with the question. For Christmas Carol, "why does Marley's ghost visit?" only hits `Marley → warns → Scrooge` if the question contains `marley` or `warns` — semantic matches are missed. Cognee's `brute_force_triplet_search.py` uses vector embeddings on the concatenated triplet text for exactly this reason.
2. **Extracted relationships sometimes reference entities not in the same batch's node set.** Our spoiler filter catches this at retrieval time (both-endpoints rule in `load_allowed_relationships`), but the on-disk artifacts still carry near-duplicate or orphan edges. A per-batch validation pass at extraction time keeps the raw data clean.

Both are additive, share the same commit, and reinforce each other: validation produces cleaner triplets, cleaner triplets embed better.

## Goal

1. Enable `embed_triplets=True` on the `add_data_points` task so Cognee persists a triplet vector index alongside the entity/relation graph.
2. Add a triplet-validation step to `extract_enriched_graph` that drops orphan or duplicate relationships before persistence.
3. Measure answer-quality deltas against Plan 1's deterministic baseline.

## Architecture

### Part A — embed_triplets=True (one-line change, plus a retrieval path)

`pipeline/cognee_pipeline.py:518` currently calls:

```python
Task(add_data_points, task_config={"batch_size": 30}),
```

Cognee's `add_data_points` (at `cognee/tasks/storage/add_data_points.py:27-32`) accepts an `embed_triplets: bool = False` kwarg. When `True`, after the main node/edge persistence it calls `_create_triplets_from_graph(nodes, edges)` → constructs `Triplet(from_node, edge, to_node)` DataPoints → embeds the concatenated triplet text → indexes in a dedicated vector collection.

**The one-line change:**

```python
Task(add_data_points, task_config={"batch_size": 30}, embed_triplets=True),
```

Cognee's `Task` forwards **kwargs to the executable (verified against `task.py:39-41`).

**The retrieval path** — once embeddings exist, `main.py:_answer_from_allowed_nodes` gets a second path (gated by `BOOKRAG_USE_TRIPLETS=1`) that calls `cognee.search(..., query_type=SearchType.INSIGHTS)` or `brute_force_triplet_search()` directly on the triplet vector index. Returns `Edge` objects. We then post-filter those edges through `load_allowed_relationships` to enforce spoiler safety.

**The spoiler-safety contract is preserved** because the filter is applied to the RETRIEVAL OUTPUT, not to what's embedded. The vector index can contain any relationship; what reaches the LLM still passes through `load_allowed_relationships`.

### Part B — triplet validation at extraction time

In `extract_enriched_graph` (in `pipeline/cognee_pipeline.py`), after the LLM returns an `ExtractionResult` and before we hand it to `add_data_points`:

```python
def _validate_relationships(extraction: ExtractionResult) -> ExtractionResult:
    """Drop relationships with missing endpoints or duplicate (src, rel, tgt) keys.

    Invariants after this pass:
      1. For every Relationship r, r.source_name and r.target_name both appear
         as a `name` field on at least one Character/Location/Faction in the
         same ExtractionResult.
      2. No two Relationships share (source_name, target_name, relation_type).
         When duplicates are detected, keep the one with the longer
         description (more information-dense).
    """
    ...
```

The validation runs BEFORE `add_data_points` persists anything, so disk artifacts stay clean. It also makes the A/B eval more honest — currently our `Scrooge → employs → Bob Cratchit (twice)` case counts as two sources for the same relationship.

## Acceptance criteria

1. `pipeline/cognee_pipeline.py:run_bookrag_pipeline` passes `embed_triplets=True` to the `add_data_points` Task. Confirm via a unit test that patches `cognee.modules.pipelines.run_pipeline` and asserts the `Task` it receives was constructed with `embed_triplets=True`.
2. New helper `_validate_relationships(extraction: ExtractionResult) -> ExtractionResult` lives in `pipeline/cognee_pipeline.py` and is called immediately after the LLM returns the extraction (before any persistence side-effects).
3. Unit tests in `tests/test_cognee_pipeline.py::TestTripletValidation`:
   a. orphan source → relationship dropped
   b. orphan target → relationship dropped
   c. duplicate (src, rel, tgt) → only one survives; the one with the longer description
   d. valid unique relationship → passes through unchanged
4. New retrieval path in `main.py` behind `BOOKRAG_USE_TRIPLETS=1` that performs vector triplet search via Cognee. Falls back to the existing keyword path when Cognee's search is unavailable (e.g., the `SearchPreconditionError` we saw in earlier runs). The fallback logic must be tested.
5. Spoiler-safety pinned by existing test `tests/test_query_endpoint.py::TestTripletRetrieval::test_triplet_flag_on_still_spoiler_safe` — it must still pass. Any regression here is a ship-blocker.
6. Re-extract Christmas Carol with Plan 1's deterministic config + new validation pass. Record the new triplet count; expect fewer than pre-Plan-2 (due to validation) but semantically richer.
7. Run the A/B eval against the new data. Both modes (keyword + vector) get a run. Record deltas in `evaluations/results/2026-04-XX-triplets-vector.md` with the Plan-1 deterministic baseline as reference.
8. `pytest` stays green. Full suite >= baseline + 6 new tests.

## Data contracts

No API changes at the HTTP layer. Internal-only:

- `QueryResultItem.entity_type` already supports `"Relationship"`; no schema change needed.
- The vector index is a Cognee-internal collection named (per Cognee) `Triplet_text` or similar. We do not need to name it or manage it directly.

Config:
- New `BOOKRAG_EMBED_TRIPLETS: bool = True` on `BookRAGConfig`. Default `True` so re-ingests automatically create the vector index. If a book was ingested before this plan shipped, its vector index is missing; the retrieval path must detect that and fall back to keyword scoring. Loud warning in logs.

## Tasks

### T1. Config field + default on (~10 min)

- Add `embed_triplets: bool = True` to `BookRAGConfig`.
- Update `configure_cognee` to not pass it (Cognee doesn't care; we pass per-Task).
- Test: `test_config.py::test_embed_triplets_default_true`.

### T2. Pipeline: pass `embed_triplets=True` into `add_data_points` Task (~15 min)

- Modify the Task construction at `pipeline/cognee_pipeline.py:518`. Use `config.embed_triplets` so it's overridable.
- Test: patch `cognee.modules.pipelines.run_pipeline`, assert the Task was constructed with the kwarg.

### T3. Extraction validation pass (~45 min)

- Implement `_validate_relationships` with the two invariants.
- Tests per the acceptance criteria — 4 new cases.
- Wire it into `extract_enriched_graph` at the point where the ExtractionResult is assembled from LLM output.

### T4. Retrieval: add vector path (~60 min)

- In `main.py:_answer_from_allowed_nodes`, when `BOOKRAG_USE_TRIPLETS=1`, branch on whether Cognee's vector search is available.
- If available: call `cognee.search(query_text=question, query_type=SearchType.INSIGHTS, datasets=[book_id])` and transform the returned Edge objects into `QueryResultItem`s. Post-filter through `load_allowed_relationships`.
- If unavailable (`SearchPreconditionError` or equivalent): fall back to the existing keyword path. Log a warning once.
- Tests:
  - mock `cognee.search` success → assert vector results appear in response with `entity_type="Relationship"` and arrow content.
  - mock `cognee.search` raising `SearchPreconditionError` → assert keyword fallback produces results and there's no 500.
  - the post-filter is still invoked: put an orphan relationship in the mocked vector return, assert it's absent from the final response.

### T5. Re-extract + eval (~30 min, requires live OpenAI and an initialized Cognee DB)

- Delete `data/processed/christmas_carol_e6ddcd76/batches` (or move it aside; the re-extract script already backs up).
- `scripts/reextract_book.py christmas_carol_e6ddcd76` — produces cleaner, validated relationships + populates the vector index.
- `scripts/eval_query.py --mode triplets --out evaluations/results/2026-04-XX-triplets-vector.md` with `BOOKRAG_USE_TRIPLETS=1`.
- `scripts/eval_query.py --mode baseline --out evaluations/results/2026-04-XX-baseline-post-plan2.md` for comparison (flag off, unchanged keyword path).

### T6. Summary report + commit (~30 min)

- `evaluations/results/2026-04-XX-plan2-summary.md` — comparison against Plan 1 deterministic baseline. Include:
  - Triplet count before/after validation.
  - Answer-similarity delta with vector triplets vs keyword triplets vs baseline.
  - Spoiler-safety still 1.000 (ship-blocker check).
  - Latency deltas (vector search adds ~100–200ms per query).
- Single commit with all changes + tests + eval results.

## Risks and mitigations

- **Risk:** Cognee's vector search requires DB setup (`SearchPreconditionError` from earlier runs). **Mitigation:** the fallback to keyword retrieval is MANDATORY in T4. If vector search never works on our environment, we still get the validation cleanup from Part B.
- **Risk:** `embed_triplets=True` significantly increases ingestion cost (each relationship gets an embedding call). **Mitigation:** measure at T5; report in the summary. For Christmas Carol's ~8 relationships per batch the cost is negligible. For Red Rising's ~hundreds of relationships it could be real.
- **Risk:** Triplet validation drops a LLM-extracted relationship that's actually correct because the LLM mentioned an entity without creating a Character for it. **Mitigation:** log dropped relationships during validation. If the drop rate exceeds 20%, the LLM isn't being prompted to extract all endpoints — a prompt fix, not a validation fix. The acceptance tests include this.
- **Risk:** The post-filter ordering is wrong and vector results bypass the spoiler gate. **Mitigation:** `test_triplet_flag_on_still_spoiler_safe` from the existing test suite is a hard gate. If it fails, the slice doesn't ship.

## Why this is second priority

Ordering matters. Doing Plan 2 before Plan 1 means the A/B numbers we record in T6 are noisy and can't be trusted to reflect the actual improvement from vector triplets. Plan 1 takes 1–2 hours and makes every subsequent measurement reliable. Plan 2 takes 3–4 hours and measurably improves answer quality — but only measurably if Plan 1 landed first.

## Exit criteria

- Vector triplet index populated in the Cognee store for Christmas Carol.
- Validation pass dropping 0–3 relationships per batch (typical noise) without affecting legitimate ones.
- Eval `answer_similarity` on questions tagged `relational` in the fixture improves by ≥ 0.05 cosine compared to Plan 1 deterministic baseline (soft; report absolute numbers regardless).
- Eval `source_chapter_precision` unchanged or better.
- Spoiler safety = 1.000 on every question in both modes.
- `pytest` green.
