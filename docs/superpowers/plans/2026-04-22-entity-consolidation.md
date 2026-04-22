# Plan 3 — Entity consolidation post-pass

**Priority:** MEDIUM — valuable, but value is only measurable after Plans 1 and 2.
**Blocked by:** Plan 1 (determinism) and Plan 2 (triplet embedding + validation).
**Date:** 2026-04-22
**Branch target:** fresh branch off main after Plans 1 and 2 merge
**Estimated effort:** half a day (~4 hours)
**Status:** ready to execute once prior plans are merged

## Problem

Our chat shows the same entity three times. Example from Christmas Carol eval, question "Who is Scrooge?":

1. "Scrooge — a miserly old man who is visited by ghosts on Christmas Eve..."
2. "Scrooge — A character who experiences a transformation..."
3. "Scrooge — A wealthy, cold-hearted businessman who dislikes Christmas..."

All three are legitimate DataPoints from different extraction batches. Each captures the character at a different point in the narrative, but the user sees three source cards for "what Scrooge is" when there should be one. This is the exact problem Cognee's `consolidate_entity_details.txt` prompt solves — and their pattern is directly portable.

**Why it isn't trivially "just dedup by name":** entity descriptions legitimately change across chapters. A chapter-1 Scrooge description is not the same record as a chapter-3 Scrooge description; both must remain accessible to a reader at the right point. Consolidation must respect chapter bounds.

## Goal

Add a post-extraction consolidation pass that, for each `(entity_type, entity_name, last_known_chapter)` group with 2+ DataPoints, merges them into a single canonical record. Preserves chapter provenance. Never crosses chapter-bucket boundaries (hard spoiler-safety invariant).

## Architecture

### Where the pass runs

Between `extract_enriched_graph` (LLM extraction + Plan 2 validation) and `add_data_points` (persistence). This keeps the consolidated records as the authoritative output; the raw per-batch extraction is preserved in `batches/batch_NN/extracted_datapoints.json` for traceability, but disk writes use the consolidated set.

### Grouping rule (the spoiler-safe version)

```
for each entity E in extraction.characters + .locations + .factions + .themes:
    key = (E.type, E.name, E.last_known_chapter)
    groups[key].append(E)

for each group with len > 1:
    canonical = consolidate(group)
    replace all members with canonical in the extraction
```

The key includes `last_known_chapter` explicitly. This is the invariant that keeps the pass spoiler-safe: we NEVER merge a ch.5 Scrooge with a ch.1 Scrooge. Each chapter-bucket produces its own canonical snapshot. A reader at ch.1 retrieves the ch.1 snapshot; a reader at ch.5 retrieves the ch.5 snapshot (which is the ch.1 content plus new developments).

Relationships are NOT consolidated in this plan. Plan 2's validation already deduplicates by `(source, relation, target)`. Relationships carry their own chapter info and need different merging logic; defer to a future slice if needed.

### Consolidation via LLM

Small dedicated prompt — `prompts/consolidate_entity_prompt.txt`, structured like Cognee's but BookRAG-specific:

```
You are consolidating multiple descriptions of the same entity extracted from
adjacent chapters of a book. Produce ONE clean description that keeps every
important detail without duplication.

Entity: {{ entity_type }} named "{{ entity_name }}"
Visible at chapter: {{ last_known_chapter }}

Candidate descriptions from the same chapter bucket:
{% for d in descriptions %}
{{ loop.index }}. {{ d }}
{% endfor %}

Rules:
- Output ONE description, 1-3 sentences.
- Preserve every factual detail mentioned in any candidate.
- Do NOT introduce facts not present in the candidates.
- Do NOT mention events from after chapter {{ last_known_chapter }}. If a
  candidate foreshadows (e.g., "will later be redeemed"), drop that clause.
- Write in neutral present tense, not narrative voice.

Return only the consolidated description text, no JSON, no quotes.
```

The `last_known_chapter` constraint is load-bearing for spoiler safety — even if the LLM sees descriptions that reference future events, the prompt must suppress them in the output.

### Structured output or string?

