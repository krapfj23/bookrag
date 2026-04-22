"""Chapter-list and single-chapter routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.loaders.book_data import (
    Chapter,
    ChapterSummary,
    _derive_chapter_title,
    list_chapter_files,
    load_chapter,
)
from api.routes.books import SafeBookId


router = APIRouter()


@router.get("/books/{book_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(book_id: SafeBookId) -> list[ChapterSummary]:
    """List chapter metadata for a ready book."""
    from main import config

    files = list_chapter_files(book_id, Path(config.processed_dir))
    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"Book '{book_id}' not found or not ready for query",
        )
    summaries: list[ChapterSummary] = []
    for idx, path in enumerate(files, start=1):
        raw_text = path.read_text(encoding="utf-8")
        summaries.append(
            ChapterSummary(
                num=idx,
                title=_derive_chapter_title(raw_text, idx),
                word_count=len(raw_text.split()),
            )
        )
    return summaries


@router.get("/books/{book_id}/chapters/{n}", response_model=Chapter)
async def get_chapter(book_id: SafeBookId, n: int) -> Chapter:
    """Load a single chapter's body as paragraph-split text."""
    from main import config

    chapter = load_chapter(book_id, n, Path(config.processed_dir))
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {n} not found for book '{book_id}'",
        )
    return chapter
