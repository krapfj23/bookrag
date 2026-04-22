# Plan: Slice 3 — Test Quality Uplift

**Spec:** `docs/superpowers/specs/2026-04-22-slice-3-test-quality-uplift.md`
**Date:** 2026-04-22
**Mode:** TDD (red → green per task; no green-first shortcuts)

## Embedded Subagent Briefs

### Test subagent
For every task the implementer MUST:
1. Write failing tests first.
2. Run and confirm they fail **for the right reason** (e.g., a unicode test fails on the unicode path, not on a `NameError` from a missing import).
3. Make them pass with the minimum change.
4. Assertions MUST target return values or on-disk artifacts, not `mock.called` / `mock.await_count`. Any new test that only asserts on mock state is rejected in review.

### Generate subagent
- **No production code changes in this slice** except docstring additions (Item 3 table).
- If a test uncovers a real production bug, STOP, write the failing test with `pytest.mark.xfail(reason="real bug, filed as <slice-id>")`, flag controller with a one-line summary, move on. No opportunistic fixes.
- Exception: if a test needs to reference a production class that lacks a docstring, add it in the same commit.

### Review subagent
**Spec reviewer** verifies:
- Every one of the 22 classes in the spec table has a docstring after T4 (ast script in T4 output is empty).
- Test count delta is `collected - baseline >= 20`.
- `TestEntityConsolidationBehavior` class exists with `>=3` tests, each asserting on `result.characters` / `result.locations` content.

**Code-quality reviewer** spot-checks 3 random new tests:
- No duplicated coverage.
- At least one assertion reads from returned data or a file written to disk.

---

## Tasks

### T1 — Add `cognee.config` stub to conftest.py

- [ ] **Red:** Add `tests/test_cognee_pipeline.py::TestConfigureCognee::test_configure_cognee_invokes_set_llm_config` that asserts `cognee.config.set_llm_config` is a `MagicMock` and was called after `configure_cognee(config)` runs. Before conftest change, fails with `AttributeError`.
- [ ] **Green:** In `tests/conftest.py::_install_cognee_mock`, after the LLMGateway block, add:

```python
cognee_config = types.ModuleType("cognee.config")
cognee_config.set_llm_config = MagicMock()
sys.modules["cognee.config"] = cognee_config
cognee.config = cognee_config
```

- [ ] Verify: `pytest tests/test_cognee_pipeline.py::TestConfigureCognee -v` → green. `pytest tests/ -q` → green.
- [ ] Delta: +1 test (1036 total).

### T2 — Add `TestEntityConsolidationBehavior`

- [ ] Append after line 971 in `tests/test_cognee_pipeline.py`, before `TestRunBookragPipeline`.
- [ ] Three tests:
  - `test_consolidate_merges_descriptions_from_every_member`
  - `test_consolidate_preserves_first_chapter_min_invariant`
  - `test_consolidate_multi_bucket_yields_one_output_per_bucket`

```python
class TestEntityConsolidationBehavior:
    """Covers consolidate_entities by asserting on returned ExtractionResult data, not mock state."""

    @pytest.mark.asyncio
    async def test_consolidate_merges_descriptions_from_every_member(self, monkeypatch):
        from models.datapoints import CharacterExtraction, ExtractionResult
        from pipeline import consolidation

        inp = ExtractionResult(
            characters=[
                CharacterExtraction(name="Scrooge", description="A miser in a counting-house.", first_chapter=1, last_known_chapter=1),
                CharacterExtraction(name="Scrooge", description="Haunted by Marley's ghost.", first_chapter=2, last_known_chapter=2),
            ],
            locations=[], factions=[], events=[], relationships=[], themes=[],
        )

        async def fake_merge(members, kind):
            joined = " ".join(m.description for m in members)
            return consolidation._ConsolidatedDescription(description=joined)

        monkeypatch.setattr(consolidation, "_merge_group_with_llm", fake_merge)

        result = await consolidation.consolidate_entities(inp)

        assert len(result.characters) == 1
        merged = result.characters[0].description
        assert "counting-house" in merged
        assert "Marley" in merged
        assert result.characters[0].first_chapter == 1
        assert result.characters[0].last_known_chapter == 2
```

- [ ] Second test: two members with `first_chapter=(3, 1)`; assert `result.characters[0].first_chapter == 1`.
- [ ] Third test: four Characters across two buckets (`last_known_chapter=1` pair + `last_known_chapter=4` pair); assert `len(result.characters) == 2`.
- [ ] Delta: +3 tests (1039 total).

### T3 — End-to-end duplicate-collapse test

- [ ] Append method to `TestRunBookragPipeline`:

```python
@pytest.mark.asyncio
async def test_run_bookrag_pipeline_collapses_duplicates_end_to_end(self, tmp_path, monkeypatch):
    # Build two ChapterChunks with fake LLM returning Scrooge from each batch
    scrooge_a = CharacterExtraction(name="Scrooge", description="from batch A", first_chapter=1, last_known_chapter=1)
    scrooge_b = CharacterExtraction(name="Scrooge", description="from batch B", first_chapter=2, last_known_chapter=2)

    async def fake_llm(*a, **kw):
        marker = kw.get("text_input", "")
        pick = scrooge_a if "batch_a" in marker else scrooge_b
        return ExtractionResult(characters=[pick], locations=[], factions=[], events=[], relationships=[], themes=[])

    monkeypatch.setattr("pipeline.cognee_pipeline.LLMGateway.acreate_structured_output", fake_llm)

    result = await cp.run_bookrag_pipeline(
        book_id="xmas", batch=sample_batch, booknlp_output=sample_booknlp,
        ontology=sample_ontology, output_dir=tmp_path / "batches", consolidate=True,
    )

    scrooges = [dp for dp in result if isinstance(dp, Character) and dp.name == "Scrooge"]
    assert len(scrooges) == 1
```