Keep it simple: return a plain string. We merge by replacing the first group member's `description` with the consolidated text, keeping its other fields (`name`, `first_chapter`, `last_known_chapter`, `aliases`, etc.), and drop the rest of the group. `first_chapter` becomes the min across merged members; `last_known_chapter` stays at the group key (which was already shared).

## Acceptance criteria

1. `prompts/consolidate_entity_prompt.txt` exists with the Jinja template above, tested with `tests/test_extraction_prompt.py::TestConsolidationPrompt` for required placeholders and safety rules ("do NOT mention events after chapter").
2. `pipeline/cognee_pipeline.py` gains `async def consolidate_entities(extraction: ExtractionResult) -> ExtractionResult`. Uses `LLMGateway.acreate_structured_output` with a simple text response model (or bypasses structured output for a plain string completion — pick whichever the LLMGateway supports cleanly).
3. `run_bookrag_pipeline` calls `consolidate_entities` between `extract_enriched_graph` and `add_data_points`. Gated by `BOOKRAG_CONSOLIDATE_ENTITIES: bool = True` config flag; when off, the pass is a no-op (tests cover both modes).
4. Unit tests in `tests/test_cognee_pipeline.py::TestEntityConsolidation`:
   a. Single entity per key → no LLM call, no-op
   b. Two entities same (type, name, last_known_chapter) → one LLM call, result has 1 entity with consolidated description
   c. Two entities with DIFFERENT `last_known_chapter` → NOT merged (spoiler-safety invariant)
   d. Consolidation preserves `first_chapter = min(group)` and `last_known_chapter = group.key`
   e. LLM failure → fall back to keeping the first entity's description unchanged; log warning
5. Spoiler-safety test: `tests/test_spoiler_filter.py::TestConsolidationDoesNotLeak`. Construct a fixture with two extracted Scrooge records, one at `last_known_chapter=1`, one at `last_known_chapter=3`. After consolidation, assert a ch.1 reader querying through `load_allowed_nodes(cursor=1)` sees ONLY the ch.1 description and never text from the ch.3 record.
6. Re-extract Christmas Carol with Plan 1 + Plan 2 + Plan 3. Record the before/after entity count and the representative consolidated descriptions for Scrooge, Bob Cratchit, Marley.
7. Eval A/B:
   - baseline (flag off): matches the Plan-2 post-consolidation numbers.
   - consolidation (flag on): should reduce "redundant sources" without dropping entity_recall.
8. `pytest` stays green.

## Data contracts

No HTTP API changes. Internal `ExtractionResult` stays the same shape; the pass mutates in place (or returns a modified copy).

Config:
- `BOOKRAG_CONSOLIDATE_ENTITIES: bool = True` default. Can be disabled for fast re-extracts that don't need the cleanup.

New prompt template:
- `prompts/consolidate_entity_prompt.txt` (one-per-call, Jinja-rendered).

## Tasks

### T1. Write the consolidation prompt + prompt tests (~30 min)

- New file `prompts/consolidate_entity_prompt.txt` per the template above.
- Tests in `tests/test_extraction_prompt.py::TestConsolidationPrompt`:
  - Required placeholders: `{{ entity_name }}`, `{{ entity_type }}`, `{{ last_known_chapter }}`, `{{ descriptions }}`.
  - Spoiler-safety language: contains phrases "do NOT mention events after" AND "chapter {{ last_known_chapter }}".
  - No foreshadowing: contains "drop that clause" or "suppress" for future-tense clauses.
  - Output format instruction: plain text, no JSON.

### T2. Helper for grouping + merging (~30 min)

- `_group_entities_for_consolidation(extraction) -> dict[key, list[entity_dict]]`
- `_merge_group(group, consolidated_description) -> entity_dict` — takes first member, replaces description, updates `first_chapter` to the min, keeps everything else.
- Pure functions, no LLM. Fully unit-testable.

### T3. Consolidation orchestrator (~60 min)

- `async def consolidate_entities(extraction: ExtractionResult) -> ExtractionResult`
- For each group with `len > 1`, render the prompt, call `LLMGateway.acreate_structured_output` (or plain-text completion), merge, replace.
- Respect a soft concurrency cap (`asyncio.Semaphore(5)` or similar) so we don't fire 20 LLM calls at once.
- On any LLM call failure, fall back to keeping the first member's description and log at WARNING.
- Tests per acceptance criteria 4a–4e.

