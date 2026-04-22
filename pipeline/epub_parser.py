"""EPUB parser that extracts chapter-segmented clean text from EPUB files.

Handles EPUB2/3 formats, strips HTML, detects chapter boundaries,
and produces structured output for downstream BookNLP processing.
"""
from __future__ import annotations

import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import ebooklib
from ebooklib import epub
from loguru import logger


class EpubSizeError(Exception):
    """Raised when an EPUB would decompress beyond configured limits."""


DEFAULT_MAX_DECOMPRESSED_BYTES = 500 * 1024 * 1024
DEFAULT_MAX_ENTRY_BYTES = 100 * 1024 * 1024


def check_epub_decompressed_size(
    path_or_bytes,
    max_total: int | None = None,
    max_entry: int | None = None,
) -> None:
    """Reject EPUBs whose total or per-entry uncompressed size exceeds the caps.

    Pure-function, no HTTP dependency. `path_or_bytes` may be a Path, str, or bytes.
    """
    max_total = max_total if max_total is not None else int(
        os.environ.get("BOOKRAG_MAX_DECOMPRESSED_BYTES", DEFAULT_MAX_DECOMPRESSED_BYTES)
    )
    max_entry = max_entry if max_entry is not None else int(
        os.environ.get("BOOKRAG_MAX_ENTRY_BYTES", DEFAULT_MAX_ENTRY_BYTES)
    )

    source: Any
    if isinstance(path_or_bytes, (bytes, bytearray)):
        import io
        source = io.BytesIO(bytes(path_or_bytes))
    else:
        source = str(path_or_bytes)

    with zipfile.ZipFile(source) as zf:
        total = 0
        for info in zf.infolist():
            if info.file_size > max_entry:
                raise EpubSizeError(
                    f"EPUB entry '{info.filename}' decompresses to "
                    f"{info.file_size} bytes (max per-entry {max_entry})"
                )
            total += info.file_size
            if total > max_total:
                raise EpubSizeError(
                    f"EPUB decompresses to total {total}+ bytes (max total {max_total})"
                )


@dataclass
class ParsedBook:
    """Structured output from EPUB parsing."""

    book_id: str
    chapter_count: int
    chapter_texts: list[str]
    full_text: str
    chapter_boundaries: list[tuple[int, int]]


