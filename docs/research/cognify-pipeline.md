# Cognify pipeline internals — research notes and BookRAG pipeline-level proposals

**Date:** 2026-04-22
**Cognee version:** 0.5.6
**Companion doc:** `docs/research/cognee-prompts.md` (prompt-level research)
**Author's intent:** the prompt doc showed what we can borrow at the text-template layer; this doc goes deeper and asks what we can borrow from the **pipeline architecture** — the actual Task chain, chunkers, retrieval ranking, and memify's streaming update mechanics.

## Why this doc

The re-extraction summary (`evaluations/results/2026-04-22-reextraction-summary.md`) flagged that single-run LLM extraction variance — not prompt wording — is the dominant signal in our eval. Moving the next needle probably requires a pipeline change, not another prompt edit. Cognee's internals have several patterns we can port without breaking our spoiler-safe invariant.

## A. Cognify's task chain, named

`cognee/api/v1/cognify/cognify.py` composes 6 Task objects in sequence:

1. `classify_documents` — map file extensions → typed Document classes (Pdf / Text / Csv / DLT row).
2. `extract_chunks_from_documents` — call a chunker (default `TextChunker`); output `DocumentChunk` objects with token-based size guards.
3. `extract_graph_from_data` — LLM extraction via `LLMGateway.acreate_structured_output()`; filters dangling edges; stamps provenance metadata onto every DataPoint recursively.
4. `summarize_text` — per-chunk `TextSummary` DataPoints; skips DLT rows; uses `uuid5(chunk.id, "TextSummary")` for stable IDs.
5. `add_data_points` — persist to graph DB + vector DB; dedups; **optionally** creates and indexes triplet embeddings when `embed_triplets=True`.
6. `extract_dlt_fk_edges` — foreign-key relationships from tabular schemas; no-op for text.

**What BookRAG does today vs Cognee:**

| Cognee step | BookRAG equivalent |
|---|---|
| classify_documents | implicit — we only ingest EPUBs |
| extract_chunks_from_documents | `chunk_with_chapter_awareness` — **custom**, chapter-aware |
| extract_graph_from_data | `extract_enriched_graph` — **custom**, uses our domain `ExtractionResult` DataPoints + BookNLP/ontology context |
| summarize_text | **missing** |
| add_data_points | **same** — we call Cognee's built-in |
| extract_dlt_fk_edges | not applicable |

We're at parity on the structural core. The two gaps worth examining are **summarize_text** (could improve answer context) and **the triplet-embedding option on `add_data_points`** (one-line change, large retrieval win).

## B. Cascade extract — what multi-round extraction actually does

`cognee/tasks/graph/cascade_extract/utils/` implements a three-stage multi-round process (default `rounds=2`):

1. `extract_nodes.extract_nodes()` — round N reads all previously-extracted node labels and prompts for *additional* nodes not already in the set. Dedups by lowercase name.
2. `extract_content_nodes_and_relationship_names()` — second pass that also collects candidate relation names (`is_author_of`, `mentioned_in`, ...). Returns `(all_nodes, all_relationship_names)`.
3. `extract_edge_triplets.extract_edge_triplets()` — given the node set and relation vocabulary, prompt for `(source, relation, target)` triplets. Deduplicates by `(source_id, target_id, rel_name)` and drops triplets whose endpoints aren't in the discovered node set.

**The winning pattern** is the dedup-and-validate state that's carried *between* rounds, not the "multi-round" label itself. Each round's prompt embeds the prior round's results, anchoring the LLM instead of letting it re-generate from scratch.

