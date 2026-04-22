# Slice 2 — Backend Refactor PLAN

> **Execution:** Use `superpowers:executing-plans` (single session, 14 sequential tasks) or `superpowers:subagent-driven-development` (parallel where safe). Per-task TDD checkboxes. Pure refactor — tests drive correctness; no new tests except T5.

**Spec:** `docs/superpowers/specs/2026-04-22-slice-2-backend-refactor.md`
**Baseline:** 1035 tests. `main.py` 1104 LOC. `pipeline/cognee_pipeline.py` 831 LOC.

## Subagent briefs

### Test subagent
No new coverage. Only rewrite `from main import X` or `from pipeline.cognee_pipeline import X` as modules move. The 1035 existing tests are the contract. Any test that starts failing is a refactor bug, NOT a test update. Exception: T5 adds exactly one new test that asserts the new `logger.warning` fires when `model_dump` raises.

### Generate subagent
Rules:
(a) Use `git mv old new` then edit — never `Write new` + `rm old`. Rename detection matters.
(b) Prefer `from pipeline.consolidation import _group_entities_for_consolidation` over star imports.
(c) One `APIRouter()` instance per route file. Register in `main.py` via `app.include_router(books.router, prefix="", tags=["books"])` — no prefix because the paths in the decorators already include `/books`, `/health`, etc.
(d) After each task, run the focused test module first (fast feedback), then the full suite (regression gate).
(e) Do NOT add type annotations that weren't there before. Behavior-preserving refactor only.
(f) When moving Pydantic models, co-locate with the router that uses them. Don't make a global `api/models.py`.

### Review subagent
Spec reviewer: diff endpoint paths + response models before/after. Any change is a bug. Check `git log --follow` on each moved symbol produces rename entries.

Code-quality reviewer: `python -c "import main"` must succeed clean. Run `grep -rn "def _validate_relationships\|def consolidate_entities\|def _group_entities_for_consolidation\|def _merge_group\|class _ConsolidatedDescription\|def _merge_chunk_extractions" pipeline/` and verify each symbol is defined in exactly one file. Verify `wc -l main.py pipeline/cognee_pipeline.py` meets the LOC targets. Verify no new test files in `tests/` except the allowed T5 addition.

---

## Task 1 — Pin current state

- [ ] Run `python -m pytest tests/ --collect-only -q | grep "::" | sort > test-snapshot.txt`.
- [ ] Verify line count is in [1035, 1036].
- [ ] Run full suite: `python -m pytest tests/ -q`. Must be all-green.
- [ ] Capture LOC baseline: `wc -l main.py pipeline/cognee_pipeline.py`.

Expected: `main.py` = 1104, `cognee_pipeline.py` = 831, tests = 1035.

---

## Task 2 — Create `pipeline/booknlp_utils.py`

**Files:**
- Create: `pipeline/booknlp_utils.py`
- Modify: `scripts/reextract_book.py`
- Modify: `pipeline/orchestrator.py` line 241 area (may be no-op — check)

- [ ] Write new module with body from `scripts/reextract_book.py:_booknlp_to_dict`, renamed to `booknlp_output_to_dict`.
- [ ] Delete `_booknlp_to_dict` from `scripts/reextract_book.py`; import `booknlp_output_to_dict` instead.
- [ ] Run `pytest tests/test_orchestrator.py tests/ -q` → 1035 pass.

---

## Task 3 — Create `pipeline/extraction_validation.py`

**Files:**
- Create: `pipeline/extraction_validation.py`
- Modify: `pipeline/cognee_pipeline.py` (remove `_validate_relationships`, add import)
- Modify: `tests/test_cognee_pipeline.py` (7 inline imports)

- [ ] Cut `_validate_relationships` from `cognee_pipeline.py:663-727` into the new file with its own module docstring and `from models.datapoints import ExtractionResult` import.
- [ ] Add `from pipeline.extraction_validation import _validate_relationships` back in `cognee_pipeline.py`.
- [ ] Rewrite 7 test-level imports to the new module.
- [ ] Run `pytest tests/test_cognee_pipeline.py::TestValidateRelationships -v` → pass.
- [ ] Run `pytest tests/ -q` → 1035 pass.

---

## Task 4 — Create `pipeline/consolidation.py`

**Files:**
- Create: `pipeline/consolidation.py`
- Modify: `pipeline/cognee_pipeline.py`
- Modify: `tests/test_cognee_pipeline.py` (12 inline imports)
- Modify: `tests/test_spoiler_filter.py` (2 inline imports)

Move these symbols:
- `_ConsolidatedDescription`
- `_group_entities_for_consolidation`
- `_merge_group`
- `consolidate_entities`
- `_merge_chunk_extractions`

- [ ] Inline a tiny prompt-loader inside `consolidation.py` to avoid a cycle with `cognee_pipeline._load_extraction_prompt`:

