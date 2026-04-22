# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

BookRAG is a spoiler-free AI chatbot for literature. It ingests EPUBs, builds a knowledge graph via Cognee, and answers queries constrained by reading progress. The repo is a **full-stack app**: Python/FastAPI backend (ingestion pipeline + query API) and a React/Vite frontend (library, upload, reading, chat UI).

**Test book:** A Christmas Carol (5 chapters, ~28k words, public domain)
**Validation book:** Red Rising (~45 chapters, ~100k words)

## Commands

```bash
# Backend — from repo root
source .venv/bin/activate
python main.py                          # FastAPI on 127.0.0.1:8000
python -m pytest tests/ -v --tb=short   # full backend suite
python -m pytest tests/test_coref_resolver.py::TestDistanceRule::test_distance_triggers_at_threshold -v

# Frontend — from frontend/
npm run dev          # Vite dev server
npm test             # Vitest component tests
npm run test:e2e     # Playwright E2E
```

Package management: `uv` for Python, `npm` for frontend. `pyproject.toml` exists at the repo root. No linter/formatter is configured for Python.

## Current Status (as of 2026-04-21)

**923 backend tests collected.** Frontend has Vitest component tests (~10 files) and 3 Playwright E2E specs (`chat`, `reading`, `upload`).

## Architecture

### Two-Phase Pipeline

**Phase 1 — Whole-Book NLP (once per book):**
EPUB → chapter-segmented text → text cleaning → BookNLP (entities, coref, quotes) → parenthetical coref resolution → ontology discovery (BERTopic + TF-IDF → OWL)

**Phase 2 — Batched KG Construction (per batch of ~3 chapters):**
Resolved text + BookNLP annotations + ontology → custom Cognee pipeline → LLM extracts DataPoints → stored in Kuzu (graph) + LanceDB (vectors)

### Pipeline Stages (in order)

`parse_epub` → `run_booknlp` → `resolve_coref` → `discover_ontology` → `review_ontology` (optional) → `run_cognee_batches` → `validate`

The orchestrator (`pipeline/orchestrator.py`) runs these sequentially via `asyncio.create_task()` on the main event loop, with crash-resume support via `pipeline_state.json`. CPU-bound stages use `asyncio.to_thread()`.

### Module Layout

```
main.py (FastAPI + CORS for localhost:3000/5173/8000)
  └─ pipeline/orchestrator.py           → asyncio.create_task, _tasks[book_id]
       ├─ pipeline/epub_parser.py       → data/processed/{book_id}/raw/
       ├─ pipeline/text_cleaner.py      → called by epub_parser (HTML/TOC/copyright/page-num cleanup)
       ├─ pipeline/booknlp_runner.py    → data/processed/{book_id}/booknlp/
       ├─ pipeline/tsv_utils.py         → shared TSV helpers for BookNLP outputs
       ├─ pipeline/coref_resolver.py    → data/processed/{book_id}/coref/ + resolved/
       ├─ pipeline/ontology_discovery.py → data/processed/{book_id}/ontology/
       ├─ pipeline/ontology_reviewer.py → optional interactive ontology review
       ├─ pipeline/batcher.py           → in-memory Batch objects (FixedSize / TokenBudget)
       └─ pipeline/cognee_pipeline.py   → data/processed/{book_id}/batches/

models/config.py         — Pydantic BaseSettings, loads config.yaml + BOOKRAG_* env vars
models/datapoints.py     — Cognee DataPoints: Character, Location, Faction, PlotEvent, Relationship, Theme + ExtractionResult
models/pipeline_state.py — PipelineState/StageStatus with thread-safe atomic JSON save/load

frontend/src/
  ├─ screens/            — LibraryScreen, UploadScreen, ReadingScreen, BookReadingRedirect
  ├─ components/         — BookCard, ChapterRow, ChatInput, LockState, ProgressPill
  └─ lib/                — API client
```

### FastAPI Endpoints (main.py)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/books/upload` | Upload EPUB, kick off pipeline |
| GET  | `/books` | List ready-for-query books |
| GET  | `/books/{id}/status` | Current stage + progress |
| GET  | `/books/{id}/validation` | Validation test results JSON |
| GET  | `/books/{id}/chapters` | Chapter summaries (num, title, word count) |
| GET  | `/books/{id}/chapters/{n}` | Single chapter split into paragraphs |
| POST | `/books/{id}/progress` | Set reader's current chapter (spoiler gate) |
| POST | `/books/{id}/query` | Query KG with spoiler filtering |
| GET  | `/books/{id}/graph/data` | KG as JSON nodes/edges |
| GET  | `/books/{id}/graph` | Interactive vis.js HTML graph |
| GET  | `/health` | Health check |

### Config

