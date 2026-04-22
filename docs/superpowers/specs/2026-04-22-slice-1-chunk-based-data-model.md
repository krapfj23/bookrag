# Slice 1 — chunk-based-data-model PRD

**Date:** 2026-04-22
**Parent:** Cognee search integration (Option B — 3 new search types)
**Followed by:** `2026-04-22-slice-2-cognee-search-types.md`

## Goal

Make the chunk the authoritative unit of reader progress and spoiler scope in the backend, while keeping the existing `(current_chapter, current_paragraph?)` API and reading UI unchanged. After this slice lands, every retrieved node and every chunk in cognee is tagged with a stable `chunk_ordinal`, the spoiler filter compares ordinals (not chapters), and `cognee.search(CHUNKS | RAG_COMPLETION | ...)` has real chunk text indexed to search against.

This slice is a prerequisite for Slice 2. It ships no new search types and no user-visible behavior change — GRAPH_COMPLETION answers the same questions the same way, just backed by a finer-grained filter internally.

## Non-goals

- No new cognee search types (that's Slice 2).
- No frontend changes. `ReadingScreen` keeps navigating by chapter and paragraph.
- No changes to `ProgressRequest` / `ProgressResponse` public schema. The wire format stays `{current_chapter, current_paragraph?}`.
- No change to chunk size (`DEFAULT_CHUNK_SIZE` stays 1500 tokens).
- No change to extraction prompts or DataPoint models beyond adding a `source_chunk_ordinal` field.

## User stories

- As the query API, I can compute "has the reader reached this chunk?" for any retrieved chunk or DataPoint so that spoiler filtering is uniform across search types.
- As the ingestion pipeline, I can assign each chunk a stable ordinal that survives restarts and re-queries.
- As a previously-ingested book (Christmas Carol, Red Rising), I can be backfilled with chunk ordinals and cognee-indexed chunk text without re-running the LLM extraction.
- As the reading UI (unchanged), I can POST `{current_chapter: 3, current_paragraph: 12}` and have it translated internally to the correct chunk ordinal for filtering.

## Data model changes

### New persisted artifact: `data/processed/{book_id}/chunks/chunks.json`

Written at the end of the `run_cognee_batches` stage (or by the backfill script for existing books). Shape:

```json
{
  "book_id": "christmas_carol_e6ddcd76",
  "chunk_size_tokens": 1500,
  "total_chunks": 25,
  "chunks": [
    {
      "ordinal": 0,
      "chunk_id": "christmas_carol_e6ddcd76::chunk_0000",
      "batch_label": "batch_01",
      "chapter_numbers": [1],
      "start_char": 0,
      "end_char": 5988,
      "text": "<full chunk text>"
    },
    ...
  ]
}
```

- `ordinal` is 0-indexed, globally monotonic across the whole book.
- `chunk_id` is the cognee `node_name`-safe identifier used when calling `cognee.add(..., node_set=[chunk_id])` and the `source_chunk_ordinal` stamp on DataPoints.
- Chunks are ordered by `(batch_label, chunk_index_within_batch)`, which — given deterministic chunking — matches reading order.

### New persisted artifact: `data/processed/{book_id}/chunks/chapter_to_chunk_index.json`

A lookup for the query-time translation layer. Shape:

```json
{
  "1": {"first_ordinal": 0, "last_ordinal": 4, "paragraph_breakpoints": [0, 3, 7, 12, 18]},
  "2": {"first_ordinal": 5, "last_ordinal": 9, "paragraph_breakpoints": [0, 4, 9, 15]},
  ...
}
```

- Keys are chapter numbers as strings (JSON-safe).
- `first_ordinal` / `last_ordinal` bound which chunks belong to that chapter. A chunk that spans two chapters (rare) is assigned to the chapter where its `start_char` falls.
- `paragraph_breakpoints[i]` gives the chunk ordinal (relative to `first_ordinal`) that contains the start of paragraph `i` within the chapter. Built by walking the raw `chapter_NN.txt` file and mapping each paragraph's char offset into a chunk.

### DataPoint schema addition

Every DataPoint subclass in `models/datapoints.py` gains a `source_chunk_ordinal: int | None = None` field. It's stamped during `extract_enriched_graph` before being persisted and serialized into `extracted_datapoints.json`.

### `reading_progress.json` — unchanged wire format, new derived field

File shape stays `{current_chapter, current_paragraph?}`. The query endpoint computes `current_chunk_ordinal` at read time via the lookup above. No migration needed for existing progress files.

## Spoiler filter rewrite

`pipeline/spoiler_filter.py` gains a new primary function:

```python
def load_allowed_nodes_by_chunk(
    book_id: str,
    chunk_ordinal_cursor: int,  # inclusive upper bound
    processed_dir: Path,
) -> list[dict]:
    """Return DataPoint dicts whose source_chunk_ordinal <= cursor."""
```

The existing `load_allowed_nodes(book_id, cursor, ...)` wraps the new function by translating `cursor` (a chapter number) to a chunk ordinal via `chapter_to_chunk_index.json` (takes `last_ordinal` of that chapter, or `first_ordinal - 1` if cursor indicates "strictly before"). This preserves every current call site.

`effective_latest_chapter(node)` is deprecated in favor of `source_chunk_ordinal`, but stays for one release with a shim that reads ordinal → chapter via the index. Remove in Slice 3 if we do it.

## Ingestion changes

### Modified: `pipeline/cognee_pipeline.py`

`run_bookrag_pipeline` gains a new stage between chunking and extraction:

1. **Assign ordinals.** After `chunk_with_chapter_awareness`, each `ChapterChunk` gets `ordinal` and `chunk_id` attributes based on a per-book counter persisted across batches (the orchestrator owns the counter — see below).
2. **Index chunk text in cognee.** Call `cognee.add(chunk.text, dataset_name=book_id, node_set=[chunk.chunk_id])` for each chunk before extraction. This populates cognee's internal chunk store so `SearchType.CHUNKS` / `RAG_COMPLETION` have text indexed. Best-effort (same semantics as `add_data_points` today — log and continue on failure).
3. **Stamp ordinal on DataPoints.** In `extract_enriched_graph`, after `extraction.to_datapoints()`, set `dp.source_chunk_ordinal = chunk.ordinal` on every DataPoint returned for that chunk.
4. **Persist `chunks.json` + `chapter_to_chunk_index.json`.** After all batches complete, the orchestrator writes both files atomically.

### Modified: `pipeline/orchestrator.py`

- Tracks a `chunk_ordinal_counter: int` per book_id across the `run_cognee_batches` stage so ordinals are monotonic across batches.
- After the last batch, calls a new helper `build_chunk_indexes(book_id, processed_dir)` that walks `batches/*/` to assemble `chunks.json` and walks `raw/chapters/*.txt` + each chunk's `(chapter_numbers, start_char, end_char)` to assemble `chapter_to_chunk_index.json`.

### New script: `scripts/backfill_chunk_ordinals.py`

For each book in `data/processed/`:

1. Re-chunk every batch's `input_text.txt` with `chunk_with_chapter_awareness` (deterministic given same `chunk_size`).
2. Assign ordinals in batch order.
3. Write `chunks/chunks.json` and `chunks/chapter_to_chunk_index.json`.
4. Re-open each batch's `extracted_datapoints.json`, attempt to match each DataPoint to its source chunk by searching its `description` as a substring within chunk text; on match, stamp `source_chunk_ordinal` and rewrite the file. On miss, leave `source_chunk_ordinal = null` and log a warning — these DataPoints get a fallback ordinal equal to `last_ordinal` of the largest `first_chapter`/`last_known_chapter` they mention (so they're at least no worse than chapter-level filtering).
5. Call `cognee.add(chunk.text, dataset_name=book_id, node_set=[chunk.chunk_id])` for every chunk so cognee's vector store gets populated without re-running extraction.

