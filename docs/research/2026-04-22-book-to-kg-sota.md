# State of the Art: Book → Knowledge Graph Pipelines

> **Overnight research log.** Started 2026-04-22 (late night). Each section is the output of one focused research iteration dispatched by the /loop skill. Findings include citations to primary sources (papers, repos, docs). Framed against BookRAG's current design (Approach C hybrid pipeline: BookNLP for coref, custom LLM extraction into Cognee DataPoints, Kuzu + LanceDB, chapter-batched with chunk-ordinal spoiler filtering).

## Table of facets (research plan)

Checked facets are complete. Each iteration removes the check-less facet with the highest perceived value or dependency on a completed one.

- [x] 1. Microsoft GraphRAG — architecture, community summaries, extraction pipeline
- [x] 2. LightRAG — dual-level retrieval, hybrid graph+vector
- [x] 3. LlamaIndex KnowledgeGraphIndex + PropertyGraphIndex
- [x] 4. LangChain LLMGraphTransformer + GraphDocument flow
- [x] 5. Neo4j GraphRAG Python library + neo4j-labs work
- [x] 6. Cognee 0.5 internals — `cognify`, `add`, DataPoints, LLMGateway
- [x] 7. BookNLP + literary NLP (entities, coref, quote attribution, speaker ID)
- [x] 8. Academic: narrative KG extraction from novels (LitBank, NovelQA, FABLES, LaMP)
- [x] 9. Ontology learning from narrative text (BERTopic → OWL; open-IE + induction)
- [x] 10. Temporal / progressive KGs and spoiler-aware retrieval
- [x] 11. Entity resolution & coreference at book scale (cross-document, long-doc)
- [x] 12. Plot event extraction / narrative schema induction
- [x] 13. Character relationship networks (graph methods applied to novels)
- [x] 14. Long-document chunking strategies (chapter/semantic/hierarchical)
- [x] 15. Evaluation benchmarks for narrative KG & QA
- [x] 16. Open-source tools: BookWorld, StoryGraph, book-focused projects
- [x] 17. Multi-hop QA over narrative graphs
- [x] 18. Fine-tuned extraction models for literature (distilled from GPT/Claude)
- [x] 19. Character persona modeling from novels (LLM-as-character, dialogue agents)
- [x] 20. Commercial graph-RAG platforms (Stardog, Neo4j Bloom, WhyHow, Vectara)
- [x] 21. Streaming / incremental KG updates for serialized content
- [x] 22. HippoRAG and biologically-inspired memory systems
- [x] 23. GraphReader / agent-based graph traversal for QA
- [x] 24. Cost & latency engineering for book-scale extraction
- [x] 25. Prompt engineering patterns for structured entity/relation extraction
- [x] 26. Embeddings for narrative content (characters, scenes, plot)
- [x] 27. Hallucination and faithfulness in narrative KG construction
- [x] 28. BookRAG gap analysis — how our design compares across facets

### Bonus facets (post-synthesis; continue until morning)

- [x] 29. Zep/Graphiti deep-dive — bi-temporal agent memory as direct prior art
- [x] 30. BookCoref 2025 + BOOKCOREF benchmark — book-scale coref state of play
- [x] 31. Novel2Graph + Renard — architectural templates from OSS book tools
- [x] 32. ColBERT / late-interaction retrieval specifically for narrative
- [x] 33. Web-serial fiction (Royal Road / AO3 / Substack) as serialized-KG market
- [x] 34. FANToM + theory-of-mind benchmarks — per-character knowledge modeling
- [x] 35. LiteraryQA cleaned-NarrativeQA + LiSCU — usable training/eval corpora
- [x] 36. iText2KG + DIAL-KG — LLM-adjudicated incremental merge

### Bonus facets, round 2 (post-midnight expansion)

- [x] 37. Interactive fiction / CYOA / TTRPG campaign tracking — branching narrative KGs
- [x] 38. Comics / manga / webtoon — serialized visual narrative parallels
- [x] 39. Multilingual fiction (Chinese web novels, fanfic translations)
- [x] 40. Unreliable narrators & author-intent extraction
- [x] 41. Reader UX patterns for long-form & chatbot reading companions
- [x] 42. Game narrative KG — dialog trees, branching, NPC knowledge state
- [x] 43. Audio / podcast narrative extraction
- [x] 44. Final consolidated executive summary (end-of-research wrap)

### Bonus facets, round 3 (post-summary — dawn window)

- [x] 45. Cross-book / series-level KG linking (recurring characters, worldbuilding consistency)
- [x] 46. Named entity linking to Wikidata / DBpedia for fictional entities
- [ ] 47. Narrator style fingerprinting & author embeddings

---

## Executive summary — read this first

> **What this document is.** 43 focused research deep-dives conducted overnight 2026-04-22 on book-to-knowledge-graph pipelines, framing each facet against BookRAG's current design and identifying stealable ideas, novel-research territory, and concrete upgrades. Every section has a TL;DR, a "concrete ideas worth stealing" block, and primary-source citations. Iteration 28 is an internal synthesis of iterations 1-27; this summary is tighter and integrates the bonus rounds (29-43).

### The three most important findings, ranked

1. **Spoiler-gated retrieval is genuinely unclaimed territory.** No published academic or commercial system partitions a KG by a consumer-progress cursor. The closest neighbours — Graphiti/Zep's bi-temporal agent memory [iter 29], McAuley's review-spoiler classification [iter 10], NarraBench's "revelation" facet [iter 8], Fable's chapter rooms [iter 41] — each touch one face of the problem. None unify them. BookRAG is already the reference implementation of a task that does not yet have a name in the literature [iter 8, 10, 15, 16, 20, 36].

2. **The single largest extraction-quality win is a three-part Phase-2 refactor, not a new model.** Gleaning loop + quote-provenance + chunk-size shrink (1500→750), combined, attack BookRAG's three biggest extraction weaknesses multiplicatively: under-extraction of minor entities [iter 1, 25], silent hallucination [iter 25, 27], and low-recall chunking [iter 14]. GraphRAG's own ablation shows ~2× entity references at 600 vs 2400 tokens [iter 1]; gleaning adds 30-50% on top [iter 1]. All three are S-effort, compose on the same prompt, and every downstream improvement (reranker, PPR, persona) compounds on the higher-recall base graph [iter 28].

3. **Bi-temporal stamps are a cheap upgrade that unifies five roadmap items.** Borrowing Graphiti's four-timestamp edge model [iter 29] — `t_valid`, `t_invalid`, `t_created`, `t_invalidated` — rewrites `load_allowed_nodes` as a canonical bi-temporal SELECT and simultaneously solves: per-identity snapshot merge (iter 29), incremental re-ingest with prompt-version invalidation [iter 21, 28], DIAL-KG-style LLM-adjudicated edge supersession [iter 36], episode provenance for quote citation [iter 29], and lays the substrate for future cross-book series linking [iter 21]. Do NOT migrate to Graphiti; steal the primitive [iter 29].

### BookRAG's defensible moat

BookRAG sits at the intersection of three capabilities no other system combines. **First**, automated KG extraction from narrative prose via parenthetical-coref insertion + typed Pydantic DataPoints is strictly stronger than GraphRAG/LightRAG's free-text `type` field [iter 1, 2] and matches only neo4j-graphrag's `LLMEntityRelationExtractor` and LlamaIndex's `SchemaLLMPathExtractor` on rigor [iter 3, 5, 28]. **Second**, the per-identity snapshot selection is lightweight event sourcing that Graphiti/Zep sell as their core IP minus the bi-temporal machinery BookRAG doesn't need (source text is immutable) [iter 29]. **Third**, spoiler-gated retrieval is a genuinely new task framing that extends naturally to every serialized-narrative medium researched: web serials [iter 33], interactive fiction [iter 37], comics/webtoons [iter 38], games [iter 42], audiobooks/podcasts [iter 43].

The inversion of the games industry is the sharpest wedge. Ink/Yarn/Cyberpunk quest-facts/BG3 approval/Valve dynamic-dialog all hand-author the flag graph that BookRAG ingests from prose [iter 42]. BookRAG automates what AAA studios do with writers' rooms and QA teams — which is a defensible product wedge (game-writer QA companion) that nobody else is architecturally positioned to serve [iter 42]. Iterations 20 and 33 confirm no commercial graph-RAG platform (Stardog, WhyHow, Vectara, Neo4j Bloom) ships spoiler-gating, and the serialized-fiction market (Royal Road, AO3, Substack) is hungry for it but currently served by zero products [iter 20, 33].

### The single highest-ROI next move

**Ship Phase A's gleaning + quote-provenance + chunk-size combined refactor as one focused 2-week sprint.** This is the unanimous answer from iterations 1, 14, 25, 27, and 28's synthesis. All three items are S-effort, touch the same prompt, and together move BookRAG's Phase-2 extraction from "good enough for A Christmas Carol" to a defensible base that everything else compounds on. Ablate on Christmas Carol + Red Rising chapters 1-10, publish the numbers. Without quote-provenance as the faithfulness gate, aggressive gleaning risks inflating the graph with fabricated edges — the three must ship together, not separately [iter 28]. Defer the reranker, PPR, and persona mode until after the ablation lands; they all benefit from the higher-recall base graph.

### Publishable research contributions

- **Consumer-progress-gated RAG as a formal task** — position paper unifying wall-clock valid-time (TKG literature) and reader-progress valid-time under one umbrella, with BookRAG as reference implementation [iter 8, 10, 28].
- **spoiler-leak-bench** — cursor-partitioned gold over Christmas Carol + Red Rising + 3 public-domain novels, with leak-rate-at-cursor as headline metric. LLM-judge calibrated against human annotators (FABLES methodology) [iter 8, 15, 28].
- **Cursor-conditioned persona / fog-of-war persona mode** — plug `load_allowed_nodes` bound into CharacterEval/CharacterBench/PingPong. First-of-kind result; no existing persona benchmark conditions on reader progress [iter 19, 34].
- **Typed narrative relationship dataset** — multi-book typed-relation gold set from BookRAG's Phase-2 extractions over public-domain novels. Addresses the Labatut & Bost / WNU 2025 field-wide gap [iter 13].
- **Renard-compatible spoiler-layer plugin** — standalone `PipelineStep` so Renard users can drop in cursor filtering. Low effort, high citability, cleanly positions BookRAG as "the spoiler layer for existing book-NLP pipelines" [iter 16, 31].
- **Forecaster-based spoiler-leakage test** — RE-NET/CyGNet over `(s, p, o, chapter)` quadruples; if chapter-N+1 facts are predictable from the ≤N slice, the KG leaks future structure. Novel automated metric [iter 10, 15].

### Biggest risks

- **Cognee 1.0 migration drift.** Dev branch at 1.0.1.dev4 as of 2026-04-21; if 1.0 consolidates around `cognify()` and drops `run_pipeline([Task(add_data_points)])`, BookRAG's moat-bearing custom extraction path needs a rebuild against a moving API. Mitigation: pin 0.5.6, version-adapter shim, 2-week evaluation spike before upgrading [iter 6, 28].
- **maverick-coref's CC-BY-NC-SA 4.0 license** permanently blocks the best-in-class LitBank coref from commercial deployment. Research branch only [iter 7, 28].
- **Hyperscaler GraphRAG commoditization** — AWS Bedrock KB, Azure GraphRAG could ship generic graph-RAG before BookRAG publishes spoiler-safety framing. Mitigation: nobody ships narrative schemas or consumer pricing; move on novelty while window is open [iter 20, 28].
- **Copyright limits public eval** — spoiler-leak-bench on Red Rising cannot be redistributed. Phase C evaluations must be Gutenberg-only for external release [iter 8, 28].
- **BookNLP coref degrades on full-length novels** — BOOKCOREF shows ~20 CoNLL-F1 drop from medium to full-book eval; Red Rising will be materially worse than Christmas Carol on coref alone [iter 30].
- **Whisper v3 hallucinates on noisy audio** (4× v2's rate on phone/video) — audiobook extension must stay scoped to studio-clean narration [iter 43].

### Reading order for the rest of the document

- **Must-read if you only have 30 minutes:** iteration 28 (full synthesis + roadmap), iteration 29 (Graphiti bi-temporal), iteration 41 (reader UX), iteration 42 (games — the product-wedge insight).
- **Must-read for Phase A implementation:** iterations 1 (gleaning), 14 (chunking), 25 (prompt patterns), 27 (faithfulness).
- **Must-read for research positioning:** iterations 8 (narrative KG academia), 10 (temporal KG / spoiler-aware), 15 (eval benchmarks), 36 (iText2KG adjudication).
- **Skim:** iterations 3-5 (framework competitors — verdict is "stay on Cognee"), 20 (commercial platforms — verdict is "nobody competes on spoiler-safety"), 33 (web-serial market sizing).
- **Optional, strong for strategy:** iterations 37-43 (cross-medium analogues; sharpen the novelty argument and surface adjacent markets).

### Iteration map

- **Framework competitors (1-5):** GraphRAG, LightRAG, LlamaIndex, LangChain, Neo4j GraphRAG
- **Infrastructure (6, 14, 24, 26):** Cognee internals, chunking, cost/latency, embeddings
- **Literary NLP (7, 11, 12, 13, 30):** BookNLP, coref at book scale, plot events, character networks, BOOKCOREF
- **Academic landscape (8, 9, 15, 17):** narrative KG work, ontology learning, eval benchmarks, multi-hop QA
- **Temporal / spoiler-aware (10, 21, 29, 36, 40):** progressive KGs, streaming updates, Zep/Graphiti, iText2KG/DIAL-KG, unreliable narrators
- **Retrieval (17, 22, 23, 32):** multi-hop, HippoRAG, GraphReader, ColBERT
- **Persona / ToM (19, 34):** character-persona modeling, FANToM
- **Ecosystem (16, 18, 20, 33, 37, 38, 39, 42, 43):** OSS tools, fine-tuned extractors, commercial platforms, web serials, IF/TTRPG, comics, multilingual, games, audio
- **Corpora (35):** LiteraryQA + LiSCU
- **Synthesis (25, 27, 28, 41, 44):** prompt patterns, faithfulness, gap analysis, reader UX, this summary

### Where we landed on the 28-facet plan vs 16 bonus facets

The original 28 facets all mapped to concrete takeaways captured in iteration 28's Phase A/B/C roadmap. The 16 bonus facets (29-44) extended the research into cross-medium analogues (games, comics, webtoons, audio, multilingual, IF/TTRPG) and deeper dives on named prior art (Graphiti, BOOKCOREF, iText2KG, FANToM). They strengthened the novelty argument and surfaced adjacent markets (game-writer QA, audiobook companion, web-serial readers) without changing the Phase A priority list — every bonus iteration's "ideas worth stealing" block either reinforced a Phase A item or queued a Phase C research track.

---

## Findings

_(Each iteration appends a dated section below.)_

### 1. Microsoft GraphRAG

**Researched:** 2026-04-22 (iteration 1)

**TL;DR:** GraphRAG is Microsoft Research's two-stage indexing + query system that builds a typed entity-relation graph from unstructured text, runs hierarchical Leiden community detection over it, pre-computes LLM summaries for every community at every hierarchy level, and answers "global sensemaking" questions via map-reduce over those summaries. Its distinguishing idea is the **community-summary corpus as a first-class retrieval surface** — not individual chunks or entities, but LLM-authored digests of graph subcommunities at varying zoom levels. [1]

**Architecture (indexing pipeline):**
- Slice corpus into `TextUnit` chunks (default 1200 tokens in the current OSS pipeline; the paper used **600 tokens with 100-token overlap** and showed GPT-4 extracts ~2x more entity references at 600 vs 2400 tokens). [1][2][5]
- LLM extraction pass per chunk → `(entity: title, type, description)` and `(relationship: source, target, description)` tuples, plus optional `covariates` (claims with time bounds). [2]
- Gleaning self-refinement: after the first extraction, a yes/no prompt with **logit_bias=100** forces a binary judgment on whether entities were missed; if yes, a continuation prompt with "MANY entities were missed in the last extraction" re-extracts. Configurable max rounds. [1][5]
- Deduplicate entities sharing `(title, type)` and relationships sharing `(source, target)` by concatenating descriptions, then LLM-summarize each merged bundle into a single canonical description. [2]
- Hierarchical **Leiden** clustering (via `graspologic`), recursive until community-size thresholds, producing multi-level community hierarchy. [1][2]
- Per-community LLM-generated "community report" = executive summary + referenced entities/relationships/claims, then secondarily summarized for shorter-context reuse. Summaries are generated bottom-up with an 8k-token context window in the paper. [1][2]
- Embed entity descriptions, text units, and community reports into a vector store. [2]

**Extraction approach:** Single multi-task prompt that asks the LLM to output entities and relationships in one pass, few-shot prompted with domain examples. The default type vocabulary in the paper is open-domain ("people, places, organizations") but is designed to be adapted via few-shot examples per domain. [1] Modern OSS releases include an **auto-tuning** workflow that samples the corpus and generates domain-specific prompt templates automatically. [4]

**Graph construction:** Nodes are typed entities; edges are free-text-described relationships (no fixed schema). Duplicate merge is by exact `(title, type)` match — semantic entity resolution is weak, and the paper flags this as a limitation. Communities are detected, not predefined, and the hierarchy is stored as `community_level` metadata on each cluster. [1][2]

**Retrieval modes:**
- **Global search** — map-reduce over community summaries at a chosen hierarchy level. Map phase: shuffle summaries into context-window-sized batches, prompt LLM for an intermediate answer plus a **helpfulness score 0-100**. Reduce phase: sort by score descending, pack top answers into the final context until token limit, generate final answer. Best for thematic/"what are the main topics" questions. [1]
- **Local search** — seed on entities semantically matching the query, fan out to neighbors, pull associated text units, relationships, and covariates into a single context window. Best for "what does X do" entity-centric questions. [2]
- **DRIFT search** — three phases: (A) **Primer** compares query against top community reports, generates broad answer + follow-up questions; (B) **Follow-up** runs local searches for each follow-up, generating intermediate answers and more questions; (C) returns a hierarchical Q/A tree. Trades cost for coverage; designed to fix local search's narrowness. [3]
- **Basic search** — plain vector similarity fallback. [2]

**Strengths relative to book-RAG use cases:**
- Community summaries are a natural fit for thematic/book-level questions ("what are the major themes", "what factions exist") — BookRAG's Theme DataPoints are a coarser hand-rolled analog.
- Gleaning loop directly addresses the precision/recall tradeoff BookRAG faces in Phase-2 extraction.
- Hierarchical community levels give a built-in zoom control — could map to chapter → act → book summaries.
- Open-domain relationship text tolerates the messy, affect-laden relations in fiction better than a rigid ontology.

**Weaknesses / gaps for BookRAG's use case:**
- **No temporal or progression awareness.** Community detection and summaries are computed over the full corpus. A reader at chapter 5 of Red Rising cannot safely consume a community summary that was synthesized from all 45 chapters — it will spoil. Retrofitting spoiler-filtering would require either per-progress-bound re-summarization or a significant rewrite of the map step.
- Assumes **static corpus**; incremental re-indexing exists in recent OSS versions but community summaries are expensive to recompute.
- Entity resolution by `(title, type)` string match misses coref-heavy narrative text — BookNLP's coref already puts BookRAG ahead here.
- No typed node schema (Character vs Faction vs Location). Cognee's DataPoints give richer downstream typing than GraphRAG's free-text node `type` field.
- Indexing is expensive: **281 minutes** for a ~1M-token Podcast dataset on a 16GB VM against GPT-4-turbo. [1] A novel-scale corpus (~100k tokens) is tractable but a library of 100 novels is not on a single machine.
- Global-search map-reduce burns a lot of tokens per query — not ideal for a chatbot latency budget.

**Key citations:**
1. [Edge et al., "From Local to Global: A GraphRAG Approach to Query-Focused Summarization", arXiv:2404.16130v2 (2024)](https://arxiv.org/html/2404.16130v2)
2. [GraphRAG docs — default indexing dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/)
3. [GraphRAG docs — DRIFT search](https://microsoft.github.io/graphrag/query/drift_search/)
4. [microsoft/graphrag GitHub repo](https://github.com/microsoft/graphrag)
5. [Neo4j — Integrating Microsoft GraphRAG Into Neo4j](https://neo4j.com/blog/developer/microsoft-graphrag-neo4j/)

**Concrete ideas worth stealing for BookRAG:**
- **Gleaning loop** on Phase-2 extraction: after DataPoint extraction, ask the LLM "did you miss any characters/locations/events?" with logit_bias-forced yes/no, then re-extract if yes. Cheap, directly improves recall on minor entities.
- **Hierarchical community summaries gated by reader progress**: run Leiden on the spoiler-filtered subgraph at query time (not index time), then summarize the 1–2 communities nearest the query — gives thematic answers without pre-baking spoilers.
- **Helpfulness-score map-reduce** for queries that span many chapters — rank chapter-local answers by a 0-100 LLM score and fold only the top ones.
- **DRIFT-style primer → follow-up** fits spoiler-gated chat naturally: primer over chapter-level summaries up to cursor, follow-up on specific entities in the allowed-node set.
- **Auto-tuning prompt template** from sampled corpus: could replace BookRAG's hand-written extraction prompts with per-book-tuned ones generated after ontology discovery.

### 2. LightRAG

**Researched:** 2026-04-22 (iteration 2)

**TL;DR:** LightRAG (Guo et al., HKUDS, Oct 2024) is a graph-enhanced RAG framework whose distinguishing bet — vs GraphRAG — is that you do not need Leiden communities or pre-baked multi-level summaries to get good graph-assisted retrieval. Instead it pairs a flat entity/relation graph with a *dual-level keyword* query path (specific vs thematic) and a set-union incremental update, claiming comparable or better win-rates than GraphRAG on UltraDomain at a fraction of the token cost.

**Architecture:**
- Chunk documents → LLM entity+relation extraction → upsert into a graph store (Neo4j/Kuzu/Postgres AGE/NetworkX all supported) + a KV chunk store + two vector indexes (one over entities, one over relations).
- No community detection, no community-summary LLM pass, no hierarchical reports. The graph is "flat" apart from the degree signal.
- Retrieval: LLM extracts dual-level keywords from the query → parallel vector lookups into the entity and relation indexes → one-hop graph expansion → pull source chunks via `chunk_id` back-pointers → CSV-serialize and token-truncate → answer LLM.

**Extraction approach:**
- Single extraction prompt emits a stream of delimited tuples: `entity{D}name{D}type{D}description` and `relation{D}source{D}target{D}keywords{D}description` (plus a relation *weight*, which the paper describes and which Neo4j's analysis calls "an educated guess based on context" rather than a learned score) [4].
- Default entity types: Person, Creature, Organization, Location, Event, Concept, Method, Content, Data, Artifact, NaturalObject [3]. Names are normalized to title case to help dedup.
- Gleaning: same "did you miss anything?" continuation loop that GraphRAG uses, configurable via `entity_extract_max_gleaning`.
- Entity/relation *summarization* prompt merges multiple descriptions for the same identity in third person, reconciling conflicts under a token cap [3].

**Graph construction:**
- Nodes = entities (name + type + merged description); edges = relations (source, target, keywords, description, weight). Edges are treated as undirected.
- Dedup by exact title-cased name: when the same entity reappears in a new chunk, the new description is appended to a list and the summarization prompt collapses them into one node [3][5]. Same rule for (source,target) edge pairs.
- Two vector collections are maintained alongside the graph:
  - *entities_vdb*: embedding of `name + " " + description`
  - *relations_vdb*: embedding of `keywords + " " + description` (plus src/tgt ids)
- Each node/edge carries a `source_chunk_ids` list — this is the bridge from graph hits back to raw text.

**Dual-level retrieval:**
- One LLM call extracts `{high_level_keywords: [...], low_level_keywords: [...]}` as strict JSON [2][3]. Low-level = proper nouns / specific items; high-level = themes / intents.
- *Local path (low-level → entities):* ANN search in `entities_vdb`, then rank retrieved nodes by node degree; pull their one-hop edges ranked by combined endpoint degree; pull source chunks referenced by those nodes [4].
- *Global path (high-level → relations):* ANN search in `relations_vdb`, rank edges by `node_degree(src)+node_degree(tgt)` then by weight; pull endpoint node properties; pull source chunks referenced by those edges [4].
- Fusion: results from both paths are deduped and CSV-serialized into three blocks (Entities / Relationships / Chunks), each independently truncated to a `max_token_size`, then concatenated into the generation prompt. In `hybrid` mode a naive chunk-vector search runs in parallel and is merged in [4].
- This is the origin of the headline "<100 tokens retrieval vs 610k for GraphRAG" claim — LightRAG does not ship community summaries into context; it ships a few dozen CSV rows [1][5].

**Incremental update:**
- New docs are chunked and extracted the same way, producing (V', E'). Merge is literally `V ← V ∪ V'` and `E ← E ∪ E'`, with the dedup+summarization step handling collisions [1][5].
- No community rebuild, no re-embedding of untouched nodes. Contrast with GraphRAG, where adding docs invalidates community membership and therefore requires regenerating community reports (~1,399 × 2 × 5,000 tokens on the paper's legal dataset) [5].
- Deletion is supported via "automatic KG regeneration" scoped to the affected documents.

**Strengths relative to book-RAG use cases:**
- Per-chunk append model maps cleanly onto BookRAG's per-batch extraction — a new batch is just another `ainsert`.
- Entity dedup is based on name equality plus LLM merge of descriptions, which naturally produces *per-identity snapshots* of the kind BookRAG's Phase 2 already tracks.
- Relation `keywords` field is a useful latent theme index — close cousin of BookRAG's Theme DataPoint.
- Chunk back-pointers make it trivial to enforce spoiler gates: filter chunks by chapter/paragraph before the answer LLM sees them, even without touching the graph.

**Weaknesses / gaps for BookRAG's use case:**
- No community summaries means no native answer to "what is this book *about*?" style questions — exactly the sensemaking niche GraphRAG's Global Search owns.
- Dedup-by-name is brittle for fiction: Scrooge/Ebenezer/"the old miser" all collapse only if the extractor picks the same surface form. BookRAG already has a better answer here via BookNLP coref + parenthetical resolution.
- Relation weight is not load-bearing (it's an LLM guess), so ranking by it adds noise. BookRAG's PlotEvent `first_chapter` signal is stronger for spoiler-aware ranking.
- The summarization-merge prompt has no chapter-awareness — re-running it after chapter 40 will overwrite the chapter-4 description of a character. BookRAG's per-identity snapshot indexing (Phase 2) explicitly avoids this; LightRAG as-shipped would need to be modified to key node versions by (name, batch_id).
- Neo4j's own review flags that there are "no production-level statistics" showing LightRAG's retrieval gains transfer to real enterprise corpora [4].
- Single `description` field per node means less typed structure than BookRAG's Character/Location/Faction/PlotEvent DataPoints — you lose schema.

**Key citations:**
1. [Guo et al., "LightRAG: Simple and Fast Retrieval-Augmented Generation," arXiv:2410.05779](https://arxiv.org/abs/2410.05779)
2. [arXiv HTML rendering of the paper](https://arxiv.org/html/2410.05779v1)
3. [HKUDS/LightRAG — `lightrag/prompt.py` (extraction, keyword, summarization prompts)](https://github.com/HKUDS/LightRAG/blob/main/lightrag/prompt.py)
4. [Neo4j — "Under the Covers With LightRAG: Retrieval"](https://neo4j.com/blog/developer/under-the-covers-with-lightrag-retrieval/)
5. [LearnOpenCV — "LightRAG: Simple and Fast Alternative to GraphRAG"](https://learnopencv.com/lightrag/)
6. [HKUDS/LightRAG GitHub repo](https://github.com/HKUDS/LightRAG)

**Concrete ideas worth stealing for BookRAG:**
- **Dual-level keyword extraction at query time.** Cheap LLM call ( strict-JSON `{high_level, low_level}`) is a better query router than BookRAG's current single-embedding lookup. Low-level keywords → match against Character/Location name vectors; high-level → match against Theme/Relationship vectors. Fits spoiler gating because both lookups can be intersected with the allowlist before ranking.
- **Relation-level vector index.** BookRAG currently vectorizes nodes; also vectorizing `Relationship` DataPoints (`subject + predicate + object + description`) gives a "global" retrieval path that finds thematic answers without Leiden.
- **Degree-ranked one-hop expansion.** After the allowed-node filter, rank candidates by degree within the allowed subgraph — promotes central characters over spear-carriers for ambiguous queries, at zero LLM cost.
- **CSV-block context format with per-block token caps.** Three capped blocks (Entities / Relationships / Chunks) is more predictable than concatenating arbitrary node JSON; also forces the generator to ground in named evidence.
- **Chunk back-pointer pattern as the spoiler boundary.** Each node/edge carries `source_chunk_ids`. Make BookRAG's spoiler filter operate *on chunk_ids first* rather than on node timestamps — simpler invariant, matches LightRAG's storage model, and lets the cursor-paragraph path share one code path with the chapter-bound path.
- **Explicit "union + LLM-summary-merge" for re-ingestion.** When a book is re-processed with a finer `batch_size`, don't rebuild — union the new extractions into the existing graph and let the summarizer reconcile. This is the upgrade path BookRAG currently lacks.

**GraphRAG vs LightRAG at a glance (for book-RAG):**

| Dimension | GraphRAG | LightRAG |
|---|---|---|
| Index-time LLM cost | High (entities + relations + claims + community summaries at each level) | Medium (entities + relations + per-node merge summary only) |
| Update cost for a new chapter | Re-detect communities, re-summarize affected levels | `V ∪ V'`, `E ∪ E'`, re-run merge summary on touched nodes |
| Retrieval latency | Local = KG+vectors; Global = map-reduce over community reports (many LLM calls) | One keyword-extraction call + two ANN lookups + one generation call |
| Sensemaking ("what's the book about up to ch. N?") | Strong — community reports are purpose-built for this | Weak — no community layer; you'd fake it via high-level keyword + relation index |
| Specific lookups ("where did X meet Y?") | Good via Local Search | Good via low-level keyword path |
| Spoiler-gate compatibility | Medium — community reports can leak late-book framing into early-chapter answers unless regenerated per cursor | High — filtering by `source_chunk_ids` before ranking is natural; but per-identity snapshots still need a BookRAG-style patch on top |

### 3. LlamaIndex — KnowledgeGraphIndex & PropertyGraphIndex

**Researched:** 2026-04-22 (iteration 3)

**TL;DR:** LlamaIndex ships two graph indices. The older `KnowledgeGraphIndex` stores naive (subject, predicate, object) triples with no node labels or properties and is effectively superseded [1][2]. `PropertyGraphIndex` (PGI), introduced 2024-05-29, is a full labeled-property-graph abstraction with pluggable extractors, retrievers, and graph stores, and is the current recommendation for any new build [1][5]. PGI is the closest off-the-shelf analogue to BookRAG's Phase-2 pipeline — typed nodes, typed edges, schema validation, and retrieval that can mix vector + symbolic paths.

**PropertyGraphIndex architecture:** PGI decomposes KG construction into four swappable layers wired together by `PropertyGraphIndex.from_documents(...)`: (1) a list of `kg_extractors` that each receive chunked `TextNode`s and append `EntityNode` / `ChunkNode` / `Relation` objects; (2) a `PropertyGraphStore` that persists the graph and (when supported) vectors; (3) an optional `vector_store` for embedding text chunks separately; (4) a list of `sub_retrievers` composed inside a top-level retriever that unions their results [2][5]. Extractors and retrievers are themselves `TransformComponent`s, so they participate in LlamaIndex's `IngestionPipeline` and can run concurrently with `num_workers` [2].

**Extractors available:**
- **`SimpleLLMPathExtractor`** (default). Prompts the LLM to emit free-form `(head, relation, tail)` triples from each chunk. Customizable via `extract_prompt`, `parse_fn`, and `max_paths_per_chunk`. Closest equivalent to the old KGIndex behavior and to BookRAG's naive fallback [2].
- **`ImplicitPathExtractor`** (default, no LLM). Walks the existing `node.relationships` attribute on LlamaIndex `TextNode`s (PREVIOUS / NEXT / SOURCE) and materializes them as edges. Cheap structural layer; BookRAG's chapter-adjacency edges would slot here [2].
- **`SchemaLLMPathExtractor`**. Enforces a Pydantic-typed schema: `possible_entities: Literal[...]`, `possible_relations: Literal[...]`, and a `kg_validation_schema` mapping entity types to allowed relation types (e.g. `{"PERSON": ["WORKS_AT", "CEO", "BOARD_MEMBER"], ...}`) [2][3]. Under the hood it asks the LLM to return a Pydantic object whose fields are constrained `Literal` unions; `strict=True` drops any triplet violating the entity→relation map, `strict=False` keeps them with warnings [2]. Subclasses can override `kg_schema_cls` for bespoke validators.
- **`DynamicLLMPathExtractor`**. Hybrid: you optionally pass `allowed_entity_types` / `allowed_relation_types` as soft hints. The LLM can extend the ontology with new types when the seed list is insufficient, unlike Schema which rejects out-of-schema triples [2]. Good fit for book ingestion where the full character cast is unknown at start.

Prompt shape for Simple is a short instruction plus "Produce up to {max_paths_per_chunk} knowledge triples in the form (subject, predicate, object)." Schema's prompt is a Pydantic structured-output call — the LLM never sees free-form instructions, it fills a typed form [2].

**Retrievers available:** Retrievers are composed by passing a `sub_retrievers=[...]` list to `index.as_retriever(...)`; results are unioned [2].
- **`LLMSynonymRetriever`** (default). Generates `max_keywords` synonyms of the query (split on `^`), matches them against node names/labels, then expands `path_depth` hops [2].
- **`VectorContextRetriever`** (default when the store supports vectors, else external). Embeds the query, fetches `similarity_top_k` nearest nodes, then expands `path_depth` hops of connected edges [2].
- **`TextToCypherRetriever`**. LLM generates a Cypher query from the live graph schema; executed against Neo4j / Memgraph / FalkorDB. `SimplePropertyGraphStore` does *not* support this — Cypher requires a real graph server [2].
- **`CypherTemplateRetriever`**. Safer variant: developer writes a parameterized Cypher template, LLM fills a Pydantic params object. Deterministic shape, LLM only decides values [2].
- **`CustomPGRetriever`**. Subclass hook overriding `custom_retrieve(query_str)` returning strings / `TextNode`s / `NodeWithScore`s. The Neo4j tutorial composes NER → per-entity `VectorContextRetriever` fan-out inside this base class [3].

**Graph stores supported:** `SimplePropertyGraphStore` (in-memory + JSON on disk, no vector, no Cypher); `Neo4jPropertyGraphStore` (vectors + Cypher); `NebulaPropertyGraphStore` (Cypher-compatible, no native vectors); `TiDBPropertyGraphStore`, `FalkorDBPropertyGraphStore`, `MemgraphPropertyGraphStore`, `KuzuPropertyGraphStore` (embedded, same engine BookRAG uses via Cognee) [2][5]. Vectors can also be offloaded to any LlamaIndex `VectorStore` (Qdrant, LanceDB, etc.) if the graph store lacks them.

**Schema enforcement:** `SchemaLLMPathExtractor` builds a dynamic Pydantic model at init time whose `triplets` field is a list of `Triplet` objects with `head_type: Literal[...]`, `relation: Literal[...]`, `tail_type: Literal[...]`. The LLM is called via `llm.structured_predict(kg_schema_cls, prompt)`, so JSON-schema coercion prevents hallucinated type names from parsing at all [2]. Post-parse, a `_validate_triplet` step checks that `relation ∈ kg_validation_schema[head_type]`; strict mode drops violators. Mapping BookRAG's DataPoints is mechanical: `possible_entities = Literal["Character","Location","Faction","PlotEvent","Theme"]`, `possible_relations` = union of BookRAG's `RelationshipType` enum, `kg_validation_schema` encodes "PlotEvent may link to Character/Location/Faction, Theme only links to PlotEvent/Character," etc.

**Strengths relative to book-RAG use cases:**
- Typed extraction out-of-the-box via `SchemaLLMPathExtractor` — matches BookRAG's DataPoint ambition without bespoke Pydantic plumbing.
- Four-way retriever composition (keyword + vector + Cypher + custom) is strictly more expressive than Cognee's current `SEARCH_TYPE.GRAPH_COMPLETION` [6].
- Graph-store abstraction means you can start on `SimplePropertyGraphStore` and swap to Kuzu/Neo4j without touching extraction code [2][5].
- Kuzu backend already exists (`KuzuPropertyGraphStore`) — BookRAG could in principle move off Cognee while keeping the same embedded DB [2].
- Active, well-documented, idiomatic Python; first-class LlamaHub ecosystem.

**Weaknesses / gaps for BookRAG's use case:**
- **No progression / reading-cursor awareness.** PGI has no concept of chapter or chunk ordinals as retrieval constraints; you'd need a `CustomPGRetriever` that wraps each `sub_retriever` in a chunk-id allowlist filter. Same plumbing BookRAG already has — but you'd be rewriting it inside LlamaIndex's retriever contract.
- **No per-identity snapshotting.** If chapter 4 and chapter 40 both produce a `(Scrooge, IS_A, Character)` node with different descriptions, PGI stores only the last write; BookRAG's "latest snapshot per identity within cursor bound" logic has no native equivalent.
- **Chunking is paragraph-agnostic.** LlamaIndex `SentenceSplitter` / `TokenTextSplitter` don't preserve chapter boundaries. You'd replace the splitter with BookRAG's existing batcher to keep chunk metadata.
- **Framework lock-in.** Adopting PGI pulls in LlamaIndex's `Settings`, `ServiceContext`, and document/node models across the ingestion path.
- **SchemaLLMPathExtractor edge-direction is flat.** The `kg_validation_schema` constrains `(head_type → relation)` but does not constrain `tail_type`. Two-sided typing (e.g., `PlotEvent -[OCCURS_AT]-> Location` only) still needs post-validation.

**Comparison with Cognee (BookRAG's current stack):**

| Dimension | LlamaIndex PGI | Cognee 0.5.6 (BookRAG) |
|---|---|---|
| Schema | Pydantic `Literal` unions + entity→relation map, enforced in structured-output call [2] | Pydantic DataPoint subclasses, enforced by prompt + copy_model [6] |
| Extractors | 4 pluggable, stackable, parallelizable | One `extract_graph_from_data` pipeline task; hybrid custom pipeline required |
| Retrievers | 5 composable sub-retrievers unioned | `SEARCH_TYPE.GRAPH_COMPLETION` + vector search, less composable |
| Storage | Abstract `PropertyGraphStore`; 7+ backends | Kuzu + LanceDB + SQLite (fixed) |
| Vector integration | Graph-native or external, toggleable | LanceDB only |
| Update model | Re-ingest adds to existing store; no per-version snapshot | Same — no versioning |
| Progression filter | Must build via `CustomPGRetriever` | Already built (spoiler_filter.py) |
| Ecosystem | Large; LlamaHub readers, agents, workflows | Smaller; pre-1.0 API churn |

PGI wins on extractor/retriever modularity and schema enforcement rigor. Cognee wins on being a more opinionated end-to-end pipeline (ontology + cognify + memify) and on already being wired to Kuzu. For BookRAG specifically, the most interesting swap would be `SchemaLLMPathExtractor` as a drop-in replacement for the current Cognee extraction prompt — it would give you JSON-schema-level guarantees on DataPoint types that the current pipeline enforces only via prompt.

**Key citations:**
1. [Introducing the Property Graph Index — LlamaIndex blog (2024-05-29)](https://www.llamaindex.ai/blog/introducing-the-property-graph-index-a-powerful-new-way-to-build-knowledge-graphs-with-llms)
2. [Using a Property Graph Index — LlamaIndex OSS docs](https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/)
3. [Customizing Property Graph Index in LlamaIndex — Neo4j Developer Blog](https://neo4j.com/blog/developer/property-graph-index-llamaindex/)
4. [Property Graph Index basic example — LlamaIndex OSS docs](https://developers.llamaindex.ai/python/examples/property_graph/property_graph_basic/)
5. [LlamaIndex integration page — Neo4j Labs](https://neo4j.com/labs/genai-ecosystem/llamaindex/)
6. [SchemaLLMPathExtractor source — run-llama/llama_index (GitHub)](https://github.com/run-llama/llama_index/tree/main/llama-index-core/llama_index/core/indices/property_graph/transformations)
7. [Building Knowledge Graph Agents with LlamaIndex Workflows](https://www.llamaindex.ai/blog/building-knowledge-graph-agents-with-llamaindex-workflows)

**Concrete ideas worth stealing for BookRAG:**
- **Adopt `SchemaLLMPathExtractor`'s structured-output pattern directly.** Replace BookRAG's Cognee extraction prompt with `llm.structured_predict(BookRAGKGSchema, chunk_text)` where `BookRAGKGSchema` is a Pydantic model whose `triplets` field has `head_type: Literal["Character","Location","Faction","PlotEvent","Theme"]` and `relation: Literal[...]`. JSON-schema coercion is strictly stronger than prompt-level type requests and eliminates the class of bugs where the LLM returns "Char" instead of "Character."
- **`kg_validation_schema` as the DataPoint edge whitelist.** Formalize which DataPoint types can point to which — right now that's implicit in the prompt. A single `ALLOWED_EDGES: dict[str, list[str]]` constant makes it testable and keeps extraction honest.
- **Retriever composition via `sub_retrievers` list.** BookRAG's current "vector search then graph-complete" is one fixed path. Structuring retrieval as an ordered list of (synonym, vector, chunk-id-filtered, cypher-template) retrievers — all gated by the spoiler allowlist — makes it trivial to A/B which ones matter per query type.
- **`CypherTemplateRetriever` pattern for known question shapes.** For common spoiler-safe queries ("who has Scrooge met so far?"), a hand-written parameterized Cypher template against Kuzu is cheaper and more reliable than an LLM-generated query; LLM only fills the entity parameter.
- **`ImplicitPathExtractor` for chapter adjacency.** Materialize `PREVIOUS_CHUNK` / `NEXT_CHUNK` / `SAME_CHAPTER` as actual graph edges rather than carrying them as metadata. Makes BookRAG's graph walkable for cursor-anchored queries without extra filtering logic.
- **`KuzuPropertyGraphStore` as a fallback if Cognee churn bites.** LlamaIndex's Kuzu backend reads the same on-disk format Cognee uses. If the Cognee 0.5.x API becomes untenable, BookRAG can point LlamaIndex at the existing `.kuzu` directory and keep the graph — no re-ingestion.
- **`DynamicLLMPathExtractor` for ontology discovery.** BookRAG currently runs a separate BERTopic ontology discovery stage. DynamicLLMPathExtractor with seed types from Phase-1 would collapse ontology-discovery and extraction into one LLM pass, with the seeds acting as soft priors rather than hard constraints.

### 4. LangChain — LLMGraphTransformer & GraphDocument

**Researched:** 2026-04-22 (iteration 4)

**TL;DR:** `LLMGraphTransformer` (in `langchain_experimental.graph_transformers.llm`) is a single-class extractor that converts `Document` chunks into `GraphDocument` objects — a much thinner abstraction than LlamaIndex PGI's pluggable-extractor + composable-retriever design. Where PGI gives you `SchemaLLMPathExtractor`, `SimpleLLMPathExtractor`, `DynamicLLMPathExtractor`, and a `sub_retrievers` pipeline, LangChain gives you one class with two internal modes (tool-calling and JSON-prompt fallback) and hands downstream retrieval off to a separate `Neo4jGraph` + `GraphCypherQAChain` + `Neo4jVector` assembly.

**LLMGraphTransformer architecture:**
Constructor (simplified from [5]): `LLMGraphTransformer(llm, allowed_nodes=[], allowed_relationships=[], prompt=None, strict_mode=True, node_properties=False, relationship_properties=False, ignore_tool_usage=False, additional_instructions="")`. Input is a `List[Document]`; output is a `List[GraphDocument]` via `convert_to_graph_documents` / `aconvert_to_graph_documents`. Internally it branches:

- **Tool-calling mode (default):** builds a dynamic Pydantic model via `create_simple_model()` — `SimpleNode(id: str, type: str, properties: Optional[List[Property]])` and a flattened `SimpleRelationship(source_node_id, source_node_label, target_node_id, target_node_label, type, properties)` [5]. When `llm_type == "openai-chat"`, `allowed_nodes` and `allowed_relationships` are injected as JSON-schema `enum` constraints on the `type` field; for other providers they go in the field `description` [5]. The model is bound via `llm.with_structured_output(DynamicGraph, include_raw=False)`. Bratanic's design note: "nested objects reduced the accuracy... so we decided to flatten the source and target nodes" [3].
- **Prompt-based fallback (`ignore_tool_usage=True` or no tool support):** uses `create_unstructured_prompt()` with a `UnstructuredRelation` Pydantic parser whose fields are `head, head_type, relation, tail, tail_type`, few-shot examples baked in (Adam/Microsoft/Best Talent), and a `JsonOutputParser` [5]. Properties are *not* extracted in this mode by design [3].
- **`allowed_relationships` as tuples** — `[("Person", "WORKS_FOR", "Company"), ...]` — activates schema-triple enforcement: the prompt enumerates valid `(source_type, RELATION, target_type)` patterns [5].
- **`strict_mode=True`** (default) post-filters extracted nodes/relationships against `allowed_nodes`/`allowed_relationships` after the LLM returns, dropping any out-of-schema triples [3][5].
- **Default system prompt** is a five-section directive ("Knowledge Graph Instructions for GPT-4") that emphasizes node-ID human-readability, basic-type labels ("person" not "mathematician"), general-and-timeless relationship types ("PROFESSOR" not "BECAME_PROFESSOR"), and explicit coreference resolution ("if John Doe is also 'he', always use 'John Doe'") ending with "Non-compliance will result in termination" [5].

**GraphDocument data model:**
From `langchain_community.graphs.graph_document`: `Node(id: str|int, type: str, properties: dict)`, `Relationship(source: Node, target: Node, type: str, properties: dict)`, `GraphDocument(nodes: List[Node], relationships: List[Relationship], source: Document)` [5]. The `source` field preserves the originating chunk, which is what `Neo4jGraph.add_graph_documents(..., include_source=True)` uses to materialize `(:Document)-[:MENTIONS]->(:Entity)` edges. `baseEntityLabel=True` adds a common `__Entity__` label across all extracted nodes so a single full-text index can cover entity-linking at query time [1][2].

**Integration path — typical LangChain book-to-graph pipeline:**
```
loader → TokenTextSplitter(chunk_size=512, chunk_overlap=24)
       → LLMGraphTransformer(llm, allowed_nodes, allowed_relationships,
                             node_properties=["description"])
       → graph.add_graph_documents(docs, baseEntityLabel=True, include_source=True)
       → CREATE FULLTEXT INDEX entity ... FOR (e:__Entity__) ON EACH [e.id]
       → retrieval = structured (GraphCypherQAChain or entity-seeded Cypher)
                   + unstructured (Neo4jVector.from_existing_index over chunks)
```
The Bratanic/LangChain blog [1] explicitly combines both: extract candidate entities from the question with another LLM call, look them up via the full-text index, expand two hops in Cypher, and concatenate those triples with top-k vector hits from chunk embeddings before the final answer LLM.

**LangGraph orchestration:**
LangGraph is a separate library — a stateful DAG/cyclic orchestrator ([7]) — and is not used inside `LLMGraphTransformer` itself. Where it shows up for KG work in 2026 is wrapping `convert_to_graph_documents` in an iterative-gleaning loop: node A extracts, node B validates/critiques against schema, conditional edge loops back to A with `additional_instructions` until a judge node accepts [6]. There is no canonical LangChain recipe for this yet; most KG examples still use a single-pass transformer.

**Strengths relative to book-RAG use cases:**
- One-line extraction with schema constraints; sensible defaults out of the box.
- Flattened relationship schema empirically extracts better than nested designs (PGI's `EntityNode`/`Relation` nesting pays an accuracy tax per [3]).
- `GraphDocument.source` back-reference is exactly the chunk-provenance link BookRAG needs for spoiler filtering — LangChain's `:Document -[:MENTIONS]-> :Entity` pattern is essentially what BookRAG's batch JSON already encodes.
- Strong Neo4j full-text-index + vector hybrid retrieval story; `baseEntityLabel=True` is a nice trick for unified entity search.

**Weaknesses / gaps for BookRAG's use case:**
- Package lives in `langchain_experimental` — the framework itself tags it unstable, and the repo split (April 2024 → separate `langchain-experimental`) has already caused import churn [5].
- No first-class progression/temporal awareness; no `effective_latest_chapter` concept. You'd bolt it on as `properties={"chapter": n}` and filter in Cypher.
- Retrieval is *not* modular the way PGI's `sub_retrievers` list is — you compose `Neo4jVector` + `GraphCypherQAChain` yourself and wire them with LCEL, which is more glue code.
- Kuzu support exists (`langchain_kuzu.KuzuGraph`) but is thinner than Neo4j; the canonical blog examples [1][4] all assume Neo4j with APOC, including the `apoc.meta.data()` schema introspection that `GraphCypherQAChain` relies on.
- Prompt-based fallback drops properties entirely [3], so provider portability costs you attribute extraction.
- Coreference is prompt-level only ("always use 'John Doe'"), no explicit resolver — BookRAG's BookNLP + parenthetical-insertion pipeline is strictly stronger for narrative text.
- Framework coupling: adopting the downstream retrieval chain drags in `langchain-core`, `langchain-community`, `langchain-experimental`, and `langchain-neo4j` — a heavier dep footprint than Cognee.

**Comparison with LlamaIndex PGI (iteration 3) and Cognee:**

| Axis | LangChain LGT | LlamaIndex PGI | Cognee |
|------|---------------|----------------|--------|
| Schema enforcement | Pydantic + `strict_mode` post-filter; enum only on OpenAI | `SchemaLLMPathExtractor` with full JSON-schema via `structured_predict`; triple validation native | Ontology-driven DataPoint classes, prompt-enforced |
| Extractor modularity | One class, two modes | Pluggable (`Simple`/`Schema`/`Dynamic`/`Implicit`Path…) chained in a list | Single cognify pipeline, customizable tasks |
| Retriever modularity | DIY LCEL compose | `sub_retrievers=[VectorContextRetriever, LLMSynonymRetriever, CypherTemplateRetriever, ...]` | Opinionated search types (INSIGHTS, CHUNKS, GRAPH_COMPLETION) |
| Graph store abstraction | `Neo4jGraph`, `KuzuGraph`, Memgraph, NebulaGraph | `Neo4jPropertyGraphStore`, `KuzuPropertyGraphStore`, `SimplePropertyGraphStore` | Kuzu + LanceDB + SQLite baked in |
| Chunk→entity provenance | `GraphDocument.source` + `:MENTIONS` edge | `EntityNode` carries source `TextNode` refs | Batch JSON on disk + DataPoint metadata |
| Maturity | Experimental tag; API churn | GA, stable since 0.10.x | Pre-1.0 (0.5.x), active breaking changes |

PGI gives you the most modular retrieval; LangChain gives you the thinnest extraction class and best hybrid Neo4j story; Cognee gives you the most opinionated end-to-end pipeline already wired to Kuzu.

**Key citations:**
1. [Enhancing RAG-based applications accuracy by constructing and leveraging knowledge graphs — LangChain blog / Tomaz Bratanic](https://www.langchain.com/blog/enhancing-rag-based-applications-accuracy-by-constructing-and-leveraging-knowledge-graphs)
2. [Enhancing the Accuracy of RAG Applications With Knowledge Graphs — Neo4j Developer Blog](https://medium.com/neo4j/enhancing-the-accuracy-of-rag-applications-with-knowledge-graphs-ad5e2ffab663)
3. [Building Knowledge Graphs with LLM Graph Transformer — Tomaz Bratanic, TDS](https://medium.com/data-science/building-knowledge-graphs-with-llm-graph-transformer-a91045c49b59)
4. [LangChain how-to: constructing knowledge graphs — docs.langchain.com](https://docs.langchain.com/oss/python/langchain/overview)
5. [LLMGraphTransformer source — langchain-experimental/libs/experimental/langchain_experimental/graph_transformers/llm.py](https://github.com/langchain-ai/langchain-experimental/blob/main/libs/experimental/langchain_experimental/graph_transformers/llm.py)
6. [LangGraph repo — langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
7. [LangGraph product page](https://www.langchain.com/langgraph)

**Concrete ideas worth stealing for BookRAG:**
- **Flatten Cognee's `Relationship` DataPoint.** BookRAG's current relationship likely carries nested source/target Character refs. Bratanic's empirical finding — flattened `source_node_id/source_node_label/target_node_id/target_node_label` extracts more reliably than nested [3] — is directly applicable. The extraction DataPoint can stay flat; hydrate nested references at load time.
- **`baseEntityLabel` equivalent for Kuzu.** Add a common `__Entity__` node property (or labels set) across Character/Location/Faction/Theme so one Kuzu full-text index can cover entity-linking at query time instead of per-type indexes.
- **Enum on OpenAI, description everywhere else.** LGT's `optional_enum_field` trick [5] — use JSON-schema `enum` only when `llm_type == "openai-chat"`, fall back to enumerating values in the field description for other providers — is a clean pattern BookRAG should copy for its own structured-output calls when Anthropic is the backend.
- **`additional_instructions` as a per-book hook.** LGT lets callers inject extra prompt text without subclassing. BookRAG could use the same pattern to inject per-book ontology hints ("In this book, 'the Golds' refers to a faction, not a color") discovered during Phase 1.
- **`:Document -[:MENTIONS]-> :Entity` as first-class edges in Kuzu.** BookRAG encodes chunk provenance in batch JSON; materializing it as actual edges (with `chapter` and `paragraph_start` properties) makes the spoiler allowlist a one-hop Cypher filter rather than a Python walk over JSON files.
- **Keep LGT in mind as a sanity-check extractor.** Running the same chapter through `LLMGraphTransformer(allowed_nodes=[...BookRAG types...], strict_mode=True)` and diffing against Cognee's extraction would be a cheap validation harness — disagreements surface prompt-engineering bugs in either pipeline.
- **Default prompt's coreference clause is worth adopting verbatim.** The "If 'John Doe' is also referred to as 'he' or 'Joe', always use 'John Doe'" instruction [5] is more explicit than what BookRAG's current extraction prompt likely says, and complements (doesn't replace) the BookNLP-based parenthetical coref.

### 5. Neo4j GraphRAG Python Library

**Researched:** 2026-04-22 (iteration 5)

**TL;DR:** `neo4j-graphrag` is Neo4j's first-party Python SDK for building KG + retrieval pipelines against a Neo4j database [1][2]. Unlike the framework-shaped offerings of LangChain and LlamaIndex, it is a vertically integrated SDK: a single `SimpleKGPipeline` orchestrates chunking → embedding → LLM extraction → resolution → upsert, and a single `GraphRAG` class pairs any of five built-in retrievers with an LLM under a configurable `RagTemplate` [3][4]. The tradeoff is obvious: it only targets Neo4j, so adopting it means giving up Kuzu's zero-ops embedded story.

**SimpleKGPipeline architecture:**
The pipeline exposes five stages, each a swappable component [3]:
1. **Chunking** via `FixedSizeSplitter(chunk_size, chunk_overlap, approximate=True)` — `approximate=True` avoids mid-word cuts, mirroring BookRAG's paragraph-aligned batching.
2. **Embedding** via `TextChunkEmbedder(embedder=OpenAIEmbeddings())` — stores chunk vectors so the retrievers can query a Neo4j vector index over `:Chunk` nodes.
3. **Extraction** via `LLMEntityRelationExtractor(llm=..., use_structured_output=True)` — emits entities/relations conforming to a declared schema.
4. **Resolution** via any of `SinglePropertyExactMatchResolver`, `FuzzyMatchResolver`, or `SpaCySemanticMatchResolver` (see below).
5. **Upsert** via `Neo4jWriter(driver, batch_size=1000)`.

The whole thing can be declared in YAML with `template_: SimpleKGPipeline` and `neo4j_config`/`llm_config`/`embedder_config`/`schema` blocks [3], which is closer to BookRAG's `config.yaml`-plus-Pydantic approach than LangChain's "compose LCEL yourself" philosophy.

**LLMEntityRelationExtractor:**
The extractor renders the chunk through `ERExtractionTemplate` with three template variables — `text` (mandatory), `schema`, and `examples` — and requests structured output [3]. Schema is defined as three lists: `node_types` (strings or `{label, description, properties: [{name, type, required}]}` dicts), `relationship_types` (same shape), and `patterns` (tuples of `(source_label, rel_label, target_label)`) [3]. Three boolean knobs — `additional_node_types`, `additional_relationship_types`, `additional_patterns` — make the schema strict or open. Compared to LangChain's `LLMGraphTransformer`, neo4j-graphrag is more schema-forward: patterns are first-class (LangChain's `allowed_relationships` can optionally carry tuples, but it's an afterthought); relationship properties are declared the same way as node properties; and the extractor always runs structured output against the schema rather than LGT's prompt-plus-post-filter `strict_mode`. Compared to LlamaIndex's `SchemaLLMPathExtractor`, the pattern list plays the same role as `kg_validation_schema`, but neo4j-graphrag additionally lets each node/rel type declare its own typed property set, which PGI does less ergonomically.

**Retrievers available [2][5]:**
- **VectorRetriever** — approximate-NN cosine search over a Neo4j vector index on `:Chunk` nodes; returns raw chunks.
- **VectorCypherRetriever** — vector search followed by a user-supplied Cypher `retrieval_query` that traverses 2–3 hops out from the matched chunks. Output is formatted as `entity - REL -> entity` strings, so the LLM sees both the chunk text and the neighborhood. This is the canonical "graph-augmented" retriever.
- **HybridRetriever** — fuses vector similarity with Neo4j full-text search over the same nodes.
- **HybridCypherRetriever** — `HybridRetriever` + user-supplied Cypher traversal.
- **Text2CypherRetriever** — sends the question plus the schema to the LLM, asks for a Cypher query, executes it, returns rows. Neo4j Labs publishes a crowd-sourced Text2Cypher (2024) dataset and fine-tuned Llama/Codestral models benchmarked on it [6][7]; the retriever accepts few-shot examples and a schema string to ground generation.
- **ExternalRetriever adapters** — Weaviate, Pinecone, and Qdrant adapters fetch vectors from an external store and then do the Neo4j graph join.

Composition pattern: build one retriever, hand it to `GraphRAG`. Retrievers also expose `.search(query_text, top_k)` for standalone use.

**GraphRAG orchestrator class:**
`GraphRAG(retriever, llm, prompt_template=RagTemplate())` is a ~50-line class [4][8]. Calling `rag.search(query_text, return_context=True)` runs the retriever, fills the `RagTemplate` (default sections: system instructions "Answer the user question using the provided context", plus `{context}`, `{examples}`, `{query_text}` placeholders), calls the LLM, and returns a `RagResultModel` with `.answer` and optionally `.retriever_result` [4][8]. To customize, subclass `RagTemplate` and pass it in — no LCEL chains, no AgentExecutor. This is closer in spirit to Cognee's `SearchType.GRAPH_COMPLETION` than to LangChain's multi-layered abstraction.

**Entity resolution:**
Three resolvers live in `neo4j_graphrag.experimental.components.resolver` [3][9]:
- **`SinglePropertyExactMatchResolver`** — merges nodes sharing a label and exact `name` property. Default, fast, no deps.
- **`FuzzyMatchResolver`** — RapidFuzz Levenshtein-normalized similarity across textual properties of same-labeled nodes; score in [0, 1] with a configurable threshold. Installed via the `fuzzy-matching` extra.
- **`SpaCySemanticMatchResolver`** — spaCy-embedding cosine similarity for semantic matches ("Ebenezer Scrooge" ≈ "Mr. Scrooge"). Installed via the `nlp` extra.
All resolvers accept a `filter_query` (e.g. `"WHERE NOT entity:Resolved"`) so already-resolved entities can be skipped on incremental runs, which is directly relevant to BookRAG's batch-by-batch ingestion.

**Strengths relative to book-RAG use cases:**
- Schema maturity: typed properties on both nodes and relationships, plus pattern tuples, out of the box [3].
- First-party Neo4j integration: vector index, full-text index, Cypher traversal all in one store; no LanceDB/Kuzu bifurcation.
- Text2Cypher as a query mode — for a book KG, questions like "which characters has Scrooge met by chapter 3" compile naturally to Cypher [6].
- `VectorCypherRetriever` with a 2–3-hop `retrieval_query` is exactly the shape BookRAG wants: start from a chunk, expand to Character/Location/Event neighbors, stop at the spoiler cutoff.
- Three-tier resolver ladder (exact → fuzzy → semantic) is more ergonomic than rolling your own.

**Weaknesses / gaps for BookRAG's use case:**
- Neo4j lock-in: retrievers, writer, resolvers, and Text2Cypher are all Neo4j-specific. BookRAG's locked decision is Kuzu + LanceDB; swapping means running a Neo4j server (Docker, 1–2 GB RAM floor) on the M4 Mac.
- No progression / fog-of-war awareness. `filter_query` can hack a spoiler cutoff into resolution, but at query time you'd need to hand-author `WHERE chunk.chapter <= $cutoff` into every `retrieval_query`; there is no `effective_latest_chapter` primitive.
- No per-identity snapshot selection. The resolvers merge duplicates into a single node; BookRAG Phase 2 explicitly wants multiple snapshots per identity indexed by batch window.
- `experimental.components` namespace — the KG-builder side is still flagged experimental in the package layout [3], so API churn is comparable to Cognee.
- Heavier deployment story: Neo4j server + plugins (APOC, GDS for some operations) + drivers vs. Kuzu's embedded single-process model.

**Migration path if BookRAG swapped Kuzu for Neo4j:**
For a single-user M4 Pro Mac, the migration is probably net negative. Kuzu is embedded, zero-config, and already wired through Cognee; Neo4j adds a daemon, a JVM, auth config, and an HTTP/Bolt hop on every query. What Neo4j does give you — Cypher, mature full-text indexes, GDS algorithms for community detection, a well-trodden Text2Cypher path, and the Bloom/Browser visualizations — is attractive for exploratory work on narrative KGs (centrality of characters, community-of-mentions per chapter) but not on the critical path for spoiler-safe QA. A realistic middle path: keep Kuzu as the production store, but mirror a read-only snapshot into Neo4j for analysis and to run `VectorCypherRetriever`/Text2Cypher experiments without committing to a swap. The `Neo4jWriter` component could be re-targeted at that mirror.

**Key citations:**
1. [neo4j/neo4j-graphrag-python — GitHub repo](https://github.com/neo4j/neo4j-graphrag-python)
2. [GraphRAG for Python — official docs index (neo4j.com/docs/neo4j-graphrag-python/current/)](https://neo4j.com/docs/neo4j-graphrag-python/current/)
3. [User Guide: Knowledge Graph Builder — SimpleKGPipeline, schema syntax, resolvers](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html)
4. [User Guide: RAG — GraphRAG class, RagTemplate, return_context](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html)
5. [GraphRAG Python Package: Accelerating GenAI With Knowledge Graphs — Neo4j Dev Blog](https://neo4j.com/blog/news/graphrag-python-package/)
6. [Benchmarking Using the Neo4j Text2Cypher (2024) Dataset — Neo4j Developer Blog](https://neo4j.com/blog/developer/benchmarking-neo4j-text2cypher-dataset/)
7. [neo4j-labs/text2cypher — datasets, evals, finetuning](https://github.com/neo4j-labs/text2cypher)
8. [`neo4j_graphrag.generation.graphrag` source module](https://neo4j.com/docs/neo4j-graphrag-python/current/_modules/neo4j_graphrag/generation/graphrag.html)
9. [`neo4j_graphrag.experimental.components.resolver` source module](https://neo4j.com/docs/neo4j-graphrag-python/current/_modules/neo4j_graphrag/experimental/components/resolver.html)
10. [The Neo4j GraphRAG Package for Python — Will Tai, Neo4j Dev Blog](https://medium.com/neo4j/the-neo4j-genai-package-for-python-bbb2bd2ad3b3)

**Concrete ideas worth stealing for BookRAG:**
- **Adopt the `patterns` tuple syntax for BookRAG's ontology.** Today BookRAG's ontology lives as OWL/JSON after BERTopic discovery; rewriting the extraction-time contract as a flat list of `(Character, MET, Character)`, `(Character, LIVES_IN, Location)` tuples — exactly the neo4j-graphrag shape — would tighten the extraction prompt without changing the graph schema.
- **Three-resolver ladder.** Run `SinglePropertyExactMatchResolver`-equivalent first (merge "Scrooge" ≡ "Scrooge"), then a RapidFuzz pass ("Ebeneezer" typo, "Mr. Scrooge" honorific), then a spaCy/embedding pass for cross-surface-form merges ("the old miser" ≡ "Scrooge"). BookRAG currently relies on BookNLP coref plus prompt-level identity hints; a post-extraction resolver ladder would catch LLM-introduced drift between batches.
- **`filter_query` on resolvers.** Tag merged nodes with `:Resolved` and skip them on the next batch. Directly portable to Kuzu: add a `resolved_at_batch` property and gate the merge query on it.
- **`VectorCypherRetriever` pattern for spoiler retrieval.** Express the allowlist as a parameterized Cypher traversal rather than a Python walk over batch JSON: `MATCH (c:Chunk) WHERE c.chapter <= $cutoff WITH c ... MATCH (c)-[:MENTIONS]->(e) ...`. Even on Kuzu, this is one query instead of N file reads.
- **`RagTemplate` subclassing over prompt-string editing.** BookRAG's Cognee `GRAPH_COMPLETION` prompt is currently edited in place. A subclassable template with named placeholders (`{context}`, `{paragraph_window}`, `{cutoff_chapter}`) would make A/B-ing prompts across facets (CHARACTER_STATE vs. PLOT_SUMMARY) safer.
- **Text2Cypher as a "structured question" escape hatch.** For questions that are genuinely graph-shaped ("list everyone Scrooge has spoken to before chapter 4"), generate a Kuzu Cypher query with a schema-primed LLM call, execute it, and serialize the rows back into the answer — bypassing vector retrieval entirely. The neo4j-labs Text2Cypher dataset and fine-tunes [6][7] are a ready-made evaluation harness even if the target dialect is Kuzu-Cypher, not Neo4j-Cypher.
- **Structured-output extraction by default.** `use_structured_output=True` on `LLMEntityRelationExtractor` [3] is the OpenAI/Anthropic JSON-schema-enforced mode; BookRAG already uses Pydantic DataPoints, but confirming that the Cognee extraction task sets OpenAI `response_format={"type": "json_schema", ...}` (not just "json_object") would be a cheap reliability win.

### 6. Cognee 0.5.x internals

**Researched:** 2026-04-22 (iteration 6)

**TL;DR:** Cognee positions itself as an "ECL" (extract / cognify / load) framework for AI memory, built around three primitives — `DataPoint` (Pydantic models with `metadata.index_fields`), `Pipeline` (ordered `Task`s executed by `run_pipeline`), and a pluggable storage trinity (graph + vector + relational). Unlike LlamaIndex PGI, which treats the KG as one index type among many, or neo4j-graphrag, which is a thin client over a single vendor's DB, Cognee's distinguishing idea is that the same typed Pydantic model is simultaneously persisted as graph nodes, graph edges (from its reference fields), and vector embeddings (over `index_fields`) in a single `add_data_points` write [1][2]. That write is what BookRAG already uses and bypasses `cognify` for — the rest of this section is context for whether that bypass is still the right call.

**Core abstractions.** A `DataPoint` is a Pydantic v2 `BaseModel` carrying a UUID, version, timestamp, a `metadata: dict` with an `index_fields` list, and arbitrary typed fields; fields whose type is another `DataPoint` (or list of them) become graph edges at persist time, and fields listed in `index_fields` become vector-embedded strings [1]. A `Task` wraps a single async callable; a `Pipeline` is an ordered list of `Task`s dispatched by `cognee.modules.pipelines.run_pipeline`, which threads the output of each task into the next and records execution state [3]. `LLMGateway.acreate_structured_output(text_input, system_prompt, response_model)` is the provider-agnostic structured-extraction entry point Cognee's own tasks use and the one BookRAG reuses directly [3]. Storage adapters are pluggable: graph (Kuzu default, Neo4j, FalkorDB, Neptune, Memgraph), vector (LanceDB default, Qdrant, Milvus, PGVector, Chroma, Weaviate), and relational (SQLite default, Postgres) [1][2].

**`cognee.add` vs `cognee.cognify`.** `cognee.add(data, dataset_name, ...)` ingests raw content into the relational `Data` table and the file store, optionally chunking and embedding for plain RAG; it does *not* by itself build a graph. `cognee.cognify(datasets=..., ontology_file_path=..., graph_model=...)` runs the full cognify pipeline over already-added data and produces the KG [4][1]. BookRAG currently calls `cognee.add` for chunk-level vector indexing and then skips `cognify`, instead running its own extraction with `LLMGateway.acreate_structured_output` against custom DataPoints and persisting via `run_pipeline([Task(add_data_points)])` — which is effectively the final task of the default cognify pipeline used in isolation.

**Default cognify pipeline (six tasks) [4].** (1) `classify_documents` — wraps each `Data` row as a typed `Document` (Pdf, Text, Audio, ...). (2) `check_permissions_on_dataset` — enforces write ACL when `ENABLE_BACKEND_ACCESS_CONTROL` is on (no-op otherwise). (3) `extract_chunks_from_documents` — splits documents into `DocumentChunk` DataPoints with configurable chunker (`TextChunker` with overlap was added in 0.5.0 [5]). (4) `extract_graph_from_data` — for each chunk, calls `LLMGateway.acreate_structured_output` with a prompt selected by `GRAPH_PROMPT_PATH` (`generate_graph_prompt.txt`, `_simple`, `_strict`, or `_guided`) and a `KnowledgeGraph` response model of `Node`/`Edge`s, optionally grounded through an `OntologyResolver` [4][6]. (5) `summarize_text` — one LLM call per chunk producing a `TextSummary` DataPoint. (6) `add_data_points` — recursively walks the DataPoint graph, deduplicates by UUID, embeds `index_fields`, writes vectors to LanceDB, writes nodes/edges to Kuzu [1][4]. This is the function BookRAG patches locally.

**DataPoint model mechanics.** `index_fields` is declarative: only those string fields are embedded, everything else is stored as a graph property [1][7]. Reference fields — `founders: list[Person]` on a `Company` — are translated into typed edges (`Company --founders--> Person`) at persist time; this is how typed relationships emerge without an explicit triple model. `copy_model` (in `cognee/shared/graph_model_utils.py`) dynamically rebuilds a DataPoint subclass at runtime, which is why BookRAG's CLAUDE.md notes that `metadata` must use plain dict defaults rather than `Field(default_factory=dict)` — `copy_model` fails to carry `default_factory` through the copy [2][7]. 0.5 added multi-user access control to the write path, so DataPoints are now scoped to a (user, dataset) pair in the relational layer [8].

**SearchType enum (14 in 0.5.6) [9][10].** Grouped by category. *Vector-only:* `SUMMARIES` (vector over pre-computed `TextSummary`), `CHUNKS` (vector over raw `DocumentChunk`), `CHUNKS_LEXICAL` (BM25/lexical fallback), `RAG_COMPLETION` (chunks + LLM synthesis — classic RAG). *Graph-aware completion:* `GRAPH_COMPLETION` (default; vector seed → subgraph expansion → LLM synthesis), `GRAPH_SUMMARY_COMPLETION` (intermediate summarization before synthesis), `TRIPLET_COMPLETION` (retrieval over pre-embedded (subject, predicate, object) triplets — added via the triplet-embedding memify work in 0.5.0 [5]), `GRAPH_COMPLETION_COT` (multi-round chain-of-thought with follow-up questions), `GRAPH_COMPLETION_CONTEXT_EXTENSION` (iterative triplet expansion until coverage threshold). *Structured-query:* `CYPHER` (executes Cypher directly; Neo4j/Kuzu only), `NATURAL_LANGUAGE` (NL→graph query translation, i.e. Cognee's Text2Cypher equivalent). *Meta / specialized:* `FEELING_LUCKY` (LLM meta-router that picks a SearchType), `TEMPORAL` (extracts time constraints and filters by time-indexed edges; integrates with Graphiti [10]), `CODING_RULES` (applies rule-based logic over code KGs, paired with the code_graph pipeline). BookRAG currently uses only `GRAPH_COMPLETION`; `TRIPLET_COMPLETION` is the near-term candidate already being considered (`docs/superpowers/specs/2026-04-22-triplet-indexing.md`).

**Ontology support.** `cognify(ontology_file_path="x.owl", ...)` hands the file to `RDFLibOntologyResolver`, which parses via RDFLib (any format RDFLib reads — RDF/XML, Turtle, N-Triples, JSON-LD) once at init and caches the graph in memory [6][11]. During `extract_graph_from_data`, the resolver matches extracted entities to OWL classes/individuals, validates relations against object-property domain/range, and merges matching ontology subgraph structure into the LLM-produced graph — a "ground the LLM against a curated schema" pattern [11]. Multiple OWL files can be passed comma-separated; `ontology_file_path` is optional as of 0.5.0 [5]. Runtime ontology changes are not hot-reloaded.

**Multi-tenancy and access control (new in 0.5) [8][12].** 0.5.0 introduced a full RBAC model: `User`, `Tenant` (organization container), `Role` (group within a tenant), and `Dataset` principals with read/write/delete/share permissions, persisted as ACL rows in the relational store. `ENABLE_BACKEND_ACCESS_CONTROL=true` activates the enforcement path: authentication becomes mandatory, databases are selected per-request via context variables, and every task checks permissions against the acting user. For single-user BookRAG the flag stays off, which is why we never see the ACL overhead — but it means every Cognee write path carries a check_permissions conditional and per-request DB-handler dispatch that adds no value to our deployment [13].

**Known rough edges.**
- **`asyncio.Lock` / LanceDB singleton binding.** Cognee 0.5.6 creates LanceDB adapter and asyncio primitives lazily at module import; they bind to whatever event loop is running when first used, and reusing them from a different loop raises `RuntimeError: ... bound to a different event loop`. BookRAG hit this running the pipeline in a background thread with its own loop and had to move to `asyncio.create_task` on the main loop (see CLAUDE.md "Temporary Decisions"). The underlying asyncio behavior is well-known [14]; the cognee-side manifestation is tracked in the macOS "Cognify hangs on KqueueSelector" class of issues [15].
- **`copy_model` + `Field(default_factory=...)`.** `copy_model` in `graph_model_utils.py` does not propagate `default_factory`, so DataPoints with factory defaults silently lose their defaults on the copy. BookRAG's workaround: plain dict `metadata = {"index_fields": [...]}` literals [2].
- **Empty-list crash in upsert_edges / upsert_nodes.** When `extract_graph_from_data` produces no edges (or no nodes) for a chunk — common on boilerplate or header-only chunks — the Kuzu adapter's bulk `UNWIND $rows` path issues a query with an empty parameter list and raises. BookRAG patches `cognee/infrastructure/databases/graph/kuzu/upsert_edges.py` and `upsert_nodes.py` with empty-list guards; the general bug class ("Resolve issue with empty node set") was addressed upstream in #1744 but not the Kuzu adapter specifically at 0.5.6 [5].
- **Best-effort persistence.** Cognee catches adapter exceptions in `add_data_points` and continues; BookRAG compensates by writing batch JSON to disk before calling Cognee so the pipeline can complete even if the graph write fails.
- **Telemetry uses blocking `requests.post` inside async contexts**, filed as issue #2120 [16] — minor but a reminder that the library has ongoing async-correctness debt.
- **Pydantic v2 migration incomplete.** `DataPoint.json()` still uses deprecated v1 methods (issue #2042) [17].

**Strengths vs. the competitive set.**
- Unified typed-model path (DataPoint → graph + vectors in one write) is more ergonomic than LlamaIndex PGI's separate KG extractor + vector index plumbing or neo4j-graphrag's explicit `SimpleKGPipeline` + retrievers split.
- The `Pipeline`/`Task` primitive is genuinely reusable — BookRAG is evidence: we discard the default cognify and drop in our own task chain while keeping the same persist step.
- 14 SearchTypes including `TEMPORAL`, `GRAPH_COMPLETION_COT`, and `FEELING_LUCKY` are more off-the-shelf retrieval variants than Microsoft GraphRAG (fixed local/global) or LightRAG (fixed low/high/hybrid) ship with.
- OWL ontology grounding in the default extractor is rare; neo4j-graphrag has schema tuples but not full OWL.
- Storage pluggability is broader than neo4j-graphrag (Neo4j-only on the graph side).

**Weaknesses / gaps.**
- API instability: the dev branch is already at 1.0.1.dev4 as of 2026-04-21, so any 0.5.x-specific code BookRAG writes is on a deprecation clock.
- Documentation is uneven — search-type details are best covered in a community dev.to post [10] rather than the official docs [9]; ontology reference is thin on how resolver matches actually influence the LLM prompt.
- Kuzu adapter has known fragility (locking errors during concurrent search [18], empty-list bug we patched, `upsert_triplet` missing for LlamaIndex interop [19]).
- 0.5.x release notes themselves are weak: 0.5.6's notes read like a generic SaaS product changelog ("memory filtering improvements in the UI") with almost no signal about library-level changes, which makes it hard to know what to pin [20].
- Performance at book-scale: single-book cognify on A Christmas Carol (~28k words) is tractable, but Red Rising (~100k words, ~45 chapters) already forces BookRAG's batched-cognify workaround because the default pipeline's one-LLM-call-per-chunk extraction plus per-chunk summarization is expensive and not checkpointed.
- Multi-tenancy adds conditional overhead BookRAG doesn't use; the `dataset_database_handler` dispatch added in 0.5.0 [5] routes every read/write through a per-request context variable.

**Key citations.**
1. [From Data Points to Knowledge Graphs — cognee blog](https://www.cognee.ai/blog/deep-dives/from-data-points-to-knowledge-graphs)
2. [cognee/shared/graph_model_utils.py — copy_model source](https://github.com/topoteretes/cognee/blob/main/cognee/shared/graph_model_utils.py)
3. [topoteretes/cognee — repo overview](https://github.com/topoteretes/cognee)
4. [Cognify — Cognee Documentation](https://docs.cognee.ai/core-concepts/main-operations/cognify)
5. [Release v0.5.0 — cognee](https://github.com/topoteretes/cognee/releases/tag/v0.5.0)
6. [Ontology Quickstart — Cognee Documentation](https://docs.cognee.ai/guides/ontology-support)
7. [Custom Data Models — Cognee Documentation](https://docs.cognee.ai/guides/custom-data-models)
8. [Multi-User Mode Permissions Overview — Cognee Documentation](https://docs.cognee.ai/core-concepts/multi-user-mode/permissions-system/overview)
9. [Search — Cognee Documentation](https://docs.cognee.ai/api-reference/search/search)
10. [Search Types in Cognee — dev.to (Chinmay Bhosale)](https://dev.to/chinmay_bhosale_9ceed796b/search-types-in-cognee-1jo7)
11. [Ontology Reference — Cognee Documentation](https://docs.cognee.ai/reference/ontology-reference)
12. [Multi-Tenant Ready: Role-Based Access Control, Dataset Sharing — cognee blog](https://www.cognee.ai/blog/cognee-news/product-announcement-user-management)
13. [Issue #2103 — Need clarity regarding ENABLE_BACKEND_ACCESS_CONTROL](https://github.com/topoteretes/cognee/issues/2103)
14. [asyncio.Lock bound-to-different-loop discussion — ComfyUI-Crystools #7](https://github.com/crystian/ComfyUI-Crystools/issues/7)
15. [Issue #1743 — Cognify hangs on macOS at KqueueSelector](https://github.com/topoteretes/cognee/issues/1743)
16. [Issue #2120 — send_telemetry() uses blocking requests.post](https://github.com/topoteretes/cognee/issues/2120)
17. [Issue #2042 — Update DataPoint to use Pydantic v2 methods](https://github.com/topoteretes/cognee/issues/2042)
18. [Issue #1100 — Kuzu locking error during cognee.search()](https://github.com/topoteretes/cognee/issues/1100)
19. [Kuzu #4440 — KuzuPropertyGraphStore missing upsert_triplet](https://github.com/kuzudb/kuzu/issues/4440)
20. [Release v0.5.6 — cognee](https://github.com/topoteretes/cognee/releases/tag/v0.5.6)

**Concrete fixes / simplifications for BookRAG.**
- **Upstream the Kuzu empty-list guards.** Our patches to `upsert_edges.py`/`upsert_nodes.py` are 5 lines each and would apply cleanly; a PR referencing #1744 would likely land. This removes local-patch drift and future-proofs against 0.5.x → 1.0 migration.
- **Stop calling `cognee.add` on the chunk path.** We already run our own chunker/parenthetical-coref path and persist DataPoints directly via `run_pipeline([Task(add_data_points)])`. The `cognee.add` call is redundant and adds a Data-table row per chunk; dropping it removes one failure surface and simplifies the "what exactly does Cognee own?" story.
- **Adopt `TRIPLET_COMPLETION` for spoiler-gated factual lookups.** Already scoped in `docs/superpowers/specs/2026-04-22-triplet-indexing.md`. The triplet embedding work landed in 0.5.0 [5] and gives a second retrieval mode that's naturally more gated (a triplet mentions two nodes; both must pass the allowlist) than free-form graph expansion.
- **Pin 0.5.6, plan a 1.0 evaluation spike.** 1.0.1 is the current stable; given how much changed between 0.5.0 and 0.5.8, a short evaluation spike would prevent a rushed forced upgrade. Key question for the spike: does 1.0 still let us run `run_pipeline([Task(add_data_points)])` in isolation, or has the API consolidated around `cognify()`?
- **Drop `ENABLE_BACKEND_ACCESS_CONTROL` from config entirely.** It's implicitly off; explicit `enable_backend_access_control=False` plus a comment removes any doubt and future-proofs against Cognee changing the default.
- **Keep the custom extraction path.** The single biggest thing Cognee's default cognify would give us is a free default extractor — but our BookNLP + parenthetical coref + ontology-discovery pipeline is tuned for narrative text and is BookRAG's moat. There is no good reason to fold back into default `cognify()`; the ECL primitive layer (DataPoint + Pipeline + Storage) is the right altitude for our reuse.

### 7. BookNLP & literary NLP

**Researched:** 2026-04-22 (iteration 7)

**TL;DR:** BookNLP is still the only turnkey "whole-pipeline for novels" toolkit (entities, coref, quotes, events, supersenses), but its coref head has been decisively beaten by maverick-coref (2024) on LitBank (78.0 vs BookNLP's 76.4/79.0). For BookRAG, the single highest-leverage swap is replacing BookNLP's coref with maverick-coref (LitBank-tuned checkpoint); entity/quote extraction can stay LLM-based or move to GLiNER for a cheap zero-shot pass.

**BookNLP pipeline:** [1] The current "big-BERT" BookNLP ships a seven-stage English pipeline: spaCy POS+dep parse → NER over the six ACE 2005 literary categories (PER, FAC, GPE, LOC, VEH, ORG) → character-name clustering → end-to-end neural coreference → quotation speaker attribution → supersense tagging (41 WordNet lexicographer classes) → event detection (asserted-realis events) → referential gender inference. Two checkpoint sizes (small, "personal-computer"; big, GPU/multi-core). Input: raw English text. Outputs: `.tokens`, `.entities`, `.quotes`, `.supersense`, `.events`, `.book` JSON. MIT license.

**Known accuracy / limitations:** [1] Reported F1 on held-out LitBank-style literary test sets:
- Entity tagging: small 88.2 / big 90.0 F1
- Supersense: 73.2 / 76.2 F1
- Events: 70.6 / 74.1 F1
- Coref: 76.4 / 79.0 F1 (avg CoNLL)
- Speaker attribution: 86.4 / 89.9 B3

BookRAG's internal "~70% coref accuracy" note is consistent with the small model on long/dialog-heavy passages — cross-document/long-range coref drift is the known failure mode. BookNLP also does not emit resolved text (why BookRAG reconstructs parentheticals from `.tokens`+`.entities`). Runtime on a full novel is minutes-to-tens-of-minutes on CPU.

**Alternatives for coreference on book-length text:**
- **maverick-coref** (Martinelli et al., ACL 2024) [2][3]: 83.6 CoNLL-F1 on OntoNotes, **78.0 on LitBank**, 87.4 on PreCo. Key selling point is efficiency: 192M-parameter model beats 13B-param LLM coref, trains with ~0.006× the memory and runs **~170× faster inference** than prior SOTA. PyTorch-Lightning API, multiple input formats. **License: CC-BY-NC-SA 4.0** — non-commercial only, a real constraint for a productized BookRAG.
- **BOOKCOREF** (ACL 2025) [2]: new book-scale coref benchmark explicitly targets long-document drift; Maverick variants gain +7.3 to +10.1 CoNLL-F1 over LingMess on LitBankNS (no-singletons). Indicates maverick-style models are the current frontier for literary-length coref.
- **LingMess / fastcoref** [4]: LingMess hits ~81.4 avg F1 on OntoNotes, ~2× faster than the older AllenNLP model. fastcoref's F-coref mode is 29× faster than AllenNLP with only ~1pt F1 drop. Good engineering baselines, but beaten by Maverick on LitBank.
- **AllenNLP coref**: effectively deprecated; AllenNLP project is archived.
- **LLM-as-coref** (GPT-4 few-shot, Llama-3): paper "Lions, Tigers, Bears" [5] shows LLMs can do literary coref annotation, but at much higher cost and with chunking headaches over a whole novel; quality is competitive on short passages, degrades on book-length without careful orchestration.

**Alternatives for character/entity extraction:**
- **spaCy `en_core_web_trf`**: strong generic NER but trained on OntoNotes/news — weak on fictional characters without fine-tuning.
- **GLiNER** [6][7]: bidirectional encoder (DeBERTa-based), zero-shot NER by label-prompt. ~0.81 F1 strict on CoNLL-2003, Apache-2.0, CPU-friendly. Out-of-box it "struggles with fiction" and benefits strongly from fine-tuning on Gutenberg/BookCorpus character spans; person extraction is the strongest axis once tuned. Good candidate for a cheap pre-LLM filter pass.
- **Flair**: classical BiLSTM-CRF stack, MIT, competitive on CoNLL but similar domain-shift issues on fiction.
- **LLM extraction** (current BookRAG Phase 2): highest quality, highest cost; Cognee's LLMGateway path is already wired.

**Quote attribution / speaker identification:** [8][9]
- **PDNC** (Project Dialogism Novel Corpus) is the community benchmark: **28 English novels, 37,131 manually annotated quotes**, with explicit/anaphoric/implicit quote types, speaker + addressee + referring expressions, character metadata.
- BookNLP's speaker-attribution head reports 86.4/89.9 B3 — strong on explicit quotes, degrades on implicit/anaphoric.
- Muzny et al. (2017) is the classic deterministic-sieve baseline.
- Michel & Epure (2024) "Realistic Evaluation of LLMs for Quotation Attribution" [9]: **Llama-3 improves +12 points over prior SOTA on the first 22 PDNC novels and +9 on the remaining**, with ablations showing the gain comes from reasoning, not memorization. Explicit quotes: nearly solved. Anaphoric/implicit: still the hard case across all systems.
- SIG (Su et al., 2023) prompt-based generation approach is an earlier LLM baseline on PDNC.

**Literary NER benchmarks:** [10]
- **LitBank**: 100 public-domain fiction works, 210,532 tokens (~2k per text), four annotation layers (entities, events, coref, quotes). CC-BY-4.0. This is the benchmark for literary coref and literary NER.
- **PDNC**: the quote-attribution benchmark (above).
- **FictionDB**-style corpora and **NarrativeQA** exist for downstream eval, but are not span-level NER benchmarks.

**Strengths of BookNLP for BookRAG's current use:**
- Covers six literary entity types out of the box, not just PER/ORG/LOC/MISC.
- Coref trained on LitBank, so prose-tuned rather than news-tuned.
- MIT license — commercial-friendly.
- Emits `.tokens`+`.entities`+`.quotes`+`.book` in one shot; parenthetical reconstruction is simple.
- Free, runs on CPU, offline.

**Weaknesses for BookRAG:**
- Coref F1 (76–79 LitBank) now trails maverick-coref at 78.0 and the "no-singletons" variants by up to ~10 F1.
- Neural architecture is a 2020-era e2e span model; no modern-model (Mistral/Llama/DeBERTa-v3) drop-in in the official repo.
- Slow on full novels (minutes on CPU, and BookRAG's pipeline currently blocks on it).
- Official repo has had minimal activity since 2022; speaker-attribution head doesn't benefit from 2024 LLM-attribution gains.

**Candidate replacements to evaluate:**
- **Coref: maverick-coref (LitBank checkpoint).** Delta: +~2 F1 over BookNLP-big, +~2-10 on no-singleton splits, 170× faster inference. Integration cost: medium — wrap `maverick` Python API, convert cluster output to BookNLP-compatible entity/coref columns so parenthetical insertion still works. **Blocker: CC-BY-NC-SA 4.0 license**; acceptable for research, a problem if BookRAG ever ships commercially.
- **Entity pass: GLiNER (fine-tuned on LitBank).** Delta: fast zero/few-shot over arbitrary custom types ("Faction", "MagicSystem") which are Phase-2 ontology-specific; Apache-2.0. Could act as a pre-filter before LLM extraction, cutting tokens.
- **Quote attribution: Llama-3 / LLM prompting on PDNC-style explicit quotes.** Delta: +9–12 pts over prior SOTA per [9]. Integration cost: low — already have LLMGateway. Use when quote-heavy passages matter for character KG edges.
- **Whole-book coref: BOOKCOREF benchmark + Maverick-incr.** If drift across chapters is the primary BookRAG pain, the incremental variants in the BOOKCOREF paper are the current frontier.

**Key citations:**
1. BookNLP repo and reported F1 numbers, `github.com/booknlp/booknlp` (MIT).
2. Martinelli, Barba, Navigli. "Maverick: Efficient and Accurate Coreference Resolution Defying Recent Trends." ACL 2024. `aclanthology.org/2024.acl-long.722/`.
3. `github.com/SapienzaNLP/maverick-coref`, `huggingface.co/sapienzanlp/maverick-mes-litbank` (CC-BY-NC-SA 4.0).
4. Otmazgin et al. "F-coref: Fast, Accurate and Easy-to-Use Coreference Resolution," EMNLP 2022; `github.com/shon-otmazgin/fastcoref`, `github.com/shon-otmazgin/lingmess-coref`.
5. "Lions, Tigers, Bears: Literary Coreference Annotation with LLMs." `arxiv.org/html/2401.17922v1`.
6. Zaratiana et al. "GLiNER: Generalist Model for NER using Bidirectional Transformer." NAACL 2024. `arxiv.org/abs/2311.08526`, `github.com/urchade/GLiNER` (Apache-2.0).
7. Poehnelt, "Building a Fiction AST and Training a NER Model with GLiNER" — practical fine-tune report on Gutenberg/BookCorpus.
8. Vishnubhotla et al., Project Dialogism Novel Corpus, `github.com/Priya22/project-dialogism-novel-corpus`; Vishnubhotla et al. (2023) "Improving Automatic Quotation Attribution in Literary Novels," ACL 2023 short.
9. Michel & Epure (2024). "A Realistic Evaluation of LLMs for Quotation Attribution in Literary Texts: A Case Study of LLaMa3." `arxiv.org/html/2406.11380`.
10. Bamman, Popat, Shen (2019) "An Annotated Dataset of Literary Entities," NAACL; Sims, Park, Bamman (2019) events; Bamman, Lewke, Mansoor (2020) coref. `github.com/dbamman/litbank` (CC-BY-4.0). Also: BOOKCOREF, ACL 2025, `aclanthology.org/2025.acl-long.1197.pdf`.

**Concrete recommendations for BookRAG:**
- **Prioritize swapping BookNLP coref for maverick-coref** (LitBank checkpoint) behind the existing "swappable interface for future BookCoref" decision. Expected wins: +F1 on long novels, dramatically faster pipeline stage, and maverick can emit cluster IDs we can fold straight into parenthetical insertion. **Verify license fit first** — CC-BY-NC-SA 4.0 may block commercial deployment.
- **Keep BookNLP for entity + quote passes in the short term** (MIT, already integrated). Phase-2 LLM extraction already compensates for its entity-tagger gaps.
- **Prototype GLiNER as an ontology-driven pre-filter** for Phase-2: given the discovered ontology (Faction, MagicSystem, Location subtypes), run GLiNER zero-shot to tag spans, then feed only labeled sentences to the LLM. This should reduce tokens and improve recall on custom types that BookNLP's ACE-2005 schema can't express.
- **For quote-heavy books (Red Rising-style dialogue), add an LLM quote-attribution pass** on explicit quotes using PDNC-style prompting; +9–12 F1 over BookNLP's speaker head, cheap (short windows), and directly improves Character ↔ PlotEvent edges.
- **Benchmark once against LitBank** (20-book test fold) to get BookRAG-specific numbers before committing to any swap — published F1 is from generic LitBank, not our downstream spoiler-gated QA metric.

### 8. Academic work on narrative KG extraction

**Researched:** 2026-04-22 (iteration 8)

**TL;DR:** The academic literary-NLP community has produced strong *component* resources — entity, coref, quote, event, and summarization benchmarks over real novels — but there is no end-to-end "novel → typed KG → spoiler-safe QA" benchmark. Character-network extraction is a mature subfield (ACM Computing Surveys 2019 devotes a whole survey to it), and 2024–2025 has brought book-scale long-context benchmarks (NovelQA, FABLES, BOOKCOREF) and a taxonomy paper (NarraBench, EACL 2026) confirming that most narrative skills are *undercovered* by existing evaluations. Crucially, **spoiler-aware retrieval is not a named research problem in the literature** — it appears as a constraint in recommendation and review-filtering work but not as a retrieval/KG evaluation axis. BookRAG is solving a problem the academy has not yet framed.

**Datasets for narrative QA and KG evaluation:**

- **LitBank** (Bamman et al., LREC 2020 / NAACL 2019) — 100 public-domain English novels, ~2k tokens sampled from each (210,532 tokens total), annotated for entities (6 ACE categories, proper + common), coref (29,103 mentions incl. pronouns), events (realis only), and quotations. MIT-style license. The canonical benchmark for literary entity/coref evaluation.
- **BOOKCOREF** (Martinelli, Bonomo, Huguet Cabot, Navigli — ACL 2025) — first book-scale coref benchmark, avg document >200k tokens. Character-focused annotations. Ships a gold test split and silver train/val produced by an automatic pipeline over archived Project Gutenberg. Shows long-doc coref systems gain up to +20 CoNLL-F1 when trained on book-scale data; existing LitBank-trained models collapse at book length.
- **PDNC — Project Dialogism Novel Corpus** (Vishnubhotla, Hammond, Hirst — LREC 2022) — 28 19th/20th-c. English novels, 37,131 manually annotated quotations with speaker, addressee, quote type, referring expression, and in-quote character mentions. Largest quote-attribution corpus.
- **NovelQA** (Wang et al., arXiv 2403.12766, 2024) — 89 English novels (61 public, 28 copyrighted held-out), 2,305 QA pairs, avg context >200k tokens, Multichoice + Generative settings, Cohen's κ = 0.947 inter-annotator agreement. Frontier LLMs struggle on multi-hop and detail questions.
- **FABLES** (Kim, Chang et al., COLM 2024, arXiv 2404.01261) — 3,158 claim-level faithfulness annotations over LLM summaries of 26 books published in 2023–2024 (deliberately post-training-cutoff to avoid contamination). Annotators must have read each book cover-to-cover. Finds no auto-rater correlates strongly with human faithfulness judgments; systematic end-of-book over-emphasis in LLM summaries.
- **NarrativeQA** (Kočiský, Schwarz, Blunsom, Dyer, Hermann, Melis, Grefenstette — TACL 2018) — 46,765 QA pairs over ~1,500 Project Gutenberg novels + movie scripts. Summary-only and story-only settings. The classic long-form narrative QA benchmark.
- **BookSum / BookSum-Chapter / BookSum-Book** (Kryściński, Rajani, Agarwal, Xiong, Radev — Findings of EMNLP 2022) — paragraph-, chapter-, and book-level abstractive summaries over Project Gutenberg + web archives. Standard summarization benchmark at book scale.
- **ChapterBreak** (Sun, Thai, Iyyer — NAACL 2022) — discourse-level challenge dataset. Given a long pre-chapter segment, distinguish the true next chapter from distractor chapters of the same book. Two splits: pg19 (Project Gutenberg) and ao3 (13,682 Archive-of-Our-Own fanfics). Long-range LMs underperform a trained segment-level baseline.
- **NarraBench** (Hamilton, Wilkens, Piper — EACL 2026, arXiv 2510.09869) — meta-benchmark: 4 dimensions × 50 narrative skills, surveys 78 existing benchmarks. Concludes only ~27% of narrative-understanding skills are well covered; narrative events, style, perspective, and "revelation" are nearly absent from current evals.
- **PG-19 / Project Gutenberg corpora** — standard training/eval substrate for long-range LMs; not an annotated KG benchmark, but the practical source for almost every literary benchmark above.
- (NovelChat and LaMP did not surface as literary-KG benchmarks in this search pass; LaMP is a general personalization benchmark, not novel-specific. A recent related system, "Living the Novel" (arXiv 2512.07474), *generates* timeline-aware conversational agents from novels but does not publish a KG benchmark.)

**Narrative KG extraction papers (2022-2026):**

- **"Extraction and Analysis of Fictional Character Networks: A Survey"** (Labatut & Bost, *ACM Computing Surveys* 52(5), 2019) — still the canonical survey. Character network = graph of characters with edges for co-occurrence/interaction/dialogue. Reviews extraction, unification (nickname collapsing), and analysis pipelines. Predates the LLM era but is the vocabulary every later paper uses.
- **HTEKG — Human-Trait-Enhanced Literary Knowledge Graph** (KEOD 2024) — schema adds psychological traits to character nodes on top of the standard character/location/event backbone. One of the few papers that explicitly names the output a literary KG.
- **"Guiding Generative Storytelling with Knowledge Graphs"** (arXiv 2505.24803, 2025) — KG used as *input* control signal for generation. Relevant because the schema (Character, Location, Event, Relation) is a near-mirror of BookRAG's extraction schema.
- **ReGraphRAG** (Findings of EMNLP 2025) — "reorganizing fragmented knowledge" KG-RAG; applied to narrative; addresses the exact scattering-across-chapters problem BookRAG's per-identity snapshots address.
- **"Use of Graph-Based Knowledge Organization to Improve RAG for Narrative Texts"** (Springer 2025 chapter) — explicit argument that narrative RAG needs structured backing; reports lift over vanilla dense retrieval on story QA.
- **"Narrative Structure Extraction"** (KONVENS 2025) and **"Harnessing LLM Ensembles for KG-Grounded Narrative Extraction"** (MDPI *Applied Sciences* 2026) — both do KG extraction for news/disinformation rather than fiction, but share the ensemble-prompting methodology BookRAG could adopt.
- **"Narrative Theory-Driven LLM Methods"** (survey, arXiv 2602.15851) and **"A Survey on LLMs for Story Generation"** (Findings of EMNLP 2025) — good entry points to the 2024–2026 narrative-LLM literature.
- **Quote attribution with LLMs**: "Evaluating LLMs for Quotation Attribution in Literary Texts" (arXiv 2406.11380, LLaMa-3 case study) and "Improving Quotation Attribution with Fictional Character Embeddings" (arXiv 2406.11368). Both use PDNC as the test bed; both beat BookNLP's speaker head.
- **Narrative temporal reasoning**: "Narrative-of-Thought" (arXiv 2410.05558) uses recounted narratives to improve temporal reasoning; "Generating Flashbacks with Event Temporal Prompts" (NAACL 2022) addresses non-linear story order directly.

**Benchmarks for downstream QA on narrative KGs:**

- NovelQA: accuracy (multichoice) + LLM-judge and human eval (generative). No KG-specific metric.
- NarrativeQA: BLEU-1/4, METEOR, ROUGE-L (generative free-form).
- FABLES: claim-level human faithfulness judgments; no auto-metric correlates.
- BOOKCOREF: CoNLL-F1 (MUC / B³ / CEAFe average).
- LitBank: span-F1 for entities/events, CoNLL-F1 for coref.
- PDNC: speaker-accuracy, addressee-accuracy (classification).
- ChapterBreak: next-chapter classification accuracy against hard negatives.
- NarraBench: taxonomy-coverage meta-metric, not a scored leaderboard.

**Open problems flagged in recent surveys:**

- Book-scale coreference with cross-chapter identity persistence (BOOKCOREF, ACL 2025).
- Nickname / alias unification for literary characters — "the old man" ↔ "Scrooge" ↔ "Ebenezer" — still hard; Bamman's BookNLP clusters on name-string morphology, not semantics.
- Reliable quote attribution beyond explicit dialogue tags (PDNC follow-ups).
- Temporal reasoning across flashbacks and parallel narratives (ChapterBreak, Narrative-of-Thought).
- End-of-book over-emphasis / position bias in LLM summaries (FABLES).
- Most narrative skills are undercovered by benchmarks (NarraBench: 73% gap).
- **Spoiler-aware retrieval / progressive-disclosure QA is not a named research problem.** Closest adjacent work is spoiler *detection* on review sites (McAuley et al., ACL 2019) and clickbait spoiling. Nothing evaluates a retrieval system on "does it leak post-cursor information?"

**Strengths of academic approaches:**

- Rigorous annotation protocols (inter-annotator agreement reported, gold test sets held out).
- Public datasets, mostly Project Gutenberg–based, license-friendly for research.
- Clear metrics (CoNLL-F1, span-F1) on well-scoped sub-tasks.
- Recent push toward book-scale (NovelQA, BOOKCOREF) means academia is finally meeting production reality.
- NarraBench gives a coverage map — you can locate your system on the narrative-skill taxonomy.

**Weaknesses / gaps for BookRAG's practical use:**

- Almost no paper ships a deployable pipeline — benchmarks release data + eval code, not an ingestion system.
- Copyright: every benchmark worth using is restricted to Project Gutenberg pre-1928 English novels, so modern/genre fiction (Red Rising, the BookRAG validation book) is *out of distribution* for every metric above.
- No spoiler-safety metric exists; BookRAG would have to author one.
- Character-network papers stop at co-occurrence graphs — they do not produce typed, queryable KGs (no PlotEvent, Theme, Faction nodes).
- QA benchmarks (NovelQA, NarrativeQA) do not expose a cursor; they assume the reader has finished.
- FABLES shows auto-metrics for faithfulness don't work — so BookRAG's spoiler-leak detection will need a human-eval or an LLM-judge calibrated against humans.

**Key citations:**

1. Bamman, D., Lewke, O., Mansoor, A. (2020). *An Annotated Dataset of Coreference in English Literature.* LREC. arXiv 1912.01140.
2. Bamman, D., Popat, S., Shen, S. (2019). *An Annotated Dataset of Literary Entities.* NAACL.
3. Martinelli, G., Bonomo, T., Huguet Cabot, P.-L., Navigli, R. (2025). *BOOKCOREF: Coreference Resolution at Book Scale.* ACL 2025. arXiv 2507.12075.
4. Vishnubhotla, K., Hammond, A., Hirst, G. (2022). *The Project Dialogism Novel Corpus.* LREC. arXiv 2204.05836.
5. Wang, C. et al. (2024). *NovelQA: Benchmarking QA on Documents Exceeding 200K Tokens.* arXiv 2403.12766.
6. Kim, Y., Chang, Y. et al. (2024). *FABLES: Evaluating Faithfulness and Content Selection in Book-Length Summarization.* COLM 2024. arXiv 2404.01261.
7. Kočiský, T. et al. (2018). *The NarrativeQA Reading Comprehension Challenge.* TACL 6. aclanthology.org/Q18-1023.
8. Kryściński, W., Rajani, N., Agarwal, D., Xiong, C., Radev, D. (2022). *BookSum.* Findings of EMNLP.
9. Sun, S., Thai, K., Iyyer, M. (2022). *ChapterBreak.* NAACL.
10. Hamilton, S., Wilkens, M., Piper, A. (2026). *NarraBench.* EACL. arXiv 2510.09869.
11. Labatut, V., Bost, X. (2019). *Extraction and Analysis of Fictional Character Networks: A Survey.* ACM Computing Surveys 52(5).
12. Michel, F. et al. (2024). *Evaluating LLMs for Quotation Attribution in Literary Texts.* arXiv 2406.11380.
13. Zhang, X. et al. (2024). *Narrative-of-Thought: Improving Temporal Reasoning via Recounted Narratives.* arXiv 2410.05558.

**Concrete ideas worth stealing for BookRAG:**

- **Adopt FABLES' evaluation protocol for spoiler leaks**: human annotators who've read the book mark whether each chatbot response leaks post-cursor facts. This gives BookRAG the first "spoiler-safety" metric and is directly publishable — FABLES-style evaluation of post-cursor faithfulness is a novel contribution nobody else has framed.
- **Use NovelQA's question taxonomy** (detail / multi-hop / discourse) as BookRAG's internal eval categories; it maps cleanly onto the spoiler-filter's behaviors (detail = node lookup, multi-hop = graph traversal).
- **Benchmark PDNC for quote attribution** on BookRAG's quote-to-speaker mapping — drop-in since BookNLP already emits quotes. This gives a real F1 number to put in any future write-up.
- **Frame "spoiler-aware retrieval" as an open research problem** in a short position paper referencing NarraBench's "revelation" gap. This is a defensible research contribution; the community has not named the problem.
- **Use BOOKCOREF's automatic silver-annotation pipeline idea** to scale BookRAG's internal regression tests beyond A Christmas Carol — generate silver identity-cluster ground truth for any Project Gutenberg book without human annotation.
- **Steal ChapterBreak's hard-negative sampling** as a probe: can BookRAG's KG distinguish a real cross-chapter continuation from a wrong-chapter distractor? Useful automatic eval for the graph's temporal coherence.
- **Adopt Narrative-of-Thought prompting** for the Phase-2 extraction LLM when a chapter contains flashbacks — recount the events in chronological order before extracting PlotEvents, which should clean up `first_chapter` / `last_known_chapter` assignments.

### 9. Ontology learning from narrative text

**Researched:** 2026-04-22 (iteration 9)

**TL;DR:** Ontology learning has swung from 30 years of pattern-based and statistical induction (Hearst, FCA, topic models) to LLM-driven construction, formalized as the LLMs4OL shared task at ISWC 2024/2025. For fiction specifically, almost all production-grade narrative ontologies (OntoMedia, GOLEM) are hand-crafted extensions of CIDOC-CRM/DOLCE, not learned — which means BookRAG's BERTopic + TF-IDF → OWL stage is solving a problem that SOTA has largely reframed as "prompt an LLM with competency questions and let it propose the classes."

**Classical ontology learning methods:**
- **Hearst lexico-syntactic patterns** ("X such as Y", "Y and other X") remain a baseline for hypernym discovery; the improved `spmi` variant uses low-rank matrix smoothing to compare concepts without direct surface matches [1]. Still used as a high-precision signal in hybrid 2024+ pipelines.
- **Formal Concept Analysis (FCA)** and its relational extension (RCA) turn object × attribute tables from text into concept lattices, from which a core ontology is semi-automatically derived [2]. Dated because lattices explode on large corpora and narrative attributes are messy, but it still shows up in WordNet-grounded pipelines.
- **Open-IE clustering** (below) and **subsumption induction via conditional-independence tests on latent topics** [3] round out the classical toolbox. In 2024+ narrative work these are rarely used standalone — they feed an LLM validator.

**Topic-model → ontology approaches:**
LDA → Top2Vec → BERTopic is the lineage. Pipelines go: cluster documents/passages → extract top terms per cluster → treat clusters as candidate classes → run subsumption tests (often Hearst or LLM) to build hierarchy. The fundamental weakness for fiction is that topic clusters are **thematic** ("poverty", "Christmas spirit", "family") rather than **taxonomic** ("Character", "Location", "PlotEvent"). BookRAG's current `discover_ontology.py` essentially uses BERTopic topics as *type* proposals, which conflates theme and type — a recurring criticism in the Short Review of Ontology Learning survey [4].

**Open information extraction (Open-IE) + induction:**
Stanford OpenIE, ReVerb, ClausIE, MinIE output (subj, rel, obj) triples. ReVerb only considers verbs and misses context; ClausIE uses clause-level grammar and is the strongest classical system per the WiRe57 benchmark [5]. For ontology induction, triples are clustered by argument distribution to discover classes and by relation-verb lemma to discover properties. Narrative-text limitations: dialogue-heavy passages produce triples like ("he", "said", "..."), pronouns overwhelm proper nouns without coref, and figurative language yields triples that don't correspond to facts-in-the-world. BookRAG side-steps this by using parenthetical-coref-resolved text, but Open-IE is still noisy on fiction.

**LLM-driven ontology construction (2023-2026):**
- **LLMs4OL** (Babaei Giglou et al., ISWC 2023/2024) evaluated 9 LLM families on three tasks: Task A term typing, Task B taxonomy discovery, Task C non-taxonomic relation extraction. Zero-shot LLM prompting matches or beats supervised baselines on WordNet, GeoNames, schema.org, and several biomedical ontologies [6]. The 2024 challenge formalized this as a shared task; the 2025 edition (Lippolis et al.) added "Ontogenia" using **Metacognitive Prompting** + Ontology Design Patterns to raise consistency [7].
- **OntoGPT / SPIRES** (Monarch Initiative) uses YAML schema templates + ontology grounding to do zero-shot structured extraction. The LLM is prompted with the schema, returns instances, and OntoGPT grounds each term against named ontologies (fuzzy/embedding match) [8]. Methodology is directly transferable: BookRAG's DataPoints are basically SPIRES schema templates.
- **BioCypher** pairs with OntoGPT to build hybrid ontologies with a "head" + "tail" fusion approach [9].
- **Chain-of-Layer** induces taxonomies top-down via in-context learning, selecting candidate entities layer-by-layer [4].
- **LKD-KGC** (Sun et al. 2025) does adaptive embedding-based schema integration — schemas emerge dynamically by clustering + LLM deduplication [10].
- **End-to-End Ontology Learning with LLMs** (Lo et al., NeurIPS 2024) produces OWL from raw text in a single model, though quality lags hand-curated ontologies [11].

**Schema-first vs schema-emergent tradeoff:**
Schema-first (Schema.org, DOLCE, SUMO, OntoMedia, GOLEM) gives interoperability, reusable reasoners, and cross-corpus comparability but can miss corpus-specific concepts (sci-fi factions, fantasy magic systems). Schema-emergent (BookRAG's current path, Chain-of-Layer, LKD-KGC) captures corpus idiosyncrasies but produces per-book silos. **Hybrid is now the default** per the LLM-KG survey [10]: anchor on a top-level ontology (DOLCE or CIDOC-CRM), let the LLM propose book-specific subclasses, validate subsumption with prompting. Cognee's own ontology layer implements exactly this — LLM-extracted nodes are fuzzy-matched (80% cutoff) to OWL classes from an optional user-supplied ontology, with `ontology_valid=True/False` tags preserving non-matching emergent concepts [12].

**Narrative-specific ontologies:**
- **OntoMedia** (Southampton, Contextus Project): events on timelines with TAQ/TPQ bounds, entity extensions for Character/Item/Space, mereological + causal + temporal relations. Rich on event-chains, weak on drama primitives like conflict [13].
- **GOLEM Ontology** (MDPI Humanities 2025, Groningen): CIDOC-CRM + LRMoo extension with DOLCE cognitive grounding. Modules for characters, relationships, events, settings, narrative inference; explicit cross-media linkage (character appears in novel, film, fan-wiki) [14]. Probably the strongest 2025 option as a "head" ontology for a BookRAG-style system.
- **NarrativeML, OntoStory, the Narrative Braid** — older academic frames, mostly for annotation rather than extraction.
- **DOREMUS** — music-specific, irrelevant here but often cited as the "CIDOC-CRM done right" exemplar.

**Evaluation of learned ontologies:**
LLMs4OL uses precision/recall on term-typing and taxonomy-discovery against gold ontologies [6]. Broader survey work cites (a) human expert judgment, (b) downstream QA impact on benchmark questions, (c) class coverage against a reference, (d) subsumption accuracy, (e) competency-question answerability [4][10]. For fiction no shared benchmark exists — this is a gap (NarraBench covers QA, not ontology quality).

**BERTopic specifics:**
Per Grootendorst (arXiv 2203.05794) [15]: sentence-transformer embeddings → UMAP to 5D → HDBSCAN density clustering (outlier-tolerant, variable-shape) → c-TF-IDF per cluster (treats each cluster as one "document" and runs TF-IDF against the corpus). Strengths for fiction: handles contextual polysemy ("cold" as temperature vs personality), tolerates outliers, topic reduction is tunable. Limitations: (1) HDBSCAN clusters are **thematic**, not type-based; (2) c-TF-IDF surfaces distinctive vocabulary, not class labels; (3) topics are flat — any hierarchy must come from a downstream step; (4) no notion of instance-vs-class distinction, which OWL requires.

**Strengths of BookRAG's current approach:**
- Deterministic, reproducible, no LLM cost for ontology discovery.
- Emits an OWL-style spec that constrains Phase 2 extraction — good engineering separation.
- Works offline, no API dependency for the ontology stage.
- Topic reduction provides natural sensitivity knob.

**Weaknesses / opportunities:**
- BERTopic topics are thematic clusters, not entity types — likely a mismatch between discovered "ontology" and the actual Character/Location/Faction/PlotEvent/Theme schema that DataPoints already declare.
- No subsumption hierarchy is learned; OWL output is essentially flat classes.
- No grounding to an upper ontology (DOLCE, CIDOC-CRM, GOLEM) means no cross-book reuse and no reasoner support.
- The "ontology" may be redundant given that DataPoints already hard-code the class list; BERTopic/TF-IDF mostly surfaces vocabulary, not structure.
- An LLM-driven stage (OntoGPT-style competency questions, or Chain-of-Layer taxonomy induction) would produce a structurally richer ontology with subclass relations.

**Key citations:**
1. Roller, Kiela, Nickel (2018) — improved Hearst patterns with spmi (low-rank smoothing).
2. Cimiano & Hotho — *Ontology Learning from Text Using FCA and RCA*, Inria 2005 / Springer.
3. Paliouras et al. — *Learning subsumption hierarchies of ontology concepts from text*, WIJ 2010.
4. Ma et al. (2024) — *A Short Review for Ontology Learning: Stride to LLMs Trend*, arXiv 2404.14991.
5. Del Corro & Gemulla (WWW 2013) — *ClausIE: Clause-Based Open Information Extraction*.
6. Babaei Giglou et al. (ISWC 2023) — *LLMs4OL: Large Language Models for Ontology Learning*, Springer LNCS.
7. Babaei Giglou et al. (arXiv 2409.10146) — *LLMs4OL 2024 Overview: The 1st LLMs for Ontology Learning Challenge*.
8. Caufield et al. (2023) — *SPIRES: Structured Prompt Interrogation and Recursive Extraction of Semantics*, Bioinformatics. Repo: monarch-initiative/ontogpt.
9. Lobentanzer et al. (2023) — *BioCypher: Democratizing Knowledge-Graph Construction in the Life Sciences*, Nature Biotechnology.
10. Bian et al. (2025) — *LLM-Empowered Knowledge Graph Construction: A Survey*, arXiv 2510.20345.
11. Lo, Jamnik, Pietquin (NeurIPS 2024) — *End-to-End Ontology Learning with Large Language Models*.
12. Cognee docs — `docs.cognee.ai/core-concepts/further-concepts/ontologies`.
13. Jewell et al. (2005) — *OntoMedia: An Ontology for Heterogeneous Media*, Contextus Project.
14. Barbieri et al. (2025) — *The GOLEM Ontology for Narrative and Fiction*, Humanities 14(10):193. Repo: GOLEM-lab/golem-ontology.
15. Grootendorst (2022) — *BERTopic: Neural Topic Modeling with a Class-Based TF-IDF Procedure*, arXiv 2203.05794.

**Concrete ideas worth stealing for BookRAG:**
- **Replace (or augment) BERTopic with an OntoGPT/SPIRES-style LLM stage:** prompt with "given these chapters, propose subclasses of Character/Location/Faction/PlotEvent/Theme specific to this book, with subsumption relations" — yields a hierarchy instead of flat themes, and aligns with existing DataPoint types.
- **Anchor the emitted OWL to GOLEM or CIDOC-CRM** as a head ontology; book-specific subclasses become tail ontology under Cognee's head+tail fusion pattern.
- **Adopt Chain-of-Layer** to induce a taxonomy layer-by-layer once BERTopic has produced candidate concept terms — cheap hybrid that keeps existing offline discovery but adds structure.
- **Use Ontogenia's Metacognitive Prompting + Ontology Design Patterns** for the ontology-review stage (currently optional/interactive) — the LLM critiques its own proposed ontology against competency questions the reader might ask.
- **Evaluate the learned ontology** using LLMs4OL-style term-typing accuracy on held-out entities — currently the ontology is never measured, only consumed.
- **Treat BERTopic output as "candidate vocabulary" not "ontology"** — rename internally to reduce confusion, since the real type schema lives in DataPoints. This is a clarity win even before adding an LLM stage.
- **Steal BioCypher's head+tail ontology fusion pattern** to let readers supply series-level ontologies (e.g., a "Red Rising universe" ontology shared across all three trilogies) that book-level extraction extends rather than replaces.

### 10. Temporal / progressive KGs & spoiler-aware retrieval

**Researched:** 2026-04-22 (iteration 10)

**TL;DR:** Temporal KGs are a mature research area (quadruple-based formalisms, forecasting benchmarks like ICEWS14, and an active 2024-2026 wave of "temporal RAG" systems). Agent-memory systems (Zep/Graphiti, HippoRAG, A-MEM, MemGPT, Generative Agents) and theory-of-mind benchmarks (FANToM) use structurally similar machinery — valid-time intervals, per-agent knowledge sets, episodic decay — but almost always apply it to *the agent's own history* rather than to gating retrieval against a *user's* externally tracked progress through a narrative. BookRAG's `source_chunk_ordinal ≤ reader_cursor` filter is essentially "valid-time in reader-progress time," and this axis appears to be a genuine gap in the published literature.

**Temporal KG formalisms:** The standard TKG formalism extends triples `(s, p, o)` to quadruples `(s, p, o, t)` where `t` is either a discrete timestamp (point-time) or an interval `[t_start, t_end]` (interval-time). Datasets split into two flavors: *event-centric* (ICEWS14, ICEWS05-15, GDELT — each fact has a single timestamp) and *validity-interval* (YAGO2/3, Wikidata temporal — facts hold across ranges). Bi-temporal models distinguish *valid time* (when the fact was true in the world) from *transaction time* (when the system learned it) [1, 2].

**Temporal KG embedding & reasoning:** TTransE and TA-TransE inject timestamp embeddings into TransE-style scoring; HyTE projects entities/relations onto time-specific hyperplanes; TComplEx adds temporal factors to ComplEx tensor decomposition [3]. For forecasting (predict `t+1` from history), RE-NET uses autoregressive GRU over entity neighborhoods; xERTE builds explainable temporal-attention subgraphs; CyGNet uses a copy-generation mechanism over historical facts; TLogic mines temporal logical rules via random walks and remains competitive for explainability [4, 5]. On ICEWS14/05-15 the embedding and rule-based families trade blows; recent work (GENTKG, CALENDAR+, "History Repeats Itself" baseline 2024) shows simple frequency baselines surprisingly strong [6].

**Time-aware / temporal RAG (2024-2026):** A clear cluster emerged in 2025. **T-GRAG** (arXiv 2508.01680) builds a temporal KG generator + temporal query decomposer + three-layer interactive retriever to resolve temporal conflicts. **TG-RAG / STAR-RAG** (arXiv 2510.13590, 2510.16715) represent corpora as bi-level temporal graphs with hierarchical time summaries, using rule-graph propagation to prune search space. **TimeRAG** (CIKM 2025) adds search-engine augmentation for complex temporal reasoning. Benchmarks for these systems are **TimeQA** (easy/hard by whether the temporal expression is explicit), **TempReason** (L1 time-time, L2 time-event, L3 event-event), **TempQuestions**, **TimeBench**, and **UnSeenTimeQA** (ACL 2025) [7, 8, 9]. Every one of these frames the temporal axis as *wall-clock world time* — "what was true in 2011?" — not as *consumer progress time*.

**Streaming / incremental KG construction:** LightRAG (EMNLP 2025) is the closest production system; its `insert` path merges new documents into existing graphs without full rebuild, with ~50% speedup [10]. ContinualGNN and dynamic-graph embedding work addresses node/edge streams but mostly targets fraud/recsys, not narrative. MemGraph streaming and Neo4j Change Data Capture handle edge streams at the DB layer.

**Fog-of-war research (games):** AlphaStar (DeepMind, Nature 2019) handles StarCraft II partial observability by feeding only what the player could see into an LSTM-over-attention encoder; enemy units behind fog are literally absent from observations [11]. OpenAI Five (Dota 2) uses a similar masking approach. The analogy to BookRAG is tight: both hide future/unseen state at *input construction time* rather than post-hoc filtering. AlphaStar's architectural lesson — mask at the feature-extraction boundary, not at the loss — is what BookRAG already does by filtering the node set before LLM context assembly.

**Episodic memory systems:** **Generative Agents** (Park et al., UIST 2023) rank memory-stream entries by recency + importance + relevance; memories are timestamped but the agent sees *its own* past, not a gated slice of external truth [12]. **MemGPT** (Packer et al., arXiv 2310.08560) treats memory as OS-style paging between context and archival store [13]. **HippoRAG** (NeurIPS 2024) indexes episodes by entities and runs personalized PageRank for retrieval. **A-MEM** (arXiv 2502.12110) self-organizes Zettelkasten-style links between memories [14]. **Zep / Graphiti** (arXiv 2501.13956) is the single closest prior art: a *bi-temporal* KG with four timestamps per edge (creation, expiration, valid-from, valid-to) and explicit edge invalidation on contradiction [15]. Zep uses this for enterprise agent memory (user told the agent X on Monday, revised it Tuesday) — the machinery would work for reader-progress gating with trivial reinterpretation of `valid_from` as `source_chunk_ordinal`.

**Narrative simulators that hide state:** AI Dungeon and NovelAI track "world state" implicitly via memory banks and context injection; neither formally gates what the narrator *reveals* to the player by a progress cursor because the player *is* driving the narrative. **FANToM** (EMNLP 2023) and **ToMi** are theory-of-mind benchmarks that test whether LLMs can track per-character belief states in information-asymmetric conversations — structurally the same problem as BookRAG (each character has seen a subset of world facts), but evaluated on dialog not retrieval [16]. No system found actively *gates generation* on per-character knowledge during narrative synthesis.

**Spoiler-safe content filtering (adjacent):** Wan, Misra, Nakashole, McAuley (ACL 2019) trained sentence-level spoiler classifiers on 1.3M Goodreads reviews (89-92% accuracy), finding spoiler language is book-specific and clusters in review tails [17]. SemEval-2023 Task 5 (clickbait spoiling) inverts this: *generate* spoilers to satisfy curiosity. Both treat spoilers as a classification/generation problem over free text; neither builds a progress-indexed knowledge structure.

**Time-aware recsys (serialized content):** Episode-next-watch models (Netflix, Spotify continue-listening) track a cursor and recommend forward, but the *content* of a recommendation (title, thumbnail, synopsis) is rarely filtered for spoilers of later episodes — this is an acknowledged UX gap handled by editorial copy, not ML.

**Valid-time filtering in graph DBs:** Neo4j supports temporal values and community-built bitemporal versioning patterns (validity-interval properties on nodes/edges, SNAPSHOT operators via Cypher) but no native "AS OF" syntax [18]. T-GQL (research proposal) and the bitemporal property-graph paper (arXiv 2111.13499) formalize what Neo4j users hand-roll. **Kuzu** (BookRAG's graph DB) has no native temporal/bitemporal primitives as of 2026 — filtering by timestamp properties is possible but must be done in application code, which is exactly what BookRAG does. TerminusDB is the one graph DB with native time-travel (content-addressed immutable commits).

**Where BookRAG sits in this landscape:** BookRAG is a **read-time valid-time filter on a static, fully-ingested KG**, where the "valid time" axis is *reader progress through the source text* rather than world time. It's closest architecturally to Zep/Graphiti's bi-temporal KG, but with three inversions: (a) the cursor is user-controlled, not event-driven; (b) validity runs over *document ordinal* not wall-clock; (c) there is one cursor per reader per book rather than one global "now." It also resembles AlphaStar's fog-of-war mask applied at input-construction time, not post-filter.

**Strengths of BookRAG's approach vs alternatives:**
- Single monotonic cursor is simpler than bi-temporal reasoning — no contradiction resolution needed because the underlying text is immutable.
- Pre-stamped `source_chunk_ordinal` per node means filtering is O(nodes) with no query-time graph traversal — cheaper than Zep's edge-invalidation walks.
- Per-identity snapshot selection (BookRAG Phase 2) gives the *latest visible* view, analogous to Zep's "valid-at-T" reads, without bi-temporal overhead.
- Works against any graph DB (Kuzu, Neo4j, LanceDB) because the filter is a property predicate, not a DB feature.

**Weaknesses / gaps (what BookRAG is not doing that TKG literature would suggest):**
- No validity intervals — only a single `first_chapter`/`last_known_chapter`. A character's state in chapter 5 may differ from chapter 2, but retrieval currently picks "latest ≤ cursor" rather than surfacing the full temporal trajectory.
- No forecasting training signal — TKG models like RE-NET / CyGNet are trained to *predict the next timestep*, which could be repurposed as a spoiler-safety test (can the system predict chapter N+1? if yes, the cursor is leaking).
- No per-character knowledge tracking (theory-of-mind layer) — BookRAG gates by reader progress, not by "what does character X know at chapter N." FANToM-style belief tracking would unlock per-character dialogue grounding.
- No bi-temporal model — re-extractions or corrections to the KG aren't versioned against `transaction_time`.
- No native DB-level "AS OF chapter N" — all filtering is application-side. TerminusDB-style time-travel would simplify the spoiler_filter code.

**Open research questions BookRAG could contribute to:**
1. Is there a retrieval task formalism that generalizes "wall-clock valid time" and "reader-progress valid time" under one umbrella (perhaps "consumer-progress TKG")?
2. Can forecasting-style TKG training (predict chapter N+1 from ≤ N) serve as an automated spoiler-leakage detector for an ingested KG?
3. How should per-character belief states be layered on top of a reader-progress KG so the system can answer "what does Cratchit know about Scrooge at the end of chapter 3?" distinct from "what does the reader know?"
4. For episodic/serialized content (TV, serialized fiction, webcomics), does a multi-cursor model (per-title, per-reader) outperform single-cursor baselines on spoiler-avoidance recsys?
5. Can bi-temporal graph engines (Zep/Graphiti, TerminusDB) be repurposed as a general substrate for progress-gated retrieval, with `valid_from = source_chunk_ordinal`?

**Key citations:**
1. Cai et al. (2024) — *A Survey on Temporal Knowledge Graph: Representation Learning and Applications*, arXiv 2403.04782.
2. Cai et al. (2023) — *Temporal Knowledge Graph Completion: A Survey*, IJCAI 2023 / arXiv 2201.08236.
3. Lacroix et al. (2020) — *Tensor Decompositions for Temporal Knowledge Base Completion* (TComplEx), ICLR 2020.
4. Han et al. (2021) — *xERTE: Explainable Subgraph Reasoning for Forecasting on Temporal Knowledge Graphs*, ICLR 2021.
5. Liu et al. (2022) — *TLogic: Temporal Logical Rules for Explainable Link Forecasting*, AAAI 2022 / arXiv 2112.08025.
6. Gastinger et al. (2024) — *History Repeats Itself: A Baseline for Temporal KG Forecasting*, arXiv 2404.16726.
7. T-GRAG (2025) — *A Dynamic GraphRAG Framework for Resolving Temporal Conflicts*, arXiv 2508.01680.
8. TG-RAG / STAR-RAG (2025) — arXiv 2510.13590 and 2510.16715.
9. Chen et al. (2021) — *TimeQA: A Dataset for Answering Time-Sensitive Questions*, NeurIPS Datasets 2021. TempReason: Tan et al. (2023), ACL 2023.
10. Guo et al. (2024) — *LightRAG: Simple and Fast Retrieval-Augmented Generation*, EMNLP 2025 / arXiv 2410.05779.
11. Vinyals et al. (2019) — *Grandmaster level in StarCraft II using multi-agent reinforcement learning* (AlphaStar), Nature 575.
12. Park et al. (2023) — *Generative Agents: Interactive Simulacra of Human Behavior*, UIST 2023 / arXiv 2304.03442.
13. Packer et al. (2023) — *MemGPT: Towards LLMs as Operating Systems*, arXiv 2310.08560.
14. Xu et al. (2025) — *A-MEM: Agentic Memory for LLM Agents*, arXiv 2502.12110. HippoRAG: Gutiérrez et al. (NeurIPS 2024).
15. Rasmussen et al. (2025) — *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, arXiv 2501.13956.
16. Kim et al. (2023) — *FANToM: A Benchmark for Stress-testing Machine Theory of Mind in Interactions*, EMNLP 2023 / arXiv 2310.15421.
17. Wan, Misra, Nakashole, McAuley (2019) — *Fine-Grained Spoiler Detection from Large-Scale Review Corpora*, ACL 2019 / arXiv 1905.13416.
18. Fröbe et al. (2023) — *SemEval-2023 Task 5: Clickbait Spoiling*, SemEval 2023. Neo4j temporal versioning: Cypher Manual temporal values docs. Bitemporal property graphs: Erb et al., arXiv 2111.13499.

**Concrete ideas worth stealing for BookRAG:**
- **Adopt Graphiti/Zep's bi-temporal edge model** (`valid_from_chunk`, `valid_to_chunk`, `created_at_transaction`, `invalidated_at_transaction`) so re-extractions version cleanly and the "latest-per-identity snapshot" becomes a native `AS OF cursor` read rather than a filter loop.
- **Forecasting-style spoiler-leakage test:** train a small RE-NET/CyGNet over `(s, p, o, chapter)` quadruples and measure whether ground-truth chapter N+1 facts can be predicted from the ≤ N slice. Nonzero predictability = KG is leaking future structure that a clever LLM could also extract.
- **Validity intervals instead of single-timestamp snapshots:** record both `first_chapter` (already present) and `last_unchanged_chapter` so queries can return "state during chapter 2-4" vs "state starting chapter 5" — captures trajectory, not just latest.
- **Theory-of-mind layer (FANToM-inspired):** augment each Character node with `known_facts_by_chapter[chapter] -> set[fact_id]`. Enables per-character dialogue grounding ("how would Cratchit answer this in chapter 3?") distinct from reader-level spoiler gating.
- **Borrow AlphaStar's mask-at-input-construction discipline:** BookRAG already does this; formalize it as a design invariant in the docs ("no filtered node may influence the LLM context, even via embeddings of allowed nodes").
- **McAuley-style spoiler classifier as a safety net:** run a spoiler-detection LLM pass on generated answers as a belt-and-braces check that the cursor filter didn't miss anything through LLM inference chains.
- **Chunk-ordinal → valid-time isomorphism:** publish BookRAG as the reference implementation of "consumer-progress-gated RAG" and frame it as a TKG with a monotonic discrete timeline, inviting the TKG community to evaluate their methods in this setting.


### 11. Entity resolution & coreference at book scale

**Researched:** 2026-04-22 (iteration 11)

**TL;DR:** Book-scale ER is the intersection of two well-studied but rarely-combined problems: long-document coreference (BOOKCOREF, ACL 2025 [1]) and record linkage ER (Ditto [2], AnyMatch [3]). BookRAG's alias fragmentation ("Bob", "Mr. Cratchit", "Bob Cratchit" as three nodes) is a classic cluster-edit problem solvable in the near term by a post-extraction HAC pass with an LLM pairwise oracle over embedding-retrieved candidates, modeled on ComEM [4] and neo4j-graphrag's resolver architecture [5]. The longer arc is a fiction-tuned bi-encoder trained on LitBank [6] aliases plus BookNLP clusters [7].

**Classical ER techniques.** Deterministic exact match, Levenshtein/Jaro-Winkler edit distance, token-sort ratio, and Soundex/Metaphone phonetic keys form the baseline every ER system starts from [8]. They excel on typo-level variance ("Scroogee" vs "Scrooge") but fail on the characteristic fiction patterns: nicknames with zero string overlap ("Bob" vs "Robert"), honorifics that add tokens ("Mr. Cratchit" vs "Bob"), definite-description epithets ("the old miser" vs "Scrooge"), and kinship references ("Tiny Tim's mother" vs "Mrs. Cratchit"). RapidFuzz-backed fuzzy match — which is what `neo4j-graphrag`'s `FuzzyMatchResolver` uses [5] — merges "Bob Cratchit"↔"Robert Cratchit" but cannot collapse "Bob"↔"Robert" without a nickname dictionary or semantic signal.

**Modern embedding-based ER.** Ditto (VLDB 2021 [2]) fine-tunes BERT/RoBERTa as a sequence-pair classifier over serialized records and adds three tricks: domain-knowledge injection, long-string summarization, and MixDA-style augmentation, yielding +29% F1 over pre-LM SOTA on ER-Magellan's 13 datasets and WDC product matching. Sentence-transformers / SBERT encoders plus cosine similarity are the lightweight drop-in used by `SpaCySemanticMatchResolver` [5]. The Abt-Buy / DBLP-ACM / Walmart-Amazon benchmarks are structured-record oriented, so fiction transfer is imperfect — but the recipe ("pretrain, fine-tune on labeled pairs, serialize attributes") maps directly onto a Character DataPoint with `name|aliases|description|chapter`.

**LLM-based ER.** Narayan et al.'s "Can Foundation Models Wrangle Your Data" (VLDB 2022 [9]) showed GPT-3 few-shot beats Ditto on 4/7 datasets with zero labeled data, proposing ZEROMATCH. AnyMatch (2024 [3]) fine-tunes a GPT-2-sized model to within 4.4% of MatchGPT/GPT-4 quality at 3,899× lower cost — the pragmatic local-model option. "Match, Compare, or Select?" / ComEM (COLING 2025 [4]) shows that the "select best from candidates" framing beats pure pairwise matching because LLMs exploit global consistency across candidates; their 3-stage compound pipeline (cheap matcher → comparison → selection) is cost-effective and the right architectural template. ERBench (NeurIPS 2024 [10]) is the current hallucination-aware LLM-ER benchmark but targets relational integrity constraints, not fiction.

**Cross-document coreference (CDCR).** Cattan et al. (2020/2021 [11]) formalized end-to-end CDCR on ECB+ using agglomerative clustering over mention embeddings — directly relevant because BookRAG's batch-level extraction is effectively a multi-document problem (each batch is a "document" and the same character recurs across them). WEC-Eng (Eirew/Cattan/Dagan, NAACL 2021 [12]) is the large-scale Wikipedia-derived CDCR benchmark. Contrastive dual-encoder CDCR (Caciularu et al. [13]) is the method-of-choice when mention pools are large, and maps onto BookRAG's "re-score all Character nodes from batches 1..N" workflow.

**Long-document coreference (book-length).** BOOKCOREF (ACL 2025 [1]) is the decisive benchmark: average document length >200k tokens, gold test split + silver train/val built by a semi-automatic pipeline, released on HuggingFace (`sapienzanlp/bookcoref`). Result worth stealing: systems fine-tuned on book-scale data gain up to +20 CoNLL-F1 over the same architecture trained on OntoNotes/LitBank. LingMess (Otmazgin/Cattan, [14]) pairs a per-category scorer with Longformer-large to hit 81.4 F1 on OntoNotes and processes 4k tokens/chunk — the most plug-and-play long-doc coref model today, and supersedes `maverick-coref` in raw accuracy for English. xCoRe (EMNLP 2025 [15]) extends this into cross-context (within+across document) in one framework.

**Narrative-specific alias challenges.** Christmas Carol has "Scrooge" / "Ebenezer" / "the old miser" / "Uncle" (spoken by Fred); Bob Cratchit appears as "Bob" / "Cratchit" / "Mr. Cratchit" / "the clerk" / "Tiny Tim's father". Red Rising has "Darrow" / "Darrow of Lykos" / "Reaper" / "The Reaper of Mars" / "Helldiver" plus deliberate identity substitution (the Carving → "Darrow au Andromedus" as a Gold). Delayed-identity reveals ("two characters revealed to be one") is explicitly called out by LitBank as a literary-coref challenge [6]. BookRAG's spoiler filter has an additional constraint: **a merge may itself be a spoiler** (unifying "the stranger" and "Scrooge's dead partner" before the reader learns it). Any ER pass must therefore gate merges by the `effective_latest_chapter` at which the identity is *textually confirmed*, not just co-referred.

**BookNLP's alias clustering.** BookNLP performs character name clustering as a pipeline step *before* pronominal coref [7]: it groups `{Tom, Tom Sawyer, Mr. Sawyer, Thomas Sawyer}` into a single `TOM_SAWYER` entity using honorific stripping + last-name matching, then allows pronouns to bind to named or common entities (but disallows common→named). BookRAG already ingests BookNLP `.entities` output but does not propagate the character cluster ID into Cognee DataPoint identity — this is a ~1-day integration gap that would eliminate a large fraction of current fragmentation without any LLM calls.

**Character-focused resolution systems.** LitBank (Bamman et al., LREC 2020 [6]) is 210k tokens / 29k mentions across 100 novels, 4× longer documents than OntoNotes, and is the standard fine-tuning corpus for fiction coref. "Fictional Character Embeddings for Quotation Attribution" (ACL 2024 [16]) trains character-specific embeddings that could be repurposed as ER vectors. KoCoNovel [17] extends the pattern to Korean novels. There is still no "character identification" QA benchmark that tests alias-aware retrieval end-to-end — a gap BookRAG could help fill.

**Cluster-edit vs single-pass ER architectures.** Single-pass: score each new mention against all existing clusters, assign to argmax or create new (O(N·K) per mention). Cluster-edit / HAC: build affinity matrix over all mentions and iteratively merge (O(N²) pairs but only O(N log N) merges with priority queue). Cattan 2020 [11] and most CDCR systems use HAC with a learned pairwise scorer. An LLM pairwise oracle (Ditto-style or ComEM-select [4]) is too expensive for full O(N²) but is tractable as a **second-stage re-ranker over top-k embedding candidates** — the standard pattern is bi-encoder retrieval + cross-encoder re-rank + HAC with a confidence threshold.

**Strengths / weaknesses for BookRAG:**
- Strength: Cognee DataPoints already carry `name`, `aliases`, `description`, `first_chapter` — every field an ER system needs.
- Strength: BookNLP is already in the pipeline and already produces alias clusters that are largely thrown away downstream.
- Weakness: per-batch extraction means the same entity is re-described N times with drift; without ER, node count grows linearly with batch count.
- Weakness: "merge as spoiler" constraint has no direct analogue in standard ER literature — novel problem, requires bespoke gating.

**Concrete 2-hour BookRAG upgrade — `resolve_aliases` stage between `run_cognee_batches` and `validate`:**

```python
# pipeline/alias_resolver.py
def resolve_aliases(book_id: str, threshold: float = 0.82) -> dict[str, str]:
    chars = load_all_character_datapoints(book_id)        # across batches
    # 1) cheap bucket by BookNLP cluster_id (if present on the mention)
    buckets = group_by_booknlp_cluster(chars)
    # 2) within each bucket, HAC with SBERT(name + top-alias) affinity
    embeddings = sbert.encode([c.name + " | " + "; ".join(c.aliases) for c in chars])
    candidate_pairs = topk_cosine_pairs(embeddings, k=10, min_sim=0.6)
    # 3) LLM pairwise oracle only on ambiguous pairs (ComEM-select prompt)
    merges = {}
    for (i, j) in candidate_pairs:
        if same_booknlp_cluster(chars[i], chars[j]):
            merges[chars[j].id] = chars[i].id; continue
        if cosine(emb[i], emb[j]) > 0.92:       # high-confidence auto-merge
            merges[chars[j].id] = chars[i].id; continue
        if llm_are_same_character(chars[i], chars[j], context):
            # SPOILER GATE: only merge if both identities are textually
            # confirmed by the earlier node's effective_latest_chapter
            if confirmed_before(chars[j], chars[i].effective_latest_chapter):
                merges[chars[j].id] = chars[i].id
    return merges  # applied by rewriting batch JSON + re-loading allowlist
```

This is ~150 LOC, adds one SBERT model and ~N² / bucket_size LLM calls (typically <200 per book), and directly mirrors `neo4j-graphrag`'s resolver interface [5] (swap `SinglePropertyExactMatch` → `CompoundResolver`). Drop-in benchmark: count `{Character}` nodes before/after on Christmas Carol; target is ~10-15 characters, not the ~30-40 fragmented nodes current runs produce.

**Longer-term path.** Fine-tune a bi-encoder on LitBank [6] alias clusters augmented with synthetic nickname/honorific/epithet perturbations (Faker + rule-based "Mr./Dr./Lord X" templates, plus GPT-generated epithets). Train with contrastive loss (same-cluster positive, different-cluster negative). This replaces the SBERT step and the LLM oracle in the recipe above, bringing per-book ER cost to ~0. Evaluation: BOOKCOREF [1] gold test + the ERBench [10] rationale-verification framing adapted to fiction.

**Key citations:**
1. Martinelli, Bonomo et al. 2025. *BOOKCOREF: Coreference Resolution at Book Scale.* ACL. <https://aclanthology.org/2025.acl-long.1197/>
2. Li, Li et al. 2021. *Deep Entity Matching with Pre-Trained Language Models (Ditto).* VLDB. <https://arxiv.org/abs/2004.00584>
3. Zhang et al. 2024. *AnyMatch — Efficient Zero-Shot Entity Matching with a Small Language Model.* <https://arxiv.org/abs/2409.04073>
4. Wang et al. 2025. *Match, Compare, or Select? (ComEM).* COLING. <https://arxiv.org/abs/2405.16884>
5. Neo4j. *neo4j-graphrag-python resolver module.* <https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html>
6. Bamman, Lewke, Mansoor. 2020. *An Annotated Dataset of Coreference in English Literature (LitBank).* LREC. <https://arxiv.org/abs/1912.01140>
7. Bamman et al. *BookNLP.* <https://github.com/booknlp/booknlp>
8. Christen. 2012. *Data Matching: Concepts and Techniques for Record Linkage.* Springer.
9. Narayan et al. 2022. *Can Foundation Models Wrangle Your Data?* VLDB 2023. <https://arxiv.org/abs/2205.09911>
10. Oh et al. 2024. *ERBench.* NeurIPS D&B. <https://arxiv.org/abs/2403.05266>
11. Cattan et al. 2020/2021. *Streamlining Cross-Document Coreference Resolution.* <https://arxiv.org/abs/2009.11032>
12. Eirew, Cattan, Dagan. 2021. *WEC: Wikipedia Event Coreference.* NAACL.
13. Caciularu et al. 2021. *Cross-Document Language Modeling (CDLM).*
14. Otmazgin, Cattan, Goldberg. 2023. *LingMess: Linguistically Informed Multi Expert Scorers.* EACL. <https://huggingface.co/biu-nlp/lingmess-coref>
15. *xCoRe: Cross-context Coreference Resolution.* EMNLP 2025. <https://aclanthology.org/2025.emnlp-main.1737.pdf>
16. *Improving Quotation Attribution with Fictional Character Embeddings.* ACL 2024. <https://arxiv.org/abs/2406.11368>
17. *KoCoNovel.* 2024. <https://arxiv.org/abs/2404.01140>

**Concrete ideas worth stealing for BookRAG:**
- **Propagate BookNLP `cluster_id` into Cognee Character DataPoints** — cheapest high-leverage change; eliminates within-cluster fragmentation pre-LLM.
- **Adopt `neo4j-graphrag` resolver interface** verbatim (`Resolver.run(nodes) -> merges`) so future resolvers compose cleanly.
- **Two-stage ER: SBERT bi-encoder retrieval → LLM pairwise oracle** (Ditto/ComEM pattern) as a pipeline stage after `run_cognee_batches`, before `validate`.
- **Spoiler-aware merge gate:** no merge unless the textual confirmation of the identity happens at-or-before the earlier node's `effective_latest_chapter` — the unique BookRAG twist on standard ER.
- **Evaluate on BOOKCOREF gold split** for book-scale coref correctness; report CoNLL-F1 alongside current validation metrics.
- **Fine-tune LingMess-Longformer on BookCorefsilver** as an optional "deep coref" pipeline stage for Phase 1, replacing BookNLP coref where accuracy matters more than speed.
- **Nickname/honorific/epithet synthetic augmentation** for a fiction-tuned bi-encoder — mirrors Ditto's MixDA recipe specifically for narrative text.
- **ComEM "select from candidates" prompt** beats pairwise for LLM ER — adopt this exact prompt shape for the oracle step.
- **Record merge provenance** (`merged_from: [node_ids]`, `merge_source: booknlp|sbert|llm`, `merge_chapter: N`) so the graph explainer can show "these two were unified in chapter 4 because the narrator said 'and that man was Scrooge'".

### 12. Plot event extraction & narrative schema induction

**Researched:** 2026-04-22 (iteration 12)

**TL;DR:** Event extraction has ~20 years of scaffolding (ACE/ERE triggers + arguments, PropBank/FrameNet roles, TempEval/MATRES temporal links, Chambers–Jurafsky narrative chains), and in 2023–2025 has largely been absorbed into LLM prompting (CODE4STRUCT, instruction-tuned extractors, multi-agent debate) benchmarked on TextEE. For fiction specifically, LitBank's literary-event annotations and Reagan et al.'s emotional arcs remain the only book-scale anchors; almost everything else is news-domain. BookRAG's `PlotEvent` is a generic LLM-emitted blob with no trigger/argument structure, no causal or temporal edges, and no schema clustering — the low-hanging fruit is (a) argument roles (agent/patient/location/time), (b) a second pass that emits `causes`/`before`/`enables` edges between PlotEvents, and (c) post-hoc clustering of events into narrative schemas for thematic retrieval.

**Event extraction basics.** In NLP a typical event is a *trigger* (usually a verb or eventive noun, e.g. "stabbed") plus a set of *arguments* filling typed roles. ACE 2005 defined 33 event subtypes with roles like Attacker/Target/Instrument; ERE and RAMS extended this; PropBank annotates verb-specific numbered roles (ARG0/ARG1…) and FrameNet organizes them into semantic frames (Killing: Killer, Victim, Instrument, Place). Events are distinguished from *states* (stative predicates, not annotated as events in ACE) and *relations* (time-invariant). LitBank (Sims, Park, Bamman ACL 2019) adapted this for fiction by annotating only *realis* events — things depicted as actually happening in the imagined world, excluding hypotheticals, generics, and narrator summary — and showed BERT+BiLSTM reaches F1 ~73.9 on that tag [4].

**Classical narrative schema induction.** Chambers & Jurafsky (ACL 2008) introduced *narrative event chains*: partially ordered sequences of events sharing a *protagonist* (a common coreferring argument) [1]. Their unsupervised recipe was: (1) parse + coref, (2) for every verb pair sharing an argument, compute pointwise mutual information of (verb, dependency-slot), (3) greedily build chains around a protagonist, (4) learn a partial order via a temporal classifier. Evaluated with the "narrative cloze" (predict a held-out verb from the chain). Pichotta & Mooney (AAAI 2016, ACL 2016) replaced PMI with LSTM language models over multi-argument event tuples and reported +22–65% relative improvements on cloze [8]. Rudinger et al. and others showed cloze is gameable by vocabulary frequency — progress has mostly moved to neural script induction and story-generation evals.

**Modern event extraction systems.** DyGIE++ (Wadden et al. EMNLP 2019) does joint NER + relation + event extraction over BERT-encoded spans with a dynamic span graph; OneIE (Lin et al. ACL 2020) adds global features and decodes the whole IE graph jointly, beating DyGIE++ on ACE05-E. DEGREE reformulates event extraction as conditional generation. TextEE (Huang et al. Findings of ACL 2024) is the current reproducibility benchmark: 16 datasets, 8 domains, 14 methods, standardized splits — and the headline finding is that even GPT-4-class LLMs underperform tuned specialists [3].

**LLM-based event extraction.** Three dominant patterns: (a) natural-language prompting with schema in context (Wang et al. 2023, ChatIE); (b) code-as-schema — CODE4STRUCT / CodeIE (ACL 2023) render the event schema as a Python class and the LLM emits an instantiation, leveraging inheritance and type hints to inject constraints [5]; (c) instruction tuning on annotation guidelines (2025 follow-ups). Multi-agent debate frameworks (DAO 2025; "Extracting Events Like Code" 2025) narrow the gap to supervised on ACE05 without fine-tuning. Key caveat from TextEE: LLMs still struggle with rare event types and long documents.

**Event coreference.** Two subtasks: within-document (Kenyon-Dean et al. 2018) and cross-document. ECB+ (Cybulska & Vossen 2014) is the canonical cross-doc benchmark — 982 news articles, 43 topics, annotated with within- and cross-document event + entity coref [6]. Recent work (Cattan et al., CDLM, X-AMR linear decoder, "Okay Let's Do This!" 2024) uses Longformer or rationale-generating LLMs. For fiction, event coref matters because the same kill/betrayal/reveal is described in flashbacks, gossip, and direct narration — today BookRAG treats each mention as a new PlotEvent.

**Narrative schema in the LLM era.** Post-GPT-4, pure cloze prediction is uninteresting (LMs trivially solve it). Publishable work has shifted to: (a) evaluating whether LLMs internalize *schemas* vs. memorize surface strings (probing tasks); (b) using LLMs to *induce* schemas from small corpora and then testing them on held-out stories; (c) story-generation as a downstream test of schema fidelity [9]. The 7th Workshop on Narrative Understanding (2025) is the current venue.

**Temporal ordering.** TempEval-3 (SemEval 2013) evaluates event + timex + temporal-relation extraction on TimeBank/AQUAINT/Platinum [10]. MATRES (Ning et al. NAACL 2018) cleans this up by annotating temporal relations only between event *start-points* on a multi-axis scheme, yielding higher IAA [11]. Relation labels are typically {before, after, equal, vague} or the 13 Allen intervals. For fiction: narrative order ≠ fabula order — flashbacks, prolepsis/foreshadowing, and unreliable narration break monotonicity. Han et al. and Zhou et al. have shown LLMs do reasonable temporal ordering on news but degrade on narrative with non-linear discourse.

**Causal event extraction.** CausalTimeBank extends TimeBank with CLINK causal edges; BECauSE 2.0 labels 1,803 causal instances across WSJ/NYT/PTB; CaTeRS annotates 320 ROCStories with 13 causal+temporal relation types tailored to narrative [12]. The 2025 survey *A Survey of Event Causality Identification* (ACM Computing Surveys) catalogs the taxonomy. Fiction-specific: discourse connectives ("and then", "but", "because", "so that"), purpose clauses, and character-motivation inference (A did X because A wanted Y) — the last folds into commonsense reasoning territory.

**Story arc / narrative structure detection.** Classical templates: Propp's 31 functions (Russian folktales), Campbell's monomyth, Freytag's 5-act pyramid. Computational: Reagan et al. *The emotional arcs of stories are dominated by six basic shapes* (EPJ Data Sci. 2016) applied SVD + hierarchical clustering to sentiment time-series over 1,327 Gutenberg fiction works and recovered six canonical shapes (Rags-to-Riches, Tragedy, Man-in-Hole, Icarus, Cinderella, Oedipus) [7]. Saldías & Roy, and subsequent "narrative-arc embeddings" work, extend this with neural sentiment models.

**Character motivation and goal extraction.** Rashkin et al. *Modeling Naive Psychology of Characters in Simple Commonsense Stories* (ACL 2018) annotates chains of mental states — *motivations* (Maslow/Reiss categories) and *emotional reactions* (Plutchik) — per character per sentence on ROCStories [13]. ATOMIC (Sap et al. AAAI 2019) scales this to 877k if-then tuples across 9 relation types (xIntent, xReact, xWant, oEffect, …) and COMET trains a transformer to generate them [14]. These supply the "why did they do that" layer a plain event extractor misses.

**Event → KG mapping.** A single event like "Scrooge refused Fred's dinner invitation on Christmas Eve at the counting-house" decomposes into: trigger = *refuse*, agent = Scrooge, theme = invitation, beneficiary = Fred, time = Christmas Eve, location = counting-house. In a KG this becomes a PlotEvent node with typed edges to Character/Location/TimeExpression nodes, each edge labeled by the role (PropBank: ARG0/ARG1; FrameNet: Refusing frame roles). Hypergraphs and n-ary relation encodings (Wikidata qualifiers, RDF reification) are the two common patterns; most LLM-extraction pipelines flatten to binary edges with a role label.

**Strengths / weaknesses of BookRAG's current PlotEvent.**
- Strength: LLM extraction captures long-range context within a batch; `chapter` field supports spoiler gating; description is human-readable.
- Weakness: no trigger/argument distinction — the event is just a prose blurb, so the graph can't answer "who did this to whom".
- Weakness: no typed edges to participants — Character→PlotEvent participation is implicit in the description text.
- Weakness: no temporal ordering beyond chapter number; no within-chapter sequence.
- Weakness: no causal or enabling edges (`caused_by`, `enables`, `motivated_by`).
- Weakness: no event coref — the same event narrated in two batches produces two unlinked PlotEvents.
- Weakness: no clustering/schema layer — can't retrieve "betrayal events" or "death events" thematically.

**Concrete upgrade proposals.**
1. **Add structured arguments to `PlotEvent`** (small scope, ~1 slice). Extend the DataPoint with `agents: list[Character]`, `patients: list[Character]`, `location: Location | None`, `instrument: str | None`, `time_expression: str | None`, and a `trigger_verb: str` (lemma). Update the Cognee extraction prompt to fill these explicitly. Gives the KG typed edges for free via Cognee's relation DataPoints.
2. **Second-pass temporal + causal linking** (medium scope). After `run_cognee_batches`, run a new stage `link_events` that, for each pair of PlotEvents within a sliding window of ±2 chapters, asks an LLM to emit one of {before, after, overlaps, causes, caused_by, enables, none} with a confidence score. Store as `PlotEvent.temporal_before: list[PlotEvent]` and `PlotEvent.causes: list[PlotEvent]`. Prompt-engineer for narrative (flashback handling) by including the surrounding chapter text. Budget: O(n²) pairs per book; on 100 events that's 10k LLM calls — feasible at gpt-4o-mini rates. Cheaper variant: only link events sharing a Character argument (Chambers–Jurafsky protagonist heuristic) → O(n·k) with k≈5.
3. **Narrative-schema clustering for thematic retrieval** (medium scope). Embed each PlotEvent (trigger + argument roles, SBERT), cluster with BERTopic or HDBSCAN, label clusters with an LLM ("deception", "reconciliation", "loss"), and store as a `NarrativeSchema` DataPoint that many PlotEvents point to. Query API gains a `/books/{id}/schemas` endpoint and chat can answer "what are the major themes so far" purely from schema cluster labels (spoiler-safe because clusters are filtered by the same chapter bound).
4. **Event coreference pass** (larger scope, optional). After extraction, run LingMess-event or a lightweight LLM pairwise classifier to merge PlotEvents describing the same fabula event across different narration points (direct vs. recollection vs. foreshadowing). Needed before any faithful temporal ordering.
5. **Emotional-arc overlay** (small scope, decorative). Compute VADER/finetuned sentiment per paragraph, surface the six-shape classification (Reagan et al.) as book-level metadata, and let the reader see "you are near the midpoint dip of a Man-in-Hole arc" without spoilers. Purely additive.

**Key citations:**
1. Chambers & Jurafsky. 2008. *Unsupervised Learning of Narrative Event Chains.* ACL. <https://aclanthology.org/P08-1090/>
2. Wadden et al. 2019. *Entity, Relation, and Event Extraction with Contextualized Span Representations (DyGIE++).* <https://arxiv.org/abs/1909.03546>
3. Huang et al. 2024. *TextEE: Benchmark, Reevaluation, Reflections, and Future Challenges in Event Extraction.* Findings of ACL. <https://aclanthology.org/2024.findings-acl.760/>
4. Sims, Park, Bamman. 2019. *Literary Event Detection.* ACL. <https://aclanthology.org/P19-1353/>
5. Wang, Li, Ji. 2023. *CODE4STRUCT: Code Generation for Few-Shot Event Structure Prediction.* <https://aclanthology.org/2023.acl-long.855.pdf> (and CodeIE, ACL 2023)
6. Cybulska & Vossen. 2014. *Using a sledgehammer to crack a nut? Lexical diversity and event coreference resolution (ECB+).* LREC.
7. Reagan, Mitchell, Kiley, Danforth, Dodds. 2016. *The emotional arcs of stories are dominated by six basic shapes.* EPJ Data Science 5:31. <https://link.springer.com/article/10.1140/epjds/s13688-016-0093-1>
8. Pichotta & Mooney. 2016. *Learning Statistical Scripts with LSTM Recurrent Neural Networks.* AAAI. <https://www.cs.utexas.edu/~ml/papers/pichotta.aaai16.pdf>
9. *Proceedings of the 7th Workshop on Narrative Understanding.* ACL 2025. <https://aclanthology.org/volumes/2025.wnu-1/>
10. UzZaman et al. 2013. *SemEval-2013 Task 1: TempEval-3.*
11. Ning, Wu, Roth. 2018. *A Multi-Axis Annotation Scheme for Event Temporal Relations (MATRES).* NAACL. <https://cogcomp.github.io/MATRES/>
12. Mostafazadeh et al. 2016. *CaTeRS: Causal and Temporal Relation Scheme for Semantic Annotation of Event Structures.*
13. Rashkin, Bosselut, Sap, Knight, Choi. 2018. *Modeling Naive Psychology of Characters in Simple Commonsense Stories.* ACL. <https://arxiv.org/abs/1805.06533>
14. Sap et al. 2019. *ATOMIC: An Atlas of Machine Commonsense for If-Then Reasoning.* AAAI. <https://arxiv.org/abs/1811.00146>
15. Lin, Ji, Huang, Wu. 2020. *A Joint Neural Model for Information Extraction with Global Features (OneIE).* ACL.
16. *A Survey of Event Causality Identification: Taxonomy, Challenges, Assessment, and Prospects.* ACM Computing Surveys 2025.

**Concrete ideas worth stealing for BookRAG:**
- **Argument roles first** — extending `PlotEvent` with explicit agent/patient/location/time slots (PropBank-style) is the single highest-leverage change; it turns every event from an opaque blurb into a structured subgraph with typed participation edges, at zero extra LLM calls (same prompt, richer schema).
- **CODE4STRUCT-style prompting** — render the event schema as a Pydantic class in the prompt; LLMs emit higher-fidelity structured events when the schema is code, not prose.
- **Chambers–Jurafsky protagonist heuristic for O(n·k) event linking** — only consider temporal/causal edges between events sharing a Character argument; prunes pair-space without losing narrative chains.
- **Post-extraction schema clustering** (BERTopic on event embeddings) yields a thematic retrieval layer ("show me all betrayals up to chapter 10") that today's string-match queries can't serve.
- **Realis filter from LitBank** — only extract events depicted as actually happening in the story world; drop hypotheticals, generics, narrator asides. Cleans the graph dramatically on literary fiction.
- **Emotional-arc classification per book** (Reagan six shapes) as free metadata for the reader UI — no spoiler risk since the shape is computed globally but revealed progressively.
- **Event coref via LLM pairwise on cross-chapter mentions** — use the same ComEM "select from candidates" prompt pattern discussed in iteration 11, but over PlotEvent descriptions, to merge narration duplicates before temporal linking.
- **Store ATOMIC-style motivation edges** (`motivated_by: str`) on each PlotEvent so the chat can answer "why did Scrooge refuse?" with text grounded in the extracted intent, not generic LLM commonsense.
- **Narrative-cloze as a validation metric** — hold out one PlotEvent per chain, ask the LLM to predict it from context, log accuracy over time to detect extraction regressions.

### 13. Character relationship networks in literature

**Researched:** 2026-04-22 (iteration 13)

**TL;DR:** Character networks — graphs whose nodes are characters and whose edges represent co-occurrence, conversation, or typed social relations — are a mature subfield with a definitive Labatut & Bost 2019 survey, but most published work stops at co-occurrence edges and un-typed/un-signed graphs. BookRAG's `Relationship` DataPoint already emits typed edges (a step past the literature's default) but lacks schema normalization, signed weights, and downstream graph metrics. The cheapest high-leverage upgrades are (a) a fixed typology (family / romantic / adversarial / professional / ideological), (b) signed edges from sentence-level sentiment, and (c) betweenness-based node attributes to rank retrieval candidates.

**Foundational work — character networks as co-occurrence graphs:**
Moretti's "Network Theory, Plot Analysis" [1] hand-drew Hamlet as a speech graph (Hamlet is at mean distance 1.45 from all vertices; removing him nearly bisects the network and exposes a "region of death" that only two edge-characters survive) and legitimized the approach in literary studies. Elson, Dames & McKeown's 2010 ACL paper [2] was the first automatic pipeline: name chunking + quotation attribution + conversation detection over 60 nineteenth-century British novels, with network features correlated against urban-vs-rural setting and third- vs first-person narration. Agarwal, Corvalan, Jensen & Rambow [3] built on this with *dynamic* social-event networks from Alice in Wonderland, showing static graphs systematically distort character importance. Sudhahar & Cristianini [4] abstracted the same pattern via SVO-triplet "semantic graphs" applied to narrative corpora.

**Labatut & Bost (CSUR 2019) comprehensive survey [5]:**
The definitive reference (40 pages, ACM Computing Surveys, also arXiv:1907.02704). Taxonomizes extraction by (i) interaction unit — co-occurrence window vs. conversation/dialogue vs. explicit action; (ii) edge polarity — unsigned vs. signed vs. typed; (iii) temporal granularity — static vs. dynamic/cumulative vs. sliding-window. Taxonomizes analysis by summarization, classification, role detection, information retrieval, recommendation. Open problems it flags: scarcity of gold-standard relation-type annotations, lack of agreed evaluation (most papers self-evaluate visually on a single novel), no canonical benchmark, and weak integration of textual semantics with graph metrics. Companion live bibliography at compnet.github.io/CharNetReview.

**Relationship-type classification:**
Beyond co-occurrence, the LLM era has produced typed extractors. Makris et al. [6] (ACL Findings 2024, "Understanding Complex Relationships in Detective Narratives") show GPT-4/Llama2 struggle on *Public / Secret / Inferred* relation categories — inferred relations (reader must deduce via chains) collapse to <40% F1 on long mysteries. An arXiv 2014 paper by Makazhanov et al. [7] "Extracting Family Relationship Networks from Novels" uses vocatives and utterance attribution (Pride and Prejudice) — a rule-based kinship extractor that predates modern LLMs but still outperforms naive prompting on fine-grained kin terms. WNU 2025 [8] ("Tracking Evolving Relationship Between Characters") benchmarks LLM extraction of relationship-type *changes* across a novel's arc.

**Dynamic character networks:**
Agarwal et al. [3] annotate social events per sentence and build per-scene graphs, showing centrality orderings that differ from static aggregates. Bost extended this to TV-series "dynamic conversational networks" (Springer 2018 chapter [5, ch. 3]). Typical encodings: (a) cumulative — add edges, never remove; (b) sliding window over scenes; (c) per-act/per-chapter snapshots that can be diffed. For BookRAG, per-batch snapshots are already a natural dynamic encoding.

**Graph-theoretic analysis:**
Degree centrality ranks protagonists crudely but inflates hub characters who only co-occur. Betweenness centrality is the standard protagonist/connector detector (Hamlet [1], Jean Valjean in Les Misérables), since it captures control over narrative information flow. Community detection (Louvain / Infomap) is the standard faction/party detector — Jayannavar et al. [9] ("Unsupervised cluster analyses of character networks in fiction," *Expert Systems with Applications*) find a reliable three-tier core/secondary/peripheral structure. Clustering coefficient and transitivity correlate with narrative "tightness" (ensemble casts vs. hub-and-spoke hero stories). Grayson et al. observe novels with male protagonists exhibit higher betweenness centralization than female-protagonist novels.

**Sentiment-weighted / signed networks:**
Nalisnick & Baird [10] (ACL 2013, "Character-to-Character Sentiment Analysis in Shakespeare's Plays") attach AFINN-weighted polarity to each directed speech act, then aggregate into signed edges. Signed structure distinguishes tragedies (denser negative edges, antagonist cliques) from comedies, and detects enemies/allies even without explicit relationship labels. Nonaka & Perry [11] (NeurIPS 2025 Workshop, arXiv:2510.18932) use signed character networks at *scale* (1,200 stories across GPT-4o / Gemini) as an LLM-evaluation axis — finding LLM-generated fiction is systematically biased toward dense positive cliques.

**Character embeddings:**
Inoue et al. [12] ("Learning and Evaluating Character Representations in Novels," ACL Findings 2022) compare (i) graph-neural-net embeddings over a corpus-wide character network vs. (ii) low-dimensional occurrence-pattern vectors, evaluated on coarse/fine character typing. Grayson et al.'s Novel2Vec [13] builds word-embedding-space representations of 19th-century characters via entity-annotated training. Hierarchical Char2Vec→Scene2Vec→Story2Vec (Bae et al.) extends to multimedia.

**Gender / power / demographic analysis:**
Fast, Vachovsky & Bernstein's "Shirtless and Dangerous" [14] (ICWSM 2016) extracted 42M (25M male / 17M female) subject-verb-object actions from 1.8B words of Wattpad fiction; male characters show higher action-verb agency, female characters are more often the subject of gaze verbs. The technique — SVO extraction keyed to gendered pronouns, lemmatized into verb-stereotype clusters — is directly portable to any character-typed corpus and the resulting "agency scores" can become node attributes.

**Relationship extraction benchmarks:**
No true "RELATIONSHIPS" dataset exists for fiction. Closest substitutes: **PDNC** (Project Dialogism Novel Corpus) [15] — 35,978 annotated quotations across 22 novels with speaker/addressee/referring-expression labels, which enables *dialogue-interaction* networks but not typed relationships. **LitBank** provides entities/events/coref but not relation types. Makazhanov's family-tree dataset [7] on Austen is a small kinship benchmark. The field-wide gap is a consistent, typed, multi-book relation benchmark with gold labels.

**Commercial / applied systems:**
LitCharts provides hand-curated character maps per book (relationships as editorial prose, no formal graph). SparkNotes and CliffsNotes similar. Character.AI exposes individual-character personas but not inter-character relation graphs. Goodreads stores book-level metadata only. The only consumer-facing automatic character-graph product visible from the HN thread and GitHub searches [16] is a hobbyist tool that dumps a whole book into Gemini/OpenAI and renders HTML/JS. No large-scale commercial product ships typed character networks today.

**Strengths / weaknesses for BookRAG's Relationship DataPoint:**
- Strengths: typed edges already extracted (ahead of co-occurrence-only literature); per-batch dynamic snapshots align with spoiler filter; Kuzu supports native graph queries (betweenness, community) out of the box.
- Weaknesses: (a) edge-type vocabulary drifts per batch (LLM proposes labels ad hoc — no normalization pass); (b) no sign / sentiment valence; (c) no downstream graph metrics computed or exposed; (d) no relationship-temporal-arc tracking (edge in batch N vs batch N+3 are not linked unless character identities resolve); (e) no evaluation benchmark.

**Concrete upgrades:**
a) **Signed edges at extraction time** — append a `valence: "positive" | "negative" | "neutral"` field to `Relationship` (one extra token in schema, ~zero cost); enables Nalisnick-style genre/antagonist detection and Nonaka-style bias diagnostics.
b) **Canonical relationship typology** — fix an enum (`familial`, `romantic`, `adversarial`, `alliance`, `professional`, `ideological`, `acquaintance`) in the Pydantic DataPoint and constrain the LLM via the schema; run a post-hoc mapping pass on existing books.
c) **Centrality as node attribute** — compute degree/betweenness/closeness per chapter bound (the spoiler filter already walks allowed nodes) and cache on Character nodes. Use betweenness as a tiebreaker when ranking retrieval candidates: "most connected characters first."
d) **Relationship temporal arc** — after per-identity snapshot selection (already shipped), diff successive `Relationship` descriptions for the same (subject, object) pair and emit a `RelationshipArc` summary ("allies in ch. 3, adversaries by ch. 12") — a natural answer to "how did X and Y's relationship change?"
e) **Community detection as faction discovery** — run Louvain on the `Character`-subgraph at each chapter bound; promote communities to candidate `Faction` nodes when no explicit faction was extracted. This catches the case where an author never names the faction but the social structure is obvious.
f) **Fast-style agency scores** — SVO extraction already implicit in BookNLP output; aggregate action verbs per character as `agency_score` / `passivity_score` attributes, useful for reader-facing "who are the active characters in chapters you've read?" retrieval.

**Key citations:**
1. Moretti, F. 2011. *Network Theory, Plot Analysis.* New Left Review 68. Stanford Literary Lab Pamphlet 2.
2. Elson, D., Dames, N., McKeown, K. 2010. *Extracting Social Networks from Literary Fiction.* ACL, pp. 138–147.
3. Agarwal, A., Corvalan, A., Jensen, J., Rambow, O. 2012. *Social Network Analysis of Alice in Wonderland.* NAACL-HLT CLfL Workshop.
4. Sudhahar, S., Cristianini, N. 2011–2015. *Automated Quantitative Narrative Analysis.* PhD thesis + Sage Big Data & Society.
5. Labatut, V., Bost, X. 2019. *Extraction and Analysis of Fictional Character Networks: A Survey.* ACM Computing Surveys 52(5) art. 89. arXiv:1907.02704.
6. (ACL Findings 2024) *Large Language Models Fall Short: Understanding Complex Relationships in Detective Narratives.* arXiv:2402.11051.
7. Makazhanov, A. et al. 2014. *Extracting Family Relationship Networks from Novels.* arXiv:1405.0603.
8. (WNU 2025 Workshop) *Tracking Evolving Relationship Between Characters in Novels.*
9. Jayannavar, P. et al. 2019. *Unsupervised cluster analyses of character networks in fiction: Community structure and centrality.* Expert Systems with Applications.
10. Nalisnick, E., Baird, H. 2013. *Character-to-Character Sentiment Analysis in Shakespeare's Plays.* ACL Short Papers, pp. 479–483. Companion: *Extracting Sentiment Networks from Shakespeare's Plays* (ICDAR 2013).
11. Nonaka, H., Perry, K. E. 2025. *Evaluating LLM Story Generation through Large-scale Network Analysis of Social Structures.* NeurIPS 2025 Workshop. arXiv:2510.18932.
12. Inoue, N. et al. 2022. *Learning and Evaluating Character Representations in Novels.* ACL Findings.
13. Grayson, S., Mulvany, M., et al. 2016. *Novel2Vec: Characterising 19th Century Fiction via Word Embeddings.* AICS.
14. Fast, E., Vachovsky, T., Bernstein, M. 2016. *Shirtless and Dangerous: Quantifying Linguistic Signals of Gender Bias in an Online Fiction Writing Community.* ICWSM. arXiv:1603.08832.
15. Vishnubhotla, K. et al. 2022. *The Project Dialogism Novel Corpus.* LREC. arXiv:2204.05836.
16. Hacker News thread 42946317 + assorted GitHub character-graph tools (2024-2025).

**Concrete ideas worth stealing for BookRAG:**
- **Fix a 7-type relationship enum in the Pydantic schema** and let the LLM slot into it — eliminates the drifting label problem at zero cost.
- **Add `valence` to `Relationship`** — one-word signed-edge annotation unlocks Nalisnick-style antagonist-cluster detection and is a cheap LLM-bias diagnostic (Nonaka 2025).
- **Expose betweenness centrality as a Character node attribute** per spoiler-bound snapshot, used as a retrieval-ranking tiebreaker — high-betweenness characters are usually the ones worth surfacing first.
- **Louvain community detection → candidate Faction nodes** when no explicit Faction was extracted, catching implicit factions in ensemble novels like Red Rising.
- **Diff successive per-identity Relationship snapshots to emit RelationshipArc nodes** — directly answers "how did X and Y's relationship change?" which is a common reader-facing question.
- **Port Fast et al.'s SVO agency extraction** off BookNLP's existing dependency parses (free — no new model calls) to attach agency/passivity attributes to Character nodes.
- **Use PDNC's 22-novel quotation gold set** as a drop-in benchmark for BookRAG's dialogue attribution and speaker-linked relationship extraction — the only sizeable gold-standard that overlaps BookRAG's pipeline outputs.
- **Treat Labatut & Bost's extraction/analysis taxonomy as a design rubric** — every BookRAG relationship pipeline knob (interaction unit, polarity, temporal granularity) should have an explicit setting documented in `config.yaml`, rather than being implicit in prompt wording.

### 14. Long-document chunking strategies

**Researched:** 2026-04-22 (iteration 14)

**TL;DR:** Chunking is the single biggest lever on extraction recall for narrative KG construction — GraphRAG's own report shows GPT-4 extracts ~2x more entity references at 600 tokens vs 2400 [1], and BookRAG's current 1500-token batches sit squarely in the "low-fidelity" zone. The highest-leverage upgrades for a narrative KG pipeline are (a) shrinking chunks and adding a "gleaning" second pass, (b) Anthropic-style contextual prepending of chapter/scene summaries (49% fewer retrieval failures in the published eval [2]), and (c) scene-boundary-aware chunking — a published, if hard, task in computational literary studies [3].

**Baseline strategies.** Fixed-token (OpenAI tiktoken packing), fixed-sentence, and LangChain's `RecursiveCharacterTextSplitter` (tries paragraph → sentence → word → char separators in order) are the defaults most teams ship. NLTK/spaCy sentence tokenizer + greedy packing to a token budget is a common step up when paragraphs are heterogeneous. Vectara's 2024 evaluation found fixed-size chunking is a surprisingly strong baseline — in their three retrieval tasks, semantic chunking did *not* consistently beat it, and the compute overhead was not justified [4].

**Semantic chunking.** Greg Kamradt's "5 Levels of Chunking" popularized the idea: window each sentence, embed, compute cosine distance between consecutive windows, and insert a breakpoint wherever distance exceeds a percentile threshold (default 95th) [5]. LlamaIndex and LangChain both ship implementations. The Vectara study swept thresholds at the 10/30/50/70/90th percentile and still found no consistent gain over fixed-size [4]. Semantic chunking is "blog-famous, paper-mediocre" — plausibly because narrative text has weak semantic boundaries (same characters, same setting, one long thread).

**Hierarchical chunking — RAPTOR.** Sarthi et al. (ICLR 2024) build a tree of summaries bottom-up: embed leaf chunks, cluster with a Gaussian Mixture Model, summarize each cluster with an LLM, re-embed the summaries, and recurse. Retrieval queries the *whole tree* (leaves + interior summaries) [6]. Reported gains: +20% absolute accuracy on QuALITY (multiple-choice narrative comprehension) when coupled with GPT-4, and significant improvements on NarrativeQA and QASPER over flat retrievers [6]. The multi-level summaries are exactly what a fog-of-war spoiler filter would need to prune, but the mechanism is the right shape for long novels.

**Propositional chunking.** Chen et al. (2023) "Dense X Retrieval" decomposes documents into *propositions* — "atomic expressions each encapsulating a distinct factoid in concise, self-contained natural language" — and indexes those instead of passages [7]. On open-domain QA, proposition-indexed retrieval beat both passage- and sentence-level units at fixed compute, with the gains propagating to downstream QA accuracy [7]. For a narrative KG, atomic propositions are close to what extraction already produces (SVO facts, PlotEvent records) — the insight is that the *retrieval unit* should match.

**Contextual retrieval (Anthropic, Sept 2024).** For each chunk, ask an LLM to generate a short context "situating this chunk within the overall document" (50–100 tokens) and prepend it *before embedding and BM25 indexing* [2]. On their eval: contextual embeddings alone cut top-20 retrieval failures 35% (5.7% → 3.7%); combined with BM25, 49% (5.7% → 2.9%); plus a reranker, 67% (5.7% → 1.9%). Prompt caching brings the one-time cost to ~$1.02 per million document tokens [2]. This is the single most cost-effective published technique, and it's directly applicable to BookRAG's extraction prompt too (prepend a scene/chapter context blurb).

**Late chunking (Jina, 2024).** Flip the order: embed the whole long document first, then mean-pool token embeddings *by chunk span*. Each chunk's vector is conditioned on the whole document's context — anaphora and cross-chunk references survive. On BeIR: SciFact nDCG@10 64.20 → 66.10, TRECCOVID 63.36 → 64.70, NFCorpus 23.46 → 29.98, with gains growing with document length [8]. Requires a long-context embedding model (jina-embeddings-v2/v3, 8,192-token window). Useful for *retrieval* but doesn't help extraction-time recall — the LLM still sees whatever text you hand it.

**Document-aware / structural chunking.** unstructured.io's `by_title` strategy partitions on detected section headings — a new Title element force-closes the current chunk even if it would fit, with `combine_under_n_chars` to merge stubby list-item sections [9]. Markdown/LaTeX-aware splitters do the same for heading syntax. For EPUBs specifically, chapter and section (`h1`/`h2`) are the obvious structural anchors — BookRAG already respects chapters, so this amounts to adding section/scene anchors within chapters.

**Chapter-aware chunking for novels.** Zehe, Gius et al. (EACL 2021, "Detecting Scenes in Fiction") published the reference scene-segmentation task: a scene is "a segment where time and discourse time are more or less equal, the narration focuses on one action/location, and character constellations stay the same" [3]. German dime-novel corpus, 550k tokens, inter-annotator gamma = 0.7. BERT baseline F1 = 24% — the task is hard [3]. A 2025 follow-up (LaTeCH-CLfL) refines the taxonomy and baselines further. Usable today as a *feature* (detect scene breaks heuristically via speaker-change + setting-word shift + time-marker regexes) even without training on the German corpus.

**Overlap strategies.** Fixed 10–20% token overlap is the LangChain default; sentence-overlap (repeat last N sentences) preserves anaphoric antecedents better than token-overlap. A "bridge sentence" — a one-line summary of the previous chunk prepended to the next — is the poor-man's contextual retrieval. Overlap helps recall but inflates dedup cost downstream (entity extractions from overlapping regions must be merged).

**Chunk size vs extraction quality.** The GraphRAG writeup is the most-cited published number: at chunk size 600, GPT-4 extracted ~2x more entity references on HotPotQA than at 2400 [1]. Their default is 300 tokens; their recommended sweet spot with one "gleaning" pass is 1200 tokens. Gleaning = re-prompt the LLM with the extracted entities and ask "what did you miss?", optionally prefixed with "MANY entities were missed in the last extraction" to bias recall [1]. No published narrative-specific sweep exists; BookRAG's own ablation at 1500 / 1000 / 500 tokens would be novel data.

**Chunk-level metadata.** For narrative text, chunks should carry: `chapter_num`, `paragraph_start_index`, `paragraph_end_index`, `scene_id` (if detected), dominant `speaker` (from BookNLP quote attribution), `pov_character` (for multi-POV novels like Red Rising), and `setting` (top TF-IDF location from ontology). This unlocks filtered retrieval ("dialogue by Cassius in Book 1") and is cheap to attach given BookNLP already labels quotes and entities.

**BookRAG's current approach — strengths/weaknesses.**
- Strengths: chapter boundaries respected; paragraph-aware splits; batch size configurable (now supports `batch_size=1` for chapter-granular Phase-2 snapshots); all intermediate chunks serialized to disk for traceability.
- Weaknesses: 1500-token chunks sit in the low-recall regime per [1]; no scene-boundary awareness inside chapters; no contextual prepend before extraction or embedding; no gleaning pass; no paragraph-level extraction (the Phase-2 snapshot caveat in `CLAUDE.md` is exactly this).

**Concrete upgrades.**
- (a) Drop `chunk_size` from 1500 → 750 or 500 tokens and add a GraphRAG-style single gleaning pass; measure entity-reference count on A Christmas Carol as a unit test.
- (b) Add heuristic scene detection (blank-line runs + time-jump regexes + speaker-discontinuity from BookNLP quotes) as a soft chunk boundary; fall back to paragraph splits when no scene break is detected within N tokens.
- (c) Contextual-retrieval prepend: for each batch, generate a 2–3 sentence "situating context" (chapter title + preceding-chapter summary + scene summary) via LLMGateway and include it in the extraction prompt *and* in the embedded chunk text for query-time retrieval. Cache with prompt caching.
- (d) Optional: RAPTOR-style tree summarization per chapter (leaf paragraphs → scene summaries → chapter summary) to feed the `GRAPH_COMPLETION` path with level-appropriate context.
- (e) Attach `pov_character` and `speaker` metadata to every chunk at partition time — free given BookNLP already runs.

**Key citations.**
1. Microsoft GraphRAG — "From Local to Global" (Edge et al., 2024), and the GraphRAG docs on chunking + gleaning. https://arxiv.org/html/2404.16130v2 ; https://microsoft.github.io/graphrag/index/default_dataflow/
2. Anthropic, "Introducing Contextual Retrieval" (Sept 2024). https://www.anthropic.com/news/contextual-retrieval
3. Zehe, Konle, Dümpelmann, Gius et al., "Detecting Scenes in Fiction: A new Segmentation Task," EACL 2021. https://aclanthology.org/2021.eacl-main.276/ ; 2025 follow-up https://aclanthology.org/2025.latechclfl-1.8.pdf
4. Qu, Tu, Bao, "Is Semantic Chunking Worth the Computational Cost?" arXiv:2410.13070 (Oct 2024), Findings of NAACL 2025. https://arxiv.org/abs/2410.13070
5. Greg Kamradt, "5 Levels of Text Splitting / Chunking" — https://x.com/GregKamradt/status/1699465826485862543 and the LlamaIndex/LangChain SemanticChunker implementations.
6. Sarthi, Abdullah, Tuli, Khanna, Goldie, Manning, "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval," ICLR 2024, arXiv:2401.18059. https://arxiv.org/abs/2401.18059
7. Chen, Zhao, Bansal et al., "Dense X Retrieval: What Retrieval Granularity Should We Use?" arXiv:2312.06648 (2023). https://arxiv.org/abs/2312.06648
8. Günther, Mohr et al. (Jina AI), "Late Chunking in Long-Context Embedding Models" (2024). https://jina.ai/news/late-chunking-in-long-context-embedding-models/
9. unstructured.io chunking docs (by_title strategy). https://docs.unstructured.io/open-source/core-functionality/chunking

**Concrete ideas worth stealing for BookRAG.**
- Shrink chunks and add gleaning — the cheapest likely recall win, and GraphRAG already published the numbers.
- Contextual-retrieval prepend for *extraction*, not just retrieval: give the LLM a 2-sentence "where we are in the story" blurb before each batch, generated once per chapter and cached. Should particularly help first-appearance disambiguation (the problem Phase-2 per-identity snapshots tries to paper over).
- Heuristic scene detection from signals BookRAG already has (quote speakers, location mentions, blank-line runs, time-jump cues like "the next morning") — no new model, no German-corpus training. Scene IDs then anchor chunk metadata and can be a unit of the spoiler bound below chapter-level.
- Propositional chunking as a *second* index layer: already extracted PlotEvent/Relationship DataPoints are essentially propositions — embed them individually alongside the chunk embeddings and retrieve over both (Dense X's core idea [7], free given BookRAG's extraction output).
- For future long-context embedding work, late chunking [8] is a clean fit once BookRAG adopts an 8k-context embedding model — lets a single chapter embed coherently and survive paragraph-level retrieval without losing anaphoric context.
### 15. Evaluation benchmarks & methodology for narrative KG + QA

**Researched:** 2026-04-22 (iteration 15)

**TL;DR:** Narrative KG+QA evaluation splits into three disjoint measurement planes — (1) extraction quality (entity/coref/relation/event F1 against LitBank-style gold), (2) retrieval quality (NDCG@10, Recall@k, RAGAS context precision/recall), and (3) answer quality (FABLES-style claim-level faithfulness, LLM-judge with calibration, ROUGE/F1 as weak baselines). BookRAG's fog-of-war problem adds a fourth plane — spoiler-leak rate — for which no published metric exists; it must be constructed by combining FABLES claim decomposition with a post-cursor-overlap detector. LLM-as-judge is cheap but systematically biased (position, length, self-preference) and underperforms humans on long-form faithfulness [1, 4, 8].

**KG construction metrics:**
- **Entity F1** — span+type match, LitBank/CoNLL conventions; exact-span strict vs. partial overlap lenient.
- **Coref CoNLL-F1** — unweighted mean of MUC (link-based), B³ (mention-based), and CEAFe (entity alignment) F1s; the canonical `reference-coreference-scorers` (Pradhan et al.) is the reference implementation [5]. LEA is a newer alternative that weights entity importance.
- **Relation extraction F1** — TACRED-style; fiction-specific gold is scarce (LitBank relations are limited; RED and DocRED dominate but are news-domain).
- **Event extraction F1** — TextEE standardizes trigger-identification (TI), trigger-classification (TC), argument-identification (AI), argument-classification (AC); AI+/AC+ additionally enforce correct trigger attachment and show prior AC numbers were inflated by loose attachment [6].
- **Schema adherence** (custom) — fraction of extracted DataPoints whose `type` field is in the declared ontology and whose required attributes parse; easy to compute at extraction time from `ExtractionResult`.

**End-to-end QA metrics:**
- **EM / token-F1** — SQuAD heritage; NarrativeQA historically reported BLEU-1/4, METEOR, ROUGE-L, but LiteraryQA (2025) shows most n-gram metrics correlate <0.07 with human judgment; only METEOR reaches τ≈0.44 after cleaning [9].
- **ROUGE/BLEU** — retained as cheap regression guards, not as truth.
- **LLM-as-judge** — MT-Bench-style pairwise or single-score; GPT-4 agrees with humans ~80% on chat, but Wang et al. show flipping answer order can swing win-rate by >30 pts [4].
- **Faithfulness** — FABLES decomposes a summary into atomic claims, then asks an annotator (or judge) to label each Yes/No/PartialSupport/Inapplicable against the source book [1].
- **Groundedness / citation precision** — fraction of output sentences with a retrieved supporting chunk ID.

**Retrieval metrics (for RAG):**
- **NDCG@10** — BEIR's canonical ranking metric; handles graded relevance, the de-facto standard [7].
- **Recall@k** (k=5/10/20), **MRR@k**, **MAP@k**, **P@k** — all available in `pytrec_eval`, wrapped by BEIR.
- **RAGAS context precision** — fraction of top-k chunks that are relevant, weighted by rank; **context recall** — fraction of ground-truth supporting claims actually retrieved; both reference-free variants exist via LLM judges [2].
- **Spoiler-leak rate** (novel) — per-query fraction of answer tokens/claims that are supported only by post-cursor text. Not published; must be built.

**Human evaluation protocols:** FABLES hired native-English annotators who had read each 2023/24 book (to avoid contamination) and paid ~$5.2K for 3,158 claim annotations across 26 books [1]. Typical IAA for faithfulness labels is Cohen's κ ≈ 0.5–0.7 (moderate-to-substantial); claim-level granularity lifts agreement vs. summary-level Likert. Pairwise preferences (MT-Bench/Arena) aggregate via Bradley-Terry or Elo; crowd win-rate agreement with experts is 80%+ for GPT-4-class judges [4].

**LLM-as-judge limitations:** (a) **Position bias** — Wang et al. 2023 show GPT-4 preferred answer A over B in A-B ordering and B over A in B-A ordering for the same pair; mitigation is Balanced Position Calibration (score both orders and average) [8]. (b) **Length bias** — judges prefer longer responses even when content is equivalent [4]. (c) **Self-preference** — models rate their own outputs higher than other models' [4, 8]. (d) **FABLES finding** — no LLM rater correlates strongly with human faithfulness labels on book-length summaries, especially for detecting unfaithful claims; reliable on short-form coherence/factuality but not on narrative faithfulness [1]. Judges are reliable when the task is short, closed-form, and has clear ground truth.

**Automatic metrics for spoiler-safety (what SHOULD exist):**
1. **Post-cursor n-gram overlap** — for each answer, compute max ROUGE-L between answer and text spans from chapters >cursor; treat high overlap as leak signal (fast, crude).
2. **Claim-level provenance check** — decompose answer into atomic claims (FABLES/RAGAS style), then ask a judge whether each claim is supported exclusively by post-cursor text; leak-rate = fraction answered yes.
3. **Predictability-shift test** (from iteration 10) — an out-of-world LLM should find post-cursor revelations surprising; if answer reduces its next-chapter perplexity, the answer leaks information.
4. **Anti-faithfulness judge** — invert RAGAS faithfulness: require ALL claims be grounded in pre-cursor allowlist; any ungrounded claim that happens to match post-cursor text = leak.

**Benchmarks specifically for narrative RAG:**
- **NovelQA** (Wang et al. 2024) — 89 novels, 2,305 Q/A by English-lit-expert annotators, 200k+ token avg; multichoice + generative; shows models collapse on evidence beyond 100k tokens and on multi-hop/detail questions [3]. Does not model reading-progress cutoffs.
- **FABLES** — 26 books (2023/24 to dodge contamination), 3,158 claim annotations; the only book-scale faithfulness gold [1].
- **NarrativeQA** (Kočiský et al. 2018) — 1,567 books/movies, 46,765 Q/A from summaries. ROUGE-L de-facto standard; LiteraryQA (2025) released a cleaned split showing the metric is weak [9].
- **StorySumm** (2024) — short-story faithfulness, claim-level; smaller but cleaner than FABLES for iteration.
- **Missing for spoiler-aware systems** — none partition by reader-progress or publish leak-rate gold; BookRAG would be first.

**Pipeline-level ablation methodology:** Standard RAG ablation protocol holds test queries and judge fixed while toggling one component. For BookRAG: (a) **remove ontology** (free-form extraction vs. ontology-constrained); (b) **remove coref** (raw chapters vs. parenthetical-inserted); (c) **vary batch_size** {1, 3, 5, full-book}; (d) **swap retriever** (Kuzu graph walk vs. LanceDB only vs. hybrid); (e) **swap LLM** (gpt-4o-mini vs. claude). Published guidance: isolate one variable at a time, fix the evaluation LLM-judge (ideally a stronger model than the system-under-test to avoid self-preference), report per-metric deltas not aggregate scores, include confidence intervals via bootstrap over queries (n≥100).

**Reproducibility and cost tracking:** Norm established by HELM/MTEB/BEIR — log per-query (prompt tokens, completion tokens, model, latency, cost_usd). Roll up to (a) cost per ingested book, (b) cost per 1k queries, (c) $/correct-answer. FABLES published its $5.2K annotation budget openly [1]; RAGAS runs are typically $0.01–0.10 per query with gpt-4o-mini judges [2]. BookRAG should record this in `pipeline_state.json` per batch and in a new `query_log.jsonl` per query.

**Strengths / gaps in BookRAG's current eval:**
- Strengths: 923 unit tests exercise every pipeline module; `validation/test_suite.py` exists; per-identity snapshot test shows methodology awareness; Christmas-Carol fixture gives deterministic regression baseline.
- Gaps: no entity/coref F1 against gold; no retrieval recall metric; no faithfulness metric; no spoiler-leak metric; no LLM-judge harness; no cost accounting; no per-query log; no ablation runner; `validation/` likely just happy-path smoke tests.

**Concrete BookRAG eval upgrade plan:**
- (a) **Port FABLES claim-level annotation** — pick 3–5 public-domain books, generate 20 queries per book per cursor position, decompose answers into claims via GPT-4o, manually label 200 claims for Yes/No/PartialSupport as a calibration set.
- (b) **Implement spoiler-leak forecaster** (iteration 10) — per-query, compute (i) ROUGE-L vs. post-cursor text and (ii) LLM-judge "does this reveal chapter >N content"; report leak-rate@cursor.
- (c) **LLM-judge faithfulness harness** — RAGAS-style claim decomposition + grounding check against allowlist; calibrate against (a); apply Balanced Position Calibration for any pairwise comparisons.
- (d) **Schema-adherence metric at extraction time** — in `cognee_pipeline.py`, log `schema_adherence = |valid_typed_datapoints| / |all_datapoints|` per batch; surface in validation endpoint.
- (e) **Ablation runner** — `scripts/ablate.py` that re-runs a fixed query set over toggled configs and emits a CSV comparable to HELM tables.
- (f) **Query log** — append every `/books/{id}/query` with tokens, cost, cursor, retrieved node IDs; enables post-hoc leak auditing.

**Key citations:**
1. Kim et al., "FABLES: Evaluating Faithfulness and Content Selection in Book-Length Summarization," COLM 2024. arXiv:2404.01261.
2. Es et al., "RAGAS: Automated Evaluation of Retrieval Augmented Generation," arXiv:2309.15217, 2023.
3. Wang et al., "NovelQA: Benchmarking QA on Documents Exceeding 200K Tokens," arXiv:2403.12766, 2024.
4. Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," NeurIPS 2023. arXiv:2306.05685.
5. Pradhan et al., CoNLL-2012 reference coreference scorers; Moosavi & Strube LEA 2016; Luo 2005 CEAF; Bagga & Baldwin 1998 B³; Vilain et al. 1995 MUC.
6. Huang et al., "TextEE: Benchmark, Reevaluation, Reflections, and Future Challenges in Event Extraction," ACL Findings 2024. arXiv:2311.09562.
7. Thakur et al., "BEIR: A Heterogeneous Benchmark for Zero-shot Information Retrieval," NeurIPS 2021.
8. Wang et al., "Large Language Models are not Fair Evaluators," ACL 2024. arXiv:2305.17926.
9. LiteraryQA / NarrativeQA re-evaluation, EMNLP 2025 (arXiv:2510.13494) — showing n-gram metrics correlate <0.07 with human judgment on narrative QA.

**Concrete ideas worth stealing for BookRAG:**
- FABLES claim decomposition pipeline applied at the reader's cursor, not just at the book level — lets us measure "what fraction of the answer is supported by what the reader has read."
- RAGAS context-precision-at-cursor: of retrieved nodes, what fraction have `effective_latest_chapter ≤ cursor`? Already computable from the allowlist.
- TextEE's AI+/AC+ attachment-aware argument F1 — gives a cleaner picture of whether extracted events have the right participants, critical for character KGs.
- Balanced Position Calibration for any pairwise ablation (e.g., ontology vs. no-ontology) — trivial to add and kills order bias.
- Publish a public `spoiler-leak-bench` with cursor-partitioned gold over Christmas Carol + Red Rising — no one has this and it would be a citable contribution.


### 16. Open-source book-focused projects

**Researched:** 2026-04-22 (iteration 16)

**TL;DR:** The OSS "book + graph/LLM" landscape is a thin band of academic prototypes (Renard, Novel2Graph, BookWorld, NovelQA), a flood of generic "chat with my PDF/EPUB" RAG demos, and a large adjacent ecosystem of worldbuilding tools (Obsidian vaults, Calibre) that expose graphs only to the author. Nothing ships spoiler-gated retrieval; most stop at character co-occurrence or full-book QA.

**Projects:**

- **BookWorld** (`alienet1109/BookWorld`, ACL 2025, Apache-2.0) [1][2]. Ran, Wang et al. Ships a Python backend + web frontend that extracts characters, locations, and world settings from EPUB/PDF/TXT and spins up a multi-agent society for interactive story generation. The authors explicitly warn "extraction code is currently unstable" and recommend manual data entry — i.e. the hard part (structured world extraction) isn't solved even in their own repo. Win rate 75.36% on story-generation fidelity. Relevance: closest thing to a "books -> structured world model" OSS project, but the target is generative play, not reader-facing QA; no progress model.

- **Renard** (`CompNet/Renard`, GPL-3.0, v0.7.1 released 2026-01-07) [3]. Amalvy et al. "Relationship Extraction from NARrative Documents." Modular `PipelineStep` architecture (tokenize -> NER -> character unification -> co-occurrence graph) directly parallel to BookRAG's stage pipeline. Ships an NLTK-based default but steps are swappable. Produces static and dynamic (windowed) character networks. No LLM extraction, no spoiler filtering, no ontology. Strong evidence that pipeline-of-steps is the right abstraction for this problem space.

- **Novel2Graph** (`IDSIA/novel2graph`) [4]. Mellace, Kanjirangat, Antonucci. Semi-supervised: character identification/clustering -> static+dynamic embeddings -> relation extraction -> relation clustering, optionally a BERT family-relation classifier. Outputs character occurrences, coref'd text, embeddings, relation reports, plus scraped Goodreads/Amazon reviews for contextualization. 14 stars — academic artifact, not maintained product. Interesting: they persist coref'd text to disk, same design choice as BookRAG.

- **novel-graph** (`schoobani/novel-graph`, v0.2.0 Feb 2025) [5]. Thin LLM-based wrapper: chunks novel, calls OpenAI to emit character relationships/descriptions/interactions as JSON. 21 stars. No license listed. Example books include Karamazov, War and Peace. This is the "just prompt GPT-4 on chunks" baseline that BookRAG's hybrid-Cognee pipeline should beat.

- **NovelQA** (`NovelQA/novelqa.github.io`, HF dataset) [6]. 89 novels (61 public), 2305 expert-annotated QA pairs, contexts >200k tokens. The repo ships dataloader scripts, book metadata JSON, and a demonstration book+gold-answer set. Not a pipeline — a benchmark. BookRAG should target their question taxonomy (detail / multi-hop / times) for eval.

- **BookSum** (`salesforce/booksum`, Kryściński et al. 2021) [7]. 146k paragraph / 12,630 chapter / 405 book-level summaries scraped from CliffNotes/SparkNotes-style sources. The `scripts/data_collection/` directory is a useful reference for chapter/paragraph alignment — BookRAG's batch boundaries could borrow their alignment heuristics.

- **LiSCU** (`huangmeng123/lit_char_data_wayback`) [8]. Literary pieces + summaries + *character descriptions* scraped from Shmoop/SparkNotes/CliffsNotes/LitCharts via Wayback Machine. Useful as a distant-supervision signal for "what a good character description looks like" at various points in a book.

- **AO3 scrapers** (`radiolarian/AO3Scraper`, `billsargent/ao3-scraper`, several others) [9]. All focus on fanfic metadata (tags, authors, kudos) — none build relationship graphs. Fandom wiki scraper `JOHW85/ScrapeFandom` dumps MediaWiki XML; no structured character/event extraction.

- **Obsidian worldbuilding vaults** (The Novelist, various templates) [10]. Bidirectional `[[links]]` + graph view give writers a manual KG. No auto-extraction. Relevance: confirms that readers/writers already think in graph terms; a spoiler-safe reader-side graph is a gap.

- **Calibre** [11]. v6+ has full-text search across libraries but no KG or semantic search plugins in the official index. Large plugin ecosystem but none KG-shaped — a plugin surface BookRAG could eventually plug into.

- **Character network academic one-offs** — `hzjken/character-network` (Harry Potter, NER+sentiment), `isthatyoung/NLP-Characters-Relationships`, `zfsang/CharacterGo`, `suvakov/chargraph` [3]. All student-project scale, all co-occurrence + sentiment, all stale.

- **Generic "chat with ebooks" RAG** — `nicholasgriffintn/genai-rag-ebooks` (MIT, 8 commits, 0 stars, abandoned), Unstructured's MongoDB Atlas EPUB tutorial, countless `rag-chatbot` topic repos. All dump EPUB text into a vector store and prompt an LLM. None model narrative time, character, or spoilers.

**Comparison: BookRAG vs OSS competitors.** Of everything surveyed, only Renard has a comparable "staged pipeline with swappable steps" architecture, and it stops at co-occurrence — no description, no events, no LLM synthesis. BookWorld is the only project that builds structured per-character data, but it optimizes for agent simulation, not for answering a reader's question, and its own authors admit extraction is unreliable. No OSS project implements a reader-progress cursor or spoiler gating; the closest prior art is Obsidian, where spoiler control is enforced by the user not opening certain notes. BookRAG's `effective_latest_chapter` + cursor-bounded allowlist is, as far as public code goes, novel.

The "chat with my ebook" cohort is a red herring — high volume, low depth, no narrative awareness. BookRAG competes on a different axis: reader-state-aware retrieval plus KG, not bigger context window plus bigger vectors.

**Standout primitives worth borrowing:**
- Renard's `PipelineStep` contract (swappable NER / unifier / extractor) — BookRAG's `pipeline/` modules already echo this; formalizing a `PipelineStep` base class would make coref-resolver/ontology-discovery genuinely swappable.
- Novel2Graph's persisted coreferenced-text directory structure — validates BookRAG's "save every intermediate to disk" policy.
- BookWorld's explicit "world agent + role agents" separation — suggests a future BookRAG mode where the spoiler-gated KG drives character role-play agents per reader cursor.
- BookSum's chapter-to-summary alignment scripts — reusable for paragraph-boundary detection during batching.
- LiSCU's character-description corpus — could serve as distant supervision / eval gold for per-snapshot character descriptions.

**Strengths of the OSS ecosystem:**
- Plentiful character-network baselines; commoditized NER+coref+co-occurrence.
- NovelQA + BookSum give ready-made eval data.
- EPUB parsing (ebooklib, Unstructured) is a solved problem.

**Weaknesses / gaps:**
- No OSS project models reader progress or spoilers.
- Extraction quality is either co-occurrence-only (fast, shallow) or raw GPT-4-on-chunks (expensive, hallucinatory). Nothing in between.
- No per-snapshot / temporal KG versioning in any maintained repo.
- Worldbuilding tools (Obsidian, Campfire, World Anvil) are author-side only; no reader-facing analog.
- Most academic repos (Novel2Graph, CharacterGo, etc.) are publication artifacts, not maintained libraries.

**Key citations:**
1. Ran, Wang et al., "BookWorld: From Novels to Interactive Agent Societies for Creative Story Generation," ACL 2025. arXiv:2504.14538.
2. https://github.com/alienet1109/BookWorld
3. https://github.com/CompNet/Renard — Amalvy et al., GPL-3.0, v0.7.1 (2026-01).
4. https://github.com/IDSIA/novel2graph — Mellace, Kanjirangat, Antonucci.
5. https://github.com/schoobani/novel-graph — v0.2.0, Feb 2025.
6. Wang et al., "NovelQA: Benchmarking Question Answering on Documents Exceeding 200K Tokens," ICLR 2025. arXiv:2403.12766. https://github.com/NovelQA/novelqa.github.io
7. Kryściński et al., "BookSum: A Collection of Datasets for Long-form Narrative Summarization," 2021. https://github.com/salesforce/booksum
8. https://github.com/huangmeng123/lit_char_data_wayback (LiSCU).
9. https://github.com/radiolarian/AO3Scraper ; https://github.com/JOHW85/ScrapeFandom
10. "The Novelist" Obsidian vault (Sakalakis, 2026); Obsidian forum worldbuilding threads.
11. Calibre plugin index, https://plugins.calibre-ebook.com/ ; Calibre 6.0 full-text search release notes.

**Concrete ideas worth stealing for BookRAG:**
- Adopt a formal `PipelineStep` ABC modeled on Renard — makes the BookNLP-vs-BookCoref swap trivial and documents the contract.
- Ingest LiSCU as a distant-supervision corpus: for each NovelQA/BookSum-overlap book, compare BookRAG's per-snapshot character descriptions against LiSCU's study-guide descriptions truncated to the reader's chapter.
- Publish BookRAG's spoiler-gated retrieval as a standalone `PipelineStep`-compatible plugin so Renard users can drop it in — low effort, high citability, cleanly positions BookRAG as "the spoiler layer for existing book-NLP pipelines."
- Borrow BookSum's chapter-boundary alignment heuristics as a fallback when EPUB TOC is missing.
- Target NovelQA's multi-hop + detail question categories as BookRAG's headline eval; report cursor-partitioned accuracy alongside full-book accuracy.

### 17. Multi-hop QA over narrative graphs

**Researched:** 2026-04-22 (iteration 17)

**TL;DR:** Multi-hop QA — questions whose answer requires composing facts across 2+ edges — is the dominant failure mode of single-shot RAG, and BookRAG's current top-15-allowed-nodes path is essentially a single-hop retriever. The strongest recent results come from HippoRAG's Personalized PageRank over an LLM-built KG (up to +20% on MuSiQue, 10-30x cheaper than IRCoT) [1] and GraphReader's agentic graph traversal with a notebook (beats GPT-4-128k at 4k context on LV-Eval) [2]. Both are directly portable to BookRAG's Kuzu graph; the spoiler-cursor bound just becomes an additional edge filter.

**Multi-hop QA benchmarks (general).** HotpotQA (crowdworker-authored, Wikipedia-grounded) defined four reasoning types: bridge-entity, intersection, relational-via-bridge, and comparison [6]. 2WikiMultiHopQA and MuSiQue are bottom-up constructions — composed from single-hop building blocks so the gold reasoning chain is explicit [3,6]. MuSiQue contains 25K 2-4 hop questions and is deliberately hard to cheat: a single-hop shortcut model drops 30 F1 points [3]. Bamboogle (Press et al.) is a 125-question adversarial probe built so no single Wikipedia paragraph contains the answer [4]. These benchmarks expose the *compositionality gap*: GPT-3 can answer both sub-questions individually but fails to compose them, and scaling model size does not close the gap [4].

**Multi-hop QA over KGs (KGQA).** MetaQA (400K questions over a movie KG, 1/2/3-hop splits) and ComplexWebQuestions are the canonical benchmarks [7]. Historically, KGQA splits into SPARQL-generation approaches (translate NL to a structured query over Freebase/Wikidata) and retrieval/embedding approaches (EmbedKGQA, subgraph reasoners). The SPARQL route requires a clean schema — unattractive for LLM-extracted narrative graphs where relation labels are noisy.

**Narrative-specific multi-hop.** NovelQA is 35.0% multi-hop, 42.8% single-hop, 22.2% detail. GPT-4 tops out at 46.88% overall, and accuracy for evidence past the 100K-token mark drops sharply [5]. NovelHopQA (2025) explicitly stratifies by hop-count: top models hit >95% EM on golden context but fall to ~60% under RAG, and accuracy declines monotonically with hop count regardless of context window size [5]. The clear finding: longer context alone does not rescue multi-hop over narrative.

**Retrieval strategies for multi-hop.** The family tree: (a) beam-search / random-walk over the KG (classical KGQA); (b) ReAct-style iterative retrieval where the LLM emits a search action, reads, then reasons; (c) IRCoT, which interleaves each CoT sentence with a fresh retrieval step, gaining up to +21 retrieval-points and +15 QA-points on HotpotQA/2Wiki/MuSiQue/IIRC [8]; (d) HippoRAG's one-shot PPR pass [1]; (e) GraphReader's agent-with-notebook [2].

**HippoRAG (Gutiérrez et al., NeurIPS 2024).** Inspired by the hippocampal indexing theory. Offline: LLM extracts an OpenIE-style KG from the corpus and embeds node names. Online: the query is parsed to seed nodes, embedding-similarity picks entry points, and **Personalized PageRank** (seeded on those entry nodes) propagates mass across the graph; top-ranked nodes' source passages are returned. Single forward pass, no iteration. Beats baselines by up to 20% on MuSiQue and matches IRCoT at 10-30x lower cost and 6-13x lower latency [1]. For BookRAG: PPR over the spoiler-allowed subgraph is ~50 lines of NetworkX; the cursor bound just masks nodes whose `effective_latest_chapter` exceeds the cursor before running PPR.

**GraphReader (Li et al., EMNLP 2024).** Chunks long documents into a graph of key-element nodes, then lets an agent (a) read a node's content, (b) fetch its neighbors, (c) write observations to a persistent notebook, (d) decide whether to continue or answer. Coarse-to-fine — starts with node summaries, drills in only when needed. On LV-Eval, GraphReader with a 4K context window beats GPT-4-128k across 16K-256K context lengths [2]. For BookRAG, the notebook maps cleanly to chapter-ordinal-aware state; the agent can be constrained to only visit nodes with `effective_latest_chapter ≤ cursor`.

**DRIFT search (GraphRAG, iteration 1).** Primer query → local community answers → synthesis. The follow-up-question step is structurally multi-hop: each local answer surfaces new entities that seed the next retrieval. Cheaper than global search but still 2-3 LLM calls per question.

**Chain-of-thought vs iterative retrieval.** Self-Ask (Press et al., EMNLP-F 2023) makes the LLM emit explicit "Follow-up: ..." / "Intermediate answer: ..." pairs, which can be routed to a search engine — it directly targets and narrows the compositionality gap [4]. IRCoT is the retrieval-native sibling: every reasoning sentence triggers a retrieval update, so the retriever sees the latest hypothesis rather than the raw question [8]. Both are prompt-only and swap in cleanly.

**Query decomposition.** Decomposed Prompting (Khot et al., ICLR 2023) treats decomposition itself as a learned skill: a "decomposer" prompt emits sub-tasks that are dispatched to specialized sub-prompts, which may recurse [9]. The alternative is *fixed-plan* decomposition (e.g., "always generate 3 sub-queries"), which is cheaper but weaker on heterogeneous questions. DecomP's modularity maps well to BookRAG, where sub-tasks could dispatch to {character-lookup, event-timeline, relationship-trace} tools.

**Answer grounding / citation for multi-hop.** Multi-hop grounding requires per-claim attribution, not just a bibliography. HotpotQA's "supporting facts" subtask and MuSiQue's gold reasoning chains are the standard evaluation targets — a system that gets the right answer via wrong evidence scores badly on joint EM. Practical pattern: have the LLM emit `{claim, source_node_id}` pairs, then verify each source was in the retrieved set.

**Narrative-specific multi-hop challenges.** (1) Temporal constraints — "what did X do after Y?" requires timeline-aware traversal, not just adjacency (see iteration 10 on temporal KGs). (2) Counterfactuals — "what if Scrooge had refused?" is unanswerable from the graph and should be refused. (3) Pronoun/coref ambiguity — the hop target may be an unnamed "he"; BookRAG's parenthetical coref resolution helps here. (4) Multi-chapter arcs — the evidence chain crosses batch boundaries, so the retriever must follow edges, not rely on single-batch co-extraction.

**BookRAG's current single-hop limitation.** `query_kg` in the GRAPH_COMPLETION path loads `load_allowed_nodes` → sorts by similarity → takes top-15 node descriptions → concatenates into the LLM prompt. There is no edge traversal: if "the person who killed Eyolf Stamfar" is a Character node with a KILLED edge to a PlotEvent that itself has a PARTICIPANT edge to the same Character, the LLM never sees the second hop unless both nodes happen to land in the top-15 by independent similarity to the query. Co-extraction within a single batch is the only mechanism that links them today.

**Concrete multi-hop upgrades for BookRAG.**
1. **2-hop neighbor fetch in `spoiler_filter`**: after picking the top-K seed nodes by similarity, expand to 1-hop and 2-hop neighbors via Kuzu, re-filter by cursor bound, return the union. ~30 lines; largest single-effort payoff.
2. **HippoRAG-style PPR over the allowed subgraph**: seed PPR on similarity-matched nodes, run on the cursor-filtered subgraph, return top-N by PPR score. Matches SOTA on MuSiQue and is single-pass.
3. **IRCoT loop wrapping `cognee_search`**: emit one CoT sentence, retrieve, append, repeat; cap at 4 iterations. Cheapest to prototype but most expensive per query.
4. **GraphReader agent with chunk-ordinal-aware traversal**: agent tools = `read_node(id)`, `list_neighbors(id, rel_type?)`, `write_notebook(text)`, `answer()`. Enforce cursor bound at the `list_neighbors` boundary.

**Key citations:**
1. Gutiérrez et al., "HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models," NeurIPS 2024. arXiv:2405.14831.
2. Li et al., "GraphReader: Building Graph-based Agent to Enhance Long-Context Abilities of Large Language Models," EMNLP 2024. arXiv:2406.14550.
3. Trivedi et al., "MuSiQue: Multihop Questions via Single-hop Question Composition," TACL 2022. arXiv:2108.00573.
4. Press et al., "Measuring and Narrowing the Compositionality Gap in Language Models" (Self-Ask), Findings of EMNLP 2023. arXiv:2210.03350.
5. Wang et al., "NovelQA: Benchmarking Question Answering on Documents Exceeding 200K Tokens," ICLR 2025. arXiv:2403.12766. NovelHopQA, arXiv:2506.02000.
6. Yang et al., "HotpotQA," EMNLP 2018; Ho et al., "Constructing A Multi-hop QA Dataset..." (2WikiMultiHopQA), COLING 2020.
7. Zhang et al., "Variational Reasoning for Question Answering with Knowledge Graph" (MetaQA), AAAI 2018; Talmor & Berant, "The Web as a Knowledge-Base for Answering Complex Questions" (CWQ), NAACL 2018.
8. Trivedi et al., "Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions" (IRCoT), ACL 2023. arXiv:2212.10509.
9. Khot et al., "Decomposed Prompting: A Modular Approach for Solving Complex Tasks," ICLR 2023. arXiv:2210.02406.

**Concrete ideas worth stealing:**
- Prototype HippoRAG PPR over the cursor-filtered Kuzu subgraph as a new `retrieval_mode: "ppr"` next to GRAPH_COMPLETION — paper-level numbers suggest +10-20% on multi-hop at negligible latency cost.
- Add 2-hop neighbor expansion as a default enrichment even without PPR; it fixes the top-15 co-extraction limitation with zero new infra.
- Adopt MuSiQue-style hop-count stratification in BookRAG's eval: tag each test question with its required hop-count and report accuracy per bucket, matching NovelHopQA's reporting convention.
- Enforce the spoiler cursor at the *edge-traversal* boundary, not just the node-set boundary — otherwise agentic traversal (GraphReader) can still leak via neighbor listings.
- Keep a "refusal" path for counterfactual narrative questions — they are structurally unanswerable from the KG and should not be hallucinated.
- Log per-claim source node ids in answers to enable MuSiQue-style joint EM evaluation later.

### 18. Fine-tuned extraction models for literature

**Researched:** 2026-04-22 (iteration 18)

**TL;DR:** A distilled 7-8B open-weight model (Qwen2.5-7B or Llama-3.1-8B) fine-tuned with LoRA on gpt-4o-mini-generated `{chunk -> DataPoint JSON}` pairs is a credible path to beat gpt-4o-mini on $/chunk for BookRAG's Phase 2 extraction, with grammar-constrained decoding (GBNF / Outlines) guaranteeing valid Pydantic JSON. The break-even is roughly one medium-length book (~100 chunks) before the self-hosted path becomes cheaper than API, once teacher-labeling cost is amortized. No off-the-shelf literature-extraction fine-tune exists; BookRAG would be producing novel training data.

**Distillation from frontier models - general methodology.** Hsieh et al.'s *Distilling Step-by-Step* (ACL 2023 Findings, arXiv:2305.02301) showed a 770M T5 beating few-shot 540B PaLM using only 80% of the labeled data, and on ANLI a model >700x smaller than the teacher matched its performance, by extracting natural-language rationales from the teacher and training the student in a multi-task framework (predict label + rationale) [1]. Microsoft's *Orca 2* (arXiv:2311.11045) generalized this: train a 7B/13B Llama-2 not just on teacher outputs but on *multiple reasoning strategies* (step-by-step, recall-then-generate, direct-answer) with the student learning to pick a strategy per task. Orca 2 matched models 5-10x larger on 15 reasoning benchmarks [2]. Standard recipe today: (i) sample diverse inputs, (ii) label with GPT-4/Claude producing output + rationale, (iii) filter by teacher self-consistency or schema validity, (iv) SFT the student, (v) optionally DPO on preference pairs where teacher disagrees with student.

**Small open-weight candidates (April 2026).** Qwen2.5-7B-Instruct is explicitly marketed as strong on "understanding structured data... and generating structured outputs, especially JSON," with 128K context, 8K max generation, and MATH 75.5 / HumanEval 84.8 [3]. Llama-3.1-8B-Instruct and Llama-3.2-3B are the standard Western baselines; Gemma-2-9B and Mistral-Small-3 round out the 7-9B class. For BookRAG's task (narrative chunk -> typed JSON), Qwen2.5-7B is the strongest starting point on published structured-output metrics.

**Structured-output fine-tuning.** Two complementary techniques, both production-ready: (1) **GBNF grammar-constrained decoding** in llama.cpp - a BNF extension that masks invalid tokens at each step, mechanically guaranteeing valid JSON (the repo ships `grammars/json.gbnf` and auto-converts a subset of JSON Schema to GBNF) [4]. (2) **Outlines / LLGuidance** - same idea library-side; llama.cpp now integrates LLGuidance in `common/llguidance.cpp` [4]. LoRA SFT trains the student to prefer valid structure; grammar decoding eliminates the remaining invalid-JSON tail. Combined, a LoRA'd Qwen2.5-7B with GBNF on a Pydantic-derived grammar should hit ~100% structural validity, which gpt-4o-mini with JSON mode already does but at much higher token cost.

**Narrative-specific extraction fine-tunes.** Nothing off-the-shelf. BookNLP is the closest thing but it is a pipeline of task-specific models (BERT-sized NER + coref), not a generative extractor [5]. GLiNER (NAACL 2024, arXiv:2311.08526) is a small bidirectional-encoder NER/RE model that outperforms ChatGPT on zero-shot NER benchmarks [6], and GLiNER multi-task extends to QA/summarization/relations, but it emits spans+types, not the rich Pydantic DataPoints (Character description, PlotEvent temporal ordering, Relationship stance) that BookRAG needs. LitBank (arXiv:1912.01140) is the natural eval set: 100 public-domain novels, 6 entity types, 29,103 coreference mentions over 210K tokens, with documents averaging 4x OntoNotes length [7].

**Cost analysis (concrete, April 2026).** gpt-4o-mini inference: $0.15/M input, $0.60/M output (base); fine-tuned: $0.30/M input, $1.20/M output, plus $3.00/M training tokens [8]. BookRAG's Red Rising at 100 chunks with ~3K input + ~1K output per chunk = 300K input + 100K output = $0.045 + $0.060 = **~$0.11/book** with base gpt-4o-mini. A fine-tuned 4o-mini would be **~$0.21/book**. Qwen2.5-7B on M4 Pro via MLX-LM: one pass on a 7B 4-bit model processes ~40-60 tok/s generation on M4 Pro, so 100K output tokens ≈ 30-45 min compute, amortized electricity <<$0.01. Training cost: gpt-4o-mini teacher labels on 500 training chunks across 3-4 books ≈ 1.5M input + 500K output = $0.23 + $0.30 = **~$0.55 teacher-labeling**, plus ~20-30 min LoRA training on M4 Pro (~$0 marginal) [9][10]. Unsloth makes Llama-3.1-8B LoRA 2.1x faster / 60% less memory vs FA2 and trains only 42M params (0.5% of model) with 99%+ accuracy retention [10]. **Break-even: immediate for training compute; self-hosted wins per-inference after about 5 books on fine-tuned 4o-mini, or about 10 books on base 4o-mini once you factor a modest hourly value for the M4.** The real win is latency/privacy/reproducibility, not raw dollars.

**Training data curation.** ~500-2000 `{chunk, DataPoint JSON}` pairs should suffice for LoRA (Distilling Step-by-Step's 80% rule, Orca 2's data-efficiency, and Unsloth's 500-sample examples all point here) [1][2][10]. Sources: full Red Rising (~100 chunks), full Christmas Carol (~10 chunks), LitBank's 100 novel excerpts (~100 x 2K tokens = 100 chunks with gold NER+coref for validation) [7], plus 100-300 synthetic chunks from other public-domain Gutenberg novels teacher-labeled. Filters: (a) teacher JSON must pass Pydantic validation, (b) teacher self-consistency - re-extract with temperature 0.7 and keep only examples where two runs agree on ≥80% of DataPoint fields, (c) manual spot-check 5-10% for hallucinated entities.

**OpenAI / Anthropic fine-tuning availability (April 2026).** OpenAI: gpt-4o-mini fine-tuning is generally available at the prices above [8]. Anthropic: fine-tuning is limited to Claude 3 Haiku on Amazon Bedrock; Haiku 4.5 (released Oct 2025) and all newer models are not yet fine-tunable through Anthropic's native API [11]. For BookRAG the managed option is gpt-4o-mini SFT; for Claude, only Bedrock-hosted Haiku 3.

**Distilled RAG-specific models.** Self-RAG (Asai et al., ICLR 2024) trains a Llama-2-7B/13B to emit retrieval and critique tokens alongside answers, distilled from GPT-4 critiques; it outperforms ChatGPT on several QA benchmarks [12]. RAG-Instruct and similar work use GPT-4-generated retrieval-grounded instruction data. For BookRAG the relevant pattern is extraction-side distillation (covered above), not RAG-time distillation, because the KG is static after ingestion.

**Structured extraction benchmarks.** LitBank (NER + coref on fiction) [7]; BookCoref (arXiv:2507.12075) extends coref to full-length books; GLiNER paper reports on CrossNER, MIT-Restaurant, MIT-Movie, Ontonotes for zero-shot NER [6]. No shared task exists for "narrative DataPoint extraction" in BookRAG's sense - BookRAG would need to define its own eval (DataPoint F1 against a human-curated chapter).

**Strengths / weaknesses of the fine-tuning path for BookRAG.**
- Strength: per-book inference cost and latency drop substantially; privacy (books never leave the Mac); full reproducibility of extractions across releases.
- Strength: GBNF guarantees structural validity, removing a class of Cognee-side failures.
- Strength: domain-adapted small model can learn BookRAG's specific DataPoint conventions (e.g., how to populate `last_known_chapter` vs `first_chapter` vs `chapter`).
- Weakness: teacher quality caps student quality; if gpt-4o-mini misses a relationship, the student will too.
- Weakness: one more moving part (LoRA adapter + GBNF + MLX runtime) in an already complex pipeline.
- Weakness: no off-the-shelf literature extraction model to warm-start from; training data must be built.
- Weakness: narrative extraction likely benefits from Orca-style reasoning chains, which bloat the output budget and complicate grammar constraints.

**Concrete pilot proposal.**
(a) Use the already-ingested Red Rising + Christmas Carol Phase-2 extractions as teacher data (they are already JSON and already on disk - no new API spend). Augment with ~200 chunks from 5 Gutenberg novels labeled by gpt-4o-mini, ~$0.30. Hold out Red Rising chapters 40-45 for eval.
(b) Fine-tune Qwen2.5-7B-Instruct with Unsloth/MLX LoRA (rank 16, alpha 32, 3 epochs, batch size 1, ~30 min on M4 Pro) on `{chunk -> DataPoint-JSON}` pairs. Derive a GBNF grammar from the Pydantic DataPoint schema.
(c) Evaluate on holdout: DataPoint F1 (entity-name match + type match), JSON validity rate, wall-clock per chunk, $/chunk. Compare against gpt-4o-mini base and LitBank-gold NER overlap.
(d) Success criterion: ≥90% of teacher's DataPoint F1 at <20% of teacher's $/chunk.
(e) If successful, wire as an alternative `extraction_backend: "mlx-qwen2.5-7b-lora"` in `models/config.py`, parallel to the Cognee LLMGateway path.

**Key citations:**
1. Hsieh et al., "Distilling Step-by-Step! Outperforming Larger Language Models with Less Training Data and Smaller Model Sizes," Findings of ACL 2023. arXiv:2305.02301.
2. Mitra et al., "Orca 2: Teaching Small Language Models How to Reason," Microsoft Research, 2023. arXiv:2311.11045.
3. Qwen Team, "Qwen2.5: A Party of Foundation Models," qwenlm.github.io/blog/qwen2.5 and qwen2.5-llm, 2024.
4. ggml-org, llama.cpp GBNF docs (`grammars/README.md`, `grammars/json.gbnf`, `common/llguidance.cpp`), 2024-2025.
5. Bamman et al., BookNLP repo, github.com/booknlp/booknlp.
6. Zaratiana et al., "GLiNER: Generalist Model for Named Entity Recognition using Bidirectional Transformer," NAACL 2024. arXiv:2311.08526.
7. Bamman et al., "An Annotated Dataset of Literary Entities" and "An Annotated Dataset of Coreference in English Literature" (LitBank), arXiv:1912.01140, LREC 2020.
8. OpenAI API pricing, developers.openai.com/api/docs/pricing (April 2026 snapshot): gpt-4o-mini base $0.15/$0.60 per M tokens; fine-tuned $0.30/$1.20; training $3.00/M.
9. Apple, "MLX LM" docs (qwen.readthedocs.io/en/latest/run_locally/mlx-lm.html); WWDC25 session 298 "Explore large language models on Apple silicon with MLX."
10. Unsloth, "Finetune Llama 3.1 with Unsloth" (unsloth.ai/blog/llama3-1): 2.1x faster, 60% less memory vs FA2+HF; 42M trainable params (0.5%) with 99%+ retention.
11. Anthropic, "Fine-tune Claude 3 Haiku in Amazon Bedrock," anthropic.com/news/fine-tune-claude-3-haiku; platform.claude.com model docs, April 2026.
12. Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection," ICLR 2024. arXiv:2310.11511.
13. Martinelli et al., "BookCoref: Coreference Resolution at Book Scale," 2025. arXiv:2507.12075.

**Concrete ideas worth stealing:**
- Add `extraction_backend` config value; default stays `cognee-llmgateway`, new option `mlx-qwen2.5-7b-lora` reads a local LoRA adapter + GBNF grammar.
- Auto-generate the GBNF grammar from BookRAG's Pydantic DataPoint schemas at startup (same source of truth) - eliminates schema drift.
- Save every Phase-2 teacher extraction to `data/processed/{book_id}/training_pairs/*.jsonl` by default so that a training set accumulates for free as users ingest books.
- Teacher self-consistency filter: re-extract at temperature 0.7 and keep only pairs where the two runs agree on ≥80% of DataPoint fields - cheap quality gate that matches Distilling Step-by-Step's rationale-filtering spirit.
- Evaluation harness: use LitBank's 100 novel excerpts as a standing entity-extraction benchmark; compute entity-name F1 against gold and report in `docs/superpowers/reviews/`.
- Orca-2-style strategy tagging: label a fraction of teacher examples with a prefix like `<strategy>recall-then-extract</strategy>` for dense chapters vs `<strategy>direct-extract</strategy>` for light ones; lets the student learn when to spend tokens on reasoning.
- Keep gpt-4o-mini as a fallback for chunks where the 7B model's GBNF-decoded output has confidence below threshold (measurable via log-probs on the selected JSON path).


### 19. Character persona modeling from novels

**Researched:** 2026-04-22 (iteration 19)

**TL;DR:** Character persona modeling has matured from hand-crafted PersonaChat profiles (2018) and LIGHT text-adventure characters (2019) into two dominant paradigms: fine-tuned character agents (Character-LLM, RoleLLM, OpenCharacter, CoSER) that bake a character's experiences into weights, and retrieval/prompt-based roleplay evaluated by benchmarks like CharacterEval, CharacterBench, and PingPong. For BookRAG, the interesting gap is *progressive knowledge* - none of these systems condition a character's knowledge on reader-cursor, which maps cleanly onto BookRAG's existing fog-of-war infrastructure and would enable "talk to Scrooge as of chapter 3" as a first-class query mode.

**Dialogue-agent foundations:** Commercial systems like Character.AI popularized LLM roleplay via system-prompt persona cards; production LLMs (GPT-4, Claude) roleplay adequately with a persona prompt alone, but lose consistency across long sessions and hallucinate out-of-character knowledge. PersonaChat (Zhang et al. ACL 2018, "Personalizing Dialogue Agents: I have a dog, do you have pets too?") was the seminal dataset: 10K crowd-sourced conversations where each speaker was assigned a 5-sentence persona card, establishing persona-grounded generation as a task (https://aclanthology.org/P18-1205/). LIGHT (Urbanek, Fan et al. EMNLP 2019) extended this into a grounded fantasy world with 663 locations, 1755 character types, and 11K episodes of combined speech+action, demonstrating that character grounding benefits from environment + relationship context, not just traits (https://parl.ai/projects/light/).

**RoleLLM / Character-LLM / CharacterEval:** RoleLLM (Wang et al. arXiv 2310.00746, ACL 2024 Findings) introduced the four-stage recipe now standard in the field: role profile construction (100 roles), Context-Instruct for role-specific knowledge extraction, RoleGPT for style imitation via GPT-4 prompting, and RoCIT (Role-Conditioned Instruction Tuning) to distil the GPT-4 teacher into open RoleLLaMA/RoleGLM - producing RoleBench (168,093 samples) as the first fine-grained character benchmark (https://arxiv.org/abs/2310.00746). Character-LLM (Shao et al. EMNLP 2023) trains a separate 7B model *per character* (Beethoven, Cleopatra, Caesar), using synthesized "experiences" from biographical profiles and introducing "protective experiences" to align the model against anachronistic knowledge leakage (https://aclanthology.org/2023.emnlp-main.814/). CharacterEval (ACL 2024) is the Chinese evaluation standard: 1,785 multi-turn dialogues, 23,020 examples, 77 characters from Chinese novels/scripts, scored on 13 metrics across 4 dimensions (conversational ability, character consistency, role-playing attractiveness, personality back-testing) with a trained reward model CharacterRM that correlates better with humans than GPT-4 does (https://aclanthology.org/2024.acl-long.638/). CharacterBench (AAAI 2025, arXiv 2412.11912) scales to 22,859 annotated samples across 3,956 characters bilingually.

**Retrieval-augmented persona:** Rather than per-character fine-tuning, RAG approaches retrieve relevant past dialogue snippets, trait statements, or wiki facts into the prompt at inference time. Advantages: one base model serves any character (matches BookRAG's architecture), persona updates are just KG edits, and scoping by chapter is trivial. Trade-off vs Character-LLM fine-tuning: style mimicry is weaker (the base LLM's voice leaks through) and retrieval must be tuned to surface idiosyncratic speech samples, not just facts.

**Persona extraction from novels:** CoSER (arXiv 2502.09082, 2025) extracts authentic multi-character dialogues from 771 renowned books via an LLM pipeline and trains/evaluates open persona models on them - the closest prior art to a BookRAG "persona card from a novel" extractor. OpenCharacter (arXiv 2501.15427) trains role-playing LLMs from large-scale *synthetic* persona profiles (name, age, race, appearance, experience, personality) - fine-tuned 8B models approach GPT-4o quality on role-play. CroSS (EMNLP 2024, "Evaluating Character Understanding of LLMs") decomposes a main character into four canonical dimensions: Attributes, Relationships, Events, Personality - a directly usable schema for BookRAG's Character DataPoint extension.

**Quote-conditioned dialogue:** The Project Dialogism Novel Corpus (PDNC, arXiv 2204.05836) annotates 35,978 quotations across 22 novels with speaker, addressees, quote type, and in-quote character mentions - precisely the scaffold needed to train a character on *their own words only* vs the surrounding narration. Improving Quotation Attribution with Fictional Character Embeddings (arXiv 2406.11368) learns character embeddings that boost attribution and implicitly encode speech style. Combining PDNC-style attribution with BookNLP's quote spans (already in BookRAG's pipeline) yields a per-character `voice_corpus: List[Quote]` suitable either as RAG retrieval targets or as a quote-conditioned fine-tuning set.

**Voice / style replication:** Style transfer for persona is an active subfield - "Enhancing Consistency and Role-Specific Knowledge Capturing by Rebuilding Fictional Character's Persona" (arXiv 2405.19778, 2024) and "Enhancing Persona Following at Decoding Time via Dynamic Importance Estimation" (2025) shift from training-time persona injection to decoding-time control, re-weighting logits toward persona-aligned tokens - cheaper than per-character fine-tuning.

**Progressive character knowledge (fog-of-war for persona):** This is the unclaimed territory. None of the surveyed benchmarks (CharacterEval, CharacterBench, PingPong, RoleBench) condition the character's knowledge state on story progress. A Scrooge at chapter 3 has not yet seen the Ghosts of Christmas; a chapter-10 Scrooge has. BookRAG already has `last_known_chapter` per node and a chapter cursor - extending this into "character subjective state at cursor C" is a plausible first-of-kind feature. Closest adjacent work: "Character is Destiny: Can LLMs Simulate Persona-Driven Decisions in Role-Playing?" (arXiv 2404.12138) examines whether an LLM character acts consistently with their in-novel persona at decision points, but without cursor conditioning.

**Theory of mind for characters:** FANToM (Kim et al. EMNLP 2023, arXiv 2310.15421) stress-tests machine ToM over information-asymmetric conversations: BeliefQ, AnswerabilityQ, InfoAccessQ - all probing "who knows what." GPT-4 scored 26.6% (CoT) vs humans at 87.5%, a >60-point gap (https://aclanthology.org/2023.emnlp-main.890/). BigToM builds synthetic belief-change narratives (desires/actions/beliefs + state-changing events) and is now saturated (GPT-4o ~82%, Gemini 2.0 ~86%). ToMi and OpenToM complete the benchmark suite. The "Plug-and-Play Multi-Character Belief Tracker" (ACL 2023, arXiv 2306.00924) is especially relevant: it maintains explicit per-character belief states as a side-channel to the LLM - essentially a per-character `knowledge_state` dict, exactly what a cursor-aware persona would need.

**Character consistency metrics:** CharacterEval's 13 metrics split persona fidelity into *knowledge consistency* (exposure, accuracy, hallucination) and *persona consistency* (behavior, utterance). PingPong (arXiv 2409.06820, 2024) uses three judge-LLM criteria: character consistency, entertainment value, language fluency, with an *interrogator* LLM actively probing the player across 64 conversations x 8 characters x 8 situations - strong correlation with human judgment. PersonaLLM (NAACL 2024 Findings) measures whether persona-assigned LLMs produce text with the linguistic signatures of the claimed Big-5 personality, finding emergent style markers.

**Worldbuilding / fandom personas:** PersonaChat's crowd personas and LIGHT's role-cards were hand-authored; modern work scrapes fandom wikis (e.g., FandomChat-style corpora used by RoleLLM's profile construction) for pre-built personas of fictional characters. For BookRAG this is the fallback when the book itself is too sparse - external wiki enrichment, flagged for spoilers.

**BookRAG's current Character DataPoint - what a persona upgrade looks like:** Current fields: name, aliases, description, first_chapter, last_known_chapter, chapters_present. A persona-oriented extension (inspired by CroSS's four dimensions + PDNC quotes + Plug-and-Play belief tracker):
- `voice_corpus: List[Quote]` - quoted dialogue spans with chapter index (from BookNLP quotes + PDNC-style attribution), filterable to `quote.chapter <= cursor`.
- `traits_per_cursor: Dict[int, List[str]]` - personality adjectives as of chapter N (already implicitly present via per-identity snapshots from Phase 2; surface them explicitly).
- `relationships_subjective: Dict[other_id, Dict[int, str]]` - how THIS character describes other_id at chapter N (distinct from the objective Relationship edge; captures Scrooge's view of Fred shifting across the book).
- `knowledge_state: Dict[int, Set[fact_id]]` - facts the character has been on-page-present for, derived by intersecting PlotEvent.chapter with Character.chapters_present.
- `speech_style_summary: str` - short LLM-generated summary of voice (formal/curt/sarcastic), cached per cursor.

**Concrete persona-mode for BookRAG:** New endpoint `POST /books/{id}/characters/{name}/chat` with body `{cursor: {chapter, paragraph?}, message: str, session_id?: str}`. Implementation:
1. Load latest Character snapshot whose `effective_latest_chapter <= cursor.chapter` (reuse `load_allowed_nodes`).
2. Build per-character retrieval index: quotes filtered to `chapter <= cursor`, relationships filtered to same bound, PlotEvents where this character is a participant.
3. System prompt: "You are {name}. Speak only as of chapter {cursor.chapter}. Refuse to discuss anything from later in the story. Here is what you know:" + retrieved traits + quote exemplars + subjective relationships.
4. For each user turn, retrieve top-k quotes matching the user's message (style anchors) + top-k relevant PlotEvents + the character's subjective view of any other character mentioned.
5. Judge-side: run a PingPong-style consistency check (is the response using any fact whose `effective_latest_chapter > cursor.chapter`? If so, reject and regenerate.) This reuses BookRAG's existing spoiler-filter logic as a post-hoc persona consistency checker - a nice reuse because the same `effective_latest_chapter` bound that protects the reader also protects the character's knowledge state.
6. Session memory scoped to `(book_id, character, cursor, session_id)` in a lightweight JSON store like reading_progress.

**Key citations:**
1. Zhang et al. "Personalizing Dialogue Agents: I have a dog, do you have pets too?" ACL 2018. https://aclanthology.org/P18-1205/
2. Urbanek, Fan et al. "Learning to Speak and Act in a Fantasy Text Adventure Game" (LIGHT). EMNLP 2019. https://parl.ai/projects/light/
3. Wang et al. "RoleLLM: Benchmarking, Eliciting, and Enhancing Role-Playing Abilities of LLMs." arXiv 2310.00746, ACL 2024 Findings. https://arxiv.org/abs/2310.00746
4. Shao et al. "Character-LLM: A Trainable Agent for Role-Playing." EMNLP 2023. https://aclanthology.org/2023.emnlp-main.814/
5. Tu et al. "CharacterEval: A Chinese Benchmark for Role-Playing Conversational Agent Evaluation." ACL 2024. https://aclanthology.org/2024.acl-long.638/
6. Zhou et al. "CharacterBench: Benchmarking Character Customization of LLMs." AAAI 2025, arXiv 2412.11912. https://arxiv.org/html/2412.11912v1
7. Kim et al. "FANToM: A Benchmark for Stress-testing Machine Theory of Mind in Interactions." EMNLP 2023, arXiv 2310.15421. https://aclanthology.org/2023.emnlp-main.890/
8. Sclar et al. "Minding Language Models' (Lack of) Theory of Mind: A Plug-and-Play Multi-Character Belief Tracker." ACL 2023, arXiv 2306.00924. https://aclanthology.org/2023.acl-long.780/
9. Vishnubhotla et al. "The Project Dialogism Novel Corpus (PDNC)." arXiv 2204.05836, 2022. https://arxiv.org/abs/2204.05836
10. Michel et al. "Improving Quotation Attribution with Fictional Character Embeddings." arXiv 2406.11368, 2024. https://arxiv.org/pdf/2406.11368
11. Gusev. "PingPong: A Benchmark for Role-Playing Language Models with User Emulation and Multi-Model Evaluation." arXiv 2409.06820, 2024. https://arxiv.org/abs/2409.06820
12. Wang et al. "OpenCharacter: Training Customizable Role-Playing LLMs with Large-Scale Synthetic Personas." arXiv 2501.15427, 2025. https://arxiv.org/html/2501.15427v1
13. Wang et al. "CoSER: Coordinating LLM-Based Persona Simulation of Established Roles." arXiv 2502.09082, 2025. https://arxiv.org/html/2502.09082v1
14. "Evaluating Character Understanding of LLMs" (CroSS dataset). EMNLP 2024. https://aclanthology.org/2024.emnlp-main.456.pdf
15. Jiang et al. "PersonaLLM: Investigating the Ability of LLMs to Express Personality Traits." NAACL 2024 Findings. https://aclanthology.org/2024.findings-naacl.229/
16. Xu et al. "Character is Destiny: Can LLMs Simulate Persona-Driven Decisions in Role-Playing?" arXiv 2404.12138, 2024. https://arxiv.org/html/2404.12138v1

**Concrete ideas worth stealing:**
- Adopt CroSS's four-dimension decomposition (Attributes / Relationships / Events / Personality) as the schema for an extended Character DataPoint; each dimension lists evidence chapter indices for cursor filtering.
- Use PDNC-style quote attribution + BookRAG's existing BookNLP quote spans to build a per-character `voice_corpus`; retrieve top-k quotes below the cursor as style exemplars in persona-chat prompts.
- Mirror RoleLLM's RoCIT pipeline at the book level: teacher (GPT-4o) generates persona-consistent chat samples per character per cursor, student (local 7B from iteration 18's distillation plan) is tuned on them - one student checkpoint per major character becomes optional premium content.
- Apply PingPong's interrogator+judge architecture as a CI eval: BookRAG ships with a test suite of 8 situations x 5 major Christmas Carol characters x 3 cursor positions, auto-scored on character consistency and spoiler leakage.
- Implement the Plug-and-Play Multi-Character Belief Tracker as BookRAG's `knowledge_state` side-channel: an explicit `Dict[character_id, Dict[chapter, Set[fact_id]]]` computed from PlotEvent participation, used to post-hoc verify that no persona-chat response references a fact the character could not know.
- Reuse `spoiler_filter.load_allowed_nodes` unchanged for persona-knowledge scoping - the same `effective_latest_chapter <= bound` rule that protects the reader also defines what the character knows. This is a one-line reuse of existing infrastructure for a genuinely novel feature.
- FANToM-style eval: for each major character at cursor C, ask "What does {character} believe about {fact revealed at chapter C+5}?" - correct answer is "unknown" or a pre-C belief. Use the 70-point gap on FANToM as a proxy to track BookRAG's improvements.
- Offer `batch_size: 1` ingestion as the "persona-ready" mode: per-chapter snapshots are the granularity needed for cursor-scoped persona views; advertise this explicitly in docs as the trade-off for enabling persona-chat mode.

### 20. Commercial graph-RAG platforms

**Researched:** 2026-04-22 (iteration 20)

**TL;DR:** The 2024-2026 commercial graph-RAG landscape is dominated by three plays: (1) hyperscaler bundles (AWS Bedrock+Neptune Analytics, Azure AI Search+GraphRAG+Fabric, GCP via Neo4j partnerships) that auto-build graphs from document ingest with zero graph modeling required, (2) specialist KG vendors (Stardog Voicebox, Neo4j Aura, WhyHow.AI, Writer Knowledge Graph) that lead with graph-first architecture and proprietary extraction, and (3) enterprise-search platforms (Glean, Vectara) that treat the graph as a permissioned identity+content substrate rather than a narrative knowledge model. None target serialized-fiction spoiler-aware retrieval; all optimize for "latest truth over a corporate corpus" where freshness beats temporal faithfulness.

**Platforms:**

- **Stardog Voicebox** [1][2][3]: Conversational LLM layer over Stardog's enterprise semantic graph (RDF/OWL), GA March 2024, "hallucination-free" marketing tied to KG-grounded answers. Architecture: Voicebox as agentic front-end to Stardog Cloud; knowledge graph + inference engine + NL2SPARQL. Pricing is enterprise-only, contact-sales. Differentiator: W3C-standard semantic layer (OWL reasoning, SHACL constraints) - closest to BookRAG's OWL ontology-discovery step. Literature fit: weak - positioned for regulated industries (finance, pharma, gov).

- **Neo4j Aura + GraphRAG** [4][5][6][7]: Managed Neo4j DBaaS plus the official `neo4j-graphrag` Python package (renamed from `neo4j-genai`). Aura Agent (EAP across Free/Pro/Business Critical tiers, GA late 2025) is a point-and-click GraphRAG agent builder. Pricing: Professional $65/GB/month, Business Critical $146/GB/month, pauseable instances save ~80%. Differentiator: first-party retrievers (vector, hybrid, text2cypher, graph-traversal) + Microsoft Agent Framework integration. Literature fit: technically fine (Neo4j has LOTR/GoT demo graphs) but no literature-specific product.

- **WhyHow.AI** [8][9][10]: KG Studio platform (open-sourced 2024), "small graphs" philosophy - many scoped graphs per agent rather than one monolithic KG. Proprietary query engine bypasses Text2Cypher, claims ~2x retrieval accuracy vs. LangChain's LLMGraphTransformer on same graph. Pricing: open-source core + managed SaaS (contact sales). Differentiator: opinionated extraction + rule-based entity resolution + schema library. Literature fit: the "small graphs" model is the closest philosophical match to BookRAG's per-book-per-cursor snapshots - a book could literally be a WhyHow "small graph."

- **Writer.com Palmyra + Knowledge Graph** [11][12][13]: Writer's vertically-integrated stack: Palmyra X5 LLM (1M-token context) + Knowledge Graph + AI Studio. Graph-based RAG pitched as "67% lower cost" vs. traditional vector RAG; graph built by a specialized "Writer graph LLM" at ingest. Pricing: Enterprise custom, typical $75K-$250K/yr mid-market, $500K+ large. Differentiator: single-vendor stack, own LLM trained to talk to own graph. Literature fit: none - positioned for marketing/legal/HR content generation.

- **Vectara** [14][15]: Fully managed RAG SaaS with hybrid search (BM25+dense+MMR), hallucination detection (HHEM), 2025 open-source RAG eval framework. Vectara's 2025 platform mentions "graph-aware summaries" and multi-modal KG integration but graph is not a first-class primitive - it's a feature layered on their vector index. Differentiator: hallucination-detection models and eval tooling. Literature fit: weak; generic document RAG.

- **Glean** [16][17][18][19]: $200M ARR, $7.2B valuation (June 2025 Series F). "Enterprise Graph" = permissions-aware graph over 100+ SaaS connectors linking people+content+activity. Pricing: ~$50/user/month, ~100-user minimum, $50-60K annual floor, +$15/user for "Work AI" GenAI add-on; large deployments $240K+. Differentiator: identity/ACL-aware retrieval and personalized ranking from user-interaction signals. Literature fit: none - enterprise intranet search, not narrative KG.

- **Microsoft Azure AI Search + GraphRAG + Fabric** [20][21][22]: Azure AI Search as vector store, Microsoft Research's open-source `graphrag` library (v2.0, Oct 2025) for community-detection graph building, Fabric SQL DB with GraphQL+MCP for structured retrieval, Cosmos DB AI Graphs. Neo4j+Fabric partnership for Spark-loaded graphs. Pricing: Azure AI Search tiered ($0 Free / $75+ Basic / S1+ scale tiers), graphrag library free, LLM calls pass-through. Differentiator: the original "community report" GraphRAG paper pattern productized. Literature fit: the MS GraphRAG paper uses "A Christmas Carol" as a literal demo corpus - BookRAG shares the test-bed.

- **AWS Neptune Analytics + Bedrock Knowledge Bases GraphRAG** [23][24]: GA March 2025. Knowledge Bases auto-extracts entities/relations from S3 docs, stores in Neptune Analytics (vector+graph in one engine), combines vector similarity + graph traversal at query. Pricing: Neptune Analytics per m-NCU-hour + Bedrock per-token + S3. Differentiator: "few clicks, no graph modeling" setup - the fastest zero-to-GraphRAG in a hyperscaler. Literature fit: generic; no narrative-specific tooling.

- **MongoDB Atlas Vector Search + `$graphLookup`** [25][26]: Vector index + aggregation-framework graph traversal in one store. Official GraphRAG + LangChain tutorial (2025). September 2025: vector search extended to self-hosted Community/Enterprise. Pricing: Atlas per-cluster. Differentiator: single document DB handles vectors, documents, and graph traversal without a separate graph engine. Literature fit: could host a BookRAG-style per-book namespace cheaply; no built-in extraction.

- **Databricks Mosaic AI Vector Search + Unity Catalog** [27]: Vector indexes as UC entities, governance + lineage baked in, managed MCP servers (2025). No native graph engine - graph-style retrieval requires external Neo4j/Neptune or DIY Delta-table joins. Differentiator: governance, lineage, Delta-table coupling. Literature fit: weak; enterprise data-platform play.

- **Diffbot GraphRAG LLM** [28][29]: Jan 2025 launch of Diffbot LLM (fine-tuned Llama 3.3 70B / 8B) grounded in Diffbot's 10B-entity / 1T-fact web knowledge graph. Open-source weights + public `diffy.chat` demo. Pricing: credit-based KG API plans. Differentiator: the graph IS the web, not a private corpus; LLM trained to be a tool-using graph querier. Literature fit: useful as an *external* wiki-enrichment sidecar for BookRAG (author/book/fandom facts) but spoiler-dangerous by default.

- **Pinecone / Cohere / Anthropic (vector-only contrast)**: Pinecone remains vector-pure; Cohere and Anthropic are model vendors, not graph-RAG platforms. Relevant only as the "why add a graph?" counterfactual.

**Architectural patterns that cross platforms:**
- Auto-extraction pipeline: doc ingest -> LLM-driven entity+relation extraction -> graph store + vector store -> hybrid retrieval at query.
- Dual-index retrieval: vector similarity for candidate seeding + graph traversal (k-hop, community, or Cypher path) for expansion.
- "Community report" summarization (MS GraphRAG pattern) is the most replicated idea.
- Managed graph engines are converging on vector+graph in one store (Neptune Analytics, Neo4j vector index, MongoDB, Kuzu/LanceDB for OSS).
- Permissions/ACL propagation through the graph (Glean, Writer, Databricks UC) is enterprise table-stakes but irrelevant for single-reader book apps.

**Pricing & cost models:**
- **Per-GB graph storage**: Neo4j Aura $65-$146/GB/mo is the public anchor.
- **Per-seat**: Glean ~$50/user/mo + $15 Work AI add-on; Writer custom ($75K-$500K+/yr typical).
- **Consumption**: Bedrock KB GraphRAG = Neptune NCU-hour + Bedrock tokens; Azure = AI Search tier + LLM pass-through.
- **Credit-based**: Diffbot (KG API credits).
- **Contact-sales opaque**: Stardog, WhyHow, Writer Enterprise, Glean.

**Book/literature coverage:** None of the commercial platforms ship a literature vertical. Microsoft's GraphRAG paper famously uses *A Christmas Carol*, but as a demo, not a product line. Neo4j has fandom demo graphs (LOTR, GoT) in its developer marketing but no literary SKU. Diffbot's KG indexes books-about-books (Wikipedia/fandom wikis) but not the books themselves. Publishers (Penguin Random House, HarperCollins) and media (Netflix, Disney) likely use Glean/Writer internally for operational knowledge, not for reader-facing narrative Q&A.

**Strengths of commercial platforms:**
- Zero-to-graph in minutes (Bedrock KB, Aura Agent) removes the hardest part of BookRAG's pipeline.
- Governance, ACLs, audit logs, SOC2 - enterprise buyers require these.
- First-party LLM+KG integration (Writer Palmyra, Diffbot LLM) proves vertically-tuned small models beat general LLMs on their own graph.
- Managed vector+graph in one store (Neptune Analytics, MongoDB) matches BookRAG's Kuzu+LanceDB combo philosophically.
- Eval tooling is getting real (Vectara's 2025 OSS RAG eval, Neo4j's retrievers benchmark).

**Gaps for BookRAG's niche:**
- No spoiler-aware / cursor-scoped retrieval. Every platform assumes "latest graph = truth"; BookRAG's `effective_latest_chapter` filter has no commercial analogue.
- No temporal snapshot model. Platforms update graphs destructively; BookRAG's per-identity snapshot selection has no parallel.
- Narrative structure is absent - no Scene/Quote/POV/NarrativeEvent primitives in any commercial schema.
- Consumer/indie pricing tier is missing entirely; floors of $50K+ annual preclude hobbyist or single-reader deployments.
- Fiction-specific extraction (quoted dialogue, coreference across long texts, unreliable narrator handling) is not a shipped product anywhere.

**Positioning takeaway for BookRAG:** BookRAG's differentiator is not graph construction (commoditized) or LLM quality (rented) but the *temporal cursor* and *narrative schema*. An OSS, pip-installable "spoiler-safe book-KG" library fills a zero-revenue but high-signal niche that no vendor will touch (fiction readers won't pay $50K/yr). The defensible moat is the ontology (Character/PlotEvent/Quote/POV with chapter-indexed snapshots) and the filter algebra (`effective_latest_chapter <= bound` with per-identity latest-snapshot selection), both of which could become a spec that commercial platforms later adopt for serialized/episodic content (TV writing rooms, game narrative design, comics).

**Key citations:**
1. Stardog Voicebox product page. https://www.stardog.com/voicebox/
2. VentureBeat, "Stardog launches Voicebox" (2024). https://venturebeat.com/ai/stardog-launches-voicebox-an-llm-powered-layer-to-query-enterprise-data
3. Stardog pricing. https://www.stardog.com/pricing/
4. Neo4j Aura Agent blog (2025). https://neo4j.com/blog/genai/build-context-aware-graphrag-agent/
5. neo4j-graphrag Python package docs. https://neo4j.com/docs/neo4j-graphrag-python/current/
6. Neo4j pricing. https://neo4j.com/pricing/
7. Microsoft Agent Framework + Neo4j GraphRAG. https://learn.microsoft.com/en-us/agent-framework/integrations/neo4j-graphrag
8. WhyHow.AI KG Studio (Medium). https://medium.com/enterprise-rag/choosing-the-whyhow-ai-knowledge-graph-studio-8ed38f1820c3
9. WhyHow KG Studio GitHub. https://github.com/whyhow-ai/knowledge-graph-studio
10. WhyHow KG Studio Beta blog. https://medium.com/enterprise-rag/whyhow-ai-kg-studio-platform-beta-rag-native-graphs-1105e5a84ff2
11. Writer Knowledge Graph product page. https://writer.com/product/graph-based-rag/
12. Writer Palmyra X5. https://writer.com/llms/palmyra-x5/
13. Writer plans. https://writer.com/plans/
14. Vectara 2025 RAG predictions. https://www.vectara.com/blog/top-enterprise-rag-predictions
15. Vectara launches OSS RAG eval (SiliconANGLE, Apr 2025). https://siliconangle.com/2025/04/08/vectara-launches-open-source-framework-evaluate-enterprise-rag-systems/
16. Glean Knowledge Graph guide. https://www.glean.com/resources/guides/glean-knowledge-graph
17. Glean Enterprise Graph product page. https://www.glean.com/product/enterprise-graph
18. Futurum, "Glean Doubles ARR to $200M" (2025). https://futurumgroup.com/insights/glean-doubles-arr-to-200m-can-its-knowledge-graph-beat-copilot/
19. Glean pricing analysis (eesel). https://www.eesel.ai/blog/glean-pricing
20. Microsoft Tech Community, "The Future of AI: GraphRAG." https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/the-future-of-ai-graphrag-%E2%80%93-a-better-way-to-query-interlinked-documents/4287182
21. Azure Cosmos DB AI Knowledge Graphs. https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/cosmos-ai-graph
22. Fabric SQL + GraphQL + MCP. https://blog.fabric.microsoft.com/en-us/blog/ai-ready-apps-from-rag-to-chat-interacting-with-sql-database-in-microsoft-fabric-using-graphql-and-mcp
23. AWS Bedrock GraphRAG GA (March 2025). https://aws.amazon.com/about-aws/whats-new/2025/03/amazon-bedrock-knowledge-bases-graphrag-generally-available/
24. AWS GraphRAG architecture blog. https://aws.amazon.com/blogs/machine-learning/build-graphrag-applications-using-amazon-bedrock-knowledge-bases/
25. MongoDB GraphRAG with LangChain. https://www.mongodb.com/docs/atlas/ai-integrations/langchain/graph-rag/
26. MongoDB Atlas Vector Search overview. https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/
27. Databricks Mosaic AI Vector Search docs. https://docs.databricks.com/aws/en/vector-search/vector-search
28. Diffbot GraphRAG LLM launch (Jan 2025). https://www.diffbot.com/company/news/20250109.html
29. Diffbot pricing. https://www.diffbot.com/pricing/

**Concrete ideas worth stealing:**
- Borrow Neo4j's retriever taxonomy (vector / hybrid / text2cypher / graph-traversal / community-report) as BookRAG's internal retrieval-mode enum, so `POST /books/{id}/query` can expose `mode=graph_traversal` vs. `mode=hybrid` explicitly.
- Adopt WhyHow's "small graphs" framing in BookRAG docs: each book is a self-contained small graph; multi-book libraries are agent-orchestrated federations - this is a clean narrative for why BookRAG isn't trying to be Neo4j.
- Copy Bedrock KB's "one click, no graph modeling" UX for the upload flow: status page should show "extracting entities -> building graph -> indexing" as named stages, matching the mental model commercial users already have.
- Copy Writer's claim framing - "graph-RAG is cheaper than vector-RAG at scale" - but invert: "graph-RAG is *more faithful* than vector-RAG for serialized fiction." Use the same benchmark-style blog post format.
- Mirror Vectara's 2025 OSS RAG eval harness pattern: ship a BookRAG eval CLI (`bookrag eval --book christmas-carol --cursor chapter:3`) that runs the golden Q&A set, reports spoiler-leak rate + answer faithfulness, and prints a grade. Commercial platforms are starting to treat eval as a first-class product surface.
- Adopt Glean's permissions-aware retrieval *mechanism* for a new purpose: instead of user ACLs, the "permission" is `cursor.chapter`, and every node carries an `effective_latest_chapter` label that the retriever filters on. This reframes BookRAG's spoiler filter as a narrow case of a general permissioned-retrieval pattern, which is useful for docs and for future multi-reader scenarios.
- Position `batch_size: 1` ingestion as "persona-ready / cursor-faithful mode" in marketing copy, analogous to Neo4j's Business Critical tier vs. Professional - a premium fidelity setting.
- Ship a Diffbot-style external-wiki sidecar with explicit spoiler filtering: an optional enrichment layer that hits Wikipedia/Wikidata but strips any fact with a `publication_date` or `plot_chapter` beyond the cursor. This is a genuinely new feature no commercial platform has.

### 21. Streaming / incremental KG updates

**Researched:** 2026-04-22 (iteration 21)

**TL;DR:** Incremental KG construction has matured dramatically in 2024-2026: LightRAG (set-union merge), Microsoft GraphRAG 1.0 (`update` CLI with delta merging), Graphiti/Zep (bi-temporal edge invalidation), and new 2025 entrants (iText2KG, DIAL-KG, ATOM) all skip full rebuilds. For serialized content (web serials, weekly TV episodes, per-chapter reader progress), the right pattern is an append-only extraction log keyed by `(book_id, chunk_ordinal)` plus per-identity snapshots — BookRAG already has half of this and can wire up the other half without architectural upheaval.

**Incremental extraction vs full rebuild:**
Full rebuild recomputes entities, coref, ontology, batching, LLM extraction, and embeddings over N chapters when only chapter N+1 is new. The work genuinely avoidable per new chapter: re-extraction of chapters 1..N, recomputation of their embeddings, and re-clustering of unaffected communities. Dependency analysis: a new chapter can (a) introduce brand-new entities, (b) add properties/relations to existing entities, (c) invalidate prior facts (e.g., "King dies in ch 17" invalidates the "King rules" edge from ch 3). Only (b) and (c) touch existing nodes, so the incremental cost should be O(|new-chunk| × |touched-entities|), not O(|corpus|) [1,6].

**LightRAG's incremental model (from iteration 2):**
LightRAG processes each new document through the same graph-indexing steps to produce a subgraph (V', E'), then merges by **set union** on node and edge sets with the existing graph. Identical entities/relations are deduplicated; LLM summaries on touched nodes are re-generated only for nodes whose neighborhood changed. Reported ~50% reduction in update time vs rebuild. Strength: simple, cheap, preserves historical connections. Weakness: no explicit invalidation — if ch 17 contradicts ch 3, both edges coexist unless a temporal model is layered on top [1].

**GraphRAG's recent incremental work:**
Microsoft GraphRAG 1.0 (released late 2024) shipped a CLI `update` subcommand that computes deltas between an existing index and newly added content, merging intelligently with consistent entity IDs so database upserts (rather than delete-and-reload) work. Key caveat: adding genuinely new content can alter **community structure**, and community summaries are the expensive part of GraphRAG indexing. The `update` command partially recomputes affected communities rather than all of them, and v0.4.0 introduced "standard-update" and "fast-update" indexing methods to trade quality for speed. Recomputation is still non-trivial for significant new content volumes [2,7].

**Streaming event processing analogies:**
Apache Flink and Kafka Streams aren't typically applied to narrative KGs, but the **event-sourced** pattern is directly relevant: treat each chapter as an immutable event appended to a topic, materialize the KG as a derived view, and reprocess by replaying the log. Graphiti explicitly adopts this vocabulary — "episodes" are ingested events, and the graph is the materialized projection [4].

**Continual learning for KG embeddings:**
ContinualGNN (Wang et al., CIKM 2020 — the query said KDD but venue is CIKM) is a streaming GNN that uses replay strategies: **novel pattern detection** (importance-weighted sampling of new nodes whose attributes differ sharply from neighbors) and **old pattern preservation** (experience replay to fight catastrophic forgetting). Later surveys (Continual Graph Learning, arXiv 2301.12230 and 2402.06330) catalog regularization-based, replay-based, and architectural methods. Relevant to BookRAG only if we adopt learned graph embeddings for retrieval — current LanceDB embeddings are per-node vectors with no temporal drift handling [3].

**Temporal-snapshot graphs:**
- **TerminusDB** uses a Git-like immutable-layer store: each commit is a delta layer, "time-travel" queries specify a commit ID, and the query engine reconstructs the graph as-of that revision. Two time dimensions: **valid time** (when a fact is true in the world) as data, **transaction time** (when it entered the DB) on the commit graph [5].
- **Graphiti/Zep** (iteration 10) implements bi-temporal edges with explicit `(t_valid, t_invalid)` intervals. New episodes can invalidate old edges rather than delete them, producing point-in-time queries [4].
- **Dgraph** supports temporal edges via user-schema date fields but lacks native bi-temporal semantics.

**Snapshot-vs-stream tradeoff:**
Storing a full KG snapshot per chapter is O(N × |KG|) storage — untenable for long series. Replaying from an event log on demand is O(|log|) latency per query. The **hybrid** pattern materializes snapshots at decision points the user actually queries (e.g., every 5 chapters or end-of-arc) and reconstructs cold intermediate states via log replay. BookRAG already implicitly does a version of this: per-identity snapshots are stored keyed by `(identity, batch)` so the "latest ≤ cursor" query is O(|batches containing identity|) with no per-chapter materialization [current codebase].

**Consistency / idempotence guarantees:**
If chapter 7 is re-ingested (extractor upgrade), naive merging double-counts. Strategies: (a) **last-write-wins** keyed by `(node_id, source_chunk)` — simplest, preserved by GraphRAG 1.0's consistent-ID scheme; (b) **max-confidence** — keep the extraction with highest LLM confidence score; (c) **LLM-reconciliation** — pass both candidates to an adjudicator LLM (DIAL-KG's "governance adjudication" module); (d) **append-only with dedup at read-time** — store everything, dedupe on query. iText2KG handles this via entity/relation resolution before merge [6,8].

**Serialized content domains:**
I found no published KG systems targeting Royal Road, AO3, or Substack serial fiction. The closest analogues: AutoPKG for continuously evolving e-commerce product graphs, and podcast-transcript KGs in enterprise contexts. Fan wikis (MediaWiki + SMW) do something like per-chapter spoiler tagging manually. BookRAG is genuinely in under-explored territory here — serialized-narrative + reader-progress-aware retrieval has no commercial competitor [8,9].

**Cold-start problem:**
For series (Red Rising has 6 books), book N extraction benefits from book N-1's entity resolution: "Darrow" in book 2 should link to the same node as book 1. Approaches: (a) author/curator-provided alias map, (b) cross-book embedding similarity + LLM adjudication, (c) hierarchical graph with series → book → chapter namespaces where book-level nodes inherit series-level identities. Graphiti's "group_id" feature implements (c) natively [4].

**BookRAG's current state:**
Full rebuild per book; no `update` command; no cross-book linking. The per-identity snapshot store (Phase 2, shipped 2026-04-21) is keyed by `(identity, batch)` but is not tied to an event log — snapshots are rebuilt from `data/processed/{book_id}/batches/*.json` at query time. Effectively we have snapshot-on-demand over a per-batch event log already; we just don't expose incremental extraction.

**Concrete incremental design for BookRAG:**
1. **Append-only extraction log** keyed by `(book_id, chapter_ordinal, chunk_ordinal)` written to `data/processed/{book_id}/extractions.jsonl`. Each record: raw chunk text, BookNLP annotations, extraction timestamp, extractor version, LLM-produced DataPoints.
2. **`re-ingest-chapter K`** CLI: replays log for chunks < K (no re-extraction), re-extracts chapter K only, runs the per-identity merge into the snapshot store. Phase 1 (BookNLP) can be skipped for unchanged chapters since BookNLP output is already cached on disk.
3. **`update` command** (new chapter arrives): append to log, run Phase 2 on the new batch, merge into snapshots. No coref re-run needed beyond the new chapter unless pronouns cross chapter boundaries (rare; BookNLP doesn't cross boundaries anyway).
4. **Extractor version field** on each record — when prompt/model changes, bump version; a "refresh" command replays extraction only for records with stale version.
5. **Cross-book series support**: add `series_id` to `models/config.py`, store an author-provided alias map at `data/series/{series_id}/aliases.json`, and at retrieval time merge identity namespaces.
6. **Bi-temporal edges** (optional, future): add `(first_chapter, last_known_chapter, invalidated_at_chapter)` to Relationship DataPoints — lets the spoiler filter serve "as of chapter K" without re-ranking.

**Key citations:**
1. LightRAG, EMNLP 2025 — arxiv.org/pdf/2410.05779 (incremental set-union merge, §3.2)
2. Microsoft GraphRAG 1.0 blog — microsoft.com/en-us/research/blog/moving-to-graphrag-1-0 and issues/741 (update CLI, consistent entity IDs)
3. ContinualGNN, Wang et al., CIKM 2020 — github.com/Junshan-Wang/ContinualGNN; survey arXiv:2301.12230
4. Zep/Graphiti bi-temporal, arXiv:2501.13956 — help.getzep.com/graphiti (episodes, group_id, t_valid/t_invalid)
5. TerminusDB — terminusdb.org/docs (immutable layer store, WOQL time-travel); Semertzidis "Time Traveling in Graphs", ceur-ws.org/Vol-1558/paper21.pdf
6. iText2KG, arXiv:2409.03284 (zero-shot incremental KG, entity/relation resolution before merge)
7. GraphRAG 0.4.0 incremental + DRIFT, ai-engineering-trend.medium.com; github.com/microsoft/graphrag/discussions/511
8. DIAL-KG, arXiv:2603.20059 (schema-free incremental + evolution-intent assessment)
9. AutoPKG, arXiv:2604.16950 (continually evolving product KG, multimodal)
10. ATOM dynamic temporal KG — cited in arXiv:2510.20345 LLM-KG construction survey

**Concrete ideas worth stealing:**
- **GraphRAG's consistent entity IDs** — deterministic hashing of `(canonical_name, type)` so re-ingestion upserts rather than creating new nodes.
- **Graphiti's bi-temporal edges** — `(t_valid, t_invalid)` lets a spoiler filter answer "what was true as of chapter K" without rebuilding, and handles fact invalidation naturally.
- **LightRAG's set-union + LLM-summary-regeneration only on touched nodes** — cheap and effective baseline; BookRAG can implement this with a single pass over the new batch.
- **iText2KG's resolve-before-merge** — run entity resolution across the new extraction and the existing snapshot store before insertion to avoid near-duplicate nodes ("Scrooge" vs "Mr. Scrooge").
- **DIAL-KG's governance adjudicator** — when two extractions disagree, an LLM-based reconciler is more accurate than last-write-wins, at the cost of one extra LLM call per conflict.
- **TerminusDB's commit graph as event log** — if we wanted time-travel on the graph itself (not just snapshots), storing each batch as a named commit in a TerminusDB-style layer would give free "graph as-of ingest T′" queries; probably overkill for BookRAG today but elegant for a future "diff between extractor versions" feature.
- **Extractor version field** — versioned records make prompt iteration safe: bump version, the refresh command only re-extracts stale records. This maps directly onto BookRAG's pain point where prompt tightening (commit 0b8efca) required a full re-ingest.


### 22. HippoRAG & biologically-inspired memory systems

**Researched:** 2026-04-22 (iteration 22)

**TL;DR:** A family of retrieval systems explicitly models the hippocampus/neocortex split (HippoRAG), the OS memory hierarchy (MemGPT), or human forgetting curves (MemoryBank) to give LLMs long-term memory that is more than a flat vector store. The most transferable primitives for BookRAG are Personalized-PageRank-over-a-subgraph (HippoRAG), importance/recency/relevance triadic scoring (Generative Agents), and periodic reflection passes that consolidate episodic batches into semantic summaries — all of which compose cleanly with the existing cursor-based allowlist.

**HippoRAG (Gutiérrez et al. NeurIPS 2024, arXiv 2405.14831):**
Offline, HippoRAG runs OpenIE over each passage to produce (subject, predicate, object) triples, embeds each noun phrase, and builds a knowledge graph whose nodes are entities and whose edges are either OpenIE-extracted relations or synonym-similarity edges (cosine ≥ threshold). At query time, a Named Entity Recognizer pulls entities from the question, seeds them as a probability distribution over graph nodes, and runs Personalized PageRank; the PPR stationary distribution is used to weight passages (each passage inherits mass from the entities it mentions), returning top-k. The hippocampal-indexing analogy: the KG is the hippocampal index, the passages are neocortical memories, PPR is pattern completion. Gains up to 20 % over SOTA on multi-hop QA with 10-30× lower cost and 6-13× higher speed than iterative RAG baselines.

**HippoRAG 2 ("From RAG to Memory", Gutiérrez et al., ICML 2025, arXiv 2502.14802):**
Recasts the problem as non-parametric continual learning and benchmarks on factual (NaturalQuestions, PopQA), sense-making (NarrativeQA), and associative (MuSiQue, 2Wiki, HotpotQA, LV-Eval) axes. Key upgrades: deeper passage integration (phrases and full passages share the graph, not just triples), better online LLM use during retrieval, and a stronger embedding backbone. ~7 % associative-memory improvement over the best embedding model while matching or exceeding factual and sense-making baselines — the original HippoRAG sometimes regressed on simple factual QA, which v2 fixes.

**MemGPT / Letta (Packer et al., arXiv 2310.08560, 2023):**
Treats the LLM as a CPU and the context window as RAM. Three tiers: **core memory** (small, always in context, persona + key facts, self-editable via function calls), **recall memory** (full conversation log, searchable via function call), **archival memory** (unbounded vector store for long-term knowledge, also function-call accessed). An interrupt-driven control loop lets the model page data in and out of its own context. Targets document analysis beyond the context window and multi-session chat where identity persists.

**Generative Agents (Park et al., UIST 2023, arXiv 2304.03442):**
25 Smallville agents driven by a **memory stream** (append-only natural-language observation log). Retrieval score = α·recency + β·importance + γ·relevance, where recency is exponential decay, importance is an LLM-rated 1-10 score assigned at insertion, and relevance is embedding cosine to the query. **Reflection** periodically fires when summed importance exceeds a threshold: the agent generates high-level questions about itself, retrieves relevant memories, and writes synthesized abstractions back into the stream. **Planning** uses the stream to produce hierarchical day plans. Ablations confirm all three (memory, reflection, planning) are necessary.

**A-Mem (Xu et al., arXiv 2502.12110, NeurIPS 2025):**
Zettelkasten-inspired agentic memory. Each new memory is stored as a structured note (content, context, keywords, tags) and the agent *itself* decides which existing notes to link to it — a learned linking step, not a fixed k-NN. Older notes can be *refined* when new ones arrive (memory evolution), which Generative Agents' append-only stream cannot do. Outperforms flat-memory baselines across six foundation models.

**Mem0 (Chhikara et al., arXiv 2504.19413, 2025):**
Production-oriented conversational memory layer. A dedicated extractor identifies salient facts from turn history, then a consolidator either ADDs, UPDATEs, DELETEs, or NO-OPs against the existing store (explicit CRUD ops on memories, akin to our per-identity snapshot merge). Mem0g variant adds a graph backend for relational structure. Reports 26 % LLM-as-judge lift over OpenAI Memory, 91 % p95 latency reduction, 90 % token-cost reduction versus full-history baselines. Vector + graph backends with configurable eviction.

**LangMem (LangChain):**
Thin primitives layer — `Memory` objects with `add/search/delete`, hot-path vs background memory (synchronous writes vs deferred reflection), and schema support for typed memories. Less opinionated than Mem0; meant as building blocks rather than a complete system.

**MemoryBank (Zhong et al., AAAI 2024, arXiv 2305.10250):**
Applies the Ebbinghaus forgetting curve to agent memory: each memory has an "intensity" that decays exponentially with elapsed time, is reset/boosted on access, and controls retrieval probability. Three components — storage (chats, event summaries, user-personality assessments), retrieval (vector recall), and intensity update (exponential decay modulated by significance). Deployed in the SiliconFriend companion chatbot.

**Hopfield-style dense associative memory (Ramsauer et al., arXiv 2008.02217, NeurIPS 2020 "Hopfield Networks is All You Need"):**
Modern continuous Hopfield networks store exponentially many patterns (in the dimension of the associative space) and converge in one update step. The update rule is mathematically equivalent to transformer attention — so attention itself is a retrieval operation over a Hopfield memory whose patterns are the KV entries. Three energy-minimum regimes: global average (first-layer heads), metastable subset averages (mid layers), single-pattern retrieval (late layers). Practically: we already have Hopfield memory whenever we have attention; the frame shift is *treating* attention as memory retrieval and designing accordingly.

**Forgetting and consolidation — applicable to fiction?:**
Neuroscience distinguishes episodic memory (specific events, hippocampus-bound) from semantic memory (generalized facts, neocortex). System-level consolidation gradually transfers episodic traces into semantic representations. Reading is a natural analog: a reader's moment-to-moment recollection of Chapter 4 (episodic) consolidates over days into a generalized theme ("Scrooge is becoming remorseful") — a semantic abstraction that no longer requires replaying the scene. Forgetting is not a bug but a feature; irrelevant episodic detail is pruned so semantic generalizations remain.

**Mapping to BookRAG's fog-of-war:**
- **Per-chapter batches = episodic memories.** Each batch JSON is a dated event log constrained to its chapter window.
- **Per-identity snapshot selection (commit 540d27a) = partial semantic consolidation.** The latest snapshot per identity within the cursor is the model's current "generalized" understanding.
- **Cursor allowlist = temporal-context-gated recall.** Only "memories" whose effective_latest_chapter ≤ bound are retrievable — exactly the hippocampal indexing theory's idea that recall is keyed by temporal/contextual tags.
- **Raw-paragraph injection below the cursor = working memory / MemGPT core.** The paragraphs are in context verbatim; the allowed-node context is the archival tier.
- **What's missing:** no importance/recency scoring, no reflection/summarization pass, no PPR-style graph traversal at query time, no explicit forgetting.

**Concrete ideas for BookRAG from this family:**
1. **PPR over the cursor-filtered subgraph (HippoRAG 1/2).** Extract entities from the user query, seed PPR on the allowlist-restricted Kuzu subgraph, weight DataPoints by stationary probability. Gives principled multi-hop traversal within the spoiler boundary without extra LLM calls.
2. **Importance/recency/relevance triadic score (Generative Agents).** Rank allowed DataPoints by α·relevance(query, node) + β·recency(cursor - last_known_chapter) + γ·importance(LLM-rated at extraction time). Importance can piggyback on the existing extraction prompt ("rate 1-10 how central this is to the story"). Recency naturally reflects "what was the reader just reading".
3. **Reflection pass per reading session.** When the cursor advances past a chapter, run a background task that reads the chapter's DataPoints + raw text and emits a reader-state summary ("so far, you've seen..."). Store as a new node type `ReaderReflection{through_chapter, summary}`. Cheap, LLM-native, and directly useful for query grounding.
4. **MemGPT-style memory tiers.** Core = current-chapter paragraphs + ReaderReflection; recall = allowlist graph context; archival = raw chapter text accessible via a "re-read" tool-call. The chatbot could then decide when to page raw text back in ("the reader is asking about a specific quote — fetch archival").
5. **Ebbinghaus decay for "what the reader probably still remembers" (MemoryBank).** Long books with breaks between reading sessions have a UX issue: the reader forgets chapter-4 detail by chapter 20. Weighting by decayed intensity (boosted on re-reads via the chapter-read endpoint) lets the chatbot proactively remind the reader of fading facts.
6. **A-Mem memory evolution for snapshot merge.** When a new batch produces a Character node that contradicts the existing snapshot, run an LLM reconciliation step instead of last-write-wins — this is already recommended by iteration 21 (DIAL-KG) and converges with A-Mem's refinement step.
7. **Hopfield framing for retrieval head.** The current Cognee vector-search + graph-walk loop is already an attention-like retrieval; framing it explicitly as a Hopfield recall lets us reason about pattern completion (partial query → full memory) and error correction (noisy query → canonical entity).

**Key citations:**
1. HippoRAG — Gutiérrez et al., NeurIPS 2024, arXiv:2405.14831; github.com/OSU-NLP-Group/HippoRAG
2. HippoRAG 2 / From RAG to Memory — Gutiérrez et al., ICML 2025, arXiv:2502.14802; PMLR 267:21497-21515
3. MemGPT — Packer et al., arXiv:2310.08560, 2023; memgpt.ai (now Letta)
4. Generative Agents — Park et al., UIST 2023, arXiv:2304.03442
5. A-Mem — Xu et al., arXiv:2502.12110, NeurIPS 2025
6. Mem0 — Chhikara et al., arXiv:2504.19413, 2025; mem0.ai
7. MemoryBank — Zhong et al., AAAI 2024, arXiv:2305.10250
8. Hopfield Networks is All You Need — Ramsauer et al., NeurIPS 2020, arXiv:2008.02217; ml-jku/hopfield-layers

**Concrete ideas worth stealing:**
- **PPR over cursor-filtered subgraph** — single best idea: principled multi-hop within the spoiler boundary, no extra LLM calls, drop-in over the existing Kuzu graph.
- **Triadic importance/recency/relevance score** — cheap addition to ranking; importance rating piggybacks on existing extraction prompt.
- **Reflection-as-reader-state** — a `ReaderReflection{through_chapter_N}` node emitted per chapter advance gives the chatbot a natural "where the reader is" handle without inventing new plumbing.
- **Explicit memory tiers in the chat agent** — core (cursor paragraphs + reflection), recall (allowlist graph), archival (raw chapter text behind a tool-call). Maps the MemGPT pattern onto fog-of-war.
- **Memory evolution on snapshot merge (A-Mem)** — LLM-based reconciliation when batches disagree, converging with iteration 21's DIAL-KG recommendation.
- **Ebbinghaus decay as a UX layer** — only applies once session tracking exists, but a decayed "reader familiarity" score over graph nodes enables proactive reminders.

### 23. GraphReader & agent-based graph traversal

**Researched:** 2026-04-22 (iteration 23)

**TL;DR:** Agentic graph traversal replaces single-pass retrieval with an LLM that iteratively issues tool calls (`read_node`, `read_neighbor`, `stop_and_answer`) to walk the KG, maintaining a notebook of insights until it self-terminates. GraphReader [1] and Think-on-Graph [2][3] are the canonical designs; they raise the recall ceiling versus PPR but multiply token cost by hop count × branching factor. For BookRAG, the load-bearing safety invariant is that the cursor filter must be applied at the *tool boundary* — every node the agent can `read_neighbor` into must first pass the spoiler gate, not just the initial seeds.

**GraphReader (Li et al. 2024, EMNLP Findings):** Two-phase system. **Graph-building phase** chunks long text, extracts atomic facts per chunk, and links chunks via shared key elements (entities/concepts) to form a graph where nodes are key-element clusters and edges are co-occurrence. **Agentic reading phase** starts with a *rational plan*: the LLM decomposes the question and selects initial nodes. It then enters a three-stage exploration loop with a fixed tool repertoire [1]:
- **Atomic-facts stage**: `read_chunk(List[ID])` pulls full chunk text; `stop_and_read_neighbor()` promotes to neighbors.
- **Chunk stage**: `search_more()`, `read_previous_chunk()`, `read_subsequent_chunk()`, `termination()`.
- **Neighbor stage**: `read_neighbor_node(key_element)`, `termination()`.

The agent maintains a **notebook** — a running, step-by-step consolidation of insights merged with each new finding. Termination fires when the agent judges the notebook sufficient. Headline result: a 4k-context agent outperforms GPT-4-128k on LV-Eval across 16k–256k contexts [1].

**Think-on-Graph / ToG (Sun et al. ICLR 2024):** Treats the LLM as an agent doing **beam search over KG triples**. At each step, given current frontier entities, it (1) fetches candidate relations, (2) LLM-prunes to top-k relations, (3) expands to tail entities, (4) LLM-prunes to top-k entities, (5) LLM decides if the current paths suffice to answer. Training-free, plug-and-play [2]. **ToG-2 (2024, arXiv 2407.10805)** tightly couples graph retrieval with unstructured-text retrieval: entities link to documents, documents contextualize entities, and the two alternate. Achieves SOTA on 6/7 knowledge-intensive datasets with GPT-3.5 and lifts LLaMA-2-13B to GPT-3.5-direct levels [3].

**ReAct applied to KG QA:** The original ReAct (Yao et al. ICLR 2023) interleaves `Thought → Action → Observation` trajectories using a Wikipedia API (`search[entity]`, `lookup[string]`, `finish[answer]`) [4]. KG adaptations substitute `search_entity(name)`, `get_relations(entity)`, `get_tail(entity, relation)`, `find_path(a, b)`. "Reasoning on Graphs" (RoG, ICLR 2024) [5] extends this with a plan-then-retrieve variant that generates relation paths as plans, then grounds them on the KG — a middle ground between GraphReader's freeform exploration and ToG's beam search.

**Broader survey signal (2024–2026):** Recent surveys [6][7] converge on a taxonomy: (a) KG-augmented LLM (retrieval), (b) LLM-augmented KG (construction), (c) synergized (agentic loops). GraphRAG and KG-RAG both sit in (a); GraphReader/ToG sit in (c). The dominant 2025 trend is hybrid retrieval — combining dense/sparse/graph signals inside one agent loop rather than picking one.

**LangGraph agents over KGs:** LangChain's LangGraph [8] models agents as stateful directed cyclic graphs with persistent checkpoints, conditional branching, and shared memory — the natural substrate for implementing GraphReader-style loops. Reported patterns include multi-agent SPARQL generation reaching 83.67% accuracy (from 8.16% baseline) and hybrid-memory traversal agents that rewrite queries mid-flight. For BookRAG, LangGraph would be overkill today (single agent, ≤10 tool calls), but the checkpoint primitive is useful if we ever persist a "reader session" across turns.

**Cost of agentic traversal:** Token cost ≈ `Σ (prompt + observation) × hops`. With branching factor b and depth d, worst-case observations = b^d, though beam/top-k pruning caps this. Empirically, ToG issues 10–30 LLM calls per question vs. HippoRAG's ~1 PPR call + 1 synthesis call [iter 22]. On `gpt-4o-mini`, a ToG trace is ~$0.01–0.03 vs. HippoRAG's ~$0.001. The ceiling is higher — agentic traversal answers multi-hop questions PPR misses — but latency is 10–30s vs. sub-second.

**Spoiler-safe agent traversal — the bounded-agent problem:** If we expose `read_neighbor(node_X)` to the LLM, three invariants must hold simultaneously:
1. **Input filter**: `node_X` itself must already have passed the cursor gate before being mentioned in any observation the agent has seen.
2. **Output filter**: the neighbors returned by the tool must be filtered against the cursor — an agent reading a spoiler-free node whose neighbor list contains future-chapter nodes will leak them.
3. **Trace hygiene**: even *refusals* leak ("I can't read node Y because it's from chapter 20"). Refusals must be indistinguishable from "no such neighbor."

This is a stronger property than iteration 17's seed-filtering: the tool itself must be cursor-aware, not just the seeds. The agent should be given a KG that has already been projected to the allowed subgraph; from the agent's perspective, future-chapter nodes *do not exist*.

**Comparison with HippoRAG (single-pass PPR):**
- **Agentic (GraphReader/ToG)**: higher ceiling on hard multi-hop; needs per-call spoiler filtering; 10–30× token cost; natural fit for "why did X do Y?" questions requiring traversal of motivation chains.
- **PPR (HippoRAG)**: lower ceiling, higher floor; single cursor-filter step before propagation; cheap; natural fit for "what do we know about X?" lookups.
- The two compose: PPR can *seed* an agent's initial frontier, the agent then decides whether expansion is needed — this is effectively ToG-2's hybrid pattern applied to fog-of-war.

**Concrete agent-mode design for BookRAG:**
1. **Tool wrappers over allowed subgraph.** Construct `allowed_graph = project(full_graph, cursor)` once per query (reuse `spoiler_filter.load_allowed_nodes` + a symmetric edge filter). All tools read from `allowed_graph` only.
2. **Tool set**: `find_entity(name) → node_id|None`, `read_node(node_id) → {type, description, effective_latest_chapter, first_chapter}`, `find_neighbors(node_id, relation?: str) → List[node_id]`, `find_paragraphs(node_id) → List[para_ref]` (chapter ≤ cursor), `stop_and_answer(answer, citations)`.
3. **Scratchpad**: notebook string + visited-node set; inject both into every turn.
4. **Stop conditions**: agent calls `stop_and_answer`, OR max 8 tool calls, OR 2 consecutive `find_neighbors` returning empty.
5. **Fallback**: if agent terminates without an answer, fall back to current GRAPH_COMPLETION.

**Tool-use safety for spoiler gate:** The only defensible architecture is **input filtering at the tool layer** — the agent physically cannot see future content because tools refuse to return it. Output auditing (scan the final answer for leaked names) is insufficient because partial facts leak through paraphrase. Implementation rule: `find_neighbors` returns `[n for n in raw_neighbors if n.effective_latest_chapter ≤ cursor]` with no error message distinguishing "filtered" from "absent." The projected subgraph should also drop *edges* whose endpoints straddle the cursor, so path-finding tools never surface a bridge through a forbidden node.

**Key citations:**
1. Li et al. 2024. *GraphReader: Building Graph-based Agent to Enhance Long-Context Abilities of LLMs.* arXiv 2406.14550 / EMNLP Findings 2024.
2. Sun et al. 2024. *Think-on-Graph: Deep and Responsible Reasoning of LLMs on Knowledge Graph.* ICLR 2024. arXiv 2307.07697.
3. Ma et al. 2024. *Think-on-Graph 2.0: Deep and Faithful LLM Reasoning with Knowledge-guided RAG.* arXiv 2407.10805 (ICLR 2025).
4. Yao et al. 2023. *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023.
5. Luo et al. 2024. *Reasoning on Graphs: Faithful and Interpretable LLM Reasoning.* ICLR 2024. arXiv 2310.01061.
6. Pan et al. 2024. *Large Language Models on Graphs: A Comprehensive Survey.* IEEE TKDE.
7. *LLMs Meet Knowledge Graphs for Question Answering: Synthesis and Opportunities.* EMNLP 2025 / arXiv 2505.20099.
8. LangChain. *LangGraph: Stateful Orchestration for Agents.* https://github.com/langchain-ai/langgraph.

**Concrete ideas worth stealing:**
- **Rational-plan prelude.** Before any tool call, force the LLM to emit a decomposed plan. Cheap, dramatically reduces wasted traversal [1].
- **Notebook as running state.** A merged insight string beats raw observation logs — fits within a small context window and mirrors our existing `_complete_over_context` interface.
- **Three-stage exploration (fact → chunk → neighbor).** Maps cleanly to BookRAG: node description → node-scoped paragraphs → neighbor nodes. Natural depth gating.
- **Tool-layer cursor enforcement.** The agent sees a *projected* allowed subgraph; future content literally does not exist from its viewpoint. Refusals are indistinguishable from absence.
- **Agent-only when PPR fails.** Run HippoRAG first; escalate to agent mode only if retrieved context scores low on an LLM-judged sufficiency check. Keeps p50 latency low, p99 recall high.
- **Hard stop budgets.** Max 8 tool calls + fallback to GRAPH_COMPLETION. Bounds worst-case cost and guarantees response.
- **ToG-2 hybrid pattern.** Alternate graph steps with raw-paragraph pulls via `find_paragraphs(node_id)` — our fog-of-war paragraph store is already a natural `context_retrieval` complement to KG steps.

### 24. Cost & latency engineering for book-scale KG

**Researched:** 2026-04-22 (iteration 24)

**TL;DR:** Book-scale ingest and per-query RAG have very different cost/latency shapes: ingest is batch-friendly (50% discount via async Batch APIs, parallel chunks, Haiku-tier models), while queries need cached system prompts, structured decoding for one-shot JSON, and streaming tokens for sub-3s first-token latency. For BookRAG specifically, the highest-leverage wins are (a) Anthropic 1-hour prompt caching on the static Phase-2 extraction prompt+ontology (90% read discount) [1][2], (b) OpenAI/Anthropic Batch API for overnight re-ingests (50% off) [3][4], and (c) Langfuse OTel traces for per-book cost attribution [9].

**Prompt caching (Anthropic / OpenAI / Gemini 2024-2026):** Anthropic charges 1.25x base input for a 5-min cache write and 2.0x for the 1-hour TTL; cache reads cost 0.10x base input — a 90% discount with up to 85% latency reduction on long prompts [1][2]. Minimum cacheable prefix is 1024 tokens (Sonnet/Opus) or 2048 (Haiku). Cache invalidates on any byte change to the cached prefix, so the ordering must be `[static system prompt][ontology][book-specific context][dynamic user turn]`. OpenAI automatic caching activates on prompts >1024 tokens with a 50% discount and no explicit opt-in [6]. Gemini 2.5 implicit caching (default May 2025) gives 75% off with 1024-token minimum on 2.5 Flash and 2048 on 2.5 Pro [5]; explicit context caching on Vertex adds a storage fee per hour per cached token. **For BookRAG:** the Phase-2 extraction system prompt plus the discovered OWL ontology is ~4-8k stable tokens per book; caching it across all ~35 batches drops 280-560k tokens from full rate to 10% rate, saving ~$0.03-0.08 per book on gpt-4o-mini and ~$0.20-0.60 on Claude Sonnet 4.

**Batch API tier (Anthropic / OpenAI):** 50% discount, up to 24h latency, separate rate-limit pool (50k requests / 200 MB per file on OpenAI) [3][4]. Ideal for bulk re-ingestion when ontology changes or we onboard a backlog of books. Cost delta: a 100-book library at ~100 LLM calls each costs ~$10-50 on gpt-4o-mini sync vs ~$5-25 batch. Unsuitable for interactive queries.

**Structured decoding / function calling / JSON mode:** OpenAI `strict: true` on response_format or tool definitions guarantees schema adherence (available on gpt-4o-mini and gpt-4o-2024-08-06+) [7]. Anthropic `tool_use` is the equivalent idiom (no strict flag, but tool schemas are enforced via retry in the SDK). Iteration 18 covered GBNF for llama.cpp (lossless local constraint). **Cost implication:** fewer retry round-trips — BookRAG's Phase-2 extraction with vanilla JSON mode empirically retries ~5-15% of batches on malformed JSON; strict mode drops that toward 0, saving both tokens and wall-clock.

**Parallel extraction:** `asyncio.gather` with an `asyncio.Semaphore(N)` is the canonical pattern; pair with `tenacity` exponential backoff on 429s, and dynamically adjust to `x-ratelimit-*` response headers [11]. Tier-1 OpenAI permits 500 RPM on gpt-4o-mini; a semaphore of 10-20 stays well inside that while extracting 35 batches in 1-2 minutes instead of 5-8 sequentially. asyncio is sufficient (no multiprocessing) because extraction is I/O-bound. BookRAG currently runs batches sequentially — the single largest latency win available.

**Model tiering (cost-optimal pipeline):** Published results show Claude Haiku 4.5 and GPT-5 nano beat mid-tier models on pure extraction/formatting tasks; reserve Sonnet/Opus for coreference disambiguation or relationship inference where reasoning matters [12]. A routing layer that sends classification/extraction to Haiku-tier and complex reasoning to Sonnet cuts average cost 40-60% [12]. For BookRAG: ontology discovery (BERTopic reranking) → Haiku/nano; per-batch datapoint extraction → gpt-4o-mini or Haiku 4.5; validation cross-checks and ambiguous coref → Sonnet 4.

**Speculative decoding:** Medusa-1 adds extra decoding heads to predict multiple tokens in parallel via tree attention, achieving 2.2x speedup without quality loss; Medusa-2 hits 2.3-3.6x with joint fine-tuning [8]. Lookahead decoding is a training-free alternative. Inference-side only — only relevant if BookRAG self-hosts Qwen/Llama. For hosted APIs, providers already apply their own speculative stacks.

**Caching by content hash:** BookRAG's per-batch JSON outputs under `data/processed/{book_id}/batches/*.json` already function as a content-addressed cache: re-running ingestion skips completed batches. Extension: key each batch file by SHA256 of `(batch_text + ontology_hash + prompt_version)` so ontology iteration only re-extracts batches affected by changed concepts. A second hash at book-upload time (EPUB content hash) prevents re-ingesting a re-uploaded identical file.

**Latency budget for a chatbot:** Target <3s to first token. Budget: retrieval 50-200ms (Kuzu graph walk + LanceDB ANN) + prompt assembly 10-50ms + LLM TTFT 500-1500ms on cached prefixes, 1-3s uncached. Non-cached first query on Claude is typically 1.5-2.5s TTFT; cached-read second query drops to 300-600ms [2]. BookRAG today is dominated by LLM TTFT; graph retrieval is negligible at Red Rising scale (~2k nodes).

**Streaming responses:** SSE is sufficient for one-way token streaming and avoids WebSocket complexity. The OpenAI and Anthropic SDKs expose `stream=True` / `messages.stream()`; FastAPI serves them via `StreamingResponse(text/event-stream)`. Cognee `search()` does not currently stream (returns a list), so the LLM completion layer is where streaming must be added. While extraction is running, the chat UI can poll `/books/{id}/status` and show a progress pill — BookRAG already has this plumbing in `ProgressPill`.

**Observability:** Langfuse is the OSS leader (19k+ GitHub stars) with OTel-native SDK v3, token accounting per request, model-aware cost ledger (OpenAI/Anthropic/Google pre-loaded), prompt versioning, and LLM-as-judge evals [9][10]. OpenInference (Arize Phoenix) provides auto-instrumentors for OpenAI/Anthropic/LangChain that emit OTel spans Langfuse consumes natively. Trace spans carry `gen_ai.usage.prompt_tokens` / `completion_tokens` attributes per the OTel GenAI semantic conventions.

**Concrete BookRAG cost/latency upgrades:**
- **(a) Anthropic prompt caching on Phase-2 system prompt + ontology** — tag the first two message blocks with `cache_control: {type: "ephemeral", ttl: "1h"}`; expect ~85% cost reduction on the Anthropic path for ingestion, indifferent on gpt-4o-mini (automatic).
- **(b) Batch API toggle** — add `cognee_pipeline.use_batch_api: bool` to `config.yaml`; when true, submit all batches as one JSONL to OpenAI/Anthropic Batch and poll. Saves 50% on ingestion; adds up to 24h latency.
- **(c) `asyncio.gather` + `Semaphore(10)` in `cognee_pipeline.run_batches`** — simplest and biggest single win; 3-5x wall-clock reduction on ingest.
- **(d) SSE streaming on `/books/{id}/query`** — wrap the LLM completion in an async generator; frontend already uses `fetch` with reader API, minor change to `ChatInput`.
- **(e) Langfuse self-hosted via Docker Compose** — wrap `LLMGateway` calls with `@observe()`, tag traces with `book_id` and `chapter_bound`, view cost per book in the Langfuse UI.
- **(f) Strict structured outputs on extraction** — switch Phase-2 extraction to OpenAI `response_format=json_schema, strict=True` using the Pydantic schema already defined in `models/datapoints.py`. Eliminates the retry loop and saves the ~10% of batches that currently re-extract.

**Key citations:**
1. Anthropic. *Prompt caching.* https://platform.claude.com/docs/en/build-with-claude/prompt-caching
2. Anthropic. *Extended 1-hour TTL for prompt caching.* https://x.com/AnthropicAI/status/1925633128174899453 ; https://markaicode.com/anthropic-prompt-caching-reduce-api-costs/
3. OpenAI. *Batch API guide.* https://developers.openai.com/api/docs/guides/batch
4. OpenAI. *Batch API FAQ.* https://help.openai.com/en/articles/9197833-batch-api-faq
5. Google. *Gemini 2.5 implicit caching (May 2025).* https://developers.googleblog.com/en/gemini-2-5-models-now-support-implicit-caching/ ; https://ai.google.dev/gemini-api/docs/caching
6. PromptHub. *Prompt Caching with OpenAI, Anthropic, and Google Models.* https://www.prompthub.us/blog/prompt-caching-with-openai-anthropic-and-google-models
7. OpenAI. *Structured Outputs (strict mode).* https://openai.com/index/introducing-structured-outputs-in-the-api/ ; https://platform.openai.com/docs/guides/structured-outputs
8. Cai et al. 2024. *Medusa: Simple LLM Inference Acceleration Framework with Multiple Decoding Heads.* arXiv 2401.10774.
9. Langfuse. *OpenTelemetry integration & token/cost tracking.* https://langfuse.com/integrations/native/opentelemetry ; https://langfuse.com/docs/observability/features/token-and-cost-tracking
10. *Top Open-Source LLM Observability Tools in 2025.* Medium/The Practical Developer.
11. Villoro. *Async OpenAI calls with rate limiter (asyncio.Semaphore + tenacity).* https://villoro.com/blog/async-openai-calls-rate-limiter/
12. Vellum / AICostCheck / Portkey. *Mixed-model routing: Haiku for extraction, Sonnet for reasoning (2025-2026).* https://www.vellum.ai/blog/gpt-4o-mini-v-s-claude-3-haiku-v-s-gpt-3-5-turbo-a-comparison ; https://portkey.ai/blog/gpt-5-nano-vs-claude-haiku-4-5/

**Concrete ideas worth stealing:**
- **Message-block ordering for cache hits.** Put the immutable extraction prompt and ontology first, book-specific context second, dynamic turn last. One byte of drift in the prefix invalidates the whole cache.
- **Content-addressed batch cache key.** Hash `(batch_text + ontology_hash + prompt_version)` so ontology edits only invalidate the affected batches, not the whole book.
- **Semaphore-throttled `asyncio.gather`.** Simplest possible parallelism; drop-in replacement for the sequential batch loop; 3-5x speedup at tier-1 rate limits.
- **Batch API as a config toggle, not a refactor.** Same JSON payloads, just a different submission path. Wire it behind `use_batch_api: true` for overnight re-ingests.
- **Strict structured outputs = fewer retries = lower cost.** The framework-level reliability win doubles as a cost win; don't analyze them separately.
- **Per-book cost attribution via Langfuse tags.** Traces tagged with `book_id` let you answer "how much did Red Rising cost to ingest" in the UI without custom accounting.
- **Tiered model routing in the orchestrator.** Ontology discovery → Haiku/nano; extraction → gpt-4o-mini; validation & ambiguous coref → Sonnet. 40-60% cost cut without quality loss on the easy stages.

### 25. Prompt engineering patterns for structured extraction

**Researched:** 2026-04-22 (iteration 25)

**TL;DR:** The biggest measured prompt-craft wins for structured extraction come from four orthogonal tricks — code-as-schema prompts (Code4Struct/CodeIE: +29.5 F1 over 20-shot SOTA, 132% over T5-large), explicit entity-definition + explanation-per-candidate (PromptNER: +4 to +24 F1 across NER benchmarks), gleaning loops with logit-biased yes/no continuation (GraphRAG), and self-verification chains (CoVe: 50-70% hallucination reduction). Role prompting and persona framing are overrated — they help *alignment* categories (+0.65 on MT-Bench Extraction) but hurt *factual* categories (-3.6 MMLU absolute). BookRAG's current Jinja prompt is solid on spoiler invariants but misses almost every empirically-validated recall trick.

**Schema-as-code prompts (CodeIE / Code4Struct):** Li et al. 2023 (CodeIE, ACL) and Wang et al. 2023 (Code4Struct, ACL) both showed that rendering the target schema as Python class definitions and asking Code-LLMs to "complete" them beats natural-language schemas by large margins. Code4Struct on Event Argument Extraction: +29.5 absolute F1 over 20-shot SOTA using only 20 training instances, and +12 F1 in zero-resource sibling-event transfer. CodeIE: 132% improvement over T5-large, 327% over T5-base averaged across 7 IE benchmarks. Intuition: PLs exhibit more structural organization than NL, so code-LLMs treat `class Character(DataPoint): name: str; ...` as a completion target rather than a loose description. BookRAG's Pydantic DataPoints already have this shape — rendering them as `class Character(DataPoint): ...` source code in the prompt instead of "a character has these fields" is a nearly-free win.

**Few-shot example selection:** Retrieval-augmented ICL picks demonstrations by cosine similarity to the target chunk, not randomly. On open-domain QA with Llama3-70B, k=5 similarity-retrieved cases gave +18.48 pts on conflict detection and +21.74 on unanswerable-identification, a 2-6 pt lift over random selection (arxiv 2512.04106). For narrative extraction this means: embed each chunk, retrieve 2-3 already-extracted-and-human-verified chunks from a curated demo bank, splice them as in-context examples. Scheme matters — MMR and class-diversity beat pure top-k when labels/types would otherwise cluster.

**Chain-of-thought vs direct extraction:** CoT adds 2-3x output tokens but fixes ambiguous cases (pronoun resolution, nested quotes). Self-Refine (Madaan et al. 2023, arxiv 2303.17651) reports ~20% average absolute task-performance gain across benchmarks from iterative generate-feedback-refine with the same LLM. For extraction with strict JSON, the pattern is "reason in a `reasoning:` field, then emit the structured `extraction:` field" — but strict-mode Structured Outputs make this harder to co-emit. Either use two calls (reasoning then extraction) or add a reasoning field to the schema.

**Role prompting for domain:** The "you are a literary NLP expert" pattern is empirically mixed. Zheng et al. 2024 (ACL Findings, arxiv 2311.10054) and follow-up work show persona prefixes *help* alignment-style tasks (MT-Bench Extraction +0.65, STEM +0.60) but *hurt* factual recall (MMLU overall -3.6 pts across 4 subject areas). Because BookRAG extraction is more style/structure than fact-retrieval, a domain persona probably nets positive, but the effect is small (<1 pt expected) and dominated by the other tricks below.

**Gleaning loop / self-refine (GraphRAG):** Microsoft's GraphRAG runs the extraction prompt, then prompts the LLM "did you miss any entities? yes/no" with `logit_bias=100` forcing a single token, then continues extraction if yes. On HotPotQA, 600-token chunks with gleaning extracted nearly 2x the entity references of 2400-token chunks with zero gleanings. Pure recall trick — costs 1.5-2x tokens, raises recall 30-50%, mild precision drop.

**Named-entity-grounded extraction:** Provide the BookNLP entity list in the prompt and constrain extraction to those entities. BookRAG already does this via `{{ booknlp_entities }}` — the empirical payoff is real. UniversalNER (Zhou et al. 2023, arxiv 2308.03279) showed that explicit entity-type-grounded prompts + distillation give +30 F1 over Vicuna, +7-9 F1 over ChatGPT, 84.78% F1 averaged across 43 NER datasets. The lesson for BookRAG: ground not just on entities but on their canonical forms and aliases so the LLM doesn't invent variants.

**Schema hints in system vs user:** Empirical consensus (OpenAI structured-outputs guide, OpenRouter docs): use `response_format` with `strict: true` for the schema itself; put extraction task description in the system prompt; put the chunk text + BookNLP annotations in the user prompt. Constrained decoding via CFG (strict mode) eliminates enum hallucination and missing-required-field errors. Do NOT duplicate schema in the user prompt — it causes the model to second-guess the CFG and produces longer outputs.

**Anti-hallucination techniques:** Chain-of-Verification (CoVe, Dhuliawala et al. 2023, arxiv 2309.11495): draft → plan verification questions → answer each in isolation → regenerate final answer. Reports 50-70% factual-hallucination reduction on QA and long-form generation. The "answer in isolation" step is load-bearing — avoiding context contamination. For extraction, a lightweight variant: after initial extraction, for each claim emit "which sentence in the chunk supports this?" and drop claims that can't cite. Self-consistency (sample N times, majority-vote) works for short outputs but is expensive for large schemas.

**Negative examples:** LitBank's realis principle (Sims, Park, Bamman 2019) defines what a "real" event is: asserted polarity (not negated), past/present tense (no future/hypothetical), specific participants, indicative modality. Short-stories event-extraction work (arxiv 2412.10745) adds explicit negative examples in the prompt — "Ram gave the test and didn't fail" (polarity), "Ganesha had not moved from his spot" (negated) — and reports measurable precision gains. BookRAG already has spoiler-focused negatives ("no foreshadowing") but doesn't codify realis.

**Structured output schemas — trade-offs:** Strict Pydantic + enum-constrained fields eliminate schema-violation errors but restrict discovery. Permissive strings + post-hoc validation retain discovery but multiply retries. Recommended hybrid: enum-constrain the closed-set fields (`relation_type`, `entity_type`) and leave `description` / `name` open. OpenAI strict mode + CFG decoding makes this a one-flag choice.

**Coverage prompts:** Before typed extraction, prompt "list every named character that appears in this chunk, however briefly." Then feed that list back for typed extraction. Improves recall for minor entities (the butler, the nephew) that get silently dropped when the LLM prioritizes the protagonist. Strong interaction with gleaning — coverage + glean catches roughly 2x entities vs single-pass per GraphRAG's reported chunk-size ablation.

**Multi-pass decomposition:** Pass 1: characters only. Pass 2: locations only. Pass 3: events linking pass 1 to pass 2. Cognee's cascade_extract prompts do exactly this (see iteration 2 / cognee-prompts.md): extract nodes → discover relation names → form triplets. Trades 3x LLM calls for materially higher per-pass quality; on by default in Cognee's cascade pipeline.

**"Think step by step" variants for extraction:** Reflexion (Shinn et al. 2023, NeurIPS, arxiv 2303.11366) adds verbal self-reflection over multiple attempts: +22 abs on AlfWorld, +20 on HotPotQA, +11 on HumanEval. Draft-then-revise (Self-Refine): generate → critique → refine, ~20% avg gain. For extraction: generate draft JSON → prompt "what did you miss or get wrong?" → revise. Worth it for validation/re-extraction loops, not every batch.

**Published prompt benchmarks for extraction:** CodeIE (+132% over T5-large), Code4Struct (+29.5 F1 over 20-shot SOTA), PromptNER (+4 ConLL, +9 GENIA, +4 FewNERD, +5 FaBNER, +24 TweetNER, +3 CrossNER), UniversalNER (+7-9 F1 over ChatGPT on 43-dataset benchmark, 84.78% avg F1), CoVe (50-70% hallucination reduction). These are the concrete numbers to quote when justifying a prompt refactor.

**BookRAG's current prompt — strengths/weaknesses:**
- Strengths: strong spoiler invariants (chapter bounds block with worked example), explicit forbidden-verb list for relation_type (post ca45b43), self-check enumeration, BookNLP entity grounding, typed JSON schema, prior-knowledge suppression.
- Weaknesses: schema rendered as JSON skeleton not as Python class (leaves Code4Struct-style gains on the table); no retrieval-augmented few-shot (examples are static if present at all); no gleaning loop; no CoVe-style verification sub-prompts; no quote-provenance requirement; no explicit realis constraint; no coverage pre-pass; single-pass extraction (vs Cognee cascade); role framing unknown but probably doesn't matter much.

**Concrete prompt upgrades (ranked by expected ROI):**
1. **Gleaning loop (highest ROI):** add a yes/no "did you miss any characters?" continuation with logit_bias. 1.5x tokens, 30-50% recall lift. Same trick for events and relationships.
2. **Schema-as-code:** render `class Character(DataPoint): name: str; first_chapter: int; ...` in the prompt instead of JSON skeleton. Free win if using OpenAI structured outputs with Pydantic — it renders the class source as the schema docstring.
3. **Quote-provenance requirement:** require every relationship and event to include a `source_sentence: str` field that quotes verbatim from the chunk. Drop anything that doesn't round-trip-match the chunk text. Lightweight CoVe.
4. **Explicit realis constraint:** one paragraph in the system prompt with LitBank's four criteria and 3-4 negative examples ("Scrooge considered firing Bob" → NOT an event; "Scrooge fired Bob" → event).
5. **Coverage pre-pass:** cheap call (nano/Haiku) that just lists entity mentions in the chunk; use that list to ground the expensive extraction call.
6. **Retrieval-augmented few-shot:** embed each chunk, pull 2-3 similar already-validated extractions from a demo bank as in-context examples.
7. **Multi-pass decomposition (quality-critical books only):** characters → locations → events-and-relationships. 3x cost, +5-10% F1 per Cognee's cascade data.

**Key citations:**
1. Li et al. 2023, "CodeIE: Large Code Generation Models are Better Few-Shot Information Extractors," ACL 2023.
2. Wang et al. 2023, "Code4Struct: Code Generation for Few-Shot Event Structure Prediction," ACL 2023, arxiv 2210.12810.
3. Ashok & Lipton 2023, "PromptNER: Prompting For Named Entity Recognition," arxiv 2305.15444.
4. Zhou et al. 2023, "UniversalNER: Targeted Distillation from LLMs for Open NER," arxiv 2308.03279.
5. Dhuliawala et al. 2023, "Chain-of-Verification Reduces Hallucination in LLMs," arxiv 2309.11495, ACL Findings 2024.
6. Shinn et al. 2023, "Reflexion: Language Agents with Verbal Reinforcement Learning," NeurIPS 2023, arxiv 2303.11366.
7. Madaan et al. 2023, "Self-Refine: Iterative Refinement with Self-Feedback," arxiv 2303.17651.
8. Edge et al. 2024, "From Local to Global: A GraphRAG Approach to Query-Focused Summarization," arxiv 2404.16130 (gleaning loop).
9. Zheng et al. 2024, "When 'A Helpful Assistant' Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of LLMs," ACL Findings, arxiv 2311.10054.
10. Sims, Park, Bamman 2019, "Literary Event Detection," ACL (LitBank realis).
11. OpenAI, "Introducing Structured Outputs in the API" (2024 launch blog + developer docs).

**Concrete ideas worth stealing:**
- **Logit-biased yes/no gleaning loop.** Single extra call per batch, 30-50% recall lift, proven by GraphRAG at production scale.
- **Schema-as-Python-class rendering.** Free if using structured outputs; 29.5 abs F1 demonstrated gain in Code4Struct's regime.
- **Quote-provenance as a required schema field.** Forces grounding without a separate CoVe pass; enables downstream mechanical validation ("does the source_sentence substring-match the chunk?").
- **LitBank realis as an explicit prompt block** with negative examples — smaller lift but near-zero implementation cost and strongly aligned with BookRAG's spoiler/fidelity ethos.
- **Coverage pre-pass on nano-tier model.** ~$0.001/chunk overhead; catches the minor-entity drop-off that single-pass extraction consistently misses.
- **Cascade decomposition (characters → locations → events)** reserved for books flagged as high-value (Red Rising, validation books) where the 3x cost is justified.

### 26. Embeddings for narrative content

**Researched:** 2026-04-22 (iteration 26)

**TL;DR:** BookRAG is almost certainly running on OpenAI `text-embedding-3-small` (1536-d) via Cognee's default LanceDB adapter, which is a middling choice in 2026 — Gemini Embedding 001, Voyage-3-large, Cohere Embed v4, and Qwen3-Embedding-8B all post materially stronger MTEB scores, and several offer 32k context that actually matters for chapter-level embedding. The highest-ROI upgrades are (a) swapping to Voyage-3.5-lite or BGE-M3 for 32k context + hybrid sparse/dense, (b) adding a cross-encoder rerank (bge-reranker-v2 or Cohere Rerank 3.5) over top-20, and (c) turning on Matryoshka truncation (256/512-d first pass, full for rerank) to make the graph-scale vector search cheap.

**General text embedding SOTA in 2026:**
MTEB English v2 (April 2026) leaders [1][10]:
- **Gemini Embedding 001** (Google, closed) — 68.32 avg, currently #1 on English; uses MRL so dims truncate down from 3072.
- **Qwen3-Embedding-8B** (Alibaba, Apache 2.0) — 70.58 on MTEB v2; strongest open-weight general purpose.
- **NVIDIA Llama-Embed-Nemotron-8B** — tops multilingual MTEB, fully open.
- **NV-Embed-v2** (NVIDIA) — 72.31 overall but weaker retrieval (62.65) vs Gemini's 67.71.
- **Microsoft Harrier-OSS-v1 27B** — MTEB v2 74.3 (MIT).
- **Voyage-3-large / Voyage-3.5** (closed) — 32k context, 2048/1024/512/256 MRL dims, int8/binary quant; +9.74% over OpenAI-v3-large averaged across 100 datasets in 8 domains including law/finance/code [2].
- **Cohere Embed v4** — multimodal (text + image interleaved), 100+ languages [7].
- **Jina embeddings v4** — 3.8B params, Qwen2.5-VL-3B backbone, both single-vector (2048-d MRL → 128-d) and multi-vector (128-d/token, ColBERT-style), 8k native context with late-chunking extensions [3][8].
- **BGE-M3** — multilingual (100+), 8192 tokens, simultaneously produces dense + sparse + multi-vector outputs from one forward pass [9].
- **OpenAI text-embedding-3-small/large** — 1536-d / 3072-d, 8k context, now middle-of-pack.

**Models evaluated on long-form / narrative text:**
LongEmbed (Zhu et al., EMNLP 2024) [6] benchmarks 32k-context retrieval across NarrativeQA, QMSum, 2WikiMultihopQA, SummScreenFD, Passkey, Needle. Finding: models using RoPE (rotary position embeddings) extend cleanly to 32k via NTK / SelfExtend / position interpolation **without retraining**. Authors released E5-Base-4k and E5-RoPE-Base. NarrativeQA is the most BookRAG-relevant subset — it's literally book-QA. Jina's late chunking [Jina blog via iteration 14] addresses the orthogonal problem: embed long context first, then pool per chunk so each chunk vector carries whole-document context.

**Domain-adapted embeddings:**
No widely-used fiction-specific embedding model exists as of 2026. Literary-domain fine-tuning would likely be done via contrastive pairs from LitBank / BookNLP-annotated coreference chains. BookNLP's own embedding layer is BERT-based (internal; not exposed as a standalone retrieval model).

**Multi-vector / late-interaction (ColBERT / ColBERTv2):**
ColBERTv2 [4] stores one vector per token and scores via MaxSim pooling at query time, with aggressive residual compression. Empirically generalizes better to new/complex domains than dense single-vector and is data-efficient for low-resource training. PLAID [4] reduces CPU late-interaction latency up to 7x vs vanilla ColBERTv2 via centroid interaction + pruning. RAGatouille (`AnswerDotAI/RAGatouille`) wraps ColBERT training/indexing for RAG pipelines. For narrative with long character-name co-occurrence and coreference resolution gaps, the per-token granularity helps: queries like "the boy who refuses the apple" can match by overlap without needing a single vector to compress the whole passage.

**Matryoshka / MRL embeddings:**
Kusupati et al., NeurIPS 2022 [5]. Trains nested subspaces (d/2, d/4, d/8…) so a single embedding can be truncated to any prefix without retraining. Up to 14x smaller vectors at iso-accuracy on ImageNet; has been adopted by OpenAI v3 (reduce-dimension API), Voyage (256–2048 dims), Gemini Embedding, Jina v4 (2048→128 truncation). Practical pattern: **first-pass retrieval with 256-d, rerank with full-dim or cross-encoder**.

**Entity / character embeddings:**
Two competing approaches:
1. **Description embedding** (what Cognee does): concatenate the DataPoint's `index_fields` (name + description + maybe aliases) into text and embed. Simple, works with any text encoder. "More like Scrooge" = cosine over character description strings.
2. **Structural KG embedding**: TransE (h + r ≈ t) models entities as points, relations as translations; cannot model symmetric relations. RotatE [from KGE refs] represents relations as rotations in complex space and captures symmetry, antisymmetry, inversion, composition. For cross-book "similar character" retrieval, a hybrid would train a joint text + structure embedding — outside what Cognee provides today.

**Relation embeddings:**
LightRAG embeds relation descriptions as text (iteration 2). Simpler than RotatE but misses graph structure. For BookRAG's `Relationship` DataPoint, embedding the `description` field (e.g., "Scrooge mistreats Bob Cratchit through long hours and low pay") works reasonably because the prose is already contextual; RotatE would only pay off with many books sharing a typed relation schema.

**Scene embeddings:**
Scenes can be detected via: (a) scene-break markers (`***`, blank lines, chapter subheads), (b) Jina-style late chunking with ~500-1000 token windows, or (c) BookNLP quote/event clustering. Dense per-scene embeddings serve "what happens in the carriage ride" style queries that neither entity nor chapter-level embeddings handle well. BookRAG could introduce a `Scene` DataPoint between `PlotEvent` (atomic) and chapter (too coarse).

**Cross-encoders / reranking:**
- **bge-reranker-v2-m3** — strong open reranker, multilingual, BGE family.
- **cross-encoder/ms-marco-MiniLM-L-12-v2** — classic lightweight baseline.
- **Cohere Rerank 3.5** [7] — 100+ languages, handles tables / JSON / code / long docs.
Standard pattern: dense top-50 → rerank to top-5. On narrative QA, reranking typically moves NDCG@10 by 5-15 points over pure dense.

**Hybrid sparse + dense:**
SPLADE [SPLADE refs] learns sparse BERT-based term expansion; outperforms BM25 on quality, slightly slower. Hybrid = run sparse + dense in parallel, fuse with RRF or convex combination. BGE-M3 is attractive here because one model emits both. Opensearch / Qdrant / LanceDB all support hybrid natively. For BookRAG, BM25 alone would catch rare named entities and quoted phrases that dense embeddings compress away ("Bah, humbug" as a literal match).

**Embedding for spoiler-aware retrieval:**
Two patterns:
- **Per-cursor embedding spaces** — prohibitively expensive; requires re-embedding at every cursor move.
- **Per-chunk tagged embedding + metadata filter at retrieval** — BookRAG's current approach. Embed once, filter by `effective_latest_chapter <= cursor` at query time. LanceDB supports metadata pre-filtering. This is strictly cheaper and safer, and matches how vector DBs are designed.
A third option: **separate indexes per "reading milestone"** (e.g., one index per chapter-bound snapshot), query the snapshot matching the cursor. More storage, but makes per-identity snapshot selection (Phase 2 work) a natural index-level operation.

**BookRAG's current embedding stack — what's happening:**
Cognee's default LanceDB adapter uses OpenAI `text-embedding-3-small` (1536-d, 8k context) unless overridden in `config.yaml` [Cognee/LanceDB docs]. `metadata.index_fields` on each Pydantic DataPoint controls which fields concatenate into the string that gets embedded — confirmed in Cognee docs. Character, Location, Faction, PlotEvent, Relationship, Theme all embed separately.

**Concrete embedding upgrades for BookRAG:**
- **(a) Evaluate Voyage-3.5-lite + Jina v4** on a 20-query Christmas Carol / Red Rising eval set. Voyage-3.5-lite has 32k context (covers most chapters in one vector) and MRL truncation; Jina v4 provides optional ColBERT-style multi-vector if we want to try late interaction.
- **(b) Add a cross-encoder rerank over top-20.** `bge-reranker-v2-m3` locally or Cohere Rerank 3.5 via API. Biggest single-change lift and drop-in.
- **(c) Swap to BGE-M3** for a single open-weight model that gives dense + sparse + multi-vector from one pass — matches the hybrid retrieval we'd want anyway and removes the OpenAI dependency.
- **(d) Matryoshka truncation for first pass** — 256-d vector search across the entire graph, 1024-d / 2048-d rerank on top-20. Cuts LanceDB scan cost ~6x on large books.
- **(e) Per-identity snapshot indexes** — one LanceDB collection per chapter-snapshot window; query only the collection matching cursor. Aligns with Phase 2 per-identity snapshot work.
- **(f) Confirm `index_fields`** on Character / Relationship DataPoints currently concatenate useful signal (name + description + aliases). If missing aliases, "Ebenezer" won't retrieve Scrooge snapshots.

**Key citations:**
1. MTEB leaderboard (HuggingFace) — https://huggingface.co/spaces/mteb/leaderboard
2. Voyage-3-large blog — https://blog.voyageai.com/2025/01/07/voyage-3-large/ and Voyage-3.5 — https://blog.voyageai.com/2025/05/20/voyage-3-5/
3. Jina embeddings v4 — arXiv:2506.18902; https://jina.ai/news/jina-embeddings-v4-universal-embeddings-for-multimodal-multilingual-retrieval/
4. Khattab & Zaharia, ColBERT (SIGIR'20); Santhanam et al., ColBERTv2 (NAACL'22); PLAID; https://github.com/stanford-futuredata/ColBERT; RAGatouille https://github.com/AnswerDotAI/RAGatouille
5. Kusupati et al., "Matryoshka Representation Learning," NeurIPS 2022 — arXiv:2205.13147
6. Zhu et al., "LongEmbed," EMNLP 2024 — arXiv:2404.12096; https://github.com/dwzhu-pku/LongEmbed
7. Cohere Embed v4 + Rerank 3.5 — https://docs.cohere.com/docs/cohere-embed, https://docs.cohere.com/docs/rerank
8. Jina late chunking — https://github.com/jina-ai/late-chunking
9. BGE-M3 / M3-Embedding — arXiv:2402.03216; https://huggingface.co/BAAI/bge-m3
10. "Embedding Model Leaderboard: MTEB Rankings March 2026" — https://awesomeagents.ai/leaderboards/embedding-model-leaderboard-mteb-march-2026/

**Concrete ideas worth stealing:**
- BGE-M3's one-model-three-outputs (dense + sparse + multi-vector) for cheap hybrid without running two encoders.
- Matryoshka 256-d first pass → full-dim rerank for graph-scale searches.
- Late chunking (embed whole chapter once, pool per-paragraph) to give each paragraph embedding chapter-wide context — directly aligns with the paragraph-cursor spoiler filter.
- Cross-encoder rerank on top-20 as a near-free quality lift.
- Per-chapter-snapshot LanceDB collections keyed by cursor bound, making spoiler filter a collection-selection instead of metadata filter.
- For cross-book "characters like Scrooge": embed `name || aliases || description || key_quotes` into a single Character vector and store alongside the KG node.

### 27. Hallucination & faithfulness in narrative KG construction

**Researched:** 2026-04-22 (iteration 27)

**TL;DR:** Hallucination in narrative KG extraction is not a single failure — it spans entity/relation/attribute fabrication, narrator-vs-character confusion, inferring off-page events, and over-generalization from negated or hypothetical text. The strongest mitigations pair an atomic-fact decomposition metric (FACTSCORE / FABLES claim-level) with schema-level provenance (every DataPoint carries a verbatim source quote), Chain-of-Verification passes on Character/PlotEvent, and SelfCheckGPT-style multi-sample consistency. For BookRAG, spoiler leakage is itself a faithfulness failure — a chapter-10 node surfacing on a chapter-3 query is unfaithful to the *reader's source window*, not the book's.

**Taxonomy of hallucinations in KG extraction** (adapted from Ji et al.'s intrinsic/extrinsic split, ACM Computing Surveys 2023 [1]):
- **Entity fabrication** — a character the text never names (often from alias confusion or pronoun mis-resolution).
- **Relation fabrication** — asserting `LOVES(A, B)` when the text only shows proximity. Most common in romance/political plots with ambiguous subtext.
- **Attribute fabrication** — hair color, age, occupation invented to fill a schema slot (extrinsic in Ji's taxonomy — unverifiable from source).
- **Type misassignment** — treating a place as a faction, an object as a character (common for named weapons/ships in SFF).
- **Over-generalization** — a one-time action promoted to a habitual trait ("Scrooge hates Christmas" from one scene).
- **Under-extraction** — silent omission; harder to detect than fabrication because there's nothing to flag. FABLES [2] calls this a *content-selection* error and shows LLMs systematically omit mid-book events while over-weighting the ending.

**Narrative-specific failure modes** (not well covered by Ji's survey, but visible in FABLES annotations [2]):
- Confusing narrator with characters (first-person unreliable narrators break extractors).
- Attributing inner thoughts as events ("Scrooge decided to change" extracted as a plot event before he actually does).
- Treating hypothetical or negated events as real ("If Tiny Tim had died..." → extracted as death).
- Confusing characters with similar names (Bob Cratchit / Bob; Darrow / Dancer).
- Inferring off-page events from references ("the war had been going for five years" → fabricates a battle sequence).

**Faithfulness metrics.** Two families apply:
- *Claim-decomposition*: FACTSCORE (Min et al. EMNLP 2023 [3]) splits generations into atomic facts and verifies each against a KB — directly portable to DataPoint fields (each `description` sentence becomes a claim). FABLES [2] applies this to book-length summaries with human annotators who actually read the book.
- *Reference-free*: RAGAS `faithfulness` [4] asks an LLM-judge whether each claim in the answer can be inferred from the retrieved context; AlignScore (Zha et al. ACL 2023) trains a classifier on NLI-style alignment. Both are cheap to run in CI.

**Detection methods.**
- *Reference-based*: compare against gold KG (annotator-curated); expensive but necessary for calibration.
- *Reference-free / LLM-judge*: RAGAS and G-Eval style prompts. FABLES [2] found **no LLM judge correlated strongly with human faithfulness annotators** for book-length summaries — a strong warning for BookRAG's eval strategy.
- *Source-check*: require a verbatim quote span for every DataPoint, then substring-validate it against the raw chapter text. Cheap and catches fabrication near-perfectly.
- *Self-consistency*: SelfCheckGPT (Manakul et al. EMNLP 2023 [5]) — sample the extractor N times with temperature > 0; facts that appear in all samples are likely grounded, facts that vary are likely hallucinated. Achieves AUC-PR 93.4 for non-factual sentence detection.

**Mitigation during extraction.**
- Chain-of-Verification (Dhuliawala et al. 2023 [6]): after an initial extraction, prompt the LLM to generate verification questions ("Where in the text does Scrooge refuse Fred's invitation?"), answer them independently, then regenerate. Reduces hallucinations 50-70% on QA and long-form.
- Quote-provenance: every DataPoint carries a `source_quote: str` field, substring-validated post-hoc.
- Multi-pass with cross-check: first pass extracts candidates, second pass validates each against source span.
- Explicit "unsure" / "not-in-text" option (RAFT, Zhang et al. 2024 [7]): RAFT trains models to cite verbatim spans and ignore distractor passages — the schema-level analogue is letting the extractor return an empty field rather than confabulate one.
- Ensemble extraction: two different LLMs (or same model with different seeds); keep only the intersection.

**Mitigation during retrieval.** Rerank filters that drop nodes without quote provenance; dual-LLM validation (retriever + verifier); mandatory citation in chunk metadata so the generator cannot invent sources.

**Mitigation during generation.** Grounded-generation system prompts ("only state things supported by the provided context; if unsure, say so"); chain-of-thought with inline citation tags; constrained decoding over a node ID vocabulary for structured answers.

**Hallucination on long documents.** Lost in the Middle (Liu et al. TACL 2024 [8]) shows a U-shaped accuracy curve over context position — models use the start and end, miss the middle. Persists in 128K+ context models per 2025 follow-ups. For book-length extraction this means: (a) extractors on a whole-book prompt will under-extract middle chapters; (b) batched extraction (BookRAG's current approach) directly mitigates this by keeping each window small; (c) positioning the most important instructions and ontology near the start of the prompt helps.

**LLM-as-judge for hallucination.** Iteration 15 flagged calibration concerns. FABLES [2] confirmed them at book length. Remedies: calibrate each judge against a small human-gold set, use SelfCheckGPT sampling as a cheaper sanity check, and prefer ensemble judges over single LLMs. SelfCheckGPT-Prompt is the strongest single-judge baseline [5].

**Specific faithfulness benchmarks for RAG.** FaithDial (dialogue faithfulness), HaluEval (broad hallucination benchmark), TruthfulQA (adjacent — tests adversarial misconceptions, not grounding), RAGAS reference-free suite [4], CONNER (narrative consistency). For long-form narrative specifically, FABLES [2] remains the closest fit.

**BookRAG-specific concerns.** Spoiler leakage is a faithfulness violation against the *reader's view of the text*, not the book. A chapter-10 node appearing on a chapter-3 query is unfaithful even if the node itself is perfectly grounded in the full book. This reframes the spoiler filter as a faithfulness-to-source-window constraint and suggests evaluating it with the same atomic-fact decomposition used for factuality — "is every claim in the answer supported by text before chapter N?"

**Concrete BookRAG hallucination safeguards:**
1. Add `source_quote: str` and `source_paragraph_id: int` fields to every DataPoint; post-extraction, substring-validate the quote against the raw chapter. Drop any DataPoint whose quote doesn't match.
2. Chain-of-Verification pass [6] for Character and PlotEvent only (highest fabrication risk); generate verification questions, re-answer, reconcile. Skip for Location/Theme (lower stakes, higher cost).
3. SelfCheckGPT-style self-consistency [5]: re-run extraction on each batch with a different seed, diff the two node sets, and flag disagreements for review or drop.
4. Add an explicit `not_in_text` boolean / `confidence: low|medium|high` to the schema so the LLM can abstain rather than confabulate (RAFT-inspired [7]).
5. Calibrate a RAGAS-style faithfulness judge [4] on a manually-annotated gold set from A Christmas Carol (50 claims across 5 chapters) before trusting it at scale; FABLES' null result [2] is a warning.
6. Reframe spoiler evaluation as faithfulness-to-reader-window: atomic-fact-decompose each answer and assert every claim is supported by text ≤ current paragraph cursor.

**Key citations:**
1. Ji et al., *Survey of Hallucination in Natural Language Generation*, ACM Computing Surveys 2023. https://arxiv.org/abs/2202.03629
2. Kim et al., *FABLES: Evaluating faithfulness and content selection in book-length summarization*, COLM 2024. https://arxiv.org/abs/2404.01261
3. Min et al., *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation*, EMNLP 2023. https://arxiv.org/abs/2305.14251
4. Es et al., *RAGAs: Automated Evaluation of Retrieval Augmented Generation*, 2023. https://arxiv.org/abs/2309.15217
5. Manakul et al., *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection*, EMNLP 2023. https://arxiv.org/abs/2303.08896
6. Dhuliawala et al., *Chain-of-Verification Reduces Hallucination in LLMs*, ACL Findings 2024. https://arxiv.org/abs/2309.11495
7. Zhang et al., *RAFT: Adapting Language Model to Domain Specific RAG*, 2024. https://arxiv.org/abs/2403.10131
8. Liu et al., *Lost in the Middle: How Language Models Use Long Contexts*, TACL 2024. https://arxiv.org/abs/2307.03172

**Concrete ideas worth stealing:**
- Mandatory `source_quote` field + substring validator — cheapest, highest-leverage hallucination gate available.
- SelfCheckGPT-style dual-seed extraction diff: flags the ~10% of nodes most likely to be fabricated, no gold needed.
- CoVe [6] pass scoped to Character and PlotEvent only — 50-70% hallucination reduction where it matters most.
- RAFT-style [7] "abstain" token in the extraction schema so under-extraction becomes explicit rather than silent.
- Treat spoiler leakage as a faithfulness metric: atomic-fact-decompose answers and check every claim against the reader's current cursor window.
- Do *not* trust a single LLM-judge for faithfulness at book scale — FABLES [2] found none correlated with human annotators.
- Keep batches small (BookRAG already does): counters the Lost-in-the-Middle degradation [8] directly.

### 28. BookRAG gap analysis — synthesis & roadmap

**Researched:** 2026-04-22 (iteration 28 — synthesis)

**Method:** Read all 27 prior sections. Cross-referenced every "Concrete ideas worth stealing" block. Scored each idea on (a) expected impact on extraction quality or retrieval accuracy, (b) implementation effort, (c) spoiler-safety relevance. Deduplicated ~180 ideas into the 8–12 highest-leverage upgrades below. Scored ideas as S (≤1 week), M (2–6 weeks), L (>6 weeks) and impact as low/medium/high on both extraction-quality and retrieval axes.

**What BookRAG is doing well (evidence-backed):**

- **Spoiler-gated retrieval is genuinely novel.** No published system — academic (iter 8, 10, 15) or commercial (iter 20) — partitions a KG by a consumer-progress cursor. Adjacent work stops at spoiler *classification* over reviews (McAuley, iter 10) or wall-clock temporal KGs (iter 10). AlphaStar's "mask at input-construction" discipline (iter 10) is the only structural analogue, and BookRAG already enforces it by filtering the node set before LLM context assembly. OSS landscape scan (iter 16) confirms: Renard stops at co-occurrence, BookWorld admits extraction is unreliable, and every "chat with my EPUB" demo treats the book as fully revealed.
- **Cognee is used at the right altitude.** Iter 6's verdict: the `DataPoint` + `run_pipeline([Task(add_data_points)])` primitive layer is the load-bearing part; the default `cognify()` pipeline is not. BookRAG's decision to bypass default cognify and run custom extraction is validated — no reason to fold back in.
- **Per-identity snapshot selection is lightweight event sourcing.** Iter 21 frames it correctly: BookRAG already has a `(batch_id, identity)` keyed event log that materializes snapshots on read, which is exactly what Graphiti/Zep charge money for — minus the bi-temporal machinery we don't need because the source text is immutable.
- **Typed DataPoints are ahead of the open-source graph-RAG default.** GraphRAG (iter 1) and LightRAG (iter 2) use free-text `type` fields and single `description` strings; BookRAG's Pydantic-enforced `Character / Location / Faction / PlotEvent / Relationship / Theme` schema is strictly stronger and compositionally cleaner than LangChain's `LLMGraphTransformer` (iter 4) or LlamaIndex's `SimpleLLMPathExtractor` (iter 3). Only neo4j-graphrag's `LLMEntityRelationExtractor` and LlamaIndex's `SchemaLLMPathExtractor` match it on rigor (iter 3, 5).
- **The allowlist is a persona-consistency checker for free.** Iter 19's key insight: the same `effective_latest_chapter ≤ bound` that protects the reader also defines what an in-story character could know. Reusing `spoiler_filter.load_allowed_nodes` for persona-chat mode is a one-line reuse of existing infra for a genuinely novel feature.
- **Character networks are already typed edge-wise.** Iter 13 found most of the academic corpus (Labatut & Bost, Elson, Agarwal) stops at co-occurrence or un-typed edges; BookRAG's `Relationship` already emits typed edges, a step past the default.
- **Batched extraction over 1500-token windows sidesteps Lost-in-the-Middle.** Iter 27 confirms: small batches directly counter the long-context degradation pattern (Liu et al., TACL 2024). BookRAG's architecture gets this right by construction.
- **"Save every intermediate to disk" policy pays dividends.** Iter 16 (Novel2Graph's coref'd-text directory) and iter 21 (event-sourced replay) both validate it: every CLAUDE.md pattern we follow gives free-resume, free-ablation, and free-event-log for incremental ingest.

**What BookRAG is NOT doing that it clearly should be (prioritized):**

1. **[highest priority] Gleaning loop on Phase-2 extraction.** Iter 1, 14, 25. GraphRAG-style logit-biased yes/no continuation ("did you miss any entities?") reported 30–50% recall lift at 1.5–2× token cost. BookRAG's prompt has spoiler invariants and forbidden-verb lists but no recall-side refinement. Effort: **S**. Payoff: **high** on extraction F1, especially for minor entities (the butler, Tiny Tim's siblings, one-scene Golds). Depends on nothing.

2. **Quote-provenance as a required schema field.** Iter 25, 27. Require every DataPoint (or at least Character / PlotEvent / Relationship) to carry a `source_quote: str` + `source_paragraph_id: int`, then substring-validate against the raw chapter. Cheapest high-leverage hallucination gate available; catches fabrication near-perfectly and sets up downstream citation. Effort: **S**. Payoff: **high** on faithfulness. Depends on nothing; composes with gleaning.

3. **Shrink chunk_size from 1500 → 750, re-measure.** Iter 14. GraphRAG's own ablation shows ~2× more entity references at 600 tokens vs 2400. BookRAG sits in the low-recall band. Ablate on Christmas Carol (measure DataPoint count + schema adherence); if positive, apply to Red Rising. Effort: **S**. Payoff: **high** on recall. Independent of other items but compounds with gleaning and contextual prepending.

4. **HippoRAG-style Personalized PageRank over the cursor-filtered Kuzu subgraph.** Iter 17, 22. BookRAG's current `load_allowed_nodes → top-15 by similarity` is structurally single-hop. PPR-over-filtered-subgraph is the single paper-level retrieval upgrade with the best evidence (~20% MuSiQue lift, 10–30× cheaper than IRCoT). The cursor bound is a node-masking step before propagation — no architectural changes. Effort: **M** (~50 LOC NetworkX + tests + eval). Payoff: **high** on multi-hop. Depends on cross-encoder rerank landing first to avoid confounds.

5. **Structural argument roles on PlotEvent.** Iter 12. Current `PlotEvent.description` is an opaque prose blob; adding `agents / patients / location / instrument / trigger_verb / time_expression` turns it into a structured subgraph with typed participation edges at zero extra LLM calls (same prompt, richer schema). Unlocks Character↔Event edge retrieval that today is implicit. Effort: **S**. Payoff: **high** on graph expressivity. Prereq for temporal/causal linking (item 10).

6. **Anthropic prompt caching + `asyncio.gather(Semaphore(10))` on ingestion.** Iter 24. Two compounding wins: 90% input-token discount on the cached Phase-2 system prompt + ontology (1-hour TTL), and 3–5× wall-clock reduction via parallel batch extraction. BookRAG's batches run sequentially today. Also turn on OpenAI `strict: true` structured outputs to eliminate the ~10% malformed-JSON retry tail (iter 24, 25). Effort: **S**. Payoff: **medium-high** on cost/latency, negligible quality risk.

7. **Cross-encoder reranker over top-20.** Iter 26. `bge-reranker-v2-m3` locally or Cohere Rerank 3.5 hosted — standard pattern, 5–15 NDCG@10 points on narrative QA. Single drop-in addition to the retrieval path; spoiler filter runs first, reranker runs on allowed candidates. Effort: **S**. Payoff: **high** on retrieval precision. Prerequisite for (4) — you want reranking before PPR so the eval doesn't conflate them.

8. **BookNLP `cluster_id` propagated into Cognee Character DataPoints.** Iter 11. BookRAG already runs BookNLP character-name clustering in Phase 1 but throws the cluster ID away at the Cognee boundary. Propagating it eliminates a large fraction of "Scrooge / Mr. Scrooge / Ebenezer" fragmentation before any LLM call. Highest-leverage ER win with zero new infra. Effort: **S**. Payoff: **high** on graph deduplication. Independent of everything else.

9. **Realis + forbidden-verb extraction constraint (LitBank-style).** Iter 12, 25. Explicit prompt block: "only extract events actually depicted as happening in the story world — no hypotheticals, negated, generic-habitual, or narrator asides," with 3–4 negative examples ("Scrooge considered firing Bob" → NOT an event). Cleans the graph dramatically on literary fiction; near-zero cost. Effort: **S**. Payoff: **medium-high** on precision. Independent.

10. **Two-hop neighbor fetch in `spoiler_filter`.** Iter 17. Even without PPR (item 4), after the top-K seed nodes expand to 1- and 2-hop neighbors via Kuzu and re-filter by cursor bound. Single largest fix for the current top-15-only retrieval's multi-hop blindness. ~30 LOC. Effort: **S**. Payoff: **medium-high**. Pure complement to PPR — ship this first, PPR second.

11. **Signed valence on Relationship + fixed 7-type enum.** Iter 13. One extra `valence: positive | negative | neutral` field and a fixed `RelationshipType = familial | romantic | adversarial | alliance | professional | ideological | acquaintance` enum eliminates label drift across batches and unlocks Nalisnick-style antagonist detection. Effort: **S**. Payoff: **medium** on graph coherence.

12. **Extractor-version field on batch JSONs + content-addressed cache.** Iter 21, 24. Key each batch file by SHA256 of `(batch_text + ontology_hash + prompt_version)`. Bumping the prompt version invalidates only affected batches; the recent commit 0b8efca (prompt tightening) required a full re-ingest that this would have averted. Sets up the incremental-update story. Effort: **S**. Payoff: **medium** on iteration velocity.

**Items to explicitly NOT do (with reasoning):**

- **Semantic chunking (Kamradt / LlamaIndex SemanticChunker).** Iter 14. Vectara's 2024 evaluation swept thresholds and found it does not consistently beat fixed-size chunking on narrative; the compute overhead is unjustified. "Blog-famous, paper-mediocre" — narrative text has weak semantic boundaries (same characters, same setting, one long thread). Stick with paragraph-aligned fixed windows.
- **Neo4j migration.** Iter 5. For single-user M4 Pro Mac deployment, the migration is net negative: Kuzu is embedded and zero-config; Neo4j adds a JVM daemon, auth, and a Bolt/HTTP hop per query. What Neo4j gives — Cypher, GDS, Bloom — is attractive for exploration but not on the critical path. Middle path: mirror a read-only Kuzu snapshot into Neo4j for analysis *only*.
- **Role prompting / "you are a literary NLP expert" persona prefixes.** Iter 25. Zheng et al. (ACL Findings 2024): personas help alignment-style tasks slightly but hurt factual recall (MMLU −3.6 pts). BookRAG extraction is more factual than stylistic; this is a trap.
- **Maverick-coref as a drop-in BookNLP replacement.** Iter 7. Best-in-class LitBank F1 (78.0) and 170× faster inference — but **CC-BY-NC-SA 4.0 license** blocks any commercial deployment. Acceptable for research iteration only; do not wire into the default pipeline.
- **Generic community detection that ignores the cursor.** Iter 1. GraphRAG's Leiden-then-summarize is designed for static corpora; running it at index time over the full book and handing those summaries to a chapter-3 reader *guarantees* spoilers. Community detection must happen at query time over the already-filtered subgraph, or not at all.
- **Migrating off Cognee toward LlamaIndex PGI or LangChain LLMGraphTransformer.** Iter 3, 4, 6. Cognee's DataPoint + Task primitive is the right abstraction; PGI gives more modular retrievers but locks you into LlamaIndex's entire `Settings`/`ServiceContext` world, and LangChain's LGT is `langchain_experimental`. Cost of migration > benefit. Keep Cognee; pin 0.5.6; plan a 1.0 evaluation spike.
- **Switching embeddings from OpenAI `text-embedding-3-small` without an eval.** Iter 26. Voyage-3.5 / BGE-M3 / Jina v4 look better on MTEB, but none have narrative-specific fine-tunes and LongEmbed's NarrativeQA split is the only signal worth trusting. Run a 20-query ablation on Christmas Carol + Red Rising before changing anything; don't swap on leaderboard aesthetics.
- **Per-query bi-temporal graph engine (TerminusDB).** Iter 21. Elegant for "diff across extractor versions" but the event log + snapshot-on-demand pattern BookRAG already has gets ~95% of the benefit at ~5% of the complexity. Revisit only if cross-book series linking becomes a first-class feature.
- **Full O(N²) LLM-pairwise entity resolution.** Iter 11. Do the SBERT bi-encoder + LLM cross-encoder ladder over top-k candidates (ComEM pattern) instead. Pure O(N²) LLM ER is wasteful and slow.

**Research contributions BookRAG could publish:**

- **Spoiler-aware retrieval as a formal task.** Iter 8, 10, 15, 16, 20. No academic or commercial system names this problem. A short position paper tied to NarraBench's "revelation" gap (iter 8) and Graphiti's bi-temporal KG machinery (iter 10) would stake the claim.
- **Consumer-progress-gated RAG / consumer-progress TKG.** Iter 10. Generalize "wall-clock valid time" and "reader-progress valid time" under one umbrella; submit BookRAG as the reference implementation. Invites the TKG community (ICEWS14, YAGO, Graphiti) to evaluate their methods in this setting.
- **Cursor-conditioned persona / fog-of-war persona mode.** Iter 19. CharacterEval, CharacterBench, PingPong all evaluate persona fidelity but *none* condition character knowledge on reader progress. Plug the `load_allowed_nodes` bound into an existing persona benchmark and you have a first-of-kind result.
- **spoiler-leak-bench.** Iter 8, 15. Cursor-partitioned gold over Christmas Carol + Red Rising + 3 other public-domain novels, with leak-rate-at-cursor as the headline metric. Calibrate an LLM-judge against FABLES-style human annotators. Genuinely new benchmark the field would pick up.
- **Typed narrative relationship dataset.** Iter 13. The field-wide gap (Labatut & Bost 2019, WNU 2025) is a consistent multi-book typed-relation gold set. BookRAG's Phase-2 extractions over public-domain novels could become one.
- **Renard-compatible spoiler layer as a standalone `PipelineStep` plugin.** Iter 16. Publish the cursor filter so Renard users can drop it in. Low effort, high citability, cleanly positions BookRAG as "the spoiler layer for existing book-NLP pipelines."
- **Forecaster-based spoiler-leakage test.** Iter 10, 15. Train a small RE-NET/CyGNet over `(s, p, o, chapter)` quadruples; if ground-truth chapter N+1 facts are predictable from the ≤N slice, the KG is leaking future structure. Novel automated metric.

**Proposed roadmap (3 phases, 3-6 month horizon):**

**Phase A (1-4 weeks, low-risk wins):**
- Gleaning loop on Phase-2 extraction (item 1).
- Quote-provenance field + substring validator (item 2).
- Shrink chunk_size 1500→750, ablate, pick (item 3).
- Anthropic prompt caching + `asyncio.gather(Semaphore(10))` + OpenAI `strict: true` (item 6).
- BookNLP `cluster_id` propagated into Character DataPoints (item 8).
- Realis + forbidden-verb constraint in prompt with 3–4 negative examples (item 9).
- Two-hop neighbor fetch in `spoiler_filter` (item 10).
- Signed valence + fixed RelationshipType enum (item 11).
- Extractor-version field + content-addressed batch cache (item 12).
- Drop the redundant `cognee.add` call on the chunk path (iter 6).
- Upstream the Kuzu empty-list patches to Cognee (iter 6).
- Auto-generate GBNF grammar from Pydantic DataPoint schemas for future local-LLM path (iter 18).

**Phase B (1-2 months, structural upgrades):**
- Cross-encoder reranker (`bge-reranker-v2-m3`) over top-20 (item 7).
- HippoRAG PPR over cursor-filtered Kuzu subgraph as `retrieval_mode: "ppr"` (item 4).
- Structured argument roles on PlotEvent (item 5).
- ER resolver ladder: SinglePropertyExactMatch → RapidFuzz → SBERT + LLM ComEM oracle, spoiler-gated (iter 5, 11).
- Schema-as-Python-class rendering in the extraction prompt via Pydantic (iter 3, 25).
- CoVe pass scoped to Character and PlotEvent only (iter 27).
- Langfuse self-hosted + per-book cost attribution (iter 24).
- `maverick-coref` evaluation spike on a research-only branch (license-gated, iter 7).
- Chapter-adjacency + PREVIOUS/NEXT edges materialized as first-class graph edges (iter 3).
- Contextual-retrieval prepend on extraction prompt (scene context) per Anthropic (iter 14).
- Triplet-completion search type adoption (iter 6, already specced).
- Second-pass temporal + causal linking stage between PlotEvents sharing a Character argument (iter 12).

**Phase C (research/novel contributions):**
- spoiler-leak-bench dataset + LLM-judge calibrated against human annotators (iter 8, 15).
- Cursor-conditioned persona mode endpoint `/books/{id}/characters/{name}/chat` (iter 19).
- ReaderReflection nodes emitted per chapter advance (iter 22).
- Forecaster-based spoiler-leakage test (TKG forecasting on `(s, p, o, chapter)`) (iter 10, 15).
- Publish "consumer-progress-gated RAG" position paper referencing NarraBench (iter 8, 10).
- Distilled local extractor (Qwen2.5-7B-LoRA + GBNF) as `extraction_backend` config (iter 18).
- Renard-compatible `PipelineStep` plugin release (iter 16).
- Per-identity snapshot LanceDB collections keyed by cursor bound (iter 26).

**Single highest-ROI next move, if you can only do one thing:**

Ship the **gleaning loop + quote-provenance + chunk-size shrink as one combined Phase-2 refactor**. All three are S-effort, they compose multiplicatively on the same prompt, and together they attack BookRAG's three biggest extraction-side weaknesses simultaneously: under-extraction of minor entities (gleaning), silent hallucination (quote-provenance), and low-recall chunking (size). GraphRAG's published numbers alone suggest ~2× the entity references at 600 vs 2400 tokens, and gleaning adds another 30–50% recall on top. Quote-provenance is the faithfulness gate that makes the other two safe to deploy — without it, aggressive gleaning risks inflating the graph with fabricated edges. One focused 2-week sprint, one ablation on Christmas Carol + Red Rising chapters 1–10, one set of numbers for the docs. Every downstream improvement (reranker, PPR, persona mode) compounds on a higher-recall, more-faithful base graph.

**Biggest risk to BookRAG's roadmap:**

**Cognee 1.0 migration drift** (iter 6). Cognee's dev branch is already at 1.0.1.dev4 as of 2026-04-21, and 0.5.x release notes are light on library-level change signal. The key question is whether 1.0 still lets BookRAG run `run_pipeline([Task(add_data_points)])` in isolation or consolidates around `cognify()`. If the latter, BookRAG's hybrid-custom pipeline (the moat on extraction quality) has to be rebuilt against a moving API surface — and we're still carrying local patches to `upsert_edges.py`/`upsert_nodes.py` plus workarounds for `copy_model`'s `default_factory` bug. Secondary risks, ranked: (i) maverick-coref's CC-BY-NC-SA 4.0 license permanently blocking a commercial path (iter 7); (ii) hyperscaler GraphRAG commoditization making "graph-RAG over books" a checkbox in Bedrock KB before BookRAG publishes its spoiler-safety framing (iter 20) — likely mitigated by nobody shipping consumer pricing or narrative schemas; (iii) copyright limiting any public eval beyond Project Gutenberg, so "spoiler-leak-bench on Red Rising" cannot be distributed externally (iter 8). Mitigation: pin Cognee 0.5.6 now, budget a 2-week evaluation spike before forcing a 1.0 upgrade, and keep the extraction path behind a version-adapter shim.

**Open research questions for the community:**

- Is there a retrieval-task formalism that unifies wall-clock valid-time and consumer-progress valid-time under one "valid-time RAG" umbrella?
- Can forecasting-trained TKG models (RE-NET, CyGNet) serve as automated spoiler-leakage detectors for cursor-partitioned graphs?
- How should per-character belief states (theory-of-mind, FANToM-style) be layered on top of a reader-progress KG so the system can answer "what does Cratchit know about Scrooge at chapter 3" distinct from "what does the reader know"?
- For episodic/serialized content (TV, webcomics, serial fiction), does a multi-cursor model (per-title per-reader) outperform single-cursor baselines on spoiler-avoidance recommendation?
- Can a bi-temporal graph engine (Zep/Graphiti, TerminusDB) be repurposed as a general substrate for progress-gated retrieval with `valid_from = source_chunk_ordinal`?
- Does LLM-judged faithfulness ever correlate with human annotators at book length, or is the FABLES null result a permanent ceiling — and what does that imply for the auditability of any spoiler-safety claim?

### 29. Zep / Graphiti deep-dive — bi-temporal agent memory

**Researched:** 2026-04-22 (iteration 29 — bonus)

**TL;DR:** Zep (commercial) and its OSS core Graphiti are the closest named prior art for BookRAG's per-identity snapshot problem. Their bi-temporal edge model — four timestamps per edge, LLM-driven invalidation when new facts contradict old — is a drop-in conceptual primitive for BookRAG's "effective_latest_chapter" + snapshot-selection logic. Borrowing the edge-invalidation prompt and bi-temporal stamps is a high-ROI S-effort cherry-pick; full migration to Graphiti is L-effort and costs BookRAG control over the extraction prompt that is its actual moat.

**Origin & positioning:** Zep is the commercial agent-memory product from getzep.com (Preston Rasmussen, Daniel Chalef, et al.); Graphiti is the Apache-2.0 OSS core, introduced in the January 2025 arXiv paper "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" [1, 2]. Positioned explicitly against MemGPT and LangChain's conversation-memory abstractions. Heavily featured by Neo4j as a reference temporal-KG app [4].

**Bi-temporal model — precise semantics:** Every edge carries four timestamps split across two time axes [1, 2]:
- **Valid time** `T`: `t_valid` / `t_invalid` — when the fact held true *in the world*.
- **Transaction time** `T'`: `t'_created` / `t'_expired` — when the system learned the fact / when the system learned the fact was no longer true.

This lets Graphiti distinguish "Alice became Bob's peer on 2024-06-01" (valid time) from "we ingested that fact on 2025-01-15" (transaction time), and supports retroactive corrections without destructive writes.

**Edge invalidation:** When a new edge is created, Graphiti runs an LLM over semantically related existing edges to detect contradictions. On a hit, it **does not** mark both "true" — it sets the loser's `t_invalid` to the winner's `t_valid`, and consistently prioritizes new information in adjudication [1]. Nothing is ever deleted; history is preserved by the `t'` axis.

**Extraction pipeline:** Chat-turn-oriented [1]:
1. Entity extraction over the current message plus `n=4` prior messages of context.
2. Entity resolution via embedding similarity + full-text search (dedup against existing nodes).
3. Fact extraction between resolved entities.
4. Fact deduplication via hybrid search.
5. Temporal extraction — absolute and relative dates pulled from text.
6. Graph integration through predefined Cypher queries; invalidation check runs here.

**Search / retrieval:** Three parallel retrievers combined [1]: cosine semantic similarity (φ_cos), Okapi BM25 full-text (φ_bm25), and breadth-first graph traversal (φ_bfs). Results reranked via RRF and MMR. The paper does not publish explicit weight values — weights are configurable per deployment.

**Benchmark claims:** On DMR (500 conversations, ~60 messages each), Zep hits 94.8% vs MemGPT 93.4% at gpt-4-turbo, and 98.2% vs 98.0% full-context at gpt-4o-mini [1]. On LongMemEval (~115k-token conversations), Zep reaches 63.8% vs 55.4% full-context at gpt-4o-mini (+8.4pp) and 71.2% vs 60.2% at gpt-4o (+11pp). Latency advantage is dramatic: Zep's median response latency at gpt-4o is 2.58s vs 28.9s for full-context (~90% reduction) while shrinking average context from 115k → 1.6k tokens. **Honest caveat:** DMR delta over MemGPT (1.4pp) is within reasonable noise for a 500-conversation benchmark; the LongMemEval numbers are the stronger claim and benefit from Zep's much smaller context (lower latency is nearly automatic given 70× less tokens).

**Graphiti OSS repo:** `github.com/getzep/graphiti` [3]. Python 3.10+, `graphiti-core` on PyPI. Pluggable graph backends: Neo4j 5.26+ (default), FalkorDB 1.1.2+, **Kuzu 0.11.2+**, and Amazon Neptune. LLM clients for OpenAI, Azure OpenAI, Gemini, Anthropic, Groq, and OpenAI-compatible (Ollama). Custom entity/relationship types defined as Pydantic models — same shape as Cognee DataPoints. Also ships an MCP server and a FastAPI REST service. Key API: `Graphiti(uri, user, pw, llm_client=..., embedder=..., graph_driver=KuzuDriver(...))`.

**Mapping to BookRAG's design:** The bi-temporal primitive maps cleanly onto the spoiler-filter semantics:
- `t_valid` → `source_chunk_ordinal_from` (or `first_chapter`) — when the fact becomes visible to the reader.
- `t_invalid` → next snapshot ordinal where this identity's description materially changes (else `None`).
- `t'_created` → pipeline run timestamp (already captured implicitly in batch filenames).
- `t'_expired` → timestamp at which a later pipeline re-run supersedes the extraction (handles re-ingest cleanly).

This unifies BookRAG's Phase-2 per-identity snapshot selection and future incremental-update logic into a single primitive: `load_allowed_nodes(cursor)` becomes `SELECT edges WHERE t_valid <= cursor AND (t_invalid IS NULL OR t_invalid > cursor)` — a canonical bi-temporal query.

**Integration options:**
- **(a) Full migration.** Replace Cognee+Kuzu with Graphiti+Kuzu (driver already exists). Gains: free temporal primitives, hybrid search, community. Costs: lose Cognee's extraction prompt control (BookRAG's actual moat — parenthetical-coref context, ontology hints, spoiler-aware windowing), rewrite 900+ tests against a new API. Verdict: **not worth it**.
- **(b) Borrow temporal primitives, keep Kuzu+Cognee.** Add `t_valid`/`t_invalid`/`t_created`/`t_invalidated` columns to BookRAG's Relationship DataPoint and to node snapshots. Rewrite `load_allowed_nodes` as a bi-temporal query. S-effort, strictly additive, compatible with existing batches. Verdict: **recommended.**
- **(c) Cherry-pick the edge-invalidation prompt** for BookRAG's snapshot merge step, where chapter-N's "Scrooge is cold" is superseded by chapter-5's "Scrooge is warm." Today BookRAG takes the latest snapshot whole; Graphiti's adjudication would let BookRAG retain non-contradicted facts from the older snapshot. S-effort, composes with (b).

**What Graphiti CAN'T do for BookRAG:** No first-class notion of a reader-progress filter as a retrieval constraint — Graphiti assumes **unidirectional agent-world time** (the agent always lives at the "now" edge of the graph). BookRAG's retrieval lives at an arbitrary cursor *inside* the graph's history, which is a stronger constraint than bi-temporality alone provides. No narrative-schema awareness (characters, factions, PlotEvent types); Graphiti's prescribed-ontology hook accepts Pydantic models but provides no book-specific priors. No concept of a "snapshot identity" spanning multiple edges — Zep's identity is a node, BookRAG needs identity across node revisions.

**Costs and limitations:** Bi-temporal storage roughly doubles edge-row size (four timestamps + extra indices). LLM-cost per ingestion is higher: entity resolution, fact dedup, and invalidation adjudication all spawn extra calls beyond raw extraction (paper doesn't quantify but structure implies 3–5× base extraction cost). Dependency stack non-trivial — even on Kuzu, Graphiti pulls embedders, cross-encoders, multiple DB drivers. Pre-1.0 API (package at `graphiti-core`, breaking changes across minor versions per repo changelog).

**Key citations:**
1. Rasmussen et al., "Zep: A Temporal Knowledge Graph Architecture for Agent Memory," arXiv:2501.13956, Jan 2025. https://arxiv.org/abs/2501.13956
2. Full paper HTML: https://arxiv.org/html/2501.13956v1
3. Graphiti OSS repo: https://github.com/getzep/graphiti
4. Neo4j blog, "Graphiti: Knowledge Graph Memory for an Agentic World": https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/
5. Zep blog, "Beyond Static Knowledge Graphs": https://blog.getzep.com/beyond-static-knowledge-graphs/
6. Zep vs Mem0 comparison, Atlan: https://atlan.com/know/zep-vs-mem0/

**Concrete ideas worth stealing:**
- **Bi-temporal stamps on every Relationship DataPoint** — four fields (`t_valid`, `t_invalid`, `t_created`, `t_invalidated`). Rewrite `load_allowed_nodes` as a bi-temporal SELECT. Makes iter 21's DIAL-KG "update via invalidation" concrete.
- **Edge-invalidation LLM adjudication prompt** — when chapter-N contradicts chapter-M's fact, run a short LLM call over the pair, invalidate the loser, keep non-contradicted facts from the loser snapshot. Unblocks per-identity snapshot merging beyond "take latest wholesale."
- **Hybrid-search triple** (cosine + BM25 + BFS) with RRF fusion — BookRAG currently has vector + graph but no BM25 leg; adding full-text to LanceDB and fusing via RRF is a ~1-day add with free recall gains.
- **Episode provenance** — Graphiti keeps every fact's source episode pointer. BookRAG should similarly store `{batch_id, chapter, paragraph_range}` on every extracted edge — unlocks quote-provenance (iter 28's top-priority move) without separate infrastructure.
- **`n=4` context window** for entity resolution — when deduping a new batch's entities against existing graph, include the prior N nodes' contexts in the LLM call. Cheap way to reduce spurious new-node creation.

### 30. BOOKCOREF (ACL 2025) — book-scale coref benchmark

**Researched:** 2026-04-22 (iteration 30 — bonus)

**TL;DR:** BOOKCOREF (Martinelli, Bonomo, Huguet Cabot, Navigli — Sapienza NLP, ACL 2025 main) is the first full-book coreference benchmark, averaging 200k+ tokens per document. A gold test set of 3 manually-corrected Project Gutenberg books plus a silver train/val split of 50 books demonstrates that even fine-tuned long-doc coref models lose ~20 CoNLL-F1 when moving from medium-scale to full-book evaluation — so BookRAG should expect BookNLP coref quality to degrade materially on Red Rising vs. A Christmas Carol.

**Authors & venue:** Giuliano Martinelli, Tommaso Bonomo, Pere-Lluís Huguet Cabot, Roberto Navigli. ACL 2025 main conference. arXiv:2507.12075, ACL Anthology 2025.acl-long.1197.

**Dataset composition:**
- 45 silver train books + 5 silver val + 3 gold test (53 total). Default config; also a "split" config that chunks each book into 1500-token windows (7,544 / 398 / 152).
- Average 200k+ tokens per doc; test set ~229k tokens total across Animal Farm (Orwell), Pride and Prejudice (Austen), Siddhartha (Hesse).
- Source: Project Gutenberg via Wayback Machine archive. Annotations shipped; raw text fetched by a script (~288 MB dataset repo).
- Annotation scheme: character-centric clusters (each cluster has a canonical name + mention spans). Mentions are character references only — no singletons kept, and non-person entities are out of scope.

**HuggingFace:** `sapienzanlp/bookcoref` (default + `split` configs). Code: `github.com/sapienzanlp/bookcoref`.

**Evaluation protocol:**
- Primary metric: CoNLL-F1 (average of MUC, B³, CEAFe). LEA not reported.
- Three evaluation modes in `evaluate.py`: `full` (whole book), `split` (1500-token chunks), `gold_window` (full predictions scored against windowed gold — measures how much models lose vs. their own ceiling).
- Singleton-free evaluation (no mention-detection-only F1); character-cluster matching only.

**Baseline numbers reported (BookCorefgold, CoNLL-F1):**
- Maverick-xl fine-tuned on silver: **62.7** full-book vs. **82.2** split → 19.5-point book-scale penalty.
- Longdoc (long-document coref): **67.0** full-book (best reported).
- Dual-cache coref: **52.6** full-book.
- Silver-pipeline upper-bound reference: 80.5 CoNLL-F1 (this is the pipeline-as-annotator ceiling, not a model).
- The paper does NOT report LingMess, fastcoref, wl-coref, or BookNLP numbers in the main table — those are inferred as "off-the-shelf models perform even worse." The "+20 CoNLL-F1 gain" quote refers to how much fine-tuning on silver helps vs. LitBank-trained baselines.

**Key findings:**
- Long-distance drift: models trained on LitBank (2-3k-token excerpts) lose coherence past ~10k tokens. Cluster fragmentation (same character split into multiple clusters) is the dominant error at book length.
- Windowed inference + grouping recovers most but not all of the gap — the grouping step (merging overlapping windows by character name) is what makes silver annotation feasible at 80.5 F1.
- Fine-tuning on silver recovers 10-15 F1 points over zero-shot, confirming silver-quality training data transfers.

**Silver set construction:**
Three-stage pipeline: (1) Character Linking (fine-tuned entity linker) seeds mention→character (44.5 F1 alone); (2) Qwen2-7B LLM filter rejects bad links (+5.2 precision); (3) Maverick windowed coref + grouping expands clusters to 80.5 F1 vs gold. Silver is reliable enough for fine-tuning but not for final evaluation — matches BookRAG's disk-first intermediate-output philosophy.

**Applicability to BookRAG:**
- A Christmas Carol is 19c text, similar to Pride and Prejudice / Siddhartha — in-distribution for BOOKCOREF silver. Expect BookNLP's ~70% coref to map to roughly 50-60 CoNLL-F1 on full-book eval (BookNLP was designed for literary text but pre-dates long-doc tricks; not fine-tuned on silver).
- Red Rising (modern sci-fi, invented names like "Darrow", "Mustang") is fully out-of-distribution for both BookNLP's LitBank training and BOOKCOREF's 19c/early-20c gold. Expect a further 5-10 F1 drop vs Carol.
- License: annotations CC-BY-NC-SA-4.0 (hf dataset card) / repo README lists CC-BY-NC-SA-4.0. **Non-commercial** — fine for BookRAG research/eval, blocks productization unless re-licensed or silver is replaced.

**Integration plan:**
- (a) Run BookRAG's `coref_resolver.py` output through a CoNLL-F1 evaluator against `bookcoref` gold; at minimum against Pride and Prejudice as an in-distribution sanity check. No test-set book matches Christmas Carol directly, so add it to the eval as a regression fixture using the silver pipeline on our side.
- (b) Use the 50-book silver split as a permissive *evaluation corpus* (read-only) — compute cluster-count, cross-chapter-merging, and long-distance-accuracy metrics we care about for spoiler filtering. Silver text is public-domain Gutenberg; only the annotations are NC-SA.
- (c) Fine-tuning path: swap BookNLP coref for `maverick-coref` fine-tuned on BOOKCOREF silver (Martinelli's checkpoints). Gives ~62.7 CoNLL-F1 zero-shot on new books vs BookNLP's ~50. Inference cost: windowed + grouping step; fits M4 Pro. This would unblock the "swap BookCoref for BookNLP" placeholder noted in CLAUDE.md's locked decisions.

**Risks / limitations:**
- NC license on annotations blocks commercial deployment without re-annotating or licensing.
- Only 3 gold test books (biased toward canonical English lit). No YA, fantasy, or translated contemporary fiction. Red Rising coverage is speculative.
- Singleton-free annotation means mentions with no co-referent (rare minor characters, one-off references) are not in the gold — BookRAG's per-chapter spoiler filter needs singletons to be tracked as *allowed nodes*; can't drop them just because coref evaluation ignores them.
- Pipeline-generated silver inherits Maverick's biases (pronoun-heavy clusters, weak on possessives); fine-tuning on silver can amplify these.

**Key citations:**
- Martinelli et al., "BOOKCOREF: Coreference Resolution at Book Scale," ACL 2025 main. arXiv:2507.12075. https://aclanthology.org/2025.acl-long.1197/
- HF dataset: https://huggingface.co/datasets/sapienzanlp/bookcoref
- Repo + eval: https://github.com/sapienzanlp/bookcoref
- Related: xCoRe (EMNLP 2025, 2025.emnlp-main.1737) on cross-context coref — potential follow-on.

**Concrete ideas worth stealing:**
- Windowed coref + grouping step (merge windows by canonical character name) — directly applicable to BookRAG's per-batch processing; we already have canonical names from BookNLP entity file.
- Character Linking as cluster seed (stage 1 of silver pipeline) — matches our ontology-discovery stage output; we could seed coref with the character list instead of trusting BookNLP's internal clustering.
- `gold_window` eval mode — measure "how much does chunking hurt" separately from "how much does the model suck." BookRAG should run the same decomposition to quantify cost of 3-chapter batching.
- Fine-tune permissively-licensed fastcoref on silver (silver is annotation-only; text is PD) then release under Apache-2.0. Unblocks commercial use.

### 31. Novel2Graph + Renard — OSS architectural templates

**Researched:** 2026-04-22 (iteration 31 — bonus)

**TL;DR:** Renard (CompNet, 2024) is the closest architectural sibling to BookRAG's pipeline: a modular `PipelineStep` framework with requirements/produces validation, published in JOSS, actively maintained (v0.7.1 Jan 2026), and explicitly designed for third-party step integration. Novel2Graph (IDSIA, 2019–2020) is a research artifact — a static snapshot of a relation-clustering approach, not a framework. The highest-leverage play is publishing BookRAG's spoiler filter as a Renard-compatible `PipelineStep` (Renard has NER → CoRef → Unifier → GraphExtractor; it has **no** temporal/cursor-based filtering).

**Novel2Graph:**
- Authors: Vani Kanjirangat, Alessandro Antonucci, et al. (IDSIA, Lugano). Base paper: "NOVEL2GRAPH: Visual Summaries of Narrative Text Enhanced by Machine Learning" (2019, Semantic Scholar); follow-up "Relation Clustering in Narrative Knowledge Graphs" (CEUR Vol-2794, 2020).
- Architecture: Stanford CoreNLP NER + DBSCAN alias clustering on Levenshtein distances → SBERT embeddings of relational sentences → clustering to merge semantically similar relations → sentiment analysis colors edges → Dash/Graphviz GUI. Outputs: CSVs + pickled embeddings + coref-resolved text in `Data/` subdirs.
- Evaluation: applied to Harry Potter series; "preliminary tests" only — no P/R/F1 tables against a labeled corpus in the 2020 CEUR paper.
- Activity: 14 stars, 4 forks, 10 commits total on master, no releases, no visible recent activity. Effectively archival. (https://github.com/IDSIA/novel2graph)
- License: not specified in repo — treat as non-reusable code, only reusable ideas.

**Renard:**
- Authors: Arthur Amalvy, Vincent Labatut, Richard Dufour (LIA Avignon / CompNet). JOSS 2024 (DOI 10.21105/joss.06574), arXiv 2407.02284, also on HAL. PyPI: `renard-pipeline`.
- Repo: https://github.com/CompNet/Renard — 20 stars, GPL-3.0, Python 3.9–3.12, 485 commits, latest v0.7.1 (2026-01-07), Gradio UI (`make ui`), HuggingFace demo. Actively maintained.
- `PipelineStep` abstraction: each step declares inputs it requires and outputs it produces; `Pipeline` validates wiring at construction and raises descriptive errors when a requirement is unmet.
- Available steps: `NLTKTokenizer`, `StanfordCoreNLPPipeline`, `NLTKNamedEntityRecognizer`, `BertNamedEntityRecognizer`, `SpacyCorefereeCoreferenceResolver`, `BertCoreferenceResolver`, `QuoteDetector`, `NLTKSentimentAnalyzer`, `NaiveCharacterUnifier`, `GraphRulesCharacterUnifier`, `CoOccurrencesGraphExtractor`, `ConversationalGraphExtractor`, `BertSpeakerDetector`. Three preconfigured pipelines: `co_occurrence_pipeline()`, `conversational_pipeline()`, `relational_pipeline()`.
- Dynamic networks via `dynamic=True` + `dynamic_window=N` — outputs a list of graphs over time windows. The JOSS paper explicitly notes prior tools (Charnetto, CHAPLIN) cannot do this.
- Extension: subclass `PipelineStep` and override `needs()`/`produces()`/`__call__()`; steps can wrap non-Python processes as adapters.

**Renard vs BookRAG pipeline comparison:**

| BookRAG stage | Renard equivalent | Notes |
|---|---|---|
| `parse_epub` | (none — Renard takes plain text) | BookRAG has EPUB+TOC+cleaning, Renard users wire their own loader |
| `run_booknlp` | `BertNamedEntityRecognizer` + `BertCoreferenceResolver` (separate) | Renard splits NER/coref into independent steps; BookNLP bundles them |
| `resolve_coref` (parenthetical insertion) | no direct equivalent | Renard keeps coref as cluster metadata; does not reconstruct resolved text |
| `discover_ontology` (BERTopic + OWL) | no equivalent | Renard has no ontology discovery — it extracts a fixed graph schema (nodes=characters, edges=cooccurrence/conversation) |
| `run_cognee_batches` (LLM extraction → DataPoints) | `CoOccurrencesGraphExtractor` / `ConversationalGraphExtractor` | Renard is statistical/rule-based; no LLM extraction step exists |
| `validate` | no equivalent | Renard has no downstream QA of the produced graph |
| Spoiler filtering at query time | no equivalent | Renard produces a static (or time-windowed) graph; no reader-cursor semantics |

BookRAG primitives Renard lacks: EPUB ingestion, ontology discovery, LLM-based typed-DataPoint extraction, validation suite, and spoiler/fog-of-war filtering. Renard primitives BookRAG lacks (and could cheaply adopt): the `needs/produces` validator pattern, the `dynamic_window` formulation for time-sliced graphs, Gradio demo UI.

**Integration sketch — "BookRAG-as-Renard-step":**
A `SpoilerFilterStep(PipelineStep)` would:
- `needs = {"characters", "graph", "chapter_index"}` (all produced by Renard's unifier + extractor)
- `produces = {"graph_filtered", "reader_cursor"}`
- Parameters: `current_chapter: int`, `current_paragraph: int | None`, `mode: "chapter_inclusive" | "strict_paragraph"`.
- Behavior: walk graph nodes, compute `effective_latest_chapter`, drop nodes/edges with `chapter > bound`. For paragraph mode, concat raw text 0..cursor for the current chapter and expose via a `raw_prefix` key.
What Renard would need to contribute upstream: a standard `chapter_index` type (currently ad-hoc) and per-node/per-edge `first_seen_chapter` metadata on the graph extractors (today the `dynamic_window` output is a list of graphs rather than a single annotated graph — we'd propose an optional `annotate_chapter_provenance=True` flag).

**Packaging strategy if we publish:**
- Name: `renard-spoiler` on PyPI (follows Renard's `renard-pipeline` convention).
- Deps: `renard-pipeline>=0.7`, `pydantic>=2`, stdlib only otherwise. Optional extra `[llm]` for GRAPH_COMPLETION carrying `openai` + `anthropic`.
- CI: GitHub Actions matrix Python 3.10/3.11/3.12, a single example notebook running on A Christmas Carol (public domain — no licensing drama), published via `nbmake` + artifact upload.
- Docs: mkdocs-material on GitHub Pages; one quickstart, one integration-with-Renard, one BookRAG-bypass example using just the filter.
- License: GPL-3.0 to match Renard (mandatory if we import Renard types) — means BookRAG proper stays MIT but the thin `renard-spoiler` adapter is GPL. Alternative: LGPL if Renard maintainers accept a relicense request for the PipelineStep base.

**Alternatives — Storytoolkit / other narrative libraries:**
- Charnetto and CHAPLIN — cited in Renard's JOSS paper as prior character-network extractors; neither is maintained (last touched pre-2022 per Renard's related-work framing).
- FanfictionNLP (CMU, 2019–2021) — BookNLP-style pipeline, archived, fanfic-specific.
- MARCUS (CEUR Vol-3117 / arXiv 2510.18201, 2025) — event-centric arc generator that builds on BookNLP. Not a pipeline framework; a research system.
- "storytoolkit" as a python narrative-pipeline library: does not appear to exist (name collides with a video editor project). Confirmed no PyPI hit.

**License compatibility:**
- Renard: GPL-3.0. Importing Renard (subclassing `PipelineStep`) forces downstream GPL. BookRAG (MIT-assumed) can stay MIT if the adapter lives in a separate repo/package.
- Novel2Graph: no license specified → legally unsafe to vendor code; ideas only.
- BookNLP: MIT. Safe to vendor.
- Cognee: Apache-2.0 (per their repo). Safe to vendor.
Net: publishing `renard-spoiler` is viable as GPL-3.0; keep BookRAG's core MIT.

**What BookRAG should borrow vs publish:**

| Primitive | Borrow from Renard | Publish from BookRAG |
|---|---|---|
| `PipelineStep` needs/produces validator | YES — adopt pattern in `pipeline/orchestrator.py` | — |
| Dynamic-window time slicing | YES — formalize our `effective_latest_chapter` as a `dynamic_window` analog | — |
| Gradio demo UI | YES — 20-line wrapper for BookRAG ingestion | — |
| Preconfigured pipelines (`co_occurrence_pipeline()` style) | YES — ship `christmas_carol_pipeline()`, `red_rising_pipeline()` defaults | — |
| Spoiler filter (`effective_latest_chapter` + cursor) | — | YES — `renard-spoiler` package |
| Parenthetical coref insertion format | — | YES — generalizable preprocessor, trivially a PipelineStep |
| LLM-based typed extraction (`DataPoint`s) | — | YES — Renard has no LLM step; our typed extractor fills a gap |
| Ontology discovery (BERTopic→OWL) | — | YES — as `OntologyDiscoveryStep`; no Renard equivalent |
| EPUB parser + text cleaner | — | YES — as `EpubIngestStep` |

**Key citations:**
- Amalvy, Labatut, Dufour. "Renard: A Modular Pipeline for Extracting Character Networks from Narrative Texts." JOSS 9(98):6574, 2024. https://joss.theoj.org/papers/10.21105/joss.06574 · arXiv 2407.02284 · HAL hal-04611122
- CompNet/Renard repo: https://github.com/CompNet/Renard (GPL-3.0, v0.7.1, 2026-01)
- Renard docs: https://compnet.github.io/Renard/pipeline.html
- Kanjirangat, Antonucci. "Relation Clustering in Narrative Knowledge Graphs." CEUR Vol-2794 paper 5, 2020. https://ceur-ws.org/Vol-2794/paper5.pdf
- Vani, Antonucci. "NOVEL2GRAPH: Visual Summaries of Narrative Text Enhanced by Machine Learning." 2019. Semantic Scholar ID 4ca919f38296b09831b6f09bdf1fd5c8874d0e94
- IDSIA/novel2graph repo: https://github.com/IDSIA/novel2graph (unlicensed, ~archival)

**Concrete ideas worth stealing:**
- Adopt Renard's `needs()`/`produces()` contract on BookRAG stages — eliminates an entire class of "stage N crashed because stage N-1 wrote the wrong key" bugs and gives us free pipeline-validity checks at orchestrator startup.
- Ship three preconfigured BookRAG pipelines (`default_pipeline()`, `fast_pipeline()` skipping ontology, `strict_spoiler_pipeline()` with `batch_size=1`) — discoverability win with zero architectural change.
- Add a `dynamic_window` mode to spoiler filter: expose a list of per-chapter snapshot graphs for UI timelines, not just the filtered point-in-time graph. Enables a "progress scrubber" UX and matches Renard's dynamic-network API so adapter users feel at home.
- Publish `renard-spoiler` adapter first (low effort, <200 LOC), use the PR/issue traffic to recruit Renard's authors as reviewers of BookRAG's main pipeline — cheap path to academic credibility.
- Borrow Novel2Graph's SBERT-over-relational-sentences clustering as an optional post-hoc step to deduplicate our `Relationship` DataPoints when Phase 2 extracts semantically-equivalent relations across batches.

### 32. ColBERT / late-interaction for narrative retrieval

**Researched:** 2026-04-22 (iteration 32 — bonus)

**TL;DR:** ColBERTv2 via RAGatouille delivers near cross-encoder quality at a fraction of the rerank cost and is now a first-class citizen in LanceDB's multivector API, so the "100x storage" objection is largely a 2021 artifact — residual compression pushes it to ~6-10x. For BookRAG, however, a cross-encoder rerank over single-vector recall (iteration 26) is still the pragmatic win; late-interaction only pays off once the library grows past ~50 books or we hit a concrete recall ceiling on lexically-varied narrative queries.

**ColBERT family:** ColBERT (SIGIR 2020, arXiv 2004.12832) introduced late interaction — encode query and doc tokens independently, score via MaxSim (sum over query tokens of max cosine against any doc token). ColBERTv2 (NAACL 2022, arXiv 2112.01488) adds denoised supervision and **residual compression to ~20 bytes per token vector**, a 6-10x storage reduction, and wins 23/29 tasks on BEIR/LoTTE, beating the next best standalone retriever by up to 8% nDCG@10 ([ColBERTv2 paper](https://aclanthology.org/2022.naacl-main.272.pdf)). PLAID (arXiv 2205.09707) is the indexing/serving layer: centroid-based pruning yields **7x GPU / 45x CPU latency reduction** with no quality loss, landing in tens of ms on GPU and low hundreds of ms on CPU even at 140M-passage scale ([PLAID](https://arxiv.org/abs/2205.09707)).

**RAGatouille library:** `bclavie/RAGatouille` (now under AnswerDotAI) is the default entry point. Three-line API: `RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")`, `.index(collection, index_name, max_document_length)`, `.search(query, k)`. Indexes are PLAID-compressed, on-disk, persistent. Training via `RAGTrainer` with hard-negative mining. Python 3.9+, **Linux/WSL2 only — no native Windows, and macOS support is historically flaky** because the underlying `colbert-ai` package pulls faiss-gpu and ninja-compiled CUDA kernels ([RAGatouille repo](https://github.com/AnswerDotAI/RAGatouille)). Integrations documented for Vespa, Intel FastRAG, and LlamaIndex.

**Benchmark numbers:** BEIR nDCG@10: ColBERTv2 averages ~0.50 vs BM25 ~0.43 and single-vector dense (ANCE/TAS-B) ~0.41-0.45; on out-of-domain LoTTE the gap widens further ([ColBERTv2 paper §5](https://arxiv.org/pdf/2112.01488)). No ColBERTv2 NarrativeQA retrieval numbers published (NarrativeQA is mostly tested as a generation benchmark). LoCo and LongEmbed are the newer long-context retrieval benchmarks (iterations 25-26); ColBERTv2's 512-token doc cap is the binding constraint there — late-interaction doesn't magically extend context, you still chunk. Jina-ColBERT-v2 (2024, [ACL MRL](https://aclanthology.org/2024.mrl-1.11.pdf)) pushes doc length to 8192 and is the first credible long-context late-interaction model.

**Storage & indexing cost:** Uncompressed ColBERT: ~128-dim fp16 per token ≈ 256 bytes/token × ~500 tokens/chunk = ~128KB/chunk, vs ~1.5KB for a single 768-dim fp16 vector — **~85x**. ColBERTv2 compressed: ~20 bytes/vector × 500 = **~10KB/chunk, ~6-7x** over single-vector. For BookRAG: a 100k-token novel → ~200 chunks × 10KB = 2MB per book (trivial); 100-book library = 200MB (still trivial next to LanceDB's current dense index). The storage argument against ColBERTv2 is **obsolete at our scale**.

**Query latency:** PLAID CPU latency is tens-to-low-hundreds of ms at 140M passages. For a per-book index of ~200 chunks, MaxSim is microseconds; query encoding (~30ms on CPU, ~3ms on GPU for the ColBERT BERT-base encoder) dominates. LanceDB single-vector ANN is sub-ms for our scale, so late-interaction adds ~30ms per query — imperceptible in a chat UI that already waits for LLM completion.

**Late-interaction vs cross-encoder rerank:** The canonical tradeoff table ([LanceDB blog on late interaction](https://www.lancedb.com/blog/late-interaction-efficient-multi-modal-retrievers-need-more-than-just-a-vector-index)): cross-encoder = slow, highest quality, O(k) forward passes per query, no precomputation; ColBERT = medium speed, near cross-encoder quality, amortized precompute. **Under load (>30 QPS) cross-encoders saturate (p99.9 >21s at 40 QPS) while ColBERT stays flat**. For BookRAG (single-user, <1 QPS), the load argument is irrelevant — a cross-encoder over top-50 dense hits is 50 BERT-base forward passes ≈ 500ms, fine. Late-interaction wins on *recall ceiling*, not throughput, for us.

**Multi-vector + graph hybrid:** A genuinely novel combination: store per-token ColBERT embeddings on `Chunk` DataPoints, keep the graph for structural traversal and spoiler filtering, then MaxSim-rank the chunks surfaced by graph walks. This sidesteps the "KG vs vector" dichotomy — graph selects the *spoiler-safe candidate pool*, MaxSim picks the best chunk. LanceDB's multivector API makes this one table (`embedding: list[FixedSizeList[128]]`) with `chapter` + `batch_id` as filter columns ([LanceDB multivector docs](https://docs.lancedb.com/search/multivector-search)).

**Narrative-specific considerations:** Fiction's retrieval pain points map well to late-interaction's strengths. Polysemy of referring expressions ("the ghost," "Marley," "the spectre," "his partner") is exactly what MaxSim handles — a query token "ghost" can max against a doc token "spectre" via BERT's contextual similarity, where a single mean-pooled vector averages the signal away. Conversely, fiction's lower overall vocab diversity means BM25 + cross-encoder may already hit the recall ceiling; the marginal lift of ColBERT over a well-tuned hybrid (BM25 + dense + CE rerank) on narrative-QA is unmeasured in published benchmarks.

**BookRAG-specific analysis:**
(a) **LanceDB supports it** — `LanceDB.create_table` accepts `pa.list_(pa.list_(pa.float32(), 128))` schemas and the query API does MaxSim natively when you pass multiple query vectors ([LanceDB ColBERT guide](https://lancedb.github.io/lancedb/guides/multi-vector/)). No migration off our current vector store.
(b) **Storage tolerable** — 2MB/book compressed, no concern up to thousands of books.
(c) **Spoiler-filter complexity is minimal** — per-token embeddings still attach to a `Chunk` row with `chapter`/`paragraph` metadata; the spoiler filter is a `WHERE chapter <= cursor` predicate applied *before* MaxSim, identical to today's single-vector filter path. No new complexity.
(d) **macOS/M4 Pro blocker** — RAGatouille's Linux-only constraint is real; we'd need to run the indexer in Docker or use LanceDB's native ColBERT path (which sidesteps `colbert-ai`) and encode queries with `transformers` + the ColBERTv2 checkpoint directly. The LanceDB-native path is the cleaner bet.

**Recommendation: (b) stick with single-vector + cross-encoder rerank for now, but plan the migration path.** Concretely: ship iteration 26's cross-encoder rerank in the next slice; add a `retrieval_mode: {dense, dense_rerank, late_interaction}` config switch; keep the LanceDB schema ready for multi-vector (already supported); revisit ColBERTv2 when (i) library >50 books, (ii) we have a measurable recall-ceiling bug on epithet/alias queries, or (iii) Jina-ColBERT-v2 or BGE-M3's ColBERT head matures enough to avoid the `colbert-ai` dependency on macOS. Late-interaction is the right endgame, not the right next step.

**Key citations:**
- [ColBERT (SIGIR 2020) — arXiv 2004.12832](https://arxiv.org/abs/2004.12832)
- [ColBERTv2 (NAACL 2022) — arXiv 2112.01488](https://arxiv.org/abs/2112.01488)
- [PLAID (CIKM 2022) — arXiv 2205.09707](https://arxiv.org/abs/2205.09707)
- [RAGatouille — github.com/AnswerDotAI/RAGatouille](https://github.com/AnswerDotAI/RAGatouille)
- [LanceDB multivector search docs](https://docs.lancedb.com/search/multivector-search)
- [LanceDB blog: late interaction needs more than a vector index](https://www.lancedb.com/blog/late-interaction-efficient-multi-modal-retrievers-need-more-than-just-a-vector-index)
- [Jina-ColBERT-v2 (ACL MRL 2024)](https://aclanthology.org/2024.mrl-1.11.pdf)
- [BEIR benchmark (NeurIPS 2021)](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/file/65b9eea6e1cc6bb9f0cd2a47751a186f-Paper-round2.pdf)

**Concrete ideas worth stealing:**
- Schema LanceDB tables with `FixedSizeList` multi-vector columns *now*, even while emitting single vectors — enables zero-migration upgrade to ColBERTv2 later.
- Spoiler-filter-first, MaxSim-second ordering: the graph's chapter predicate prunes the candidate pool before the expensive scoring, which is the opposite of the usual "rerank top-k" flow and suits fog-of-war perfectly.
- Use ColBERT's MaxSim explainability (query-token → doc-token alignment scores) as a debugging UI for "why did the retriever surface this chunk?" — free interpretability win that cross-encoders can't provide.
- Treat `batch_size=1` snapshots as first-class chunks for late-interaction indexing: each chapter's per-identity snapshot becomes its own retrievable unit, with MaxSim handling the "the ghost" vs "Marley" alias problem across snapshots.
- Defer ColBERTv2 until after a measured recall failure, not before — `docs/research/` now has enough iteration-26/32 context to justify the deferral on evidence, not vibes.

### 33. Web-serial fiction as serialized-KG market

**Researched:** 2026-04-22 (iteration 33 — bonus)

**TL;DR:** Web-serial platforms host multi-million-word works updated chapter-by-chapter for audiences that forget cast/plot between weekly drops and rely on spoiler-laden community wikis. Royal Road alone saw ~14M visits in Feb 2025 and AO3 hit 879M page views in the first week of Jan 2026, yet no product ships cursor-aware, spoiler-safe retrieval over these catalogs. The market is latent because authors can't fund it, platforms (AO3 especially) prohibit commercial scraping, and hyperscalers ignore the vertical — but a self-serve / browser-extension / author-opt-in wedge is viable.

**Market size:**
- **Royal Road:** ~14M visits in February 2025; top-5000 globally per Similarweb; 70/30 male/female, 18–24 core ([RoyalRoad Analysis 2025](https://medium.com/@hrule/royalroad-analysis-2025-86b92fae99d8), [Similarweb](https://www.similarweb.com/website/royalroad.com/)).
- **AO3:** 17.2M+ works in 77,400+ fandoms (Apr 2026); crossed 5M comments Dec 2025; peaked at 879M page views in the first week of Jan 2026 ([AO3 Statistics 2025 Update](https://www.transformativeworks.org/ao3-statistics-2025-update/), [AO3 Wikipedia](https://en.wikipedia.org/wiki/Archive_of_Our_Own)).
- **Webnovel.com:** global rank ~1,672, +13% MoM traffic; **Wuxiaworld:** rank ~14,848, +12% MoM ([Similarweb webnovel](https://www.similarweb.com/website/webnovel.com/), [Similarweb wuxiaworld](https://www.similarweb.com/website/wuxiaworld.com/)).
- **Scribble Hub:** ~116K registered users, 25,800 novels, 23.22M monthly visits (Dec 2025) ([SEMrush](https://www.semrush.com/website/scribblehub.com/overview/)).
- **Tapas:** 10M registered users, 75K creators, 100K series ([Jane Friedman Tapas Q&A](https://janefriedman.com/tapas-author-qa/)).
- **Substack fiction:** 50+ authors earn >$1M/yr across the platform; fiction specifically has standouts like Simon K Jones (6K+ subs) and Elle Griffin ($19K year 1) ([Quasa / Substack CEO](https://quasa.io/media/substack-s-ceo-reveals-over-50-authors-earn-1m-annually-through-paid-subscriptions), [pubstacksuccess](https://pubstacksuccess.substack.com/p/payments-for-fiction-writers-how)).

**Typical serial lengths:**
- **The Wandering Inn (pirateaba):** ~16M+ words across 10 volumes, 2016–present — arguably the longest single narrative fiction work ever written, dwarfing *A Christmas Carol*'s 28K by ~570x ([Wandering Inn stats](https://wanderinginn.neocities.org/statistics), [LitRPG FB group](https://www.facebook.com/groups/LitRPG.books/posts/24528808686715803/)).
- **Salvos (MelasD):** ~1M words published on Royal Road.
- Typical chapter release: 1.5K–5K words, often weekly ([Royal Road forums](https://www.royalroad.com/forums/thread/117095)).
- "Top Rising Stars" routinely cross 500K words in under a year; long-running hits sit at 2–5M words with 500+ chapters — already beyond a single-LLM-context fit, making KG retrieval a *requirement* rather than a nice-to-have.

**Reader fan-wiki infrastructure:**
- **Fandom-hosted wikis:** *The Wandering Inn Wiki* has 1,819 character pages; uses `{{status|Alive}}` spoiler tags to hide character fates; explicitly forbids Patreon-only spoilers until public release ([Wandering Inn Wiki](https://thewanderinginn.fandom.com/wiki/The_Wandering_Inn_Wiki)).
- **Self-hosted MediaWiki:** wiki.wanderinginn.com for fans who want the non-Fandom experience.
- Pain point from the community: "chapter pages list characters, but the reverse — character → chapter list — doesn't exist," exactly the query BookRAG's KG makes trivial.
- All wikis are volunteer-maintained, lag the serial by weeks-to-months, and are aggressively spoiler-prone above the fold.

**Existing tools for serials:**
- **No cursor-aware chatbot for any major web serial** as of April 2026 (searches returned zero products).
- Scattered fan projects (GitHub `fs-c/royalroad-api`, `EL-S/RoyalRoadAPI`) scrape HTML and export EPUBs, but stop at ingestion — no KG, no spoiler gate.
- SpoilerBlocker-style browser extensions exist for film/TV but not for web-serial wikis specifically.

**Distribution economics:**
- ~75% of successful Royal Road stories have Patreon links; typical author converts 7–20% of followers to patrons (median ~13%) ([Chapter Chronicles](https://www.chapterchronicles.com/blog/royal-road-patreon-2025/)).
- Patreon-gated chapters run 5–30 chapters ahead of public Royal Road drops — the "reader's cursor" literally differs between free and paid tiers.
- Substack fiction: paid tier typically $5–8/mo; Royal Road Premium is site-wide, not per-story.
- Aligns well with "reading companion as a $2–3 Patreon add-on tier" or a bundled feature at the top Substack paid tier.

**License / scraping concerns:**
- **AO3:** explicitly prohibits scraping for commercial use, including paid-access apps and commercial AI training; rate-limits and bans scrapers; no official API; allows non-commercial/academic scraping if done responsibly ([AI and Data Scraping on the Archive](https://www.transformativeworks.org/ai-and-data-scraping-on-the-archive/), [AO3 ToS](https://archiveofourown.org/tos)). **AO3 is effectively off-limits for a commercial BookRAG.**
- **Royal Road:** no official API, "anti-Amazon" protections explicitly target AI scrapers; unofficial scrapers exist but violate ToS for commercial use ([Royal Road anti-Amazon thread](https://www.royalroad.com/forums/thread/135707)).
- **Substack:** public RSS, cleanest legal path — author-opt-in via their own Substack is frictionless.
- **Wuxiaworld / Webnovel:** translated Chinese LN content, murky licensing, platform-gated paid chapters.
- **Kindle Vella:** discontinued by Amazon in 2025, leaving its serial readership migrating elsewhere.

**Pain points for current readers:**
- Forgetting 100+ character names across week-long gaps (LitRPG cast sizes are notorious).
- Re-reading 5M-word serials to catch up is infeasible; "previously on…" recaps don't exist.
- Looking up "who is X?" on Fandom wikis almost guarantees spoilers from future chapters.
- Patreon readers reading 10 chapters ahead of public need *differently-gated* lookups than free readers of the same serial.

**Concrete product hypothesis:**
BookRAG-for-serials ships as **three distribution wedges**:
- **(a) Browser extension:** reads chapter DOM on Royal Road/Scribble Hub/Substack, syncs cursor automatically, overlays a "who is this character?" sidebar. Client-side ingestion sidesteps the ToS commercial-scraping concern (user-owned copy, user-initiated).
- **(b) Author-side opt-in:** authors enroll their serial, BookRAG ingests via author-provided EPUB/Patreon RSS, offered as a premium Patreon tier ("your reading companion"). Revenue-share with author. This is the cleanest legal path and the strongest wedge for Royal Road's Patreon-heavy ecosystem.
- **(c) Standalone app:** user pastes chapters or uploads EPUB (same UX as current BookRAG), manual cursor tracking. Zero platform dependency.

**Similar products in other media:**
- **Sigmund.ai** (Marvel universe Q&A) — works because Marvel canon is stable and well-documented; proves the "ask questions about a giant fictional universe" pattern.
- **Hot Take / Netflix spoiler tags** — seconds-of-episode granularity; validates the cursor-aware UX.
- **Anime wiki spoiler tags** (MyAnimeList, AniList) — rudimentary reveal/hide toggles; pain point is exactly BookRAG's strength.

**Why this market is latent, not served:**
- Hyperscalers (OpenAI, Anthropic, Google) target enterprise RAG, not consumer fiction (iter. 20).
- Academic NLP focuses on public-domain canon (iter. 8) — Pride & Prejudice, not *The Wandering Inn*.
- OSS KG projects (LightRAG, GraphRAG, Cognee — iter. 16) are framework-level; none ship a serial-reader product.
- Platform-side: Royal Road/AO3 are community-run, thin-margin; they can't build this. Substack is generalist, not fiction-specialized.
- Authors individually lack the engineering budget. Readers individually won't pay enterprise-tier prices. The market is real but fragmented into $3/mo checks.

**Concrete research questions:**
- (a) Would Patreon-tier authors pay 20–30% rev-share for "your reading companion" if it measurably lifts conversion? Need 5–10 author interviews, ideally Wandering Inn / Mother of Learning / Beware of Chicken scale.
- (b) Would readers pay $3–5/mo for a third-party cross-serial app, or is the WTP actually $0 (= browser extension with ads)?
- (c) Is the "paste your chapter" self-serve flow the MVP, or does the extension's auto-cursor-sync create enough lift to be worth shipping first?
- (d) Does AO3's non-commercial scraping carveout permit a fully-local, open-source, donation-funded variant?

**Key citations:**
- [RoyalRoad Analysis 2025](https://medium.com/@hrule/royalroad-analysis-2025-86b92fae99d8)
- [AO3 Statistics 2025 Update](https://www.transformativeworks.org/ao3-statistics-2025-update/)
- [AI and Data Scraping on the Archive (AO3)](https://www.transformativeworks.org/ai-and-data-scraping-on-the-archive/)
- [The Wandering Inn Statistics](https://wanderinginn.neocities.org/statistics)
- [Royal Road Patreon Analysis — Chapter Chronicles](https://www.chapterchronicles.com/blog/royal-road-patreon-2025/)
- [Substack CEO on $1M+ authors (Quasa)](https://quasa.io/media/substack-s-ceo-reveals-over-50-authors-earn-1m-annually-through-paid-subscriptions)
- [Tapas Author Q&A — Jane Friedman](https://janefriedman.com/tapas-author-qa/)
- [Scribble Hub Traffic — SEMrush](https://www.semrush.com/website/scribblehub.com/overview/)
- [fs-c/royalroad-api (unofficial)](https://github.com/fs-c/royalroad-api)

**Concrete ideas worth stealing:**
- Ship browser-extension wedge first — client-side ingestion dodges the AO3/Royal Road commercial-scraping ToS landmine and auto-syncs the reader's cursor (current_chapter) from the URL/scroll position, which is *exactly* BookRAG's existing spoiler-gate primitive.
- Use `batch_size=1` as the default for serials (not the opt-in it is for novels) — chapters already arrive one at a time, so per-chapter snapshot extraction is zero-cost overhead and maximizes per-identity fidelity.
- Offer authors a "Patreon tier bot" rev-share product before a consumer app — authors already price-signal via Patreon, and enrollment sidesteps platform ToS entirely.
- Treat the Fandom-wiki "character → chapters appearing in" inverse index as a killer feature: it's what fans already manually hack together, and the KG gives it for free.
- The Wandering Inn's 16M words at 570x *A Christmas Carol* is the natural stress test for BookRAG's scaling — pick one chapter-1-to-now cursor test case and it validates the entire ingestion + retrieval stack against the most pathological realistic input.

### 34. FANToM + theory-of-mind benchmarks

**Researched:** 2026-04-22 (iteration 34 — bonus)

**TL;DR:** The theory-of-mind (ToM) benchmark literature (FANToM, BigToM, ToMi, Hi-ToM, OpenToM, SimToM) has spent five years formalizing exactly the problem BookRAG's spoiler filter solves: given a world with facts that different observers have differentially witnessed, answer questions consistent with a chosen observer's knowledge state. BookRAG's reader-cursor is a degenerate ToM case (the reader is one more observer whose knowledge state is being projected), and "talk to Scrooge at chapter 3" is a direct ToM inference task that existing character DataPoints don't yet implement. Running BookRAG on FANToM is not a drop-in evaluation but its question templates (BeliefQ / AnswerabilityQ / InfoAccessQ) port cleanly to book passages.

**FANToM (Kim et al. EMNLP 2023, arXiv 2310.15421):** Multi-party conversations generated by GPT-4 and human-validated, in which characters join and leave a conversation, producing deliberate information asymmetry. Questions come in three families: BeliefQ (choice or free-response — "what does character X believe about fact F?"), AnswerabilityQ (list or binary — "who in the conversation can answer question Q?"), and InfoAccessQ (list or binary — "who has access to information I?"), plus a FactQ baseline for comprehension (Kim et al. 2023, [ACL Anthology](https://aclanthology.org/2023.emnlp-main.890/), [project page](https://hyunw.kim/fantom/)). The eval is refusal-aware: scoring credits models that correctly decline to answer when a character lacks the information. Headline numbers: human "All Question Types" score is 87.5%; GPT-4 0613 scores 8.2% without CoT and 26.6% with CoT. Models do well on BeliefQ[Choice] (73.3% for GPT-4) but collapse on AnswerabilityQ[List] (28.6%) — i.e., they can pick the "right" belief when forced to, but can't enumerate who knows what. This is the "illusory ToM" diagnostic.

**Other ToM benchmarks:**
- **BigToM (Gandhi et al. NeurIPS 2023, arXiv 2306.15448):** Procedurally generated from causal templates linking percepts → beliefs → desires → actions. 25 controls × 5,000 model-written evaluations; tests forward and backward inference across the causal graph. GPT-4 "mirrors human inference patterns, though less reliable"; smaller models struggle ([NeurIPS 2023 paper](https://papers.neurips.cc/paper_files/paper/2023/file/2b9efb085d3829a2aadffab63ba206de-Paper-Datasets_and_Benchmarks.pdf)).
- **ToMi (Le et al. EMNLP 2019):** Templatic Sally-Anne-style corpus with distractor sentences and reorderings; first- and second-order false-belief probes. The de facto ToM baseline for NLP ([facebookresearch/ToMi](https://github.com/facebookresearch/ToMi)).
- **Hi-ToM (He et al., Findings of EMNLP 2023, arXiv 2310.16755):** Extends ToMi to higher-order recursion ("A believes that B believes that C believes..."). All tested LLMs decline monotonically with order.
- **OpenToM (Xu et al. ACL 2024, arXiv 2402.06044):** Longer narrative stories with explicit character personalities and intention-driven actions; splits physical-world ToM from psychological-world ToM. Finding: SOTA models handle physical state tracking but fail on psychological state.
- **SimToM (Wilf et al., arXiv 2311.10227):** Not a benchmark but a prompting method — two-stage perspective-taking where stage 1 filters context to "what character X knows" before stage 2 answers the ToM question. Substantial gains on ToMi/BigToM with no fine-tuning.

**Results headline across the landscape:** the human–model gap is largest on set-based and refusal-aware metrics (FANToM AnswerabilityQ[List], Hi-ToM higher orders, OpenToM psychological). Typical failure mode: models default to a privileged (omniscient) viewpoint rather than projecting to the queried character. CoT helps modestly; perspective-taking prompts (SimToM) and explicit symbolic state (SymbolicToM) help more.

**Connection to narrative:** novels are continuous ToM exercises — the reader tracks who-knows-what across hundreds of pages, and much of the plot tension comes from asymmetric belief (dramatic irony = reader knows what character doesn't). BookRAG has so far treated the reader as the single "observer" whose cursor gates the graph. But the same math applies per character: each character has witnessed a subset of on-page events and is privy to a subset of told-but-not-witnessed events.

**Theory: BookRAG's spoiler filter is the 1-of-N case of a character-knowledge projection.** Formalize: world state W is a multiset of facts {f_1, ..., f_n}, each annotated with a first-known position c_i (cursor ordinal — could be chapter, paragraph, or token offset). An observer X has a knowledge function K_X: Facts → {seen, unseen} determined by X's trajectory through the narrative. For the reader, K_reader(f_i) = seen iff c_i ≤ cursor_reader — this is exactly what `pipeline/spoiler_filter.py::load_allowed_nodes` computes via `effective_latest_chapter`. For a character C, K_C(f_i) = seen iff (C was on-page when f_i was narrated) OR (some other character who knew f_i told C before cursor_reader). The reader projection is a pure cursor comparison; the character projection additionally requires tracking tell-events (dialogue, letters, overheard speech). Same retrieval shape, different witness predicate.

**Implementing "talk to Scrooge at chapter 3" as ToM inference:** step 1, compute Scrooge's on-page witness set — scenes where Scrooge appears in chapters 1–3 (derivable from BookNLP character tags on the parenthetical-coref text). Step 2, compute Scrooge's told set — facts mentioned in dialogue directed at Scrooge or in his presence (BookNLP quote attribution gives addressee). Step 3, optionally run SimToM-style perspective filtering: pass the chapter 1–3 raw text through an LLM with the prompt "list only facts Scrooge would know as of end-of-chapter-3." Step 4, filter the KG allowlist to nodes in that union. Step 1+2 are cheap graph ops; step 3 is the expensive but highest-fidelity option, and it mirrors SymbolicToM's explicit per-character belief graph (Sclar et al. ACL 2023 Outstanding Paper, [ACL Anthology](https://aclanthology.org/2023.acl-long.780/), [github.com/msclar/symbolictom](https://github.com/msclar/symbolictom)).

**Running BookRAG against FANToM — viability.** Not a drop-in: FANToM is dialog-scale (~minute-long multi-party chats) and BookRAG is book-scale (chapters). But the protocol transfers: (a) pick a chapter boundary as a cursor; (b) generate BeliefQ/AnswerabilityQ/InfoAccessQ about characters using the existing Character DataPoints; (c) score against an oracle built from full-book extraction. The expensive ingredient is the oracle — FANToM had humans label; for BookRAG a study guide or SparkNotes can serve as partial gold. A realistic scope is a "FANToM-Books" mini-eval on Christmas Carol and Red Rising: ~50 questions each across the three families.

**Plug-and-Play Multi-Character Belief Tracker (Sclar et al. ACL 2023, arXiv 2306.00924):** SymbolicToM maintains an explicit graph per character of "what X believes about Y's beliefs about Z...", updated as the narrative unfolds, and used as a side-channel context filter before the base LLM answers. Zero-shot and robust OOD. Architectural fit with BookRAG: Character DataPoints already have a `known_facts` slot conceptually — SymbolicToM's update rules (on-page witnessing, told-about events, and nested belief updates for dialogues) could populate per-character snapshot sets in the same per-batch loop that currently produces `last_known_chapter`. Output: every Character node carries a `known_node_ids: set[str]` field, and the query API accepts a `character_id` parameter that intersects the reader-cursor allowlist with that set.

**Open research question for BookRAG:** is cursor-aware retrieval enough, or is per-character knowledge projection needed? Concrete test: in Christmas Carol, Scrooge witnesses Marley's ghost (chapter 1) but never tells Cratchit. A query "what does Cratchit know about Marley as of chapter 2?" should exclude the ghost visitation. Today's BookRAG would surface it because both facts are ≤ cursor. This is a ToM failure — the spoiler filter is observer-agnostic once the cursor is set. The fix is either (a) character-conditioned retrieval (intersect cursor allowlist with per-character witness set) or (b) refuse to answer "as-character" questions. Option (a) is a real feature; option (b) is the honest punt.

**Key citations:**
- Kim et al., FANToM, EMNLP 2023 — [arXiv 2310.15421](https://arxiv.org/abs/2310.15421), [ACL Anthology](https://aclanthology.org/2023.emnlp-main.890/)
- Gandhi et al., BigToM, NeurIPS 2023 — [arXiv 2306.15448](https://arxiv.org/abs/2306.15448)
- Le, Boureau, Nickel, ToMi, EMNLP 2019 — [github.com/facebookresearch/ToMi](https://github.com/facebookresearch/ToMi)
- He et al., Hi-ToM, Findings of EMNLP 2023 — [arXiv 2310.16755](https://arxiv.org/abs/2310.16755)
- Xu et al., OpenToM, ACL 2024 — [arXiv 2402.06044](https://arxiv.org/abs/2402.06044)
- Wilf et al., SimToM — [arXiv 2311.10227](https://arxiv.org/abs/2311.10227)
- Sclar et al., SymbolicToM, ACL 2023 Outstanding Paper — [arXiv 2306.00924](https://arxiv.org/abs/2306.00924), [ACL Anthology](https://aclanthology.org/2023.acl-long.780/)

**Concrete ideas worth stealing:**
- Adopt FANToM's three question families (BeliefQ, AnswerabilityQ, InfoAccessQ) as the template for a BookRAG "character-aware" eval harness; score them refusal-aware so "I don't know — Scrooge hasn't seen that" is credited.
- Add a `known_node_ids` set to Character DataPoints, populated during Phase 2 extraction via a SymbolicToM-style witness/told update rule per batch.
- Prototype "talk to character X at cursor c" via a SimToM two-stage prompt: stage 1 computes X's knowledge set from on-page witness + dialogue-addressee heuristics; stage 2 answers over that filtered context.
- Use the AnswerabilityQ[List] format as a diagnostic: ask BookRAG "which characters in Christmas Carol as of chapter 3 would know about Marley's ghost?" — current system cannot answer; this is a concrete test for per-character projection.
- Frame the spoiler filter externally as "ToM-consistent retrieval" — it gives BookRAG a legible NLP-literature position ("observer-projected retrieval over a temporal KG") rather than the idiosyncratic "spoiler filter" framing.
- Steal Hi-ToM's order-counting idea as a future ambition: order-2 belief queries ("what does Scrooge believe Cratchit knows about Marley?") are the natural extension once order-1 works.

### 35. LiteraryQA + LiSCU — under-explored corpora

**Researched:** 2026-04-22 (iteration 35 — bonus)

**TL;DR:** LiteraryQA (Sapienza NLP, EMNLP 2025) is a cleaned 138-book / 3,785-QA subset of NarrativeQA restricted to literary works, with Gutenberg boilerplate stripped and bad QA pairs filtered — and it establishes that n-gram metrics (BLEU/ROUGE/METEOR) are nearly useless for long-document narrative QA (low system-level correlation with humans) while a small LLM-as-Judge (Prometheus 2 7B) reaches 0.68 correlation. LiSCU (Brahman et al., Findings of EMNLP 2021) is a distant-supervision corpus of literary summaries paired with character descriptions scraped from SparkNotes, LitCharts, CliffsNotes, and Shmoop; the summary partition has ~9,499 samples and the test split ~957. Both are research-only licensed and most directly useful to BookRAG as held-out evaluation signals — LiSCU for Character-DataPoint description quality, LiteraryQA for end-to-end QA faithfulness on overlapping public-domain books.

**LiteraryQA:**
- Authors: Tommaso Bonomo, Luca Gioffré, Roberto Navigli (Sapienza NLP) ([arXiv 2510.13494](https://arxiv.org/abs/2510.13494), [ACL Anthology 2025.emnlp-main.1729](https://aclanthology.org/2025.emnlp-main.1729/)).
- Size: 138 documents, 3,785 QA pairs after refinement (down from NarrativeQA's 355 docs / 10,557 QA pairs). Filtering removed 178 movies, 20 plays, 11 non-narrative works, 8 mismatched samples; an additional 125 duplicate QA and 308 double-corrected samples were dropped.
- Cleaning methodology: algorithmic extraction from original HTML removed HTML/Markdown tags, Project Gutenberg headers/footers, and legal license text; encoding fixes (e.g., "Ăvariste" → "Évariste"). Documents average ~3,000 tokens shorter post-cleaning.
- Metric finding: all n-gram metrics have low system-level correlation with human judgment; summary-based LLM-as-Judge is the recommended protocol. Prometheus 2 7B hits 0.68 system-level correlation — an open-weight model is enough.
- License: CC BY-NC-SA 4.0 on the cleaned dataset; book bodies come from Project Gutenberg public domain. Data + code: [SapienzaNLP/LiteraryQA](https://github.com/SapienzaNLP/LiteraryQA).
- Representative titles named in the paper: 20 annotated books including works by James Joyce, Jack London, Arthur Conan Doyle, and Joseph Conrad.

**NarrativeQA background (for contrast):**
- Kočiský et al. 2018, TACL ([aclanthology.org/Q18-1023](https://aclanthology.org/Q18-1023/)). Original size: 355 documents (books + movie scripts), 10,557 QA pairs. Questions/answers were authored by crowdworkers from Wikipedia/study-guide summaries (not from the full text), which is precisely the noise LiteraryQA addresses: questions reference plot events that don't appear in the Gutenberg text as scraped, and source documents contained Gutenberg license boilerplate.

**LiSCU (Literary-Structured / Stories Character Understanding):**
- Authors: Faeze Brahman, Meng Huang, Oyvind Tafjord, Chao Zhao, Mrinmaya Sachan, Snigdha Chaturvedi. Findings of EMNLP 2021 ([arXiv 2109.05438](https://arxiv.org/abs/2109.05438), [ACL Anthology 2021.findings-emnlp.150](https://aclanthology.org/2021.findings-emnlp.150/)).
- Composition: literary pieces + their summaries paired with character descriptions, scraped from four study-guide sites: Shmoop, SparkNotes, CliffsNotes, LitCharts.
- Size: LiSCU-summary partition ~9,499 (book-summary, character-description, character-name) triples; test split ~957 examples. Splits are stratified by book to avoid leakage. Full-book version exists but most tasks run over the summary partition.
- Tasks: (i) Character Identification — given a description with the name masked, pick the correct character from a candidate set; (ii) Character Description Generation — given a summary and character name, generate the description.
- Implicit spoiler handling: none — descriptions are whole-book summaries, so every description is maximally spoiler-laden. This is the opposite of BookRAG's retrieval discipline and would need paragraph-level alignment before being reused as cursor-aware training signal.
- Distribution: the original data was not released as a single archive; the reproduction repo [huangmeng123/lit_char_data_wayback](https://github.com/huangmeng123/lit_char_data_wayback) rebuilds the corpus by scraping Wayback Machine copies of study-guide pages.

**Ethics / license posture:**
- SparkNotes, LitCharts, CliffsNotes, and Shmoop content is copyrighted; LiSCU sidesteps direct redistribution by shipping scraper scripts that users run themselves against Wayback Machine snapshots. This is a fair-use research posture, not a commercial-use license. Any BookRAG commercial product that fine-tunes on LiSCU inherits downstream IP risk.
- LiteraryQA's own annotations are CC BY-NC-SA 4.0 (NonCommercial + ShareAlike) — also research-only, and the ShareAlike provision would virally attach to any derivative corpus BookRAG releases.
- Practical read: both corpora are safe for BookRAG's internal academic-style evaluation and ablations; neither is safe for shipping a commercial model trained directly on them.

**Size estimates (consolidated):**
- LiteraryQA: 138 books, ~3.8k QA; books are full-length Gutenberg novels (tens of thousands of tokens each).
- LiSCU-summary: ~9.5k summary+character-description samples across hundreds of book titles (study guides cover the secondary-school / college canon — Austen, Dickens, Shakespeare, Fitzgerald, Steinbeck, etc.).
- LiSCU full-book variant is smaller (only ~100s of books are available in Gutenberg-public-domain form among those covered by the study guides).

**Eval protocol possibilities for BookRAG:**
- (a) Take the intersection of LiteraryQA's 138 books with BookRAG-ingestible Gutenberg titles; run BookRAG in GRAPH_COMPLETION mode at `current_chapter = last_chapter` (full-book cursor) and score answers with summary-based Prometheus-2-as-Judge. This gives a standing, defensible faithfulness number (0–1) against an EMNLP 2025 benchmark.
- (b) Use LiSCU character descriptions as distant-supervision gold for BookRAG's Character DataPoint `description` field — score via ROUGE-L + an LLM judge prompted with "does BookRAG's description match the gold description in role, traits, arc?" Caveat: LiSCU descriptions cover the entire book; BookRAG's descriptions should only match LiSCU when the reader cursor is at book-end.

**Training data possibilities:**
- (c) LiSCU (summary, character_name) → description triples are directly usable as SFT for a fine-tuned Character extractor. The training cost is that the model learns to produce whole-book spoiler-laden descriptions — which is the wrong behavior for BookRAG. Use only if paired with a cursor-masking augmentation that truncates the input summary.
- (d) LiteraryQA (question, summary/book → answer) pairs are viable SFT for answer synthesis. 3,785 is small (comparable to few-shot regimes), so better suited to DPO / preference-tuning against BookRAG's own draft answers.

**Overlap with BookRAG's book fixtures:**
- A Christmas Carol: not confirmed in LiteraryQA's named examples (paper highlights 20 titles, Dickens not among them; full 138-title list not public in the abstract — needs repo inspection). Likely in LiSCU (SparkNotes/LitCharts both have Christmas Carol guides). Action item: clone the LiSCU reproduction repo and grep for "Christmas Carol".
- Red Rising: not in LiteraryQA (Gutenberg-only + published 2014, still in copyright). Unlikely in LiSCU-summary at the time of the 2021 crawl; if present, only via LitCharts (which covers post-2000 YA/adult fantasy).

**Comparison with other narrative corpora:**
- vs. LitBank (iter 6): LitBank is token-level entity/coref gold on 100 books, ~2k tokens each. Complementary — LitBank trains components, LiSCU/LiteraryQA evaluate end-to-end QA and character generation.
- vs. FABLES (iter 8): FABLES is faithfulness judgments over LLM-generated book summaries. LiteraryQA provides the same spirit (human-grounded faithfulness) but on QA rather than free-form summarization.
- vs. PDNC (iter 7): PDNC is quote-speaker gold for novels. Orthogonal axis — PDNC evaluates the `Quote → Character` edge, LiSCU evaluates the `Character → description` node.
- Unique niche for LiteraryQA: the only long-document narrative QA benchmark with cleaned Gutenberg bodies and a validated LLM-as-Judge protocol.
- Unique niche for LiSCU: the only large-scale gold-standard character description corpus — nothing else in the space (PeoLM, CHIA, FriendsQA) targets summary → character-description generation.

**Key citations:**
- LiteraryQA: Bonomo, Gioffré, Navigli, EMNLP 2025 — [arXiv 2510.13494](https://arxiv.org/abs/2510.13494), [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1729/), [GitHub SapienzaNLP/LiteraryQA](https://github.com/SapienzaNLP/LiteraryQA).
- LiSCU: Brahman et al., Findings of EMNLP 2021 — [arXiv 2109.05438](https://arxiv.org/abs/2109.05438), [ACL Anthology 2021.findings-emnlp.150](https://aclanthology.org/2021.findings-emnlp.150/), [reproduction repo huangmeng123/lit_char_data_wayback](https://github.com/huangmeng123/lit_char_data_wayback).
- NarrativeQA: Kočiský et al., TACL 2018 — [ACL Anthology Q18-1023](https://aclanthology.org/Q18-1023/).

**Concrete ideas worth stealing:**
- Adopt LiteraryQA's summary-based Prometheus-2 7B LLM-as-Judge as BookRAG's official faithfulness metric; this single decision retires BLEU/ROUGE from the backend eval suite and aligns with 2025 SOTA.
- Treat LiteraryQA's cleaning pipeline (HTML strip + Gutenberg header/footer + license-section removal + diacritic fix) as a reference checklist for `pipeline/text_cleaner.py` — LiteraryQA reports documents are ~3,000 tokens shorter after cleaning; BookRAG should measure the same delta as a QA signal on its own cleaner.
- Cross-reference BookRAG Character DataPoints against LiSCU descriptions only for overlapping books and at end-of-book cursor — this gives a "does our extractor roughly converge to the canonical SparkNotes character sketch?" sanity check without committing to train on copyrighted content.
- Steal the idea of per-QA "modification flags" from LiteraryQA's schema: every BookRAG validation item should carry a provenance flag (auto-generated / human-edited / LLM-corrected) so dataset drift is auditable.
- Use LiteraryQA's filter rationale as documentation for BookRAG's own corpus policy: "we exclude movies, plays, and non-narrative works; we keep prose novels only" is a defensible, citable scope statement.
- The single most actionable insight: replace BookRAG's current free-form faithfulness scoring with the LiteraryQA protocol on the overlap subset — it immediately makes BookRAG's eval legible to reviewers familiar with the 2025 literature.

### 36. iText2KG + DIAL-KG — LLM-adjudicated incremental merge

**Researched:** 2026-04-22 (iteration 36 — bonus)

**TL;DR:** iText2KG (WISE 2024) and DIAL-KG (arXiv March 2026) both solve the "conflicting extractions on re-ingest" problem by resolving before merging, but with very different mechanisms: iText2KG uses embedding cosine similarity at a 0.7 threshold to match new entities against a growing global set, while DIAL-KG runs a three-verdict LLM adjudication ({Merge, Hierarchy, Separate}) inside same-type embedding clusters and tracks an evolving Meta-Knowledge Base. Neither — nor Graphiti's LLM edge-invalidation — handles the *cursor-aware merge* that BookRAG's spoiler semantics require, so the problem is only partially solved; we can adopt their resolver prompts but need a spoiler-aware wrapper on top.

**iText2KG (Lairgi et al. 2024):** Yassir Lairgi and 4 co-authors, accepted at WISE 2024 (International Web Information Systems Engineering), arXiv 2409.03284, code at github.com/AuvaLab/itext2kg. Architecture is four modules [1]: (1) **Document Distiller** — an LLM is prompted with a user-defined JSON schema ("blueprint") and extracts schema-conformant semantic blocks, reducing downstream noise; (2) **Incremental Entity Extractor** — extracts local entities per block, then matches against a growing global set using **cosine similarity over text-embedding-3-large with threshold 0.7**; merge if above, otherwise add to global set; (3) **Incremental Relations Extractor** — supports two modes: global-entity context (richer graph, more noise) vs local-entity context (~10% lower recall, higher precision); (4) **Graph Integrator** — writes to Neo4j. Threshold calibrated on 1,500 entity pairs + 500 relation pairs (entity mean 0.60±0.12, relation 0.56±0.10; 0.7 chosen for high precision). Evaluated on CVs, scientific papers, and company websites with Schema Consistency, Information Consistency, Triplet Precision, and Entity/Relation Resolution FDR — beats baselines on all three scenarios. Notably **no LLM in the merge loop** — the merge is purely embedding-driven, so iText2KG is cheaper but dumber than DIAL-KG.

**DIAL-KG (Schema-Free Incremental KG Construction, arXiv 2603.20059, March 2026):** Three-stage closed-loop architecture anchored by a **Meta-Knowledge Base (MKB)** of entity profiles (canonical name, aliases, type) and schema proposals [2]. Stage 1 Dual-Track Extraction (triples for static facts, events for complex/temporal). Stage 2 **Governance Adjudication** — the core of the system and the directly relevant piece: (a) *Evidence Verification* — LLM rejects a candidate only if the text directly contradicts it (conservative); (b) *Logical Verification* — reflexive-relation and inverse-pair contradiction removal plus schema-constraint checking (e.g., `ceo_of` must connect Person→Organization); (c) *Evolutionary-Intent Verification* — LLM tags each normalized event as Informational or Evolutionary, and Evolutionary triggers ("deprecated", "removed", "no longer") drive **soft deprecation** of prior facts. Entity adjudication runs at two levels: *intra-batch normalization* clusters by embedding similarity within same type, then LLM decides {Merge, Hierarchy, Separate} pairwise; *cross-batch alignment* matches new entities against historical MKB profiles. Stage 3 Schema Evolution — novel relation types become MKB schema proposals that guide subsequent batches (self-evolving constraints, no predefined ontology). Evaluation: F1 0.865 (WebNLG), 0.853 (Wiki-NRE), 0.922 (SoftRel-Δ) beating EDC and AutoKG; Δ-Precision ≥0.97; Deprecation-Handling Precision >0.98; 15% fewer relation types with 1.6–2.8pt redundancy reduction vs EDC.

**Algorithm comparison:**

| System | Merge signal | Conflict resolution | Temporal model |
|---|---|---|---|
| iText2KG | Embedding cosine ≥0.7 | None — latest write-wins after match | None |
| DIAL-KG | Embedding cluster → LLM {Merge, Hierarchy, Separate} | LLM Evolutionary-Intent tag → soft-deprecate prior fact | Event-based deprecation |
| Graphiti/Zep (iter 29) | LLM compares new edge to semantically-related existing edges | LLM sets `t_invalid` on contradicted edges to `t_valid` of invalidator | Bi-temporal: event time T + ingestion time T′ [3] |
| LightRAG summary-merge (iter 2) | Same-name entities concatenated, LLM re-summarizes | Implicit — re-summarization smooths conflicts | None |

Same across all four: embedding or lexical candidate retrieval, then LLM decision. Different: the *decision space* — iText2KG binary (merge/not), LightRAG collapse (always merge into summary), DIAL-KG ternary+deprecation, Graphiti invalidation with timestamps. Graphiti and DIAL-KG are the only two that preserve superseded state.

**Applicability to BookRAG:** Today BookRAG's merge is implicit "latest-batch wins per identity" inside `load_allowed_nodes` — it picks the latest snapshot whose `effective_latest_chapter` ≤ cursor (see `pipeline/spoiler_filter.py`, per Phase 2 notes in CLAUDE.md). This is effectively iText2KG without the embedding match: we rely on exact identity keys from BookNLP coref. DIAL-KG's ternary adjudicator is the closest conceptual fit because Character entities in literature genuinely have the three cases (the Ghost of Christmas Past = same as Spirit #1? Scrooge-nephew vs Scrooge? Fezziwig's clerk vs Scrooge-clerk?). Graphiti's temporal invalidation maps cleanly onto relationships-that-change-over-plot (Scrooge→Jacob Marley `business_partner` at t=chapter_1 invalidated by Marley's death).

**Merge-as-spoiler constraint (new in BookRAG):** Here is the crucial gap none of these systems address. When merging two Character snapshots from different cursors, **you cannot use the later snapshot's description to "improve" the earlier one if the reader's cursor is ≤ earlier**. In iText2KG terms: the global entity set is itself cursor-dependent. In DIAL-KG terms: Evidence Verification must consider not just "does text support this" but "is this text visible at cursor C." In Graphiti terms: the bi-temporal model needs a third axis — *reader knowledge time* — distinct from event time and ingestion time. Re-ingesting chapter 5 cannot retroactively improve the chapter-2 view of Scrooge. This is the novel contribution — "merge-as-spoiler" / "cursor-aware merge" — that I have not found in any 2024–2026 literature.

**Concrete merge-upgrade design for BookRAG:**
1. **Relationship edges → Graphiti edge-invalidation.** For Relationship DataPoints, store `valid_from_chapter` and `invalid_from_chapter`. When a new batch produces a contradictory edge (same source/target, incompatible predicate), run Graphiti's LLM-compare prompt and set `invalid_from_chapter = new edge's valid_from_chapter`. At query time, filter edges where `valid_from_chapter ≤ cursor < (invalid_from_chapter or ∞)`.
2. **Character/Location attribute conflicts → DIAL-KG adjudicator.** Adopt the {Merge, Hierarchy, Separate} prompt on same-type embedding clusters of Character descriptions. Hierarchy is particularly useful for literature (Ghost-of-Christmas-Past is-a Spirit).
3. **Cursor-aware wrapper — BookRAG-novel layer.** Do NOT collapse snapshots at ingestion. Keep per-batch snapshots indexed by `(identity, snapshot_chapter)`. Run the DIAL-KG adjudicator **at query time, scoped to snapshots with `snapshot_chapter ≤ cursor`**. Cache per-cursor adjudication results (cursor changes monotonically forward per reader, so cache is warm-on-scroll). This is the piece the literature doesn't provide.
4. **Do NOT adopt iText2KG's 0.7 cosine threshold directly.** BookNLP already gives us coref-resolved identity keys; embedding match is a backup, not the primary signal. Use it only for cross-identity suggestions ("are these two BookNLP clusters actually the same character?") flagged for human review in `ontology_reviewer.py`.

**Key citations:**
1. Lairgi, Y. et al. "iText2KG: Incremental Knowledge Graphs Construction Using Large Language Models." WISE 2024. arXiv:2409.03284. https://arxiv.org/abs/2409.03284 / https://github.com/AuvaLab/itext2kg
2. "DIAL-KG: Schema-Free Incremental Knowledge Graph Construction via Dynamic Schema Induction and Evolution-Intent Assessment." arXiv:2603.20059, March 2026. https://arxiv.org/html/2603.20059
3. Rasmussen, P. et al. "Zep: A Temporal Knowledge Graph Architecture for Agent Memory." arXiv:2501.13956, Jan 2025. https://arxiv.org/html/2501.13956v1
4. Graphiti repo: https://github.com/getzep/graphiti (cross-ref iter 29)

**Concrete ideas worth stealing:**
- DIAL-KG's **ternary Merge/Hierarchy/Separate** verdict — directly usable as the Cognee post-processing prompt for Character entities. Hierarchy captures literary type/instance (Spirit → Ghost of Christmas Past) that BookRAG has no current representation for.
- DIAL-KG's **Evolutionary-Intent tag** — adapt the "deprecated/removed" trigger list to literary equivalents ("died", "left", "became", "revealed as") for relationship-edge invalidation.
- iText2KG's **Document Distiller schema-first prompt** — already aligns with BookRAG's DataPoint Pydantic schemas; we could strengthen the extraction prompt by explicitly passing the Character/Location/Relationship JSON schema as a blueprint, not just field names.
- Graphiti's **bi-temporal edges** (t_valid / t_invalid) — straight port to Relationship DataPoints as `valid_from_chapter` / `invalid_from_chapter`, enabling "what did Scrooge think of Marley at chapter 2" queries that today's graph cannot answer.
- DIAL-KG's **MKB entity profile (canonical + aliases + type)** — this is exactly what BookRAG's identity key should evolve into; currently identity is a bare string from BookNLP.
- **The novel piece BookRAG must invent**: cursor-indexed snapshot storage with query-time adjudication. No 2024–2026 paper does this; it is a publishable delta.

---

### 37. Interactive fiction, CYOA & TTRPG campaign KGs

**Researched:** 2026-04-22 (iteration 37 — bonus round 2)

**TL;DR:** Interactive fiction engines (Inform 7, Ink, Twine) model narrative state as declarative properties/relations or typed variables, but none of them solve BookRAG's problem — they *author* branching state rather than *observe* a fixed narrative through a moving reader cursor. TTRPG tools like World Anvil, Kanka, and Foundry VTT have the closest analogue (per-player visibility toggles, subscriber-group secrets), but these are manually curated by the GM, not derived from content. The AI-DM space (AI Dungeon, SessionKeeper, Archivist, Loreify) is emerging and uses vector memory + summarisation, but no commercial tool treats "spoiler fidelity" as a first-class constraint the way BookRAG does.

**Interactive fiction engines & state modeling:**
Inform 7 models the world via **object properties and relations between entities**, with rooms, containers, inventory, and player location tracked as mutable state that evolves from an initial configuration through rule-governed actions ([Wikibooks: Beginner's Guide to IF with Inform 7](https://en.wikibooks.org/wiki/Beginner%27s_Guide_to_Interactive_Fiction_with_Inform_7); [Strange Loop 2014 talk](https://www.thestrangeloop.com/2014/intro-to-modeling-worlds-in-text-with-inform-7.html)). Descriptions of rooms and objects can be **conditioned on state** (e.g., "the description of a room might change if a container is open or closed") — a primitive similar in spirit to BookRAG's chapter-conditioned node descriptions, but authored not extracted. Ink (inkle) uses **typed variables** (numbers, strings, booleans) plus a **LIST type** that acts as "a rack of numbered flip-switches" for inventories or presence-tracking ([inkle Ink docs](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md); [VariablesState.cs](https://github.com/inkle/ink/blob/master/ink-engine-runtime/VariablesState.cs)). Ink's standout feature for BookRAG's purposes is **parallel shared-state story-flows** — simultaneous NPC conversations that mutate a shared world — which is structurally similar to BookRAG needing a coherent graph across multiple reader-position projections. Twine's Harlowe/SugarCube have similar variable-based state. TADS and Glulx (the VM underneath Inform) add richer object systems but remain authorship-oriented.

**CYOA / branching narrative research:**
Mark Riedl's **Scheherazade** (Li & Riedl, AAAI 2015) learns **plot graphs** — partially-ordered graphs of events — by crowdsourcing narratives for a given scenario and sampling interactive playable narratives from the learned space ([AAAI PDF](https://faculty.cc.gatech.edu/~riedl/pubs/aaai15.pdf); [Georgia Tech GVU project page](https://gvu.gatech.edu/research/projects/scheherazade-story-generator)). The plot-graph formalism is relevant: BookRAG's per-chapter extraction is effectively building a plot graph of the book a posteriori, and the "partial order" constraint is a hint that causal/temporal ordering should be first-class (cf. iteration 32 on temporal KGs). Riedl's 2021 [Medium introduction to AI story generation](https://mark-riedl.medium.com/an-introduction-to-ai-story-generation-7f99a450f615) surveys Propp-style generators through LLM-era methods.

**Disco Elysium & 80 Days analysis:**
Post45's "Disco Elysium and Narrative Superposition" ([post45.org 2024](https://post45.org/2024/04/disco-elysium-and-narrative-superposition/)) characterises the game's state as a **dense narrative superposition** — every potential narrative coexists until player action collapses it. This is directly analogous to BookRAG's position: at a given reader cursor, a superposition of possible descriptions for each entity exists (across batches/chapters), and the retrieval layer must collapse to the correct one. Disco Elysium uses extensive **skill-check variables** and a flag system (the "Thought Cabinet" mechanic) to gate dialogue and descriptions — a manual per-player-state projection much like World Anvil's visibility toggle but runtime-evaluated.

**TTRPG campaign tools & per-PC knowledge models:**
- **World Anvil** has the most developed per-reader visibility: a **Visibility Toggle** for article sections, **Secrets** (separately-authored content embedded in articles, with per-subscriber-group gating), and BBCode `[spoiler]` tags for inline hiding ([World Anvil Visibility Toggle blog](https://blog.worldanvil.com/worldanvil/dev-news/introducing-the-visibility-toggle-show-to-your-players-only-what-you-want-them-to-see/); [Loreteller: WA Secrets Guide](https://loreteller.com/learn/world-anvil-secrets-guide/)). All manually curated.
- **Kanka** offers **granular per-entity permissions** with custom roles and per-article overrides ([Kanka docs, via PhD20's 2025 guide](https://phd20.com/blog/ultimate-guide-ttrpg-campaign-managers/)).
- **LegendKeeper** advertises "reveal at just the right time" but its fog-of-war tool is disabled/unfinished ([LegendKeeper changelog](https://www.legendkeeper.com/changelog/); [EN World forum thread](https://www.enworld.org/threads/my-experience-with-paid-d-d-tools-after-3-years-as-a-dm-player.714161/)).
- **Foundry VTT** supports per-journal-entry permission levels (None / Limited / Observer / Owner), assignable per-user, with community modules like Permission Viewer for at-a-glance auditing ([Foundry VTT Journal Entries docs](https://foundryvtt.com/article/journal/); [Users and Permissions](https://foundryvtt.com/article/users/)).
- **Obsidian** + the TTRPG tutorials community relies on Dataview queries and frontmatter tags; no native visibility model ([obsidianttrpgtutorials.com](https://obsidianttrpgtutorials.com/)).

**Gap:** none of these tools derives visibility from content — the GM hand-marks every secret. BookRAG's thesis (cursor-conditioned retrieval from an auto-extracted KG) has no commercial analogue in TTRPG space.

**Automated DMs / AI GMs:**
AI Dungeon uses a context-assembly approach — **AI Instructions + Plot Essentials + Author's Note + Story Cards** serialised into every prompt, plus an auto-summarisation **Memory System** and **Memory Bank** that compress history into retrievable AI-generated summaries ([AI Dungeon Memory System help](https://help.aidungeon.com/faq/the-memory-system); [AI Dungeon model differences](https://help.aidungeon.com/ai-model-differences)). Their newer Atlas model features a "cache-efficient processor" for larger effective context. Community-built AI DMs (DungeonLM, davidpm1021/ai-dungeon-master) use vector memory + Neo4j-backed agentic memory ([Neo4j agentic MUD blog](https://neo4j.com/blog/developer/agentic-memory-multi-user-dungeon/)). AI-DM note-takers (SessionKeeper, Archivist, Loreify, GM Assistant) transcribe sessions and build searchable campaign wikis with entity extraction ([SessionKeeper](https://www.sessionkeeper.ai/); [Archivist](https://www.myarchivist.ai/); [Loreify](https://loreify.ai/); [GM Assistant](https://gmassistant.app/)). **None of them implement per-player spoiler filtering** — they are DM-facing tools, and the DM sees everything.

**Narrative state representation formats:**
Inform 7: declarative rules + property/relation graph. Ink: typed variables + LIST bitfields + knot/stitch flow state. Twine: free-form JS variables. World Anvil: article sections + subscriber-group ACLs (not exposed as RDF publicly; export is BBCode/JSON). Foundry VTT: per-document permission maps stored in the Document's `ownership` field (user-id → 0/1/2/3 enum). None of these are standards; each is tool-specific.

**Connection to BookRAG:**
BookRAG is **passive fog-of-war** — the reader is an observer, and the narrative is fixed. TTRPG is **active fog-of-war** — each PC is a participant whose knowledge state depends on in-fiction experience. The shared primitive is **cursor-conditioned retrieval over a projection function `visible(entity, observer_state) -> description`**. BookRAG's `effective_latest_chapter` bound is a scalar cursor over one dimension (reader position); a TTRPG version would need a **per-observer multi-dimensional cursor** (which sessions PC-A attended, which secrets PC-A was told privately, which checks PC-A passed). Iteration 34's per-identity snapshot selection extends naturally: replace "snapshot ≤ reader_chapter" with "snapshot ∈ observer_knowledge_set". The architecture generalises.

**Potential product extension:**
**BookRAG-for-TTRPG**: ingest a published adventure module (*Curse of Strahd*, *Waterdeep: Dragon Heist*, *Rise of the Runelords*), extract a KG, and expose a DM-facing chatbot that answers "what does the party know about Strahd as of session 6?" — filtered by a manually-maintained "party knowledge" cursor (session log + explicit reveals). Licensing is the same hazard as AO3 (iteration 33): WotC's OGL/fan-content policies and Paizo's Community Use Policy gate public distribution, but **private DM-uploaded PDFs** are a safer product posture — same pattern as BookRAG's user-supplied EPUBs. The fact that AI note-takers (SessionKeeper, Archivist) are already commercial businesses validates market demand; none of them currently do "what do the players know vs. what does the DM know" as a first-class split, which is the differentiator.

**Key citations:**
- [Inform 7 — Ganelson website](https://ganelson.github.io/inform-website/)
- [Ink docs — WritingWithInk.md](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md)
- [Li & Riedl, Scheherazade, AAAI 2015 (PDF)](https://faculty.cc.gatech.edu/~riedl/pubs/aaai15.pdf)
- [World Anvil Visibility Toggle announcement](https://blog.worldanvil.com/worldanvil/dev-news/introducing-the-visibility-toggle-show-to-your-players-only-what-you-want-them-to-see/)
- [Foundry VTT Users and Permissions](https://foundryvtt.com/article/users/)
- [AI Dungeon Memory System](https://help.aidungeon.com/faq/the-memory-system)
- [Disco Elysium and Narrative Superposition, Post45 2024](https://post45.org/2024/04/disco-elysium-and-narrative-superposition/)
- [Neo4j: Agentic Memory MUD](https://neo4j.com/blog/developer/agentic-memory-multi-user-dungeon/)

**Concrete ideas worth stealing:**
- **Ink's LIST bitfield** as a data-structure idiom for "which chapters/events has entity-X been seen in" — replace BookRAG's per-snapshot chapter int with a compact bitset of appearances, enabling queries like "first mentioned in ch3, re-characterised in ch7."
- **World Anvil's Secret-as-embedded-atom** — extract spoiler-sensitive relationship facts as separate embeddable atoms keyed by `reveal_chapter`, and let the description template pull only atoms ≤ cursor. Maps cleanly onto the per-identity snapshot mechanism already in `load_allowed_nodes`.
- **Foundry's 4-level ownership enum** (None/Limited/Observer/Owner) as a model for progressive disclosure: BookRAG could expose **Limited** (entity exists, name known, no details) vs **Full** (current description) as distinct retrieval modes, letting the chatbot truthfully say "the book has mentioned a character called Marley, but you haven't learned anything about him yet" — useful for post-chapter-1 readers.
- **AI Dungeon's "state-in-context is source of truth"** principle — serialise the reader's cursor and allowed-entity list into the prompt explicitly, so the LLM cannot hallucinate knowledge the reader lacks. BookRAG already does this with `load_allowed_nodes`; doubling down with explicit "the reader has not yet read about X, Y, Z" negative constraints could further reduce leakage.
- **Scheherazade's plot graph as validation target** — the extracted KG should, in principle, reconstruct a partial-order plot graph; this could become a quality metric (graph-edit distance vs a human-authored plot outline for *A Christmas Carol*).

**Dead-ends:**
- No academic TTRPG-KG work surfaced — the field is entirely commercial/hobbyist.
- LegendKeeper's fog-of-war is abandonware.
- No public RDF/OWL export format from any major worldbuilding tool; interoperability is nil.

---

### 38. Comics / manga / webtoons — serialized visual narrative

**Researched:** 2026-04-22 (iteration 38 — bonus round 2)

**TL;DR:** Comics, manga, and webtoons have identical spoiler/progression problems to prose — One Piece's 1100+ chapters and 523M+ copies sold prove the market — but the technical stack is fundamentally different: OCR + panel segmentation + speaker attribution must precede any text-graph work. Research infrastructure (Manga109, MangaLMM, Manga109Dialog) now exists and is surprisingly mature, but no one has bolted a reader-cursor-aware KG on top. A visual BookRAG is plausible but probably 10× the engineering of the prose version.

**Market scale:**
- **One Piece:** ~523 million physical+digital units sold globally (as of 2026-03-31), 114 collected volumes, 1100+ chapters; 2025 Japan sales of 4.21M copies made it the #1 best-selling manga that year for the first time since 2018 ([accio.com/One Piece sales](https://www.accio.com/business/one-piece-manga-sales-2025-total-copies-sold-trend), [Guinness World Records](https://www.guinnessworldrecords.com/news/2023/10/one-piece-the-record-of-the-mega-popular-manga-series-explained-760171)).
- **WEBTOON Entertainment:** ~170M monthly active users across 150+ countries, $352.8M revenue in 2024 (+5.6% YoY), $166.1M ad revenue (+14.2%), though net loss widened to $102.6M ([WEBTOON IR Q4 2024](https://ir.webtoon.com/news-releases/news-release-details/webtoon-entertainment-inc-reports-fourth-quarter-and-full-year), [Korea Herald](https://www.koreaherald.com/article/10429396)).
- **Marvel/DC:** continuity spans ~90 years (Action Comics #1, 1938), with Marvel's Earth-616 main continuity + hundreds of alternate universes (Ultimate, What-If, Elseworlds) creating a combinatorial explosion no prose series approaches.

**Existing spoiler-management in fandom:**
Fandom wikis use template-based spoiler banners (e.g., One Piece Wiki's `Forum:Spoilers` policy treats raw-scan content as spoilers for ~1 week post-release ([One Piece Wiki Forum:Spoilers](https://onepiece.fandom.com/wiki/Forum:Spoilers))). Reddit communities like r/OnePiece use post flair ("Current Chapter," "Powerscaling," "Anime Help") and CSS spoiler blur; Discord servers split channels by chapter-N-or-lower. All manual, all honor-system, all known to leak.

**Comics / manga NLP pipelines:**
- **Manga109** (Aizawa et al., IEEE MultiMedia 2020): 109 Japanese manga volumes, 21,142 pages, 500k+ annotations (frames, balloons, text, character faces, character bodies). CVPR 2025 extended it with instance-level segmentation masks ([arXiv:2005.04425](https://arxiv.org/abs/2005.04425), [CVPR 2025 paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Xie_Advancing_Manga_Analysis_Comprehensive_Segmentation_Annotations_for_the_Manga109_Dataset_CVPR_2025_paper.pdf)).
- **Manga109Dialog** (2023, arXiv:2306.17469): 132,692 speaker-to-text pairs — the largest speaker-attribution dataset for comics. This is the manga equivalent of BookNLP's quote-attribution layer.
- **Hinami et al., "Towards Fully Automated Manga Translation"** (AAAI 2021, arXiv:2012.14271): first multimodal context-aware translation pipeline — uses *visual* context from neighbouring panels to disambiguate speech-bubble referents. Directly relevant: they already solve "which speaker does this balloon belong to" at scale ([AAAI paper](https://ojs.aaai.org/index.php/AAAI/article/view/17537)).
- **Manga OCR** (kha-white, HuggingFace): Donut-style transformer fine-tuned on vertical Japanese text in speech bubbles — the de facto open-source OCR for manga ([manga-ocr PyPI](https://pypi.org/project/manga-ocr/)).

**Character / entity extraction from comics:**
Manga109 supports character face and body detection + character re-identification (clustering faces across pages to identify a recurring character without a name prior). ICDAR 2024's Comics Datasets Framework benchmarks detection across Manga109 + DCM + eBDtheque ([ACM DOI](https://dl.acm.org/doi/10.1007/978-3-031-70645-5_11)). No public work constructs a **typed KG** (Character / Location / Faction / Event) from manga — the closest is Manga109's metadata annotations, which are flat tags not relational.

**Visual-language models for comics (2024–2026):**
- **MangaLMM** (arXiv:2505.20298, May 2025): a Qwen2.5-VL-based specialized model achieving >70% OCR score and outperforming GPT-4o on VQA for manga.
- **MangaUB** (arXiv:2407.19034, 2024): benchmark showing off-the-shelf LMMs (GPT-4V, Claude 3.5 Sonnet vision) handle single-panel understanding reasonably but fail on **sequential multi-panel reasoning** — exactly what a plot-event KG would require.
- "One missing piece in Vision and Language: A Survey on Comics Understanding" (arXiv:2409.09502) explicitly identifies sequential panel reasoning and long-range narrative tracking as the open frontier.

**Transcript-based approaches:**
ComicTranslate (GitHub ogkalu2/comic-translate) and Koharu (GitHub mayocream/koharu) are desktop apps that stack OCR + translation LLM — after OCR, the extracted dialogue could in principle be fed into a BookNLP-like pipeline, but panel order and speaker attribution remain out-of-band annotations you'd need to preserve.

**Comics continuity databases:**
- **Comic Vine** (`comicvine.gamespot.com/api`) is the largest community-maintained comics semantic database — millions of fan edits covering Marvel + DC + indie continuity, canon and non-canon. RESTful API with characters, issues, story-arcs, volumes. Saint-Louis (2023) analyzes it as a "semantic platform" though the API itself is not a true RDF/OWL graph ([Sage journal](https://journals.sagepub.com/doi/full/10.1177/20563051231195544)).
- Marvel + DC also publish their own APIs (Marvel Developer Portal, DC has partner feeds) but with narrower coverage and no continuity-graph semantics.

**Manga-specific challenges:**
- **Right-to-left reading order** — panel order is not raster; requires a dedicated layout model (Manga109 provides panel-order annotations).
- **Sound effects (onomatopoeia)** rendered as stylized art, not selectable text; OCR fails on them.
- **Art-style shifts for flashbacks / dream sequences** — visual cues (chibi, sepia, watercolor) signal non-present time, which a KG would need to encode as `temporal_context: flashback`.
- **Character identity is visual first, named second** — a character may appear for dozens of panels before being named; face-clustering (re-ID) must predate name-linking.

**Comics-specific challenges:**
- **Retcons:** facts about a character's origin can be overwritten by later issues (Wolverine's backstory rewritten multiple times) — the KG needs issue-number-stamped versioning, not just per-identity snapshots.
- **Alternate universes / Elseworlds:** Earth-616 Spider-Man, Earth-1610 Spider-Man, Spider-Man Noir are the same *character archetype* but distinct entities; requires a universe dimension on every node.
- **Crossover events:** Secret Wars, Crisis on Infinite Earths rewrite thousands of nodes simultaneously — versioning explosion.

**Progressive-disclosure in fan communities:**
r/OnePiece's flair system is the industry-standard informal solution, and the One Piece Wiki explicitly rate-limits raw-scan spoilers for ~1 week. Fandom wikis have `{{spoiler}}` templates and "This article contains spoilers for [arc name]" banners. All are pre-LLM and all are manual.

**Tooling that partially exists:**
- Manga OCR → text extraction (solved)
- Manga109Dialog → speaker attribution (solved for annotated set)
- Comic Vine API → canon/continuity ground truth (solved for English-language comics)
- MangaLMM → panel-level VQA (solved-ish)
- None of these integrate into a reader-cursor-aware KG + spoiler filter.

**License / IP considerations:**
Every major manga publisher (Shueisha, Kodansha, Shogakukan) aggressively pursues DMCA against unofficial scans — the same IP hostility applies to derivative datasets built on raw scans. Manga109 is licensed for academic use only, non-redistributable. This makes **self-serve upload by a legally-purchased-digital-copy owner** (via DRM-stripped CBZ/CBR, similar to how BookRAG accepts user-uploaded EPUB) the only clean distribution path. See iteration 33 on AO3-style ToS issues.

**Visual BookRAG — product thesis:**
The pipeline would be: CBZ/CBR upload → per-page panel segmentation (Manga109-style detector) → OCR (manga-ocr for JP, Tesseract+LLM post-edit for EN) → speaker attribution (Manga109Dialog-trained model) → character face-clustering → batch of ~3 chapters feeds into Cognee extraction with `source_page`, `source_panel` stamps → reader cursor is `(chapter, page, panel)` triple. Spoiler filter works identically to BookRAG's.

The **technical moat** is that each stage compounds error: 95% OCR × 85% panel-order × 80% speaker-attribution × 90% face-clustering ≈ 58% end-to-end correctness before extraction even starts. By contrast, BookRAG's prose pipeline starts from ~99% clean text.

**Is it worth BookRAG pivoting / extending?**
Honest assessment: **no, not as a pivot — yes, as a far-future extension.** Market is enormous (170M+ WEBTOON MAU is comparable to Spotify's premium subscriber base). But each of OCR, panel-order, and speaker-attribution is a research problem where SOTA is still in the 80s percent-wise. The prose BookRAG is a better first product; a visual variant is a second, harder, well-funded startup. The right MVP is English-language webtoons (which have embedded text metadata in some cases, bypassing OCR) rather than Japanese manga scans.

**Key citations:**
- [Manga109 (arXiv:2005.04425)](https://arxiv.org/abs/2005.04425)
- [Manga109Dialog (arXiv:2306.17469)](https://arxiv.org/abs/2306.17469)
- [Hinami et al., AAAI 2021 (arXiv:2012.14271)](https://arxiv.org/abs/2012.14271)
- [MangaLMM (arXiv:2505.20298)](https://arxiv.org/html/2505.20298v1)
- [Comics survey (arXiv:2409.09502)](https://arxiv.org/html/2409.09502v2)
- [One Piece sales — Guinness](https://www.guinnessworldrecords.com/news/2023/10/one-piece-the-record-of-the-mega-popular-manga-series-explained-760171)
- [WEBTOON Q4 2024 IR](https://ir.webtoon.com/news-releases/news-release-details/webtoon-entertainment-inc-reports-fourth-quarter-and-full-year)
- [Comic Vine API docs](https://comicvine.gamespot.com/api/documentation)
- [One Piece Wiki Forum:Spoilers](https://onepiece.fandom.com/wiki/Forum:Spoilers)

**Concrete ideas worth stealing:**
- **Issue-number + panel-number source stamps** (comics analogue of BookRAG's `source_chunk_id`) — even text-BookRAG could benefit from finer-grained `(chapter, paragraph)` stamps stored on every DataPoint, enabling sub-chapter cursor queries without re-ingestion.
- **Universe dimension on nodes** — comics need `universe: "Earth-616"` as a first-class discriminator. Prose equivalent: **timeline/POV dimension** for stories with alternating POVs (A Song of Ice and Fire, The Expanse), so a reader on Catelyn's ch12 doesn't see Jon's ch12 facts.
- **Retcon-aware versioning** — comics' retcon problem is a generalized case of BookRAG's per-identity snapshots; lift the Phase 2 snapshot mechanism into an explicit *retcon supersedes* edge so readers re-reading a series see the *current* canonical version rather than the version-as-of-their-first-read.
- **Face-clustering before naming** as a model for **anaphora-before-coref**: in prose, a character can be introduced as "the old man" for 40 pages before being named "Dumbledore." BookNLP's coref eventually links them, but a face-cluster-analogue could be a cluster-of-descriptions pipeline where "the old man" is a provisional entity that later merges with "Dumbledore" once named — useful for mystery novels where identity is deliberately withheld.
- **MangaUB's sequential-reasoning failure mode** is the same failure mode LLMs show on long novels: single-panel/paragraph comprehension is solved, multi-panel/multi-chapter causal chains are not. BookRAG's KG approach is the correct bet; doubling down on **explicit causal edges between PlotEvents** (not just temporal ordering) would differentiate further.

**Dead-ends:**
- No public Marvel/DC KG with continuity semantics exists; Comic Vine is semantic but flat.
- GPT-4V / Claude Vision on raw manga pages still under-performs specialized stacks for sequential reasoning per MangaUB.
- Manga109 is research-only licensed — cannot be used to train a commercial model.

### 39. Multilingual fiction

**Researched:** 2026-04-22 (iteration 39 — bonus round 2)

**TL;DR:** Chinese web novels are a $7.8B global market with 600M+ users and a massive MTL-reader subculture that BookRAG currently cannot serve at all — BookNLP is English-only, BERTopic defaults to English, and the parenthetical-coref insertion format assumes whitespace tokenization. A credible multilingual upgrade path exists: BGE-M3 for embeddings, LTP/HanLP + a CN-novel NER corpus for Chinese entities, Maverick-coref (OntoNotes-CN trained) for coreference, and GPT-4o as a fallback coref oracle. The hardest domain-specific problem is not language but **translation drift in fan-translated serials** — names, pronouns, and cultivation terms change across chapters, so a KG built on translated text inherits the translator's mistakes.

**Market:**
The global web-novel-platforms market is ~$7.8B in 2025 with 600M+ registered users across leading platforms, projected at 12.4% CAGR to $22.4B by 2034; Asia-Pacific is 54.3% of revenue ([WiseGuy Web Novel Market](https://www.wiseguyreports.com/reports/web-novel-market), [Dataintelo](https://dataintelo.com/report/web-novel-platforms-market)). Qidian hit 200M MAU in 2022 contributing 25B RMB to the industry, with ~20M Chinese web-novel writers ([The China Project](https://thechinaproject.com/2022/08/17/chinas-sprawling-world-of-web-fiction/)). WebNovel.com (the international arm) has 50M registered, ~10M MAU in 2023 ([Gitnux stats](https://gitnux.org/web-novel-industry-statistics/)). MTL readership — fans who read raw Chinese through Google Translate / LNMTL glossaries — is a distinct subculture with its own forums and community-maintained term lists ([LNMTL](https://lnmtl.com/), [Wuxiaworld forum "How to read MTL"](https://forum.wuxiaworld.com/discussion/8397/how-to-read-mtl)).

**Multilingual literary corpora:**
- **Qidian-Webnovel Corpus** (2025, Journal of Open Humanities Data) — Chinese web novels paired with multilingual reader responses, explicitly built for NLP ([johd.368](https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.368)).
- **Chinese Novel NER Corpus** (arXiv:2311.15509) — 263,135 entities in 105,851 sentences from 260 online Chinese novels across 13 genres including xianxia ([paper](https://arxiv.org/abs/2311.15509)).
- **Syosetu711K** — 711,700 Japanese light novels scraped from Shōsetsuka ni Narō ([HF dataset](https://huggingface.co/datasets/RyokoAI/Syosetu711K)).
- **SyosetuNames-3.5M** — 3.5M unique character names extracted for NER training ([HF](https://huggingface.co/datasets/Sunbread/SyosetuNames-3.5M)).
- NER corpora exist for **Ming-Qing classical Chinese novels** (Journey to the West, Three Kingdoms) via Springer LNCS work. No equivalent to LitBank in Chinese as of April 2026.

**Multilingual embedding models:**
**BGE-M3 (BAAI, ACL Findings 2024)** — dense + sparse + multi-vector retrieval in 100+ languages, up to 8,192 tokens, SOTA on multilingual/cross-lingual/long-document benchmarks ([arXiv:2402.03216](https://arxiv.org/abs/2402.03216)). Self-knowledge distillation fuses the three retrieval modes. This is the obvious drop-in replacement for BookRAG's current English-tilted embedder. Competitors: multilingual-E5, Cohere embed-multilingual-v3, GTE-multilingual. BGE-M3 wins on Chinese retrieval in public benchmarks and has the longest context window of the four.

**Multilingual coreference:**
CoNLL-2012 OntoNotes covers English, Chinese, and Arabic ([W12-4501](https://aclanthology.org/W12-4501.pdf)). **Maverick** (ACL 2024) achieves SOTA on CoNLL-2012 with only 192M params and 170x faster inference than autoregressive coref models ([SapienzaNLP/maverick-coref](https://github.com/SapienzaNLP/maverick-coref)). It has been adopted as the textual coref module in a 2025 Chinese multimodal dialogue benchmark ([arXiv:2504.14321](https://arxiv.org/html/2504.14321)), suggesting real-world CN fluency. Challenges unique to CJK: no whitespace (Chinese/Japanese), pro-drop (subjects routinely omitted in Japanese), honorifics/titles that shift with social context ("Senpai," "Shixiong"), and a richer pronoun system with in-group/out-group distinctions.

**Translation artifacts in MTL web serials:**
Community-maintained glossaries on LNMTL exist precisely because raw MTL suffers from (1) inconsistent character names across chapters (transliteration drift — "Wang Teng" vs "Wang Tang"), (2) wrong-gender pronouns (Chinese 他/她 are homophonous in pinyin, and pro-drop makes this worse), (3) mistranslated cultivation terms (境界 jìngjiè rendered inconsistently as "realm," "boundary," "state") ([Dragneel Club MTL guide](https://dragneelclub.com/top-5-machine-translation-sites-for-novels/)). An MTL reader's fog-of-war is compounded by translator drift: a character who was "Lin Feng" in ch1 may be "Forest Wind" in ch40.

**Character name challenges in Chinese:**
Surname-first order (Wang Wei), one-char surname + one-or-two-char given name; **courtesy names (zi 字)** bestowed at adulthood and used for formal address among peers, **art names / pen names (hao 号)** self-selected ([Wikipedia Chinese name](https://en.wikipedia.org/wiki/Chinese_name), [Wikipedia Courtesy name](https://en.wikipedia.org/wiki/Courtesy_name)). In xianxia specifically: sect titles (Senior Brother / Shixiong 师兄), Dao-names taken upon breakthrough, demon/beast names that change form, clan prefixes. A single character in a xianxia novel routinely has 6–10 surface forms referring to the same identity — much worse than an English novel's "Scrooge / Mr. Scrooge / Ebenezer / the old miser." No off-the-shelf tool handles this for Western readers; community glossaries at [Immortal Mountain](https://immortalmountain.wordpress.com/glossary/wuxia-xianxia-xuanhuan-terms/) are the de facto solution.

**Named entity / coref in Chinese fiction:**
Toolchain: **LTP** (Harbin Institute of Technology), **HanLP**, **LAC** (Baidu), **Stanford CoreNLP Chinese**, **jieba** for segmentation. The arXiv:2311.15509 corpus paper reports that genre matters less than domain (literary vs. news) — models trained on news CoNLL-2003 collapse on novels. Recent LLM-based approaches (GPT-4o, Qwen) do zero-shot CN NER competitively but are expensive at book scale.

**Translation-aware KG construction:**
Three design options: **(a)** build KG on source-language text, translate fields lazily at query time — preserves precision, requires CN-capable extractor; **(b)** build KG on translated text — loses precision, inherits translator errors, but reuses existing English stack; **(c)** **hybrid** — source-text KG with per-language `surface_forms: {zh: [...], en: [...]}` map on each entity, display in reader's language. (c) is the right answer for BookRAG.

**How BookRAG handles non-English books today:**
Honest assessment: broken. BookNLP is English-only (trained on English LitBank/GutenTag); BERTopic with default `sentence-transformers/all-MiniLM-L6-v2` is English-tilted; parenthetical-coref insertion `"he [Scrooge]"` assumes whitespace tokens, so dropping it into untokenized Chinese produces garbage. A Chinese EPUB would parse but fail at `run_booknlp`. Today BookRAG is effectively English-only.

**Upgrade path for multilingual BookRAG:**
1. **Detect language at `parse_epub`** (langdetect or fasttext-lid), route to a language-specific pipeline.
2. **Replace BookNLP** with LTP/HanLP for Chinese (jieba segment → LTP NER → LTP coref), **GiNZA/spaCy-ja** for Japanese, **KoNLPy/spaCy-ko** for Korean.
3. **Swap embeddings to BGE-M3** project-wide — works for English too, so there's no downside beyond 8× model size.
4. **Replace BERTopic English defaults** with BGE-M3 embeddings + HDBSCAN (language-agnostic).
5. **Add a `surface_forms` dict to every DataPoint** (`Character`, `Location`, etc.) keyed by language, populated during extraction. Display layer translates.
6. **For xianxia/cultivation specifically**: a pluggable **domain glossary** (cultivation realms, sect titles, dan grades) injected into the extraction prompt — same pattern as LNMTL's community glossaries.
7. **GPT-4o / Claude as coref oracle fallback** — when LTP confidence is low, re-run coref via LLM on that passage only.

**Licensing considerations:**
Qidian / WebNovel.com have explicit ToS prohibiting scraping and redistribution; their translations are licensed exclusively to Wuxiaworld, WebNovel, and Volare. BookRAG's user-uploads-their-own-EPUB model sidesteps this — same personal-use posture as with commercial English EPUBs. Chinese classics (Three Kingdoms, Journey to the West, Dream of Red Chamber, Water Margin) are public-domain worldwide and safe for demo/validation. Fanfic-translation legal status is gray; fan translations of licensed works remain an infringement risk for the translator, not for a personal-use reader tool.

**Key citations:**
- [BGE-M3 / M3-Embedding (arXiv:2402.03216)](https://arxiv.org/abs/2402.03216)
- [Chinese Novel NER Corpus (arXiv:2311.15509)](https://arxiv.org/abs/2311.15509)
- [Qidian-Webnovel Corpus (JOHD 2025)](https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.368)
- [Maverick-coref (SapienzaNLP)](https://github.com/SapienzaNLP/maverick-coref)
- [CoNLL-2012 OntoNotes multilingual coref](https://aclanthology.org/W12-4501.pdf)
- [Syosetu711K](https://huggingface.co/datasets/RyokoAI/Syosetu711K) / [SyosetuNames-3.5M](https://huggingface.co/datasets/Sunbread/SyosetuNames-3.5M)
- [Web Novel Market Report](https://www.wiseguyreports.com/reports/web-novel-market), [China Project web fiction](https://thechinaproject.com/2022/08/17/chinas-sprawling-world-of-web-fiction/)
- [LNMTL](https://lnmtl.com/), [Wuxiaworld MTL forum](https://forum.wuxiaworld.com/discussion/8397/how-to-read-mtl)
- [Wikipedia: Chinese name](https://en.wikipedia.org/wiki/Chinese_name), [Courtesy name](https://en.wikipedia.org/wiki/Courtesy_name)

**Concrete ideas worth stealing:**
- **Per-language `surface_forms` on every DataPoint** — not just "aliases," but an explicit language-keyed dict. This also solves cross-lingual reader use cases: a bilingual reader who knows a character as "Lin Feng" in the raw Chinese but reads the English translation gets both forms linked to one identity. Implementable as a `Dict[str, List[str]]` field on `Character` / `Location` in `models/datapoints.py` with zero breaking changes to English-only books.
- **Community-glossary-as-extraction-prompt-context** — LNMTL readers maintain term lists (realm names, sect hierarchies) because MT alone fails. A BookRAG `ontology/glossary.yaml` per book, optionally community-sourced, injected as few-shot examples into the Phase 2 extraction prompt, would dramatically improve xianxia extraction quality.
- **Translator-drift detection** — for multi-chapter MTL serials, flag entities whose name changes across batches via string-distance alerts. Surface to the user: "Is 'Forest Wind' (ch40) the same character as 'Lin Feng' (ch1)?" Makes BookRAG *better than the translation*.
- **Detect-and-route at `parse_epub`** — cheap language detection followed by a strategy-pattern pipeline (`EnglishPipeline`, `ChinesePipeline`, `JapanesePipeline`) is a cleaner refactor than sprinkling `if lang == ...` through every module. The `asyncio.create_task` orchestrator already supports this cleanly.
- **BGE-M3 as the default embedder for *all* books** — English performance is competitive with English-specific models, and it unlocks multilingual with a one-line change. The 8192-token context window also helps long-paragraph fiction (Dickens, Tolstoy, Murakami).

**Dead-ends:**
- No public BookNLP-equivalent exists for Chinese, Japanese, or Korean as of April 2026 — you would assemble LTP/HanLP + a custom coref layer rather than drop-in-replace.
- No multilingual NarrativeQA / LitBank benchmark to measure end-to-end spoiler-safe QA performance across languages.
- Qidian / WebNovel ToS make *training data* acquisition legally fraught — any public dataset you build from their content risks takedown (the Qidian-Webnovel Corpus paper works around this with reader-response-only release and sample texts).

### 40. Unreliable narrators & author-intent

**Researched:** 2026-04-22 (iteration 40 — bonus round 2)

**TL;DR:** Naive KG extraction from fiction treats the narrator's assertions as ground truth, which silently corrupts the graph whenever the narrator lies, self-deceives, dreams, or is later contradicted. The narratology literature (Booth 1961, Phelan 2005) gives a clean taxonomy — misreporting / misreading / misevaluating on three axes (facts, values, knowledge) — and recent NLP work (TUNa, ACL 2025; the CAUTION project) has started operationalizing this. BookRAG can cheaply bolt on a `narrator_attribution` + `confirmed_by_chapter` layer without changing its extraction pipeline, and the spoiler cursor already correctly hides CLAIM→REVEAL transitions.

**Narratology background.** Wayne Booth coined "implied author" and "unreliable narrator" in *The Rhetoric of Fiction* (1961): a narrator is reliable "when he speaks for or acts in accordance with the norms of the work (which is to say, the implied author's norms), unreliable when he does not" ([Booth key theories](https://literariness.org/2017/02/24/key-theories-of-wayne-c-booth/); [Booth Wikipedia](https://en.wikipedia.org/wiki/Wayne_C._Booth)). The implied author is inferred from authorial choices, distinct from both the real author and the narrator. James Phelan (Ohio State) refined this into a 6-cell grid: three "mis-" types (misreporting, misreading, misevaluating) and three "under-" types (underreporting, underreading, underevaluating), sorted along **three axes — facts, values/ethics, and knowledge/perception** ([Unreliability — living handbook of narratology](https://www-archiv.fdm.uni-hamburg.de/lhn/node/66.html)). Crucially, a narrator can report facts accurately but misevaluate them (Stevens in *The Remains of the Day*), or misreport because they underread (Huck Finn).

**Unreliable-narrator detection — computational.** The most directly relevant paper is Mohseni et al., **"Classifying Unreliable Narrators with Large Language Models"** (ACL 2025, [arxiv:2506.10231](https://arxiv.org/abs/2506.10231)). They release **TUNa**, a human-annotated dataset spanning blog posts, Reddit, hotel reviews, and literature, with a four-level taxonomy: **intra-narrational, inter-narrational, intertextual, and extratextual** unreliability. They find intra-narrational (contradictions *within* a single narrator's account) is the easiest task for LLMs; intertextual (requiring outside-the-text knowledge) is hardest. Fine-tuning and curriculum learning beat zero-shot. The DFG-funded **CAUTION** project (Univ. Stuttgart, [dfg-spp-cls](https://dfg-spp-cls.github.io/projects_en/2020/01/24/TP-Caution/)) is explicitly building data-driven heuristics for textual signals of unreliability (sentiment-vs-fact divergence, deictic collapse, excessive self-justification).

**Ground-truth vs narrator-claim in KGs.** The obvious encoding — which nothing in BookRAG does today — is **dual edge types**: `CLAIMED(source=narrator_X, proposition=P, chapter=N)` vs `HOLDS(P, confirmed_chapter=M)`. EvoKG ([arxiv:2509.15464](https://arxiv.org/html/2509.15464v1)) already handles factual contradictions and temporal progression in evolving KGs; Oxford Semantic describes the non-monotonic machinery needed ("new data can invalidate previously inferred results. Facts need to be retracted" — [Oxford Semantic blog](https://www.oxfordsemantic.tech/blog/how-to-use-negation-in-semantic-reasoning-for-a-knowledge-graph-and-how-incremental-retraction-works)). For BookRAG, full non-monotonic reasoning is overkill; a flat `attributed_to` + `status ∈ {claim, confirmed, retracted}` triple is enough.

**Free indirect discourse & perspective.** FID ("Was it true? Had he really seen her?") blends narrator voice with character thought and is notoriously hard even for humans to segment. BookNLP's quote-attribution (4-step pipeline per [Improving Quotation Attribution](https://arxiv.org/html/2406.11368)) only handles direct speech — FID falls into narration by default. This matters because a confident-sounding sentence may actually encode a character's mistaken belief, not narrator assertion. Heuristic: whenever a BookNLP-tagged character's thoughts immediately precede narration, treat the adjacent narration as possibly FID and tag provenance `character_perspective=X` rather than `narrator`.

**Retcons in serialized fiction.** Web serials (Worm, Wandering Inn, royalroad.com) edit prior chapters in place. BookRAG's current one-shot ingestion assumes text is immutable. Iteration 21's incremental re-ingestion work is the natural hook: a retcon diff should invalidate only the batches touching changed paragraphs and version the affected nodes (`node_version` + `superseded_by`).

**Dreams, flashbacks, stories-within-stories.** LitBank realis (iter 12) handles event modality, but **characters mentioned only inside a dream or inset story** still spawn spurious KG nodes under the current pipeline. Christmas Carol's Ghost of Christmas Yet To Come shows future events — these get extracted as PlotEvents with chapter=4 but describe events that (within the story world) haven't happened. Fix: pass BookNLP realis tags into extraction and tag spawned nodes `realis=irrealis` so the spoiler filter and UI can distinguish.

**Author intent vs text.** Post-structuralist "death of the author" (Barthes) says intent doesn't matter; practical KG construction cares anyway because authoritative paratexts (Tolkien's *Silmarillion*, Rowling's Pottermore, GRRM's *World of Ice and Fire*) contradict or extend the novels. BookRAG could model these as a **secondary dataset with lower precedence**, merged at query time — or kept separate so spoiler filtering works per-source.

**Spoiler-filter interactions.** Nicely, the existing cursor filter already handles the CLAIM/REVEAL case correctly: if Amy's falsified-diary claim is in chapter 5 and the reveal is chapter 20, a reader at chapter 10 sees only the claim. No extra machinery needed — *provided* the KG tags the reveal as a separate node/event with `first_chapter=20`, not as a silent overwrite of the chapter-5 claim. This argues against LLM-driven node merging that collapses "Amy (diary version)" into "Amy (revealed)".

**How BookRAG can be better.**
- Add `narrator_attribution: str | None` on PlotEvent (values: "narrator", "character:Scrooge", "implied_author"). When absent, default "narrator".
- Add `confirmed_by_chapter: int | None` — populated only when a later batch explicitly contradicts/confirms an earlier claim. LLM prompt addition: "If this passage contradicts an earlier claim, emit a `Retraction` DataPoint with `target_node_id` and `retracted_in_chapter`."
- Flag 1st-person-protagonist novels at ingestion (BookNLP POV detection — see [Bamman LitBank](https://people.ischool.berkeley.edu/~dbamman/pubs/pdf/Bamman_DH_Debates_CompHum.pdf)) and apply stricter attribution on all extracted claims.
- Store per-describer sentiment: if Scrooge describes Cratchit, tag the description with `perspective=Scrooge` and `sentiment=negative`; at query time, the LLM can weight or discount biased descriptions.
- Don't merge "character-at-time-T" snapshots across reveals — Phase 2's per-identity snapshot selection (current code) already gets this half-right.

**Specific novels to test against.**
- *A Christmas Carol* — Ghosts' future visions (irrealis); Scrooge's transformation (conflicting character descriptions across chapters).
- *Gone Girl* — Amy's diary (chapters 1-half: CLAIMED by Amy; second half: retracted en masse).
- *Fight Club* — narrator identity reveal invalidates every prior `ASSERTS(narrator ≠ Tyler)` claim.
- *Red Rising* — Darrow's Carving (post-Carving claims are under false identity; the KG should tag early-book Darrow and Gold-infiltrator Darrow as the same character but with different `known_as` per chapter range).
- *The Remains of the Day* — textbook misevaluation; facts are reported accurately, values are not.
- *We Were Liars* — intra-narrational misreporting; amnesiac narrator.

**Key citations.**
- Booth 1961, *Rhetoric of Fiction* ([UChicago Press](https://press.uchicago.edu/ucp/books/book/chicago/R/bo5965941.html))
- Phelan 2005 / Nünning via [living handbook of narratology — Unreliability](https://www-archiv.fdm.uni-hamburg.de/lhn/node/66.html)
- Mohseni et al., "Classifying Unreliable Narrators with LLMs", ACL 2025 ([arxiv:2506.10231](https://arxiv.org/abs/2506.10231); [ACL](https://aclanthology.org/2025.acl-long.1013/))
- CAUTION project (DFG SPP-CLS, [project page](https://dfg-spp-cls.github.io/projects_en/2020/01/24/TP-Caution/))
- Bamman, "LitBank: Born-Literary NLP" ([PDF](https://people.ischool.berkeley.edu/~dbamman/pubs/pdf/Bamman_DH_Debates_CompHum.pdf))
- Michel et al., "Improving Quotation Attribution with Fictional Character Embeddings" ([arxiv:2406.11368](https://arxiv.org/html/2406.11368))
- EvoKG, "Temporal Reasoning over Evolving Knowledge Graphs" ([arxiv:2509.15464](https://arxiv.org/html/2509.15464v1))

**Concrete ideas worth stealing.**
- Phelan's 3-axis taxonomy as extraction prompt scaffolding: for each extracted claim, ask the LLM to tag axis ∈ {fact, value, knowledge} and confidence.
- TUNa's intra/inter-narrational split maps cleanly to batch-local vs cross-batch contradiction detection — a lightweight cross-batch validator pass could catch retcons cheaply.
- EvoKG-style retraction edges instead of node overwrites; preserves the spoiler-safe CLAIM-at-chapter-N view.
- BookNLP POV detection gate: 1st-person-homodiegetic narrators default `narrator_attribution="character:<name>"` on every extracted claim unless overridden.
- Irrealis propagation: any node first introduced inside a BookNLP-tagged irrealis span inherits `realis=irrealis` until a later realis occurrence confirms it.

### 41. Reader UX patterns for long-form & chatbot companions

**Researched:** 2026-04-22 (iteration 41 — bonus round 2)

**TL;DR:** Long-form readers chronically forget cast and prior events, and every mature reading product (Kindle X-Ray, Fable, fandom wikis) converges on three affordances: on-page character lookups, chapter-scoped discussion rooms, and click-to-reveal spoiler gates. BookRAG's chat already maps onto these precedents; the remaining UX gaps are (a) a persistent "safe-through-chapter-N" indicator, (b) an inline one-tap "who is X?" query tied to the reader's cursor, and (c) source-passage highlighting in the reading view.

**Long-form reading UX research:** Kindle X-Ray (introduced 2012) is the canonical precedent — press-and-hold on a name returns a character card with aliases collapsed to one identity ("Adrian / Adrian Drake / Drake / Dice all resolve to one entry"), plus "Notable Clips" curated by publishers, and tabs for People / Terms / Images ([SlashGear](https://www.slashgear.com/1475659/kindle-x-ray-feature-explained/), [KDP X-Ray for Authors](https://kdp.amazon.com/en_US/help/topic/G202187230)). The design principle Amazon emphasizes: "keeps readers on the page, reducing the time spent looking up definitions" ([selfpublishing.com](https://selfpublishing.com/kindle-x-ray/)). Apple Books and Kobo expose reading stats (time-to-finish, pages-per-session) but no entity-lookup comparable to X-Ray. Kobo's distinctive feature is font customization including OpenDyslexic ([Kobo help](https://help.kobo.com/hc/en-us/articles/360020048733)).

**Chatbot-in-reading-app precedents:** Dedicated AI companions include BookAI.chat, BookChat.studio, Myreader.ai, and Emdash (Deepgram) — all let users "chat with" an uploaded book, but none are progress-gated by default ([BookChat](https://www.bookchat.studio/), [Myreader](https://www.myreader.ai/), [Emdash](https://deepgram.com/ai-apps/emdash)). Fable is the closest social analog: "spoiler-free chapter rooms and episode rooms" where club members only see annotations/discussion from peers who have read up to the same chapter ([Fable club features](https://fable.co/club-features), [Book Riot review](https://bookriot.com/fable-book-club-app-review/)). Fable's in-book annotation ("Let's discuss" tab pops up at chapter boundaries) is the single most portable idea for BookRAG's chat: pin chat to the same chapter scope the reader is currently in.

**Spoiler-sensitive UI affordances:** The Fandom Developers Wiki SpoilerTags extension hides text behind a "Click to reveal" tooltip (not hover, to avoid mobile misfires), inspired by Reddit and Discord spoiler tags ([Fandom SpoilerTags](https://dev.fandom.com/wiki/SpoilerTags)). Fandom's SpoilerAlert variant is heavier: "covers [the area] with a dialog that asks the visitor if they want to risk seeing spoilers" ([Fandom SpoilerAlert](https://dev.fandom.com/wiki/SpoilerAlert)). Key UX rule from these communities: click-to-reveal, never hover; and always offer a dialog-level "yes, I accept the risk" for large sections. MyAnimeList uses `[spoiler]...[/spoiler]` BBCode that renders as a gray bar — identical pattern. For BookRAG: the answer-level equivalent is "this answer references chapter 12 events — reveal?" rather than silently refusing.

**Reader pain points — published research:** A Springer 2024 study (Events Remembering Support Via Character Relationships' Visualization) explicitly frames the problem: "readers usually find it difficult to finish [a long novel] at once, which causes them to repeat the read-and-pause step, leading to confusion... readers tend to forget the events of novels by the time they resume reading, which would make them give up" ([Springer](https://link.springer.com/chapter/10.1007/978-3-031-60114-9_3)). Their intervention — visualizing character relationships per episode as positive/negative/neutral — improved event recall in user studies. De Gruyter's "Plotting Memory" (2022) makes the complementary literary-theory point: skilled novelists "guide the reader's memory" through explicit recapping, but modern serialized fiction shifts that burden onto the reader or external tools ([De Gruyter](https://www.degruyterbrill.com/document/doi/10.1515/jlt-2022-2024/html)). On spoiler avoidance, a 2024 IJoC paper ("Spoilers as Self-Protection") and a 2021 ResearchGate study find that narrative engagement, appreciation, suspense, and FoMO all independently predict spoiler-avoidance behavior — meaning the readers who would most benefit from a KG companion are also the most sensitive to leakage ([IJoC](https://ijoc.org/index.php/ijoc/article/download/19466/4538), [ResearchGate](https://www.researchgate.net/publication/354888014)).

**Chat UI patterns for literary companions:** The 2025 ACM IMX paper "Spoiler Alert! Understanding and Designing for Spoilers in Social Media" recommends layered reveal: summary hidden → tap → preview sentence → tap again → full answer ([ACM DL](https://dl.acm.org/doi/10.1145/3706370.3727861)). Kindle X-Ray's card structure (summary → notable clips → full passages) is a static version of that layering. The pattern for BookRAG: answer → cited passage with chapter stamp → "explore related characters" chips.

**Accessibility:** OpenDyslexic is the de facto dyslexia-friendly font across Kobo, Kindle Paperwhite (except v1/v2), OverDrive/Libby, and Snapplify ([OpenDyslexic.org](https://opendyslexic.org/), [Wikipedia](https://en.wikipedia.org/wiki/OpenDyslexic)). Scientific evidence for reading-speed benefit is mixed, but user preference is consistently positive (Broadbent 2023). For a chat UI: screen-reader support requires ARIA live regions on streaming responses and semantic roles on spoiler gates (`aria-expanded`, `aria-label="Reveal spoiler for chapter 12"`). Dynamic spoiler-gated content is especially tricky because NVDA/VoiceOver will announce revealed text mid-read — the Fandom SpoilerTags extension explicitly doesn't work on mobile for this reason.

**Privacy:** Reading progress is behavioral personal data under GDPR Art. 4(1) — Kindle persists it to Amazon's cloud tied to account, Apple Books stores it per-device with optional iCloud sync. Kobo anonymizes at the aggregate-stats level. For BookRAG's single-user local deployment this is moot, but any hosted variant would need to treat `reading_progress.json` as profiling data (consent, export, deletion).

**Mental model research:** Williamson & Lambert's narrative-cognition work (and the broader "situation model" tradition from Zwaan & Radvansky) argues readers build internal graphs of characters and relations, but recall them episodically, not structurally — readers don't think "edge (Scrooge)-[employs]->(Cratchit)," they think "the scene where Scrooge grudgingly grants Bob a day off." This argues against exposing the raw KG to readers. Better: use the KG to power natural-language answers and a character-glossary side panel, keep the graph view as an optional "developer mode."

**Failure modes of literary chatbots:** (1) hallucination past the cursor — the LLM confabulates events from training data even when the allowed-nodes list is empty (iter 27); (2) spoiler leakage via vague cues ("character X has a complicated future"); (3) over-summarization flattening surprise — answering "what is the theme" before the reader has felt the theme; (4) refusal theater — cold-refusing every future-tense question instead of gracefully deferring ("I can answer this after you finish chapter 8"). Book Riot's Fable review surfaces a related UX failure: "slick but somewhat confusing interface" — feature discoverability beats feature count.

**Product design principles for BookRAG's chat UI:** (a) always-visible "safe through chapter N" pill in the chat header; (b) user-overridden peek toggle with Fandom-style "accept the risk" dialog; (c) inline chapter citations on every answer fragment; (d) for "what happens next"-class questions, prefer "I'll answer this when you reach chapter N" over hard refusal; (e) optional graph-view tab (developers/power-users), not default.

**Concrete UX upgrades for BookRAG frontend:** (1) confidence/scope indicator on every answer ("based on chapters 1–5"); (2) source-passage highlight that jumps the reading view to the cited paragraph; (3) character-glossary side panel auto-generated from `load_allowed_nodes` per-identity snapshots (cheap — the data is already indexed); (4) "I forgot who X was" one-tap query bound to long-press on names in the reading view (Kindle X-Ray parity); (5) Fable-style chapter-scoped "discussion" chips that suggest questions appropriate for the current chapter; (6) OpenDyslexic as a font toggle.

**Key citations:** [Springer 2024 Events Remembering](https://link.springer.com/chapter/10.1007/978-3-031-60114-9_3); [De Gruyter Plotting Memory 2022](https://www.degruyterbrill.com/document/doi/10.1515/jlt-2022-2024/html); [IJoC Spoilers as Self-Protection 2024](https://ijoc.org/index.php/ijoc/article/download/19466/4538); [ACM IMX 2025 Designing for Spoilers](https://dl.acm.org/doi/10.1145/3706370.3727861); [Fandom SpoilerTags](https://dev.fandom.com/wiki/SpoilerTags); [Kindle X-Ray SlashGear](https://www.slashgear.com/1475659/kindle-x-ray-feature-explained/); [Fable club features](https://fable.co/club-features); [OpenDyslexic](https://opendyslexic.org/).

**Concrete ideas worth stealing:**
- Kindle X-Ray alias-collapse card: one entity, all surface forms linked — maps directly onto BookRAG's per-identity snapshot output.
- Fable "chapter rooms": scope chat history and suggested-questions list to the reader's current chapter; auto-advance as they progress.
- Fandom layered reveal dialog for risky answers ("this references events through chapter 19 — reveal?") instead of hard refusal.
- Long-press-name → glossary card interaction in the reading view; uses existing allowed-nodes query with a name filter.
- OpenDyslexic + adjustable line-height toggle; near-zero implementation cost, high accessibility payoff.
- "I'll answer this when you reach chapter N" deferred-answer pattern — queue the question, re-surface when progress advances.
- Always-on "safe through ch. N" pill as the chat's primary trust affordance; doubles as the cursor control.

### 42. Game narrative KGs

**Researched:** 2026-04-22 (iteration 42 — bonus round 2)

**TL;DR:** AAA games have been solving per-entity knowledge gating and hundreds-of-flags state management for two decades, mostly via hand-authored scripts (Ink, Yarn, Cyberpunk's quest facts) plus fuzzy rule databases (Valve's L4D2 system). Every one of BookRAG's core primitives — progress cursor, spoiler allowlist, per-entity snapshots — has a shipped analog in game tech, which means the hard problems (query performance, edit workflows, writer UX) have prior art worth stealing. The inverse is also true: BookRAG automates what games hand-author, which is a defensible product wedge for a game-writer QA tool.

**Dialog system tools:** Ink (inkle) organizes narrative into **knots** (named blocks) and **stitches** (sub-blocks), with conditional choices gated on whether a knot has been visited — the visit count is the state primitive ([inkle/ink WritingWithInk](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md)). Yarn Spinner uses `$var` variables (bool/number/string), `<<set>>` commands, and `<<if>>...<<endif>>` blocks; options are shown/hidden via inline `<<if>>` on the option line ([Yarn Spinner Flow Control docs](https://docs.yarnspinner.dev/write-yarn-scripts/scripting-fundamentals/flow-control)). Both are essentially graph-of-nodes + boolean predicates — structurally identical to BookRAG's allowlist predicate.

**Quest state & world flags:** Cyberpunk 2077 tracks progress via **quest facts** — named integer keys (e.g. `mq055_judy_default_on`) that default to 0 until explicitly set, compared with `<, <=, ==, >=, >` to drive Pauses and Conditions in quest graphs ([redmodding wiki: Quests facts and files](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators-theory/files-and-what-they-do/file-formats/quests-.scene-files/quests-facts-and-files)). Skyrim's Creation Kit exposes **Story Manager + Aliases + Scenes** to generate radiant quests whose actors/locations resolve at runtime ([UESP Skyrim:Radiant](https://en.uesp.net/wiki/Skyrim:Radiant)).

**Per-NPC knowledge systems:** Valve's **AI-Driven Dynamic Dialog** (Elan Ruskin, GDC 2012) is the canonical reference: thousands of "facts" about the world are fuzzy-pattern-matched against a rule database of response lines; writers add rules like columns in a spreadsheet, and the runtime picks the best-matching line given current facts ([GDC Vault](https://gdcvault.com/play/1015528/AI-driven-Dynamic-Dialog-through), [gamedeveloper.com overview](https://www.gamedeveloper.com/design/video-valve-s-system-for-creating-ai-driven-dynamic-dialog)). This is a **rule-based retrieval** architecture over a typed fact store — directly analogous to BookRAG's allowed-nodes set + LLM-completion shape, except BookRAG's facts are KG nodes rather than key/value flags.

**Character relationship / affection:** BG3 uses per-companion approval in [-∞, +100], with thresholds that gate romance dialogue options and a hard −50 floor that permanently removes the companion ([bg3.wiki Approval](https://bg3.wiki/wiki/Approval), [FextraLife BG3 Approval Guide](https://baldursgate3.wiki.fextralife.com/Companion+Approval+Guide)). This is a **typed weighted edge** between PC and NPC with discrete threshold events — same shape as a BookRAG Relationship edge if we added a numeric valence attribute.

**Procedural narrative systems:** Ken Levine's **Narrative Lego** (GDC 2014) proposes "Stars" (NPCs) with ~10 **Passions** each (percentage bars raised/lowered by player actions); narrative beats emerge from Passion thresholds rather than hand-authored branches ([GDC Vault Narrative Legos](https://www.gdcvault.com/play/1020434/Narrative), [gamedeveloper.com Ken Levine's Narrative Lego's](https://www.gamedeveloper.com/design/ken-levine-s-narrative-lego-s)). The insight for BookRAG: character state can be represented as a small vector of continuous emotional axes, not just flags.

**Articy:draft as interchange:** articy:draft X exports to a **Generic JSON** format whose top-level `Packages` node contains the project data; export is rule-configurable per object type/template ([Articy Help Center Exports_JSON](https://www.articy.com/help/adx/Exports_JSON.html), [articy technical exports overview](https://www.articy.com/en/articydraft/integration/techexports/)). This is the closest commercial schema to what BookRAG produces and a plausible **import path** if we ever wanted to let a game writer load their articy project into BookRAG for KG-based QA.

**AI Dungeon (contrast):** Latitude's AI Dungeon uses **Memory Bank** (LLM-summarized past actions, embedding-ranked by relevance), **Story Cards** (keyword-triggered world info), and **Plot Essentials** (always-injected context) to compensate for finite context windows ([AID Memory System FAQ](https://help.aidungeon.com/faq/the-memory-system), [Why does the AI forget?](https://help.aidungeon.com/faq/why-does-the-ai-forget-or-mix-things-up)). Failure modes the docs openly acknowledge: forgetting, character amnesia, inconsistency — all traceable to the lack of a structured KG. This is the "no-KG" null hypothesis and BookRAG's structured graph is its answer.

**Shared primitives with BookRAG:**
- Quest facts (Cyberpunk) ≡ spoiler-filter allowlist predicates.
- Ink knot-visited checks ≡ `effective_latest_chapter ≤ cursor`.
- BG3 approval valence ≡ weighted Relationship edges.
- Valve rule database retrieval ≡ allowed-nodes-as-context LLM completion.
- AI Dungeon Memory Bank ≡ Phase 2 per-identity snapshot selection.

**What BookRAG could borrow:**
1. **Yarn-style conditional predicate syntax** on edges/nodes for authors/curators (e.g. `visible_if: $chapter_seen >= 7 AND $witnessed_event_42`) — more expressive than a single `first_chapter` int.
2. **Articy JSON as an import format** — let game writers drop an articy export into BookRAG for structured NPC-knowledge QA.
3. **BG3-style numeric valence on Relationship edges** — extend the Relationship DataPoint with a `-100..+100` affection score extracted per batch, enabling "how does X feel about Y at chapter N" queries.
4. **Valve-style rule retrieval** — for future procedural re-telling ("summarize what the reader knows so far about Scrooge"), pattern-match allowed nodes against response-rule templates rather than free LLM gen.
5. **Per-NPC "witnessed" projection** — extend the cursor to optionally filter by `witnessed_by=<character>` so the LLM answers from that character's knowledge, not the reader's (feeds theory-of-mind work from iter 34).

**What BookRAG has that games don't:** automated **extraction from natural-language prose**. Every system above assumes a writer hand-authors facts, flags, and knots. BookRAG ingests an EPUB and produces the flag graph. That inversion is the defensible wedge.

**Product thesis — BookRAG as a game-writer QA companion:** BG3 ships ~2M words of dialogue; Larian writers use internal tools to track who-knows-what, and bugs of the form "NPC references an event the player hasn't triggered" are endemic. A tool that ingests a studio's Ink/Yarn/articy export + story bible prose, builds a KG, and answers "at quest stage Y, what does NPC X know?" has a clear pain-point buyer. The Phase 2 per-identity snapshot work is already the right abstraction — swap "chapter cursor" for "quest-fact state vector" and the architecture ports.

**Key citations:**
- [Elan Ruskin — AI-Driven Dynamic Dialog, GDC 2012](https://gdcvault.com/play/1015528/AI-driven-Dynamic-Dialog-through)
- [Ken Levine — Narrative Legos, GDC 2014](https://www.gdcvault.com/play/1020434/Narrative)
- [Ink Writing With Ink docs](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md)
- [Yarn Spinner Flow Control](https://docs.yarnspinner.dev/write-yarn-scripts/scripting-fundamentals/flow-control)
- [Cyberpunk 2077 quest facts](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators-theory/files-and-what-they-do/file-formats/quests-.scene-files/quests-facts-and-files)
- [BG3 Approval wiki](https://bg3.wiki/wiki/Approval)
- [articy:draft JSON export](https://www.articy.com/help/adx/Exports_JSON.html)
- [AI Dungeon Memory System](https://help.aidungeon.com/faq/the-memory-system)
- [UESP Skyrim:Radiant](https://en.uesp.net/wiki/Skyrim:Radiant)

**Concrete ideas worth stealing:**
- Add a numeric **valence** attribute (`[-100, 100]`) to Relationship DataPoints, extracted per batch — enables affection/rapport queries and stacks with Phase 2 snapshots.
- Add a **predicate-DSL** field on spoiler-filter allowlists, Yarn-style: richer than `first_chapter` int and queryable by future curator UIs.
- Add a `witnessed_by` optional filter to the query endpoint so callers can project the KG through a single character's knowledge (per-NPC fog-of-war).
- Prototype an **articy:draft JSON importer** as an optional ingest path — opens the door to game-writer QA as a vertical.
- Steal Valve's **rule-table editing UX** for curators: a spreadsheet where each row is a retrieval rule matching fact-patterns → canned response — complements the LLM path with deterministic fallbacks.


### 43. Audiobook & podcast narrative extraction

**Researched:** 2026-04-22 (iteration 43 — bonus round 2)

**TL;DR:** BookRAG's Phase 1/2 pipeline generalizes to audio with a Whisper-large-v3 front-end (~2% WER on clean narration, ~10% average across benchmarks) and pyannote diarization (15-25% DER on challenging multi-voice content), but two hard problems arise: (1) audio lacks explicit chapter/paragraph boundaries, which breaks the cursor-based spoiler gate, and (2) single-narrator audiobooks defeat diarization because one voice performs all characters. The market is large — global audiobook revenue ~$10.9B in 2025 ([Grand View Research](https://www.grandviewresearch.com/industry-analysis/audiobooks-market)) and narrative podcasts like The Magnus Archives crossed 100M downloads in Feb 2025 ([Rusty Quill via Spotify](https://rustyquill.com/show/the-magnus-archives/)) — and serialized-podcast fandoms are the most spoiler-anxious audiences on the internet, making BookRAG's spoiler-gating thesis more valuable for audio than for text.

**ASR state of the art:** Whisper-large-v3 (OpenAI, 2023, arXiv 2212.04356) hits ~2.1% WER on LibriSpeech clean (a 12.5% relative improvement over v2) and ~10.3% averaged across benchmarks ([SambaNova/SayToWords benchmarks](https://sambanova.ai/blog/introducing-whisper-large-v3)). Deepgram flagged a regression: v3 has 4x more hallucinations than v2 on noisy real-world data (median WER 53.4 vs 12.7 on phone/video) ([Deepgram](https://deepgram.com/learn/whisper-v3-results)) — so audiobook use case (studio-clean) is Whisper's best-case scenario, but full-cast drama and podcasts with ambient sound design are not. AssemblyAI's Universal-2 and Nvidia Parakeet are competitive closed alternatives. Cost on Groq runs v3 at 164x real-time — an 8-hour audiobook transcribes in ~3 minutes ([Groq](https://groq.com/blog/groq-runs-whisper-large-v3-at-a-164x-speed-factor-according-to-new-artificial-analysis-benchmark)).

**Speaker diarization:** pyannote.audio 3.1 is the open-source SOTA; DIHARD-challenge systems achieve 15-25% DER (i.e. 75-85% of audio duration correctly attributed) ([pyannote.ai](https://www.pyannote.ai/blog/how-to-evaluate-speaker-diarization-performance)). The premium pyannoteAI model is ~20% more accurate than OSS. **The gotcha for audiobooks:** most single-narrator audiobooks have exactly one acoustic speaker (the narrator doing voices), so diarization collapses to a trivial single cluster. Character attribution must come from text-level quote attribution (BookNLP's existing strength) applied to the transcript, not from voice embeddings. Full-cast productions (Sandman Audible, Graphic Audio) are the exception where diarization actually helps.

**Audiobook-specific features:** narrator performs all dialog with acting but near-constant voice identity, chapter breaks are often audio-only (silence + bell tone) rather than TTS-announced, and many productions add music/sound design (Audible Originals especially). Chapter-marker metadata embedded in M4B/MP3 files usually exists but doesn't always align with published-book chapters when audiobook editions reorganize content.

**Narrative podcasts:** The Magnus Archives (200 main-run episodes, 2016-2021; Rusty Quill; 100M+ downloads by Feb 2025; continuation The Magnus Protocol launched Jan 2024); Welcome to Night Vale (280+ episodes since 2012, twice-monthly; Night Vale Presents publishes official transcripts for every episode at nightvalepresents.com/transcripts); Limetown (3 seasons); Homecoming (2 seasons, adapted to Amazon Prime); The Bright Sessions (4 seasons, 60+ episodes). Transcripts are widely published for accessibility — Night Vale's official transcript archive covers the full run, and fan-maintained transcripts filled early gaps.

**Existing transcription datasets:** LibriSpeech (~1000 hrs, LibriVox public-domain audiobooks read from Project Gutenberg, 16kHz, split into train.100/train.360/train.500 and clean/other by WER percentile — [OpenSLR 12](https://www.openslr.org/12), [Panayotov et al. ICASSP 2015](https://www.danielpovey.com/files/2015_icassp_librispeech.pdf)); Multilingual LibriSpeech (~50k hrs, 8 languages, [OpenSLR 94](https://www.openslr.org/94/)); Gigaspeech (10k hrs mixed audiobook/podcast/YouTube). None are copyrighted contemporary audiobooks — that data is locked inside Audible.

**Pipeline extension for BookRAG:** audio file → Whisper-large-v3 (word-level timestamps) → pyannote diarization (skip for single-narrator) → chapter-marker detection (M4B metadata OR silence+acoustic-jingle detection) → produce a text transcript structurally isomorphic to our current `raw/chapters/chapter_NN.txt` + paragraph split → feed into existing BookNLP → coref → ontology → Cognee pipeline. Where it breaks: paragraph boundaries don't exist in audio; a "paragraph" would have to be reconstructed as a pause-delimited utterance group (heuristic: >500ms silence = paragraph break). Scene breaks in serialized podcasts map to episode boundaries cleanly — easier than audiobook chapters.

**Timestamp-based spoiler gating:** podcast episode number is a clean cursor (same gating as chapter). For audiobooks the natural cursor is wall-clock position (e.g. "4h 23m into the file"). Mapping wall-clock to the BookRAG graph requires aligning every extracted DataPoint to a `first_timestamp` attribute during Phase 2. `effective_latest_chapter` becomes `effective_latest_timestamp`. The paragraph-cursor feature (Phase 2 per-identity snapshot) generalizes: each diarized utterance or each silence-segmented "paragraph" becomes the minimum gating unit.

**Licensing:** Audible files are AAX/AAXC DRM-protected and tied to an Amazon account; OpenAudible/AAXtoMP3 decryption is a grey area (EULA-prohibited but arguably fair-use for personal format shifting under US §1201 exemptions, which have been granted for accessibility). LibriVox is public-domain and free. Podcasts are published via open RSS — legally fetchable, though Terms of Use on many shows restrict redistribution of transcripts. BookRAG's "ingest audio file user owns, never redistribute" posture is similar to the physical-EPUB posture today.

**Accessibility angle:** visually-impaired users are already disproportionately audiobook-heavy. Pairing a voice-query interface with spoiler-safe answers is a strong accessibility story — WCAG screen-reader compat (flagged in iter 41) plus voice I/O makes BookRAG a genuine assistive-tech product, which unlocks education/library procurement channels.

**Dual-mode reading (text + audio):** Amazon's Whispersync-for-Voice feature already aligns Kindle + Audible for millions of users — the technical precedent exists and BookRAG could mirror it by keeping a shared cursor between EPUB paragraph and audiobook timestamp, auto-syncing so "where am I in audio" always resolves to the correct text paragraph and vice versa.

**Specific podcasts worth supporting:** The Magnus Archives (archive-horror, strongly serial, 200 episodes, huge spoiler-anxious fandom, official transcripts exist); The Adventure Zone (5 seasons, actual-play D&D, massive fandom wiki with character pages); The Bright Sessions (4 seasons, superhero-therapy drama with branching character arcs); Homecoming (self-contained, adapted to Prime — good "also-read-also-listen" case); Limetown (investigative-fiction, short, easy test corpus).

**Product thesis:** in-car audiobook companion — driver asks "who was Mrs. Cratchit again?" via voice, BookRAG returns a spoiler-gated audio answer bounded by current playback position. Inferring playback position from the audio app requires platform integration (Audible doesn't expose this; Spotify Connect does for podcasts, Apple MediaPlayer framework does for any audio on iOS). A lighter MVP: user manually sets "I'm at episode 42, 15 minutes in" once per session, same UX as today's chapter cursor.

**Key citations:** [Whisper arXiv 2212.04356](https://arxiv.org/abs/2212.04356); [pyannote-audio GitHub](https://github.com/pyannote/pyannote-audio); [LibriSpeech ICASSP 2015 paper](https://www.danielpovey.com/files/2015_icassp_librispeech.pdf); [Grand View Audiobook Market Report 2030](https://www.grandviewresearch.com/industry-analysis/audiobooks-market); [Rusty Quill — Magnus Archives 100M downloads](https://rustyquill.com/show/the-magnus-archives/); [Night Vale official transcripts](http://www.nightvalepresents.com/transcripts); [Deepgram — Whisper v3 hallucinations](https://deepgram.com/learn/whisper-v3-results).

**Concrete ideas worth stealing:**
- Replace paragraph boundaries with **silence-delimited utterance groups** (>500ms pause) as the minimum spoiler-gating unit — maps cleanly onto Phase 2 per-identity snapshots.
- Add a **`first_timestamp` / `last_known_timestamp`** attribute to every DataPoint alongside chapter numbers, so the same graph serves text and audio cursors interchangeably.
- For single-narrator audiobooks, **skip diarization entirely** and rely on BookNLP quote-attribution on the Whisper transcript — diarization is noise for this common case.
- **Audiobook chapter detection from M4B markers** first, falling back to silence+jingle heuristic — gives a free Phase 1 stage with no new ML.
- **Whispersync-style cursor linking**: one shared reading-progress object keyed by book-edition-ID covers both EPUB paragraph and audio timestamp via an alignment table built once at ingest time (text-audio forced alignment with gentle / aeneas).
- Target **Magnus Archives + Night Vale + The Adventure Zone** as the three flagship podcast corpora — all have complete official transcripts, large spoiler-sensitive fandoms, and strong serial continuity.

### 45. Cross-book / series-level KG linking

**Researched:** 2026-04-22 (iteration 45 — bonus round 3)

**TL;DR:** Series-level KGs are a generalization of per-book KGs where character identity is keyed on `(series_id, canonical_name)` and the spoiler cursor extends to `(book_order, chapter, paragraph)`. There is essentially zero academic literature on *series-scale* coreference (BookCoref caps at single books of ~200k tokens), but fan infrastructure — especially Spliki's per-chapter section tagging and Dragonmount's character database — shows the UX is solved even when the NLP isn't. Author-facing continuity tools (Urdr, Plottr, World Anvil) have started automating consistency QA but publishing houses have no standard continuity-checking software.

**Cross-document entity linking.** BookCoref (ACL 2025, Martinelli et al., 53-book benchmark averaging 200k+ tokens) is the first book-scale CR benchmark and explicitly stops at the single-book boundary — the train/test splits are per-book documents from Project Gutenberg [arxiv.org/abs/2507.12075]. xCoRe (EMNLP 2025) proposes a three-step unified pipeline (within-context clusters → cross-context merge) that is the natural extension point for series-level linking [aclanthology.org/2025.emnlp-main.1737]. The WEC-Eng and ECB+ benchmarks referenced in iteration 11 cover news-article-scale CDCR but not narrative fiction. For BookRAG, the key insight is that *within-series* CDCR is an easier problem than generic CDCR: entity name strings are highly repetitive across volumes (Harry, Hermione, Ron appear in all 7 HP books), so a simple string-match-plus-ontology-check likely outperforms a learned CDCR system that was trained on news.

**Series-KG data model.** Proposed extension: add a `Series` root DataPoint and `Book` DataPoints with `book_order: int`. `Character.identity` keys on `(series_id, canonical_name)` instead of the current `(book_id, name)`. Per-identity snapshots are keyed on `(series_id, identity, book_order, chapter)` rather than `(book_id, identity, chapter)`. The `effective_latest_chapter` field generalizes to `effective_latest_position = (book_order, chapter)` with lexicographic comparison. Spliki implements exactly this pattern: "every section of an article is assigned to a specific chapter or episode" and the user sets a dropdown cursor ("your spot in the story") that filters future sections [spliki.com/wiki/wheel_of_time_books].

**Worldbuilding consistency.** Two framings: (a) reader-facing — "did the author contradict themselves?"; (b) author-facing — "am I about to contradict myself?". Urdr is the most ambitious automated entry: its "Consistency Engine" uses a "Unified 7" relational schema plus RAG/vector search to catch timeline errors ("Kaelen cannot be exiled in 2140 if he died in 2138"), rule violations (magic system drift), dead-character returns, and geography glitches [urdr.io/blog/fix-plot-holes-consistency-checks]. World Anvil and Campfire provide the *infrastructure* (character sheets, timelines, relationship graphs) but leave the consistency checking to humans [kindlepreneur.com/campfire-vs-world-anvil]. Plottr and Scrivener+Aeon Timeline+Scapple are the dominant manual "series bible" stacks [plottr.com/series-bible-software; hollowlands.com/2014/09/creating-a-book-series-bible-using-scrivener-scapple-and-aeon-timeline]. A BookRAG-native consistency check is almost free: run the same per-identity snapshot diff across books and flag attribute contradictions (e.g., Character.eye_color changes between snapshots without an in-text trigger).

**Reading order for non-linear series.** Narnia is the canonical test case: American editions used publication order, HarperCollins standardized chronological order in 1994, and the scholarly consensus recommends *publication order for first read, chronological for re-read* — chiefly because "None of the children knew who Aslan was, any more than you do" breaks in chronological order [narniaweb.com/books/readingorder; thegospelcoalition.org/blogs/trevin-wax/why-you-should-narnia-in-publication-order]. This means `book_order` cannot be a single int — it needs to be either reader-declared or a branching DAG (Discworld's reading-order flowchart is the extreme case: 40+ books with multiple entry-point subseries). Multi-POV series (Expanse, ASOIAF, Malazan) add a within-book dimension: ASOIAF's *A Feast for Crows* and *A Dance with Dragons* cover the same timeframe with disjoint POV casts and are commonly read interleaved ("A Feast for Crows and A Dance with Dragons combined chronological order") — BookRAG would need a `(book_order, pov_slice, chapter)` cursor to support this.

**Author-intent data.** Companion references are the ground truth for series-level canonical facts: Tolkien's *Silmarillion* + *Unfinished Tales* for LOTR, Pottermore/Wizarding World for HP, N.K. Jemisin's *Broken Earth* appendices, Sanderson's *Arcanum Unbounded* for the Cosmere. Fan wikis are the largest distant-supervision source — the WoT Compendium tracks 2,792 named characters [hammondkd.github.io/WoT-compendium], A Wheel of Time Wiki on Fandom, and Dragonmount's character database are all structured enough to scrape as gold labels for series-level entity linking [wot.fandom.com; dragonmount.com/characters/index]. Fandom's infobox templates are the de facto data model: per-character attributes like `species`, `affiliation`, `status`, `first_appearance`, `last_appearance` with book/chapter provenance.

**Publishing-industry tooling.** Big 5 publishers have no standard continuity-checking software — Madeleine Vasaly's editor blog lists the state of the art as "Scrivener collections, style sheets in Word, spreadsheet character bibles" [madeleinevasaly.com/blog/2022/8/3/tools-for-maintaining-continuity-in-fiction]. Series bibles remain a manual discipline; even $20M-franchise series (Jack Reacher, Expanse) are tracked in Scrivener + spreadsheets per author interviews. This is a *green field* for BookRAG: a series-scale KG built automatically from the manuscripts is something no Big 5 house currently has.

**BookRAG extension design.**
(a) Add `Series` and `Book` DataPoint types with `book_order: int` (nullable for standalones, list for branching series).
(b) Character identity keys on `(series_id, canonical_name)`; introduce a series-level ontology-discovery stage that merges per-book ontologies by string match + embedding similarity + human confirmation.
(c) Cross-book per-identity snapshot selection with cursor `(book_order, chapter, paragraph)`; `load_allowed_nodes` filters on lexicographic `(book_order, chapter) <= cursor`.
(d) "Series library" view in UI: pick a series, see per-book reading progress, single chat box queries the series-wide KG bounded by the union of per-book cursors.
(e) Reading-order DAG support: config per series declares allowed traversal orders; the cursor is a monotone position in that DAG, not an int.

**Cross-book coref challenges.** Same name, different character: Fred/George Weasley, the three Gryffindor quidditch Weasleys, or "Jon" across ASOIAF (Jon Snow, Jon Connington, Jon Arryn, Jon Umber) require disambiguation by context and relationship rather than string match. Same character, major appearance change: Harry at 11 vs 17, or Paul-then-Muad'Dib-then-the-Preacher in Dune — a single canonical identity must survive per-book snapshot drift. Spin-offs with cameos: HP's *Cursed Child*, *Fantastic Beasts*, the Strike novels (Rowling as Galbraith) — these are adjacent series that may share characters but live in a different `series_id` namespace. Fan-fiction crossovers are out of scope but motivate a `shared_universe` relation between series.

**Specific test series.** Red Rising (5 books, tight continuity, single-POV-then-multi-POV, validates `book_order` cursor); Discworld (40+ books, deliberately loose continuity, famous reading-order flowchart — validates the DAG model); Expanse (9 books, 3 primary POVs + novella interludes — validates POV-slice cursor and skip-interlude support); Wheel of Time (14 books, 2,792+ named characters, retcons from Robert Jordan to Brandon Sanderson — validates large-scale entity linking and author-style-shift robustness). Narnia is the Narnia-order unit test.

**Key citations:**
- BookCoref: Martinelli et al., ACL 2025 [arxiv.org/abs/2507.12075]
- xCoRe unified CDCR: EMNLP 2025 [aclanthology.org/2025.emnlp-main.1737]
- Spliki anti-spoiler wiki: [spliki.com; dragonmount.com/forums/topic/108734]
- Urdr Consistency Engine: [urdr.io/blog/fix-plot-holes-consistency-checks]
- WoT Compendium (2,792 characters): [hammondkd.github.io/WoT-compendium]
- Narnia reading-order debate: [narniaweb.com/books/readingorder]
- Fiction-editor continuity tooling survey: [madeleinevasaly.com/blog/2022/8/3/tools-for-maintaining-continuity-in-fiction]

**Concrete ideas worth stealing:**
- Spliki's dropdown-cursor UX maps 1:1 onto BookRAG's current `(chapter, paragraph)` cursor — extend the dropdown to `(book, chapter, paragraph)` and the filtering logic is unchanged.
- Urdr's "Unified 7" relational schema + contradiction rules (timeline, rule, dead-char, geography) are a ready-made checklist for a `consistency_check` endpoint over the series KG.
- Fandom infobox templates (`first_appearance`, `last_appearance`, `status`, `affiliation`) are a drop-in attribute schema for series-scoped Character DataPoints.
- Reading-order DAG per series, not a single int — even tight series like ASOIAF need it for the Feast+Dance interleave.
- Scrape fan wikis as distant supervision: for each wiki character article, the (name, first_appearance_book) pairs are free gold labels for series-level entity linking evaluation.
- Publication-order-first-then-chronological-on-reread is a *per-reader preference*, so store `reading_mode: publication|chronological|custom` alongside the cursor.

### 46. Named entity linking for fictional entities

**Researched:** 2026-04-22 (iteration 46 — bonus round 3)

**TL;DR:** NEL to Wikidata is solved for encyclopedic (news/Wikipedia) text — ReFinED (Ayoola 2022) scales to all ~90M Wikidata entities and beats prior SOTA by +3.7 F1 — but fiction is out-of-distribution: benchmarks (AIDA-CoNLL, MSNBC, TAC-KBP) contain essentially no fictional-character mentions, and Wikidata coverage is deep for HP/LOTR/ASOIAF yet long-tail-sparse. For BookRAG, NEL is useful as a *best-effort enrichment layer* on canonical surface forms (top-N characters per book), gated behind spoiler filters, never as the primary identity resolver.

**Wikidata coverage of fiction:** Wikidata models fiction via `instance of (P31) → fictional human (Q15632617)` / `fictional character (Q95074)`, with attributes like `present in work (P1441)`, `from narrative universe (P1080)`, `creator (P170)`, `narrative role (P7184)`. [Wikidata:WikiProject Fictional universes](https://www.wikidata.org/wiki/Wikidata:WikiProject_Fictional_universes) and [WikiProject Narration](https://www.wikidata.org/wiki/Wikidata:WikiProject_Narration) coordinate the schema; `characters (P674)` on a work links outward to character Q-IDs. Coverage is heavily skewed: major franchises (HP, LOTR, GoT/ASOIAF, MCU, Star Wars) have hundreds of fully-attributed character entries; mid-tier literary fiction often has only protagonist Q-IDs; most public-domain 19th-century fiction has sparse-to-zero character coverage (Scrooge exists as Q2546323 but with ~5 statements vs. ~50 for Frodo Baggins Q173568).

**NEL state of the art:**
- **BLINK** (Wu et al. 2020, [arXiv:1911.03814](https://arxiv.org/abs/1911.03814)) — two-stage BERT bi-encoder retrieves from 5.9M Wikipedia entities, then cross-encoder re-ranks. Zero-shot capable; entities defined by short text description. SOTA on TACKBP-2010 and zero-shot WikiLinks.
- **GENRE** (De Cao et al. ICLR 2021, [arXiv:2010.00904](https://arxiv.org/abs/2010.00904)) — autoregressive BART generates the entity's unique title token-by-token, constrained by a prefix trie. Tiny memory footprint (scales with vocab, not entity count); SOTA or competitive on 20+ datasets.
- **ReFinED** (Ayoola et al. NAACL 2022, [arXiv:2207.04108](https://arxiv.org/abs/2207.04108)) — joint mention-detection + fine-grained typing + disambiguation in one forward pass, **60× faster than BLINK**, scales to all ~90M Wikidata entities (15× Wikipedia), +3.7 F1 average over prior SOTA. Shipped at Amazon for web-scale extraction.
- **LLM-based NEL** (2024–2025) — hybrid approaches like the [LLM-SPARQL framework](https://link.springer.com/chapter/10.1007/978-981-96-1809-5_16) and [adaptive-routing targeted-reasoning systems](https://arxiv.org/html/2510.20098) use GPT-4-class models for hard disambiguation cases, outperforming ReFinED on CoNLL-AIDA, MSNBC, AQUAINT.

**Fictional-entity NEL specifics:** Near-zero dedicated work. [protagonistTagger (Gagala 2021, arXiv:2110.01349)](https://arxiv.org/pdf/2110.01349) is the closest — NER+NED for literary characters, 83% P/R, but disambiguates *within a single novel* (Tom Sawyer variants → `TOM_SAWYER`), not to Wikidata Q-IDs. BookNLP character clustering is the de facto intra-book baseline. No published benchmark links novel mentions to Wikidata at scale; the HTRC 213k-novel BookNLP dataset has surface forms but no Q-IDs.

**DBpedia vs Wikidata:** DBpedia is extracted from Wikipedia infoboxes — coverage mirrors Wikipedia's fiction articles (good for famous characters with their own article, nothing for minor ones). Wikidata is manually curated and allows entries without a Wikipedia article, so it has strictly better long-tail fiction coverage plus richer typed relations (P1441 present-in-work, P1080 narrative-universe). Prefer Wikidata as the target KB.

**Anti-pattern: linking to a spoiler-unaware KB:** Wikidata character entries summarize the entire canon. Scrooge's Wikidata entry reveals his redemption arc in the description; Ned Stark's reveals his fate. Linking naively at query time would leak future plot to a chapter-3 reader. Any NEL integration MUST filter Wikidata fields through the same spoiler gate as the internal KG, OR only surface the Q-ID itself (not the description) until the reader has crossed a threshold chapter.

**Use cases for NEL in BookRAG:**
1. **Cross-book inference** — "other miserly characters in literature" SPARQL query over `instance of fictional character` + trait edges.
2. **Canonical metadata** — pin Dickens's Scrooge to Q2546323, author attribution sanity check, disambiguate same-name characters across books.
3. **Series-scoped disambiguation** (pairs with iter 45) — link all series-internal mentions to a single Q-ID across books.
4. **External enrichment** — pull typed relations (P170 creator, P136 genre) for UI display.
5. **Evaluation** — Wikidata character lists as gold references for BookRAG's extracted character set.

**Risks:** (a) spoiler leakage via descriptions/aliases; (b) wrong links — Scrooge the character vs. Scrooge McDuck; (c) crowdsourced drift (fan-edited entries change); (d) over-reliance on sparse long-tail entries; (e) confidence miscalibration — models are trained on encyclopedic text and may be overconfident on OOD literary surface forms.

**Implementation path:** (1) run BookNLP character clustering to get canonical surface form per identity; (2) query ReFinED or a GENRE constrained-decoding model over the top-N (say N=20) characters per book, restricted to `instance of ⊆ {fictional character, fictional human, ...}`; (3) confidence threshold ≥ 0.85 + type-compatibility check; (4) manual review UI for top-N, accept/reject/override; (5) store `wikidata_qid` as optional field on Character DataPoint; (6) any Wikidata-sourced text (description, aliases) goes through the same chapter-bound spoiler filter as internal KG nodes; (7) cache SPARQL lookups locally — don't hit the Wikidata endpoint per query.

**Key citations:**
- [BLINK (Wu et al. 2020)](https://arxiv.org/abs/1911.03814) + [facebookresearch/BLINK](https://github.com/facebookresearch/BLINK)
- [GENRE (De Cao et al. ICLR 2021)](https://arxiv.org/abs/2010.00904) + [facebookresearch/GENRE](https://github.com/facebookresearch/GENRE)
- [ReFinED (Ayoola et al. NAACL 2022)](https://arxiv.org/abs/2207.04108) + [amazon-science/ReFinED](https://github.com/amazon-science/ReFinED) + [Amazon Science blog](https://www.amazon.science/blog/improving-entity-linking-between-texts-and-knowledge-bases)
- [Wikidata WikiProject Fictional universes](https://www.wikidata.org/wiki/Wikidata:WikiProject_Fictional_universes), [Property P674 characters](https://www.wikidata.org/wiki/Property:P674), [Q95074 character](https://www.wikidata.org/wiki/Q95074)
- [protagonistTagger (Gagala 2021)](https://arxiv.org/pdf/2110.01349)
- [LLM-SPARQL hybrid for Wikidata NEL (2024)](https://link.springer.com/chapter/10.1007/978-981-96-1809-5_16), [Adaptive-routing LLM NEL (arXiv:2510.20098)](https://arxiv.org/html/2510.20098)
- [ELEVANT entity-linking evaluation tool](https://github.com/ad-freiburg/elevant)

**Concrete ideas worth stealing:**
- Use **ReFinED with a `fictional character` type constraint** as a drop-in NEL layer — its joint typing head lets you reject real-world-entity candidates cleanly before disambiguation.
- Run NEL only on the **top-N characters per book** (by mention count) — cost-bounded, and the long tail has no Wikidata coverage anyway so there's nothing to link to.
- Treat Wikidata Q-IDs as a **spoiler-gated sidecar**, not a replacement identity — always keep BookRAG's internal identity as source of truth; Q-ID is an optional enrichment field.
- **Spoiler-filter the linked data, not just the link** — when surfacing Wikidata fields, redact description/P1441 values whose associated work/chapter exceeds the reader's bound.
- Use **Wikidata P674 characters-of-work** as a gold reference set at ingest time: if BookRAG extracted 30 characters but Wikidata lists 50 for this work, flag the delta for review (evaluation without manual annotation).
- Use **GENRE constrained decoding** over a book-specific prefix trie (only this book's Wikidata characters) for fast, guaranteed-valid disambiguation when a book is known to have full Wikidata coverage (HP, LOTR, ASOIAF).
- Fan-wiki character pages carry Wikidata Q-ID sitelinks — scrape once to get a ready-made distant-supervision mapping for series-level eval.

### 47. Narrator style fingerprinting & author embeddings

**Researched:** 2026-04-22 (iteration 47 — bonus round 3)

**TL;DR:** Modern author embeddings (LUAR, STAR, StyleDistance) compress stylistic identity into dense vectors trained via contrastive learning over same-author text pairs, achieving 80%+ accuracy discriminating among 1,000+ authors. For BookRAG, a per-book style vector unlocks (a) persona replies in the author's narratorial voice, (b) "explain in author's voice" reader aids, and (c) canonicity checks on generated continuations — though IP/ethics around style cloning remain legally unsettled.

**Stylometry foundations:** Burrows's Delta (2002) is still the workhorse of literary attribution — it computes distance between texts using z-scored frequencies of the N most-frequent words (usually function words: prepositions, determiners, particles). Function words are topic-invariant and dense, making them ideal style markers ([Burrows 2002, DSH](https://academic.oup.com/dsh/article-abstract/17/3/267/929277); [Evert et al. 2017 "Understanding Delta"](https://academic.oup.com/dsh/article/32/suppl_2/ii4/3865676)). Delta variants (cosine, quadratic, eder's) remain competitive baselines. Complementary features: character n-grams, POS n-grams, PCFG production rules, punctuation distributions. The classical pipeline: MFW matrix → PCA → nearest-neighbor — remains a strong interpretable baseline even in 2026.

**Author embedding models (2021-2025):**
- **LUAR** (Rivera-Soto et al., EMNLP 2021) — transformer trained with contrastive loss on same-author / different-author episode pairs. First large-scale cross-domain study (Amazon reviews, Reddit, fanfiction). Shows surprising zero-shot transfer between some domains but not others ([ACL Anthology](https://aclanthology.org/2021.emnlp-main.70/); [LLNL/LUAR GitHub](https://github.com/llnl/LUAR)).
- **STAR** (Style Transformer for Authorship Representations) — trained on 4.5M texts from 70k authors with Supervised Contrastive Loss; 80%+ accuracy distinguishing among 1,616 authors with 8 support documents ([Huertas-Tato et al., KBS 2024](https://dl.acm.org/doi/10.1016/j.knosys.2024.111867)).
- **StyleDistance** (Patel et al., NAACL 2025) — addresses content leakage in contrastive authorship training by generating synthetic near-paraphrases with LLMs, varying 40 style features while holding content constant. Outperforms prior embeddings on authorship verification and style transfer eval ([arxiv 2410.12757](https://arxiv.org/html/2410.12757v1); [aclanthology](https://aclanthology.org/2025.naacl-long.436/)).
- **Style-content disentanglement** via InfoNCE + semantic-similarity hard negatives ([Huertas-Tato et al. 2024, arxiv 2411.18472](https://arxiv.org/abs/2411.18472)).
- Notable caveat: "Can Authorship Representation Learning Capture Stylistic Features?" ([TACL 2024](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00610/118299/)) shows LUAR partly encodes topic alongside style — content leakage is the active frontier.

**Style transfer & preservation:** **STRAP** (Krishna, Wieting, Iyyer, EMNLP 2020) reformulates unsupervised style transfer as controlled paraphrase generation: paraphrase input to strip style, then fine-tune per-style decoders to re-stylize ([aclanthology 2020.emnlp-main.55](https://aclanthology.org/2020.emnlp-main.55/); [style.cs.umass.edu](https://style.cs.umass.edu/)). Ships a 15M-sentence, 11-style corpus. STRAP's key insight — style ≠ semantics, so measure transfer by paraphrase-semantic-similarity — reshaped evaluation. 2024+ alternatives: prefix-tuning and soft-prompt controllers with frozen LLMs; style-vector injection into attention layers.

**Authorship verification tasks (PAN @ CLEF):** PAN 2020-2023 ran cross-fandom authorship verification on fanfiction ([pan.webis.de](https://pan.webis.de/publications.html)). PAN 2024 and 2025 pivoted to **Voight-Kampff Generative AI Authorship Verification** — human vs. machine detection, with LLMs adversarially mimicking specific human authors ([PAN 2024](https://pan.webis.de/clef24/pan24-web/generated-content-analysis.html); [PAN 2025](https://pan.webis.de/clef25/pan25-web/generated-content-analysis.html)). Multi-Author Writing Style Analysis (style-change detection inside a document) is a live subtask — directly relevant to detecting narrator shifts.

**Narrator voice vs author voice:** Classical stylometry blurs the two. Multi-author style-change detection (PAN) gives a framework: within one document, detect boundaries where style signature shifts. Applied inside a single novel: distinguishing Dickens's omniscient narrator from Scrooge's dialogue register; or in multi-POV novels (Red Rising has first-person Darrow; ASOIAF rotates POV chapters), segmenting style by POV character. A per-chapter or per-speaker LUAR vector reveals these shifts quantitatively.

**Embeddings for fiction authors:** Project Gutenberg is the standard literary benchmark. LUAR trained on fanfiction transfers to literary authorship but drops accuracy. StyleDistance reports strongest content-independent performance. For a book-level vector: pool chunk-level LUAR embeddings (mean or attention-weighted). Reported retrieval metrics: LUAR R@8 ~70-80% for Reddit-scale authorship; literary-domain numbers are scarcer but stylometry achieves >90% on Gutenberg with 20+ authors.

**Applications to BookRAG:**
- (a) **Persona voice anchoring** — generate Scrooge's reply in Dickens's narratorial voice while respecting the character's dialogue register. Concatenate `[author_style_vector, character_dialogue_prototype]` as soft prompt.
- (b) **Style-aware context** — prepend a few in-book sentences matching a target register to the LLM context as few-shot style demonstrations.
- (c) **Canonicity check** — compute LUAR distance between generated text and the book's style centroid; flag outputs drifting outside N-sigma as "not in the author's voice."
- (d) **Reading-aid style transfer** — "explain this passage in modern plain English" or "rewrite in the author's voice" using STRAP-style paraphrase → re-stylize pipeline.
- (e) **Narrator-shift detection** — use multi-author style-change detection to auto-segment POV chapters, improving speaker attribution (iteration 40).

**Ethics / IP considerations:** Style itself is not copyrightable under current US doctrine, but training on copyrighted corpora to replicate an author's voice is actively litigated (Authors Guild v. OpenAI; NYT v. OpenAI). Extracted style-embedding features are derivative but not verbatim — lower risk than verbatim reproduction but still gray. BookRAG should: (1) surface "in the author's voice" features only for public-domain works by default; (2) for user-uploaded copyrighted books, restrict style-cloning features to local, non-redistributable use; (3) never ship pretrained style vectors for copyrighted authors.

**Practical implementation for BookRAG:**
1. Add a one-time `compute_style_vector` pipeline stage after `parse_epub`: chunk the book at 512 tokens, run through a frozen LUAR or StyleDistance checkpoint, mean-pool → `Book.author_style_vector` (768-d).
2. Store per-chapter and per-POV style vectors alongside the book-level centroid for narrator-shift analysis.
3. At query time, for persona answers, inject style vector as soft prompt (via prefix tuning on the LLM) OR — simpler — retrieve 3 top-similarity canonical passages and use them as few-shot demonstrations.
4. For canonicity checks on extracted relationships: cosine-similarity between an extracted-triplet's source passage embedding and the book's style centroid, flag low-similarity extractions as possible hallucinations.
5. Gate all style-cloning features behind a config flag; default-off for non-public-domain books.

**Key citations:**
- Rivera-Soto et al., "Learning Universal Authorship Representations," EMNLP 2021 ([aclanthology](https://aclanthology.org/2021.emnlp-main.70/))
- Krishna, Wieting, Iyyer, "Reformulating Unsupervised Style Transfer as Paraphrase Generation" (STRAP), EMNLP 2020 ([aclanthology](https://aclanthology.org/2020.emnlp-main.55/))
- Patel et al., "StyleDistance: Stronger Content-Independent Style Embeddings," NAACL 2025 ([aclanthology](https://aclanthology.org/2025.naacl-long.436/))
- Burrows, "'Delta': A Measure of Stylistic Difference and a Guide to Likely Authorship," DSH 2002 ([OUP](https://academic.oup.com/dsh/article-abstract/17/3/267/929277))
- Huertas-Tato et al., "Understanding writing style in social media with supervised contrastively pre-trained transformer" (STAR), KBS 2024 ([ACM](https://dl.acm.org/doi/10.1016/j.knosys.2024.111867))
- PAN @ CLEF shared tasks ([pan.webis.de](https://pan.webis.de/publications.html))
- "Can Authorship Representation Learning Capture Stylistic Features?" TACL 2024 ([MIT Press](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00610/118299/))

**Concrete ideas worth stealing:**
- Ship a `Book.author_style_vector` field populated at ingest via frozen StyleDistance; costs ~1 min per book, unlocks downstream features.
- Per-POV-character style vectors for multi-POV novels — auto-detect narrator boundaries using PAN-style change detection as a sanity check against BookNLP speaker attribution.
- STRAP-style paraphrase-then-restylize for "explain in the author's voice" reader aid — no fine-tuning needed, works with frozen LLMs.
- Use style-centroid cosine as a **cheap hallucination filter** on extracted triplets: passages that don't look like this book probably aren't from this book (catches LLM confabulation during extraction).
- For persona generation, combine BookNLP-attributed dialogue examples (character register) + book-level style vector (narratorial register) as dual soft-prompts — separates "what Scrooge sounds like" from "what Dickens sounds like describing Scrooge."
- Adversarial setup from PAN 2025 (LLMs mimicking specific humans) is a ready-made **eval harness** for BookRAG's persona feature: can a classifier tell a real Scrooge quote from a BookRAG-generated one?
