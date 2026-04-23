# Relationship Rescue — Fallback Resolution Before Drop

**Spec date:** 2026-04-23
**Problem:** Red Rising ingestion dropped **145 of 209** LLM-proposed relationships (~69%) as "orphans" in `_validate_relationships`. A relationship is dropped when either `source_name` or `target_name` doesn't exactly string-match a `name` on a Character/Location/Faction extracted in the same chunk.
**Goal:** Add a cascade of fallback resolution strategies that fire **before** a relationship is dropped, so we retain links the LLM correctly perceived but named inconsistently.

## Failure modes (hypothesized — needs empirical confirmation)

Based on how LLM extraction errs on novels, the 145 Red Rising drops likely decompose roughly as:

| Mode | What the LLM did | Why current validator drops it |
|---|---|---|
| **A. Alias** | `source_name="Darrow"`, `target_name="My Father's Son"` | `Character.aliases = ["My Father's Son"]` exists, but validator only matches `.name` |
| **B. Coref surface form** | `source_name="the boy"`, `target_name="Eo"` | "the boy" doesn't match any `.name`; BookNLP coref maps it to Darrow but validator ignores that |
| **C. Cross-chunk endpoint** | `source_name="Scrooge"` (extracted in chunk 1), `target_name="Tiny Tim"` (extracted in chunk 2) | Validator scope is one chunk; `allowed_names` set is rebuilt per chunk |
| **D. Paraphrase / case / punctuation** | `source_name="A Pitiless Golden Man"` vs stored `"Pitiless Golden Man"` | Exact string match, case/article sensitive |
| **E. Event-endpoint** | `source_name="Darrow"`, `target_name="The Reaping"` (a PlotEvent) | Validator only checks Character/Location/Faction — PlotEvent is not allowed |
| **F. Theme-endpoint** | rare, but `target_name="Hierarchy"` when Theme was extracted | Same — Themes not allowed |
| **G. True hallucination** | Endpoint is a name the LLM invented / misread | Correctly dropped — no entity exists for it anywhere |

We want to keep A–F. G should still die.

## Action item (Phase 0): Instrument before we fix

Before ranking fallback strategies, measure which modes account for the drops. Add a structured drop-log in `_validate_relationships`:

```python
logger.debug(
    "rel_drop book={} chunk_ordinal={} src={!r} tgt={!r} rel={} reason={}",
    book_id, ordinal, rel.source_name, rel.target_name, rel.relation_type, reason,
)
```

Where `reason ∈ {"src_orphan", "tgt_orphan", "both_orphan"}`, and include a post-batch summary `logger.info("rel_drops: src_orphan=X tgt_orphan=Y both_orphan=Z")`. Re-ingest Red Rising (or a subset), tally.

Also persist dropped orphans to `batches/batch_NN/dropped_relationships.json` so we can later replay them after implementing rescues — without re-running the LLM. This is **the single most important deliverable** from this plan, because it lets us measure rescue rate per strategy without another ingestion pass.

## Fallback cascade (cheapest → most expensive)

Insert between "is endpoint in allowed_names?" and "drop as orphan" in `_validate_relationships`. Each tier short-circuits; each logs which tier rescued the relationship for later tuning.

### Tier 1 — Alias match (cheapest; rescues mode A)

Build an **alias index** alongside `allowed_names`:

```python
name_by_alias = {}  # surface form → canonical name
for entity in (characters, locations, factions):
    name_by_alias[entity.name] = entity.name
    for alias in getattr(entity, "aliases", []):
        name_by_alias[alias] = entity.name
```

If `rel.source_name not in allowed_names` but `rel.source_name in name_by_alias`, rewrite `rel.source_name = name_by_alias[rel.source_name]` and proceed. Same for target.

Expected rescue rate: 10–25% of orphans (aliases are already populated on many extracted Characters). Zero cost at runtime; no new LLM calls.

### Tier 2 — Case/punctuation normalization (cheapest; rescues mode D)

Normalize with a single canonical form: `lower().strip().translate(no_punctuation).collapse_whitespace()`. Build `allowed_norm = {norm(name): canonical_name ...}`. On miss, try `norm(endpoint)`.

Expected rescue rate: 5–10%. Cheap. Risk of false merges minimal if we require norm match *plus* token overlap ≥ 80%.

### Tier 3 — Batch scope (rescues mode C)

Today the validator runs per-chunk. Switch it to run at the `_merge_chunk_extractions` output — i.e., after all chunks in a batch are merged but before Cognee persistence. Then `allowed_names` covers the entire batch, not a 3-paragraph window. This is a one-line site change in `cognee_pipeline.py:755` — move the call.

Expected rescue rate: 15–30%. Red Rising batches are ~3 chapters, which is where most "Darrow talks to Cassius" cross-references happen.

Risk: none, validation semantics are identical, just wider scope.

### Tier 4 — BookNLP coref cluster match (rescues mode B)

`Character.booknlp_coref_id` is already stored. BookNLP also produces a `coref.json` mapping every mention (surface form + span) to its cluster. Build a secondary alias index from BookNLP:

```python
booknlp_alias_index = {
    surface_form: cluster_canonical_name
    for mention in booknlp_mentions
    for surface_form in [mention.text]
}
```

On alias-miss, case-miss, and batch-miss, try the BookNLP index. "the boy" → cluster 607 → `"Darrow"` → rewrite endpoint.

Expected rescue rate: 10–20%. Requires loading BookNLP output into the validator context — currently it's only loaded upstream for the parenthetical-insertion pass. A modest plumbing change; no new compute.

### Tier 5 — Event endpoints (rescues mode E)

