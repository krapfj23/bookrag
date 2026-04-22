# Cognee prompt library — research notes and BookRAG enhancement proposals

**Date:** 2026-04-22
**Cognee version:** 0.5.6 (installed at `/Users/jeffreykrapf/anaconda3/lib/python3.10/site-packages/cognee/`)
**Author:** derived from a survey of 22 Cognee prompt files + comparison against BookRAG's `prompts/extraction_prompt.txt`.

## Why this doc exists

The previous prompt-tightening pass (commit `ca45b43`) cleaned up relation labels but didn't materially move the eval scores — the single-run LLM extraction variance was the dominant signal (documented in `evaluations/results/2026-04-22-reextraction-summary.md`). Before iterating further on our own prompt, it's worth learning from Cognee's prompt library. Cognee has shipped many variants of graph extraction, consolidation, and QA prompts; our goal is to identify the techniques that would survive being ported into BookRAG's spoiler-safe regime.

## What BookRAG's extraction prompt already has

`prompts/extraction_prompt.txt` is already one of the more structured prompts in this codebase. Today it provides:

- Jinja placeholder injection (`{{ ontology_classes }}`, `{{ ontology_relations }}`, `{{ booknlp_entities }}`, `{{ booknlp_quotes }}`, `{{ chapter_numbers }}`, `{{ text }}`).
- A "Chapter Bounds (CRITICAL)" block with a worked example and a strict rule that `first_chapter` / `last_known_chapter` must be drawn from `{{ chapter_numbers }}`.
- A "Relation Labels (CRITICAL)" block (added in `ca45b43`) that explicitly forbids dialogue verbs (`said`/`asked`/`replied`/`told`/`answered`) and motion verbs (`took`/`came`/`went`/`walked`/`met`) as `relation_type`, plus a list of 12+ semantic labels to prefer and a substitution test.
- A "Self-Check Before Returning" block that enumerates four verifications (chapter bounds, future-tense prohibition, etc.).
- A typed JSON schema that covers Characters, Locations, Factions, Events, Relationships, Themes.
- Explicit prior-knowledge suppression: "Do NOT use your prior knowledge of this book."

The structural invariants (chapter bounds, no foreshadowing, forbidden relation verbs, self-check) are specific to spoiler-aware reading and do not appear in Cognee. The open questions are whether there are patterns from Cognee that would improve precision or reduce extraction variance WITHOUT weakening those invariants.

## Cognee prompts surveyed

**Graph extraction (5 files)**
- `generate_graph_prompt_oneshot.txt` — general KG extraction with one-shot example; atomic node taxonomy (Person/Organization/Location/Date/Event/Work/Product/Concept).
- `generate_event_graph_prompt.txt` — "ANY action or verb = one event"; quantity over filtering; explicit disallowed-examples language.
- `generate_event_entity_prompt.txt` — extracts entities FROM already-identified events with typed semantic roles (agent, subject, instrument, source, cause, effect, purpose); explicit temporal-entity exclusion.
- `patch_gen_kg_instructions.txt` — code-patch generation, not relevant.
- `extract_ontology.txt` — sparse; BookRAG already discovers ontology separately.
- `extract_entities_user.txt` — minimal fallback template.

**Cascade extraction (4 files in `cognee/tasks/graph/cascade_extract/prompts/`)**
- `extract_graph_nodes_prompt_system.txt` + `..._input.txt` — iterative node extraction across numbered rounds, accumulating "Previously Extracted Entities".
- `extract_graph_relationship_names_prompt_system.txt` + `..._input.txt` — two-phase: first discover candidate relationship names, then re-use as vocabulary.
- `extract_graph_edge_triplets_prompt_system.txt` + `..._input.txt` — form `(start_node, relationship_name, end_node)` triplets from pre-identified nodes and relation names; "exclude trivial, redundant, nonsensical triplets".

**Retrieval / answering (4 files)**
- `answer_simple_question.txt` — brief QA with provided context.
- `answer_simple_question_restricted.txt` — adds explicit rejection language: "If provided context is not connected to the question, answer: The provided knowledge base does not contain the answer."
- `graph_context_for_question.txt` — formats graph context as `node1 -- relation -- node2` triplets (structurally identical to our triplet arrow format).
- `context_for_question.txt` — fallback for raw text context.

**Consolidation + summarization (3 files)**
- `consolidate_entity_details.txt` — synthesizes entity descriptions "using its own description, neighboring nodes, and edges connecting them"; instructs to use synonyms to avoid verbatim duplication.
- `summarize_content.txt` — brief paraphrasing.
- `summarize_search_results.txt` — consolidates relationship lists, "eliminate redundancies, summarize input into natural sentences".

## What Cognee does that BookRAG does not (worth borrowing)

Ten concrete proposals, ordered roughly by ROI / safety. Each notes where it would plug in and its blast radius.

### 1. Triplet validation pass (LOW blast)

