# BookRAG

A spoiler-free AI chatbot for literature. Upload an EPUB, set your reading progress, and ask questions — the system will never reveal anything beyond the chapter you're on.

This repo is the **upload and ingestion pipeline**: it parses books, resolves coreferences, discovers an ontology, and builds a knowledge graph that powers spoiler-aware retrieval.

## How It Works

The pipeline transforms an EPUB into a queryable knowledge graph in two phases:

```
Phase 1 — Whole-Book NLP (once per book)
  EPUB
   → chapter-segmented text
   → BookNLP (entities, coreference, quotes)
   → parenthetical coref resolution
   → ontology discovery (BERTopic + TF-IDF → OWL)

Phase 2 — Batched Knowledge Graph Construction (per ~3 chapters)
  resolved text + annotations + ontology
   → custom Cognee pipeline
   → Claude extracts structured entities via LLMGateway
   → stored in Kuzu (graph) + LanceDB (vectors)
```

Spoiler filtering happens at query time: every entity in the graph carries chapter metadata, so the retrieval layer can exclude anything beyond the reader's current progress.

### Pipeline Stages

```
parse_epub → run_booknlp → resolve_coref → discover_ontology → review_ontology → run_cognee_batches → validate
```

Each stage saves intermediate outputs to disk. The orchestrator supports crash-resume — if the process dies mid-pipeline, it picks up where it left off.

### Knowledge Graph Schema

The pipeline extracts six entity types into the graph:

| Entity | Description | Example |
|--------|-------------|---------|
| **Character** | Named individuals with aliases and chapter presence | Scrooge, Bob Cratchit |
| **Location** | Places where events occur | Scrooge's counting house |
| **Faction** | Groups with member lists | The Ghosts of Christmas |
| **PlotEvent** | Events with participants and locations | Marley's ghost visits Scrooge |
| **Relationship** | Typed edges between characters | Scrooge *employs* Bob Cratchit |
| **Theme** | Thematic threads linked to characters | Redemption, Greed |

### Coreference Resolution

BookNLP identifies *who* pronouns refer to, but doesn't produce resolved text. This pipeline reconstructs it using parenthetical insertion:

```
Original:    "He muttered to his clerk about the cold."
Resolved:    "He [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit] about the cold."
```

Insertions trigger based on two rules:
- **Distance** — the last mention of the same character is 3+ sentences away
- **Ambiguity** — multiple characters are active in a sliding sentence window

The format is reversible (strip brackets to recover the original) and Claude parses it reliably during extraction.

## Project Structure

```
main.py                          FastAPI app — upload, status, progress endpoints
pipeline/
  ├── orchestrator.py            Runs stages sequentially with crash-resume
  ├── epub_parser.py             EPUB → chapter-segmented text
  ├── booknlp_runner.py          BookNLP integration (entities, coref, quotes)
  ├── coref_resolver.py          Parenthetical coreference resolution
  ├── ontology_discovery.py      BERTopic + TF-IDF → OWL ontology
  ├── ontology_reviewer.py       Optional ontology refinement
  ├── cognee_pipeline.py         Custom Cognee pipeline with Claude extraction
  ├── batcher.py                 Chapter batching strategies (fixed-size, token-budget)
  ├── text_cleaner.py            HTML/text cleanup
  └── tsv_utils.py               BookNLP TSV parsing helpers
models/
  ├── config.py                  Pydantic settings from config.yaml + env vars
  ├── datapoints.py              Graph schema (DataPoints) + LLM extraction models
  └── pipeline_state.py          Thread-safe pipeline state persistence
tests/                           18 test files, 805 passing tests
```

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An Anthropic API key (for Claude extraction in Phase 2)

### Install

```bash
git clone https://github.com/krapfj23/bookrag.git
cd bookrag

# Install dependencies
uv pip install -e ".[dev]"

# Optional: BookNLP for coreference (heavy — includes spaCy + transformers)
uv pip install -e ".[booknlp]"
python -m spacy download en_core_web_sm
```

### Configure

Copy `.env.example` to `.env` and set your API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Runtime settings live in `config.yaml` (batch size, retry count, thresholds).

### Run

```bash
# Start the API server
python main.py

# Upload a book
curl -X POST http://localhost:8000/books/upload \
  -F "file=@christmas_carol.epub"

# Check pipeline status
curl http://localhost:8000/books/{book_id}/status

# Set reading progress (for spoiler filtering)
curl -X POST http://localhost:8000/books/{book_id}/progress \
  -H "Content-Type: application/json" \
  -d '{"current_chapter": 3}'
```

### Test

```bash
# Run the full suite
python -m pytest tests/ -v --tb=short

# Run a specific module's tests
python -m pytest tests/test_coref_resolver.py -v
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/books/upload` | Upload an EPUB, starts pipeline in background |
| `GET` | `/books/{book_id}/status` | Pipeline progress and current stage |
| `GET` | `/books/{book_id}/validation` | Validation results after pipeline completes |
| `POST` | `/books/{book_id}/progress` | Set the reader's current chapter |
| `GET` | `/health` | Health check |

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **NLP**: BookNLP (coreference, entity extraction, quote attribution)
- **Ontology**: BERTopic + TF-IDF + rdflib (OWL output)
- **Knowledge Graph**: [Cognee](https://github.com/topoteretes/cognee) (custom pipeline with Kuzu + LanceDB)
- **LLM**: Claude via Cognee's LLMGateway for structured entity extraction
- **Config**: Pydantic Settings + YAML + env vars
- **Logging**: Loguru

## Design Decisions

Key architectural choices and their rationale:

- **Parenthetical coref insertion** over token replacement — preserves original text, is reversible, and Claude parses it well during extraction
- **One Cognee dataset per book** with chapter metadata on every entity — enables spoiler filtering at query time without dataset-per-chapter overhead
- **BookNLP for coreference** (~70% accuracy) with a swappable interface — Claude catches remaining errors during extraction; designed to swap in BookCoref when available
- **All intermediate outputs saved to disk** — full traceability, and any stage can be re-run without re-running upstream stages
- **Hybrid custom Cognee pipeline** (Approach C) — LLM validates and enriches BookNLP's structured output rather than relying solely on either

See [bookrag_pipeline_plan.md](bookrag_pipeline_plan.md) for the complete decision log.

## Testing

The test suite has **805 passing tests** across 18 test files (~10,000 lines of test code against ~4,800 lines of production code).

Tests are validated against *A Christmas Carol* (5 chapters, public domain) with real BookNLP output fixtures. Each test class documents which pipeline behavior and plan document section it covers.

```
tests/
  test_epub_parser.py          EPUB parsing, HTML cleanup, chapter detection
  test_booknlp_runner.py       BookNLP integration and output parsing
  test_coref_resolver.py       Coreference resolution rules and edge cases
  test_coref_quality.py        End-to-end coref quality on real book data
  test_ontology_discovery.py   BERTopic/TF-IDF ontology generation
  test_ontology_reviewer.py    Ontology refinement logic
  test_cognee_pipeline.py      Custom Cognee pipeline stages
  test_batcher.py              Fixed-size and token-budget batching
  test_datapoints.py           DataPoint models and extraction conversion
  test_orchestrator.py         Pipeline orchestration and crash-resume
  test_pipeline_state.py       Thread-safe state persistence
  test_main.py                 FastAPI endpoint integration tests
  ...and 6 more
```
