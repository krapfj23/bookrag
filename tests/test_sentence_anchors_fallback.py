"""Regression tests for the booknlp/input.txt offset-alignment fix (Slice R1 REVISE).

The bug: load_chapter called build_paragraphs_anchored with byte offsets
computed from load_cleaned_full_text (chapter files joined with '\\n\\n'),
but BookNLP token byte_onset/byte_offset values are relative to
booknlp/input.txt, which the BookNLP runner prefixes with chapter-header
markers ('=== CHAPTER N ===\\n\\n').  The coordinate mismatch caused sentence
text to be sliced from the wrong position — producing garbage text or empty
strings — while build_paragraphs_anchored still returned ok=True, suppressing
the regex fallback.

The fix: load_chapter now prefers booknlp/input.txt as the coordinate space
for find_chapter_offsets and slices chapter_text from that file so that token
relative offsets are valid.
"""
from __future__ import annotations

from pathlib import Path

from api.loaders.book_data import load_chapter
from api.loaders.sentence_anchors import (
    load_booknlp_input_text,
)
from models.pipeline_state import PipelineState, save_state


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_CHAPTER_TEXT = (
    "Marley was dead, to begin with. There is no doubt about that.\n\n"
    "Scrooge knew he was dead. Of course he did."
)

# input.txt as BookNLP runner writes it: chapter header + chapter text
_HEADER = "=== CHAPTER 1 ===\n\n"
_INPUT_TXT = _HEADER + _CHAPTER_TEXT

# Correct byte offsets relative to _INPUT_TXT
_HEADER_LEN = len(_HEADER)   # 19
# "Marley" starts at 19, "dead," ends at ...
# Let's be precise with the token table:
#   "Marley was dead, to begin with." → 0..31  relative to chapter start
#   "There is no doubt about that."   → 32..62 relative to chapter start
#   "Scrooge knew he was dead."       → 64..89 relative (after \n\n = 63+1=64)
#   "Of course he did."               → 90..108

_TOKENS = [
    # paragraph 0, sentence 0: "Marley was dead, to begin with."
    # Offsets are relative to _INPUT_TXT (i.e., _HEADER_LEN + offset_in_chapter)
    {"paragraph_ID": 0, "sentence_ID": 0, "word": "Marley",  "byte_onset": _HEADER_LEN + 0,  "byte_offset": _HEADER_LEN + 6},
    {"paragraph_ID": 0, "sentence_ID": 0, "word": "was",     "byte_onset": _HEADER_LEN + 7,  "byte_offset": _HEADER_LEN + 10},
    {"paragraph_ID": 0, "sentence_ID": 0, "word": "dead",    "byte_onset": _HEADER_LEN + 11, "byte_offset": _HEADER_LEN + 15},
    # paragraph 0, sentence 1: "There is no doubt about that."
    {"paragraph_ID": 0, "sentence_ID": 1, "word": "There",   "byte_onset": _HEADER_LEN + 32, "byte_offset": _HEADER_LEN + 37},
    {"paragraph_ID": 0, "sentence_ID": 1, "word": "that",    "byte_onset": _HEADER_LEN + 56, "byte_offset": _HEADER_LEN + 60},
    # paragraph 1, sentence 2: "Scrooge knew he was dead."
    {"paragraph_ID": 1, "sentence_ID": 2, "word": "Scrooge", "byte_onset": _HEADER_LEN + 63, "byte_offset": _HEADER_LEN + 70},
    {"paragraph_ID": 1, "sentence_ID": 2, "word": "dead",    "byte_onset": _HEADER_LEN + 83, "byte_offset": _HEADER_LEN + 87},
    # paragraph 1, sentence 3: "Of course he did."
    {"paragraph_ID": 1, "sentence_ID": 3, "word": "Of",      "byte_onset": _HEADER_LEN + 89, "byte_offset": _HEADER_LEN + 91},
    {"paragraph_ID": 1, "sentence_ID": 3, "word": "did",     "byte_onset": _HEADER_LEN + 102, "byte_offset": _HEADER_LEN + 105},
]

def _write_tokens_tsv(path: Path, rows: list[dict]) -> None:
    """Write a minimal BookNLP-style TSV with the fields used by sentence_anchors."""
    fields = ["paragraph_ID", "sentence_ID", "word", "byte_onset", "byte_offset"]
    lines = ["\t".join(fields)]
    for r in rows:
        lines.append("\t".join(str(r.get(f, "")) for f in fields))
    path.write_text("\n".join(lines), encoding="utf-8")


