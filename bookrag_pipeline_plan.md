# BookRAG: Upload & Ingestion Pipeline Plan

## Project Overview

BookRAG is a spoiler-free AI chatbot for literature that ingests books, builds a knowledge graph, and answers queries constrained by the user's reading progress. This document covers the architecture and implementation plan for the **upload and ingestion pipeline** — everything from EPUB upload to a queryable knowledge graph in Cognee.

**Test book:** A Christmas Carol by Charles Dickens (~28k words, 5 chapters, public domain)
**Validation book:** Red Rising by Pierce Brown (~100k words, ~45 chapters)

---

## Architecture Summary

The pipeline has two distinct phases:

**Phase 1 — Whole-Book NLP (runs once per book)**
Parse the EPUB, run BookNLP on the full text to extract entities, coreference clusters, quotation attribution, and events. Resolve coreferences into annotated text using parenthetical insertion. Discover an ontology from BookNLP's structured output. Optionally review the ontology via CLI.

**Phase 2 — Batched Knowledge Graph Construction (runs per batch)**
Segment the coref-resolved text by chapter, batch into groups of ~3 chapters, and feed each batch into a custom Cognee pipeline. The pipeline calls Claude (via Cognee's LLMGateway) with both the resolved text and BookNLP's structured annotations as context, constrained by the discovered ontology. Extracted entities become custom DataPoints with chapter metadata, stored in Cognee's graph and vector databases.

---

## Decision Log

### Infrastructure

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File format | EPUBs only | MVP scope; PDFs and plain text deferred |
| EPUB parsing | ebooklib (Python) | Server-side, handles EPUB2/3, no JS needed for API-only MVP |
| Web framework | FastAPI | Async-native, pairs well with Cognee's async API |
| Package manager | uv | Fast dependency resolution, modern toolchain |
| Logging | loguru | Zero-config, nice formatting |
| Config | .env for secrets + YAML for settings | Separation of concerns |
| Storage backend | Cognee defaults (Kuzu + LanceDB + SQLite) | Zero setup, swap to Neo4j later via config |
| Pipeline execution | Simple background threads | Lighter weight than Celery for single-user local |
| Interface | API-only (curl/Postman) | No frontend for MVP |
| Users | Single user, local (M4 Pro Mac) | No auth, no user scoping |
| Python version | Whatever BookNLP requires (3.9+) | BookNLP compatibility is the constraint |

### NLP Phase

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Coreference system | BookNLP only (~70% accuracy) | Simplest; Claude catches remaining errors during extraction; swappable interface for future BookCoref upgrade |
| BookNLP model | Small model with MPS acceleration | M4 Pro Apple Silicon handles this fine for single books |
| BookNLP scope | Whole book at once | Coreference resolution needs full-document context |
| Text resolution strategy | Parenthetical insertion: `"he [Darrow] grabbed the sword"` | Preserves original text structure; reversible; Claude parses it well |
| Pronoun annotation aggressiveness | Both distance AND ambiguity rules | Annotate when antecedent is 3+ sentences away OR when multiple characters are in scope; tunable threshold |
| EPUB text cleaning | Moderate | Strip HTML + obvious junk (page numbers, copyright, headers); keep epigraphs and section breaks |
| Intermediate outputs | Save everything to disk | Full traceability; re-run downstream without re-running upstream |

### Knowledge Graph Phase

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cognee approach | Approach C — Hybrid custom pipeline | Best quality; LLM validates/enriches BookNLP output; chapter metadata as first-class field |
| Cognee dataset mapping | One dataset per book, chapters as metadata | Unified knowledge graph; spoiler filtering at query time |
| LLM for extraction | Anthropic Claude (cloud API) | Quality priority; willing to spend $5-10 per book |
| LLM call mechanism | Cognee's LLMGateway.acreate_structured_output | Stay in Cognee ecosystem; get structured output validation and retries |
| Ontology source | BookNLP output → BERTopic + TF-IDF → OWL file | Auto-discovered from actual book content, not predefined |
| Ontology review | Optional CLI interactive prompt | Auto by default; user can review/edit before Pass 2 |
| Quotation attribution | Passed as structured context alongside text | BookNLP's .quotes data sent to LLM as a "cheat sheet," not embedded in text |
| Batch size | Default 3 chapters; pluggable batcher interface | Start with fixed-N; future token-budget-based heuristic |
| Chapter metadata | Tag at chunk level (entities inherit from chunks) | Cognee already tracks chunk→entity provenance |
| Retry behavior | 3 retries then halt pipeline | Fail loud; don't proceed with incomplete data |
| Progress updates | Batch-level: "BookNLP: processing chapters 7–9 of 45" | Granular enough for debugging, not overwhelming |

### Evaluation

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Quality checks | Automated test suite with known-answer queries | e.g., "Who is Scrooge's clerk?" → Bob Cratchit; "What are the three ghosts?" → Past, Present, Future |

---

## Pipeline Architecture

### Phase 1: Whole-Book NLP

```
EPUB File
  │
  ▼
┌─────────────────────────────────────┐
│ Step 1: EPUB Parsing (ebooklib)     │
│                                     │
│ - Extract chapter-segmented text    │
│ - Strip HTML + moderate cleaning    │
│ - Preserve chapter boundaries       │
│ - Build token-to-chapter mapping    │
│                                     │
│ Output: raw/chapters/*.txt          │
│         raw/full_text.txt           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 2: BookNLP (whole book)        │
│                                     │
│ - Character name clustering         │
│ - Coreference resolution            │
│ - Quotation attribution             │
│ - Event detection                   │
│ - Supersense tagging                │
│                                     │
│ Output: booknlp/*.tokens            │
│         booknlp/*.entities          │
│         booknlp/*.quotes            │
│         booknlp/*.supersense        │
│         booknlp/*.book (JSON)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 3: Coreference Resolution      │
│                                     │
│ - Build coref clusters from         │
│   BookNLP .entities + .tokens       │
│ - Apply distance + ambiguity rules  │
│ - Generate parenthetical insertion  │
│   text: "he [Darrow] grabbed..."    │
│ - Produce per-chapter resolved text │
│                                     │
│ Output: coref/clusters.json         │
│         coref/resolution_log.json   │
│         resolved/chapters/*.txt     │
│         resolved/full_text.txt      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 4: Ontology Discovery          │
│                                     │
│ - Extract entity types from BookNLP │
│   character profiles + entities     │
│ - Run BERTopic + TF-IDF on text    │
│   to discover themes & relation     │
│   types                             │
│ - Generate OWL ontology file        │
│                                     │
│ Output: ontology/discovered.json    │
│         ontology/book_ontology.owl  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 5: Optional Ontology Review    │
│                                     │
│ - CLI interactive prompt            │
│ - Display discovered entity types   │
│   and relationship types            │
│ - User can add/remove/edit          │
│ - Save review snapshot              │
│                                     │
│ Output: ontology/review_snapshot.json│
│         ontology/book_ontology.owl  │
│         (updated if edited)         │
└──────────────┬──────────────────────┘
               │
               ▼
           Phase 2
```

### Phase 2: Batched Knowledge Graph Construction

```
resolved/chapters/*.txt + booknlp/* + ontology/*.owl
  │
  ▼
┌─────────────────────────────────────┐
│ Step 6: Chapter Batching            │
│                                     │
│ - Group chapters into batches       │
│ - Default: 3 chapters per batch     │
│ - Pluggable batcher interface for   │
│   future token-budget heuristic     │
│ - For each batch, collect:          │
│   - Resolved text                   │
│   - BookNLP entities for those chaps│
│   - BookNLP quotes for those chaps  │
│   - Chapter numbers                 │
│                                     │
│ Output: in-memory batch objects     │
└──────────────┬──────────────────────┘
               │
               ▼ (per batch, 3 retries on failure)
┌─────────────────────────────────────┐
│ Step 7: Custom Cognee Pipeline      │
│                                     │
│ Pipeline tasks:                     │
│                                     │
│ 1. chunk_with_chapter_awareness     │
│    - Split batch text into chunks   │
│    - Each chunk tagged with chapter │
│    - Respect paragraph boundaries   │
│                                     │
│ 2. extract_enriched_graph           │
│    - Custom extraction task         │
│    - Uses Cognee LLMGateway         │
│    - Calls Claude with:             │
│      • Resolved text chunk          │
│      • BookNLP annotations for      │
│        that chunk (entities, quotes,│
│        speaker attribution)         │
│      • OWL ontology constraints     │
│    - Outputs custom DataPoints      │
│      with chapter metadata          │
│    - Prompt template TBD at         │
│      implementation time            │
│                                     │
│ 3. add_data_points                  │
│    - Cognee built-in                │
│    - Persists to Kuzu (graph) +     │
│      LanceDB (vectors)             │
│                                     │
│ Progress: "Cognee: batch 2/3        │
│   (chapters 4-5 of 5)"             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 8: Validation                  │
│                                     │
│ - Run automated known-answer        │
│   test suite against the graph      │
│ - e.g., "Who is Scrooge's clerk?"   │
│   → expects "Bob Cratchit"          │
│ - Log pass/fail results             │
│                                     │
│ Output: validation_results.json     │
└─────────────────────────────────────┘
```

---

## What We Use From Cognee vs What We Build

### Using from Cognee

| Component | Purpose |
|-----------|---------|
| `Task`, `run_pipeline` | Pipeline orchestration |
| `DataPoint` base class | Schema for graph entities |
| `add_data_points` task | Persisting to graph + vector DBs |
| `LLMGateway.acreate_structured_output` | Calling Claude with structured output validation |
| `cognee.search()` | Query-time retrieval (future, not this plan) |
| Ontology grounding (RDFLib OWL parsing) | Constraining extraction to domain entities |
| Kuzu (graph DB) | Embedded graph storage |
| LanceDB (vector DB) | Embedded vector storage |
| SQLite (metadata DB) | Pipeline metadata |

### Building Ourselves

| Component | Purpose |
|-----------|---------|
| EPUB parser + text cleaner | ebooklib → chapter-segmented clean text |
| BookNLP orchestration | Running BookNLP, parsing its output files |
| Coreference text resolver | BookNLP clusters → parenthetical insertion text |
| Ontology discovery | BERTopic + TF-IDF → OWL file generation |
| CLI ontology reviewer | Interactive prompt for editing discovered ontology |
| Chapter-aware chunker | Custom Cognee task respecting chapter boundaries |
| Enriched graph extractor | Custom Cognee task: resolved text + BookNLP annotations → DataPoints |
| Chapter batcher | Pluggable batcher (fixed-N now, token-budget later) |
| Validation test suite | Known-answer queries for quality checking |
| Pipeline orchestrator | Background thread management, progress tracking, retry logic |
| Custom DataPoint models | Chapter-aware entity schemas (Character, Location, PlotEvent, etc.) |

---

## Custom DataPoint Models (Draft)

These Pydantic models define the graph schema. Chapter metadata is a first-class field on every entity.

```python
from cognee.infrastructure.engine import DataPoint
from typing import List, Optional, Dict, Any

class Character(DataPoint):
    name: str
    aliases: List[str] = []
    description: Optional[str] = None
    first_chapter: int
    chapters_present: List[int] = []
    metadata: Dict[str, Any] = {"index_fields": ["name", "description"]}

class Location(DataPoint):
    name: str
    description: Optional[str] = None
    first_chapter: int
    metadata: Dict[str, Any] = {"index_fields": ["name", "description"]}

class Faction(DataPoint):
    name: str
    description: Optional[str] = None
    first_chapter: int
    members: List[Character] = []
    metadata: Dict[str, Any] = {"index_fields": ["name"]}

class PlotEvent(DataPoint):
    description: str
    chapter: int
    participants: List[Character] = []
    location: Optional[Location] = None
    metadata: Dict[str, Any] = {"index_fields": ["description"]}

class Relationship(DataPoint):
    source: Character
    target: Character
    relation_type: str
    description: Optional[str] = None
    first_chapter: int
    metadata: Dict[str, Any] = {"index_fields": ["relation_type", "description"]}

class Theme(DataPoint):
    name: str
    description: Optional[str] = None
    first_chapter: int
    related_characters: List[Character] = []
    metadata: Dict[str, Any] = {"index_fields": ["name", "description"]}
```

These are draft schemas — they will be refined during implementation when we see what the LLM actually extracts well.

---

## File Output Structure

Every intermediate output is saved for traceability and debugging.

```
data/processed/{book_id}/
├── raw/
│   ├── full_text.txt                  # Clean plain text from EPUB
│   └── chapters/
│       ├── chapter_01.txt
│       ├── chapter_02.txt
│       └── ...
├── booknlp/
│   ├── {book_id}.tokens               # Token-level annotations (TSV)
│   ├── {book_id}.entities             # Entity mentions + coref IDs (TSV)
│   ├── {book_id}.quotes               # Quotation attribution (TSV)
│   ├── {book_id}.supersense           # Semantic categories (TSV)
│   └── {book_id}.book                 # Character profiles (JSON)
├── coref/
│   ├── clusters.json                  # Resolved coref clusters
│   └── resolution_log.json            # What got resolved, why, confidence
├── resolved/
│   ├── full_text_resolved.txt         # Coref-resolved full text
│   └── chapters/
│       ├── chapter_01.txt             # "he [Scrooge] muttered..."
│       └── ...
├── ontology/
│   ├── discovered_entities.json       # Raw discovery output
│   ├── book_ontology.owl              # Generated OWL file
│   └── review_snapshot.json           # State at time of optional review
├── batches/
│   ├── batch_01/
│   │   ├── input_text.txt             # Concatenated resolved chapters
│   │   ├── annotations.json           # BookNLP annotations for these chapters
│   │   └── extracted_datapoints.json  # LLM extraction output
│   └── ...
├── validation/
│   └── test_results.json              # Known-answer test pass/fail
└── pipeline_state.json                # Stage status, timestamps, errors, retries
```

---

## FastAPI Endpoints

### POST /books/upload

Upload an EPUB file. Kicks off the full pipeline in a background thread.

**Request:** multipart/form-data with EPUB file
**Response:** `{ "book_id": "christmas_carol", "status": "processing" }`

### GET /books/{book_id}/status

Returns current pipeline state with batch-level progress.

**Response:**
```json
{
  "book_id": "christmas_carol",
  "status": "processing",
  "stages": {
    "epub_parsing": { "status": "complete", "duration_seconds": 2.1 },
    "booknlp": { "status": "complete", "duration_seconds": 340.5 },
    "coref_resolution": { "status": "complete", "duration_seconds": 5.2 },
    "ontology_discovery": { "status": "complete", "duration_seconds": 12.8 },
    "cognee_ingestion": {
      "status": "running",
      "current_batch": 2,
      "total_batches": 2,
      "chapters": "4-5 of 5",
      "retries": 0
    },
    "validation": { "status": "pending" }
  },
  "ready_for_query": false
}
```

### GET /books/{book_id}/validation

Returns the known-answer test results.

### POST /books/{book_id}/progress

Set reading progress (for future query filtering).

**Request:** `{ "current_chapter": 3 }`

### POST /books/{book_id}/query

Query the knowledge graph with spoiler filtering (future — not part of this plan).

---

## Project Structure

```
bookrag/
├── pyproject.toml                     # uv project config
├── .env                               # API keys (ANTHROPIC_API_KEY, etc.)
├── config.yaml                        # Pipeline settings (batch_size, model, thresholds)
├── main.py                            # FastAPI app
├── routers/
│   ├── books.py                       # /books/upload, /books/{id}/status
│   ├── progress.py                    # /books/{id}/progress
│   └── query.py                       # /books/{id}/query (future)
├── pipeline/
│   ├── orchestrator.py                # Background thread management, retry logic
│   ├── epub_parser.py                 # ebooklib → chapter-segmented text
│   ├── text_cleaner.py                # HTML stripping, junk removal
│   ├── booknlp_runner.py              # Run BookNLP, parse output files
│   ├── coref_resolver.py              # Clusters → parenthetical insertion text
│   ├── ontology_discovery.py          # BERTopic + TF-IDF → OWL
│   ├── ontology_reviewer.py           # CLI interactive prompt
│   ├── batcher.py                     # Chapter batching (pluggable interface)
│   └── cognee_pipeline.py             # Custom Cognee tasks + pipeline
├── models/
│   ├── datapoints.py                  # Custom DataPoint schemas
│   ├── pipeline_state.py              # Pipeline stage tracking
│   └── config.py                      # Pydantic config model
├── validation/
│   ├── test_suite.py                  # Known-answer test runner
│   └── fixtures/
│       └── christmas_carol.json       # Expected answers for test book
├── data/
│   ├── books/                         # Input EPUBs
│   └── processed/                     # All intermediate + final outputs
└── logs/                              # loguru output
```

---

## Configuration (config.yaml)

```yaml
pipeline:
  batch_size: 3                        # Default chapters per batch
  max_retries: 3                       # Retries before halting
  booknlp_model: "small"               # "small" or "big"

coref:
  distance_threshold: 3                # Annotate when antecedent 3+ sentences away
  annotate_ambiguous: true             # Also annotate when multiple characters in scope

cognee:
  llm_provider: "anthropic"
  llm_model: "claude-sonnet-4-20250514"
  graph_db: "kuzu"                     # or "neo4j"
  vector_db: "lancedb"                 # or "qdrant"

ontology:
  auto_review: false                   # If true, skip CLI prompt
  min_entity_frequency: 2              # Minimum mentions to include entity type

cleaning:
  strip_html: true
  remove_toc: true
  remove_copyright: true
  keep_epigraphs: true
  keep_section_breaks: true
```

---

## Implementation Order

1. **EPUB parsing + text cleaning** — Get A Christmas Carol chapters extracted and cleaned
2. **BookNLP integration** — Run BookNLP on the full text, parse all output files into structured Python objects
3. **Coreference resolver** — Build the parenthetical insertion engine with distance + ambiguity rules
4. **Ontology discovery** — BERTopic + TF-IDF on BookNLP output → OWL file generation
5. **Custom DataPoint models** — Define the Pydantic schemas for Character, Location, PlotEvent, etc.
6. **Custom Cognee pipeline** — Build the chapter-aware chunker + enriched graph extractor tasks
7. **Pipeline orchestrator** — Background threads, retry logic, progress tracking, state persistence
8. **FastAPI endpoints** — Wire up /upload and /status
9. **Validation test suite** — Known-answer queries for A Christmas Carol
10. **Red Rising validation** — Run the full pipeline on Red Rising to stress test

---

## Open Items for Implementation

These decisions were intentionally deferred to implementation time:

- **Extraction prompt template** — The exact prompt for Claude in the enriched graph extractor task. Will be designed iteratively based on what the LLM extracts well from A Christmas Carol.
- **Token-budget batcher heuristic** — The algorithm for dynamically sizing batches based on chapter token length. Start with fixed-3, measure, then tune.
- **Coref annotation threshold tuning** — The exact distance (3 sentences? 5?) and ambiguity detection logic. Will be calibrated by inspecting resolution output on A Christmas Carol.
- **DataPoint schema refinements** — The draft schemas above will evolve based on what the LLM actually extracts well vs what it struggles with.
- **Search/query implementation** — Not part of this plan; will be designed after the ingestion pipeline is validated.
- **Spoiler filtering at query time** — Depends on the search implementation; chapter metadata is in place to support it.
