# Slice 2 — cognee-search-types PRD

**Date:** 2026-04-22
**Parent:** Cognee search integration (Option B — 3 new search types)
**Depends on:** `2026-04-22-slice-1-chunk-based-data-model.md`

## Goal

Wire three cognee search types into `POST /books/{book_id}/query` with chunk-ordinal-based spoiler filtering:

1. **`CHUNKS`** — return raw passages from cognee's vector store, filtered to `source_chunk_ordinal ≤ reader_ordinal`.
2. **`RAG_COMPLETION`** — retrieve filtered chunks via CHUNKS, then synthesize an answer via our existing LLM completion path (not cognee's built-in RAG, which can't enforce our spoiler filter).
3. **`GRAPH_COMPLETION_COT`** — chain-of-thought graph completion, with cognee's subgraph restricted via `node_name=[allowed names]` computed from the allowed-DataPoint set, plus a post-filter as defense in depth.

GRAPH_COMPLETION's existing implementation (disk-based keyword ranker + LLM completion) is untouched. Slice 2 ships alongside it — it does not replace it.

## Non-goals

- No frontend changes. `search_type` on `QueryRequest` already accepts arbitrary strings; the values are validated server-side against an allowlist.
- No new search types beyond the three above. Summaries, Cypher, Temporal, Triplet, etc. explicitly skipped.
- No change to GRAPH_COMPLETION behavior. Parity with today.
- No progress-model changes (Slice 1 did all the plumbing).

## Acceptance criteria

