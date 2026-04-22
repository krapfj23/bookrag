"""Reading-progress route."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from api.routes.books import SafeBookId


class ProgressRequest(BaseModel):
    current_chapter: int
    current_paragraph: int | None = None


class ProgressResponse(BaseModel):
    book_id: str
    current_chapter: int
    current_paragraph: int | None = None


router = APIRouter()


@router.post("/books/{book_id}/progress", response_model=ProgressResponse)
async def set_progress(book_id: SafeBookId, req: ProgressRequest) -> ProgressResponse:
    """Set the reader's current chapter + optional paragraph cursor."""
    from main import config, orchestrator

    if req.current_chapter < 1:
        raise HTTPException(status_code=400, detail="current_chapter must be >= 1")
    if req.current_paragraph is not None and req.current_paragraph < 0:
        raise HTTPException(status_code=400, detail="current_paragraph must be >= 0")

    state = orchestrator.get_state(book_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    progress_path = Path(config.processed_dir) / book_id / "reading_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"book_id": book_id, "current_chapter": req.current_chapter}
    if req.current_paragraph is not None:
        payload["current_paragraph"] = req.current_paragraph
    progress_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info(
        "Updated reading progress: book_id={}, chapter={}, paragraph={}",
        book_id, req.current_chapter, req.current_paragraph,
    )

    return ProgressResponse(
        book_id=book_id,
        current_chapter=req.current_chapter,
        current_paragraph=req.current_paragraph,
    )
