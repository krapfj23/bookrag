"""FastAPI application for BookRAG — spoiler-free AI chatbot for literature.

Endpoints:
  POST /books/upload          — Upload an EPUB, kick off pipeline
  GET  /books/{book_id}/status — Pipeline progress
  GET  /books/{book_id}/validation — Validation results
  POST /books/{book_id}/progress — Set reading progress
  GET  /health                — Health check
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from models.config import load_config, BookRAGConfig
from pipeline.orchestrator import PipelineOrchestrator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_CONCURRENT_PIPELINES = 5
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_]")
_EPUB_ZIP_MAGIC = b"PK\x03\x04"

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
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = PipelineOrchestrator(config)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    book_id: str
    message: str


class ProgressRequest(BaseModel):
    current_chapter: int


class ProgressResponse(BaseModel):
    book_id: str
    current_chapter: int


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to a safe slug (alphanumeric + underscore only).

    Prevents path traversal via crafted filenames like '../../etc/passwd.epub'.
    """
    stem = Path(filename).stem.lower()
    slug = _SAFE_SLUG_RE.sub("_", stem)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "book"


@app.post("/books/upload", response_model=UploadResponse)
async def upload_book(file: UploadFile = File(...)) -> UploadResponse:
    """Upload an EPUB file and start the processing pipeline.

    Returns immediately with a ``book_id`` that can be used to poll status.
    """
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are accepted")

    # Read with size limit to prevent OOM
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    # Validate EPUB magic bytes (EPUBs are ZIP files)
    if not content.startswith(_EPUB_ZIP_MAGIC):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid EPUB (invalid ZIP header)",
        )

    # Check concurrent pipeline limit
    active = sum(1 for t in orchestrator._threads.values() if t.is_alive())
    if active >= MAX_CONCURRENT_PIPELINES:
        raise HTTPException(
            status_code=429,
            detail=f"Too many pipelines running ({active}/{MAX_CONCURRENT_PIPELINES}). Try again later.",
        )

    # Generate safe book_id from sanitized filename
    slug = _sanitize_filename(file.filename)
    book_id = f"{slug}_{uuid.uuid4().hex[:8]}"

    # Save uploaded file
    books_dir = Path(config.books_dir)
    books_dir.mkdir(parents=True, exist_ok=True)
    epub_path = books_dir / f"{book_id}.epub"

    try:
        epub_path.write_bytes(content)
        logger.info("Saved EPUB: {} ({} bytes)", epub_path, len(content))
    except Exception as exc:
        logger.error("Failed to save upload: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Launch pipeline in background
    orchestrator.run_in_background(book_id, epub_path)

    return UploadResponse(book_id=book_id, message="Pipeline started")


@app.get("/books/{book_id}/status")
async def get_status(book_id: str) -> dict:
    """Return the current pipeline state as JSON."""
    state = orchestrator.get_state(book_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    return state.to_dict(sanitize=True)


@app.get("/books/{book_id}/validation")
async def get_validation(book_id: str) -> dict:
    """Return validation test results for a processed book."""
    validation_path = (
        Path(config.processed_dir) / book_id / "validation" / "validation_results.json"
    )
    if not validation_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Validation results not found for '{book_id}'. Pipeline may still be running.",
        )
    return json.loads(validation_path.read_text(encoding="utf-8"))


@app.post("/books/{book_id}/progress", response_model=ProgressResponse)
async def set_progress(book_id: str, req: ProgressRequest) -> ProgressResponse:
    """Set the reader's current chapter progress for spoiler filtering.

    This is stored as a simple JSON file alongside the book's processed data.
    """
    state = orchestrator.get_state(book_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    if req.current_chapter < 1:
        raise HTTPException(status_code=400, detail="current_chapter must be >= 1")

    progress_path = Path(config.processed_dir) / book_id / "reading_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps({"book_id": book_id, "current_chapter": req.current_chapter}, indent=2),
        encoding="utf-8",
    )
    logger.info("Updated reading progress: book_id={}, chapter={}", book_id, req.current_chapter)

    return ProgressResponse(book_id=book_id, current_chapter=req.current_chapter)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check."""
    return HealthResponse(status="ok", version="0.1.0")
