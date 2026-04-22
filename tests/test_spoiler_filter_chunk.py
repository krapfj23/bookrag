import json
from pathlib import Path


def _write_batch(tmp_path, book_id, batch_label, datapoints):
    d = tmp_path / book_id / "batches" / batch_label
    d.mkdir(parents=True, exist_ok=True)
    (d / "extracted_datapoints.json").write_text(json.dumps(datapoints))


def _write_chapter_index(tmp_path, book_id, idx_payload):
    d = tmp_path / book_id / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    (d / "chapter_to_chunk_index.json").write_text(json.dumps(idx_payload))


def test_load_allowed_nodes_by_chunk_respects_cursor(tmp_path):
    from pipeline.spoiler_filter import load_allowed_nodes_by_chunk

    _write_batch(tmp_path, "book", "batch_01", [
        {"type": "Character", "name": "A", "first_chapter": 1, "source_chunk_ordinal": 2},
        {"type": "Character", "name": "B", "first_chapter": 1, "source_chunk_ordinal": 5},
        {"type": "Character", "name": "C", "first_chapter": 2, "source_chunk_ordinal": 10},
    ])

    out = load_allowed_nodes_by_chunk("book", chunk_ordinal_cursor=5, processed_dir=tmp_path)
    names = sorted(n["name"] for n in out)
    assert names == ["A", "B"]


def test_load_allowed_nodes_shim_translates_chapter_to_ordinal(tmp_path):
    from pipeline.spoiler_filter import load_allowed_nodes, load_allowed_nodes_by_chunk

    _write_batch(tmp_path, "book", "batch_01", [
        {"type": "Character", "name": "A", "first_chapter": 1, "source_chunk_ordinal": 0},
        {"type": "Character", "name": "B", "first_chapter": 1, "source_chunk_ordinal": 3},
        {"type": "Character", "name": "C", "first_chapter": 2, "source_chunk_ordinal": 4},
    ])
    _write_chapter_index(tmp_path, "book", {
        "1": {"first_ordinal": 0, "last_ordinal": 3, "paragraph_breakpoints": [0, 1, 2, 3]},
        "2": {"first_ordinal": 4, "last_ordinal": 4, "paragraph_breakpoints": [0]},
    })

    by_chapter = sorted(n["name"] for n in load_allowed_nodes("book", cursor=1, processed_dir=tmp_path))
    by_ordinal = sorted(n["name"] for n in load_allowed_nodes_by_chunk("book", 3, tmp_path))
    assert by_chapter == by_ordinal == ["A", "B"]


def test_node_without_ordinal_falls_back_to_chapter(tmp_path):
    from pipeline.spoiler_filter import load_allowed_nodes_by_chunk

    _write_batch(tmp_path, "book", "batch_01", [
        {"type": "Character", "name": "A", "first_chapter": 1},  # no ordinal
        {"type": "Character", "name": "B", "first_chapter": 3},  # no ordinal
    ])
    _write_chapter_index(tmp_path, "book", {
        "1": {"first_ordinal": 0, "last_ordinal": 3, "paragraph_breakpoints": []},
        "2": {"first_ordinal": 4, "last_ordinal": 5, "paragraph_breakpoints": []},
        "3": {"first_ordinal": 6, "last_ordinal": 9, "paragraph_breakpoints": []},
    })

    # cursor=5 == end of chapter 2; chapter-fallback: chapter 1 yes, chapter 3 no
    out = load_allowed_nodes_by_chunk("book", chunk_ordinal_cursor=5, processed_dir=tmp_path)
    names = sorted(n["name"] for n in out)
    assert names == ["A"]
