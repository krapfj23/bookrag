# Slice 3: Test Quality Uplift

**Date:** 2026-04-22
**Status:** Draft
**Owner:** Test subagent (implementation) / Review subagent (verification)
**Depends on:** Slice 1 (security guards in `configure_cognee`)

## Goal

Raise the signal-to-noise ratio of the 1035-test BookRAG backend suite so test failures map to real regressions, not to mock-wiring drift.

## Principle

**High-signal tests verify behavior at module boundaries, not mock wiring.** A test that asserts `mock_llm.await_count == 1` passes whenever the function calls the LLM — including when the function mutates no data, returns the wrong shape, or silently swallows errors. A test that asserts `len(result.characters) == 1 and result.characters[0].name == "Scrooge"` fails loudly on those regressions. This slice converts or augments the weakest tests toward the second style, and closes coverage holes that the existing mock-heavy style hid.

## In-Scope Items

### Item 1 — Add `cognee.config` stub to `tests/conftest.py`

**Problem.** `tests/conftest.py::_install_cognee_mock` stubs `LLMGateway`, `DataPoint`, `Pipeline`, `Storage`, `Search`, `Task`, `run_pipeline`, `add_data_points`, `SearchType` — but not `cognee.config`. `pipeline/cognee_pipeline.py:86` calls `cognee.config.set_llm_config(llm_config)`. Because `cognee.config` is not installed in `sys.modules`, any test that touches `configure_cognee()` either crashes on `AttributeError` at import or is skipped by a guard. Coverage for that branch is silently 0%.

**Fix.** In `_install_cognee_mock`, build `types.ModuleType("cognee.config")`, attach `set_llm_config = MagicMock()` to it, register in `sys.modules["cognee.config"]`, and set `cognee.config = <that module>` so both attribute access (`cognee.config.set_llm_config`) and import form (`from cognee.config import set_llm_config`) work. Slice 1 added a runtime guard; this slice completes the test-path coverage.

**Non-goals.** Do not stub any cognee submodule not referenced by production code today. Do not convert the ad-hoc stub installer into a pytest plugin.

### Item 2 — Deepen Plan 2/3 tests (behavior, not mock-to-mock)

**Problem.** Three test classes pin mock state instead of observable behavior:

- `TestEntityConsolidation` (tests/test_cognee_pipeline.py:780): several tests assert `mock_llm.await_count == N`. This passes even if `consolidate_entities` returns an empty list or drops every member.
- `TestValidateRelationships` (tests/test_cognee_pipeline.py:647): mostly good, but at least one test is a tautology where the "input" and "expected output" are the same object.
- `TestRunBookragPipeline::test_consolidate_*` (tests/test_cognee_pipeline.py:972): asserts `mock_consolidate_entities.await_count == 1` without checking whether the pipeline actually produces fewer duplicate characters.

**Fix.**
- Add a sibling class `TestEntityConsolidationBehavior` with >=3 tests. Each test calls `consolidate_entities` with a real `ExtractionResult` and a stub `_ConsolidatedDescription` returned from a fake LLM. Assertions target the **returned** `ExtractionResult.characters` content: merged descriptions contain tokens from every input member, `first_chapter == min(members' first_chapter)`, multi-bucket inputs yield `len(result.characters) == number_of_buckets`.
- Audit `TestValidateRelationships` once; strengthen any tautology by asserting on the output list's *shape* and *content*, not on the input.
- Add `test_run_bookrag_pipeline_collapses_duplicates_end_to_end`: feed `extract_enriched_graph` two chunks whose fake LLM returns two Characters named "Scrooge"; after the full pipeline runs through `consolidate_entities`, assert the final `ExtractionResult.characters` contains exactly one Character named "Scrooge".

**Non-goals.** Do not rewrite passing mock-state tests that don't have a behavior twin yet — just add behavior tests alongside. Do not remove existing coverage.

### Item 3 — Fill missing test class docstrings

**Problem.** CLAUDE.md requires every backend test class to have a docstring. The audit identified 22 concentrated violations in `test_cognee_pipeline.py` (11) and `test_main.py` (9), plus 2 in `test_datapoints.py`. The linter-style check `pytest --collect-only` does not enforce this, so drift is invisible.

**Fix.** Add a one-line docstring (<=2 lines) to each of the 22 classes listed in the table below. Target: 100% class-docstring coverage across these files after the slice lands.

