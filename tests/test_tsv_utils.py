"""Tests for pipeline/tsv_utils.py — shared TSV parsing utilities.

Covers:
- read_tsv: valid TSV, empty file, headers only, blank lines skipped, single column
- safe_int: valid ints, invalid strings, None, empty string

These functions were extracted from pipeline/booknlp_runner.py to eliminate
duplicate TSV parsing logic between booknlp_runner and orchestrator.

Aligned with:
- CLAUDE.md: BookNLP output files are TSV format
- Plan: "Extract shared TSV utilities into pipeline/tsv_utils.py"
"""
from __future__ import annotations

import pytest

from pipeline.tsv_utils import read_tsv, safe_int


# ---------------------------------------------------------------------------
# read_tsv
# ---------------------------------------------------------------------------

class TestReadTsv:
    """Tests for the shared TSV reader used by all BookNLP file parsers."""

    def test_valid_tsv(self, tmp_path):
        f = tmp_path / "test.tsv"
        f.write_text("col1\tcol2\na\tb\nc\td\n")
        rows = read_tsv(f)
        assert len(rows) == 2
        assert rows[0] == {"col1": "a", "col2": "b"}
        assert rows[1] == {"col1": "c", "col2": "d"}

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.tsv"
        f.write_text("")
        assert read_tsv(f) == []

    def test_headers_only(self, tmp_path):
        f = tmp_path / "headers.tsv"
        f.write_text("col1\tcol2\n")
        assert read_tsv(f) == []

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "blanks.tsv"
        f.write_text("col1\tcol2\na\tb\n\nc\td\n")
        rows = read_tsv(f)
        assert len(rows) == 2

    def test_single_column(self, tmp_path):
        f = tmp_path / "single.tsv"
        f.write_text("name\nAlice\nBob\n")
        rows = read_tsv(f)
        assert len(rows) == 2
        assert rows[0] == {"name": "Alice"}

    def test_booknlp_entities_format(self, tmp_path):
        """Realistic BookNLP .entities TSV with COREF, start_token, etc."""
        f = tmp_path / "entities.tsv"
        f.write_text(
            "COREF\tstart_token\tend_token\tprop\tcat\ttext\n"
            "0\t10\t11\tPROP\tPER\tScrooge\n"
            "1\t80\t82\tPROP\tPER\tBob Cratchit\n"
        )
        rows = read_tsv(f)
        assert len(rows) == 2
        assert rows[0]["COREF"] == "0"
        assert rows[0]["text"] == "Scrooge"
        assert rows[1]["text"] == "Bob Cratchit"

    def test_mismatched_columns_no_crash(self, tmp_path):
        """Rows with fewer values than headers should still parse (missing cols omitted)."""
        f = tmp_path / "short.tsv"
        f.write_text("a\tb\tc\n1\t2\n")
        rows = read_tsv(f)
        assert len(rows) == 1
        assert rows[0] == {"a": "1", "b": "2"}


# ---------------------------------------------------------------------------
# safe_int
# ---------------------------------------------------------------------------

class TestSafeInt:
    """Tests for the integer parser that returns -1 on failure."""

    def test_valid_positive(self):
        assert safe_int("42") == 42

    def test_valid_zero(self):
        assert safe_int("0") == 0

    def test_valid_negative(self):
        assert safe_int("-1") == -1

    def test_invalid_string(self):
        assert safe_int("abc") == -1

    def test_empty_string(self):
        assert safe_int("") == -1

    def test_none(self):
        assert safe_int(None) == -1

    def test_float_string(self):
        assert safe_int("3.14") == -1

    def test_whitespace(self):
        assert safe_int("  ") == -1


# ---------------------------------------------------------------------------
# Integration: verify booknlp_runner uses these shared functions
# ---------------------------------------------------------------------------

class TestSharedUsage:
    """Verify that booknlp_runner imports from tsv_utils (not its own copy)."""

    def test_booknlp_runner_uses_shared_read_tsv(self):
        from pipeline import booknlp_runner
        assert booknlp_runner.read_tsv is read_tsv

    def test_booknlp_runner_uses_shared_safe_int(self):
        from pipeline import booknlp_runner
        assert booknlp_runner.safe_int is safe_int


# ---------------------------------------------------------------------------
# Integration: verify EntityMention is unified
# ---------------------------------------------------------------------------

class TestUnifiedEntityMention:
    """Verify coref_resolver uses the same EntityMention as booknlp_runner."""

    def test_same_class(self):
        from pipeline.booknlp_runner import EntityMention as BNLPEntityMention
        from pipeline.coref_resolver import EntityMention as CorefEntityMention
        assert BNLPEntityMention is CorefEntityMention

    def test_coref_resolver_entity_has_char_offsets(self):
        """The unified EntityMention has start_char/end_char with defaults."""
        from pipeline.coref_resolver import EntityMention
        em = EntityMention(coref_id=1, start_token=0, end_token=1, prop="PRON", cat="PER", text="he")
        assert em.start_char == 0
        assert em.end_char == 0
