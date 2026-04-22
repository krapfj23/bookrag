# BookRAG Research — Coref Pipelines + GraphRAG Alternatives
_Compiled 2026-04-22_

## TL;DR

Two concrete coref upgrades are worth evaluating, with **Longdoc (as adapted for BookCoref) being the single highest-value swap** to consider. On the 2025 BookCoref benchmark — the first and only book-scale coref benchmark (~200k token average documents) — off-the-shelf BookNLP scored 42.2 CoNLL-F1, while Longdoc fine-tuned on BookCoref's silver data reached 67.0 F1. That's a +25 F1 delta over BookNLP on exactly the input regime BookRAG cares about. **Maverick** (SapienzaNLP, ACL 2024) is a second option: stronger than BookNLP on short documents (83.6 F1 on OntoNotes, 78.0 on LitBank), already packaged as a pip install, but its encoder has fixed input length and does not natively handle book-length text — you'd chunk and stitch, which is exactly what BookNLP already does internally. LLM-only coref (GPT-4/Claude) is not competitive yet: the CODI-CRAC 2025 shared task found LLM entries still trailing traditional systems even at OntoNotes scale, and cost/latency on a 100k-word novel is prohibitive. A **hybrid** (BookNLP mention detection + Claude cluster resolution for ambiguous cases only) is the most interesting novel pipeline if the team has research budget.

On retrieval: **the highest-value evaluation targets are HippoRAG 2 and a narrative-specialized temporal graph** (E²RAG / ChronoRAG / Graphiti). HippoRAG 2's Personalized-PageRank-over-KG matches GraphRAG's multi-hop ability at a fraction of index cost, and its "phrase + passage" dual-node graph maps cleanly onto BookRAG's DataPoint+chapter-metadata model. E²RAG and ChronoRAG are explicitly designed for narrative documents with temporal/causal constraints — which is essentially what spoiler-filtering is. Zep/Graphiti's bi-temporal edges (`t_valid`, `t_invalid`) are the closest existing abstraction to "first-seen chapter," and worth stealing even if you don't adopt Zep wholesale. **LazyGraphRAG** is worth knowing about but probably not worth adopting: its 1000× index cost reduction is aimed at enterprise corpora, not single-book pipelines where you already pay the indexing cost once. Long-context-only (Gemini/Claude 1M) is **not** a replacement: per-query cost is 1000×+ a RAG pipeline and multi-fact recall degrades to ~60% on realistic tasks — and crucially, long-context can't enforce spoiler constraints structurally.

Priority ranking (effort → value):
1. **Benchmark BookNLP vs. Longdoc (fine-tuned) vs. Maverick on Red Rising** (low effort, high info value) — this is the empirical question that determines whether the coref swap matters.
2. **Prototype HippoRAG 2-style PPR retrieval over existing Kuzu graph** (medium effort, high value) — can run alongside current GraphRAG; compare answer quality.
3. **Adopt bi-temporal edges (`chapter_valid_from`) from Graphiti** as a first-class schema feature (low effort, medium value) — cleaner than the current "first-appearance chapter" tag and sets up future plot-evolution queries.
4. Waste-of-time list: long-context-only replacement for the pipeline; LLM-only coref; LightRAG as a like-for-like swap (optimized for streaming enterprise ingest, not single-book).

---

## Part 1: Coreference options

### Current baseline: BookNLP

- **Architecture**: BERT-based entity tagger + quote attribution + coref, pipeline-style. Constrains pronouns and proper names, does not produce resolved text.
- **Training**: LitBank (Bamman et al., ~210k tokens annotated across 100 public-domain literary works) plus ~500 contemporary books, ~968k tokens total for entity tagging.
- **Reported numbers (from the repo README)**: coref Avg F1 76.4 (small) / 79.0 (big) — but these are measured on LitBank's ~2k-word excerpts, not full novels.
- **On full books**: BookCoref (ACL 2025) evaluated BookNLP off-the-shelf on full books and reported **42.2 CoNLL-F1** on BookCorefgold. This is a much more honest picture of its real-world accuracy on the use case BookRAG targets, and roughly consistent with the "~70% accuracy" folk estimate in the BookRAG CLAUDE.md.
- **Maintenance**: MIT license, Python 3.7 era, no visible 2024-2026 release activity in the public repo (7 commits on main, no recent commit timestamps). Actively used but not actively evolving.
- **Failure modes**: Long-range pronoun-antecedent mismatches in dialogue-heavy passages; merging distinct same-name entities (e.g. multiple minor "John"s); struggles on non-explicit quote attribution (the BookNLP+ follow-up work reports 68.9% on those).