| # | File | Line | Class | Docstring intent |
|---|------|------|-------|------------------|
| 1 | tests/test_cognee_pipeline.py | 218 | TestChapterChunk | covers the ChapterChunk DataPoint shape and chapter metadata. |
| 2 | tests/test_cognee_pipeline.py | 237 | TestChunkWithChapterAwareness | verifies chunker preserves chapter boundaries and last-known-chapter tagging. |
| 3 | tests/test_cognee_pipeline.py | 298 | TestFormatBookNLPEntities | asserts BookNLP entity rows render into the extraction prompt block. |
| 4 | tests/test_cognee_pipeline.py | 333 | TestFormatBookNLPQuotes | asserts BookNLP quote rows render with speaker attribution. |
| 5 | tests/test_cognee_pipeline.py | 362 | TestFormatOntologyClasses | verifies discovered ontology classes serialize into the prompt. |
| 6 | tests/test_cognee_pipeline.py | 385 | TestFormatOntologyRelations | verifies discovered relation labels serialize into the prompt. |
| 7 | tests/test_cognee_pipeline.py | 408 | TestRenderPrompt | covers render_prompt placeholder substitution and guardrails. |
| 8 | tests/test_cognee_pipeline.py | 477 | TestExtractEnrichedGraph | covers single-batch extraction with mocked LLMGateway. |
| 9 | tests/test_cognee_pipeline.py | 598 | TestSaveBatchArtifacts | asserts per-batch JSON artifacts are written under data/processed. |
| 10 | tests/test_cognee_pipeline.py | 972 | TestRunBookragPipeline | covers the orchestrated run over multiple batches. |
| 11 | tests/test_cognee_pipeline.py | 1196 | TestSpecAlignment | asserts implementation still matches bookrag_pipeline_plan.md decisions. |
| 12 | tests/test_main.py | 111 | TestHealthEndpoint | covers GET /health. |
| 13 | tests/test_main.py | 125 | TestUploadEndpoint | covers POST /books/upload shape and pipeline kickoff. |
| 14 | tests/test_main.py | 252 | TestStatusEndpoint | covers GET /books/{id}/status stage reporting. |
| 15 | tests/test_main.py | 302 | TestValidationEndpoint | covers GET /books/{id}/validation JSON shape. |
| 16 | tests/test_main.py | 325 | TestProgressEndpoint | covers POST /books/{id}/progress writes reading_progress.json. |
| 17 | tests/test_main.py | 385 | TestCORS | asserts the configured dev-origin allowlist. |
| 18 | tests/test_main.py | 407 | TestExtractChapterUsesEffectiveLatest | verifies chapter-extraction respects effective_latest_chapter. |
| 19 | tests/test_main.py | 836 | TestQueryResponseIncludesParagraph | covers /query JSON returning paragraph-cursor metadata. |
| 20 | tests/test_datapoints.py | 111 | TestCharacterDataPoint | covers the Character DataPoint schema. |
| 21 | tests/test_datapoints.py | 308 | TestCharacterExtraction | covers CharacterExtraction (pre-persistence model) schema. |
| 22 | tests/test_datapoints.py | 382 | TestExtractionResult | covers the ExtractionResult aggregate model and round-trip. |

**Non-goals.** Do not touch docstrings on non-test classes. Do not extend to other test files in this slice.

### Item 4 — Unicode + path edge cases

**Problem.** The top-tested modules (`datapoints`, `booknlp_runner`, `text_cleaner`, `coref_resolver`) use ASCII fixtures almost exclusively. Real books contain curly apostrophes, em dashes, cyrillic, zero-width joiners, NBSP runs, and null bytes; real filesystems have spaces and non-ASCII characters; real BookNLP runs occasionally emit truncated JSON.

**Fix.** Add >=20 tests across four files:

- `tests/test_datapoints.py` (+6): Character/Location with curly apostrophe, em dash, cyrillic ("Соня"), zero-width joiner ("a‍z"); ExtractionResult serialization round-trip preserves those bytes; idempotent round-trip.
- `tests/test_booknlp_runner.py` (+5): truncated `.book` JSON, `.book` with a null where an int is required, missing `"characters"` key entirely, filename path containing spaces, filename path containing non-ASCII characters.
- `tests/test_text_cleaner.py` (+5): paragraph >1 MiB of text, embedded null byte, unbalanced HTML nesting, all-whitespace chapter, NBSP-only chapter.
- `tests/test_coref_resolver.py` (+4): tokens containing cyrillic, tokens containing zero-width joiner, TSV entry with literal tab in the name field, name field containing curly apostrophe.

**Non-goals.** Do not change production code opportunistically. If a test discovers a real bug, write the failing test, flag to controller, and move on.

### Item 5 — Graph visualization smoke test

**Problem.** `GET /books/{id}/graph` returns an HTML response containing an embedded vis.js script. Zero tests hit that endpoint.

**Fix.** Add `test_graph_html_smoke` to `tests/test_main.py`. Smoke only; no DOM assertion. Assert `response.status_code == 200`, `"text/html" in response.headers["content-type"]`, `"<script" in response.text`, `("vis.js" in response.text) or ("vis-network" in response.text)`.

**Non-goals.** Do not test JS execution, DOM structure, or node layout. Frontend tests live in Slice 4.

## Out of Scope (Explicit)

- Rewriting passing tests for stylistic reasons.
- End-to-end or integration tests that require a live Cognee server.
- Migrating to a new test runner.
- Any frontend tests (Slice 4).
- Docstring coverage on test files outside the 22 classes listed.
- Production-code bugfixes discovered during test writing (log-and-defer).

## Success Metric

After this slice:

1. `pytest tests/ -v` runs green with **>=1055 tests collected** (baseline 1035 + >=20 new tests; target 1060).
2. `TestConfigureCognee::test_configure_cognee_invokes_set_llm_config` (or equivalent) exercises `cognee.config.set_llm_config` without skipping.
3. At least **three** tests inside `TestEntityConsolidationBehavior` and/or strengthened `TestValidateRelationships` assert on **returned `ExtractionResult` data** (not on `mock.called` / `mock.await_count`).
4. All 22 classes listed in the table have a docstring (verifiable by the ast script in plan T4).
