# OpenAI Strict-Mode Compatibility Audit — `ExtractionResult`

**Date:** 2026-04-22
**Context:** Phase A Stage 0 / Task 3 from `docs/superpowers/plans/2026-04-22-phase-a-stage-0-plan.md`.
**Verdict:** **Defer to Stage 1.** Current schema is broadly non-compliant; Stage 1 restructures DataPoints anyway (provenance, valence, cluster_id, `RelationshipType` enum), so the fix belongs there.

## Strict-mode rules (OpenAI structured outputs)

1. No `$ref` / recursion — schemas must be fully inlined.
2. No `oneOf` anywhere. `anyOf` tolerated at nested levels but not at root.
3. All properties must appear in `required`. Optional = `X | None` with explicit null, required=True.
4. `additionalProperties: false` mandatory on every object.
5. Max 100 properties, max 5 levels deep, max 5000 enum values.

## Current `ExtractionResult` (non-compliant)

Inspected via `ExtractionResult.model_json_schema()`:

| Rule | Status | Example |
|---|---|---|
| No `$ref` | **Violated** | Root uses `$defs` + `$ref` pattern emitted by Pydantic for nested models (`CharacterExtraction`, `LocationExtraction`, etc.). |
| No `oneOf` | OK | None found. |
| All properties required | **Violated** | `CharacterExtraction` has 6 properties, only 2 in `required` (`name`, `first_chapter`). Same pattern for every nested extraction model. |
| `additionalProperties: false` | **Violated** | Not set on any object. |
| `anyOf` (root/nested) | Gray area | Nested `anyOf: [X, null]` emitted by Pydantic for `Optional[X]`. Strict mode tolerates this at nested levels but requires the owning property to still appear in `required` with explicit `"type": ["X", "null"]` emission. |

## Fix shape (Stage 1)

Stage 1 already plans to restructure DataPoints with:
- `provenance: list[Provenance]`
- `valence: float`, `confidence: float`, `RelationshipType` enum
- `booknlp_coref_id: int | None`
- `extractor_version`, `cache_key`, `created_at` on `ExtractionResult`

Bundle the strict-mode compliance fix into that work:

1. Flatten `$ref` by passing `ref_template` or manually post-processing `model_json_schema()` to inline `$defs`.
2. Set `additionalProperties=False` via `ConfigDict(extra="forbid")` on every DataPoint and extraction model.
3. Include every property in `required`, using `X | None` with explicit `default=None` for optional fields.
4. Audit test: walk the emitted schema, assert no `$ref`, assert all objects have `additionalProperties: false`, assert properties==required at every level.

## Not blocked

The current `LLMGateway.acreate_structured_output` path in Cognee 0.5.6 does not use strict mode — it uses Pydantic's `response_format` without `strict: true`. The non-compliance is latent, not active. No production regression from deferring.

## Stage 0 scope decision

- **Task 3a (audit):** ✅ Completed — this document.
- **Task 3b (enable strict):** ❌ Deferred to Stage 1.
- **Task 4 (upstream Kuzu PR):** Deferred — requires third-party PR against topoteretes/cognee, user consent needed before filing.

Task 3b and Task 4 are tracked in the roadmap and will be revisited at their natural points.
