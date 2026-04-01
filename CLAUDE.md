# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

BookRAG is a spoiler-free AI chatbot for literature. It ingests EPUBs, builds a knowledge graph via Cognee, and answers queries constrained by reading progress. This repo is the **upload and ingestion pipeline**.

**Test book:** A Christmas Carol (5 chapters, ~28k words, public domain)
**Validation book:** Red Rising (~45 chapters, ~100k words)

## Commands

```bash
# Run all tests
python -m pytest tests/ -v --tb=short

# Run a single test file
python -m pytest tests/test_coref_resolver.py -v --tb=short

# Run a single test
python -m pytest tests/test_coref_resolver.py::TestDistanceRule::test_distance_triggers_at_threshold -v

# Run the FastAPI app
python main.py
```

No linter or formatter is configured. No pyproject.toml or Makefile exists. Package management uses uv (`uv pip install`).

## Current Status (as of 2026-03-31)

**744 tests passing, 1 failing, 1 collection error.**

Known issues:
- `tests/test_quality_control.py` — collection error: imports `Token` from `pipeline.booknlp_runner` but that name is not exported. Either the dataclass was renamed/removed or the test needs updating.
- `tests/test_orchestrator.py::TestStageRunBooknlp::test_stub_when_booknlp_not_installed` — 1 failure.

## Architecture

### Two-Phase Pipeline

**Phase 1 — Whole-Book NLP (once per book):**
EPUB → chapter-segmented text → BookNLP (entities, coref, quotes) → parenthetical coref resolution → ontology discovery (BERTopic + TF-IDF → OWL)

**Phase 2 — Batched KG Construction (per batch of ~3 chapters):**
Resolved text + BookNLP annotations + ontology → custom Cognee pipeline → Claude extracts DataPoints via LLMGateway → stored in Kuzu (graph) + LanceDB (vectors)

### Pipeline Stages (in order)

`parse_epub` → `run_booknlp` → `resolve_coref` → `discover_ontology` → `review_ontology` (optional) → `run_cognee_batches` → `validate`

The orchestrator (`pipeline/orchestrator.py`) runs these sequentially in a background daemon thread with crash-resume support via `pipeline_state.json`.

### Module Dependencies

```
main.py (FastAPI)
  └─ pipeline/orchestrator.py
       ├─ pipeline/epub_parser.py      → data/processed/{book_id}/raw/
       ├─ pipeline/booknlp_runner.py   → data/processed/{book_id}/booknlp/
       ├─ pipeline/coref_resolver.py   → data/processed/{book_id}/coref/ + resolved/
       ├─ pipeline/ontology_discovery.py → data/processed/{book_id}/ontology/
       ├─ pipeline/batcher.py          → in-memory batch objects
       ├─ pipeline/cognee_pipeline.py  → data/processed/{book_id}/batches/
       └─ models/pipeline_state.py     → data/processed/{book_id}/pipeline_state.json
```

`models/config.py` — Pydantic settings loaded from config.yaml + env vars (prefix `BOOKRAG_`).
`models/datapoints.py` — Custom Cognee DataPoint models (Character, Location, Faction, PlotEvent, Relationship, Theme).

### Key Design Pattern: Parenthetical Coref Insertion

BookNLP does NOT produce resolved text. We reconstruct it from `.entities` + `.tokens` + `.book` files. The format is: `"he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"`. This is reversible (strip brackets to recover original), and Claude parses it well during Phase 2 extraction.

## Testing

- **16 test files** in `tests/`, roughly 1 per pipeline module.
- **784 tests total** (744 passing, 1 failing, 1 file with collection error — see Current Status).
- **Cognee mock** in `tests/conftest.py` — installs a fake `cognee` module before any imports (required because cognee is not always installed locally). The mock provides a minimal `DataPoint` as a Pydantic BaseModel.
- **Shared fixtures** in `conftest.py`: Christmas Carol BookNLP output (book JSON, entities TSV, sample text with parenthetical coref).
- Every test class has a docstring explaining what it covers and which plan doc it aligns with.

## Locked Decisions — Do NOT Revisit

- Approach C (Hybrid Custom Pipeline) — NOT cognee.add() + default cognify()
- BookNLP only for coref (~70% accuracy); swappable interface for future BookCoref
- Parenthetical insertion format: `"he [Scrooge] muttered..."`
- One Cognee dataset per book, chapters as metadata, spoiler filtering at query time
- Cognee defaults: Kuzu + LanceDB + SQLite
- Claude (Anthropic) via Cognee LLMGateway for extraction
- ebooklib for EPUB parsing
- 3 chapters default batch size, pluggable batcher interface
- All intermediate outputs saved to disk
- Simple background threads (not Celery), API-only, single user, M4 Pro Mac
- loguru for all logging, .env + config.yaml for config

## Style

- Save all intermediate outputs to disk for traceability
- Use loguru for all logging (not stdlib logging)
- Flag Cognee pre-1.0 API instability proactively
- Comments only on non-obvious design choices

## Reference Docs

- `bookrag_pipeline_plan.md` — Full architecture plan with decision log
- `bookrag_deep_research_context.md` — Cognee internals, BookNLP output schemas, prompt patterns
