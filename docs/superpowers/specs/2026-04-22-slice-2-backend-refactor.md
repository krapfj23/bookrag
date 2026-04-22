# Slice 2 — Backend Refactor SPEC

**Date:** 2026-04-22
**Type:** Pure move/split refactor. Zero behavior change.
**Scale:** ~1500 LOC moved across ~10 new files. Zero new tests except one for the model_dump logger fix.

## Goal

Split two god-modules (`main.py` 1104 LOC, `pipeline/cognee_pipeline.py` 831 LOC) along change-reason seams into an `api/` package plus two focused pipeline modules, so future edits touch one file per concern rather than scrolling through monoliths.

## Module dependency diagram

```
main.py (< 450 LOC — app shell)
  │
  ├──▶ fastapi.FastAPI, CORSMiddleware
  ├──▶ models.config.load_config / ensure_directories
  ├──▶ pipeline.orchestrator.PipelineOrchestrator
  └──▶ app.include_router(...) for each of:
         │
         ├── api/routes/health.py         → (nothing else)
         ├── api/routes/books.py          ──▶ api/loaders/book_data.py
         │                                     └─▶ models.pipeline_state.load_state
         ├── api/routes/chapters.py       ──▶ api/loaders/book_data.py
         ├── api/routes/progress.py       ──▶ api/loaders/book_data.py
         ├── api/routes/query.py          ──▶ api/query/synthesis.py
         │                                     └─▶ pipeline.spoiler_filter
         │                                     └─▶ cognee.* (optional at import time)
         │                                └──▶ api/loaders/book_data.py
         └── api/routes/graph.py          ──▶ api/loaders/graph_data.py

pipeline/cognee_pipeline.py (< 500 LOC)
  │  keeps: configure_cognee, ChapterChunk, chunk_with_chapter_awareness,
  │         _load_extraction_prompt, render_prompt, extract_enriched_graph,
  │         _save_batch_artifacts, run_bookrag_pipeline
  ├──▶ pipeline.consolidation  (NEW)
  │      └── _ConsolidatedDescription, _group_entities_for_consolidation,
  │          _merge_group, _merge_chunk_extractions, consolidate_entities,
  │          _load_consolidation_prompt
  └──▶ pipeline.extraction_validation  (NEW)
         └── _validate_relationships

pipeline/orchestrator.py
  ├──▶ pipeline.cognee_pipeline.run_bookrag_pipeline, configure_cognee  (unchanged)
  └──▶ pipeline.booknlp_utils.booknlp_output_to_dict  (NEW — was inline)

scripts/reextract_book.py
  ├──▶ pipeline.cognee_pipeline.run_bookrag_pipeline, configure_cognee  (unchanged)
  └──▶ pipeline.booknlp_utils.booknlp_output_to_dict  (NEW — was _booknlp_to_dict)
```

No cycles: `api/*` imports `pipeline.*` but never the reverse. `pipeline.consolidation` and `pipeline.extraction_validation` depend only on `models.datapoints`, `loguru`, `jinja2`, and `cognee.infrastructure.llm.LLMGateway` (same stack `cognee_pipeline` already pulls).

## Why split this way — change-reason boundaries

**Routes change when endpoints change.** `api/routes/*.py` exist so that adding a new endpoint (or adjusting CORS for a specific verb) only touches one small file. A router per HTTP resource (books / chapters / progress / query / graph / health) matches the URL grouping in `CLAUDE.md`'s endpoint table.

**Synthesis changes when retrieval strategy changes.** `_complete_over_context` and `_vector_triplet_search` answer the question "how do we get an answer string out of allowed-node context." They change together when we tune the synthesis prompt, switch to a different triplet search path (e.g., Plan 2 cognee_search module), or add retries. They do NOT change when endpoint shapes change. Grouping them in `api/query/synthesis.py` keeps the route handler thin.

**Loaders change when disk layout changes.** `_load_chapter`, `_list_chapter_files`, `_get_reading_progress`, and `_load_batch_datapoints` all read disk artifacts from `data/processed/{book_id}/`. When we change the chunk index format or batch artifact shape, we touch loaders — not routes, not synthesis.

**Consolidation changes when entity-dedup strategy changes.** The Plan 3 helpers (`_group_entities_for_consolidation`, `consolidate_entities`, `_merge_group`, `_ConsolidatedDescription`, `_merge_chunk_extractions`) are a cohesive feature — they exist because entities sometimes appear in multiple chunks of one batch. They change together; they should live together.

**Validation changes when relationship invariants change.** `_validate_relationships` enforces orphan-drop + duplicate-collapse. A different invariant set (e.g., minimum description length, stricter endpoint-type matching) would change this one function. It does not change when consolidation prompts change, so it belongs in its own module.

**Booknlp conversion is shared plumbing.** The dataclass-to-dict helper appears twice today (`orchestrator.py:241` via `to_pipeline_dict()` call — actually a method on `BookNLPOutput`; and the separate duplicate `_booknlp_to_dict` at `scripts/reextract_book.py:43-71`). The reextract path does not go through `BookNLPOutput.to_pipeline_dict()` because `parse_booknlp_output` returns a different shape. Extracting a single `booknlp_output_to_dict(output) -> dict[str, Any]` into `pipeline/booknlp_utils.py` removes the duplicate.

