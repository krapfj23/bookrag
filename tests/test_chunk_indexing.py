import json
from pathlib import Path

from pipeline.chunk_index import (
    build_chunks_json,
    build_chapter_to_chunk_index,
    load_chunks,
    load_chapter_index,
    chapter_paragraph_to_ordinal,
    ChunkRecord,
)
from pipeline.cognee_pipeline import ChapterChunk


def _chunks(*tuples) -> list[ChapterChunk]:
    return [
        ChapterChunk(
            text=text, chapter_numbers=chs, start_char=sc, end_char=ec,
            ordinal=ordinal, chunk_id=f"book::chunk_{ordinal:04d}",
        )
        for (text, chs, sc, ec, ordinal) in tuples
    ]


def test_build_chunks_json_monotonic_ordinals(tmp_path):
    chunks = _chunks(
        ("a" * 100, [1], 0, 100, 0),
        ("b" * 100, [1], 100, 200, 1),
        ("c" * 100, [2], 0, 100, 2),
    )
    out = build_chunks_json("book", chunks, chunk_size_tokens=1500, output_dir=tmp_path)
    payload = json.loads(Path(out).read_text())
    assert payload["total_chunks"] == 3
    assert [c["ordinal"] for c in payload["chunks"]] == [0, 1, 2]
    assert payload["chunks"][0]["chunk_id"] == "book::chunk_0000"


def test_build_chapter_to_chunk_index_bounds(tmp_path):
    chunks = _chunks(
        ("x", [1], 0, 10, 0),
        ("y", [1], 10, 20, 1),
        ("z", [2], 0, 10, 2),
    )
    # Fake chapter raw text so paragraph_breakpoints can be computed.
    raw_dir = tmp_path / "book" / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text("p0\n\np1\n\np2")
    (raw_dir / "chapter_02.txt").write_text("q0")

    out = build_chapter_to_chunk_index("book", chunks, processed_dir=tmp_path)
    idx = json.loads(Path(out).read_text())
    assert idx["1"]["first_ordinal"] == 0
    assert idx["1"]["last_ordinal"] == 1
    assert idx["2"]["first_ordinal"] == 2
    assert idx["2"]["last_ordinal"] == 2
    # paragraph_breakpoints length equals number of paragraphs in raw
    assert len(idx["1"]["paragraph_breakpoints"]) == 3
    assert len(idx["2"]["paragraph_breakpoints"]) == 1


def test_cross_chapter_chunk_assigned_to_start_chapter(tmp_path):
    # Chunk spans chapters [1, 2] but start_char places it in chapter 1.
    chunks = _chunks(("spans", [1, 2], 0, 50, 0))
    raw_dir = tmp_path / "book" / "raw" / "chapters"
    raw_dir.mkdir(parents=True)
    (raw_dir / "chapter_01.txt").write_text("p0")
    (raw_dir / "chapter_02.txt").write_text("p0")
    out = build_chapter_to_chunk_index("book", chunks, processed_dir=tmp_path)
    idx = json.loads(Path(out).read_text())
    assert idx["1"]["first_ordinal"] == 0
    assert idx["1"]["last_ordinal"] == 0
    assert "2" not in idx or idx["2"].get("first_ordinal") is None


def test_chapter_paragraph_to_ordinal_maps_correctly(tmp_path):
    # Build an index manually and verify the translator.
    idx_payload = {
        "1": {"first_ordinal": 0, "last_ordinal": 4, "paragraph_breakpoints": [0, 1, 2, 3, 4]},
        "2": {"first_ordinal": 5, "last_ordinal": 9, "paragraph_breakpoints": [0, 2, 4]},
    }
    idx_dir = tmp_path / "book" / "chunks"
    idx_dir.mkdir(parents=True)
    (idx_dir / "chapter_to_chunk_index.json").write_text(json.dumps(idx_payload))

    # chapter 2, paragraph 0 → first_ordinal(2) + breakpoints[0] = 5 + 0 = 5
    assert chapter_paragraph_to_ordinal("book", 2, 0, processed_dir=tmp_path) == 5
    # chapter 2, paragraph 1 → 5 + 2 = 7
    assert chapter_paragraph_to_ordinal("book", 2, 1, processed_dir=tmp_path) == 7
    # chapter 1, no paragraph → last_ordinal(1) = 4
    assert chapter_paragraph_to_ordinal("book", 1, None, processed_dir=tmp_path) == 4
    # chapter 3 not present → None
    assert chapter_paragraph_to_ordinal("book", 3, 0, processed_dir=tmp_path) is None


def test_load_chunks_missing_returns_empty(tmp_path):
    assert load_chunks("book", processed_dir=tmp_path) == []


def test_load_chapter_index_missing_returns_empty(tmp_path):
    assert load_chapter_index("book", processed_dir=tmp_path) == {}