class _HTMLTextExtractor(HTMLParser):
    """Strips HTML tags and extracts plain text, handling common EPUB quirks."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth: int = 0
        self._block_tags = {
            "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
            "li", "blockquote", "tr", "section", "article",
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "br":
            self._chunks.append("\n")
        elif tag in self._block_tags:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._block_tags:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def handle_entityref(self, name: str) -> None:
        from html import unescape
        self._chunks.append(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        from html import unescape
        self._chunks.append(unescape(f"&#{name};"))

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        # Replace non-breaking spaces
        raw = raw.replace("\u00a0", " ")
        raw = raw.replace("\xa0", " ")
        # Collapse runs of whitespace on each line, preserve newlines
        lines = raw.split("\n")
        lines = [" ".join(line.split()) for line in lines]
        # Collapse 3+ blank lines into 2
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _slugify(name: str) -> str:
    """Convert a filename into a URL-safe slug for use as book_id."""
    name = Path(name).stem
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"[-\s]+", "_", name).strip("_")
    return name


def _extract_text_from_html(html_bytes: bytes) -> str:
    """Parse HTML content and return plain text."""
    try:
        html_str = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        html_str = html_bytes.decode("latin-1", errors="replace")

    extractor = _HTMLTextExtractor()
    extractor.feed(html_str)
    return extractor.get_text()


def _is_content_chapter(text: str) -> bool:
    """Heuristic: decide whether extracted text is actual chapter content.

    Filters out near-empty spine items (cover pages, blank pages, navs).
    """
    stripped = text.strip()
    if len(stripped) < 50:
        return False
    word_count = len(stripped.split())
    return word_count >= 15


def parse_epub(epub_path: str | Path, output_dir: str | Path | None = None) -> ParsedBook:
    """Parse an EPUB file into chapter-segmented plain text.

    Args:
        epub_path: Path to the .epub file.
        output_dir: Base output directory. Defaults to ``data/processed/{book_id}/raw``.

    Returns:
        A ``ParsedBook`` dataclass with all extracted data.
    """
    epub_path = Path(epub_path)
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    # Guard against files that are too large before decompressing.
    # The API upload endpoint enforces 500 MB on the compressed file; this
    # duplicates that check at the parser level for files arriving via other paths.
    file_size = epub_path.stat().st_size
    if file_size > 500 * 1024 * 1024:
        raise ValueError(
            f"EPUB file too large: {file_size} bytes (limit 500 MB)"
        )

    try:
        check_epub_decompressed_size(epub_path)
    except EpubSizeError as exc:
        raise ValueError(str(exc)) from exc
    except zipfile.BadZipFile:
        # Not a valid ZIP — let ebooklib produce its own error downstream
        pass

    book_id = _slugify(epub_path.name)
    logger.info("Parsing EPUB: {} (book_id={})", epub_path.name, book_id)

    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})

    # Walk the spine to preserve reading order
    spine_ids = [item_id for item_id, _linear in book.spine]
    id_to_item: dict[str, ebooklib.epub.EpubItem] = {
        item.get_id(): item for item in book.get_items()
    }

    chapter_texts: list[str] = []
    for spine_id in spine_ids:
        item = id_to_item.get(spine_id)
        if item is None:
            logger.warning("Spine item '{}' not found in manifest — skipping", spine_id)
            continue
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        content = item.get_content()
        text = _extract_text_from_html(content)

        if _is_content_chapter(text):
            chapter_texts.append(text)
            word_count = len(text.split())
            logger.debug(
                "Chapter {:>3}: {:>6} words  (spine_id={})",
                len(chapter_texts),
                word_count,
                spine_id,
            )
        else:
            logger.debug("Skipping non-content spine item: {} ({} chars)", spine_id, len(text))

    if not chapter_texts:
        logger.warning("No content chapters detected — falling back to all ITEM_DOCUMENT items")
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            text = _extract_text_from_html(item.get_content())
            if text.strip():
                chapter_texts.append(text)

    logger.info("Extracted {} chapters from {}", len(chapter_texts), epub_path.name)

    # Build full text with chapter markers and compute boundaries
    full_text_parts: list[str] = []
    chapter_boundaries: list[tuple[int, int]] = []
    cursor = 0

    for idx, ch_text in enumerate(chapter_texts, start=1):
        marker = f"=== CHAPTER {idx} ===\n\n"
        full_text_parts.append(marker)
        cursor += len(marker)
        start = cursor
        full_text_parts.append(ch_text)
        cursor += len(ch_text)
        end = cursor
        chapter_boundaries.append((start, end))
        full_text_parts.append("\n\n")
        cursor += 2

    full_text = "".join(full_text_parts)

    # Log summary
    total_words = sum(len(ch.split()) for ch in chapter_texts)
    logger.info(
        "Total: {} words across {} chapters (avg {:.0f} words/chapter)",
        total_words,
        len(chapter_texts),
        total_words / max(len(chapter_texts), 1),
    )

    # Write outputs
    if output_dir is None:
        output_dir = Path("data/processed") / book_id / "raw"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = output_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    full_text_path = output_dir / "full_text.txt"
    full_text_path.write_text(full_text, encoding="utf-8")
    logger.info("Wrote full text to {}", full_text_path)

    for idx, ch_text in enumerate(chapter_texts, start=1):
        ch_path = chapters_dir / f"chapter_{idx:02d}.txt"
        ch_path.write_text(ch_text, encoding="utf-8")

    logger.info("Wrote {} chapter files to {}", len(chapter_texts), chapters_dir)

    return ParsedBook(
        book_id=book_id,
        chapter_count=len(chapter_texts),
        chapter_texts=chapter_texts,
        full_text=full_text,
        chapter_boundaries=chapter_boundaries,
    )


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    test_path = Path("data/input/test_book.epub")
    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])

    if not test_path.exists():
        logger.error("Usage: python -m pipeline.epub_parser <path_to_epub>")
        logger.error("File not found: {}", test_path)
        sys.exit(1)

    result = parse_epub(test_path)
    logger.info("Parsed '{}': {} chapters, {} total chars", result.book_id, result.chapter_count, len(result.full_text))