Backfill is idempotent: re-running skips books that already have `chunks/chunks.json` unless `--force` is passed.

## Acceptance criteria

1. Running `python main.py` → uploading a fresh EPUB → pipeline completes → `data/processed/{book_id}/chunks/chunks.json` exists with `total_chunks > 0` and every entry has ordinal, chunk_id, chapter_numbers, start_char, end_char, text.
2. `data/processed/{book_id}/chunks/chapter_to_chunk_index.json` exists with one entry per chapter and monotonically increasing `first_ordinal` values.
3. `data/processed/{book_id}/batches/batch_*/extracted_datapoints.json` — every DataPoint has a non-null `source_chunk_ordinal` that falls in `[0, total_chunks - 1]`.
4. `cognee.search(SearchType.CHUNKS, query_text="Marley", datasets=[book_id], top_k=5)` returns at least one result with text that matches the book's actual chapter-1 content (demonstrates cognee has indexed our chunks).
5. `load_allowed_nodes(book_id, cursor=1, ...)` returns the same set of nodes (up to ordering) as `load_allowed_nodes_by_chunk(book_id, chunk_ordinal_cursor=last_ordinal_of_chapter_1, ...)`.
6. `POST /books/{book_id}/query` with `search_type=GRAPH_COMPLETION` returns an `answer` of at least 20 characters for a reasonable question, matching behavior before this slice (no functional regression).
7. Running `scripts/backfill_chunk_ordinals.py --all` on a checkout with existing Christmas Carol ingestion produces the two new artifacts and leaves `batches/*/extracted_datapoints.json` with ≥ 90% of DataPoints having non-null `source_chunk_ordinal`.
8. `python -m pytest tests/ -v` passes with the new tests (see below) and no regressions in the current 923-test suite.
9. `frontend/` — no code changes, `npm test` and `npm run test:e2e` still pass.
10. `reading_progress.json` files on disk are not migrated or rewritten by this slice.