1. `POST /books/{id}/query` with `search_type="CHUNKS"` and a reasonable question returns 200 with `result_count > 0` for a book whose reader has progressed past chapter 1, and every `results[*].content` is a passage whose source chunk ordinal is `≤ reader's effective chunk ordinal`. `answer` is empty string (CHUNKS is retrieval-only).
2. `POST /books/{id}/query` with `search_type="RAG_COMPLETION"` returns 200 with a non-empty `answer` string synthesized from the same filtered chunk set as CHUNKS. `results` contains the supporting chunks that were passed to the synthesizer.
3. `POST /books/{id}/query` with `search_type="GRAPH_COMPLETION_COT"` returns 200 with a non-empty `answer` and `results` populated with nodes that all have `source_chunk_ordinal ≤ reader ordinal`.
4. For all three types, setting `current_paragraph` on `POST /progress` shifts the reader ordinal to `chapter_to_chunk_index[current_chapter].first_ordinal + offset_within_chapter`, where `offset_within_chapter` is derived from `paragraph_breakpoints` — so partial-chapter reads filter at paragraph granularity, mapped through chunks.
5. When the allowed-node / allowed-chunk set is empty (reader at chapter 1 paragraph 0), all three types return 200 with `result_count=0` and `answer` equal to the existing GRAPH_COMPLETION fallback string ("I don't have information about that yet based on your reading progress.").
6. Every cognee response is passed through a `filter_results_by_chunk_ordinal(results, cursor)` helper before being serialized to the client — defense in depth even when the upfront `node_name` filter already constrained cognee.
7. If cognee is unavailable (`COGNEE_AVAILABLE=False`) or `cognee.search()` raises, CHUNKS / RAG_COMPLETION / GRAPH_COMPLETION_COT return `502` with `{"detail": "cognee search failed: <search_type>"}`. GRAPH_COMPLETION is unaffected (it doesn't use cognee.search).
8. `node_name` passed to cognee is capped at 500 entries. When truncated, a warning is logged with `allowed_count` and `cap=500`. Which 500 get picked: the most recent (highest ordinal) so the cap favors nodes relevant to the reader's current position.
9. `_ALLOWED_SEARCH_TYPES` in `main.py` is updated to exactly `{GRAPH_COMPLETION, CHUNKS, RAG_COMPLETION, GRAPH_COMPLETION_COT}` — SUMMARIES is dropped from the allowlist (it was never implemented and isn't spoiler-safe).
10. `python -m pytest tests/ -v` passes including the new tests; no regressions in the 923-test baseline + Slice 1 additions.

## Module layout

### New file: `pipeline/cognee_search.py`

```
async def search_chunks(book_id, question, chunk_ordinal_cursor, top_k=15) -> list[QueryResultItem]
async def search_rag_completion(book_id, question, chunk_ordinal_cursor, top_k=15, extra_paragraphs=[]) -> tuple[str, list[QueryResultItem]]
async def search_graph_completion_cot(book_id, question, chunk_ordinal_cursor, top_k=15) -> tuple[str, list[QueryResultItem]]

def _build_allowed_node_names(book_id, chunk_ordinal_cursor, cap=500) -> list[str]
def _filter_results_by_chunk_ordinal(results, cursor, book_id) -> list[QueryResultItem]
def _chunk_ordinal_from_result(result, book_id) -> int | None
```

All three public entry points share:
- Empty-allowed-set short-circuit (returns `("", [])` or `[]`).
- Try/except around the cognee call that re-raises a typed `CogneeSearchError` — caught by `main.py` and converted to `502`.
- Post-filter via `_filter_results_by_chunk_ordinal`.

### Modified: `main.py`

- `_ALLOWED_SEARCH_TYPES` updated (see AC 9).
- `query_book`: switch over `req.search_type`. GRAPH_COMPLETION keeps the current path. The other three dispatch into `pipeline.cognee_search`. The reader's `chunk_ordinal_cursor` is computed once at the top via a new helper `_reader_chunk_ordinal(book_id, current_chapter, current_paragraph)` that reads `chunk_to_chapter_index.json`.
- `QueryResponse` unchanged — the response schema supports all three types already.

### Mapping cognee results → `QueryResultItem`

| Search type | `content` | `entity_type` | `chapter` |
|---|---|---|---|
| CHUNKS | chunk text (truncated to 800 chars if needed) | `"Chunk"` | primary chapter of the chunk (via chunk_id lookup) |
| RAG_COMPLETION | same as CHUNKS for each supporting chunk | `"Chunk"` | same |
| GRAPH_COMPLETION_COT | node `name` + " — " + `description` | DataPoint type (`Character`, `Location`, etc.) | chapter derived from `source_chunk_ordinal` via index |

### Chunk-ordinal lookup for cognee results

Cognee stores chunks with the `node_set=[chunk_id]` we set at ingestion (Slice 1). When `cognee.search(CHUNKS)` returns a result, its metadata includes the `node_set`. `_chunk_ordinal_from_result` extracts `chunk_id`, splits on `::chunk_`, parses the ordinal. If the result lacks a parseable chunk_id (shouldn't happen for books ingested post-Slice-1, but possible for backfilled books where `cognee.add` failed silently), the helper returns `None` and the post-filter drops the result with a debug log.

## Test plan

New `tests/test_cognee_search.py`:
- `test_search_chunks_filters_by_ordinal` — mock `cognee.search` returning 10 chunks (5 above cursor), verify only 5 returned.
- `test_search_rag_completion_synthesizes_answer` — mock returns chunks, verify `_complete_over_context` is called with the filtered set and a non-empty answer comes back.
- `test_search_graph_completion_cot_passes_node_name` — verify `cognee.search` call args include the allowed node_name list and `node_name_filter_operator="OR"`.
- `test_graph_cot_caps_node_name_at_500` — allowed set of 600 nodes, verify only 500 passed and a warning is logged.
- `test_graph_cot_picks_most_recent_500_when_capped` — verify selection preference is highest ordinals first.
- `test_empty_allowed_set_short_circuits` — no cognee call, fallback answer returned.
- `test_cognee_raise_converts_to_search_error` — cognee.search raises RuntimeError, helper raises CogneeSearchError.
- `test_post_filter_drops_result_with_unparseable_chunk_id` — defense-in-depth case.
- `test_chunk_ordinal_from_result_reads_node_set` — unit test for the helper.

Extend `tests/test_query_endpoint.py`:
- `test_query_chunks_returns_filtered_passages` — happy path, mocked cognee.
- `test_query_rag_completion_returns_answer_and_sources` — happy path.
- `test_query_graph_completion_cot_returns_answer_and_sources` — happy path.
- `test_query_unknown_search_type_returns_400` — "SUMMARIES" now rejected.
- `test_cognee_unavailable_returns_502_for_new_types` — stub `COGNEE_AVAILABLE=False`, verify 502 with typed detail for each new type.
- `test_graph_completion_unaffected_by_cognee_unavailable` — GRAPH_COMPLETION still returns 200.
- `test_reader_chunk_ordinal_respects_paragraph_cursor` — set progress with `current_paragraph=5`, verify derived ordinal matches `paragraph_breakpoints[5]`.

## Risks

- **Cognee chunk metadata stability.** The exact shape of `SearchResult.search_result` across cognee SearchTypes is documented but not frozen by a public contract in 0.5.6. If cognee changes how `node_set` surfaces, `_chunk_ordinal_from_result` may need updating. Mitigation: feature-detect — if the primary extraction path returns `None`, fall back to substring-matching the result text against our `chunks.json` before dropping (implemented behind a single helper, easy to revisit).
- **`cognee.search(GRAPH_COMPLETION_COT, node_name=[…500])` prompt size.** 500 node names at avg 20 chars + separators ≈ 10 KB of prompt context on top of cognee's own system prompt. Well within GPT-4o-mini's 128k window, but worth smoke-testing on Red Rising before declaring done.
- **Spoiler filter belt-and-suspenders double-cost.** Passing `node_name` AND post-filtering means cognee does one pass, we do another. That's the point — the post-filter is authoritative — but if cognee's filtering is already tight we're paying for verification. Acceptable: the post-filter walks at most `top_k=15` results.