Cognee's `extract_graph_edge_triplets_prompt_system.txt` has an explicit instruction: "exclude trivial, redundant, nonsensical triplets" and requires every triplet to be in `(start_node, relationship_name, end_node)` form with both endpoints validated against the already-extracted node set.

**Proposal:** Add a "Triplet Validation" bullet to our Self-Check section:

```
5. For every relationship you emit, verify:
   - `source_name` and `target_name` BOTH exist in the characters/locations arrays you just produced.
   - `relation_type` is NOT "is_a", "has", "relates_to", "involves", "appears_in", or any other generic container predicate. (Those are already implied by the typed schema.)
   - The same (source, relation_type, target) triple does not appear twice — merge descriptions if it does.
```

**Risk:** None; structural validation only. This catches drift like `Scrooge → employs → Bob Cratchit` appearing twice with different descriptions (already observed in our data).

### 2. Character description temporal anchoring (LOW blast, spoiler-reinforcing)

BookRAG's spoiler contract already constrains `description` by chapter. Cognee's pattern of making the anchor **visible in the field itself** rather than only enforced by the schema makes the LLM less likely to drift across retries.

**Proposal:** Change the character example in the JSON schema from

```json
"description": "brief description based on this text",
```

to

```json
"description": "who this character is AS OF chapter {{ last_known_chapter }}, in one or two sentences",
```

and add a Self-Check bullet: *"Every description either mentions its `last_known_chapter` explicitly OR describes only state present in that chapter."*

**Risk:** Low. Reinforces an existing invariant; does not change extraction scope.

### 3. Entity consolidation pass — NEW prompt (MEDIUM blast)

`consolidate_entity_details.txt` is the most directly applicable Cognee prompt we haven't borrowed. It takes an entity, its neighbors, and the edges connecting them, and produces a consolidated description. BookRAG's eval already shows the problem this solves: the chat surfaces "Scrooge — a miserly old man" three times because three batches each produced their own Scrooge description.

**Proposal:** Add `prompts/consolidate_entity.txt` as a NEW prompt, run as a post-processing Task in `run_bookrag_pipeline` after `add_data_points`. For each `(type, name)` group with >1 snapshot within the same `last_known_chapter` bucket, merge descriptions into one. Preserve `first_chapter` as the min and `last_known_chapter` as the max across merged records.