```python
_CONSOLIDATION_PROMPT_CACHE: dict[str, str] = {}

def _load_consolidation_prompt(path: str = "prompts/consolidate_entity_prompt.txt") -> str:
    if path not in _CONSOLIDATION_PROMPT_CACHE:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Consolidation prompt not found at {p.resolve()}.")
        _CONSOLIDATION_PROMPT_CACHE[path] = p.read_text(encoding="utf-8")
    return _CONSOLIDATION_PROMPT_CACHE[path]
```

- [ ] Delete all five moved blocks in `cognee_pipeline.py`; replace with grouped imports.
- [ ] Rewrite 14 test-level imports.
- [ ] Run the focused tests + full suite.

---

## Task 5 — Fix silent model_dump error at `cognee_pipeline.py:498`

**Files:**
- Modify: `pipeline/cognee_pipeline.py`
- Modify: `tests/test_cognee_pipeline.py` (append exactly one test)

- [ ] Replace:
```python
except Exception:
    dp_records.append({"type": type(dp).__name__, "id": str(dp.id)})
```
with:
```python
except Exception as exc:
    logger.warning("Failed to serialize DataPoint {}: {}", getattr(dp, "id", "<no-id>"), exc)
    dp_records.append({"type": type(dp).__name__, "id": str(dp.id)})
```

- [ ] Append one test in `TestSaveBatchArtifacts`:

```python
def test_save_batch_artifacts_logs_warning_on_model_dump_failure(self, tmp_path):
    """When a DataPoint's model_dump raises, warning fires AND fallback record stays."""
    from unittest.mock import MagicMock
    from pipeline.cognee_pipeline import _save_batch_artifacts
    from pipeline.batcher import Batch

    bad_dp = MagicMock()
    bad_dp.id = "dp-boom"
    bad_dp.model_dump.side_effect = RuntimeError("serialize boom")
    type(bad_dp).__name__ = "Character"
    batch = Batch(chapters=[], combined_text="", chapter_numbers=[1])

    messages = []
    from loguru import logger as _lg
    sink_id = _lg.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        _save_batch_artifacts(batch, {}, [bad_dp], tmp_path)
    finally:
        _lg.remove(sink_id)

    assert any("Failed to serialize DataPoint dp-boom" in m for m in messages)
    out = (tmp_path / "batch_01" / "extracted_datapoints.json").read_text()
    assert '"id": "dp-boom"' in out
```

- [ ] Run `pytest tests/ -q` → **1036 pass**. New baseline from here.

---

## Task 6 — Remove `print()` from `coref_resolver.py` demo

- [ ] In `pipeline/coref_resolver.py:613-656`, drop the `logger.remove()` + custom print-sink setup in `main()`. Replace every `print(...)` with `logger.info(...)`.
- [ ] Run `python pipeline/coref_resolver.py` — visual smoke test, loguru-formatted output.
- [ ] `grep -c "print(" pipeline/coref_resolver.py` → **0**.
- [ ] `pytest tests/test_coref_resolver.py -q` → same count, pass.

---

## Task 7 — Create `api/loaders/book_data.py` + `api/loaders/graph_data.py`

- [ ] Create `api/__init__.py`, `api/loaders/__init__.py` (empty).
- [ ] Move to `api/loaders/book_data.py` (rename without leading underscore on new boundary):
  - `_derive_title` → `derive_title`
  - `_list_ready_books` → `list_ready_books(processed_dir)`
  - `_list_chapter_files` → `list_chapter_files(book_id, processed_dir)`
  - `_derive_chapter_title`
  - `_load_chapter` → `load_chapter(book_id, n, processed_dir)`
  - `_load_paragraphs_up_to` → `load_paragraphs_up_to(...)`
  - `_get_reading_progress` → `get_reading_progress(book_id, processed_dir)`
  - Pydantic models `BookSummary`, `ChapterSummary`, `Chapter`.
- [ ] Move to `api/loaders/graph_data.py`: `_load_batch_datapoints` → `load_batch_datapoints(book_id, processed_dir, max_chapter)`.
- [ ] Replace removed code in `main.py` with imports. Update every call site to pass `Path(config.processed_dir)` explicitly.
- [ ] Rewrite test imports in `tests/test_main.py` + `tests/test_chapters_endpoints.py` + `tests/test_books_endpoint.py`.
- [ ] Run focused tests + full suite.

---

## Task 8 — Create `api/query/synthesis.py`

Move from `main.py`:
- `_ALLOWED_SEARCH_TYPES` → `ALLOWED_SEARCH_TYPES`
- `_SpoilerSafeAnswer`
- `_complete_over_context` → `complete_over_context`
- `_answer_from_allowed_nodes` → `answer_from_allowed_nodes`
- `_vector_triplet_search` → `vector_triplet_search`
- `_extract_chapter` → `extract_chapter`
- `_result_to_text`, `_result_entity_type`
- `_search_datapoints_on_disk`
- `QueryRequest`, `QueryResponse`, `QueryResultItem`