## Test plan

New `tests/test_chunk_indexing.py`:
- `test_assign_ordinals_monotonic_across_batches` — fixture with 3 batches, verify ordinals are 0..N-1 in reading order.
- `test_build_chapter_to_chunk_index` — ensures `first_ordinal`/`last_ordinal` bound correctly and paragraph_breakpoints have the right length.
- `test_cross_chapter_chunk_assigned_to_start_chapter` — chunk whose char range spans a chapter boundary.
- `test_chunks_json_roundtrip` — write then read, fields survive.

New `tests/test_spoiler_filter_chunk.py` (augments existing `test_spoiler_filter.py`):
- `test_load_allowed_nodes_by_chunk_respects_cursor`.
- `test_load_allowed_nodes_shim_translates_chapter_to_ordinal` — chapter cursor returns same set as the corresponding ordinal cursor.
- `test_node_without_ordinal_falls_back_to_chapter` — graceful handling of backfill misses.

Existing `tests/test_cognee_pipeline.py`:
- Extend the `run_bookrag_pipeline` test to assert `cognee.add` was called once per chunk with correct `node_set` and that returned DataPoints carry `source_chunk_ordinal`.

New `tests/test_backfill_chunk_ordinals.py`:
- `test_backfill_writes_chunks_json` — fixture book with batches but no chunks dir, run backfill, verify artifacts.
- `test_backfill_stamps_ordinals_on_datapoints` — start with `source_chunk_ordinal=None`, run backfill, verify ≥ 90% stamped.
- `test_backfill_is_idempotent` — second run is a no-op.
- `test_backfill_force_overwrites` — `--force` rewrites even if artifacts exist.

No new frontend tests.

## Out of scope (deferred to Slice 3 if done)

- Frontend chunk indicator in `ReadingScreen`.
- `ProgressRequest` migration to chunk ordinals.
- Removing the chapter-based `load_allowed_nodes` shim.
- Chunk-level re-extraction (extraction prompts still see the full batch window).
- Per-paragraph spoiler cursor within a chunk — the current chunk is still included in the allowed set if the reader is mid-chunk. Raw-text paragraph injection keeps handling that case.

## Risks

- **Cognee `cognee.add()` cost.** Indexing every chunk runs cognee's embedder. For Red Rising (~90 chunks) this is ~90 embedding calls per ingestion. Budget implication: roughly the cost of one current extraction batch per book. Worth it for search quality, but flag in the plan.
- **Backfill substring-matching heuristic.** Matching DataPoint descriptions back to source chunks by substring is lossy — descriptions are LLM-synthesized, not verbatim quotes. The 90% acceptance threshold assumes typical cases; books with heavily paraphrased descriptions may score lower. Fallback to chapter-level ordinal keeps correctness.
- **Ordinal stability across re-ingestion.** If the user re-uploads a book, ordinals will be reassigned from scratch. Any stored `reading_progress.json` referring to chunks by ordinal would break — but we're not storing chunk ordinals in progress files (that's Slice 3), so this is a non-issue for now.