`config.yaml` + `BOOKRAG_*` env vars flow into `models/config.py` (Pydantic). LLM API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) are **not** `BOOKRAG_`-prefixed — set them directly in `.env`. Default LLM: `openai` / `gpt-4o-mini`. Graph DB: Kuzu. Vector DB: LanceDB.

### Key Design Pattern: Parenthetical Coref Insertion

BookNLP does NOT produce resolved text. We reconstruct it from `.entities` + `.tokens` + `.book` files. Format: `"he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"`. Reversible (strip brackets to recover original), and LLMs parse it well during Phase 2 extraction.

### Fog-of-War Retrieval (Phase 0)

Reader progress is persisted per book in `reading_progress.json` (chapter-granular). At query time, `pipeline/spoiler_filter.py` walks `data/processed/{book_id}/batches/*.json` and builds an allowlist of nodes whose `effective_latest_chapter` (= max of `first_chapter`, `last_known_chapter`, `chapter`) is ≤ the reader's cursor. Retrieval runs ONLY over this allowlist — Cognee's default graph search is bypassed because it retrieves over the full dataset before filtering, which leaks spoilers through graph-completion reasoning.

For `GRAPH_COMPLETION` queries, the top-K allowed nodes are passed as context to the LLM via `_complete_over_context`. The LLM never sees post-progress content.

Limitations (addressed in later phases):
- Progress is chapter-granular, not paragraph-granular (Phase 1).
- Each entity has one DataPoint with a single `last_known_chapter`. If the entity's description was written from chapter-5 evidence, a reader at chapter-5 sees the full description; we can't rewind to a "chapter-3 snapshot" of the same entity (Phase 2).

## Testing

- **Backend**: 23 test files in `tests/`, 923 tests collected. ~1 test file per pipeline module plus cross-module quality/validation suites.
- **Cognee mock** in `tests/conftest.py` installs a fake `cognee` module before imports (cognee isn't always installed locally). Mock provides `DataPoint` as a Pydantic `BaseModel` plus `LLMGateway`, `Pipeline`, `Storage`, `Search` stubs.
- **Shared fixtures** in `conftest.py`: Christmas Carol BookNLP output (book JSON, entities TSV, parenthetical-coref sample text, sample ontology).
- **Frontend**: Vitest for components/screens, Playwright for E2E (`frontend/e2e/*.spec.ts`).
- Every backend test class has a docstring explaining coverage.

## Locked Decisions — Do NOT Revisit

- Approach C (Hybrid Custom Pipeline) — NOT `cognee.add()` + default `cognify()`
- BookNLP only for coref (~70% accuracy); swappable interface for future BookCoref
- Parenthetical insertion format: `"he [Scrooge] muttered..."`
- One Cognee dataset per book, chapters as metadata, spoiler filtering at query time
- Cognee defaults: Kuzu + LanceDB + SQLite
- LLM via Cognee LLMGateway for extraction (currently OpenAI default, Anthropic supported)
- ebooklib for EPUB parsing
- 3 chapters default batch size, pluggable batcher interface
- All intermediate outputs saved to disk
- `asyncio.create_task` for background pipelines (not threads, not Celery), API-only, single user, M4 Pro Mac
- loguru for all logging, `.env` + `config.yaml` for config

## Temporary Decisions

- **Pipeline runs on main event loop via `asyncio.create_task()`** (was daemon threads). Cognee 0.5.6 singletons (LanceDB adapter, `asyncio.Lock`) bind to the loop where they're created, causing `RuntimeError: bound to a different event loop` when the pipeline ran in a background thread with its own loop. CPU-bound stages (BookNLP, coref, ontology) use `asyncio.to_thread()`. If scaling requires true background processing, revisit with multiprocessing or Celery (not threads).
- **Cognee `add_data_points` is best-effort** — extraction data is saved to disk before persistence. If Cognee persistence fails, the pipeline still completes and endpoints serve from disk files.
- **Patched Cognee 0.5.6 locally** — `upsert_edges.py` and `upsert_nodes.py` have empty-list guards added. `metadata` fields on DataPoints use plain dict defaults (not `Field(default_factory=...)`) to work with Cognee's `copy_model`.

## Style

- Save all intermediate outputs to disk for traceability
- Use loguru for all logging (not stdlib logging)
- Flag Cognee pre-1.0 API instability proactively
- Comments only on non-obvious design choices

## Reference Docs

- `docs/superpowers/slices.md` — current slice-based development status and backlog
- `docs/superpowers/specs/`, `plans/`, `reviews/` — per-slice specs, plans, review notes
- `docs/superpowers/playbook.md` — workflow playbook
- `bookrag_pipeline_plan.md` — original architecture plan and decision log (historical)
- `bookrag_deep_research_context.md` — Cognee internals, BookNLP output schemas, prompt patterns (historical)