## What stays in `main.py` and why

1. **App construction.** `load_config`, `ensure_directories`, `FastAPI(...)`, `CORSMiddleware`.
2. **Orchestrator instance.** `orchestrator = PipelineOrchestrator(config)` — module-level singleton that routes inject via a lightweight getter.
3. **Cognee startup.** The `try: configure_cognee(config)` block — this runs once at import time and sets a global `COGNEE_AVAILABLE` flag that `api/query/synthesis.py` reads.
4. **Logging setup.** `logger.remove()` + two `logger.add(...)` calls for stderr + file sink.
5. **Router inclusion.** Six `app.include_router(...)` calls, one per resource.
6. **`__main__` block.** The `uvicorn.run(app, host=..., port=8000)` guard.

Everything else goes. The request/response Pydantic models (`UploadResponse`, `ProgressRequest`, `Chapter`, `QueryRequest`, etc.) move to live next to the router that owns them, not in a single global models file — Pydantic models are part of the endpoint's contract and benefit from co-location.

## Non-goals

- No behavior change to any endpoint. Request shapes, response shapes, status codes, and error strings are byte-identical before and after.
- No change to `run_bookrag_pipeline`'s signature or its ordering of pipeline stages.
- No prompt changes. `prompts/extraction_prompt.txt` and `prompts/consolidate_entity_prompt.txt` are not edited.
- No new tests. The 1035-test contract is preserved; only import paths in existing tests may change. Exception: T5 adds one test for the `logger.warning` serialization-failure path.
- No new dependencies in `pyproject.toml`.
- `slowapi` is NOT introduced by this slice. If a later slice adds it, the router shell will accept per-route limiter decorators without structural change.
- `asyncio.create_task` stays (Locked Decision). Kuzu + LanceDB stays (Locked Decision). `loguru` everywhere stays (Locked Decision).
- `CLAUDE.md` is updated only to reflect the new file layout and bumped test count (923 → 1036). No "Locked Decisions" mutated.

## Risks

1. **Import cycles.** `api/routes/query.py` wants to import `api/query/synthesis.py`, which wants to read the `COGNEE_AVAILABLE` flag set in `main.py`. Mitigation: `synthesis.py` does its own `try: import cognee` at import time and exposes `COGNEE_AVAILABLE` locally; `main.py` also imports cognee the same way. Both reach the same answer; neither imports the other at module scope.
2. **Forgotten test path updates.** `tests/test_cognee_pipeline.py` has 19 inline `from pipeline.cognee_pipeline import ...` statements inside test methods that reference consolidation/validation symbols. `tests/test_spoiler_filter.py` has 2 more. Mitigation: grep for each moved symbol after each task and rewrite in one pass per test file; final T13 re-greps to prove zero stragglers.
3. **Pytest discovery breakage.** New `api/` package needs `__init__.py` files at each level. Missing init → pytest can't collect → false "test count drop." Mitigation: T7 explicitly creates `api/__init__.py`, `api/routes/__init__.py`, `api/loaders/__init__.py`, `api/query/__init__.py` as empty files.
4. **`git mv` history loss.** If an implementer uses `Write` + `rm` instead of `git mv`, rename detection fails and `git log --follow` becomes useless. Mitigation: generator brief forbids it; reviewer checks with `git log --follow --diff-filter=R`.
5. **Silent serialization fix regresses fallback.** The fix at `cognee_pipeline.py:498` adds `logger.warning` but MUST preserve the existing fallback record (`{"type": type(dp).__name__, "id": str(dp.id)}`) so `extracted_datapoints.json` shape is unchanged. Mitigation: new T5 test patches `model_dump` to raise and asserts (a) warning fires, (b) fallback record is in the output list.
6. **Coref demo print → logger change.** The `__main__` block at `pipeline/coref_resolver.py:613-656` uses `print` after reconfiguring loguru to a print sink (line 615-619). Switching to `logger.info` means output still flows through loguru — cosmetically identical.

## Exit criteria

1. `python -m pytest tests/` collects exactly **1036 tests** (baseline 1035 + 1 new for T5).
2. All 1036 tests pass, zero errors, zero failures. `test-snapshot.txt` diff with the post-refactor collection shows exactly 1 added test ID.
3. `wc -l main.py` reports **< 450 LOC**.
4. `wc -l pipeline/cognee_pipeline.py` reports **< 500 LOC**.
5. `python -c "import main; print('ok')"` succeeds (no import cycles at startup).
6. `git log --follow --diff-filter=R` on each moved file shows rename entries where possible.
7. `grep -r "_validate_relationships\|consolidate_entities\|_group_entities_for_consolidation\|_merge_group\|_ConsolidatedDescription\|_merge_chunk_extractions" pipeline/cognee_pipeline.py` returns zero matches.
8. No `print(` in `pipeline/coref_resolver.py` (grep returns zero hits).
9. `python -c "from pipeline.booknlp_utils import booknlp_output_to_dict; print('ok')"` works.
10. Manual smoke test: start the server, POST `/books/upload` with a fixture EPUB, watch logs for the same stage sequence as before. No new warnings, no new errors.
11. One commit. Conventional message: `refactor: split main.py + cognee_pipeline.py along responsibility lines (slice 2)`.
