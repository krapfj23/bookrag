# Plan 1 — Extraction determinism

**Priority:** HIGHEST. Do before Plan 2 or Plan 3.
**Date:** 2026-04-22
**Branch target:** `feat/fog-of-war-phase-0` (or a fresh branch off main)
**Estimated effort:** 1–2 hours
**Status:** ready to execute

## Problem

Every time we change the extraction prompt or pipeline and re-ingest a book, the eval scores swing unpredictably because the LLM extraction is non-deterministic. Specific evidence from `evaluations/results/2026-04-22-reextraction-summary.md`:

- Single re-extraction of Christmas Carol dropped 3 Characters, 1 Location, 1 Faction, 2 Themes compared to the previous run — from identical source text and identical ontology.
- Theme names got renamed on re-extraction ("Generosity" → "Generosity vs. Greed"), causing `entity_recall` to drop from 0.917 → 0.708 despite a structurally better prompt.
- We cannot tell whether a prompt or pipeline change actually improved quality because the variance per-question across runs exceeds the per-change effect size.

**Consequence:** every future change looks either like a regression or a no-op. Plans 2 and 3 will suffer the same measurement failure unless this is fixed first.

## Goal

Make the extraction step reproducible — two consecutive re-extractions on the same inputs should produce the same (or near-identical) DataPoints. Close enough that eval-score deltas reflect real quality changes, not LLM sampling noise.

## Approach: two layers of stabilization

### Layer A: Cognee's `llm_temperature` → 0.0

Cognee already defaults `llm_temperature=0.0` in its config (`cognee/infrastructure/llm/config.py:48`). Our code sets `llm_provider` and `llm_model` via `configure_cognee()` in `pipeline/cognee_pipeline.py` but does NOT explicitly set temperature. OpenAI's default is 1.0; unless Cognee overrides it at call time, our extraction is running at temperature 1.0.

**Fix:** explicitly pass `llm_temperature=0.0` in the `cognee.config.set_llm_config()` call. One config line.

### Layer B: Seed the OpenAI call (defense in depth)

Even at temperature 0, OpenAI's gpt-4o-mini / gpt-4.1-mini are not fully deterministic because the server-side routing can pick different instances. OpenAI accepts a `seed` parameter that, combined with temperature=0, gives a far tighter reproducibility contract.

**Fix:** expose `llm_seed` as a BookRAGConfig field (default `42`) and thread it into the `cognee.config.set_llm_config({...})` call alongside temperature.

### Layer C: Optional N-sample averaging for validation only (out of scope for this slice)

If after A+B we still see drift, a future slice can add multi-sample majority voting — N=3 extractions per batch, take entities/relations that appear in ≥2 of 3. That's expensive and probably unnecessary; deferring.

## Acceptance criteria

1. `models/config.py` has a new `llm_temperature: float = 0.0` field on `BookRAGConfig` (settable via `BOOKRAG_LLM_TEMPERATURE` env var).
2. `models/config.py` has a new `llm_seed: int | None = 42` field on `BookRAGConfig`.
3. `pipeline/cognee_pipeline.py:configure_cognee()` reads those two fields and passes them to `cognee.config.set_llm_config()` under keys `llm_temperature` and `llm_seed` (or the env-var keys Cognee recognizes; verify against `cognee/infrastructure/llm/config.py`).
4. Unit test `tests/test_cognee_pipeline.py::TestConfigureCognee::test_temperature_and_seed_propagated` pins that `configure_cognee()` calls `cognee.config.set_llm_config` with the expected keys.
5. Determinism regression test: `scripts/reextract_book.py christmas_carol_e6ddcd76` run twice back-to-back produces byte-identical `extracted_datapoints.json` files (or, if timestamp/id fields differ, identical content after stripping non-deterministic fields).
6. `pytest` stays green. Full suite ≥ 994 tests.
7. The eval baseline is re-captured with the deterministic extraction and checked into `evaluations/results/2026-04-XX-baseline-deterministic.md`. This becomes the new reference point for Plans 2 and 3.

## Data contracts

No API changes. No schema changes. Only new config fields:

