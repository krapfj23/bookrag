"""Text cleaner for raw chapter text extracted from EPUBs.

Applies configurable cleaning passes: HTML entities, page numbers,
copyright boilerplate, TOC fragments, and whitespace normalization,
while preserving epigraphs and section breaks.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class CleaningConfig:
    """Controls which cleaning passes are applied."""

    strip_html: bool = True
    remove_toc: bool = True
    remove_copyright: bool = True
    keep_epigraphs: bool = True
    keep_section_breaks: bool = True
    # When False (default), smart quotes and em-/en-dashes survive cleaning —
    # BookNLP relies on curly quote pairs for dialogue/speaker attribution,
    # and the reader styles them natively. Flip to True for downstream
    # consumers that need ASCII-only text.
    ascii_quotes: bool = False


@dataclass
class CleaningStats:
    """Counts of items removed during cleaning."""

    html_entities_replaced: int = 0
    page_numbers_removed: int = 0
    copyright_lines_removed: int = 0
    toc_lines_removed: int = 0
    unicode_quotes_normalized: int = 0
    nbsp_replaced: int = 0
    invisibles_stripped: int = 0
    scene_breaks_normalized: int = 0


# --- Patterns ---

_PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,5}\s*$")

_COPYRIGHT_PATTERNS = [
    re.compile(r"(?i)^\s*copyright\s*[\u00a9\u24b8(c)]\s*\d{4}"),
    re.compile(r"(?i)^\s*all rights reserved"),
    re.compile(r"(?i)^\s*published by\s+"),
    re.compile(r"(?i)^\s*isbn[\s:\-]*[\dxX\-]+"),
    re.compile(r"(?i)^\s*printed in\s+"),
    re.compile(r"(?i)^\s*library of congress"),
    re.compile(r"(?i)^\s*first (edition|printing)"),
    re.compile(r"(?i)^\s*cover (design|art|illustration)"),
    re.compile(r"(?i)^\s*\d+\s*\u00a9\s*"),
]

_TOC_LINE_RE = re.compile(
    r"(?i)^\s*chapter\s+[\dIVXLCivxlc]+[\s.:]*\d+\s*$"
)

_SECTION_BREAK_RE = re.compile(
    r"^\s*("
    r"[*\-=~#]{3,}"            # ***  ---  ===  ~~~  ###
    r"|\*\s+\*\s+\*"           # * * *
    r"|[•·]\s*[•·]\s*[•·]"  # ••• · · ·
    r"|⁂|⁑|⁕|⁖|⁂⁂⁂"     # ⁂ ⁑ ⁕ ⁖
    r"|---+|===+|~~~+"
    r")\s*$"
)

# Canonical scene-break sentinel emitted to the cleaned text. The reader
# detects this exact string and renders an ornamental dinkus; BookNLP treats
# it as an inert 3-char paragraph.
SCENE_BREAK_SENTINEL = "***"

# Characters that serve no semantic purpose in rendered prose and frequently
# survive EPUB → plaintext conversion as noise.
#   U+00AD  soft hyphen (reflow hint)
#   U+200B  zero-width space
#   U+200C  zero-width non-joiner
#   U+200D  zero-width joiner
#   U+2060  word joiner
#   U+FEFF  byte-order mark
_INVISIBLES_RE = re.compile(r"[­​‌‍⁠﻿]")

_EPIGRAPH_RE = re.compile(
    r'^(\s*[\x22\u201c\u201d\u2018\u2019\u0022].+[\x22\u201c\u201d\u2018\u2019\u0022]\s*$'
    r'|^\s*\u2014.+$)',
    re.MULTILINE,
)

_UNICODE_QUOTES: dict[str, str] = {
    "\u201c": '"',  # left double
    "\u201d": '"',  # right double
    "\u2018": "'",  # left single
    "\u2019": "'",  # right single
    "\u00ab": '"',  # left guillemet
    "\u00bb": '"',  # right guillemet
    "\u2013": "-",  # en dash
    "\u2014": "--", # em dash
    "\u2026": "...", # ellipsis
}

_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[\da-fA-F]+|[a-zA-Z]+);")


def _replace_html_entities(text: str, stats: CleaningStats) -> str:
    """Decode any residual HTML entities."""
    count = len(_HTML_ENTITY_RE.findall(text))
    if count > 0:
        text = html.unescape(text)
        stats.html_entities_replaced += count
    return text


def _replace_nbsp(text: str, stats: CleaningStats) -> str:
    """Replace non-breaking spaces with regular spaces."""
    count = text.count("\u00a0")
    text = text.replace("\u00a0", " ")
    stats.nbsp_replaced += count
    return text


def _normalize_unicode_quotes(text: str, stats: CleaningStats) -> str:
    """Replace fancy Unicode quotes/dashes with ASCII equivalents.

    Opt-in only: the default cleaner preserves curly quotes and em-/en-
    dashes because BookNLP's dialogue/speaker detection depends on them
    and the reader styles them natively.
    """
    count = 0
    for fancy, plain in _UNICODE_QUOTES.items():
        occurrences = text.count(fancy)
        if occurrences > 0:
            text = text.replace(fancy, plain)
            count += occurrences
    stats.unicode_quotes_normalized += count
    return text


def _strip_invisibles(text: str, stats: CleaningStats) -> str:
    """Drop soft hyphens, zero-widths, word joiner, and BOM."""
    count = len(_INVISIBLES_RE.findall(text))
    if count:
        text = _INVISIBLES_RE.sub("", text)
        stats.invisibles_stripped += count
    return text


def _normalize_scene_breaks(lines: list[str], stats: CleaningStats) -> list[str]:
    """Rewrite any recognized scene-break line to the canonical sentinel."""
    out: list[str] = []
    for line in lines:
        if _SECTION_BREAK_RE.match(line):
            if line.strip() != SCENE_BREAK_SENTINEL:
                stats.scene_breaks_normalized += 1
            out.append(SCENE_BREAK_SENTINEL)
        else:
            out.append(line)
    return out


def _remove_page_numbers(lines: list[str], stats: CleaningStats) -> list[str]:
    """Remove lines that are standalone page numbers."""
    result: list[str] = []
    for line in lines:
        if _PAGE_NUMBER_RE.match(line):
            stats.page_numbers_removed += 1
        else:
            result.append(line)
    return result


def _remove_copyright(lines: list[str], stats: CleaningStats) -> list[str]:
    """Remove lines matching common copyright/boilerplate patterns."""
    result: list[str] = []
    in_copyright_block = False

    for line in lines:
        stripped = line.strip()

        if any(pat.match(stripped) for pat in _COPYRIGHT_PATTERNS):
            stats.copyright_lines_removed += 1
            in_copyright_block = True
            continue

        # Continue removing blank lines that follow copyright lines
        if in_copyright_block and stripped == "":
            continue

        in_copyright_block = False
        result.append(line)

    return result


def _remove_toc(lines: list[str], stats: CleaningStats) -> list[str]:
    """Remove table-of-contents lines (e.g., 'Chapter 1 ... 15')."""
    result: list[str] = []
    consecutive_toc = 0
    held_toc_lines: list[str] = []

    for line in lines:
        if _TOC_LINE_RE.match(line.strip()):
            consecutive_toc += 1
            held_toc_lines.append(line)
            stats.toc_lines_removed += 1
            continue

        if consecutive_toc == 1:
            # Only one TOC-like line — probably a real chapter heading, put it back
            result.append(held_toc_lines[0])
            stats.toc_lines_removed -= 1

        # 2+ consecutive TOC lines: they stay removed (already counted)
        consecutive_toc = 0
        held_toc_lines.clear()
        result.append(line)

    # Handle trailing single TOC line at end of input
    if consecutive_toc == 1:
        result.append(held_toc_lines[0])
        stats.toc_lines_removed -= 1

    return result


def _protect_epigraphs(text: str) -> tuple[str, dict[str, str]]:
    """Replace epigraph blocks with placeholders so they survive cleaning."""
    placeholders: dict[str, str] = {}
    counter = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal counter
        key = f"__EPIGRAPH_{counter}__"
        placeholders[key] = match.group(0)
        counter += 1
        return key

    # Only protect quoted text in the first 20 lines of the input
    # (epigraphs appear at chapter starts)
    lines = text.split("\n")
    head = "\n".join(lines[:20])
    tail = "\n".join(lines[20:])

    head = _EPIGRAPH_RE.sub(_replace, head)
    return head + ("\n" + tail if tail else ""), placeholders


def _restore_epigraphs(text: str, placeholders: dict[str, str]) -> str:
    """Restore epigraph placeholders back to original text."""
    for key, original in placeholders.items():
        text = text.replace(key, original)
    return text


def _normalize_whitespace(text: str) -> str:
    """Collapse excess blank lines, strip trailing whitespace per line."""
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    text = "\n".join(lines)
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def clean_text(
    text: str,
    config: CleaningConfig | None = None,
) -> str:
    """Apply all configured cleaning passes to the input text.

    Args:
        text: Raw chapter or full-book text.
        config: Cleaning configuration. Uses defaults if None.

    Returns:
        Cleaned text string.
    """
    if config is None:
        config = CleaningConfig()

    stats = CleaningStats()

    # Unicode normalization: NFC (not NFKC) — keeps semantic codepoints
    # (fractions, full-width, non-breaking space) distinct while still
    # canonicalizing pre-composed/decomposed sequences of the same glyph.
    text = unicodedata.normalize("NFC", text)

    # Character-level passes (before line splitting)
    text = _replace_nbsp(text, stats)
    text = _strip_invisibles(text, stats)
    if config.ascii_quotes:
        text = _normalize_unicode_quotes(text, stats)

    if config.strip_html:
        text = _replace_html_entities(text, stats)

    # Protect epigraphs before line-level removal
    placeholders: dict[str, str] = {}
    if config.keep_epigraphs:
        text, placeholders = _protect_epigraphs(text)

    lines = text.split("\n")

    # Line-level passes
    lines = _remove_page_numbers(lines, stats)

    if config.remove_copyright:
        lines = _remove_copyright(lines, stats)

    if config.remove_toc:
        lines = _remove_toc(lines, stats)

    # Section breaks: either normalize to the canonical sentinel (default)
    # or erase entirely (opt-out).
    if config.keep_section_breaks:
        lines = _normalize_scene_breaks(lines, stats)
    else:
        kept: list[str] = []
        for line in lines:
            if _SECTION_BREAK_RE.match(line):
                kept.append("")
            else:
                kept.append(line)
        lines = kept

    text = "\n".join(lines)
    text = _normalize_whitespace(text)

    # Restore epigraphs
    if config.keep_epigraphs and placeholders:
        text = _restore_epigraphs(text, placeholders)

    # Log summary
    if stats.html_entities_replaced:
        logger.debug("Replaced {} HTML entities", stats.html_entities_replaced)
    if stats.page_numbers_removed:
        logger.debug("Removed {} page-number lines", stats.page_numbers_removed)
    if stats.copyright_lines_removed:
        logger.debug("Removed {} copyright/boilerplate lines", stats.copyright_lines_removed)
    if stats.toc_lines_removed:
        logger.debug("Removed {} TOC lines", stats.toc_lines_removed)
    if stats.unicode_quotes_normalized:
        logger.debug("Normalized {} Unicode quotes/dashes", stats.unicode_quotes_normalized)
    if stats.nbsp_replaced:
        logger.debug("Replaced {} non-breaking spaces", stats.nbsp_replaced)
    if stats.invisibles_stripped:
        logger.debug("Stripped {} invisible characters", stats.invisibles_stripped)
    if stats.scene_breaks_normalized:
        logger.debug(
            "Canonicalized {} scene-break lines to '{}'",
            stats.scene_breaks_normalized,
            SCENE_BREAK_SENTINEL,
        )

    return text


def clean_chapters(
    chapter_texts: list[str],
    config: CleaningConfig | None = None,
) -> list[str]:
    """Clean a list of chapter texts individually.

    Args:
        chapter_texts: List of raw chapter strings.
        config: Cleaning configuration. Uses defaults if None.

    Returns:
        List of cleaned chapter strings.
    """
    if config is None:
        config = CleaningConfig()

    cleaned: list[str] = []
    for idx, raw in enumerate(chapter_texts, start=1):
        logger.debug("Cleaning chapter {}/{}", idx, len(chapter_texts))
        cleaned.append(clean_text(raw, config))

    logger.info("Cleaned {} chapters", len(cleaned))
    return cleaned


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    sample = (
        "&amp; Some text with HTML entities &lt;b&gt;bold&lt;/b&gt;\n"
        "\n"
        "\u201cThis is an epigraph with fancy quotes,\u201d said the author.\n"
        "\u2014 Famous Person\n"
        "\n"
        "42\n"
        "\n"
        "Copyright \u00a9 2024 by Author Name\n"
        "All rights reserved.\n"
        "Published by Big Publisher\n"
        "\n"
        "Chapter I    1\n"
        "Chapter II   15\n"
        "Chapter III  42\n"
        "\n"
        "The actual story begins here. It was a dark and stormy night.\n"
        "\n"
        "* * *\n"
        "\n"
        "The next section continues with more\u00a0text and non-breaking spaces.\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "Too many blank lines above should be collapsed.\n"
    )

    logger.info("--- Raw text ---")
    print(repr(sample))
    print()

    result = clean_text(sample)
    logger.info("--- Cleaned text ---")
    print(result)
