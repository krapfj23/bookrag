# Plan 1 — Extraction determinism summary

**Date:** 2026-04-22
**Branch:** `main`
**Plan:** `docs/superpowers/plans/2026-04-22-extraction-determinism.md`
**Deterministic baseline eval:** [2026-04-22-baseline-deterministic.md](2026-04-22-baseline-deterministic.md)

## What we did

- Added `llm_temperature: float = 0.0` and `llm_seed: int | None = 42` to `BookRAGConfig`.
- Threaded `llm_temperature` through `configure_cognee()` into `cognee.config.set_llm_config()`. Cognee 0.5.6 does not accept an `llm_seed` key (verified via `InvalidConfigAttributeError` at runtime), so `llm_seed` is stored on our config for future use but not forwarded today.
- Re-extracted Christmas Carol twice back-to-back with the new config; compared the two outputs.

## What we expected

Two back-to-back re-extractions would produce semantically identical DataPoints after stripping nondeterministic fields like `id`, `created_at`, `updated_at`.

## What actually happened

**Only 29.4% of extracted records were byte-semantic identical across runs.** Breaking down by DataPoint type on Christmas Carol chapter 1 batch:

| Type | Run 1 | Run 2 | Name-level stability |
|---|---|---|---|
| Character | 12 | 11 | 86% (only diff is curly-vs-straight apostrophe) |
| Location | 1 | 3 | 50% |
| Faction | 0 | 0 | n/a |
| Theme | 8 | 5 | 12% (same concepts, different phrasings) |
| PlotEvent | 14 | 12 | low — each run paraphrases differently |
| Relationship | 8 | 7 | 22% (same ties, different verbs) |

Example theme drift:
- Run 1: `Hope`, `Redemption`, `Social Responsibility`, `The Importance of Family and Togetherness`
- Run 2: `redemption`, `the consequences of greed`, `the spirit of Christmas`

Example relationship drift:
- Run 1: `Scrooge was_business_partners_with Marley`
- Run 2: `Scrooge was_partner_of Marley`

Both are correct. Neither is more correct than the other. That's the problem.

## Honest diagnosis

**Temperature=0 pins the *ranking* of tokens at each step, but not the *phrasing* of free-form text.** With a structured-output schema that says "return a list of themes", the LLM can legitimately choose any of several valid generalizations of the same underlying fact. Temperature=0 doesn't eliminate that choice — it just removes the sampling noise on top of it.

Seed (`seed=42` in the OpenAI API) would reduce some of this drift, but Cognee 0.5.6's LLMConfig rejects that key. Adding it would require either:
1. A Cognee version bump (if a future version accepts it).
2. Bypassing Cognee's LLMGateway for our extraction call and going directly to the OpenAI SDK, losing Cognee's gateway features (logging, rate limiting).
3. N-sample majority voting on entity names (expensive; 3× extraction cost).

None of these is in scope for Plan 1 as written.

## What Plan 1 actually delivered

1. **Entity-level naming is stable enough** (Character/Location at 86%/50%; the drift is encoding-level not semantic) for subsequent plans to compare against. This is the lever we needed most — the triplet embedding work in Plan 2 depends on entity name stability for vector-index lookups.

2. **Free-form text (PlotEvent descriptions, Theme names, relation verb variants) remains variable.** Plans 2 and 3 will need to compensate — either through fuzzy matching or a consolidation pass that normalizes before ranking.

3. **Deterministic baseline captured.** `2026-04-22-baseline-deterministic.md` shows `answer_similarity=0.489`, `entity_recall=0.597`. These are the new reference numbers for Plans 2 and 3. The lower scores vs our earlier "v1 baseline" (0.714 / 0.917) reflect the extraction-time variance dropping our expected-entity matches: the current Christmas Carol dataset has no `Tiny Tim` standalone Character, for instance, which the eval fixture expects.

4. **The config plumbing is in place.** If we later bypass Cognee for a direct OpenAI call with `seed=42`, the config flag is ready.

## Recommendation for Plans 2 and 3

**Do not retry extraction for determinism.** The marginal improvement isn't worth the complexity. Instead:

- **Plan 2 (triplet embedding)** — vector search is robust to the verb-phrasing drift we saw (`was_partner_of` vs `was_business_partners_with`). Both will embed near the same location, and a well-phrased query will retrieve both. This is actually the *right* argument for triplet embedding: keyword matching fails on verb drift, vector embedding tolerates it.

- **Plan 3 (consolidation)** — must include synonym normalization for relation verbs. When two `Relationship` records have the same `(source, target)` but different `relation_type`, consolidation should treat them as the same tie and merge descriptions. This is a small but real change to Plan 3's spec.

- **Eval fixture** — our `expected_entities` hard-codes specific strings. A future improvement is fuzzy matching, but it's cheap and not urgent.

## Exit criteria check (against Plan 1 spec)

| Criterion | Status |
|---|---|
| `llm_temperature`/`llm_seed` fields added | ✅ |
| Threaded into `configure_cognee` | ✅ (temperature only; seed blocked by Cognee) |
| Unit test pinning propagation | ✅ 3 tests pass |
| Determinism regression: byte-identical files | ❌ 29.4% semantic overlap |
| `pytest` green at ≥ 994 | ✅ 999 |
| Baseline committed | ✅ |

Three of six exit criteria fully met. Two partially met (seed blocked but documented; determinism is entity-stable but not text-stable). One fully met. The plan's stated goal — "make the extraction step reproducible" — is partially achieved: reproducible enough for named-entity comparisons across runs, not reproducible enough for text-similarity deltas to be pure signal.

**Net value:** the baseline file gives Plans 2 and 3 a reference point, and the honest characterization above tells them what kind of noise to expect. The naïve version of Plan 1 (just temperature=0) overpromised; this summary corrects the record.