### T4. Wire into `run_bookrag_pipeline` (~15 min)

- Insert between extraction and `add_data_points`. Gate by `config.consolidate_entities`.
- Test: patch the consolidation function, verify it's called in the right order, with the right input, and its output is what gets persisted.

### T5. Spoiler-safety regression test (~30 min)

- New test in `tests/test_spoiler_filter.py::TestConsolidationDoesNotLeak`. Fixture with two Scrooge records at different `last_known_chapter`. Write them through a simulated pipeline that runs consolidation, then load via `load_allowed_nodes(cursor=1)`. Assert: returned record's description contains ch.1 text only; no text unique to the ch.3 record appears.

### T6. Re-extract + eval A/B (~45 min)

- Re-extract Christmas Carol (deterministic, validated, consolidated).
- Run eval in both modes (flag on vs off — both through the SAME re-extract; the flag gates only a parameter of `run_bookrag_pipeline`, not persistence).
- Compare against Plan 2's baseline.

### T7. Summary + commit (~20 min)

- `evaluations/results/2026-04-XX-plan3-summary.md`. Expected findings:
  - Entity count reduced (duplicates merged).
  - `answer_similarity` roughly flat or slightly improved.
  - Source-card count per query drops visibly.
  - Spoiler safety 1.000 (mandatory).
- Single commit.

## Risks and mitigations

- **Risk: The LLM introduces facts not in any candidate.** Every "a miserly old man" + "a wealthy businessman" consolidation is a chance for the LLM to add a third trait from training data. **Mitigation:** the prompt explicitly forbids it; the test should construct a fixture where the LLM is tempted (well-known character) and verify no smuggled facts appear. If the test flakes, strengthen the prompt.
- **Risk: Consolidation crosses chapter buckets by accident.** Catastrophic for spoiler safety. **Mitigation:** T5 is a dedicated spoiler test. The grouping key includes `last_known_chapter` — if a bug ever removes that field from the key, T5 fails loudly.
- **Risk: Ingestion cost balloons.** Each chapter bucket with N duplicates is 1 extra LLM call. For Christmas Carol that's roughly 5 extra calls per re-ingest. For Red Rising's ~45 chapters it's maybe 20–40 extra calls. **Mitigation:** config flag defaults to on but is easy to disable. Cost is reported in the summary.
- **Risk: The "first member's description" fallback on LLM failure is inconsistent with other group members.** **Mitigation:** the fallback is documented in the plan and tested; users can rerun ingestion if needed. Not a correctness issue.
- **Risk: Relationships get stranded if we rename an entity.** If entity A's canonical name is "Scrooge" and one member had `name="Ebenezer Scrooge"` that's referenced by a relationship, the relationship now points at a missing entity. **Mitigation:** the grouping key is `(type, name, ...)` so only entities with EXACTLY the same name are merged. Entity alias resolution is a separate concern (BookNLP handles it in principle).

## Why this is third priority

Plan 1 makes the eval reliable. Plan 2 fixes the "relationships missed by keyword search" problem. Plan 3 fixes the "three Scrooge cards" problem. Each is easier to measure once the prior one ships.

If we skipped Plan 1, consolidation's eval would show ±5% deltas on any metric and we couldn't tell if the consolidation is good. If we skipped Plan 2, consolidation might look like a regression because the keyword path was already averaging out the duplicate-source problem by returning less relevant results anyway.

Done in order, each plan's effect is cleanly separable.

## Exit criteria

- Duplicate Scrooge/Cratchit/Marley entries in Christmas Carol's extracted_datapoints.json are collapsed to one per chapter bucket.
- Consolidated descriptions don't reference future-chapter events (spoiler test passes).
- Eval `answer_similarity` within ±0.02 of Plan 2 baseline — consolidation should NOT hurt quality, and may slightly help by reducing duplicate noise in the synthesis context.
- Source-card count per eval question visibly lower (inspect per-question detail in the eval output).
- `pytest` green.