- [ ] Delta: +1 test (1040 total).

### T4 — Fill 22 class docstrings

- [ ] Add a one-line docstring (from the spec table's "Docstring intent" column) as the first statement of each of the 22 classes.
- [ ] Verify script:

```bash
python3 -c "
import ast, pathlib
missing = []
for f in ['tests/test_cognee_pipeline.py', 'tests/test_main.py', 'tests/test_datapoints.py']:
    tree = ast.parse(pathlib.Path(f).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith('Test') and ast.get_docstring(node) is None:
            missing.append(f'{f}:{node.lineno}:{node.name}')
assert not missing, missing
print('OK')
"
```

Must print `OK`.

- [ ] Delta: 0 tests.

### T5 — Unicode cases for test_datapoints.py (+6 tests)

- [ ] New class `TestUnicodeAndPathEdges`:
  - `test_character_name_curly_apostrophe`
  - `test_character_name_em_dash`
  - `test_location_name_cyrillic`
  - `test_character_name_zero_width_joiner_preserved`
  - `test_extraction_result_json_roundtrip_preserves_unicode`
  - `test_extraction_result_json_roundtrip_idempotent`

```python
def test_character_name_curly_apostrophe(self):
    from models.datapoints import CharacterExtraction
    c = CharacterExtraction(name="D’Artagnan", description="", first_chapter=1, last_known_chapter=1)
    assert c.name == "D’Artagnan"
    assert "’" in c.model_dump_json()
```

- [ ] Delta: +6 tests (1046 total).

### T6 — Malformed JSON + path cases for test_booknlp_runner.py (+5 tests)

- [ ] New class `TestMalformedInputAndPaths`:
  - `test_parse_book_json_truncated_raises_clean_error`
  - `test_parse_book_json_null_where_int_expected`
  - `test_parse_book_json_missing_characters_key`
  - `test_run_with_path_containing_spaces`
  - `test_run_with_nonascii_path`

```python
def test_parse_book_json_truncated_raises_clean_error(self, tmp_path):
    import json
    from pipeline.booknlp_runner import parse_book_json
    p = tmp_path / "book.json"
    p.write_text('{"characters": [{"id": 0, "names": {"Scroo')
    with pytest.raises(json.JSONDecodeError):
        parse_book_json(p)
```

- [ ] Delta: +5 tests (1051 total).

### T7 — Large-input + null-byte cases for test_text_cleaner.py (+5 tests)

- [ ] New class `TestExtremeInputs`:
  - `test_clean_text_handles_megabyte_paragraph`
  - `test_clean_text_strips_or_preserves_null_byte`
  - `test_clean_text_malformed_html_nesting`
  - `test_clean_text_all_whitespace_chapter_returns_empty`
  - `test_clean_text_nbsp_only_chapter_returns_empty`

```python
def test_clean_text_handles_megabyte_paragraph(self):
    from pipeline.text_cleaner import clean_text
    big = "Scrooge. " * 150_000
    out = clean_text(big)
    assert len(out) > 0
    assert "Scrooge" in out
```

- [ ] Delta: +5 tests (1056 total).

### T8 — Unicode tokens for test_coref_resolver.py (+4 tests)

- [ ] New class `TestUnicodeTokens`:
  - `test_tokens_with_cyrillic_preserved_through_resolution`
  - `test_tokens_with_zero_width_joiner_not_split`
  - `test_tsv_entry_with_literal_tab_in_name_raises_clean_error`
  - `test_name_with_curly_apostrophe_aligns_across_mentions`
- [ ] Delta: +4 tests (1060 total).

### T9 — Graph HTML smoke test

- [ ] Append `TestGraphHTMLEndpoint` to `tests/test_main.py`:

```python
def test_graph_html_smoke(self, client, ready_book_fixture):
    response = client.get(f"/books/{ready_book_fixture}/graph")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "<script" in body
    assert ("vis.js" in body) or ("vis-network" in body)
```

- [ ] Delta: +1 test (1061 total).

### T10 — Full suite run + commit

- [ ] `pytest tests/ -v --tb=short` → green, **>=1055 collected** (target 1061).
- [ ] T4 ast script → prints `OK`.
- [ ] `grep -c "assert result\." tests/test_cognee_pipeline.py` >= 3 new assertions.
- [ ] Commit:

```
Slice 3: test quality uplift — +26 tests, 22 docstrings, cognee.config stub

- conftest.py: add cognee.config stub so configure_cognee() is exercised.
- TestEntityConsolidationBehavior: 3 behavior tests on consolidate_entities.
- test_run_bookrag_pipeline_collapses_duplicates_end_to_end: e2e dedup.
- +20 unicode/path/malformed-input edge cases across 4 modules.
- /books/{id}/graph HTML smoke test.
- 22 class docstrings backfilled.
```

## Task Dependencies

```
T1 → T2 → T3
 └→ T4 (parallel with T2/T3 after T1)
T5, T6, T7, T8, T9 parallel after T1.
T10 depends on all of T1-T9.
```

## Expected Final Test Count

1035 + T1(1) + T2(3) + T3(1) + T5(6) + T6(5) + T7(5) + T8(4) + T9(1) = **1061**.
Floor: **>=1055**. Headroom: 6 tests.

## Critical Files

- /Users/jeffreykrapf/Documents/thefinalbookrag/tests/conftest.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/tests/test_cognee_pipeline.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/tests/test_main.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/tests/test_datapoints.py
- /Users/jeffreykrapf/Documents/thefinalbookrag/pipeline/cognee_pipeline.py