**Worth stealing for BookRAG:** the **triplet validation pattern** (drop edges whose endpoints aren't in the extracted node set, dedup by triple). Our current `extract_enriched_graph` already returns structured DataPoints via Pydantic, but we don't enforce the "both endpoints must exist" rule programmatically. The spoiler filter handles this at retrieval time (`load_allowed_relationships`), but enforcing it at *extraction* time prunes noise earlier and reduces variance across runs.

A full cascade adoption is not the right move yet — it doubles extraction cost and our primary variance driver is LLM determinism, not missed entities.

## C. Chunkers

`cognee/modules/chunking/`:

- **`TextChunker`** — paragraph-based accumulator. Walks paragraphs, accumulates tokens, yields when the token budget would be exceeded by the next paragraph. Tracks `cut_type` (paragraph / sentence / word) metadata. Respects paragraph boundaries strictly.
- **`LangchainChunker`** — wraps `RecursiveCharacterTextSplitter` with 10-word overlap. Splits recursively down to characters if needed. No semantic-boundary awareness.

Neither knows about chapters. Our `chunk_with_chapter_awareness` already does the right thing for books: it tags chunks with `chapter_numbers` so retrieval can filter by chapter. Cognee's `TextChunker` paragraph accumulation is cleaner than our custom loop, and borrowing its accumulation mechanism as an internal utility (while keeping our chapter-boundary reset) is a drop-in ergonomic win. Not a quality win.

## D. Retrieval internals — how Cognee ranks triplets

`cognee/modules/retrieval/utils/brute_force_triplet_search.py` composes three ranking signals:

1. **Vector distance** (primary) — embeds the query, searches multiple vector collections (`Entity_name`, `TextSummary_text`, `EntityType_name`, `DocumentChunk_text`, `EdgeType_relationship_name`). Gets node/edge distances.
2. **Graph distance penalty** (`triplet_distance_penalty=6.5`) — after vector search, projects a subgraph of hit-nodes and penalizes edges by *hop count* from the query-relevant nodes. Direct edges rank above 2-hop edges.
3. **Feedback weight** (`feedback_influence ∈ [0,1]`) — if a feedback system is wired in, blends node/edge feedback into the composite score.

Score formula (informally): `node_distances + penalty * hop_count + feedback_influence * feedback_weight`.

`graph_completion_retriever.py` wraps this with `wide_search_top_k=100` — retrieve 100 candidates, then re-rank within the subgraph. Output is a list of `Edge` objects passed to the answer prompt.

**Spoiler-safety fit:** compatible. Filtering a list of `Edge` objects by "both endpoints in allowlist" is a one-pass operation that runs BEFORE any answer-synthesis LLM call. This is exactly the hook point BookRAG already owns — we'd just swap our keyword-score pass for Cognee's `brute_force_triplet_search` and then apply `load_allowed_relationships` as a post-filter. Triplet-level vector retrieval is the biggest concrete quality unlock this doc identifies.

## E. Memify's actual task chain

`cognee/tasks/memify/` — not a generic "enrich the graph" layer. Specifically a **feedback-weight streaming update system** built from:

1. `extract_user_sessions.py` — fetch Q&A sessions with user ratings.
2. `extract_subgraph.py` — compute the subgraph of nodes/edges the session cited.
3. `extract_feedback_qas.py` — filter sessions that have ratings.
4. `get_triplet_datapoints.py` — batch the cited triplets for embedding/indexing.
5. `apply_feedback_weights.py` — streaming exponential moving average: `new = old + α * (normalized_score - old)`, clipped to [0,1]. Default α=0.1 (slow trust update).

**Not** an LLM-based entity consolidation pass. Cognee does *not* auto-merge duplicate entity descriptions. If we want that behavior (and the `consolidate_entity_details.txt` prompt suggests it), we'd have to build it ourselves — memify is a different thing.

What memify does give us: a clean pattern for down-ranking low-quality extractions without re-extracting. If a reader flags "this answer cited the wrong thing", we can weight those edges down and let future retrieval prefer others. Orthogonal to spoiler safety, which operates at filter time.

## F. Task framework — `run_tasks.py`

Worth looking at if we're ever refactoring `orchestrator.py`:

- `run_tasks()` takes `data_per_batch=20` (default), splits input into batches, `asyncio.gather()`s all tasks on each batch.
- `Task` auto-detects callable type (async generator / generator / coroutine / function) and batches generator outputs for the next task using `batch_size` from `task_config`.
- Error propagation is strict — any failed data item fails the whole pipeline. No retries (our `DEFAULT_MAX_RETRIES` is homegrown).
- Distributed swap via `COGNEE_DISTRIBUTED` env var — sidecar process pool.
- OpenTelemetry instrumentation on every stage.

**Ergonomic but not load-bearing.** Our orchestrator does fine; adopting `run_tasks` saves ~100 lines but isn't a quality unlock. Defer indefinitely.

## G. Five concrete pipeline-level enhancements for BookRAG, ranked

### 1. Triplet embedding at ingestion (`embed_triplets=True`) — HIGH IMPACT, LOW BLAST

**What:** Pass `embed_triplets=True` to `add_data_points()` in `pipeline/cognee_pipeline.py`. Cognee's built-in constructs `Triplet(from_node, edge, to_node)` records, embeds the concatenated `(source_name, relation_type, target_name, description)` text, and indexes it in a dedicated vector collection.

**Why it matters:** our current triplet retrieval (main.py `_answer_from_allowed_nodes` + `load_allowed_relationships`) is keyword-based. For the Christmas Carol eval, semantic questions like "how does Scrooge change" only fire if the question literal-matches the edge description. Vector triplet search would hit `Marley → warns → Scrooge` for "why does Marley's ghost visit?" even without keyword overlap.

**Spoiler safety:** unchanged. We'd still post-filter the returned edges through `load_allowed_relationships` before synthesis. The filter is applied to the retrieval output, not the vector index.

**Blast radius:** low. One-line change to extraction call, plus a second retrieval path in `main.py` that consults the vector index when triplets are enabled. Fallback to keyword-based retrieval stays.

### 2. Per-chunk text summaries (cognify step 4) — MEDIUM-HIGH IMPACT, MEDIUM BLAST

**What:** Adopt `summarize_text` as a new stage after extraction. One `TextSummary` per chunk, stored as a DataPoint, indexed alongside characters and events.

**Why it matters:** today our answer synthesis sees only extracted entity+relation descriptions. For questions that need narrative context ("what's the tone of chapter 1?" or "how does Scrooge describe his office?") we have nothing to cite — extracted entities are atomic. Chunk summaries are a middle layer between raw text and structured entities, and they follow the same chapter-bound rules.

**Spoiler safety:** high-risk if done naively. Chunk summaries can easily leak forward-chapter content if they're too lossy. Mitigation: summaries inherit the chunk's `chapter_numbers` and the spoiler filter treats them exactly like any other chapter-bound DataPoint. Each summary must be gated the same way PlotEvents are.

**Blast radius:** medium. New DataPoint type (`ChunkSummary`), one new LLM call per chunk at ingestion (doubles extraction cost), retrieval code needs to include the new type in `load_allowed_nodes`.

### 3. Triplet validation at extraction time — MEDIUM IMPACT, LOW BLAST

**What:** Borrow cascade extract's dedup/validate pattern as a post-processing step inside `extract_enriched_graph`. After the LLM returns an `ExtractionResult`, drop any `Relationship` where `source_name` or `target_name` isn't in the extracted `characters` / `locations` / `factions` sets. Dedupe `(source, relation, target)` triples within a batch.

**Why it matters:** the re-extraction surfaced 8 relationships; two were near-duplicates (`Scrooge → employs → Bob Cratchit` appeared twice with different descriptions). The current spoiler filter catches orphan-endpoint relationships at retrieval time, but catching them at extraction time keeps the on-disk artifacts clean.

**Spoiler safety:** no change; this is a pre-storage cleanup.

**Blast radius:** low. Pure post-processing of the `ExtractionResult`; no prompt change. Add tests in `tests/test_cognee_pipeline.py`.

### 4. Entity-consolidation post-pass — MEDIUM IMPACT, MEDIUM BLAST

**What:** A new stage that runs between `extract_enriched_graph` and `add_data_points`. Groups DataPoints by `(type, name)` and `last_known_chapter` bucket, sends each group to a consolidation LLM prompt (per `consolidate_entity_details.txt`), produces one merged description per group.

Important: **never consolidate across chapter-bucket boundaries.** A ch.5 Scrooge description must not bleed into the ch.1 reader's view. The consolidation groups nodes within the same `last_known_chapter`, produces one canonical description per bucket.

**Why it matters:** the exact problem the A/B eval surfaced — "Scrooge — a miserly old man" appears three times in the source cards. Consolidation collapses them into one canonical record per chapter bucket.

**Spoiler safety:** careful but safe. The bucket-per-chapter rule preserves the invariant. Tests must pin it.

**Blast radius:** medium. New prompt, new stage, extra LLM calls per batch. Gate behind a config flag for the initial rollout.

### 5. Chapter-aware chunker refactor — LOW IMPACT, LOW BLAST

**What:** Subclass Cognee's `TextChunker` and reset the accumulator on chapter boundary transitions.

**Why it matters:** our current chunker works; the refactor is purely ergonomic. Saves ~30 lines and picks up Cognee's `cut_type` metadata for free.

**Spoiler safety:** neutral.

**Blast radius:** low. Contained to `cognee_pipeline.chunk_with_chapter_awareness`.

## Recommendations (ranked by what to do next)

1. **Enable triplet embedding at ingestion** — single highest-leverage change this doc surfaces. One-line extraction-call change, add a second retrieval path behind the existing `BOOKRAG_USE_TRIPLETS` flag, benchmark via the existing A/B eval. Do this before any more prompt work.

2. **Add extraction-time triplet validation** — quick cleanliness win; removes near-duplicate rows we already observed. Low-blast; bundle with (1) in the same spec.

3. **Extraction determinism first, then entity consolidation** — the re-extraction summary already identified determinism (temperature=0 or averaged runs) as the real measurement unlock. Entity consolidation pays off more once variance is controlled; otherwise consolidation noise compounds extraction noise. Sequence: determinism → eval stabilizes → consolidation.

4. **Defer everything else.** Per-chunk summaries, chapter-aware chunker refactor, `run_tasks` adoption — each is nice but would absorb effort away from items 1–3 without moving the eval needle.

## What NOT to do

- **Don't call `cognee.cognify()` on the raw EPUB text.** We'd lose our domain DataPoints, BookNLP context, ontology-discovered classes, and the chapter-bounds contract. Locked decision; research reaffirms it.

- **Don't adopt `run_tasks` framework wholesale** just to save lines. The custom orchestrator's crash-resume via `pipeline_state.json` is specific to our async-per-book model; replacing it for cleanliness adds risk without payoff.

- **Don't chase cascade extract for its own sake.** The only reason to add a second LLM pass is if we measure that extraction misses entities. Current evidence points to the opposite: the LLM varies across runs but doesn't miss much in any single run. Solve determinism first, re-measure, then decide.

## One-paragraph synthesis for the project log

Two items from this research are worth implementing before further prompt tuning: enabling `embed_triplets=True` so retrieval uses vector search on relationships instead of keyword match (biggest likely quality win, low blast radius, already fits the spoiler-filter hook), and adding extraction-time triplet validation so the on-disk batches don't carry near-duplicate edges (low-risk cleanliness). Everything else — cascade extract, per-chunk summaries, entity consolidation, chunker refactor, task-framework adoption — is deferred behind extraction-determinism work, which the re-extraction summary already identified as the more fundamental unlock.