def _setup_book(tmp_path: Path) -> tuple[Path, str]:
    """Write a minimal ready book with booknlp/input.txt and tokens file."""
    book_id = "test_book"
    book_dir = tmp_path / book_id
    chapters_dir = book_dir / "raw" / "chapters"
    chapters_dir.mkdir(parents=True)
    (chapters_dir / "chapter_01.txt").write_text(_CHAPTER_TEXT, encoding="utf-8")

    booknlp_dir = book_dir / "booknlp"
    booknlp_dir.mkdir()
    (booknlp_dir / "input.txt").write_text(_INPUT_TXT, encoding="utf-8")

    # Write tokens TSV with byte offsets relative to _INPUT_TXT
    tokens_path = booknlp_dir / f"{book_id}.tokens"
    _write_tokens_tsv(tokens_path, _TOKENS)

    state = PipelineState.new(book_id, ["parse_epub", "validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")

    return tmp_path, book_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBookNLPInputTxtOffsetAlignment:
    """Verify that load_chapter correctly aligns BookNLP byte offsets with
    booknlp/input.txt (which has chapter-header markers) rather than the
    naive chapter-concatenation from raw/chapters/.

    Before the fix, the mismatch of 'len(=== CHAPTER N ===\\n\\n)' bytes
    caused sentence text to be sliced from the wrong position in the
    chapter string, producing garbage.  After the fix the sentences contain
    the real words from _CHAPTER_TEXT.
    """

    def test_anchored_sentences_contain_real_words(self, tmp_path):
        processed_dir, book_id = _setup_book(tmp_path)
        chapter = load_chapter(book_id, 1, processed_dir)
        assert chapter is not None
        assert chapter.anchors_fallback is False, (
            "BookNLP reconciliation should succeed when input.txt is used "
            "for offset computation"
        )
        assert len(chapter.paragraphs_anchored) > 0

        all_sentence_texts = [
            s.text
            for para in chapter.paragraphs_anchored
            for s in para.sentences
        ]
        joined = " ".join(all_sentence_texts)
        assert "Marley" in joined, f"Expected 'Marley' in sentences, got: {joined!r}"
        assert "Scrooge" in joined, f"Expected 'Scrooge' in sentences, got: {joined!r}"
        # Guard against the pre-fix garbage: header text leaked into sentences
        assert "=== CHAPTER" not in joined, (
            "Chapter header marker leaked into sentence text — byte offsets "
            "are still aligned to the wrong coordinate space"
        )

    def test_first_paragraph_has_two_sentences(self, tmp_path):
        """Paragraph 0 has sentences 0+1 → two AnchoredSentences."""
        processed_dir, book_id = _setup_book(tmp_path)
        chapter = load_chapter(book_id, 1, processed_dir)
        assert chapter is not None
        assert chapter.anchors_fallback is False
        # First anchored paragraph should have 2 sentences
        first_para = chapter.paragraphs_anchored[0]
        assert len(first_para.sentences) == 2, (
            f"Expected 2 sentences in para 1, got {len(first_para.sentences)}: "
            f"{[s.text for s in first_para.sentences]}"
        )
        assert first_para.sentences[0].sid == "p1.s1"
        assert "Marley" in first_para.sentences[0].text

    def test_second_paragraph_has_two_sentences(self, tmp_path):
        """Paragraph 1 has sentences 2+3 → two AnchoredSentences."""
        processed_dir, book_id = _setup_book(tmp_path)
        chapter = load_chapter(book_id, 1, processed_dir)
        assert chapter is not None
        assert chapter.anchors_fallback is False
        second_para = chapter.paragraphs_anchored[1]
        assert len(second_para.sentences) == 2, (
            f"Expected 2 sentences in para 2, got {len(second_para.sentences)}: "
            f"{[s.text for s in second_para.sentences]}"
        )
        assert second_para.sentences[0].sid == "p2.s1"
        assert "Scrooge" in second_para.sentences[0].text

    def test_load_booknlp_input_text_returns_content(self, tmp_path):
        """load_booknlp_input_text loads booknlp/input.txt correctly."""
        processed_dir, book_id = _setup_book(tmp_path)
        content = load_booknlp_input_text(book_id, processed_dir)
        assert content is not None
        assert content == _INPUT_TXT

    def test_load_booknlp_input_text_missing_returns_none(self, tmp_path):
        """Returns None when input.txt does not exist."""
        result = load_booknlp_input_text("nonexistent_book", tmp_path)
        assert result is None


class TestFallbackWhenBookNLPFails:
    """When BookNLP reconciliation produces no usable rows the regex fallback
    must fire: paragraphs_anchored must be non-empty and anchors_fallback=True.

    This guards against a silent empty result where neither path succeeds.
    """

    def _setup_no_booknlp(self, tmp_path: Path) -> tuple[Path, str]:
        book_id = "no_booknlp_book"
        book_dir = tmp_path / book_id
        chapters_dir = book_dir / "raw" / "chapters"
        chapters_dir.mkdir(parents=True)
        (chapters_dir / "chapter_01.txt").write_text(_CHAPTER_TEXT, encoding="utf-8")
        # No booknlp directory → load_tokens_for_book returns None
        state = PipelineState.new(book_id, ["parse_epub", "validate"])
        state.status = "complete"
        state.ready_for_query = True
        save_state(state, book_dir / "pipeline_state.json")
        return tmp_path, book_id

    def test_fallback_fires_when_no_booknlp(self, tmp_path):
        processed_dir, book_id = self._setup_no_booknlp(tmp_path)
        chapter = load_chapter(book_id, 1, processed_dir)
        assert chapter is not None
        assert chapter.anchors_fallback is True
        assert len(chapter.paragraphs_anchored) == 2, (
            f"Regex fallback should produce 2 anchored paragraphs (one per \\n\\n block), "
            f"got {len(chapter.paragraphs_anchored)}"
        )
        assert len(chapter.paragraphs) == 2
        # Regex fallback should have the same paragraph count
        assert len(chapter.paragraphs_anchored) == len(chapter.paragraphs)

    def test_fallback_sentences_contain_real_words(self, tmp_path):
        processed_dir, book_id = self._setup_no_booknlp(tmp_path)
        chapter = load_chapter(book_id, 1, processed_dir)
        assert chapter is not None
        assert chapter.anchors_fallback is True
        all_texts = [s.text for p in chapter.paragraphs_anchored for s in p.sentences]
        joined = " ".join(all_texts)
        assert "Marley" in joined
        assert "Scrooge" in joined
