# Triplet indexing + GraphRAG evaluation framework

**Date:** 2026-04-22
**Branch:** `feat/fog-of-war-phase-0`
**Parent research:** conversation thread investigating cognee `cognify` + `memify` internals.

## Problem

Today `_answer_from_allowed_nodes` in `main.py` returns only entity-typed DataPoints (Character, Location, Faction, Theme, PlotEvent). `Relationship` records are present on disk but NOT surfaced as first-class retrieval units — the user sees "Scrooge — a miserly old man" three times but never "Scrooge → visited_by → Marley's Ghost (ch.1)". Two concrete problems this causes:

1. **Coarse citations.** Cited sources are entity blobs rather than relationships. The chat answers correctly but shows "what an entity is" rather than "what happened".
2. **No way to measure answer quality regressions** across changes to the query pipeline. We have unit tests but no end-to-end quality harness.

## Goal

Ship two things together so they can measure each other:

1. **Triplet-aware retrieval** — Relationship DataPoints become first-class results, subject to a stricter spoiler rule (both endpoints must be visible to the reader).
2. **GraphRAG evaluation framework** — a reusable fixture + runner that measures answer quality, source precision, spoiler safety, and latency against the real `/query` endpoint. Lets us run A/B comparisons (feature flag OFF vs ON) and track quality over time.

## User stories

- As the BookRAG author, I can flip `BOOKRAG_USE_TRIPLETS` and see how the answer quality shifts on a fixed 12-question benchmark.
- As a reader, I see relationship citations like "Scrooge → nephew_of → Fred (ch.1)" as sources, not just entity blobs.
- As a maintainer, I can rerun the eval suite after any query-path change and immediately see regressions.

## Acceptance criteria

1. `pipeline/spoiler_filter.py` has a function `load_allowed_relationships(book_id, cursor, processed_dir, allowed_nodes=None)` that returns Relationship DataPoints whose `source_name` AND `target_name` are both present in `allowed_nodes`. If `allowed_nodes` is None, it's derived from `load_allowed_nodes`.
2. `main.py:_answer_from_allowed_nodes` gains a second ranking pass that surfaces allowed Relationships as `QueryResultItem` with content like `"{source_name} → {relation_type} → {target_name}"` and chapter derived from the relationship's own `chapter` / `first_chapter`.
3. Environment variable `BOOKRAG_USE_TRIPLETS` (default `false`) gates whether Relationships are included in results. When false, behavior is unchanged.
4. `evaluations/christmas_carol_questions.json` contains 12 question records, each with: `id`, `question`, `max_chapter`, `expected_answer_gist`, `expected_source_chapters: int[]`, `expected_entities: string[]`, `category` ("factual" | "relational" | "thematic").
5. `scripts/eval_query.py` runs the fixture against `http://localhost:8000/query`, in modes `baseline` (flag off) and `triplets` (flag on), and computes per-question + aggregate metrics:
   - **answer_similarity** — OpenAI embedding cosine between `answer` and `expected_answer_gist`.
   - **source_chapter_precision** — fraction of returned source chapters that fall inside `expected_source_chapters`.
   - **entity_recall** — fraction of `expected_entities` that appear somewhere in `answer` or sources (case-insensitive substring).
   - **spoiler_safety** — 1.0 iff zero sources have `chapter > max_chapter`, else 0.0.
   - **latency_ms** — wall-clock of the single `/query` POST.
6. Results are written to `evaluations/results/YYYY-MM-DD-triplet-ab.md` as a human-readable table + per-question details.
7. Backend tests cover: (a) Relationship requires both endpoints allowed, (b) config flag gates the behavior, (c) triplet result item shape is correct.
8. No existing test regresses. `pytest` count stays ≥ 948.

## Non-goals (explicit)