**NOTE:** The brief mentioned `_post_filter_triplets` — that symbol does NOT exist in the current `main.py`. Skip it.

- [ ] Create `api/query/__init__.py`.
- [ ] Each function takes `processed_dir: Path` explicitly (no module-global config).
- [ ] `synthesis.py` does its own `try: import cognee` at import time.
- [ ] Remove all synthesis logic from `main.py`.
- [ ] Rewrite `tests/test_query_endpoint.py` + `tests/test_main.py` imports.
- [ ] Run focused tests + full suite.

---

## Task 9 — `api/routes/health.py` and `api/routes/books.py`

- [ ] Create `api/routes/__init__.py`.
- [ ] `api/routes/health.py` — `APIRouter`, `/health` endpoint, `HealthResponse`.
- [ ] `api/routes/books.py` — `/books/upload`, `/books`, `/books/{id}/status`, `/books/{id}/validation`. Hosts `UploadResponse`, `SafeBookId`, upload constants.
- [ ] Use late `from main import orchestrator, config` inside route functions to avoid cycles.
- [ ] In `main.py`, `from api.routes import books as books_routes` + `app.include_router(books_routes.router)`.
- [ ] Delete the four route defs + helpers from `main.py`.
- [ ] Run `pytest tests/test_main.py tests/test_books_endpoint.py -v` → pass.

---

## Task 10 — `api/routes/chapters.py` and `api/routes/progress.py`

- [ ] `chapters.py` hosts `GET /books/{id}/chapters` and `GET /books/{id}/chapters/{n}`.
- [ ] `progress.py` hosts `POST /books/{id}/progress`. Hosts `ProgressRequest`, `ProgressResponse`.
- [ ] Register both routers in `main.py`.
- [ ] Run `pytest tests/test_chapters_endpoints.py -v` → pass.

---

## Task 11 — `api/routes/query.py`

- [ ] Move `POST /books/{id}/query` body verbatim from `main.py:826-906`, threading `processed_dir` explicitly.
- [ ] Env-flag branch (`BOOKRAG_USE_TRIPLETS`) stays in the route — it's route-level orchestration.
- [ ] Register router.
- [ ] Run `pytest tests/test_query_endpoint.py -v` → pass.

---

## Task 12 — `api/routes/graph.py`

- [ ] Move `/graph/data` and `/graph` endpoints. The inline vis.js HTML template stays an f-string (out of scope to Jinja-ify).
- [ ] Register router.
- [ ] Run `pytest tests/ -q` → 1036.

---

## Task 13 — Verify exit criteria

- [ ] `wc -l main.py` < 450. Expected ≈ 85 LOC post-refactor.
- [ ] `wc -l pipeline/cognee_pipeline.py` < 500. **Risk:** may land around 600 LOC. Contingency: move `_save_batch_artifacts` to `pipeline/batch_artifacts.py` (~50 LOC saved) and the `_format_*` helpers (lines 224-283) to `pipeline/prompt_formatters.py` (~60 LOC saved).
- [ ] Snapshot diff:
```bash
python -m pytest tests/ --collect-only -q | grep "::" | sort > test-snapshot-after.txt
diff test-snapshot.txt test-snapshot-after.txt
```
  Expected: exactly one added test ID (T5's new test). Zero deleted. Zero renamed.
- [ ] `pytest tests/ -q` → 1036 pass.
- [ ] `python -c "import main; print('import ok')"` — clean.
- [ ] Start the server, run one end-to-end smoke cycle (upload → status → chapters → progress → query).

---

## Task 14 — Commit

- [ ] Stage precisely (no `git add -A`).
- [ ] Commit message:

```
refactor: split main.py + cognee_pipeline.py along responsibility lines (slice 2)

Extract FastAPI routes into api/routes/, query synthesis into api/query/,
disk loaders into api/loaders/. Split Plan 3 consolidation helpers and Plan 2
relationship validation out of cognee_pipeline.py. Deduplicate BookNLP→dict
converter into pipeline/booknlp_utils.py. Fix silent model_dump serialization
error with logger.warning. Replace print() in coref_resolver demo with loguru.

main.py: 1104 → <450 LOC. cognee_pipeline.py: 831 → <500 LOC.
Tests: 1035 → 1036 (one new test for the model_dump fix). Zero behavior change
to public API. All Locked Decisions preserved.
```

- [ ] Update `docs/superpowers/slices.md` to mark Slice 2 done.
- [ ] Remove `test-snapshot*.txt` build artifacts.

---

## Critical files for implementation

- /Users/jeffreykrapf/Documents/thefinalbookrag/main.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/pipeline/cognee_pipeline.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/pipeline/orchestrator.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/scripts/reextract_book.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/pipeline/coref_resolver.py
