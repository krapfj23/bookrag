import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest


def _seed_book(tmp_path: Path, book_id: str = "book") -> Path:
    """Create a minimal processed book dir with one batch + input_text."""
    book_dir = tmp_path / book_id
    batch_dir = book_dir / "batches" / "batch_01"
    batch_dir.mkdir(parents=True)

    # Input text long enough to produce >= 1 chunk at chunk_size=1500
    text = "Scrooge sat in his counting-house. " * 500
    (batch_dir / "input_text.txt").write_text(text)

    # A couple of DataPoints whose descriptions contain substrings of the text
    dps = [
        {"type": "Character", "name": "Scrooge", "first_chapter": 1,
         "description": "Scrooge sat in his counting-house."},
        {"type": "Location", "name": "Counting-house", "first_chapter": 1,
         "description": "the counting-house"},
    ]
    (batch_dir / "extracted_datapoints.json").write_text(json.dumps(dps))

    # Raw chapter 1 — needed by chapter_to_chunk_index
    raw_dir = book_dir / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text(text)

    # Mark the book as ready
    (book_dir / "pipeline_state.json").write_text(json.dumps({
        "book_id": book_id, "ready_for_query": True,
    }))

    return book_dir


def test_backfill_writes_chunk_indexes(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    book_dir = _seed_book(tmp_path)

    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))

    chunks_path = book_dir / "chunks" / "chunks.json"
    idx_path = book_dir / "chunks" / "chapter_to_chunk_index.json"
    assert chunks_path.exists()
    assert idx_path.exists()

    chunks_payload = json.loads(chunks_path.read_text())
    assert chunks_payload["total_chunks"] >= 1


def test_backfill_stamps_ordinals_on_datapoints(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    book_dir = _seed_book(tmp_path)
    dp_file = book_dir / "batches" / "batch_01" / "extracted_datapoints.json"
    before = json.loads(dp_file.read_text())
    assert all("source_chunk_ordinal" not in dp for dp in before)

    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))

    after = json.loads(dp_file.read_text())
    stamped = sum(1 for dp in after if dp.get("source_chunk_ordinal") is not None)
    assert stamped >= len(after) * 0.9  # >= 90%


def test_backfill_is_idempotent(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    _seed_book(tmp_path)
    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))
        first_call_count = mock_cognee.add.await_count
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))
        assert mock_cognee.add.await_count == first_call_count  # skipped


def test_backfill_force_overwrites(tmp_path):
    from scripts.backfill_chunk_ordinals import backfill_book

    _seed_book(tmp_path)
    with patch("scripts.backfill_chunk_ordinals.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        import asyncio
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=False))
        before_calls = mock_cognee.add.await_count
        asyncio.run(backfill_book("book", processed_dir=tmp_path, force=True))
        assert mock_cognee.add.await_count > before_calls
