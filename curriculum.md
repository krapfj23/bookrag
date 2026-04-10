# BookRAG Codebase Curriculum

A structured, module-by-module deep dive into the BookRAG spoiler-free ingestion pipeline. Each module includes context, a detailed explanation, design rationale, and a quiz question. Work through these in order — each builds on the last.

**How to use:** Read the explanation, then attempt the quiz question *without looking at the code*. If you get stuck, re-read the relevant section. Discuss your answer with Claude Code for feedback before moving on.

**Reference:** See `pedagogy.md` for learning strategies and self-assessment rubric.

---

## Module 0: The Big Picture

Before diving into individual modules, understand the full system.

### What BookRAG Does

BookRAG ingests EPUB novels and builds a knowledge graph that supports spoiler-free querying. A reader who's on chapter 3 can ask "Who is Scrooge's clerk?" and get an answer drawn only from chapters 1-3.

### The Two-Phase Architecture

**Phase 1 — Whole-Book NLP (runs once per book):**
Process the entire book through traditional NLP to extract characters, resolve pronouns, discover entity types, and build an ontology. This phase uses BookNLP (an academic NLP pipeline) and statistical methods (BERTopic, TF-IDF). No LLM calls.

**Phase 2 — Batched Knowledge Graph Construction (runs per batch of ~3 chapters):**
Feed resolved text + NLP annotations + the discovered ontology to Claude (via Cognee's LLMGateway), which extracts structured entities, relationships, and events. These are stored as DataPoints in a graph database (Kuzu) and vector database (LanceDB).

### Why Two Phases?

Phase 1 needs the full book for accurate coreference (pronouns resolved by seeing the whole document). Phase 2 is batched because LLM context windows and cost make processing the full book at once impractical. The ontology from Phase 1 *constrains* Phase 2 — Claude can only extract entity types that were already discovered, preventing hallucination.

### The Pipeline Stages (in execution order)

```
1. parse_epub        — Extract chapter-segmented text from EPUB file
2. run_booknlp       — Run NLP: entities, coreference clusters, quote attribution
3. resolve_coref     — Insert parenthetical annotations into text
4. discover_ontology — Auto-discover entity types and themes (BERTopic + TF-IDF + BookNLP)
5. review_ontology   — Optional interactive CLI review of discovered ontology
6. run_cognee_batches — Batch chapters, extract DataPoints via Claude, persist to graph/vector DB
7. validate          — Run known-answer tests against the completed graph
```

### Data Flow Diagram

```
EPUB file
  |
  v
[epub_parser] --> chapter_01.txt, chapter_02.txt, ..., full_text.txt
  |
  v
[booknlp_runner] --> .tokens, .entities, .quotes, .book (character profiles)
  |
  v
[coref_resolver] --> "he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"
  |
  v
[ontology_discovery] --> book_ontology.owl + discovered_entities.json
  |
  v
[cognee_pipeline] --> Character, Location, PlotEvent, Relationship, Theme DataPoints
  |                    stored in Kuzu (graph) + LanceDB (vectors)
  v
[validation] --> validation_results.json (structural + content + query checks)
```

### Key Files to Know

| File | Role |
|------|------|
| `pipeline/orchestrator.py` | Runs all 7 stages sequentially, manages state |
| `models/config.py` | Pydantic settings from config.yaml + env vars |
| `models/datapoints.py` | The 6 DataPoint types stored in the knowledge graph |
| `models/pipeline_state.py` | Crash-resume state tracking |
| `main.py` | FastAPI server (upload, status, progress endpoints) |
| `prompts/extraction_prompt.txt` | Jinja2 template for Claude's extraction instructions |
| `config.yaml` | All tunable parameters |
| `tests/conftest.py` | Shared test fixtures + Cognee mock |

### Quiz: Module 0

**Q: Why does BookRAG process the entire book in Phase 1 but only 3 chapters at a time in Phase 2? What would go wrong if you reversed this — batched Phase 1 and ran Phase 2 on the whole book?**

<details>
<summary>Key points to consider</summary>

- Coreference resolution needs full-book context (a pronoun in chapter 5 may refer to a character introduced in chapter 1)
- LLMs have context window limits and cost scales with input size
- The ontology discovered in Phase 1 constrains Phase 2 — it can't exist if Phase 1 is batched
- Running Phase 2 on the full book would mean one massive LLM call (expensive, unreliable, may exceed context)
</details>

---

## Phase 1: Whole-Book NLP

---

## Module 1: EPUB Parser

**File:** `pipeline/epub_parser.py` (~247 lines)
**Input:** An `.epub` file on disk
**Output:** `ParsedBook` dataclass containing chapter texts, full text with markers, and chapter boundary offsets

### Context: What Problem Does This Solve?

EPUBs are ZIP archives containing HTML files, CSS, images, and metadata. The reading order is defined by a "spine" — an ordered list of HTML documents. A novel's chapters typically correspond to separate spine items, but not always (some EPUBs pack everything into one HTML file, others split mid-chapter).

The parser's job is to extract clean plain text segmented by chapter, preserving reading order and paragraph structure while stripping all HTML formatting.

### How It Works

**Step 1 — Read the EPUB spine:**
Uses `ebooklib` to open the EPUB and iterate through spine items in reading order. Only processes items of type `ITEM_DOCUMENT` (skips images, CSS, fonts).

**Step 2 — Strip HTML from each spine item:**
A custom `_HTMLTextExtractor` (subclass of Python's `HTMLParser`) walks the HTML tree:
- Block-level tags (`<p>`, `<div>`, `<h1>`-`<h6>`, `<li>`, `<blockquote>`) insert newlines
- `<br>` becomes `\n`
- `<script>` and `<style>` content is skipped entirely (depth-tracked to handle nesting)
- Text content is accumulated into a buffer
- Post-processing: collapse per-line whitespace, normalize Unicode (non-breaking spaces, smart quotes)

**Step 3 — Filter content chapters:**
The `_is_content_chapter()` heuristic requires a spine item to have 50+ characters and 15+ words to qualify as a "chapter." This filters out cover pages, title pages, blank separators, and other non-content items.

**Step 4 — Assemble outputs:**
- `chapter_texts`: List of individual chapter strings
- `full_text`: All chapters joined with `=== CHAPTER N ===\n\n` markers
- `chapter_boundaries`: List of `(start_char, end_char)` tuples marking each chapter's position within `full_text`

**Step 5 — Save to disk:**
Writes `full_text.txt` and individual `chapters/chapter_01.txt`, `chapter_02.txt`, etc. to `data/processed/{book_id}/raw/`.

### Design Rationale

**Why one spine item = one chapter?** Most well-structured EPUBs follow this convention. Explicit chapter heading detection (regex for "Chapter 1", "STAVE ONE", etc.) is fragile across the vast variety of EPUB formatting. The spine-based approach works for the majority of commercial EPUBs.

**Why save both individual chapters AND full text?** BookNLP needs the full text as one document (for cross-chapter coreference). Downstream modules (batcher, validation) need individual chapters. Saving both avoids re-splitting later.

**Why character-level boundary tracking?** The coref resolver needs to map BookNLP's token offsets (which reference the full text) back to specific chapters. `chapter_boundaries` provides the character-level mapping to do this.

**Why the 50-char / 15-word content filter?** It's deliberately lenient. A stricter filter (e.g., 500+ words) would accidentally drop short chapters (like a one-paragraph epilogue). The current threshold only catches truly empty or metadata-only spine items.

### Key Details

- `_slugify()` converts filenames to URL-safe `book_id` values using NFKD Unicode normalization
- HTML encoding errors fall back to Latin-1 (handles old EPUBs with non-UTF-8 content)
- 3+ consecutive blank lines are collapsed to 2 (prevents runaway whitespace from messy HTML)
- `ignore_ncx=True` in ebooklib skips the NCX navigation file (would add noise)

### What Feeds Into the Next Module

The `full_text` string (with chapter markers) goes to the text cleaner. The `chapter_texts` list and `chapter_boundaries` are stored in the orchestrator's context for later use by the coref resolver and batcher.

### Quiz: Module 1

**Q: The EPUB parser uses a heuristic (50+ chars, 15+ words) to filter out non-content spine items. Imagine a book where the author writes a one-sentence, 40-character dedication: "For my mother, who taught me to dream." What would happen to this dedication in the current pipeline? Is this the right behavior? Why or why not?**

<details>
<summary>Key points to consider</summary>

- 40 characters < 50 threshold, so it would be filtered out
- A dedication is arguably not "content" for knowledge graph purposes (no characters, events, or relationships)
- But if the dedication contained a character name relevant to the story, losing it could matter
- The filter is a pragmatic trade-off: catch the common case (blank/metadata pages) at the cost of occasionally dropping very short content
</details>

---

## Module 2: Text Cleaner

**File:** `pipeline/text_cleaner.py` (~358 lines)
**Input:** Raw chapter texts from the EPUB parser
**Output:** Cleaned chapter texts with boilerplate removed and Unicode normalized

### Context: What Problem Does This Solve?

EPUB-extracted text carries residue from its HTML origins: encoded entities (`&amp;`), smart quotes (`\u201c`), page numbers from print layouts, copyright boilerplate, tables of contents, and inconsistent whitespace. These artifacts are noise for NLP models and LLMs. The cleaner strips them while preserving literary content like epigraphs and section breaks.

### How It Works (5 Cleaning Passes, In Order)

**Pass 1 — Character-level normalization (before line splitting):**
- Non-breaking spaces (`\u00a0`) → regular spaces
- Unicode smart quotes → ASCII (`"` and `'`)
- Em dashes → `--`, en dashes → `-`, ellipsis character → `...`
- HTML entity unescaping (`&lt;` → `<`, etc.) if `strip_html=True`

**Pass 2 — Epigraph protection (if `keep_epigraphs=True`):**
This is the cleverest part. Epigraphs (quoted text or attributed lines at the start of chapters) look like boilerplate to naive filters. The cleaner:
1. Scans the first 20 lines for epigraph patterns: quoted text (`"..."`, `'...'`) or attribution lines (`— Author Name`)
2. Replaces them with unique placeholders (`__EPIGRAPH_0__`, `__EPIGRAPH_1__`, etc.)
3. Runs all line-level cleaning passes (which would otherwise delete them)
4. Restores the originals from placeholders

**Pass 3 — Line-level removal:**
- **Page numbers:** Lines matching `^\s*\d{1,5}\s*$` (isolated numbers, 1-5 digits)
- **Copyright boilerplate:** 9 regex patterns covering "Copyright ©", "All rights reserved", ISBN, publisher info, "Library of Congress", "First edition", cover art credits
- **Table of contents:** Lines matching `chapter\s+[\dIVXLCivxlc]+[\s.:]*\d+` (e.g., "Chapter I    1"). Only removed when 2+ consecutive lines match — a single "Chapter I" is kept as a real chapter heading.

**Pass 4 — Section break handling (if `keep_section_breaks=False`):**
Replaces `***`, `---`, `===`, `~~~`, or 3+ consecutive dashes with a blank line.

**Pass 5 — Whitespace normalization:**
- Strip trailing spaces per line
- Collapse 3+ consecutive newlines to 2
- Final `strip()` + trailing newline

### Design Rationale

**Why normalize Unicode quotes to ASCII?** Consistency for downstream NLP. BookNLP and tokenizers handle ASCII quotes more reliably than the 6+ Unicode quote variants. The semantic content is unchanged.

**Why the epigraph protection dance?** Epigraphs are real literary content — they set tone, foreshadow themes, and sometimes contain character names. But they *look* like boilerplate (short, quoted, often with an author attribution that resembles copyright text). The placeholder strategy is the simplest way to protect them without making every cleaning regex epigraph-aware.

**Why the 2-consecutive-line TOC heuristic?** A single line like "Chapter I" is likely a real chapter heading within the text. But "Chapter I....1 / Chapter II....15 / Chapter III....32" is clearly a table of contents. The consecutive-line requirement distinguishes these cases.

**Why track `CleaningStats`?** Traceability. If downstream results look wrong, you can check: "Were 47 lines removed as copyright? That seems high — maybe the regex is too aggressive." The stats are logged and available for debugging.

### What Feeds Into the Next Module

Cleaned chapter texts are concatenated into a single string and passed to BookNLP. The cleaner doesn't change the chapter count or boundaries — it only modifies content within each chapter.

### Quiz: Module 2

**Q: The text cleaner has a specific order of operations: character-level normalization first, then epigraph protection, then line-level removal, then whitespace normalization. Why does the epigraph protection step need to happen *before* line-level removal but *after* character-level normalization? What would go wrong if you reordered these?**

<details>
<summary>Key points to consider</summary>

- If epigraph protection happened AFTER line-level removal, the copyright regex might delete an epigraph attribution line like "— Charles Dickens, 1843" (looks like a copyright line)
- If epigraph protection happened BEFORE character-level normalization, the regex matching epigraph patterns (looking for `"..."`) might fail on smart quotes (`\u201c...\u201d`) that haven't been normalized yet
- The ordering encodes a dependency: normalization enables pattern matching, protection must precede destructive removal
</details>

---

## Module 3: BookNLP Runner

**File:** `pipeline/booknlp_runner.py` (~519 lines)
**Input:** Full cleaned text (single string)
**Output:** `BookNLPOutput` dataclass containing characters, entities, quotes, tokens, and a coref-ID-to-name mapping

### Context: What Problem Does This Solve?

To build a knowledge graph, we need to know *who* is in the book, *what* they're called, *what* they say, and *which mentions refer to the same person*. BookNLP is an academic NLP pipeline specifically designed for fiction that provides all of this. It identifies named entities, clusters coreferent mentions (e.g., "Scrooge", "he", "the old miser" → same person), and attributes quoted speech to speakers.

### What BookNLP Produces (5 Output Files)

| File | Content | Used For |
|------|---------|----------|
| `.tokens` | Every token with POS tag, dependency relation, coref cluster ID, character offsets | Token-to-character mapping, sentence boundaries |
| `.entities` | Entity mentions with coref ID, token span, type (PER/LOC/etc.), form (PROP/NOM/PRON) | Who/what is mentioned, mapping to characters |
| `.quotes` | Quoted text with start/end tokens and attributed speaker (coref ID) | Dialogue extraction with attribution |
| `.book` | JSON array of character profiles: names (with counts), gender, actions, possessions, modifiers | Canonical names, character context |
| `.supersense` | WordNet semantic categories | Not used in current pipeline |

### How the Runner Works

**Step 1 — Execute BookNLP:**
Writes the full text to `input.txt`, instantiates the BookNLP model (configurable: "small" or "big"), and calls `model.process()` in a thread pool (BookNLP is CPU-bound; running it in a thread prevents blocking the async event loop).

**Step 2 — Parse output files:**
Each TSV file is parsed into typed dataclasses:

- **`TokenAnnotation`**: `token_id`, `text`, `lemma`, `pos`, `dep`, `coref_id`, `start_char`, `end_char`
- **`EntityMention`**: `coref_id`, `start_token`, `end_token`, `prop` (PROP/NOM/PRON), `cat` (PER/LOC/etc.), `text`
- **`QuoteAttribution`**: `text`, `speaker_coref_id`, `start_token`, `end_token`
- **`CharacterProfile`**: `coref_id`, `canonical_name`, `aliases`, `gender`, actions, modifiers, possessions

**Robust TSV parsing:** BookNLP's output format varies between versions. The parser tries multiple column name variants (e.g., `token_ID_within_document` OR `token_id`, `POS_tag` OR `pos`). Invalid rows are logged and skipped rather than crashing.

**Step 3 — Character name enrichment (two-pass):**

BookNLP's `.book` file sometimes produces placeholder names like `CHARACTER_5` when it can't confidently assign a canonical name. The enrichment fixes this:

- **Pass 1 (PROP mentions):** For each character with a placeholder name, find the most frequently occurring proper noun mention (e.g., "Scrooge" appears 42 times → use "Scrooge").
- **Pass 2 (NOM fallback):** For remaining placeholders, use the most frequent nominal mention that isn't a generic pronoun. Filter out "he", "she", "it", "they", "man", "person". Title-case the result (e.g., "the ghost" → "The Ghost").

**Step 4 — Character offset backfill:**
Tokens have precise character offsets (`byte_onset`/`byte_offset` in the original text). Entities and quotes only have token spans. The backfill maps token IDs to character offsets, giving every entity/quote precise positions in the original text.

### Design Rationale

**Why async execution with thread pool?** BookNLP is pure Python CPU work (no I/O to await). Running it in `asyncio.to_thread()` keeps the FastAPI event loop responsive during the ~30-60 second processing time.

**Why two-pass name enrichment instead of one?** Proper nouns are more reliable names than nominals. "Scrooge" is better than "The Miser." But some characters are only ever referred to by title or role ("The Ghost of Christmas Past" is never given a proper name in the text). The two-pass approach prefers proper nouns but doesn't leave characters unnamed.

**Why robust TSV parsing with fallback column names?** BookNLP is academic software with version-to-version format changes. The defensive parsing means the pipeline doesn't break when BookNLP updates its output format slightly.

### Key Detail: The coref_id_to_name Mapping

The runner builds a `dict[int, str]` mapping coref cluster IDs to canonical character names. This is the bridge that lets the coref resolver know that coref cluster 0 = "Scrooge", cluster 1 = "Bob Cratchit", etc. Every downstream module uses this mapping.

### What Feeds Into the Next Module

The `BookNLPOutput` — specifically `tokens`, `entities`, `characters`, and `coref_id_to_name` — feeds directly into the coref resolver. The `characters` and `entities` also feed into ontology discovery. The `.book` JSON provides character context for the extraction prompt in Phase 2.

### Quiz: Module 3

**Q: BookNLP assigns a `prop` field to each entity mention: PROP (proper noun like "Scrooge"), NOM (nominal like "the clerk"), or PRON (pronoun like "he"). Why does the pipeline's name enrichment filter out PRON mentions entirely and only consider PROP and NOM? What would happen if you included pronouns in the name enrichment logic?**

<details>
<summary>Key points to consider</summary>

- Pronouns ("he", "she", "it") are the most frequent mentions of any character but carry zero identity information
- If you counted pronouns, the "most frequent mention" for every male character would be "he" — making them all indistinguishable
- PROP mentions are identity-rich ("Scrooge", "Bob Cratchit"); NOM mentions are partially informative ("the clerk", "the ghost")
- The PROP-first, NOM-fallback strategy maximizes name quality while covering characters who lack proper nouns
</details>

---

## Module 4: Coreference Resolver

**File:** `pipeline/coref_resolver.py` (~692 lines)
**Input:** BookNLP tokens, entities, characters, chapter texts, chapter boundaries
**Output:** `CorefResult` with resolved chapter texts, cluster data, and a resolution log

### Context: What Problem Does This Solve?

BookNLP identifies which mentions refer to the same character (coreference clusters), but it does NOT produce resolved text. If the original text says "He muttered to his clerk," BookNLP knows "He" = Scrooge and "his clerk" = Bob Cratchit, but the text itself is unchanged. 

The coref resolver *inscribes* this knowledge into the text using a parenthetical format: `"He [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"`. This is the key innovation that makes Phase 2 work — Claude can read the annotated text and immediately know who every pronoun refers to.

### The Parenthetical Insertion Format

```
Original:  "He muttered to his clerk about the matter."
Resolved:  "He [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit] about the matter."
```

**Properties:**
- **Reversible:** Strip all `\s*\[[^\]]+\]` patterns → recover original text exactly
- **Claude-friendly:** LLMs parse bracketed annotations naturally
- **Non-destructive:** Original words are never modified, only appended to

### The Two Triggering Rules

Not every pronoun needs annotation. "He said" right after "Scrooge entered" is obvious. Annotation only fires when clarity is at risk:

**Rule 1 — Distance:** If the last mention of this character was `N+` sentences ago (default N=3), annotate. The reader (or LLM) may have lost track.

**Rule 2 — Ambiguity:** If 2+ characters have been mentioned within a sliding window of recent sentences (default window=2), annotate to clarify which character "he" or "she" refers to.

Both rules can fire simultaneously (logged as `rule_triggered = "both"`). Either rule alone is sufficient to trigger annotation.

### The Algorithm (Token-Walk)

The resolver walks through every token in reading order:

```
For each token:
  1. Emit whitespace gap since last token (preserving original spacing)
  2. Emit the token's word
  3. If this token STARTS a mention → record it
  4. If this token ENDS a mention:
     a. Look up the character's coref cluster
     b. Check distance rule: current_sentence - last_mention_sentence >= threshold?
     c. Check ambiguity rule: 2+ characters active in the sentence window?
     d. If either rule fires AND mention text ≠ alias → append " [AliasName]"
     e. Update last_mention_sentence for this character
  5. Accumulate into the current chapter's buffer
```

### Alias Selection (Shortest-Unique)

When annotating, the resolver picks the *shortest unambiguous* alias for each character. This avoids awkward multi-word annotations:

1. Collect all aliases per character (canonical name + variants from BookNLP)
2. Sort by length (shortest first)
3. For each candidate, check if it's unique across all characters in the book
4. Pick the shortest unique alias; fall back to canonical name if none are unique

Example: If "Bob" is unique to Bob Cratchit, use `[Bob]` instead of `[Bob Cratchit]`.

### Edge Cases Handled

| Edge Case | Handling |
|-----------|----------|
| PROP mentions ("Scrooge") | Never annotated — already clear |
| Character still named `CHARACTER_*` | Skipped (failed enrichment) |
| Mention text matches alias | Skipped — avoid "Scrooge [Scrooge]" |
| All-caps multi-word mentions | Skipped — likely headings ("STAVE ONE") |
| Generic pronoun as canonical name | Skipped — indicates failed enrichment |
| First mention of a character | Distance rule fires (infinite distance from "never seen") |

### Design Rationale

**Why parenthetical insertion instead of full text rewrite?** Reversibility. The original text is never lost. If coreference is wrong (BookNLP is ~70% accurate), the original can be recovered. Claude also handles the bracketed format well — it's a common annotation convention.

**Why two rules instead of one?** Distance alone misses: "Scrooge and Bob walked. He spoke." (distance=1, but "he" is ambiguous). Ambiguity alone misses: a pronoun 20 sentences after its last mention with no other characters around (unambiguous but reader forgot who "he" is).

**Why sentence-level tracking (not token-level)?** Sentences are the natural unit of reading comprehension. A pronoun 3 sentences away from its antecedent is harder to resolve than one 3 tokens away in the same sentence.

### Output Structure

```
coref/
  clusters.json          — Per-cluster: canonical_name, mention_count, resolution_count
  resolution_log.json    — Per-annotation: token_id, original_text, inserted_label, rule, sentence, chapter
resolved/
  full_text_resolved.txt — Complete annotated text
  chapters/
    chapter_01.txt       — Per-chapter annotated text
    chapter_02.txt
    ...
```

### What Feeds Into the Next Module

The `resolved_chapters` (annotated text) feed into ontology discovery (for BERTopic/TF-IDF analysis) and into Phase 2 (as the primary text input for Claude's extraction). The `clusters` data provides character information used in prompt rendering.

### Quiz: Module 4

**Q: Consider this passage: `"Scrooge looked at Marley's ghost. He was terrified. He spoke slowly."` With `distance_threshold=3` and `ambiguity_window=2`, which pronouns get annotated, and with which rule? Walk through the algorithm step by step.**

<details>
<summary>Key points to consider</summary>

- Sentence 0: "Scrooge" (coref 0) and "Marley" (coref 1) mentioned. Both clusters' last_mention updated to sentence 0.
- Sentence 1: "He" — distance from sentence 0 = 1 (below threshold 3). But ambiguity window [0,1] contains both Scrooge and Marley → ambiguity rule fires. Annotated as "He [Scrooge]" (or whichever BookNLP assigned).
- Sentence 2: "He" — distance from sentence 1 (if annotated as Scrooge) = 1 (below threshold). Ambiguity window [0,1,2] still contains both characters → ambiguity rule fires again.
- Key insight: The ambiguity window is the reason both pronouns get annotated, NOT the distance rule.
</details>

---

## Module 5: Ontology Discovery

**File:** `pipeline/ontology_discovery.py` (~476 lines)
**Input:** BookNLP output (characters, entities) + full text (optionally coref-resolved)
**Output:** `OntologyResult` containing discovered entities, themes, relations, and an OWL ontology file

### Context: What Problem Does This Solve?

When Claude extracts knowledge from text in Phase 2, it needs to know *what types of things to look for*. Without constraints, Claude might invent entity types that don't exist in the book or miss important ones. Ontology discovery analyzes the book's content and produces a formal vocabulary of entity types, relationships, and themes — an OWL (Web Ontology Language) file that constrains Phase 2 extraction.

Think of it as: "Before asking Claude to fill out a form, first figure out what fields the form should have."

### The Five Steps

**Step 1 — Entity type discovery (from BookNLP):**
Maps BookNLP entity categories to ontology classes:
- PER → Character
- LOC, FAC, GPE → Location
- VEH → Object
- ORG → Organization

Counts frequency per entity per class. Filters pronoun mentions (PRON) as noise.

**Step 2 — Theme discovery (BERTopic):**
Splits the full text into paragraphs (50+ chars each). Feeds them to BERTopic, which clusters paragraphs into latent topics. Each topic gets a label derived from its top keywords (e.g., `"betrayal_guilt_redemption"`). These become Theme classes in the ontology.

*Requires 10+ paragraphs to run. Logs a warning and returns empty themes if the corpus is too small.*

**Step 3 — Domain term extraction (TF-IDF):**
Runs TF-IDF (Term Frequency-Inverse Document Frequency) on text chunks to identify domain-specific vocabulary — words that are unusually important in *this* book compared to general English. Extracts unigrams and bigrams (single words and two-word phrases) with `min_df=2` (must appear in 2+ chunks) and `max_df=0.8` (can't appear in 80%+ of chunks, filtering out generic words).

**Step 4 — Relationship inference:**
Two sources:
- **BookNLP agent actions:** Verbs from character profiles (e.g., "employs", "haunts", "fears"). Top 50 by frequency.
- **TF-IDF relation verbs:** Checks extracted terms against a hardcoded vocabulary of relation-like verbs ("loves", "hates", "kills", "marries", "employs", etc.).

**Step 5 — OWL generation (RDFLib):**
Builds an RDF graph with:
- **Classes:** BookEntity (root) → Character, Location, Faction, Organization, Object, PlotEvent, Relationship, Theme + discovered theme subclasses
- **Individuals:** Each discovered entity as a named individual (e.g., `Bob_Cratchit` of type `Character`), filtered by `min_entity_frequency` (default: 2 mentions)
- **Object properties:** Each inferred relationship as an OWL property with label and evidence

Serialized as RDF/XML to `book_ontology.owl`.

### Design Rationale

**Why auto-discover instead of using a fixed ontology?** Every book has different entity types. A spy novel needs "Agency" and "Operation"; a fantasy novel needs "Kingdom" and "Spell". Auto-discovery adapts to the content. The base classes (Character, Location, etc.) are always present as a safety net.

**Why BERTopic for themes?** BERTopic finds latent thematic clusters without supervision. It doesn't require predefined categories — it discovers what the book is *about*. This is more robust than keyword lists for diverse genres.

**Why the hardcoded relation verb list?** TF-IDF finds important terms, but not all important terms are relationships. "counting-house" is important in A Christmas Carol but isn't a relationship. The verb list acts as a filter: only terms that match known relationship patterns become relation candidates.

**Why OWL format?** Cognee natively supports OWL ontologies. It can parse the file and use it to constrain extraction (tagging entities as `ontology_valid = True/False`). OWL is also a standard format readable by other tools.

**Why filter by `min_entity_frequency=2` during OWL build but not during discovery?** Discovery is comprehensive — capture everything. The OWL file is operational — only include entities mentioned enough times to matter. An entity mentioned once might be noise; mentioned twice suggests it's real.

### What Feeds Into the Next Module

The `OntologyResult` (and its OWL file) feeds into the optional ontology reviewer, and then directly into Phase 2's prompt rendering. The `ontology_classes` and `ontology_relations` are injected into the Jinja2 extraction prompt, telling Claude exactly what types and relationships it's allowed to extract.

### Quiz: Module 5

**Q: Ontology discovery uses two different statistical methods — BERTopic and TF-IDF — for seemingly related tasks (understanding the book's content). Why use both? What does each capture that the other misses?**

<details>
<summary>Key points to consider</summary>

- BERTopic clusters paragraphs by semantic similarity — it finds THEMES (abstract concepts like "redemption", "isolation")
- TF-IDF finds important TERMS (specific words/phrases like "counting-house", "workhouse")
- BERTopic is contextual (understands that "cold heart" and "frozen soul" relate to the same theme); TF-IDF is lexical (treats them as different terms)
- TF-IDF captures domain-specific vocabulary that may not cluster into coherent topics
- Together they cover both the thematic structure (what the book is about) and the domain vocabulary (the specific words the book uses)
</details>

---

## Module 6: Ontology Reviewer

**File:** `pipeline/ontology_reviewer.py` (~307 lines)
**Input:** `OntologyResult` from discovery
**Output:** Potentially modified `OntologyResult` + `review_snapshot.json` audit trail

### Context: What Problem Does This Solve?

Auto-discovered ontologies aren't perfect. BERTopic might produce a nonsensical theme, or the entity type inference might miss an important category. The reviewer provides an optional human-in-the-loop checkpoint before Phase 2 extraction begins.

### How It Works

If `auto_review=True` in config (default: False), the reviewer is skipped entirely — all discoveries are accepted as-is.

In interactive mode:
1. **Display** all discovered entities (by type, with instance counts), themes (with top keywords), and relations (with source and evidence)
2. **Prompt:** "Accept all without changes?"
3. **If editing:** Offer to add/remove/rename entity types, remove themes, add/remove relations
4. **Rebuild OWL** if any changes were made
5. **Save** a `review_snapshot.json` recording what was accepted/changed and whether review was interactive or auto

### Design Rationale

**Why optional?** For automated pipelines (API-driven uploads), manual review isn't feasible. `auto_review=False` (the default) means the review step is a no-op. Interactive review is for when a human is running the pipeline locally and wants control.

**Why rich library with fallback?** The `rich` library makes beautiful terminal tables, but it's a heavy dependency. The reviewer works without it (plain `print`/`input`), ensuring the pipeline runs in minimal environments.

**Why an audit trail (review_snapshot.json)?** If extraction quality is poor in Phase 2, you can check: "Was the ontology reviewed? Were important types removed?" This supports debugging and reproducibility.

### Quiz: Module 6

**Q: The ontology reviewer is set to `auto_review=False` by default, meaning it's a no-op in the pipeline. Why would the architect include a no-op stage in the pipeline rather than just conditionally skipping it in the orchestrator? What benefit does the stage existing (even as a no-op) provide?**

<details>
<summary>Key points to consider</summary>

- The stage always exists in the pipeline sequence, which means crash-resume state tracking includes it
- A no-op stage that saves a review_snapshot.json (with "review_mode: auto") creates an audit trail even when no review happens
- It's a placeholder for future automation (e.g., an LLM-based ontology review)
- The orchestrator doesn't need conditional logic — every pipeline run has the same stages, just with different behavior
</details>

---

## Phase 2: Batched Knowledge Graph Construction

---

## Module 7: DataPoint Models

**File:** `models/datapoints.py` (~250 lines)
**Input:** N/A (schema definitions)
**Output:** N/A (used by cognee_pipeline.py and validation)

### Context: What Problem Does This Solve?

The knowledge graph needs a schema — what types of nodes and edges exist, what fields they have, and how they relate. DataPoint models define this schema as Pydantic classes that Cognee can store in Kuzu (graph DB) and LanceDB (vector DB).

### The Six DataPoint Types

| Type | Represents | Key Fields | Relations |
|------|-----------|------------|-----------|
| **Character** | A person in the book | `name`, `aliases`, `description`, `first_chapter`, `chapters_present` | None |
| **Location** | A place | `name`, `description`, `first_chapter` | None |
| **Faction** | A group/organization | `name`, `description`, `first_chapter`, `members` | `members: list[Character]` |
| **PlotEvent** | Something that happens | `description`, `chapter`, `participants`, `location` | `participants: list[Character]`, `location: Location` |
| **Relationship** | A connection between characters | `source`, `target`, `relation_type`, `description`, `first_chapter` | `source: Character`, `target: Character` |
| **Theme** | A thematic element | `name`, `description`, `first_chapter`, `related_characters` | `related_characters: list[Character]` |

### The Two-Layer Architecture

**Layer 1 — Extraction models (flat, LLM-friendly):**
These are plain Pydantic BaseModel classes that match the JSON schema in the extraction prompt. They use string references: `source_name: str`, `participant_names: list[str]`, `location_name: str`.

**Layer 2 — DataPoint models (relational, graph-friendly):**
These inherit from Cognee's `DataPoint` class and use actual object references: `source: Character`, `participants: list[Character]`. They're what gets stored in the graph.

**The bridge:** `ExtractionResult.to_datapoints()` converts Layer 1 → Layer 2 by:
1. Creating all Character and Location DataPoints first, building lookup maps (`char_map`, `loc_map`)
2. Creating Faction, PlotEvent, Relationship, Theme DataPoints, resolving string names to actual objects via the maps
3. Skipping any reference that can't be resolved (graceful degradation)

### Design Rationale

**Why two layers instead of having the LLM output DataPoints directly?** LLMs work better with flat JSON. Asking Claude to output nested objects with UUIDs and cross-references would increase hallucination and reduce extraction quality. The flat → relational conversion is deterministic and reliable.

**Why UUID5 (deterministic) instead of UUID4 (random)?** Same entity name → same UUID across pipeline runs. This enables idempotent re-processing: if you re-run Phase 2, the same "Scrooge" character gets the same ID, allowing upsert instead of duplication.

**Why `index_fields` in metadata?** Controls which fields get embedded in the vector database. `name` and `description` are embedded (for semantic search); `first_chapter` and `aliases` are not (they're structured data for filtering, not semantic content).

**Why `chapters_present` on Character but not on Location?** Characters move through the story — tracking which chapters they appear in enables precise spoiler filtering. Locations are typically mentioned throughout and don't have the same chapter-sensitivity.

### What Feeds Into the Next Module

These models define the extraction target for `cognee_pipeline.py`. The `ExtractionResult` is the `response_model` passed to Claude via LLMGateway. The resulting DataPoints are persisted to Kuzu + LanceDB and later validated by the validation suite.

### Quiz: Module 7

**Q: The `to_datapoints()` conversion uses UUID5 with seed strings like `f"character:{c.name}"` and `f"rel:{source_name}:{relation_type}:{target_name}"`. Why include the entity type prefix ("character:", "rel:") in the seed? What would happen if two different entity types had the same name (e.g., a Character named "London" and a Location named "London")?**

<details>
<summary>Key points to consider</summary>

- Without the prefix, UUID5("London") would produce the same ID for both the Character and Location
- With the prefix, UUID5("character:London") ≠ UUID5("location:London") — different IDs, different nodes in the graph
- This is a namespace collision prevention strategy
- Relationships include both endpoints AND the relation type in the seed, preventing: "Scrooge employs Bob" and "Scrooge fears Bob" from colliding
</details>

---

## Module 8: Batcher

**File:** `pipeline/batcher.py` (~205 lines)
**Input:** List of chapter texts + chapter numbers
**Output:** List of `Batch` objects (groups of chapters)

### Context: What Problem Does This Solve?

Phase 2 can't process the entire book at once (LLM context limits, cost). The batcher groups chapters into manageable batches. The default is 3 chapters per batch — small enough for reliable LLM extraction, large enough to capture cross-chapter relationships.

### Two Strategies

**FixedSizeBatcher (default):**
Groups exactly `batch_size` chapters per batch. The last batch may be smaller.
```
5 chapters, batch_size=3 → [ch1,ch2,ch3] + [ch4,ch5]
```

**TokenBudgetBatcher (alternative):**
Groups chapters until accumulated tokens reach `max_tokens`. Token estimate: `len(text) // 4` (rough chars-to-tokens conversion). A single chapter that exceeds the budget gets its own batch.

### The Batch Object

```python
@dataclass
class Batch:
    chapter_numbers: list[int]   # e.g., [1, 2, 3]
    texts: list[str]             # Individual chapter texts
    combined_text: str           # Chapters joined by "\n\n"
    
    @property
    def word_count(self) -> int  # Whitespace-split word count
```

### Design Rationale

**Why consecutive chapters only?** Cross-chapter relationships (a character introduced in chapter 1 referenced in chapter 2) are captured within a batch. Non-consecutive batching would miss these local relationships and confuse the LLM.

**Why `batch_size=3` default?** Empirical trade-off. 1 chapter = too little context for relationship extraction. 5+ chapters = approaching LLM context limits for long novels. 3 is the sweet spot for most fiction.

**Why a pluggable interface (ABC)?** Different books have different chapter lengths. A 2000-word chapter and a 15000-word chapter shouldn't be in the same batch size. The `TokenBudgetBatcher` handles this, and future strategies (e.g., semantic-similarity-based batching) can be added without changing the orchestrator.

### Quiz: Module 8

**Q: The FixedSizeBatcher groups by chapter count (3 per batch), while the TokenBudgetBatcher groups by estimated token count. For a book where chapter 1 is 500 words and chapter 2 is 15,000 words, how would each batcher handle this differently? Which produces better results for LLM extraction, and why?**

<details>
<summary>Key points to consider</summary>

- FixedSizeBatcher: [ch1(500w), ch2(15000w), ch3(?)] — batch could be 15,500+ words, potentially exceeding useful LLM context
- TokenBudgetBatcher: ch2 alone might exceed the token budget → gets its own batch; ch1 groups with ch3+
- TokenBudgetBatcher produces more consistent input sizes, which means more consistent extraction quality
- But: it breaks chapter consecutiveness (ch1 with ch3, skipping ch2), which could miss ch1→ch2 relationships
- Actually, TokenBudgetBatcher is still consecutive — ch2 just gets its own batch: [ch1], [ch2], [ch3+]
</details>

---

## Module 9: Cognee Pipeline

**File:** `pipeline/cognee_pipeline.py` (~513 lines)
**Input:** A batch of chapters + BookNLP annotations + ontology + extraction prompt template
**Output:** List of DataPoints persisted to Kuzu + LanceDB

### Context: What Problem Does This Solve?

This is where everything comes together. The Cognee pipeline takes the resolved text, the NLP annotations from Phase 1, and the discovered ontology, and uses Claude to extract structured knowledge (DataPoints) from the text. It's the core of Phase 2.

### The Three Stages

**Stage 1 — `chunk_with_chapter_awareness()`:**
Splits a batch's combined text into chunks that respect paragraph boundaries. Greedily accumulates paragraphs until reaching `chunk_size * 4` characters (the `* 4` converts from token estimate to character estimate). Never splits mid-paragraph. Each chunk is tagged with the batch's chapter numbers.

**Stage 2 — `extract_enriched_graph()`:**
For each chunk:
1. **Render the prompt:** Jinja2 template filled with ontology classes, ontology relations, BookNLP entities (filtered to PROP/NOM, capped at 50), BookNLP quotes (capped at 30, truncated to 120 chars), and chapter numbers. The actual text is sent separately (not embedded in the system prompt).
2. **Call Claude:** `LLMGateway.acreate_structured_output(text_input, system_prompt, response_model=ExtractionResult)`. Claude returns structured JSON validated against the Pydantic model.
3. **Convert to DataPoints:** `ExtractionResult.to_datapoints()` resolves string references to object references.
4. **Retry on failure:** Up to 3 attempts with exponential backoff (`2^attempt` seconds).

**Stage 3 — Persistence + Artifacts:**
- DataPoints are persisted via Cognee's `run_pipeline()` with the `add_data_points` task (batch_size=30)
- Three artifact files saved per batch:
  - `input_text.txt` — The raw text that was sent to Claude
  - `annotations.json` — The BookNLP entities/quotes used as context
  - `extracted_datapoints.json` — The extracted DataPoints as JSON

### The Extraction Prompt (prompts/extraction_prompt.txt)

The prompt is carefully structured to prevent hallucination:

1. **Role:** "Expert literary analyst building a knowledge graph"
2. **Ontology constraints:** "Only extract these entity types: {{ ontology_classes }}"
3. **BookNLP cheat sheet:** "These are known entities and attributed quotes"
4. **Chapter context:** "You are extracting from chapters {{ chapter_numbers }}. Every entity needs a chapter number."
5. **Rules:** Extract only explicit content; no inference; no prior knowledge; use canonical [bracketed] names
6. **Output schema:** Exact JSON structure matching `ExtractionResult`

The key design: Claude's system prompt gets the constraints and context; the user message gets the actual text. This separation follows LLM best practices (system prompt for instructions, user message for content).

### Design Rationale

**Why chunk within a batch?** Even a 3-chapter batch can be too large for a single LLM call. Chunking by paragraph ensures each call is within context limits while maintaining coherent text (no mid-sentence splits).

**Why cap BookNLP entities at 50 and quotes at 30?** The extraction prompt has limited space. Including 500 entity mentions would bloat the prompt and distract Claude. The caps prioritize the most relevant annotations.

**Why save artifacts to disk?** Debugging. If Claude extracts something wrong, you can inspect: "What text did it see? What annotations were provided? What did it actually output?" This is the traceability principle from the architecture doc.

**Why separate system prompt and text input?** LLMGateway (and most LLM APIs) distinguish between system instructions and user content. Mixing them reduces instruction-following quality. The `{{ text }}` placeholder in the template is replaced with a redirect message; the actual text goes in `text_input`.

### What Feeds Into the Next Module

The extracted DataPoints (now in Kuzu + LanceDB) are the completed knowledge graph. They feed into the validation stage, and eventually into the query system (not yet built) that answers reader questions with spoiler filtering.

### Quiz: Module 9

**Q: The extraction prompt includes both ontology constraints ("only extract these entity types") AND BookNLP annotations ("these are known entities"). These seem redundant — if BookNLP already found the entities, why does Claude need to re-extract them? What does Claude add that BookNLP can't provide?**

<details>
<summary>Key points to consider</summary>

- BookNLP finds MENTIONS (surface-level: "Scrooge is at the counting-house"); Claude extracts MEANING (semantic: "Scrooge works at the counting-house" → employs relationship, Location entity)
- BookNLP can't extract: relationships, themes, plot events, factions, or descriptions
- BookNLP provides the "cheat sheet" so Claude doesn't have to re-discover who the characters are — it can focus on deeper extraction
- The ontology constrains Claude's output types; BookNLP grounds Claude's entity recognition. Together they prevent hallucination while enabling deep extraction
- This is the "double extraction" strategy: BookNLP for breadth (who/what exists), Claude for depth (what it means)
</details>

---

## Infrastructure

---

## Module 10: Orchestrator & Pipeline State

**File:** `pipeline/orchestrator.py` (~700 lines), `models/pipeline_state.py` (~138 lines)
**Input:** A book_id and EPUB path
**Output:** A fully processed book (all stages complete) with state tracking

### Context: What Problem Does This Solve?

The pipeline has 7 stages, each taking seconds to minutes. If it crashes at stage 5, you don't want to re-run stages 1-4. The orchestrator manages sequential execution with crash-resume: it persists state after each stage, and on restart, skips completed stages.

### How the Orchestrator Works

**Launching:** `run_in_background(book_id, epub_path)` starts a daemon thread. The thread runs `_run_pipeline()`, which executes stages sequentially:

```python
for stage_name, stage_fn in STAGES:
    if state.stages[stage_name].status == "complete":
        continue  # Skip completed stages (crash-resume)
    state.stages[stage_name].status = "running"
    _persist(state)
    try:
        stage_fn(ctx, state)
        state.stages[stage_name].status = "complete"
    except Exception as e:
        state.stages[stage_name].status = "failed"
        state.stages[stage_name].error = str(e)
        state.status = "failed"
        _persist(state)
        return
    _persist(state)
```

**Shared context:** A `ctx: dict` is passed through all stages. Each stage reads inputs from `ctx` and writes outputs to `ctx`. For example, `_stage_parse_epub` writes `ctx["parsed_book"]`; `_stage_run_booknlp` reads it and writes `ctx["booknlp_output"]`.

### Pipeline State Persistence

**`PipelineState`** tracks:
- `status`: "pending" | "processing" | "complete" | "failed"
- `stages`: dict mapping each stage name → `StageStatus` (status, duration, error)
- `current_batch` / `total_batches`: Progress within the batched stage
- `ready_for_query`: True only after full successful completion

**Thread-safe I/O:**
- Module-level `threading.Lock()` protects all file access
- Atomic writes: save to `.json.tmp`, then rename to `.json` (prevents corruption if crash happens mid-write)
- Error sanitization: API responses get last-line-only errors (no stack traces or file paths)

### Resume Logic

On startup, `_init_or_resume_state()`:
1. If `pipeline_state.json` exists → load it
2. If status is "complete" → reset for reprocessing
3. If status is "failed" or "processing" → resume from the failed/interrupted stage
4. If no file → create fresh state with all stages "pending"

Each stage also has internal resume checks. For example, `_stage_run_booknlp` checks if BookNLP output files already exist on disk before running the expensive NLP processing again.

### Design Rationale

**Why daemon threads instead of Celery/task queues?** This is a single-user, local application (M4 Pro Mac). Celery requires Redis/RabbitMQ infrastructure. A daemon thread is the simplest thing that works. The architecture doc explicitly locks this decision.

**Why atomic file writes?** A crash during `json.dump()` could produce a corrupt half-written JSON file. Writing to `.tmp` first and renaming is atomic on most filesystems — the state file is always either the old valid version or the new valid version, never corrupt.

**Why sanitize errors for API but keep full errors on disk?** The API serves a frontend that shouldn't display internal file paths or stack traces (security). But the developer debugging a failure needs the full traceback (available in `pipeline_state.json` on disk and in log files).

**Why a shared `ctx` dict instead of explicit function parameters?** The stages have varying input/output signatures. A dict is flexible — stages can add new keys without changing the orchestrator's interface. The trade-off is less type safety, but the pipeline is simple enough that this works.

### Quiz: Module 10

**Q: The orchestrator persists state BOTH before a stage runs (status="running") and after it completes (status="complete"). Why persist the "running" state? If the pipeline crashes, how does the resume logic distinguish between "this stage was running when we crashed" vs "this stage failed cleanly"?**

<details>
<summary>Key points to consider</summary>

- If we only persisted after completion, a crash mid-stage would leave the state showing "pending" — and resume would try to run the stage again, which is correct
- But persisting "running" before the stage gives real-time progress visibility (the API can show "currently running stage X")
- On resume: "running" status = the stage was interrupted (crashed). "failed" status = the stage ran to completion but threw an exception. Both are retried.
- The distinction matters for logging/debugging: "running" on resume means unexpected crash; "failed" means a handled error
</details>

---

## Module 11: FastAPI & Configuration

**File:** `main.py` (~225+ lines), `models/config.py` (~101 lines), `config.yaml`
**Input:** HTTP requests (upload, status, progress)
**Output:** HTTP responses (book_id, pipeline state, validation results)

### Context: What Problem Does This Solve?

The FastAPI server is the entry point for the entire system. It accepts EPUB uploads, launches the pipeline, and provides status/progress endpoints for a future frontend. The config system provides a single source of truth for all tunable parameters.

### FastAPI Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/books/upload` | Upload an EPUB, start the pipeline |
| `GET` | `/books/{book_id}/status` | Poll pipeline progress |
| `GET` | `/books/{book_id}/validation` | Get validation results |
| `POST` | `/books/{book_id}/progress` | Report reader's current chapter |
| `GET` | `/health` | Health check |

### Upload Flow (the interesting one)

1. **Validate file:** Check `.epub` extension, verify size ≤ 500MB, check ZIP magic bytes (`PK\x03\x04`)
2. **Enforce concurrency:** Max 5 concurrent pipelines (checks `orchestrator._threads` for alive threads)
3. **Generate book_id:** Sanitize filename + append 8 random hex chars (e.g., `christmas_carol_a1b2c3d4`)
4. **Save EPUB** to `data/books/{book_id}.epub`
5. **Launch pipeline:** `orchestrator.run_in_background(book_id, epub_path)` → returns immediately
6. **Return:** `{"book_id": "...", "message": "Pipeline started"}`

### Configuration (Pydantic Settings)

**Priority:** Environment variables (`BOOKRAG_*` prefix) > YAML file values > field defaults

```python
class BookRAGConfig(BaseSettings):
    batch_size: int = 3
    distance_threshold: int = 3
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    # ... 15+ more fields
    
    model_config = {"env_prefix": "BOOKRAG_", "env_nested_delimiter": "__"}
```

**Why this layering?** YAML for project-level defaults that get committed to git. Environment variables for machine-specific overrides (API keys, model selection) that should NOT be committed. Pydantic field defaults as the ultimate fallback.

### Design Rationale

**Why no authentication?** The architecture doc locks this: single user, local machine, trusted network. Adding auth would be premature complexity.

**Why magic bytes validation instead of full EPUB parsing?** Speed. Checking the first 4 bytes (`PK\x03\x04` = ZIP header) catches the most common error (uploading a non-EPUB file) without the overhead of parsing the entire archive. Full validation happens when `epub_parser` runs.

**Why 500MB limit?** EPUBs are typically 0.5-5MB. 500MB is generous enough for any real book but prevents accidental upload of large non-book files. The limit is enforced by reading up to `MAX_UPLOAD_BYTES + 1` — if the extra byte exists, the file is too large.

**Why `_sanitize_filename()`?** Path traversal prevention. A malicious filename like `../../etc/passwd.epub` would escape the data directory. The sanitizer strips everything except alphanumeric characters and underscores.

### Quiz: Module 11

**Q: The upload endpoint generates a book_id by combining a sanitized filename with 8 random hex characters (e.g., `christmas_carol_a1b2c3d4`). Why include randomness instead of just using the sanitized filename? What problem would arise if two users uploaded files with the same name?**

<details>
<summary>Key points to consider</summary>

- Without randomness, uploading "christmas_carol.epub" twice would produce the same book_id
- The second upload would overwrite the first's EPUB file and collide with its pipeline state
- The orchestrator checks "is a pipeline already running for this book_id?" — same ID would either be rejected or cause state corruption
- Even in single-user mode, the user might upload the same book with different content (different edition, different annotations)
- The random suffix guarantees uniqueness without requiring a database of existing IDs
</details>

---

## Module 12: The Test Suite

**File:** `tests/conftest.py` (~200+ lines), 18 test files (~10,166 lines total)
**Not a pipeline module — but essential for understanding the system**

### Context: Why Study the Tests?

The test suite is the most concrete documentation of what every module *actually does*. It contains realistic fixtures (Christmas Carol data), edge case inventories, and behavioral specifications. If the code tells you *how*, the tests tell you *what* and *what if*.

### The Cognee Mock (conftest.py)

Cognee is a heavy dependency that may not be installed locally. The conftest solves this with a **pre-import mock**:

```python
# Executed at module load time, BEFORE any test imports datapoints.py
def _install_cognee_mock():
    mock_datapoint = type("DataPoint", (BaseModel,), {"id": Field(default_factory=uuid4)})
    sys.modules["cognee.infrastructure.engine"] = MockModule(DataPoint=mock_datapoint)
    sys.modules["cognee.infrastructure.llm"] = MockModule(LLMGateway=MagicMock())
    # ... more mocked submodules
```

This works because Python's import system checks `sys.modules` before loading from disk. By injecting fake modules, any subsequent `from cognee.infrastructure.engine import DataPoint` gets the mock.

### Christmas Carol Fixtures

Three fixtures model *A Christmas Carol* realistically:

1. **`christmas_carol_book_json()`** — BookNLP `.book` output with 4 characters (Scrooge, Bob Cratchit, Marley, Tiny Tim), complete with name variants, gender, actions, possessions
2. **`christmas_carol_entities_tsv()`** — 13 entity mention rows covering characters + locations + edge cases (empty fields)
3. **`christmas_carol_text()`** — 20 paragraphs of resolved text with parenthetical coref annotations

These fixtures are used across multiple test files, providing consistent test data.

### Testing Patterns Used

| Pattern | Example | Why |
|---------|---------|-----|
| **Fixture-driven** | Christmas Carol data shared across files | Consistent, realistic test data |
| **Parametrized config** | CorefConfig with different thresholds | Test behavior under varying settings |
| **Property-based invariants** | "No text lost during chunking" | Catches unexpected edge cases |
| **Edge case enumeration** | Empty inputs, missing fields, single tokens | Proves robustness |
| **File I/O specification** | Exact directory names, JSON schemas | Ensures output matches architecture docs |
| **Async testing** | `AsyncMock` for LLMGateway calls | Tests async pipeline without real API calls |
| **Graceful degradation** | All retries fail → returns `[]` | Proves failure handling works |

### Test Coverage by Pipeline Stage

| Stage | Test File(s) | Key Tests |
|-------|-------------|-----------|
| EPUB parsing | `test_epub_parser.py` | HTML stripping, chapter detection, content filtering |
| Text cleaning | `test_text_cleaner.py` | Each cleaning pass, epigraph protection, stats tracking |
| BookNLP | `test_booknlp_runner.py` | TSV parsing, name enrichment (PROP/NOM), character offset backfill |
| Coref resolution | `test_coref_resolver.py`, `test_coref_quality.py` | Distance rule, ambiguity rule, alias selection, text reconstruction, Christmas Carol regression |
| Ontology | `test_ontology_discovery.py`, `test_ontology_reviewer.py` | BERTopic integration, TF-IDF terms, OWL generation, CLI review flow |
| DataPoints | `test_datapoints.py` | All 6 types, to_datapoints() conversion, UUID determinism |
| Batcher | `test_batcher.py` | Fixed-size grouping, token-budget grouping, word counting |
| Cognee pipeline | `test_cognee_pipeline.py` | Chunking, prompt rendering, LLM extraction (mocked), artifact saving |
| Orchestrator | `test_orchestrator.py` | Stage sequencing, crash-resume, progress tracking |
| Config | `test_config.py` | YAML loading, env var overrides, defaults |
| FastAPI | `test_main.py` | Upload validation, status endpoint, health check |
| Prompts | `test_extraction_prompt.py` | Jinja2 template rendering, variable injection |
| Validation | `test_validation.py`, `test_quality_control.py` | Structural checks, content assertions, known-answer queries |

### Quiz: Module 12

**Q: The Cognee mock in conftest.py installs fake modules into `sys.modules` at import time, before any tests run. Why is this necessary? What would happen if the tests simply used `unittest.mock.patch` to mock Cognee imports in each test function instead?**

<details>
<summary>Key points to consider</summary>

- `models/datapoints.py` has `from cognee.infrastructure.engine import DataPoint` at the TOP of the file (module-level import)
- Module-level imports execute when the file is FIRST imported, not when a function is called
- `unittest.mock.patch` decorates test functions — by the time the test function runs, the import has already happened (and failed)
- The sys.modules trick works because it intercepts the import mechanism itself, before Python tries to find cognee on disk
- This is a pattern for testing code that depends on optional/heavy packages not installed in the test environment
</details>

---

## Final Assessment

After completing all 12 modules, you should be able to:

1. **Trace a book from upload to knowledge graph** — describe every transformation the data undergoes
2. **Explain the two-phase architecture** — why Phase 1 is whole-book and Phase 2 is batched
3. **Describe the parenthetical coref format** — how it works, why it was chosen, what rules trigger it
4. **Explain the ontology's role** — how it's discovered, what it constrains, why it prevents hallucination
5. **Describe the DataPoint schema** — all 6 types, the two-layer extraction architecture, UUID determinism
6. **Explain crash-resume** — how state is persisted, how stages are skipped, why atomic writes matter
7. **Articulate design trade-offs** — for each module, name the alternatives considered and why they were rejected

### Suggested Next Steps

- **Run the tests:** `python -m pytest tests/ -v --tb=short` and read the output
- **Inspect real artifacts:** Run `run_christmas_carol.py` and examine the files in `data/processed/`
- **Read the architecture doc:** `bookrag_pipeline_plan.md` has the full decision log
- **Read the deep research:** `bookrag_deep_research_context.md` for Cognee internals and BookNLP schemas
- **Trace the extraction prompt:** Read `prompts/extraction_prompt.txt` alongside `cognee_pipeline.py`
