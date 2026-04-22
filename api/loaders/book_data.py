"""Disk loaders for book and chapter data plus the Pydantic response models
they populate.

Every function takes ``processed_dir: Path`` explicitly — no module-level
dependency on the running FastAPI config. This keeps the loaders usable from
scripts and tests that don't boot the full app.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from api.loaders.sentence_anchors import (
    AnchoredParagraph,
    build_paragraphs_anchored,
    find_chapter_offsets,
    load_cleaned_full_text,
    load_tokens_for_book,
    regex_fallback_paragraphs,
)


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class BookSummary(BaseModel):
    book_id: str
    title: str
    total_chapters: int
    current_chapter: int
    ready_for_query: bool


class ChapterSummary(BaseModel):
    num: int
    title: str
    word_count: int


class Chapter(BaseModel):
    num: int
    title: str
    paragraphs: list[str]
    paragraphs_anchored: list[AnchoredParagraph] = []
    anchors_fallback: bool = True
    has_prev: bool
    has_next: bool
    total_chapters: int


# ---------------------------------------------------------------------------
# Title derivation + chapter title parsing
# ---------------------------------------------------------------------------

_BOOK_ID_HEX_SUFFIX_RE = re.compile(r"_[0-9a-f]{8}$")
_TITLE_TERMINATORS = ".!?:"


def derive_title(book_id: str) -> str:
    """Strip an optional trailing _<8-hex> id and title-case the remaining slug."""
    slug = _BOOK_ID_HEX_SUFFIX_RE.sub("", book_id)
    words = [w for w in slug.split("_") if w]
    return " ".join(w.capitalize() for w in words) if words else book_id


def _derive_chapter_title(raw_text: str, n: int) -> str:
    """First non-empty stripped line if short + not sentence-terminated + no special chars, else 'Chapter N'.

    Rejects lines containing '*' or '#' (Gutenberg boilerplate markers).
    """
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            len(stripped) < 80
            and stripped[-1] not in _TITLE_TERMINATORS
            and "*" not in stripped
            and "#" not in stripped
        ):
            return stripped
        break
    return f"Chapter {n}"


# ---------------------------------------------------------------------------
# Disk scanners
# ---------------------------------------------------------------------------

def list_ready_books(processed_dir: Path) -> list[BookSummary]:
    """Scan processed_dir for books ready for query.

    Skips directories whose pipeline_state.json is missing or unreadable
    and logs a warning; never raises.
    """
    from models.pipeline_state import load_state  # local import — avoid cycles

    if not processed_dir.exists():
        return []

    books: list[BookSummary] = []
    for child in sorted(processed_dir.iterdir()):
        if not child.is_dir():
            continue
        state_path = child / "pipeline_state.json"
        if not state_path.exists():
            logger.warning("Skipping {}: pipeline_state.json missing", child.name)
            continue
        try:
            state = load_state(state_path)
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Skipping {}: cannot load pipeline state ({})", child.name, exc)
            continue
        if not state.ready_for_query:
            continue
        chapters_dir = child / "raw" / "chapters"
        total_chapters = (
            len(list(chapters_dir.glob("chapter_*.txt"))) if chapters_dir.exists() else 0
        )
        current_chapter, _ = get_reading_progress(child.name, processed_dir)
        books.append(
            BookSummary(
                book_id=child.name,
                title=derive_title(child.name),
                total_chapters=total_chapters,
                current_chapter=current_chapter,
                ready_for_query=True,
            )
        )
    return books


def list_chapter_files(book_id: str, processed_dir: Path) -> list[Path]:
    """Return sorted chapter_*.txt paths for a ready book.

    Prefers raw/chapters/ (which preserves \\n\\n paragraph breaks).
    Returns [] if the book dir is missing OR ready_for_query is false.
    """
    from models.pipeline_state import load_state  # local import — avoid cycles

    book_dir = processed_dir / book_id
    state_path = book_dir / "pipeline_state.json"
    if not state_path.exists():
        return []
    try:
        state = load_state(state_path)
    except (json.JSONDecodeError, KeyError, OSError):
        return []
    if not state.ready_for_query:
        return []
    chapters_dir = book_dir / "raw" / "chapters"
    if not chapters_dir.exists():
        return []
    return sorted(chapters_dir.glob("chapter_*.txt"))


def load_chapter(book_id: str, n: int, processed_dir: Path) -> Chapter | None:
    """Load a single chapter. Returns None if the book isn't ready or n is out of range."""
    files = list_chapter_files(book_id, processed_dir)
    if not files:
        return None
    if n < 1 or n > len(files):
        return None
    raw_text = files[n - 1].read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    title = _derive_chapter_title(raw_text, n)

    anchored: list[AnchoredParagraph] = []
    fallback = True
    tokens = load_tokens_for_book(book_id, processed_dir)
    full_text = load_cleaned_full_text(book_id, processed_dir)
    if tokens and full_text:
        offsets = find_chapter_offsets(full_text, raw_text)
        if offsets is not None:
            start, end = offsets
            anchored, ok = build_paragraphs_anchored(raw_text, tokens, start, end)
            if ok:
                fallback = False
    if fallback:
        anchored = regex_fallback_paragraphs(paragraphs)

    return Chapter(
        num=n,
        title=title,
        paragraphs=paragraphs,
        paragraphs_anchored=anchored,
        anchors_fallback=fallback,
        has_prev=n > 1,
        has_next=n < len(files),
        total_chapters=len(files),
    )


def load_paragraphs_up_to(
    book_id: str,
    chapter: int,
    paragraph_cursor: int,
    processed_dir: Path,
) -> list[str]:
    """Return paragraphs 0..paragraph_cursor (inclusive) from `chapter`.

    Empty list if the book/chapter doesn't exist. Cursor values past the last
    paragraph are clamped. Reuses load_chapter's paragraph splitting.
    """
    ch = load_chapter(book_id, chapter, processed_dir)
    if ch is None:
        return []
    return ch.paragraphs[: max(paragraph_cursor + 1, 0)]


def get_reading_progress(
    book_id: str, processed_dir: Path
) -> tuple[int, int | None]:
    """Load current reading progress. Returns (chapter, paragraph_or_None).

    Paragraph is 0-indexed when present. None means "paragraph cursor not
    recorded" — callers treat that as Phase-0-compatible chapter-only progress.
    """
    progress_path = processed_dir / book_id / "reading_progress.json"
    if not progress_path.exists():
        return 1, None
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1, None
    chapter = int(data.get("current_chapter", 1))
    paragraph = data.get("current_paragraph")
    paragraph = int(paragraph) if paragraph is not None else None
    return chapter, paragraph
