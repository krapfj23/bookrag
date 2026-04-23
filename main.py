"""FastAPI application for BookRAG — spoiler-free AI chatbot for literature.

Endpoints:
  POST /books/upload          — Upload an EPUB, kick off pipeline
  GET  /books/{book_id}/status — Pipeline progress
  GET  /books/{book_id}/validation — Validation results
  POST /books/{book_id}/progress — Set reading progress
  GET  /health                — Health check
"""
from __future__ import annotations

# MUST come before any torch/numpy/sklearn import. macOS + conda-venv loads two
# OpenMP runtimes (conda's libomp + pip torch's libomp) which causes
# `OMP: Error #179: pthread_mutex_init failed` during BERTopic/UMAP. Setting
# these env vars lets the duplicate loads coexist and forces single-threaded
# BLAS so the multiprocessing resource tracker doesn't crash.
import os as _os
_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
_os.environ.setdefault("OMP_NUM_THREADS", "1")
_os.environ.setdefault("MKL_NUM_THREADS", "1")
_os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
_os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import asyncio
import html as html_mod
import json
import os
import re
import shutil
import sys

from dotenv import load_dotenv
load_dotenv()
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Path as FPath, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from typing import Annotated, Any

from api.loaders.book_data import (
    BookSummary,
    Chapter,
    ChapterSummary,
    _derive_chapter_title,
    derive_title as _derive_title,
    get_reading_progress as _get_reading_progress_impl,
    list_chapter_files as _list_chapter_files_impl,
    list_ready_books as _list_ready_books_impl,
    load_chapter as _load_chapter_impl,
    load_paragraphs_up_to as _load_paragraphs_up_to_impl,
)
from api.loaders.graph_data import load_batch_datapoints as _load_batch_datapoints_impl
from api.query.synthesis import (
    ALLOWED_SEARCH_TYPES as _ALLOWED_SEARCH_TYPES,
    QueryRequest,
    QueryResponse,
    QueryResultItem,
    _SpoilerSafeAnswer,
    _result_entity_type as _synthesis_result_entity_type,
    _result_to_text as _synthesis_result_to_text,
    _search_datapoints_on_disk as _synthesis_search_datapoints_on_disk,
    answer_from_allowed_nodes as _synthesis_answer_from_allowed_nodes,
    complete_over_context as _synthesis_complete_over_context,
    extract_chapter as _synthesis_extract_chapter,
    vector_triplet_search as _synthesis_vector_triplet_search,
)
from models.config import load_config, ensure_directories, BookRAGConfig
from pipeline.orchestrator import PipelineOrchestrator

# Cognee search imports — optional at import time, configured at startup
try:
    import cognee
    from cognee.modules.search.types import SearchType
    from pipeline.cognee_pipeline import configure_cognee

    COGNEE_AVAILABLE = True
except (ImportError, AttributeError):
    COGNEE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAFE_BOOK_ID_RE = re.compile(r"^[a-z0-9_-]+$")

# Re-export for test/legacy imports that still reference main.SafeBookId and
# the upload-size constants.
from api.routes.books import (
    MAX_CONCURRENT_PIPELINES,
    MAX_UPLOAD_BYTES,
    SafeBookId,
    _EPUB_ZIP_MAGIC,
    _SAFE_SLUG_RE,
    _sanitize_filename,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan> — {message}",
)
logger.add(
    "logs/bookrag.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

config: BookRAGConfig = load_config()
ensure_directories(config)


def _query_rate_limit() -> str:
    raw = os.environ.get("BOOKRAG_QUERY_RATE_LIMIT", "30/minute")
    # Basic shape validation — slowapi accepts "<int>/<unit>" forms.
    # An invalid value would crash every /query request with a 500;
    # catch it here and fall back to the default with a warning.
    try:
        n_str, unit = raw.split("/", 1)
        int(n_str.strip())
    except (ValueError, AttributeError):
        logger.warning(
            "Invalid BOOKRAG_QUERY_RATE_LIMIT={!r}; falling back to 30/minute", raw
        )
        return "30/minute"
    return raw


_manifest_lock = asyncio.Lock()

limiter = Limiter(key_func=get_remote_address, default_limits=[])

app = FastAPI(
    title="BookRAG",
    description="Spoiler-free AI chatbot for literature",
    version="0.1.0",
)

_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    retry_after = str(int(getattr(exc, "retry_after", 60)))
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": retry_after},
    )


