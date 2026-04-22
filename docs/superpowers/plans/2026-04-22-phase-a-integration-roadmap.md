# Phase A Integration Roadmap

**Date:** 2026-04-22
**Source:** `docs/research/2026-04-22-book-to-kg-sota.md` — executive summary + iter 1, 2, 3, 6, 8, 9, 10, 11, 12, 17, 18, 21, 22, 23, 30
**Scope:** 12 Phase-A improvements + 3 bonus items from the overnight research doc. This roadmap sequences them into 6 stages, each of which becomes its own spec + plan + subagent-driven execution cycle.

---

## Sequencing principle

Four forces decide order:

1. **Dependency** — schema changes ripple through the extractor, cache keys, and tests; bundle them.
2. **Cost-first** — caching lands before gleaning so the gleaning cost-multiplier hits a cached prefix.
3. **Ablation sanity** — chunk-size sweep runs *after* prompt/schema changes settle, so the baseline reflects the real pipeline.
4. **Risk isolation** — retrieval-side (spoiler filter two-hop) is orthogonal to extraction and parks alone.

## Pre-work: resolve cognee-search branch

The `feature/cognee-search-integration` worktree is blocked at final merge review with findings **C1** (cognee result shape mismatch with mocks), **C2** (`cognee.add` alone doesn't make chunks searchable — needs `cognify()` or direct vector upsert), **C3** (CLAUDE.md locked-decision violation: the Approach-C rule says no `cognee.add` + default `cognify()`).

**Decision required before Stage 0 kicks off.** C1/C2 imply the Slice-2 search wrappers don't actually retrieve from cognee in prod — only from mocks. Options:

- **A** — Split the branch: merge Slice 1 (chunk-based data model) only; park Slice 2 behind a feature flag until C1/C2 are resolved against real cognee.
- **B** — Fix in place: replace `cognee.add` + CHUNKS search with direct LanceDB query against the Cognee-owned collection, staying inside Approach-C's "custom pipeline" rule.
- **C** — Document as known-limitation and ship: mocks pass, real search falls back to the existing GRAPH_COMPLETION path; revisit at Cognee 1.0.

**Recommendation:** **A**. Slice 1 is clean data-model work (`source_chunk_ordinal`, `chunks.json`, `chapter_to_chunk_index.json`) that downstream stages rely on. Slice 2 wrappers without working retrieval are net-negative. Park Slice 2; resurrect when C2 is understood.

This roadmap assumes **option A** is chosen; all stages that touch chunk ordinals assume Slice 1 is merged.

---

## Stage 0 — Housekeeping & concurrency foundation

Items: **Bonus A** (drop redundant `cognee.add` on chunk path), **Bonus B** (upstream Kuzu empty-list patches), **Item 6** (Anthropic caching + `Semaphore(10)` + OpenAI `strict:true`).

**Why first:** item 6 is the multiplier for everything that follows. Gleaning (stage 3) triples LLM calls per chunk; without caching, gleaning is a cost non-starter. Bonus A removes dead-weight SQLite writes. Bonus B is async (file PR, don't block).

**Work:**
- `pipeline/cognee_pipeline.py:815-825` — delete the `run_pipeline([Task(add_data_points, ...)])` that's shadowed by explicit DataPoint upsert. Gate behind `config.persist_raw_to_cognee_docstore: bool` defaulting `False` for forward-compat with Cognee 1.0.
- `pipeline/cognee_pipeline.py:367-420` — wrap the per-chunk extraction loop in `asyncio.gather` with `asyncio.Semaphore(10)`. Existing `Semaphore(5)` on consolidation (line 613) stays.
- `pipeline/cognee_pipeline.py:310-325` — for Anthropic, split the prompt into (system + ontology + few-shots) cached block and (per-chunk user text) uncached block using `cache_control: {type: "ephemeral"}` on the last cached content block. Minimum 1024 tokens (Sonnet) or 4096 (Opus/Haiku) — confirm ontology+few-shots exceed threshold or caching is silently dropped.
- `models/config.py` — add `llm_strict_json: bool = True`. When `llm_provider == "openai"`, pass `response_format={"type":"json_schema", "strict": true, "schema": ...}`. Flatten any `Optional[X]` to `X | None` with `default=None, required=True`; reject Pydantic `Union` at schema root.
- File upstream issue + PR against topoteretes/cognee for `add_nodes([])` / `add_edges([])` empty-input guards. Ten-line change; does not block local work.

**Tests:**
- `tests/test_cognee_pipeline.py` — assert semaphore caps concurrency (mock the LLM with a latency-counter; run 30 chunks, assert max-in-flight ≤ 10).
- Cache hit telemetry: new test reads the mocked response's `usage.cache_read_input_tokens` and asserts it's > 0 on the second chunk of a batch.
- `tests/test_config.py` — new: `llm_strict_json` toggles OpenAI request payload.
- Strict-mode schema export: add `tests/test_datapoints.py::test_extraction_result_is_strict_compatible` that runs `ExtractionResult.model_json_schema()` through a validator catching `$ref`, `oneOf`, missing `additionalProperties:false`, non-required fields.

**Acceptance:**
- Full `python -m pytest tests/ -v` passes (1046 baseline + new).
- Red Rising Ch.1 ingestion: cache-read-tokens > 80% of input-tokens on chunks ≥ 2.
- Wall-clock improvement ≥ 3× on a 15-chunk batch (10× theoretical, 3–5× realistic under RPM caps).

**Commit discipline:** 3 commits (cognee.add removal, semaphore+caching, strict JSON). No Co-Authored-By trailer.

---

## Stage 1 — Schema bundle

Items: **Item 11** (signed valence + `RelationshipType` enum), **Item 2** (quote-provenance field + substring validator), **Item 8** (BookNLP `cluster_id` on Character), **Item 12** (extractor-version field + content-addressed batch cache).

**Why bundled:** all four touch `models/datapoints.py` and the `ExtractionResult` shape. Bundling means one schema-version bump, one migration of existing `data/processed/*/batches/*.json`, one wave of test updates. Splitting them triples the migration cost.

**Work:**
- `models/datapoints.py:79-92` — `Relationship.relation_type: RelationshipType` enum (FAMILY, ROMANTIC, FRIEND, ALLY, MENTOR, SUBORDINATE, RIVAL, ENEMY, ACQUAINTANCE, UNKNOWN). Add `valence: float` in `[-1, 1]`, `confidence: float` in `[0, 1]`. Document directionality in docstring (MENTOR/SUBORDINATE directional; FAMILY/ROMANTIC/ENEMY symmetric).
- `models/datapoints.py:26-107` — add `provenance: list[Provenance]` to every DataPoint and Relationship. `Provenance` is a new Pydantic model: `chunk_id: str`, `quote: str` (≤200 chars), `char_start: int`, `char_end: int`.
- `models/datapoints.py:26-39` — `Character.booknlp_coref_id: int | None`. None-allowed for non-PER-derived characters (rare edge case); required for coref-derivable ones.
- `models/datapoints.py:228-241` — `ExtractionResult` gains `extractor_version: str` (format `"phase2@YYYY-MM-DD"`), `prompt_hash: str`, `model_id: str`, `schema_version: str`, `cache_key: str`, `created_at: datetime`.
- `pipeline/cognee_pipeline.py:670-734` — extend `_validate_relationships` to drop entries whose provenance fails the substring validator (strict → substring → normalized-whitespace-lowercase fallback). Log-and-drop, don't raise.
- `pipeline/cognee_pipeline.py:467-516` — `_save_batch_artifacts` writes `extractor_version`, `cache_key` into `extracted_datapoints.json`. New helper `_compute_cache_key(prompt_template_hash, model_id, schema_version, ontology_hash, chunk_text_hash, max_gleanings)`.
- `pipeline/coref_resolver.py:70-81` — surface `cluster_id` (= BookNLP `COREF` column) on `CorefCluster`; forward into the sidecar `coref_hints` passed to extraction.
- `prompts/extraction_prompt.txt` — add quote-provenance instructions ("for every extracted entity/event/relationship, emit the 10–200-char verbatim quote that evidences it, plus its char offsets") and the anchored valence scale ("-1 murderous hatred, 0 neutral/professional, +1 devoted love").
- `scripts/migrate_batches_to_phase_a_schema.py` — one-shot migrator for existing `data/processed/*/batches/*/extracted_datapoints.json`. Stamp `extractor_version="pre-phase-a"`, set `provenance=[]`, compute `cache_key=null`. Existing books continue to serve; re-ingestion happens lazily.

**Tests:**
- New `tests/test_provenance.py` — substring validator strict/substring/normalized tiers; offset-drift handling; curly-quote normalization.
- `tests/test_datapoints.py` — RelationshipType enum validation; valence bounds; BookNLP cluster_id optional.
- `tests/test_cognee_pipeline.py` — cache-key determinism (same inputs → same key), cache-key sensitivity (prompt change → key change), cache hit skips LLM call.
- `tests/test_quality_control.py` — gold-set audit: 80%+ of Christmas Carol relationships carry a valid provenance quote; 0 hallucinated quotes (every quote is a substring of its chunk).
- `tests/test_migration_phase_a.py` — migrator idempotent, leaves ready books queryable.

**Acceptance:**
- 30 Christmas Carol relationships: 100% valid `RelationshipType` enum, 100% valence in `[-1,1]`, ≥ 80% have passing provenance (rest dropped, not hallucinated).
- Re-ingest Red Rising Ch.1–3: second run hits the cache for 100% of chunks (0 LLM calls).
- Migrator runs on current `data/processed/` snapshot without data loss; query endpoints unaffected.

**Commit discipline:** 5 commits (schema, provenance validator, coref cluster forwarding, cache key + extractor version, migrator). No Co-Authored-By.

---

## Stage 2 — Prompt engineering

Items: **Item 9** (realis + forbidden-verb constraint), **Item 1** (gleaning loop).

**Why after schema:** gleaning re-emits entities that need provenance fields; realis filter adds `PlotEvent.realis: Literal["actual","generic","other"]`, another schema touch. Doing them on top of Stage 1's settled schema avoids a second migration.

**Work:**
- `models/datapoints.py` — `PlotEvent.realis: Literal["actual","generic","other"] = "actual"` default.
- `prompts/extraction_prompt.txt` — add a REJECT/ACCEPT negative-few-shot block (3–4 pairs). Reject examples: `"Scrooge wondered if Marley would return"` (irrealis/modal under verb of attitude), `"If she had stayed, everything would be different"` (counterfactual), `"He planned to visit his nephew"` (plan, not actualized). Accept examples mirror past-tense asserted events.
- `pipeline/cognee_pipeline.py:334-438` — wrap the single LLM call in a gleaning loop. Config: `max_gleanings: int = 1` (GraphRAG default). Loop keeps full conversation history (system + first_prompt + first_response + CONTINUE + ...) rather than re-sending source. Stop on `max_gleanings` hit OR `LOOP_PROMPT` returning "N"-first-char. Dedupe merged results on `(name, type)` + provenance-quote match.
- Cache-key update: include `max_gleanings` in `_compute_cache_key` signature (already planned in Stage 1 — verify).
- Filter `realis != "actual"` at retrieval, not at extraction. `pipeline/spoiler_filter.py` gets a `realis_filter: bool = True` flag passed from query config.

**Tests:**
- `tests/test_extraction_prompt.py` — realis rejection: 3 hand-crafted passages, verify LLM emits `realis="other"` (via stubbed LLM returning canonical responses) and retrieval filter drops them.
- `tests/test_gleaning_loop.py` — new. Mock LLM returns 2 entities first pass, 3 more on continuation, signals "N" on loop prompt. Assert total entities = 5, conversation-history grows correctly, no source re-sent.
- Gleaning stops on `NO`: mock LLM returns "N" immediately after first pass; assert 1 LLM call total.
- Gleaning caps at `max_gleanings`: mock says "Y" forever; assert loop terminates at N+1 calls.
- `tests/test_quality_control.py` — Christmas Carol Ch.1 gold-set: minor characters (Fred, Belle) recall +20% with gleaning on vs off.

**Acceptance:**
- Christmas Carol Ch.1 entity recall vs hand-gold: +15% minimum from gleaning.
- 30-event audit: ≥ 90% `realis="actual"`; irrealis events correctly labeled and filtered at query time.
- Cost-per-chapter ≤ 2× baseline after caching (gleaning adds ~1.3× calls; cache offsets ~90% of input tokens).

**Commit discipline:** 3 commits (realis field + prompt, gleaning loop, retrieval-side realis filter).

---

## Stage 3 — Chunk-size ablation

Items: **Item 3** (shrink chunk_size 1500→750, ablate, pick).

**Why last for extraction:** ablating against an unimproved baseline measures the wrong thing. Run this only after Stages 0–2 stabilize the pipeline.

**Work:**
- `scripts/benchmark_chunk_size.py` — new. Sweeps `chunk_size ∈ {1500, 1000, 750, 500}`, fixed `max_gleanings=1`, fixed seed, fixed prompt_hash. Ingests Christmas Carol + Red Rising Ch.1–5 per size. Emits JSONL to `data/benchmarks/chunk_size_YYYY-MM-DD.jsonl` with columns: `chunk_size, tokens_in, tokens_out, cost_usd, entity_count, relation_count, provenance_pass_rate, minor_char_recall`.
- `pipeline/cognee_pipeline.py:138-207` — `chunk_with_chapter_awareness()` already parameterizes `chunk_size`. Confirm overlap scales proportionally (target ~10% overlap at 750 = 75 tokens; currently hardcoded? check).
- Switch overlap computation to `chunk_size // 10` (from whatever fixed value exists).
- `config.yaml` — update `chunk_size` to winner after ablation (not pre-committed).

**Tests:**
- `tests/test_benchmark_chunk_size.py` — smoke test: benchmark script runs end-to-end on a 2-chapter fixture, emits valid JSONL, doesn't crash.
- `tests/test_cognee_pipeline.py::test_chunk_overlap_scales` — overlap at `chunk_size=750` is 75 ± 5.

**Acceptance:**
- Benchmark runs on both books, produces the JSONL.
- Winner chosen by: max(minor_char_recall) subject to (cost_usd ≤ 1.5× current baseline AND provenance_pass_rate ≥ 80%). Prior from GraphRAG: expect 750 to win; 500 often over-fragments.
- `config.yaml` updated to winner.

**Commit discipline:** 2 commits (benchmark script, chunk_size update + ablation result appended to research doc).

---

## Stage 4 — Retrieval-side two-hop

Items: **Item 10** (two-hop neighbor fetch in `spoiler_filter`).

**Why parked alone:** zero extraction coupling. Can ship in parallel with Stages 0–3 in principle, but deferring keeps the blast radius contained and the acceptance criteria honest (hard to measure retrieval quality if the graph itself is churning).

**Work:**
- `pipeline/spoiler_filter.py:47-109` — add `expand_two_hop(seed_nodes, allowed, k=20, damping=0.5)` using personalized PageRank over the allowed subgraph. Power-iterate 5× (HippoRAG shows convergence by then).
- `pipeline/spoiler_filter.py:155-241` — `load_allowed_relationships` extended to include edges whose both endpoints are in the expanded set (still respecting chapter-cursor filter).
- `main.py:833` (`/books/{id}/query` handler) — apply expansion *after* spoiler filter allow-mask, *before* LLM context assembly. Hard cap final node count at 30.
- Degree filter: skip seeds whose 1-hop fan > 50; take top-50 by edge-weight first.
- Config knob `config.retrieval.two_hop_enabled: bool = True`; `config.retrieval.two_hop_k: int = 20`.

**Tests:**
- `tests/test_spoiler_filter.py::test_two_hop_expansion_respects_cursor` — seed = Scrooge at Ch.3 cursor; expansion must not include Belle (Ch.2) *or* Fred's nephew-future (Ch.5). Actually, Belle SHOULD be included (Ch.2 ≤ Ch.3); Fred's late-revelation events (>Ch.3) MUST NOT.
- `tests/test_spoiler_filter.py::test_two_hop_caps_at_k` — 100-node synthetic graph, assert returned node count ≤ 30.
- `tests/test_spoiler_filter.py::test_two_hop_degree_filter` — hub node (degree > 50) doesn't blow out expansion.
- `tests/test_spoiler_filter.py::test_ppr_converges` — top-k stable across iterations 5, 10, 20.
- Integration: `tests/test_query_endpoint.py::test_query_uses_two_hop_when_enabled` vs disabled.

**Acceptance:**
- Christmas Carol query "Who visits Scrooge on Christmas Eve?" at Ch.2 cursor: two-hop surfaces Marley's Ghost via Scrooge's edges (Marley is 1-hop from Scrooge, visitation events are 2-hop from the Ghost entity). Baseline one-hop misses the bridging event node.
- No spoiler leaks on 10-question audit set.
- Query latency p50 ≤ 200ms added vs baseline.

**Commit discipline:** 2 commits (PPR expansion implementation, main.py wiring + config).

---

## Stage 5 — Future-ready: GBNF generator

Items: **Bonus C** (GBNF grammar auto-gen from Pydantic).

**Why last:** only relevant to a future local-LLM path. Hosted APIs (OpenAI/Anthropic) already use Stage-0's structured-output. Park as contingency gear.

**Work:**
- `pipeline/grammar.py` — new. `build_gbnf_from_pydantic(Model: type[BaseModel]) -> str`. Use `llama-cpp-python`'s `LlamaGrammar.from_json_schema(Model.model_json_schema())`.
- `scripts/emit_grammars.py` — one-shot emitter writing `grammars/extraction_result.gbnf`.
- `requirements.txt` / `pyproject.toml` — add `llama-cpp-python` as optional extra `local-llm`.

**Tests:**
- `tests/test_grammar.py` — round-trip: generated grammar parses a known-good JSON extraction, rejects a malformed one.

**Acceptance:**
- Grammar file emits without error.
- Sample extraction JSON parses under the grammar.

**No config flip.** This is contingency gear; don't switch the default LLM path.

**Commit discipline:** 1 commit.

---

## Execution model

Each stage is one **subagent-driven-development** cycle:

1. Write a per-stage spec (`docs/superpowers/specs/2026-04-22-phase-a-stage-N-*.md`) pinning acceptance criteria, tests, and file touch-points. Re-use this roadmap as the outline.
2. Write a per-stage plan (`docs/superpowers/plans/2026-04-22-phase-a-stage-N-*.md`) with bite-sized tasks (one action each).
3. Create a worktree off `main`: `.worktrees/phase-a-stage-N`.
4. Run `superpowers:subagent-driven-development` per the plan: implementer → spec reviewer → code quality reviewer per task.
5. Merge to main. Do NOT batch stages into one branch — each stage ships independently.

**Budget guidance:**
- Stage 0: ~3–4 hours active work, ~8 subagent cycles.
- Stage 1: ~6–8 hours, ~14 subagent cycles (largest; five commits, one migrator).
- Stage 2: ~4 hours, ~8 subagent cycles.
- Stage 3: ~3 hours + benchmark wall-clock time (~30 min per chunk_size × 4 = 2 hrs LLM time).
- Stage 4: ~4 hours, ~8 subagent cycles.
- Stage 5: ~1 hour.

Total: ~20 active hours + ~2 hours benchmark wall-clock.

---

## Test strategy across stages

**Baseline:** 1046 tests collected as of 2026-04-22. Every stage adds tests; no stage removes or weakens a test. Full suite passes before merge.

**Known-answer regression:** maintain `tests/golds/christmas_carol_gold.json` (hand-curated entities + relationships per chapter). Stages 1, 2, 3 run a gold-set audit; stage passes only if recall improves or holds vs prior stage.

**Spoiler-safety regression:** maintain `tests/golds/spoiler_audit.json` (10 queries per book, with the earliest chapter at which they become answerable). Stage 4 must not change any "earliest-answerable" values.

**Cost telemetry:** each stage's acceptance check includes a cost measurement on the Red Rising Ch.1–3 benchmark. Log to `data/benchmarks/phase_a_costs.jsonl`. Stage regressing cost >1.5× without recall improvement reverts.

---

## Open questions (flag before Stage 1)

1. **Migration policy for existing books** — do we force-reingest on schema bump, or accept that old books serve via `extractor_version="pre-phase-a"` and have empty `provenance`? Roadmap assumes lazy reingestion; confirm.
2. **BookNLP coref quality** — BOOKCOREF paper reports ~20-point F1 drop on full novels. If cluster_id is unreliable, Stage 1's identity-keying on `(book_id, booknlp_coref_id)` degrades fuzzy-name merging. Need a fallback (keep name-keyed merge as a gate when `cluster_id` is missing or clusters < 3 mentions).
3. **Strict-mode schema breakage** — current `ExtractionResult` may use `Union` or `Optional` patterns that OpenAI strict mode rejects. Audit before Stage 0 ships; worst case, restructure DataPoint unions as discriminated wrappers.
4. **Cognee 1.0 migration window** — Bonus A gates `cognee.add` removal behind a config flag; if Cognee 1.0 changes `search()` semantics, flip the flag. Track 1.0 release notes.

---

## Out of scope (Phase B or beyond)

- Switching extractor to Anthropic Claude (currently OpenAI-default); Phase B.
- Replacing BookNLP with maverick-coref (license-blocked).
- Custom fine-tuned extractor; Phase C.
- Frontend changes; none in Phase A.
- Cognee 1.0 migration; wait for GA.
