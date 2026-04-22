"""Tests for sentence-anchored chapter loader (Slice R1, AC 1–3)."""
from __future__ import annotations

from pathlib import Path

from api.loaders.book_data import load_chapter
from api.loaders.sentence_anchors import (
    build_paragraphs_anchored,
    regex_fallback_paragraphs,
)
from models.pipeline_state import PipelineState, save_state


CH1 = (
    "Marley was dead, to begin with. There is no doubt about that.\n\n"
    "Scrooge knew he was dead. Of course he did. He was his partner."
)


def _ready(processed: Path, book_id: str) -> Path:
    book = processed / book_id
    (book / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book / "raw" / "chapters" / "chapter_01.txt").write_text(CH1, encoding="utf-8")
    s = PipelineState.new(book_id, ["parse_epub", "validate"])
    s.status = "complete"
    s.ready_for_query = True
    save_state(s, book / "pipeline_state.json")
    return book


def test_regex_fallback_produces_anchored_paragraphs(tmp_path):
    paragraphs = [
        "Marley was dead, to begin with. There is no doubt about that.",
        "Scrooge knew he was dead. Of course he did. He was his partner.",
    ]
    anchored = regex_fallback_paragraphs(paragraphs)
    assert len(anchored) == 2
    assert [s.sid for s in anchored[0].sentences] == ["p1.s1", "p1.s2"]
    assert anchored[0].sentences[0].text.startswith("Marley was dead")
    assert [s.sid for s in anchored[1].sentences] == ["p2.s1", "p2.s2", "p2.s3"]


def test_load_chapter_includes_paragraphs_anchored_and_fallback_flag(tmp_path):
    _ready(tmp_path, "carol")
    chapter = load_chapter("carol", 1, tmp_path)
    assert chapter is not None
    # Existing fields unchanged.
    assert chapter.num == 1
    assert chapter.has_prev is False
    assert chapter.total_chapters == 1
    assert len(chapter.paragraphs) == 2
    # New fields.
    assert chapter.anchors_fallback is True  # no BookNLP run → fallback
    assert len(chapter.paragraphs_anchored) == 2
    first = chapter.paragraphs_anchored[0]
    assert first.paragraph_idx == 1
    assert first.sentences[0].sid == "p1.s1"
    assert first.sentences[1].sid == "p1.s2"
    second = chapter.paragraphs_anchored[1]
    assert second.paragraph_idx == 2
    assert [s.sid for s in second.sentences] == ["p2.s1", "p2.s2", "p2.s3"]


def test_build_paragraphs_anchored_from_tokens(tmp_path):
    # Simulated .tokens rows: paragraph_ID + sentence_ID + byte offsets.
    tokens = [
        {"paragraph_ID": 0, "sentence_ID": 0, "word": "Marley",   "byte_onset": 0,  "byte_offset": 6},
        {"paragraph_ID": 0, "sentence_ID": 0, "word": "was",      "byte_onset": 7,  "byte_offset": 10},
        {"paragraph_ID": 0, "sentence_ID": 0, "word": "dead.",    "byte_onset": 11, "byte_offset": 16},
        {"paragraph_ID": 0, "sentence_ID": 1, "word": "No",       "byte_onset": 17, "byte_offset": 19},
        {"paragraph_ID": 0, "sentence_ID": 1, "word": "doubt.",   "byte_onset": 20, "byte_offset": 26},
        {"paragraph_ID": 1, "sentence_ID": 2, "word": "Scrooge",  "byte_onset": 28, "byte_offset": 35},
        {"paragraph_ID": 1, "sentence_ID": 2, "word": "knew.",    "byte_onset": 36, "byte_offset": 41},
    ]
    text = "Marley was dead. No doubt.\n\nScrooge knew."
    anchored, ok = build_paragraphs_anchored(text, tokens, chapter_start=0, chapter_end=len(text))
    assert ok is True
    assert [p.paragraph_idx for p in anchored] == [1, 2]
    assert [s.sid for s in anchored[0].sentences] == ["p1.s1", "p1.s2"]
    assert anchored[0].sentences[0].text.startswith("Marley was dead")
    assert [s.sid for s in anchored[1].sentences] == ["p2.s1"]
