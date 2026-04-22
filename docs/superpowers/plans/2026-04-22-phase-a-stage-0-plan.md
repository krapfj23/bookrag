# Phase A Stage 0 — Housekeeping & Concurrency Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Goal:** Land the three quick-win improvements that unblock everything downstream in Phase A — remove dead-weight chunk persistence, parallelize extraction, harden structured output.

**Architecture:** Three isolated changes on `pipeline/cognee_pipeline.py` and `models/config.py`. Each task ships independently with TDD. No schema changes (that's Stage 1).

**Tech stack:** Python 3.10, FastAPI, Cognee 0.5.6 LLMGateway, OpenAI `gpt-4o-mini`/`gpt-4.1-mini`, Pydantic v2.

**Source:** `docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md` § Stage 0.

---

### Task 1: Gate `cognee.add` on chunk path behind config flag

**Why:** Bonus A from roadmap. `cognee.add` writes raw chunks to SQLite document store. BookRAG's Approach C doesn't use cognee's default `search()` over raw docs — it reads from Kuzu + LanceDB via explicit DataPoints. The call is dead weight (latency + disk) and violates CLAUDE.md's locked decision: "Approach C — NOT `cognee.add()`". Gate behind a config flag so Slice 2 can flip it on when C1/C2 are resolved.

**Files:**
- Modify: `models/config.py` (add `persist_raw_to_cognee_docstore: bool = False`)
- Modify: `pipeline/cognee_pipeline.py:785-797` (wrap `cognee.add` loop in `if config.persist_raw_to_cognee_docstore`)
- Test: `tests/test_cognee_pipeline.py` (new test)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cognee_pipeline.py — append
def test_run_bookrag_pipeline_skips_cognee_add_when_flag_disabled(tmp_path):
    """Bonus A: cognee.add should NOT be called when persist_raw_to_cognee_docstore is False."""
    from pipeline.cognee_pipeline import run_bookrag_pipeline
    from pipeline.batcher import Batch

    batch = Batch(
        chapter_numbers=[1],
        texts=["hello world"],
        combined_text="hello world",
    )

    with patch("pipeline.cognee_pipeline.extract_enriched_graph", new=AsyncMock(return_value=[])), \
         patch("pipeline.cognee_pipeline.cognee") as mock_cognee, \
         patch("pipeline.cognee_pipeline.add_data_points"), \
         patch("pipeline.cognee_pipeline.run_pipeline", new=AsyncMock()), \
         patch("pipeline.cognee_pipeline._persist_raw_to_cognee_docstore", return_value=False):
        mock_cognee.add = AsyncMock()
        asyncio.run(run_bookrag_pipeline(
            batch=batch, booknlp_output={}, ontology={}, book_id="b",
            chunk_size=1500, chunk_ordinal_start=0, output_dir=tmp_path,
        ))
        assert mock_cognee.add.await_count == 0


def test_run_bookrag_pipeline_calls_cognee_add_when_flag_enabled(tmp_path):
    """Bonus A: cognee.add IS called when persist_raw_to_cognee_docstore is True."""
    from pipeline.cognee_pipeline import run_bookrag_pipeline
    from pipeline.batcher import Batch

    batch = Batch(
        chapter_numbers=[1],
        texts=["hello world"],
        combined_text="hello world",
    )

    with patch("pipeline.cognee_pipeline.extract_enriched_graph", new=AsyncMock(return_value=[])), \
         patch("pipeline.cognee_pipeline.cognee") as mock_cognee, \
         patch("pipeline.cognee_pipeline.add_data_points"), \
         patch("pipeline.cognee_pipeline.run_pipeline", new=AsyncMock()), \
         patch("pipeline.cognee_pipeline._persist_raw_to_cognee_docstore", return_value=True):
        mock_cognee.add = AsyncMock()
        asyncio.run(run_bookrag_pipeline(
            batch=batch, booknlp_output={}, ontology={}, book_id="b",
            chunk_size=1500, chunk_ordinal_start=0, output_dir=tmp_path,
        ))
        assert mock_cognee.add.await_count >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_skips_cognee_add_when_flag_disabled tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_calls_cognee_add_when_flag_enabled -v
```

Expected: both FAIL (helper `_persist_raw_to_cognee_docstore` does not exist).

- [ ] **Step 3: Add config flag**

In `models/config.py`, add alongside existing fields:

```python
    # Bonus A (Phase A Stage 0): when False, skip cognee.add for chunk indexing.
    # BookRAG's Approach C reads from Kuzu+LanceDB via DataPoints; cognee.add is
    # dead weight unless Slice 2 (cognee-search-types) is live and needs raw-doc
    # retrieval via cognee.search(CHUNKS|RAG_COMPLETION).
    persist_raw_to_cognee_docstore: bool = False
```

- [ ] **Step 4: Add helper and gate the loop**

In `pipeline/cognee_pipeline.py`, add module-level helper above `run_bookrag_pipeline`:

```python
def _persist_raw_to_cognee_docstore() -> bool:
    """Return whether cognee.add should index raw chunk text.

    Read lazily from config each call so tests can monkeypatch. See
    docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md § Stage 0.
    """
    from models.config import load_config
    try:
        return bool(getattr(load_config(), "persist_raw_to_cognee_docstore", False))
    except Exception:
        return False
```

Replace the existing loop:

```python
    # Index chunk text in cognee so CHUNKS / RAG_COMPLETION can find it later.
    for c in chunks:
        try:
            await cognee.add(
                data=c.text,
                dataset_name=book_id,
                node_set=[c.chunk_id],
            )
        except Exception as exc:
            logger.warning(
                "cognee.add failed for {} (chunk text not indexed): {}",
                c.chunk_id, exc,
            )
```

with:

```python
    # Bonus A (Phase A Stage 0): gate cognee.add behind config flag.
    # Default False — BookRAG's Approach C reads from Kuzu+LanceDB, not
    # cognee's raw-doc store. Slice 2 will flip this on when chunk retrieval
    # via cognee.search(CHUNKS|RAG_COMPLETION) is wired up (blocked on C1/C2).
    if _persist_raw_to_cognee_docstore():
        for c in chunks:
            try:
                await cognee.add(
                    data=c.text,
                    dataset_name=book_id,
                    node_set=[c.chunk_id],
                )
            except Exception as exc:
                logger.warning(
                    "cognee.add failed for {} (chunk text not indexed): {}",
                    c.chunk_id, exc,
                )
    else:
        logger.debug(
            "Skipping cognee.add for {} chunks (persist_raw_to_cognee_docstore=False)",
            len(chunks),
        )
```

- [ ] **Step 5: Run the new tests — verify they pass**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_skips_cognee_add_when_flag_disabled tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_calls_cognee_add_when_flag_enabled -v
```

Expected: both PASS.

- [ ] **Step 6: Run the existing ordinal test — verify it still passes**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/test_cognee_pipeline.py::test_run_bookrag_pipeline_assigns_ordinals_and_calls_cognee_add -v
```

Expected: FAIL (the old test asserts `mock_cognee.add.await_count >= 1` but new default is False). Fix the old test by patching `_persist_raw_to_cognee_docstore` to return True in that test's scope, since its purpose is to verify ordinal assignment and node_set format — not the persistence default.

Update the old test's context:

```python
    with patch("pipeline.cognee_pipeline.extract_enriched_graph", new=AsyncMock(return_value=[])), \
         patch("pipeline.cognee_pipeline.cognee") as mock_cognee, \
         patch("pipeline.cognee_pipeline.add_data_points"), \
         patch("pipeline.cognee_pipeline.run_pipeline", new=AsyncMock()), \
         patch("pipeline.cognee_pipeline._persist_raw_to_cognee_docstore", return_value=True):
```

Then re-run — it should PASS.

- [ ] **Step 7: Run full suite — no regressions**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/ --tb=short -q
```

Expected: 1081 passed (1079 baseline + 2 new). No failures.

- [ ] **Step 8: Commit**

```
git add models/config.py pipeline/cognee_pipeline.py tests/test_cognee_pipeline.py
git commit -m "feat(cognee_pipeline): gate cognee.add behind persist_raw_to_cognee_docstore flag

Default False. BookRAG's Approach C reads from Kuzu+LanceDB via DataPoints;
cognee.add is dead weight unless Slice 2 (cognee-search-types) is live. Slice 2
will flip the flag on when C1 (result shape) and C2 (cognify() requirement) are
resolved.

Phase A Stage 0 / Bonus A — see
docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md."
```

---

### Task 2: Parallelize chunk extraction with `Semaphore(10)`

**Why:** Item 6 from roadmap. Current loop at `extract_enriched_graph:370-420` is sequential (one LLM call per chunk, awaited in order). For a 5-chunk batch that's 5× latency. `asyncio.gather` with a semaphore-bounded concurrency of 10 parallelizes without tripping OpenAI tier rate limits.

**Files:**
- Modify: `pipeline/cognee_pipeline.py:365-420` (restructure loop)
- Test: `tests/test_cognee_pipeline.py` (concurrency test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cognee_pipeline.py`:

```python
def test_extract_enriched_graph_parallelizes_up_to_semaphore_limit():
    """Item 6: chunk extraction runs concurrently (up to EXTRACTION_CONCURRENCY)."""
    from pipeline.cognee_pipeline import extract_enriched_graph, ChapterChunk, EXTRACTION_CONCURRENCY
    from models.datapoints import ExtractionResult

    chunks = [
        ChapterChunk(text=f"chunk {i}", chapter_numbers=[1], start_char=0, end_char=10, ordinal=i)
        for i in range(20)
    ]

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_llm_call(*args, **kwargs):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        async with lock:
            in_flight -= 1
        return ExtractionResult(characters=[], locations=[], events=[],
                                relationships=[], themes=[], factions=[])

    with patch("pipeline.cognee_pipeline.LLMGateway.acreate_structured_output",
               new=fake_llm_call), \
         patch("pipeline.cognee_pipeline.render_prompt",
               return_value=("sys", "user")):
        asyncio.run(extract_enriched_graph(chunks=chunks, booknlp={}, ontology={}))

    assert max_in_flight <= EXTRACTION_CONCURRENCY, \
        f"max_in_flight={max_in_flight} exceeded cap={EXTRACTION_CONCURRENCY}"
    assert max_in_flight >= 2, \
        f"max_in_flight={max_in_flight} suggests sequential execution, not parallel"
```

- [ ] **Step 2: Run — verify it fails**

Expected: import error on `EXTRACTION_CONCURRENCY`.

- [ ] **Step 3: Refactor the chunk loop**

In `pipeline/cognee_pipeline.py`, add module-level constant near the top:

```python
# Item 6 (Phase A Stage 0): cap concurrent LLM calls during per-chunk extraction.
# 10 is conservative vs. OpenAI Tier 3+ (allows ~50 concurrent) and Anthropic Tier 2+
# (~50). Tunable if telemetry shows headroom.
EXTRACTION_CONCURRENCY = 10
```

Refactor `extract_enriched_graph` (around line 334-447). The outer structure stays — keep stats accumulation, per_chunk_extractions collection, and the downstream merge/consolidate path. Only the LLM-call inner loop changes from sequential to a semaphore-bounded `asyncio.gather`.

New structure for the per-chunk block:

```python
    sem = asyncio.Semaphore(EXTRACTION_CONCURRENCY)

    async def _extract_one(i: int, chunk: ChapterChunk) -> tuple[int, ChapterChunk, ExtractionResult | None]:
        async with sem:
            logger.info(
                "Extracting from chunk {}/{} (chapters {}, ~{} tokens)",
                i + 1, len(chunks), chunk.chapter_numbers, chunk.token_estimate,
            )
            system_prompt, text_input = render_prompt(chunk, booknlp, ontology)
            last_error: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    extraction = await LLMGateway.acreate_structured_output(
                        text_input=text_input,
                        system_prompt=system_prompt,
                        response_model=ExtractionResult,
                    )
                    return i, chunk, extraction
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "LLM extraction attempt {}/{} failed for chunk {}: {}",
                        attempt, max_retries, i + 1, exc,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
            logger.error(
                "All {} attempts failed for chunk {}. Last error: {}",
                max_retries, i + 1, last_error,
            )
            return i, chunk, None

    results = await asyncio.gather(*[_extract_one(i, c) for i, c in enumerate(chunks)])
    # Preserve chunk order in downstream merge (asyncio.gather preserves order).
    for i, chunk, extraction in results:
        if extraction is None:
            continue

        # Plan 2: validate relationships ...
        extraction = _validate_relationships(extraction)

        # Accumulate stats ...
        extraction_stats["characters"] += len(extraction.characters)
        extraction_stats["locations"] += len(extraction.locations)
        extraction_stats["events"] += len(extraction.events)
        extraction_stats["relationships"] += len(extraction.relationships)
        extraction_stats["themes"] += len(extraction.themes)
        extraction_stats["factions"] += len(extraction.factions)

        per_chunk_extractions.append(extraction)
        if getattr(chunk, "ordinal", None) is not None:
            batch_chunk_ordinals.append(chunk.ordinal)

        logger.info(
            "  Chunk {}: extracted {} characters, {} events, {} relationships",
            i + 1, len(extraction.characters), len(extraction.events),
            len(extraction.relationships),
        )
```

- [ ] **Step 4: Run the new test — verify pass**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/test_cognee_pipeline.py::test_extract_enriched_graph_parallelizes_up_to_semaphore_limit -v
```

Expected: PASS with `max_in_flight` between 2 and 10.

- [ ] **Step 5: Full suite — no regressions**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/ --tb=short -q
```

Expected: all previous tests + new concurrency test pass.

- [ ] **Step 6: Commit**

```
git add pipeline/cognee_pipeline.py tests/test_cognee_pipeline.py
git commit -m "perf(cognee_pipeline): parallelize chunk extraction with Semaphore(10)

Restructures extract_enriched_graph's per-chunk loop from sequential awaits to
asyncio.gather bounded by Semaphore(EXTRACTION_CONCURRENCY=10). 5× wall-clock
speedup on typical 5-chunk batches; no change to extraction semantics
(chunk order preserved through gather, per_chunk_extractions collected in
input order).

Conservative vs OpenAI Tier 3+ (~50 concurrent allowed) and Anthropic Tier 2+
(~50). Tunable if telemetry shows headroom.

Phase A Stage 0 / Item 6."
```

---

### Task 3: OpenAI `strict: true` structured output

**Why:** Item 6 from roadmap. OpenAI's strict mode rejects any schema deviation — no silent "close-enough" JSON. Prevents the class of bugs where a field comes back as `None` when the schema says `str`. Cognee's `LLMGateway.acreate_structured_output` path needs auditing to confirm/enable strict.

**Files:**
- Audit: `ExtractionResult` and nested models in `models/datapoints.py` for strict-mode compatibility (no `Union` at root, no `$ref`, all fields required+nullable-explicit).
- Investigate: `LLMGateway.acreate_structured_output` — does it pass `strict: true` already, or opt in?
- Modify: `models/config.py` (add `llm_strict_json: bool = True`)
- Modify: `pipeline/cognee_pipeline.py` if LLMGateway doesn't support strict directly — may need to bypass LLMGateway for OpenAI direct path.
- Test: `tests/test_datapoints.py::test_extraction_result_schema_is_openai_strict_compatible`

**Sub-task 3a: Schema audit (non-mutating)**

- [ ] **Step 1: Write the schema-compatibility validator test**

```python
# tests/test_datapoints.py — append
def test_extraction_result_schema_is_openai_strict_compatible():
    """Item 6: ExtractionResult schema must satisfy OpenAI strict-mode rules:
    - No $ref or recursion
    - No oneOf at any level
    - No anyOf at root
    - additionalProperties: false on every object
    - All properties must be in 'required'
    """
    from models.datapoints import ExtractionResult
    schema = ExtractionResult.model_json_schema()

    def walk(node, path="root"):
        if not isinstance(node, dict):
            return
        assert "oneOf" not in node, f"oneOf disallowed by strict mode at {path}"
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, \
                f"additionalProperties must be false at {path}"
            props = set((node.get("properties") or {}).keys())
            required = set(node.get("required") or [])
            assert props == required, \
                f"all properties must be required at {path}: missing={props-required}"
        for key, value in node.items():
            if isinstance(value, dict):
                walk(value, f"{path}.{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    walk(item, f"{path}.{key}[{i}]")

    walk(schema)
    # $ref resolution: flattened schemas for strict mode shouldn't contain refs.
    # Pydantic emits $defs + $ref by default; log but don't fail here — the
    # LLM call site is responsible for inlining refs before sending.
```

- [ ] **Step 2: Run — observe what fails**

Expected: test fails on missing `additionalProperties: false` and/or `required` mismatch. Record exactly which paths fail.

- [ ] **Step 3: Decide scope based on failures**

If the schema is broadly non-compliant (likely — Pydantic's default schema emits `anyOf` for `Optional[X]` and doesn't set `additionalProperties: false`): **this task needs Stage 1 to land first** because Stage 1 restructures DataPoints (provenance, valence, cluster_id). Fixing the schema twice is waste.

Record the compatibility audit findings in `docs/superpowers/reviews/2026-04-22-openai-strict-mode-audit.md` and **skip the rest of Task 3 for Stage 0**. Move to Task 4.

If the schema is mostly compliant with <5 targeted fixes needed: proceed to sub-task 3b.

**Sub-task 3b: Enable strict mode at the LLM call site (conditional on 3a)**

Only execute if 3a audit shows the schema is near-compliant.

- [ ] **Step 4: Add config flag**

```python
# models/config.py
    # Item 6 (Phase A Stage 0): enable OpenAI structured-output strict mode.
    # Ignored when llm_provider != "openai".
    llm_strict_json: bool = True
```

- [ ] **Step 5: Investigate LLMGateway strict support**

Inspect `cognee/infrastructure/llm/LLMGateway.py` (check the venv). Determine whether `acreate_structured_output` forwards a `strict` kwarg to the underlying OpenAI client. If not, bypass it for OpenAI with a direct `openai.AsyncOpenAI().beta.chat.completions.parse` call gated on `config.llm_provider == "openai" and config.llm_strict_json`.

- [ ] **Step 6: Implement the strict call path (if not already strict)**

Details deferred until 3a audit decides scope.

- [ ] **Step 7: Commit (if 3b executed)**

---

### Task 4: File upstream Kuzu empty-list PR

**Why:** Bonus B from roadmap. CLAUDE.md notes BookRAG patches cognee's `upsert_edges.py` and `upsert_nodes.py` locally to guard against empty lists. Upstreaming removes local maintenance burden.

**Files:** None in this repo. This task produces a PR against topoteretes/cognee.

- [ ] **Step 1: Locate patched files in venv**

```
find /Users/jeffreykrapf/Documents/thefinalbookrag/.venv -name "upsert_edges.py" -o -name "upsert_nodes.py" 2>/dev/null
```

- [ ] **Step 2: Diff against upstream cognee 0.5.6**

Clone `https://github.com/topoteretes/cognee` at tag `0.5.6`, diff. Confirm the exact guard is not in upstream.

- [ ] **Step 3: Open an issue**

Via `gh`: `gh issue create --repo topoteretes/cognee --title "bug(graph-kuzu): add_nodes/add_edges crash on empty input" --body "..."` with repro:

```python
from cognee.infrastructure.databases.graph import get_graph_engine
engine = await get_graph_engine()
await engine.add_nodes([])   # KuzuException / pandas ValueError on empty DataFrame
await engine.add_edges([])
```

- [ ] **Step 4: Open a PR with the guard + unit test**

One-line guard at top of each function: `if not nodes: return` / `if not edges: return`. Add a unit test that calls both with empty lists and asserts no raise.

- [ ] **Step 5: Record the PR URL in `docs/superpowers/reviews/`**

---

## Execution notes

- **Task 4 is async:** file and forget. Don't block Tasks 1-3 on upstream review.
- **Task 3 is conditional:** audit first, decide whether to proceed or defer to Stage 1.
- **Test runner:** use `/Users/jeffreykrapf/anaconda3/bin/python -m pytest` — project's `.venv` has a broken build-backend for editable install via uv. Working around that is out of scope for Stage 0.
- **Commit discipline:** no `Co-Authored-By` trailer on any commit (project convention, see user memory).
- **Baseline:** 1079 passing tests at start of Stage 0.
- **Target:** all existing + 2 new (Task 1) + 1 new (Task 2) + 1 new (Task 3a audit) = 1083 passing.