- **Description consolidation** — deferred to a follow-up slice. Duplicate entity descriptions are real but orthogonal to triplets.
- **Feedback weights** — deferred.
- **Session learning / cognify_session** — deferred; trust model not designed.
- **New DataPoint type** — we DO NOT add a dedicated `Triplet` DataPoint. Relationships already ARE triplets; we promote them to first-class retrieval instead of persisting a derived representation.
- **Cognee runtime setup fix** — the `SearchPreconditionError` from cognee.search is still present. Out of scope. The pre-filter path already bypasses it.
- **Embeddings-at-ingestion changes** — no pipeline re-ingestion required. We work over the existing on-disk batch outputs.

## Data contracts

### On disk (unchanged, observed)

`data/processed/{book_id}/batches/batch_NN/extracted_datapoints.json` is a flat list. Relationship entries look like:

```json
{
  "type": "Relationship",
  "source_name": "Scrooge",
  "target_name": "Marley",
  "relation_type": "business partner of",
  "description": "Marley was Scrooge's dead business partner whose ghost appears...",
  "chapter": 1,
  "first_chapter": 1,
  "last_known_chapter": 1
}
```

### API response (additive)

`QueryResponse.results[*]` gets one new optional field:

```ts
interface QueryResultItem {
  content: string;           // "Scrooge → business partner of → Marley" for triplets
  entity_type: string | null; // "Relationship" for triplets, else the entity type
  chapter: number | null;
  // NEW — optional; only set for triplets
  relation?: {
    source: string;
    relation_type: string;
    target: string;
  };
}
```

If the frontend doesn't consume `relation` it's harmless. `AssistantBubble` sources render `content` as-is, so triplet sources already look like the arrow format.

### Eval fixture schema

```ts
interface EvalQuestion {
  id: string;                       // "cc-001"
  question: string;
  max_chapter: number;              // what the reader has unlocked
  expected_answer_gist: string;     // 1-2 sentence ground truth
  expected_source_chapters: number[];
  expected_entities: string[];      // names/terms that must appear somewhere
  category: "factual" | "relational" | "thematic";
}
```

## Architecture

```
main.py:query_book
  ├─ load_allowed_nodes(book_id, cursor)           -- existing
  ├─ load_allowed_relationships(book_id, cursor,   -- NEW
  │     allowed_nodes)                             --   gated by BOOKRAG_USE_TRIPLETS
  ├─ _answer_from_allowed_nodes(nodes + rels)      -- ranks both, returns interleaved
  └─ _complete_over_context(answer text)           -- unchanged
```

The key spoiler invariant — "a relationship is only visible if both endpoints are visible" — lives in `load_allowed_relationships`. Tests pin that invariant even if the node-level filter changes shape later.

## Evaluation metrics rationale

- **answer_similarity** is a soft signal (embeddings overlap) — not a hard pass/fail. Report cosine scores; we watch deltas, not absolute values.
- **source_chapter_precision** catches the most common query-path bug: sources from wrong chapters. Sharp signal.
- **entity_recall** is a proxy for "did the right names show up". Surface-level but robust against paraphrase.
- **spoiler_safety** must be 100% always. Anything less is a ship-blocker.
- **latency_ms** documents cost. A triplet pass adds O(allowed_rels) work; we want it to stay under 2× baseline.

## Success criteria for the whole feature

- Triplets flag ON: `answer_similarity` and `entity_recall` each ≥ baseline (OR within noise, ±0.03 cosine, ±5%).
- Triplets flag ON: `source_chapter_precision` ≥ baseline.
- Triplets flag ON: `spoiler_safety` = 1.0 on every question.
- Triplets flag ON: `latency_ms` ≤ 1.5× baseline.
- `pytest` stays green; new tests cover the invariant.
- Eval results committed; future PRs can compare.

## Out-of-scope risks to flag later

- The triplet description (`r.description`) is LLM-extracted and may contain paraphrased spoilers even when endpoints are within cursor. Mitigation: rely on the chapter-gate and trust the extraction's `chapter` field to bound scope. Future hardening: re-run the spoiler filter on the description text itself.
- Triplet retrieval by keyword isn't great for synonym-heavy questions. A future step is to route triplets through vector search once Cognee's DB initialization is resolved.