**Risk:** Medium — adds LLM calls at ingestion time, and care is needed to NEVER merge snapshots across chapter bounds (a ch.5 Scrooge description must not bleed into the ch.1 reader's retrieval). Safe implementation: bucket first by `last_known_chapter`, consolidate within bucket, never across.

### 4. Multi-round relationship name discovery (MEDIUM-HIGH blast, optional)

Cognee's cascade approach first discovers `relationship_names` from the text (not from a fixed ontology), then re-grounds the actual triplet extraction against that discovered vocabulary. The benefit: the LLM does not invent `ate_breakfast_with` because it knows the relation vocabulary is a closed set.

**Proposal:** This one is a bigger architectural change — another pipeline stage between ontology discovery and batch extraction. We already do ontology discovery; extending it to include a relationship-name census is natural. Gate behind a config flag.

**Risk:** Medium-high. Adds a pipeline stage. The payoff is less relation-label drift across batches (which currently causes the same tie to land as `employs` in one batch and `is_employer_of` in another — we have seen both in our data).

### 5. Expand the relation-label rejection list (LOW blast)

Our existing list targets dialogue and motion verbs. Cognee's "exclude trivial, redundant, nonsensical triplets" generalizes the same concept; concrete bans worth adding:

- `is_a`, `has`, `relates_to`, `involves`, `concerns`, `mentions`, `appears_in` — these are container predicates that the typed schema already expresses.
- `thought` / `knew` / `remembered` — single-character mental actions, not relations.

**Proposal:** Extend the bullet list in "Relation Labels (CRITICAL)".

**Risk:** Minimal; tightens filtering.

### 6. Inline glossary for ontology relations (LOW blast)

Cognee's `generate_graph_prompt_oneshot.txt` includes one-shot examples for each structural rule. Our `{{ ontology_relations }}` placeholder today injects a bare list of relation names. A glossary format — `name: short definition` — reduces the chance the LLM applies the label inconsistently.

**Proposal:** Change the ontology discovery output format (and `_format_ontology_relations` in `pipeline/cognee_pipeline.py`) to produce lines like:

```
- employs: character A pays or hires character B as an employee
- is_rival_of: two characters hold opposing interests or are in active conflict
- warns: one character communicates a threat or caution about future events to another
- loves: romantic or kinship affection (not generic fondness)
```

**Risk:** Low. Requires a small code change to the ontology formatter. Improves precision.

### 7. Explicit "knowledge base doesn't answer that" rejection (LOW blast, answer-side)

Our current answer synthesis (`_complete_over_context` in `main.py`) already says "If the context does not contain the answer, say you don't know yet." Cognee's `answer_simple_question_restricted.txt` has a sharper version that locks the LLM into a specific fallback string: *"The provided knowledge base does not contain the answer."*

**Proposal:** Change our system prompt to include a fixed fallback sentence: *"If the sources don't answer the question, reply ONLY with: 'I don't have enough context from what you've read to answer that yet.' — do not speculate or guess."*

**Risk:** Low. Makes "don't know" answers consistent and flags them clearly to the UI. Can be rendered differently in the AssistantBubble if desired.

### 8. Quote-first framing for relationship extraction (LOW blast)

BookRAG already passes `{{ booknlp_quotes }}` to the LLM. Cognee's event-entity prompt leans harder on spoken content: "events are typically revealed through dialogue and observation". We can encourage the LLM to look at quotes FIRST when deciding whether two characters have a semantic tie.

**Proposal:** Add to "Semantic Content" section: *"When two characters share dialogue in the provided quotes, prefer extracting a semantic relationship (employs, warns, is_sibling_of) over a PlotEvent; dialogue is where relations are most explicitly revealed."*

**Risk:** Low. Nudges the LLM; doesn't prevent any existing extraction.

### 9. Temporal entity exclusion (LOW blast)

Cognee's event-entity prompt explicitly forbids dates, durations, and calendar references as standalone entities. Our extraction is already close to this but doesn't state the rule.

**Proposal:** Add to "What NOT to Do": *"Do NOT create standalone nodes for dates, times, durations, or seasons. Attach them as properties to events (e.g., a PlotEvent can describe 'Christmas Eve, 1843' in its description; Christmas Eve is NOT its own node)."*

**Risk:** Low. Prevents a class of noise nodes.

### 10. Description synonymy guidance for consolidation (LOW blast)

Cognee's `consolidate_entity_details.txt` instructs the LLM to "use synonym words to change wording" — prevents verbatim duplication of source text. When BookRAG extracts descriptions, the LLM sometimes emits near-verbatim sentences from the narration, which then fail our eval's entity_recall fuzz-match and look like plagiarism in the UI.

**Proposal:** Add to "Extraction Rules → General": *"Write descriptions in your own concise prose. Do NOT copy long phrases verbatim from the source text; paraphrase when the underlying meaning is clear."*

**Risk:** Low. Reduces surface-text leakage.

## Proposals NOT worth adopting

A few Cognee patterns we should explicitly decline:

- **"Quantity over filtering" event extraction** (`generate_event_graph_prompt.txt`). Cognee's default is to extract one event per verb. For BookRAG that would explode PlotEvent counts without improving answer quality, and would weaken the distinction between "things that happen" and "narrative surface" that our current `What NOT to Do` guidance protects.
- **One-shot examples embedded in the extraction prompt** (`generate_graph_prompt_oneshot.txt`). A concrete example is useful but Cognee's one-shot runs to hundreds of tokens and burns prompt budget. We already have a compact worked-example block in the Chapter Bounds section; a second one for relations would duplicate rather than add.
- **Multi-round iterative extraction with "Previously Extracted Entities" accumulation** (cascade prompts). Structurally more capable, but creates a per-batch conversation state that's harder to cache and test. Defer until we have evidence current single-pass extraction misses important entities.
- **Default `cognify()` + `memify()` orchestration**. Already a locked BookRAG decision (CLAUDE.md). These prompts rely on Cognee's generic ontology, not our domain-specific DataPoints.

## Proposed prioritization

Ship together as a single prompt revision:
- #1 Triplet validation — Self-Check addition
- #2 Temporal anchoring in character descriptions
- #5 Expand relation-label rejection list
- #8 Quote-first relationship framing
- #9 Temporal entity exclusion
- #10 Description synonymy guidance

These are all edits to `prompts/extraction_prompt.txt`, each under 100 words, with no architectural changes. Pinned with a few tests in `tests/test_extraction_prompt.py`. Ship one commit.

Ship separately as their own slices (each includes a design doc + tests + eval):
- #3 Entity consolidation pass — needs a new prompt file + a new post-extraction pipeline stage + a separate spec for the chapter-bucket guarantee.
- #6 Ontology relation glossary — code change to the ontology formatter plus a small prompt touch.

Defer indefinitely pending signal:
- #4 Multi-round relationship discovery — large. Revisit after extraction determinism is solved (the bigger unlock per the re-extraction summary).
- #7 Fixed fallback string for unanswerable queries — depends on whether we want the UI to treat "don't know" messages specially.

## Next concrete step

Implement the six-item combined prompt revision (#1/2/5/8/9/10) as one commit with accompanying tests. Re-run `scripts/reextract_book.py christmas_carol_e6ddcd76` to measure the change, then run the A/B eval (`BOOKRAG_USE_TRIPLETS=1`). That keeps all blast-low proposals together while deferring the architectural ones behind their own specs.