Extend `allowed_names` to include `extraction.events` when the relationship `relation_type` is one of a PlotEvent-appropriate subset (e.g., `ALLY`, `ENEMY`, `ACQUAINTANCE` → no; `MENTOR`, `SUBORDINATE`, `FAMILY`, `ROMANTIC` → no; all make little sense with events). **Safer choice:** add a new relation type `PARTICIPANT` (and possibly `WITNESS`, `PERPETRATOR`) with explicit Character↔PlotEvent semantics, and route event-endpoint relationships through that. Mode-E orphans with valid narrative relation types are probably real misclassifications by the LLM; forcing them into PARTICIPANT preserves the link rather than dropping it.

Expected rescue rate: 5–15%. Schema change needed (new enum entries). Downstream /query synthesis would see additional triplets like `"Darrow → participant → The Reaping"`.

Risk: dilutes the original 10-type narrative relation set. Could also be done as a separate `EventParticipation` DataPoint type to keep `Relationship` clean.

### Tier 6 — Fuzzy similarity (last resort before drop; rescues residual mode D + near-misses)

If all exact/alias/coref lookups miss, fall back to token-set similarity (e.g., `rapidfuzz.token_set_ratio ≥ 90` or Jaccard over normalized tokens ≥ 0.8) against the full allowed set. Only rescue when exactly one entity scores above threshold — ambiguity → drop.

Expected rescue rate: 3–8%. Cost: O(orphans × entities) per batch; negligible at our scale (~50 entities × ~5 orphans).

Risk: false positives. Mitigate with a strict threshold and by requiring the canonical name to share ≥ 1 rare token with the endpoint (excludes matches on stopwords like "the", "lord").

### Tier 7 — Auto-create placeholder entity (opt-in; rescues orphans that are probably real but un-extracted)

For relationships where the LLM provided a `description` that implies the endpoint is a narratively real character (not a typo or pronoun), create a minimal `Character` stub with `name=endpoint_name, description="(referenced in a relationship but not extracted directly)", provenance=[relationship.provenance]`. Log at WARN.

Expected rescue rate: 5–10%. Highest risk: pollutes the graph with low-evidence entities. Should be gated by config flag and require the relationship itself to have valid provenance.

Risk tradeoff: this is the "always say yes" version — only worth running if users report missing connections after the earlier tiers are in. Start disabled.

### Drop floor

Anything still unresolved after Tiers 1–6 (and optionally 7): drop with `rel_drop reason=hard_orphan`. These are true hallucinations and should stay out of the graph.

## Integration sequence

Do the tiers in an order that maximizes information per ingestion:

1. **Land the drop-log + dropped_relationships.json** — ship first, alone. Re-ingest Red Rising. Now we have ground-truth failure categories.
2. **Land Tier 3 (batch scope)** — one-line change, zero risk, probably the biggest single rescue. Measure lift.
3. **Land Tiers 1 + 2 + 6 together** (string normalization + alias + fuzzy) — they share a canonicalization path. Measure cumulative.
4. **Land Tier 4 (BookNLP coref)** — more plumbing, meaningful lift, but only if Tiers 1–3 + 6 haven't already closed the gap to <5% drop rate.
5. **Land Tier 5 (event endpoints)** — schema change, weigh carefully. Only if `rel_drop reason=tgt_event` is a meaningful category in the instrumentation data.
6. **Land Tier 7 (placeholder)** — only if users are asking for more coverage; tune threshold to minimize false positives. Keep gated.

## Success metric

**Relationship retention rate** per book after ingestion: `kept / proposed`. Red Rising baseline: 64/209 = **31%**. Target after Tiers 1–4 and 6: **≥ 65%**. Secondary metric: no regression in extraction quality (sample 50 rescued relationships, manually verify ≥ 90% are true narrative links).

## Risks / open questions

- **Alias quality.** If `Character.aliases` is itself unreliable (LLM-generated), Tier 1 could match hallucinated aliases to hallucinated relationship endpoints and *introduce* fake links instead of rescuing real ones. Mitigation: audit alias quality on a sample before enabling.
- **Batch scope broadens spoiler surface within a batch.** Today if chunk N mentions a character first, chunk N-2 relationships about that character are dropped. After Tier 3, they'd be kept — but the `effective_latest_chapter` on the relationship is still stamped from the late chunk, so the fog-of-war filter still excludes it until the reader reaches that point. Verify no leak.
- **BookNLP cluster bleed.** BookNLP coref is ~70% accurate; we're already using it for parenthetical insertion. Tier 4 amplifies its errors by re-purposing its clusters as a rescue index. Confine lookups to high-confidence clusters (multiple mentions, singleton clusters excluded).
- **Tier 5 schema drift.** Adding relationship types splits the clean 10-entry narrative enum. Strongly prefer a separate `EventParticipation` DataPoint to keep `Relationship` semantic.

## Not in scope

- Re-running the LLM to resolve ambiguous endpoints (too expensive, would double ingestion time).
- Graph-wide cross-book entity linking (this spec is within a single book's ingestion).
- Retroactively repairing existing ingestions — ship the drop log to a **replay** script that reads `dropped_relationships.json` and re-validates under the new cascade, no re-ingestion required.

## Acceptance criteria

1. `data/processed/{id}/batches/batch_NN/dropped_relationships.json` exists for every future ingestion, with reason, source/target names, original provenance.
2. `_validate_relationships` emits per-tier rescue counts at INFO (`rescued_alias=X rescued_coref=Y rescued_fuzzy=Z hard_orphan=W`).
3. Red Rising retention rate rises from 31% to ≥ 65% (actual target set after Phase 0 instrumentation confirms failure-mode breakdown).
4. A replay script rebuilds allowed relationships for already-ingested books without re-running the pipeline.
5. No new relationship in the graph lacks provenance.
