"""Backfill chunk ordinals for books ingested before Slice 1.

Re-chunks each batch's input_text.txt (deterministic), assigns globally-monotonic
ordinals, writes chunks.json + chapter_to_chunk_index.json, stamps
source_chunk_ordinal on every DataPoint by substring-matching its description
against chunk text, and calls cognee.add() to index chunk text.

Usage:
    python -m scripts.backfill_chunk_ordinals --book christmas_carol_e6ddcd76
    python -m scripts.backfill_chunk_ordinals --all
    python -m scripts.backfill_chunk_ordinals --all --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from loguru import logger

import cognee

from pipeline.chunk_index import (
    CHUNKS_FILENAME,
    CHAPTER_INDEX_FILENAME,
    build_chunks_json,
    build_chapter_to_chunk_index,
)
from pipeline.cognee_pipeline import chunk_with_chapter_awareness, ChapterChunk


def _already_done(book_dir: Path) -> bool:
    return (book_dir / "chunks" / CHUNKS_FILENAME).exists() and (
        book_dir / "chunks" / CHAPTER_INDEX_FILENAME
    ).exists()


def _reconstruct_chunks(book_id: str, book_dir: Path, chunk_size: int = 1500) -> list[ChapterChunk]:
    """Re-chunk each batch's input_text.txt. Returns chunks with ordinals assigned."""
    batches_dir = book_dir / "batches"
    chunks_all: list[ChapterChunk] = []
    ordinal = 0
    for batch_subdir in sorted(batches_dir.glob("batch_*")):
        input_text = (batch_subdir / "input_text.txt").read_text(encoding="utf-8")
        # Chapter numbers from the batch label (batch_NN where NN is the first chapter)
        try:
            first_chapter = int(batch_subdir.name.split("_")[1])
        except (IndexError, ValueError):
            first_chapter = 1
        chunks = chunk_with_chapter_awareness(
            text=input_text,
            chunk_size=chunk_size,
            chapter_numbers=[first_chapter],
        )
        for c in chunks:
            c.ordinal = ordinal
            c.chunk_id = f"{book_id}::chunk_{ordinal:04d}"
            ordinal += 1
        chunks_all.extend(chunks)
    return chunks_all


def _stamp_datapoint_ordinals(
    book_id: str, book_dir: Path, chunks: list[ChapterChunk]
) -> tuple[int, int]:
    """Stamp source_chunk_ordinal on every DataPoint in batches/*/extracted_datapoints.json.

    Uses substring match: a DataPoint is assigned to the first chunk whose text
    contains its description (or its name, if description is empty). DataPoints
    that don't match fall back to last_ordinal of the chapter derived from
    first_chapter/chapter.

    Returns (total, matched).
    """
    chunks_sorted = sorted(chunks, key=lambda c: c.ordinal)

    def _find_ordinal(desc: str) -> int | None:
        if not desc:
            return None
        for c in chunks_sorted:
            if desc in c.text:
                return c.ordinal
        return None

    total = 0
    matched = 0
    for dp_file in sorted((book_dir / "batches").glob("batch_*/extracted_datapoints.json")):
        payload = json.loads(dp_file.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else payload.get("datapoints", [])
        for dp in items:
            if not isinstance(dp, dict):
                continue
            total += 1
            probe = dp.get("description") or dp.get("name") or ""
            ord_ = _find_ordinal(probe)
            if ord_ is None:
                # Chapter-level fallback: last chunk of that chapter
                ch = dp.get("first_chapter") or dp.get("chapter")
                if ch is not None:
                    matching = [c.ordinal for c in chunks_sorted if ch in c.chapter_numbers]
                    if matching:
                        ord_ = max(matching)
            if ord_ is not None:
                dp["source_chunk_ordinal"] = ord_
                matched += 1
        if isinstance(payload, list):
            dp_file.write_text(json.dumps(items, indent=2))
        else:
            payload["datapoints"] = items
            dp_file.write_text(json.dumps(payload, indent=2))
    return total, matched


async def _index_chunks_in_cognee(book_id: str, chunks: list[ChapterChunk]) -> None:
    """Call cognee.add for every chunk so CHUNKS / RAG_COMPLETION have text."""
    for c in chunks:
        try:
            await cognee.add(
                data=c.text,
                dataset_name=book_id,
                node_set=[c.chunk_id],
            )
        except Exception as exc:
            logger.warning("cognee.add failed for {}: {}", c.chunk_id, exc)


async def backfill_book(book_id: str, processed_dir: Path, force: bool = False) -> None:
    book_dir = Path(processed_dir) / book_id
    if not book_dir.exists():
        logger.warning("Book dir {} does not exist — skipping", book_dir)
        return
    if _already_done(book_dir) and not force:
        logger.info("{} already has chunk indexes — skipping (use --force to overwrite)", book_id)
        return

    logger.info("Backfilling {} ...", book_id)
    chunks = _reconstruct_chunks(book_id, book_dir)
    if not chunks:
        logger.warning("No chunks reconstructed for {} — aborting", book_id)
        return

    build_chunks_json(
        book_id=book_id, chunks=chunks, chunk_size_tokens=1500,
        output_dir=processed_dir,
    )
    build_chapter_to_chunk_index(
        book_id=book_id, chunks=chunks, processed_dir=processed_dir,
    )

    total, matched = _stamp_datapoint_ordinals(book_id, book_dir, chunks)
    logger.info("Stamped {}/{} DataPoints with source_chunk_ordinal", matched, total)

    await _index_chunks_in_cognee(book_id, chunks)
    logger.info("Backfill complete for {}", book_id)


def _all_books(processed_dir: Path) -> list[str]:
    return sorted(p.name for p in processed_dir.iterdir() if p.is_dir())


async def _main_async(book_ids: list[str], processed_dir: Path, force: bool) -> None:
    for bid in book_ids:
        await backfill_book(bid, processed_dir, force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill chunk ordinals.")
    parser.add_argument("--book", help="Specific book_id to backfill")
    parser.add_argument("--all", action="store_true", help="Backfill every book")
    parser.add_argument("--force", action="store_true", help="Overwrite existing indexes")
    parser.add_argument(
        "--processed-dir", default="data/processed",
        help="Top-level processed dir (default: data/processed)",
    )
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    if args.all:
        books = _all_books(processed_dir)
    elif args.book:
        books = [args.book]
    else:
        parser.error("Provide --book <id> or --all")
        return  # pragma: no cover

    asyncio.run(_main_async(books, processed_dir, force=args.force))


if __name__ == "__main__":
    main()
