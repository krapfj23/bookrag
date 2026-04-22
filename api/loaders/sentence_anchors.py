"""Derive sentence-anchored paragraphs for a chapter.

Strategy:
  1. If a BookNLP .tokens file exists for the book and its byte offsets
     reconcile with the chapter's cleaned text, group tokens by
     paragraph_ID then sentence_ID and emit p{n}.s{m} ids.
  2. Otherwise, split each paragraph string on a sentence-ending regex
     and emit p{n}.s{m} ids; set anchors_fallback=True.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


class AnchoredSentence(BaseModel):
    sid: str
    text: str


class AnchoredParagraph(BaseModel):
    paragraph_idx: int
    sentences: list[AnchoredSentence]


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z\"'(\[])")


def regex_fallback_paragraphs(paragraphs: list[str]) -> list[AnchoredParagraph]:
    out: list[AnchoredParagraph] = []
    for p_idx, para in enumerate(paragraphs, start=1):
        parts = [s.strip() for s in _SENT_SPLIT_RE.split(para) if s.strip()]
        if not parts:
            parts = [para.strip()]
        sents = [
            AnchoredSentence(sid=f"p{p_idx}.s{s_idx}", text=t)
            for s_idx, t in enumerate(parts, start=1)
        ]
        out.append(AnchoredParagraph(paragraph_idx=p_idx, sentences=sents))
    return out


def build_paragraphs_anchored(
    chapter_text: str,
    token_rows: Iterable[dict],
    chapter_start: int,
    chapter_end: int,
) -> tuple[list[AnchoredParagraph], bool]:
    """Return (anchored, ok). ok=False means caller should fall back."""
    # Filter tokens whose byte range lies inside the chapter slice.
    rows: list[dict] = []
    for r in token_rows:
        try:
            bo = int(r.get("byte_onset", r.get("start_char", -1)))
            be = int(r.get("byte_offset", r.get("end_char", -1)))
        except (TypeError, ValueError):
            continue
        if bo < 0 or be < 0:
            continue
        if bo >= chapter_start and be <= chapter_end:
            rows.append({**r, "_bo": bo, "_be": be})

    if not rows:
        return [], False

    # Group by paragraph_ID (preserve order of first appearance).
    para_order: list[int] = []
    by_para: dict[int, list[dict]] = {}
    for r in rows:
        try:
            pid = int(r.get("paragraph_ID", r.get("paragraph_id", -1)))
        except (TypeError, ValueError):
            return [], False
        if pid < 0:
            return [], False
        if pid not in by_para:
            by_para[pid] = []
            para_order.append(pid)
        by_para[pid].append(r)

    anchored: list[AnchoredParagraph] = []
    for p_idx, pid in enumerate(para_order, start=1):
        # Group this paragraph's tokens by sentence_ID preserving order.
        sent_order: list[int] = []
        by_sent: dict[int, list[dict]] = {}
        for r in by_para[pid]:
            try:
                sid = int(r.get("sentence_ID", r.get("sentence_id", -1)))
            except (TypeError, ValueError):
                return [], False
            if sid < 0:
                return [], False
            if sid not in by_sent:
                by_sent[sid] = []
                sent_order.append(sid)
            by_sent[sid].append(r)
        sentences: list[AnchoredSentence] = []
        for s_idx, sid in enumerate(sent_order, start=1):
            toks = by_sent[sid]
            s_bo = min(t["_bo"] for t in toks) - chapter_start
            s_be = max(t["_be"] for t in toks) - chapter_start
            s_bo = max(0, s_bo)
            s_be = min(len(chapter_text), s_be)
            text = chapter_text[s_bo:s_be].strip()
            if not text:
                # Could not slice text back — signal fallback.
                return [], False
            sentences.append(AnchoredSentence(sid=f"p{p_idx}.s{s_idx}", text=text))
        if sentences:
            anchored.append(AnchoredParagraph(paragraph_idx=p_idx, sentences=sentences))

    if not anchored:
        return [], False
    return anchored, True


def find_chapter_offsets(full_text: str, chapter_text: str) -> tuple[int, int] | None:
    """Locate chapter_text inside full_text. Returns (start, end) bytes or None."""
    start = full_text.find(chapter_text)
    if start < 0:
        return None
    return start, start + len(chapter_text)


def load_tokens_for_book(book_id: str, processed_dir: Path) -> list[dict] | None:
    booknlp_dir = processed_dir / book_id / "booknlp"
    if not booknlp_dir.exists():
        return None
    # The BookNLP runner writes {book_id}.tokens; see booknlp_runner.run_booknlp.
    candidate = booknlp_dir / f"{book_id}.tokens"
    if not candidate.exists():
        matches = list(booknlp_dir.glob("*.tokens"))
        if not matches:
            return None
        candidate = matches[0]
    from pipeline.tsv_utils import read_tsv
    return read_tsv(candidate)


def load_cleaned_full_text(book_id: str, processed_dir: Path) -> str | None:
    """Reconstruct cleaned full text by concatenating chapter_*.txt."""
    chapters_dir = processed_dir / book_id / "raw" / "chapters"
    if not chapters_dir.exists():
        return None
    parts: list[str] = []
    for p in sorted(chapters_dir.glob("chapter_*.txt")):
        parts.append(p.read_text(encoding="utf-8"))
    return "\n\n".join(parts) if parts else None


def load_booknlp_input_text(book_id: str, processed_dir: Path) -> str | None:
    """Load the raw text that BookNLP actually processed (booknlp/input.txt).

    BookNLP token byte offsets are relative to this file, NOT to the
    reconstructed chapter concatenation from raw/chapters/.  Using this
    text for offset arithmetic ensures sentence slicing is accurate.
    Returns None if the file does not exist.
    """
    input_path = processed_dir / book_id / "booknlp" / "input.txt"
    if not input_path.exists():
        return None
    return input_path.read_text(encoding="utf-8")