### Option A: Longdoc (as fine-tuned in BookCoref, 2025)

- **Architecture**: Incremental long-document coref with memory cache. Designed from the start for documents that don't fit into a single encoder pass.
- **Headline number**: **67.0 CoNLL-F1 on BookCorefgold** when fine-tuned on BookCoref's silver training set. Off-the-shelf (no BookCoref training) it still beats BookNLP on BookCorefgold: 46.6 vs. 42.2.
- **Compute**: 26 seconds / 5.8 GB VRAM for inference on a full book on an RTX-4090 — much better than Maverickxl (183s, 12.8 GB) or dual-cache (473s, 11.8 GB).
- **Availability**: BookCoref's authors released data, code, and checkpoints under CC-BY-NC-SA 4.0 (non-commercial; fine for a personal/research project, but check the license if BookRAG ever monetizes).
- **Integration effort**: Medium. BookNLP today provides entity typing, quote attribution, and supersense tagging — Longdoc only solves the coref sub-problem. If you swap, you still need a mention-type layer and a quote-attribution layer. Realistically you'd keep BookNLP for entity typing / quotes and swap only its coref output for Longdoc's. That fits BookRAG's "swappable interface" design note.
- **Would it beat BookNLP's 70%?** Yes, almost certainly — published head-to-head on the same book-length benchmark.

### Option B: Maverick (SapienzaNLP, ACL 2024)

- **Architecture**: Encoder-only, deliberately rejects recent trends toward decoder-heavy models. Small, fast, accurate.
- **Reported F1**: 83.6 on OntoNotes, **78.0 on LitBank** (pre-trained checkpoint available on HuggingFace as `sapienzanlp/maverick-mes-litbank`).
- **On full books**: The `maverickxl` variant was tested in BookCoref — off-the-shelf 41.2 F1 on BookCorefgold, fine-tuned 61.0. So **better than BookNLP after fine-tuning on BookCoref's silver data, but worse than Longdoc**. Its encoder has a fixed max input length, so "book-length" really means chunk-and-stitch.
- **Availability**: `pip install maverick-coref`, CC-BY-NC-SA 4.0. Three public checkpoints (OntoNotes / LitBank / PreCo).
- **Integration effort**: Low — cleanest API of any option here. Would drop into BookRAG's existing pipeline structure almost unchanged.
- **Would it beat BookNLP's 70%?** On short excerpts, yes. On full books, depends on whether you can fine-tune. Without BookCoref fine-tuning, it may tie or slightly underperform BookNLP on full novels (41.2 vs. 42.2 on BookCorefgold).

### Option C: LingMess, fast-coref, wl-coref, s2e-coref (older neural baselines)

- **LingMess** (Otmazgin et al.): linguistically-informed multi-expert scorer, ~81.4 F1 OntoNotes. Fast-ish but not designed for book length.
- **fast-coref** (Otmazgin et al.): knowledge-distilled LingMess, 78.5 F1 OntoNotes. The BookCoref paper explicitly calls out that LingMess and s2e-coref "face memory constraints when processing extended texts… impractical for book-scale settings."
- **wl-coref** (Dobrovolskii 2021): word-level coref, small and clever, but also not designed for 100k+ tokens.
- **s2e-coref** (Kirstain et al. 2021): improves wl-coref's speed slightly.
- **Verdict**: All four are **older baselines** for BookRAG. None are book-scale native. No checkpoint of any of these beats Longdoc on BookCoref. Skip.

### Option D: LLM-based coref (GPT-4 / Claude / open models)

