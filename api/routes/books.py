"""Book-lifecycle routes — upload, list, status, validation.

Uses late ``from main import orchestrator, config`` inside each handler to
avoid an import cycle: main.py includes this router at startup, which means
this module is imported BEFORE main.py has finished initializing `config`
and `orchestrator`. The late import is ugly-but-correct for a single-user
FastAPI app.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Path as FPath, UploadFile
from loguru import logger
from pydantic import BaseModel

from api.loaders.book_data import BookSummary, list_ready_books


# ---------------------------------------------------------------------------
# Upload constants + helpers
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_CONCURRENT_PIPELINES = 5
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_]")
_EPUB_ZIP_MAGIC = b"PK\x03\x04"


# Type alias for validated book_id path parameters
SafeBookId = Annotated[str, FPath(pattern=r"^[a-z0-9_-]+$")]


class UploadResponse(BaseModel):
    book_id: str
    message: str
    reused: bool = False


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to a safe slug (alphanumeric + underscore only).

    Prevents path traversal via crafted filenames like '../../etc/passwd.epub'.
    """
    stem = Path(filename).stem.lower()
    slug = _SAFE_SLUG_RE.sub("_", stem)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "book"


router = APIRouter()


@router.post("/books/upload", response_model=UploadResponse)
async def upload_book(file: UploadFile = File(...)) -> UploadResponse:
    """Upload an EPUB file and start the processing pipeline.

    Returns immediately with a ``book_id`` that can be used to poll status.
    """
    from main import orchestrator, config, _manifest_lock

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

    from pipeline.epub_parser import check_epub_decompressed_size, EpubSizeError
    try:
        check_epub_decompressed_size(content)
    except EpubSizeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    from pipeline.content_hash import sha256_bytes, lookup_existing_book, record_book
    content_hash = sha256_bytes(content)
    existing = lookup_existing_book(config.processed_dir, content_hash)
    if existing is not None:
        logger.info("Upload matches existing book {} (sha256={}); returning cached", existing, content_hash[:12])
        return UploadResponse(book_id=existing, message="already processed", reused=True)

    # Check concurrent pipeline limit
    active = sum(1 for t in orchestrator._tasks.values() if not t.done())
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
    async with _manifest_lock:
        record_book(config.processed_dir, content_hash, book_id)

    return UploadResponse(book_id=book_id, message="Pipeline started")


@router.get("/books", response_model=list[BookSummary])
async def list_books() -> list[BookSummary]:
    """List every book whose pipeline has completed and is ready for query."""
    from main import config

    return list_ready_books(Path(config.processed_dir))


@router.get("/books/{book_id}/status")
async def get_status(book_id: SafeBookId) -> dict:
    """Return the current pipeline state as JSON."""
    from main import orchestrator

    state = orchestrator.get_state(book_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    return state.to_dict(sanitize=True)


@router.get("/books/{book_id}/validation")
async def get_validation(book_id: SafeBookId) -> dict:
    """Return validation test results for a processed book."""
    from main import config

    validation_path = (
        Path(config.processed_dir) / book_id / "validation" / "validation_results.json"
    )
    if not validation_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Validation results not found for '{book_id}'. Pipeline may still be running.",
        )
    return json.loads(validation_path.read_text(encoding="utf-8"))
