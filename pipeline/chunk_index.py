"""Chunk-level indexing and translation helpers.

Two on-disk artifacts are produced at ingestion time (or by the backfill script):

  data/processed/{book_id}/chunks/chunks.json
  data/processed/{book_id}/chunks/chapter_to_chunk_index.json

They let the query path translate the reader's (chapter, paragraph) progress
into a stable ``chunk_ordinal`` that every DataPoint is also stamped with,
enabling chunk-uniform spoiler filtering.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from pipeline.cognee_pipeline import ChapterChunk

CHUNKS_FILENAME = "chunks.json"
CHAPTER_INDEX_FILENAME = "chapter_to_chunk_index.json"


@dataclass
class ChunkRecord:
    ordinal: int
    chunk_id: str
    batch_label: str
    chapter_numbers: list[int]
    start_char: int
    end_char: int
    text: str

    def to_dict(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "chunk_id": self.chunk_id,
            "batch_label": self.batch_label,
            "chapter_numbers": list(self.chapter_numbers),
            "start_char": self.start_char,
            "end_char": self.end_char,
            "text": self.text,
        }


def _chunks_dir(book_id: str, processed_dir: Path) -> Path:
    d = Path(processed_dir) / book_id / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_chunks_json(
    book_id: str,
    chunks: list[ChapterChunk],
    chunk_size_tokens: int,
    output_dir: Path | str,
    batch_label_lookup: dict[int, str] | None = None,
) -> Path:
    """Persist chunks.json. `output_dir` is the top-level processed dir."""
    out_dir = _chunks_dir(book_id, Path(output_dir))
    records = []
    for c in chunks:
        if c.ordinal is None or c.chunk_id is None:
            raise ValueError(f"Chunk missing ordinal/chunk_id: {c}")
        label = (batch_label_lookup or {}).get(c.ordinal, "")
        records.append(
            ChunkRecord(
                ordinal=c.ordinal,
                chunk_id=c.chunk_id,
                batch_label=label,
                chapter_numbers=c.chapter_numbers,
                start_char=c.start_char,
                end_char=c.end_char,
                text=c.text,
            ).to_dict()
        )
    records.sort(key=lambda r: r["ordinal"])
    payload = {
        "book_id": book_id,
        "chunk_size_tokens": chunk_size_tokens,
        "total_chunks": len(records),
        "chunks": records,
    }
    out = out_dir / CHUNKS_FILENAME
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    logger.info("Wrote {} with {} chunks", out, len(records))
    return out


def build_chapter_to_chunk_index(
    book_id: str,
    chunks: list[ChapterChunk],
    processed_dir: Path | str,
) -> Path:
    """Persist chapter_to_chunk_index.json.

    Assigns each chunk to the chapter where its start_char falls (the first
    entry in ``chapter_numbers``). Walks raw/chapters/chapter_NN.txt to compute
    paragraph_breakpoints for each chapter: for each paragraph index p, the
    ordinal (relative to first_ordinal) of the chunk that contains it.
    """
    out_dir = _chunks_dir(book_id, Path(processed_dir))
    book_dir = Path(processed_dir) / book_id

    per_chapter: dict[int, list[ChapterChunk]] = {}
    for c in chunks:
        if c.ordinal is None:
            raise ValueError(f"Chunk missing ordinal: {c}")
        start_chapter = c.chapter_numbers[0] if c.chapter_numbers else None
        if start_chapter is None:
            continue
        per_chapter.setdefault(int(start_chapter), []).append(c)

    idx: dict[str, dict] = {}
    raw_chapters_dir = book_dir / "raw" / "chapters"

    for chapter_num in sorted(per_chapter.keys()):
        cs = sorted(per_chapter[chapter_num], key=lambda x: x.ordinal)
        first_ordinal = cs[0].ordinal
        last_ordinal = cs[-1].ordinal

        breakpoints: list[int] = []
        raw_file = raw_chapters_dir / f"chapter_{chapter_num:02d}.txt"
        if raw_file.exists():
            raw_text = raw_file.read_text(encoding="utf-8")
            paragraphs = raw_text.split("\n\n")
            # For each paragraph's start_char within this chapter, find the chunk
            # whose [start_char, end_char) contains it.
            cursor = 0
            for para in paragraphs:
                rel = 0
                for c in cs:
                    if c.start_char <= cursor < c.end_char:
                        rel = c.ordinal - first_ordinal
                        break
                    if c.start_char > cursor:
                        rel = max(0, c.ordinal - first_ordinal - 1)
                        break
                else:
                    rel = last_ordinal - first_ordinal
                breakpoints.append(rel)
                cursor += len(para) + 2  # +2 for the "\n\n" separator
        else:
            logger.warning(
                "Raw chapter file {} missing — paragraph_breakpoints left empty",
                raw_file,
            )

        idx[str(chapter_num)] = {
            "first_ordinal": first_ordinal,
            "last_ordinal": last_ordinal,
            "paragraph_breakpoints": breakpoints,
        }

    out = out_dir / CHAPTER_INDEX_FILENAME
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    logger.info("Wrote {} with {} chapter entries", out, len(idx))
    return out


def load_chunks(book_id: str, processed_dir: Path | str) -> list[dict]:
    path = Path(processed_dir) / book_id / "chunks" / CHUNKS_FILENAME
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load {}: {}", path, exc)
        return []
    return payload.get("chunks", [])


def load_chapter_index(book_id: str, processed_dir: Path | str) -> dict:
    path = Path(processed_dir) / book_id / "chunks" / CHAPTER_INDEX_FILENAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load {}: {}", path, exc)
        return {}


def chapter_paragraph_to_ordinal(
    book_id: str,
    chapter: int,
    paragraph: int | None,
    processed_dir: Path | str,
) -> int | None:
    """Translate (chapter, paragraph?) to a chunk ordinal.

    Returns None if the chapter is not indexed.
    - paragraph=None → last_ordinal of the chapter (inclusive chapter-level cursor).
    - paragraph=i → first_ordinal + paragraph_breakpoints[i] (clamped).
    """
    idx = load_chapter_index(book_id, processed_dir)
    entry = idx.get(str(chapter))
    if entry is None:
        return None
    first_ordinal = entry["first_ordinal"]
    last_ordinal = entry["last_ordinal"]
    if paragraph is None:
        return last_ordinal
    breakpoints = entry.get("paragraph_breakpoints", [])
    if not breakpoints:
        return last_ordinal
    idx_safe = max(0, min(paragraph, len(breakpoints) - 1))
    return first_ordinal + breakpoints[idx_safe]


def ordinal_to_chapter(
    book_id: str,
    ordinal: int,
    processed_dir: Path | str,
) -> int | None:
    """Reverse lookup: which chapter contains this ordinal?"""
    idx = load_chapter_index(book_id, processed_dir)
    for chapter_str, entry in idx.items():
        if entry["first_ordinal"] <= ordinal <= entry["last_ordinal"]:
            return int(chapter_str)
    return None


def chapter_strictly_before_ordinal(
    book_id: str,
    chapter: int,
    processed_dir: Path | str,
) -> int:
    """Return the largest ordinal strictly before `chapter` (used when the
    paragraph cursor excludes the current chapter from the graph).

    If chapter is 1 or not indexed, returns -1 (empty allowed set).
    """
    idx = load_chapter_index(book_id, processed_dir)
    entry = idx.get(str(chapter))
    if entry is None:
        # Chapter not indexed — assume all prior chapters are allowed.
        prior = [int(v["last_ordinal"]) for k, v in idx.items() if int(k) < chapter]
        return max(prior) if prior else -1
    return entry["first_ordinal"] - 1
