# Phase A Stage 4 — Two-Hop Neighbor Expansion

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.

**Goal:** Surface peripheral-but-relevant entities at query time. Currently keyword ranking alone picks nodes that mention the question's words; a question like "What happens at dinner?" finds Bob Cratchit but misses Tiny Tim, his wife, and the goose. Two-hop expansion adds the graph neighbors of the top keyword hits so relational questions see the connected web.

**Architecture:** Simple BFS over `load_allowed_relationships` (bounded, degree-capped) instead of personalized PageRank — BookRAG graphs are ~50-300 nodes per book, so PPR is overkill and BFS is equivalent in effect at this scale. Expansion happens in `api/query/synthesis.py::keyword_rank_results` after the keyword scan, before the result list is returned.

**Deviations from roadmap:**
- BFS not PPR (simpler, equivalent at this scale; documented)
- Integration point is `api/query/synthesis.py` (current location of the retrieval path), not `main.py:833` (spec was written before the backend refactor that moved synthesis out)

**Source:** `docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md` § Stage 4.

**Baseline:** 1152 passing tests at start of Stage 4.

---

## Task order

1. **Task 1:** `expand_neighbors` helper in `pipeline/spoiler_filter.py` — pure-function BFS over relationships, degree-capped, result-capped.
2. **Task 2:** Wire into `api/query/synthesis.py::keyword_rank_results` behind a config flag.
3. **Task 3:** Config knobs + tests.

All three in one pass; one commit per task.

---

### Task 1 — `expand_neighbors` helper

**Why:** Pure function, easy to test in isolation. Takes seeds + edges, returns expanded node set.

**Signature:**

```python
def expand_neighbors(
    seed_names: set[str],
    relationships: list[dict],  # items from load_allowed_relationships
    degree_cap: int = 50,
    max_result: int = 20,
) -> set[str]:
    """Return seed_names ∪ (1-hop neighbors via allowed relationships),
    dropping seeds whose 1-hop fan exceeds degree_cap, and capping total
    result at max_result.

    Name-keyed because relationships carry source_name/target_name, not UUIDs.
    """
```

**Behavior:**
- Includes every seed name that has <= degree_cap neighbors.
- For high-degree seeds (hubs), still includes the seed itself but skips expansion.
- Result includes the seeds even when the cap trims.
- Deterministic ordering: neighbors appended in the order relationships are seen.

**Tests (`tests/test_neighbor_expansion.py`):**
- Single seed, 3 relationships → seed + 3 neighbors
- Seed with no relationships → just seed
- Hub seed (fan > degree_cap) → seed only, expansion skipped
- Multiple seeds, overlapping neighbors → union, no duplicates
- `max_result` trims result
- Symmetric: seed as source_name OR target_name both count

---

### Task 2 — Wire into keyword retrieval path

**Why:** Currently `keyword_rank_results` returns only nodes that match question keywords. A question like "What happens at dinner?" matches nothing if 'dinner' isn't in descriptions. Seeding from top-N keyword hits and adding their 1-hop neighbors surfaces the relational context the question implies.

**Change:** After keyword scan, take top-5 scored nodes as seeds, expand 1 hop via `load_allowed_relationships`, add any expanded nodes not already in the result list with score 0 (sorted after keyword hits).

**Files:**
- Modify: `api/query/synthesis.py::keyword_rank_results`
- Modify: `models/config.py` (add `retrieval_expand_neighbors: bool = True`, `retrieval_seed_count: int = 5`, `retrieval_expansion_cap: int = 20`)

---

### Task 3 — Tests + commit

Tests in `tests/test_query_retrieval.py` (or existing query tests):
- Expansion disabled: result equals keyword-only
- Expansion enabled, seed with neighbor: neighbor appears in result at lower rank
- Expansion capped: total result <= expansion_cap
- Expansion preserves keyword-hit order at the top

---

## Out of scope

- PPR implementation (deferred; BFS adequate at current scale)
- Cross-book expansion (each book is isolated)
- Vector-similarity seeding (already covered by `vector_triplet_search` in the triplet path)