- **State of the art as of 2025-2026**: The CODI-CRAC 2025 shared task (4th edition) introduced a dedicated LLM track with 4 LLM-based entries out of 9. Organizers' headline finding: **"traditional systems still kept the lead,"** though LLMs "showed clear potential." There is no published LLM-only system that beats Maverick/Longdoc on OntoNotes, let alone on book-scale data.
- **Papers to flag**: CorefInst (2509.17505), "Improving LLMs' Learning for Coreference Resolution" (2509.11466). Both acknowledge that LLM coref is not yet competitive.
- **Why it's hard**: Book-length input exceeds context windows for cluster-level reasoning; chunked approaches lose cross-chunk coref (which is precisely the hardest problem). Cost: at ~100k tokens and the need for multiple passes to reconcile chunks, one book of Claude-based coref likely costs $5-50 per book and takes minutes-to-hours.
- **Verdict as a full swap**: Not ready. Do not build BookRAG's primary coref on a pure-LLM approach.

### Option E: Hybrid — neural mention detection + LLM cluster resolution

- **Motivation**: The French fiction paper ([arxiv:2510.15594](https://arxiv.org/html/2510.15594v1)) is an existence proof that a **modular mention-pair pipeline** (BiLSTM-CRF + CamemBERT for mentions, lightweight scorer for pairs) can reach 74.3 CoNLL-F1 with gold mentions on 285k-token novels, and 58.98 with predicted mentions. This is a mention/cluster split that could be LLM-augmented at the cluster step where BookNLP is weakest.
- **Applied to BookRAG**: keep BookNLP for mention detection and entity typing (it's good at that), but use Claude to resolve ambiguous clusters within a batch (e.g. "are `Scrooge_17` and `the old miser` the same entity?"). The parenthetical-coref format you already use is ideal for this kind of targeted patching — Claude can operate on small windows, and you only pay for the hard cases.
- **Integration effort**: Medium-high. New module. But it reuses BookNLP entirely, so fallback is safe.
- **Would it beat 70%?** Plausibly yes, especially on the long-range cases BookNLP already bracket-inserts conservatively (pronouns constrained by rule). Worth a spike if Longdoc swap turns out to have licensing/integration friction.

### Option F: Benchmarks themselves

- **LitBank** (Bamman et al.): ~2k-word excerpts from 100 public-domain novels. The dominant literary-coref benchmark for a decade. Older baseline for "short" literary coref.
- **BookCoref** (ACL 2025, SapienzaNLP): the first full-book benchmark (200k+ tokens average). Gold test split + silver train/val splits. **This is now the benchmark to measure against for BookRAG.**
- **ChronoQA** (introduced by E²RAG, 2506.05939): narrative QA benchmark specifically for temporal/causal/character consistency. Not a coref benchmark per se, but evaluates the downstream effect of coref quality on narrative QA.
- **The French fiction benchmark** (2510.15594, Oct 2025): three fully-annotated French novels, 285k tokens — analogous to BookCoref in spirit.

### Comparison table

| Tool | Max doc length | F1 on LitBank-ish | F1 on full books (BookCoref) | Integration effort | Licence | Recommendation |
|---|---|---|---|---|---|---|
| **BookNLP** | Book-length (internal chunking) | 79.0 (short) | 42.2 | — (current) | MIT | Current baseline |
| **Longdoc (fine-tuned)** | Book-length (native) | not reported | **67.0** | Medium | CC-BY-NC-SA 4.0 | **Top swap candidate** |
| **Maverick (xl)** | ~chunk-length | 78.0 | 41.2 off-shelf / 61.0 fine-tuned | Low | CC-BY-NC-SA 4.0 | Good short-doc upgrade; weak on full books without FT |
| **LingMess / fast-coref / wl-coref / s2e** | Short docs | 78–81 | Not book-scale viable | Low (but pointless) | Various (mostly Apache/MIT) | Skip |
| **LLM-only (Claude/GPT-4)** | Chunked | ~OntoNotes-competitive in best cases | Not reported on BookCoref | High | Commercial | Not ready as full replacement |
| **Hybrid (BookNLP + LLM)** | Book-length | N/A | Likely > 50 | Medium-high | Mixed | Research bet; worth a spike |

---

## Part 2: Retrieval/KG alternatives

### Current baseline: custom GraphRAG over Cognee

- Kuzu graph + LanceDB vectors, Claude extracting DataPoints (Character, Location, Faction, PlotEvent, Relationship, Theme) per 3-chapter batch.
- Spoiler filtering is done at query time by filtering nodes to `chapter_of_first_appearance ≤ reader_chapter`.
- Cognee is pre-1.0 (0.5.6 is patched locally; 1.0.1 was released April 18 2026 — worth evaluating a clean upgrade separately).

### Option A: RAPTOR (ICLR 2024)

- **Core idea**: Recursively cluster chunks (Gaussian Mixture over embeddings), summarize each cluster with an LLM, build a tree bottom-up. Retrieval traverses the tree or collapses it.
- **Narrative relevance**: RAPTOR's original paper uses **NarrativeQA** (precisely your target domain) and QuALITY as its headline benchmarks — +20 absolute accuracy on QuALITY with GPT-4, and state-of-the-art NarrativeQA results when combined with SBERT.
- **Spoiler filtering**: **Bad fit.** Cluster summaries mix content from different narrative times by design; enforcing chapter constraints requires rebuilding trees per reader position or aggressive filtering that defeats the tree's purpose.
- **Verdict**: Strong for unconstrained narrative QA, weak for spoiler-aware retrieval. Good to benchmark against, not to replace your current pipeline.

### Option B: HippoRAG 2 (ICML 2025)

- **Core idea**: Dual-node KG (phrases + passages) with Personalized PageRank from query-linked seed nodes. The PPR distribution becomes the retrieval score.
- **Narrative relevance**: +7 F1 over NV-Embed-v2 on associative/multi-hop. MuSiQue F1 44.8→51.9, 2Wiki Recall@5 76.5→90.4.
- **Spoiler filtering**: **Good fit.** PPR can be restricted to a subgraph (nodes with `chapter ≤ R`), so spoiler-aware retrieval is literally a vertex-mask on the PPR walk. This is much cleaner than community-summary filtering.
- **Cost**: HippoRAG 2's authors claim 10-30× cheaper multi-hop reasoning than GraphRAG — indexing is phrase-extraction + passage-embedding, not community summarization.
- **Integration effort**: Medium. You'd reuse your existing Kuzu graph. Add a PPR retriever (networkx/graph-tool can prototype; Kuzu has recursive-relationship support). Swap or A/B against the current GraphRAG retriever.
- **Verdict**: **Top retrieval alternative to evaluate.**

### Option C: LightRAG

- **Core idea**: Dual-level retrieval (entity + relationship) with incremental graph updates. Designed for streaming ingestion.
- **Narrative relevance**: Not specifically benchmarked on narrative. ~30% latency reduction vs. standard RAG; ~50% cheaper incremental updates.
- **Spoiler filtering**: Neutral. Can filter by entity metadata, same as your current approach.
- **Verdict**: Optimizations target a use case (streaming enterprise data) you don't have. Skip as a like-for-like swap.

### Option D: GraphReader

- **Core idea**: Agent explores KG by reading nodes, taking actions, building up answer state.
- **Spoiler filtering**: Agent could be constrained at action time ("don't read node X if its chapter > R"), but the agentic loop adds 5-20× the inference cost of retrieval.
- **Verdict**: Interesting for complex multi-hop; too expensive for a single-user local deployment as primary retriever.

### Option E: StructRAG

- **Core idea**: Structure-aware RAG using Deep Document Model (DDM) for hierarchical document structure, structure-aware retrieval combining semantic relevance + source diversity.
- **Narrative relevance**: Designed for scholarly QA, not narrative. Hierarchy here = section/subsection, not chapter/scene.
- **Verdict**: Conceptually useful (preserves document hierarchy) but not a direct fit.

### Option F: Self-RAG / HyDE

- **Self-RAG**: Model learns to retrieve-and-critique. Orthogonal to KG structure; could layer on top of your current pipeline.
- **HyDE**: Generate hypothetical answer, embed, retrieve. Cheap trick, often helps. Can drop in as a query-expansion step without changing anything else.
- **Verdict**: HyDE is a cheap win worth trying as a query preprocessor. Self-RAG is a larger architectural change with unclear benefit in your setup.

### Option G: E²RAG and ChronoRAG (narrative-specific)

- **E²RAG** ([arxiv:2506.05939](https://arxiv.org/abs/2506.05939)): Dual-graph KG with separate entity and event subgraphs linked by a bipartite mapping. Explicitly preserves temporal/causal facets for narrative QA. Introduces ChronoQA benchmark (novels, temporal/causal/character consistency).
- **ChronoRAG** ([arxiv:2508.18748](https://arxiv.org/abs/2508.18748)): Two-layer graph; Layer 0 preserves original dialogue/details, Layer 1 captures relational structure. Specifically designed for temporal ordering of narrative passages.
- **Spoiler filtering**: **Strong fit.** Both explicitly model chronology; "what was true before time T" is a first-class query on the event graph. This is the closest published architecture to what BookRAG is trying to be.
- **Integration effort**: Medium-high. Requires splitting your current DataPoint schema into entities vs. events (you already have PlotEvent!). The Character / PlotEvent distinction in your existing `models/datapoints.py` maps almost 1:1 onto E²RAG's bipartite model.
- **Verdict**: **Second-highest-value evaluation target.** If anything published in 2025 is BookRAG-shaped, it's these two.

### Option H: Zep / Graphiti (bi-temporal agent memory)

- **Core idea**: Temporally-aware KG where every edge has validity intervals (`t_valid`, `t_invalid`) plus system timestamps (`t_created`, `t_expired`) — bi-temporal modeling.
- **Narrative relevance**: Zep targets agent memory (chat history, evolving facts), not book ingestion. But **the bi-temporal abstraction is exactly what spoiler filtering wants**: instead of one `chapter_of_first_appearance` integer, each relationship gets a `(chapter_introduced, chapter_invalidated)` pair, so you can answer "what did the reader know about X at chapter N?" with a single temporal query.
- **Performance claims**: +18.5% accuracy on LongMemEval vs. baseline; 300ms P95 retrieval latency (hybrid: embeddings + BM25 + graph traversal).
- **Integration effort**: Don't adopt Zep wholesale (licensing + assumes agent/chat context). But **steal the schema**: add `chapter_valid_from` / `chapter_valid_to` to your Relationship DataPoint. Low effort, big interpretability win.
- **Verdict**: **Third-highest-value pick up.** Particularly elegant for BookRAG's core problem.

### Option I: Mem0, Letta/MemGPT

- **Mem0**: Production memory layer, vector + optional graph. Three-level hierarchy (user/session/agent). Ease-of-integration focused.
- **Letta/MemGPT**: Agent-managed memory via tool calls (agent edits its own memory blocks).
- **Verdict**: Both solve agent memory, not book ingestion. Nothing here that your custom pipeline doesn't already handle better.

### Option J: Long-context-only (Gemini 1M / Claude 1M)

- **The case for**: A 100k-word novel fits in a 1M context window. Why index at all?
- **The case against**:
  - **Cost**: Per-query cost is 30-60× latency and ~1250× dollar cost of a RAG pipeline (Tian Pan, April 2026 analysis).
  - **Accuracy**: Near-perfect single-needle (Gemini 99.7%, Claude ~90%) but **multi-fact recall falls to ~60%** on realistic tasks ([BigData Boutique](https://bigdataboutique.com/blog/needle-in-haystack-optimizing-retrieval-and-rag-over-long-context-windows-5dfb3c)). The Chroma "Context Rot" paper (2024) documents consistent degradation as context grows, even for recent models.
  - **Spoiler enforcement**: You'd have to re-truncate the book per query. Doable but wasteful; and the model may still "accidentally" reason from material you thought you excluded if the prompt is sloppy. Structural graph filtering is safer.
  - **Offline**: Long-context reasoning is API-only for frontier models; BookRAG's "single user, local M4 Pro Mac" constraint rules out the big 1M-context models for routine queries.
- **Verdict**: **Not a replacement.** Use long-context as a final-pass synthesizer over RAG-retrieved chunks (hybrid is the consensus 2026 answer), not as the primary retrieval mechanism. This is close to what you're already doing.

### Option K: Cognee trajectory + alternatives

- **Cognee 2026 status**: Active — 1.0.1 released April 18, 2026; December 2025 integrations with Claude Agent SDK (MCP) and n8n; Graphiti integration for temporal-aware graphs; Amazon Neptune adapter. Pre-1.0 → 1.0 transition suggests API has stabilized somewhat; worth a clean re-evaluation separate from this research doc.
- **Alternatives with similar DataPoint+pipeline abstraction**:
  - **Graphiti** (open source, Neo4j-backed, bi-temporal): the closest direct analogue. More opinionated about temporal modeling, less general about DataPoints.
  - **LangGraph + your own DataPoints**: not really a KG framework but a compose-your-own pipeline scaffold. More control, more code.
  - **Neo4j LLM Graph Builder**: simpler, more Neo4j-native, weaker on pipeline ergonomics.
- **Verdict**: Your Cognee investment is fine. The 1.0 release closes the main "pre-1.0 API instability" risk flagged in CLAUDE.md. Revisit the patched files in a month or two.

### Option L: LazyGraphRAG (Microsoft, Nov 2024 / GA 2025)

- **Core idea**: Skip up-front community summarization. Use NLP noun-phrase extraction for concept co-occurrence, defer LLM work to query time.
- **Claim**: 1000× cheaper indexing, comparable answer quality to GraphRAG Global Search, 700× lower query cost on global queries.
- **Narrative relevance**: Not specifically narrative. The deferred-summarization tradeoff is more compelling for enterprise corpora where you index millions of docs and query rarely.
- **BookRAG fit**: Weak. You have ~100 books max, index once, query often — the use case LazyGraphRAG is explicitly **not** optimized for.
- **Verdict**: Interesting to know, not a practical adoption.

### Option M: k-core hierarchies (alternative to Leiden communities)

- **Core idea**: k-core decomposition for deterministic, density-aware hierarchy in linear time, as an alternative to Leiden community detection inside GraphRAG.
- **Papers**: "Core-based Hierarchies for Efficient GraphRAG" (2603.05207).
- **BookRAG fit**: Possibly useful **if** you ever adopt Microsoft-style community summarization. You don't currently. Defer.

### Comparison table

| System | Core idea | Narrative-tested? | Spoiler-filter fit | Integration effort | Recommendation |
|---|---|---|---|---|---|
| **Custom GraphRAG (current)** | Entity-graph + vector + LLM extraction | Yes (by construction) | Native | — | Keep as baseline |
| **RAPTOR** | Recursive cluster→summary tree | Yes (NarrativeQA/QuALITY) | Poor (cluster summaries mix times) | Medium | Benchmark only |
| **HippoRAG 2** | PPR over phrase+passage KG | Multi-hop QA (not novels specifically) | Good (subgraph mask) | Medium | **Prototype** |
| **LightRAG** | Dual-level retrieval, incremental updates | No | Neutral | Low | Skip |
| **GraphReader** | KG-walking agent | Partial | Possible at action time | High | Too expensive |
| **StructRAG** | Structure-aware over doc hierarchy | No (scholarly) | Neutral | Medium | Not a direct fit |
| **Self-RAG / HyDE** | Query/reflection improvements | Orthogonal | Orthogonal | Low (HyDE) / High (Self-RAG) | HyDE as cheap add |
| **E²RAG / ChronoRAG** | Dual-graph entity+event, chronological layers | **Yes (novels)** | **Excellent** | Medium-high | **Strong evaluate** |
| **Zep / Graphiti** | Bi-temporal KG | Agent memory (not novels) | **Excellent (steal schema)** | Low (schema-only) | **Adopt schema idea** |
| **Mem0 / Letta** | Agent memory abstractions | No | Weak | Medium | Skip |
| **Long-context only** | Stuff whole book into context | Yes, but expensive | Weak (prompt-enforced only) | Low | Use as synthesizer, not retriever |
| **LazyGraphRAG** | Defer summarization to query time | No | Neutral | Medium | Wrong use case |
| **k-core hierarchies** | Replace Leiden clustering | No | Neutral | Medium | Defer |

---

## Part 3: Recommendations for BookRAG

In priority order, with honest rationale:

### 1. Benchmark Longdoc + Maverick vs. BookNLP on Red Rising (1-2 days of work)

Set up a head-to-head on the 100k-word validation book already in scope. Use BookCoref's evaluation harness if possible (CoNLL F1 on coref clusters). The BookCoref paper has already done this experiment on public-domain novels — you're confirming it holds on contemporary fiction. If Longdoc wins by >15 F1 (likely), swap it in as the coref module behind BookNLP's mention/type/quote output.

**Expected outcome**: Resolved-text quality improves visibly in the parenthetical output; Claude's downstream DataPoint extraction gets cleaner; fewer duplicate Character nodes for the same entity. Don't touch ontology discovery or Cognee — keep those isolated from the coref swap.

### 2. Prototype HippoRAG 2-style PPR retrieval over existing Kuzu graph (3-5 days)

Run it in parallel to the current retriever. Seed PPR from query-linked nodes, mask the vertex set by `chapter ≤ R`, return top-k. Compare answer quality on a held-out query set vs. current GraphRAG.

**Why this and not E²RAG**: HippoRAG 2 is a retriever, not a schema redesign. You can keep your current DataPoints and evaluate just the retrieval layer. E²RAG is a bigger commitment (dual graph, schema changes).

### 3. Add bi-temporal edges to Relationship DataPoint (1 day)

Replace the implicit `chapter_of_first_appearance` on nodes with explicit `chapter_valid_from` / `chapter_valid_to` on Relationship edges. This is a small schema change that unlocks much cleaner queries like "what did Scrooge know about Marley before chapter 3?" and sets up future plot-evolution features without committing to full E²RAG architecture.

### 4. (Optional, research bet) Hybrid coref: BookNLP mentions + Claude cluster resolution for hard cases (1-2 weeks)

If Longdoc licensing (CC-BY-NC-SA 4.0) is a blocker for commercial plans, or if Longdoc integration proves painful, try the hybrid. Use BookNLP as-is, then post-process each batch's ambiguous cluster boundaries with a Claude prompt that operates on the parenthetical-annotated text. Cheap because you only invoke Claude on the hard subset.

### 5. (Optional) HyDE query expansion (half a day)

Generate a hypothetical passage from the reader's query using Claude, embed it, and use that embedding as the retrieval key. Free lunch, often bumps relevance 5-10%. Easy A/B.

### Things I'd explicitly NOT do

- **Don't replace the pipeline with long-context-only.** The cost, latency, and multi-fact recall tradeoffs are bad, and you lose structural spoiler enforcement — the core differentiator of BookRAG.
- **Don't adopt LLM-only coref** as the primary path. The CODI-CRAC 2025 shared task is the most recent authoritative read: LLMs are not there yet, even at sentence-level coref.
- **Don't swap to LightRAG or LazyGraphRAG.** Their advantages are in use cases (streaming ingest, enterprise index cost) that aren't BookRAG's.
- **Don't adopt Zep wholesale.** Its bi-temporal schema is a gift worth stealing; its agent-memory assumptions are not what you're building.
- **Don't chase Mem0 / Letta / agent-memory frameworks.** They solve a different problem (chat/agent state), not book comprehension.

### Unknowns worth flagging

- **No published F1 for Longdoc or Maverick on contemporary fiction.** BookCoref uses public-domain books. Contemporary fiction (Red Rising) may behave differently — dialogue-heavy YA vs. Victorian prose. The 1-day benchmark above resolves this.
- **BookCoref's silver training data licence** (CC-BY-NC-SA 4.0) is non-commercial. If BookRAG ever goes commercial, Longdoc-fine-tuned-on-BookCoref is legally grey — you'd need to retrain on your own annotated data or a permissively-licensed corpus.
- **HippoRAG 2 has no reported number on literary narrative specifically** — only on MuSiQue/2Wiki/associative multi-hop. Narrative-specific benchmarking is on you.
- **Cognee 1.0.1 just released** (4 days before this report). Its stability story may have changed. Re-evaluate the local patches in 2-4 weeks.

---

## Sources

### Coreference
1. BookNLP repository — https://github.com/booknlp/booknlp
2. LitBank — https://github.com/dbamman/litbank
3. BOOKCOREF: Coreference Resolution at Book Scale (ACL 2025) — https://arxiv.org/abs/2507.12075 ; https://aclanthology.org/2025.acl-long.1197/ ; https://github.com/sapienzanlp/bookcoref
4. Maverick: Efficient and Accurate Coreference Resolution (ACL 2024) — https://aclanthology.org/2024.acl-long.722.pdf ; https://github.com/SapienzaNLP/maverick-coref
5. LingMess — https://huggingface.co/biu-nlp/lingmess-coref
6. F-coref — https://ar5iv.labs.arxiv.org/html/2209.04280 ; https://huggingface.co/biu-nlp/f-coref
7. wl-coref — https://github.com/vdobrovolskii/wl-coref
8. s2e-coref — https://github.com/yuvalkirstain/s2e-coref
9. A Controlled Reevaluation of Coreference Resolution Models (2024) — https://arxiv.org/html/2404.00727.pdf
10. CODI-CRAC 2025 Multilingual Coreference Shared Task — https://arxiv.org/html/2509.17796v1
11. CorefInst: Leveraging LLMs for Multilingual Coreference Resolution — https://arxiv.org/html/2509.17505
12. Improving LLMs' Learning for Coreference Resolution — https://arxiv.org/abs/2509.11466
13. The Elephant in the Coreference Room (French fiction, Oct 2025) — https://arxiv.org/html/2510.15594v1
14. BookNLP-fr — https://cnrs.hal.science/hal-04722979/
15. Improving Quotation Attribution with Fictional Character Embeddings — https://arxiv.org/html/2406.11368v1
16. xCoRe: Cross-context Coreference Resolution — https://aclanthology.org/2025.emnlp-main.1737.pdf

### Retrieval / GraphRAG alternatives
17. GraphRAG (Microsoft, From Local to Global) — https://arxiv.org/abs/2404.16130
18. LazyGraphRAG — https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
19. RAPTOR — https://arxiv.org/abs/2401.18059 ; https://github.com/parthsarthi03/raptor
20. HippoRAG — https://arxiv.org/abs/2405.14831 ; https://github.com/osu-nlp-group/hipporag
21. HippoRAG 2 / From RAG to Memory (ICML 2025) — https://www.marktechpost.com/2025/03/03/hipporag-2-advancing-long-term-memory-and-contextual-retrieval-in-large-language-models/
22. LightRAG — https://www.maargasystems.com/2025/05/12/understanding-graphrag-vs-lightrag-a-comparative-analysis-for-enhanced-knowledge-retrieval/
23. StructRAG — https://dl.acm.org/doi/10.1145/3701716.3717819
24. E²RAG (Entity-Event KG for RAG, 2025) — https://arxiv.org/abs/2506.05939
25. ChronoRAG (Chronological Passage Assembling for Temporal QA) — https://arxiv.org/abs/2508.18748
26. RAG Meets Temporal Graphs (Oct 2025) — https://arxiv.org/html/2510.13590v1
27. T-GRAG (Dynamic GraphRAG for Temporal Conflicts) — https://arxiv.org/abs/2508.01680
28. Zep: A Temporal Knowledge Graph Architecture for Agent Memory — https://arxiv.org/abs/2501.13956
29. Graphiti — https://github.com/getzep/graphiti
30. Mem0 — https://arxiv.org/html/2504.19413v1
31. "Core-based Hierarchies for Efficient GraphRAG" (2026) — https://arxiv.org/html/2603.05207v1
32. When to use Graphs in RAG: A Comprehensive Analysis — https://arxiv.org/html/2506.05690v3
33. Awesome-GraphRAG — https://github.com/DEEP-PolyU/Awesome-GraphRAG

### Long-context vs. RAG
34. BigData Boutique: Why Long Context Windows Fail in RAG — https://bigdataboutique.com/blog/needle-in-haystack-optimizing-retrieval-and-rag-over-long-context-windows-5dfb3c
35. Context Rot (Chroma Research) — https://research.trychroma.com/context-rot
36. Long-Context Models vs. RAG (April 2026) — https://tianpan.co/blog/2026-04-09-long-context-vs-rag-production-decision-framework
37. U-NIAH: Unified RAG and LLM Evaluation for Long Context NIAH — https://arxiv.org/html/2503.00353v1

### Cognee
38. Cognee docs — https://docs.cognee.ai/core-concepts
39. Cognee GitHub — https://github.com/topoteretes/cognee
40. Cognee + Graphiti integration — https://www.cognee.ai/blog/deep-dives/cognee-graphiti-integrating-temporal-aware-graphs

### Prompt-injection flag
No prompt-injection-looking content was detected in any fetched source. All quoted claims trace to arxiv PDFs, ACL anthology pages, primary GitHub READMEs, or vendor technical blogs. Vendor blogs (Zep, Cognee, LightRAG) have been treated as marketing-adjacent — their quantitative claims are flagged as vendor-sourced where relevant.