orchestrator = PipelineOrchestrator(config)

if COGNEE_AVAILABLE:
    try:
        configure_cognee(config)
        logger.info("Cognee configured for search at startup")
    except (AttributeError, Exception) as exc:
        logger.warning("Cognee configuration skipped at startup: {}", exc)
        COGNEE_AVAILABLE = False


# Register sub-routers — routes live in api/routes/*.
from api.routes import (
    books as books_routes,
    chapters as chapters_routes,
    graph as graph_routes,
    health as health_routes,
    progress as progress_routes,
    query as query_routes,
)

app.include_router(books_routes.router)
app.include_router(health_routes.router)
app.include_router(chapters_routes.router)
app.include_router(progress_routes.router)
app.include_router(query_routes.router)
app.include_router(graph_routes.router)

# Re-export moved models for test imports that referenced them on main.
HealthResponse = health_routes.HealthResponse
UploadResponse = books_routes.UploadResponse
ProgressRequest = progress_routes.ProgressRequest
ProgressResponse = progress_routes.ProgressResponse

# ---------------------------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------------------------

# Thin wrappers so internal callers stay concise — the real implementations
# live in api.loaders.book_data and take processed_dir explicitly.

def _list_ready_books() -> list[BookSummary]:
    return _list_ready_books_impl(Path(config.processed_dir))


def _list_chapter_files(book_id: str) -> list[Path]:
    return _list_chapter_files_impl(book_id, Path(config.processed_dir))


def _load_chapter(book_id: str, n: int) -> Chapter | None:
    return _load_chapter_impl(book_id, n, Path(config.processed_dir))


def _load_paragraphs_up_to(
    book_id: str,
    chapter: int,
    paragraph_cursor: int,
) -> list[str]:
    return _load_paragraphs_up_to_impl(
        book_id, chapter, paragraph_cursor, Path(config.processed_dir)
    )


def _get_reading_progress(book_id: str) -> tuple[int, int | None]:
    return _get_reading_progress_impl(book_id, Path(config.processed_dir))


# Synthesis helpers are thin wrappers around api.query.synthesis.* so legacy
# imports (tests that monkeypatch ``main._complete_over_context`` etc.) keep
# working. New callers should import from api.query.synthesis directly.

def _extract_chapter(item: Any) -> int | None:
    return _synthesis_extract_chapter(item)


def _result_to_text(item: Any) -> str:
    return _synthesis_result_to_text(item)


def _result_entity_type(item: Any) -> str | None:
    return _synthesis_result_entity_type(item)


def _search_datapoints_on_disk(book_id: str, question: str, max_chapter: int) -> list[QueryResultItem]:
    return _synthesis_search_datapoints_on_disk(
        book_id, question, max_chapter, Path(config.processed_dir)
    )


async def _complete_over_context(question: str, context: list[str]) -> str:
    return await _synthesis_complete_over_context(question, context)


def _answer_from_allowed_nodes(
    book_id: str,
    question: str,
    graph_max_chapter: int,
) -> list[QueryResultItem]:
    return _synthesis_answer_from_allowed_nodes(
        book_id, question, graph_max_chapter, Path(config.processed_dir)
    )


async def _vector_triplet_search(
    book_id: str,
    question: str,
    graph_max_chapter: int,
) -> list[QueryResultItem]:
    return await _synthesis_vector_triplet_search(
        book_id, question, graph_max_chapter, Path(config.processed_dir)
    )


def _load_batch_datapoints(book_id: str, max_chapter: int | None = None) -> dict:
    """Thin wrapper over api.loaders.graph_data.load_batch_datapoints."""
    return _load_batch_datapoints_impl(book_id, Path(config.processed_dir), max_chapter)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