```python
# models/config.py (additions)
class BookRAGConfig(BaseSettings):
    ...existing fields...
    llm_temperature: float = 0.0
    llm_seed: int | None = 42
    model_config = SettingsConfigDict(env_prefix="BOOKRAG_")
```

Env-var overrides: `BOOKRAG_LLM_TEMPERATURE=0.3` and `BOOKRAG_LLM_SEED=`  (unset → None, which reverts to non-seeded).

## Tasks

### T1. Add config fields (~10 min)

- Modify `models/config.py` — add `llm_temperature` and `llm_seed`.
- Regenerate `config.yaml` example if any exists — use defaults.
- Tests: `tests/test_config.py::TestDeterminism::test_defaults_are_temperature_zero_seed_42`.

### T2. Propagate into Cognee (~20 min)

- Modify `pipeline/cognee_pipeline.py:configure_cognee()` to include `"llm_temperature": config.llm_temperature` and `"llm_seed": config.llm_seed` in the dict passed to `cognee.config.set_llm_config()`.
- Verify against `cognee/infrastructure/llm/config.py:LLMConfig` that those keys are accepted. Fix key names if Cognee uses different ones.
- Test: `tests/test_cognee_pipeline.py::TestConfigureCognee::test_temperature_and_seed_propagated` — patch `cognee.config.set_llm_config` with a MagicMock, invoke `configure_cognee(config_with_values)`, assert the mock was called with the expected keys.

### T3. Sanity-check against a live dry-run (~15 min, requires OPENAI_API_KEY)

- Run `scripts/reextract_book.py christmas_carol_e6ddcd76` twice in succession without restarting anything.
- Diff the two resulting `batches/batch_01/extracted_datapoints.json` files. Acceptable differences: `id`, `created_at`, `updated_at`, `topological_rank`. Everything semantic (names, descriptions, relations, chapters) must match.
- If diffs exceed the allowlist: open a follow-up ticket; for this slice, document the residual noise in the eval result file.

### T4. Re-capture deterministic baseline (~10 min)

- `scripts/eval_query.py --mode baseline --out evaluations/results/2026-04-XX-baseline-deterministic.md`
- Record `answer_similarity` and `entity_recall` as the new reference. Plans 2 and 3 measure against this, not the previous noisy baselines.

### T5. Commit + document (~15 min)

Single commit with message documenting both layers and the measured variance reduction. Update `docs/research/cognify-pipeline.md` with a pointer to the baseline file so future research is grounded in the new numbers.

## Risks and mitigations

- **Risk:** Cognee's config key names differ from what we guess. **Mitigation:** T2 includes verifying against the installed Cognee source. If the key is `llm_temperature`, great. If it's something else (`temperature`, `generation_temperature`), use the actual key and add a comment citing the source line.
- **Risk:** OpenAI's seed parameter is advisory — even at temperature 0 + seed, gpt-4o-mini can produce different tokens on different days. **Mitigation:** document the residual drift. If it's ≥5% of entities per run, this slice wasn't enough and we need N-sample majority voting.
- **Risk:** Setting temperature 0 makes extraction more conservative — some boundary cases might start failing. **Mitigation:** the post-T3 diff against a temperature-1 run will flag this. If the deterministic run drops > 10% of entities compared to the noisy run, we have a quality regression to investigate before committing.

## Exit criteria for this slice

- Two back-to-back re-extractions produce semantically identical data (allowlist of diff fields is documented).
- `2026-04-XX-baseline-deterministic.md` committed.
- `pytest` green.
- Ready to start Plan 2 or Plan 3 with a stable reference point.

## Why this is the highest-priority plan

Without determinism:
- Plan 2 (triplet embedding) ships, eval scores move by ±5%, we can't tell if triplet vector search actually helps.
- Plan 3 (consolidation) ships, eval scores move by ±8%, we can't tell if consolidation is collapsing real duplicates or losing real entities.
- Every future prompt edit is a guess.

With determinism, each subsequent change produces a signed effect size we can read off the eval diff. Two hours of work to save weeks of second-guessing.
