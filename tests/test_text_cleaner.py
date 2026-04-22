"""Comprehensive tests for pipeline/text_cleaner.py.

Covers:
- CleaningConfig: all defaults, all toggles
- HTML entity replacement (&amp; &lt; &#169; etc.)
- Non-breaking space replacement
- Unicode quote normalization (left/right double/single, guillemets, en/em dash, ellipsis)
- Page number removal (standalone number lines)
- Copyright boilerplate removal (all 8 patterns + blank-line continuation)
- TOC removal (consecutive "Chapter X  N" lines, single-line false positive guard)
- Section break preservation/removal
- Epigraph protection (quoted text in first 20 lines, em-dash attribution)
- Whitespace normalization (trailing, 3+ blank lines → 2)
- clean_chapters batch function
- Config toggles: strip_html=False, remove_toc=False, remove_copyright=False,
  keep_epigraphs=False, keep_section_breaks=False

Alignment with plan docs:
- CLAUDE.md: "Moderate cleaning — strip HTML + obvious junk, keep epigraphs and section breaks"
- bookrag_pipeline_plan.md: config.yaml cleaning section matches CleaningConfig defaults
- bookrag_deep_research_context.md: Section 5 Gap #5 — moderate aggressiveness
"""
from __future__ import annotations

import pytest

from pipeline.text_cleaner import (
    CleaningConfig,
    CleaningStats,
    clean_text,
    clean_chapters,
    _replace_html_entities,
    _replace_nbsp,
    _normalize_unicode_quotes,
    _remove_page_numbers,
    _remove_copyright,
    _remove_toc,
    _protect_epigraphs,
    _restore_epigraphs,
    _normalize_whitespace,
)


# ============================================================================
# CleaningConfig tests
# ============================================================================

class TestCleaningConfig:
    """Verify defaults match plan's config.yaml cleaning section."""

    def test_defaults_match_plan(self):
        """Per bookrag_pipeline_plan.md config.yaml:
        strip_html: true, remove_toc: true, remove_copyright: true,
        keep_epigraphs: true, keep_section_breaks: true
        """
        cfg = CleaningConfig()
        assert cfg.strip_html is True
        assert cfg.remove_toc is True
        assert cfg.remove_copyright is True
        assert cfg.keep_epigraphs is True
        assert cfg.keep_section_breaks is True

    def test_all_toggleable(self):
        cfg = CleaningConfig(
            strip_html=False,
            remove_toc=False,
            remove_copyright=False,
            keep_epigraphs=False,
            keep_section_breaks=False,
        )
        assert cfg.strip_html is False
        assert cfg.remove_toc is False


# ============================================================================
# HTML entity replacement
# ============================================================================

class TestHTMLEntityReplacement:

    def test_named_entities(self):
        stats = CleaningStats()
        result = _replace_html_entities("&amp; &lt; &gt; &quot;", stats)
        assert result == "& < > \""
        assert stats.html_entities_replaced == 4

    def test_numeric_entities(self):
        stats = CleaningStats()
        result = _replace_html_entities("&#169; &#8212;", stats)
        assert "©" in result
        assert stats.html_entities_replaced == 2

    def test_hex_entities(self):
        stats = CleaningStats()
        result = _replace_html_entities("&#x00A9;", stats)
        assert "©" in result

    def test_no_entities(self):
        stats = CleaningStats()
        result = _replace_html_entities("No entities here.", stats)
        assert result == "No entities here."
        assert stats.html_entities_replaced == 0

    def test_mixed_text_and_entities(self):
        stats = CleaningStats()
        result = _replace_html_entities("Tom &amp; Jerry say &quot;hi&quot;", stats)
        assert result == 'Tom & Jerry say "hi"'
        assert stats.html_entities_replaced == 3


# ============================================================================
# Non-breaking space replacement
# ============================================================================

class TestNBSP:

    def test_unicode_nbsp(self):
        stats = CleaningStats()
        result = _replace_nbsp("word\u00a0word", stats)
        assert result == "word word"
        assert stats.nbsp_replaced == 1

    def test_multiple_nbsp(self):
        stats = CleaningStats()
        result = _replace_nbsp("a\u00a0b\u00a0c", stats)
        assert result == "a b c"
        assert stats.nbsp_replaced == 2

    def test_no_nbsp(self):
        stats = CleaningStats()
        result = _replace_nbsp("normal text", stats)
        assert result == "normal text"
        assert stats.nbsp_replaced == 0


# ============================================================================
# Unicode quote normalization
# ============================================================================

class TestUnicodeQuotes:

    def test_left_right_double_quotes(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes("\u201cHello\u201d", stats)
        assert result == '"Hello"'
        assert stats.unicode_quotes_normalized == 2

    def test_left_right_single_quotes(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes("\u2018it\u2019s\u2019", stats)
        assert result == "'it's'"

    def test_guillemets(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes("\u00abBonjour\u00bb", stats)
        assert result == '"Bonjour"'

    def test_em_dash(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes("word\u2014word", stats)
        assert result == "word--word"

    def test_en_dash(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes("1\u20132", stats)
        assert result == "1-2"

    def test_ellipsis(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes("wait\u2026", stats)
        assert result == "wait..."

    def test_no_fancy_quotes(self):
        stats = CleaningStats()
        result = _normalize_unicode_quotes('"plain quotes"', stats)
        assert result == '"plain quotes"'
        assert stats.unicode_quotes_normalized == 0

    def test_all_quote_types_together(self):
        stats = CleaningStats()
        text = "\u201cHe said, \u2018Go!\u2019\u201d \u2014 Author"
        result = _normalize_unicode_quotes(text, stats)
        assert '"' in result
        assert "'" in result
        assert "--" in result


# ============================================================================
# Page number removal
# ============================================================================

class TestPageNumberRemoval:

    def test_standalone_numbers_removed(self):
        stats = CleaningStats()
        lines = ["Content here", "42", "More content", "  123  "]
        result = _remove_page_numbers(lines, stats)
        assert "42" not in result
        assert "  123  " not in result
        assert stats.page_numbers_removed == 2

    def test_numbers_in_text_preserved(self):
        stats = CleaningStats()
        lines = ["He was 42 years old", "Chapter 7 begins"]
        result = _remove_page_numbers(lines, stats)
        assert len(result) == 2
        assert stats.page_numbers_removed == 0

    def test_large_numbers(self):
        stats = CleaningStats()
        lines = ["99999", "100000"]  # 5 digits max, 6 digits not matched
        result = _remove_page_numbers(lines, stats)
        assert stats.page_numbers_removed == 1  # Only 99999 (5 digits)
        assert "100000" in result

    def test_empty_lines_preserved(self):
        stats = CleaningStats()
        lines = ["Text", "", "More text"]
        result = _remove_page_numbers(lines, stats)
        assert len(result) == 3

    def test_zero_is_page_number(self):
        stats = CleaningStats()
        lines = ["0"]
        result = _remove_page_numbers(lines, stats)
        assert stats.page_numbers_removed == 1


# ============================================================================
# Copyright removal
# ============================================================================

class TestCopyrightRemoval:

    def test_copyright_symbol_line(self):
        stats = CleaningStats()
        lines = ["Copyright \u00a9 2024 by Author", "More text"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 1
        assert "More text" in result

    def test_all_rights_reserved(self):
        stats = CleaningStats()
        lines = ["All rights reserved.", "Content"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 1

    def test_published_by(self):
        stats = CleaningStats()
        lines = ["Published by Random House", "Content"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 1

    def test_isbn(self):
        stats = CleaningStats()
        lines = ["ISBN 978-0-123456-78-9", "Content"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 1

    def test_printed_in(self):
        stats = CleaningStats()
        lines = ["Printed in the United States", "Content"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 1

    def test_library_of_congress(self):
        stats = CleaningStats()
        lines = ["Library of Congress Catalog", "Content"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 1

    def test_first_edition(self):
        stats = CleaningStats()
        lines = ["First edition 2024", "First printing", "Content"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 2

    def test_cover_design(self):
        stats = CleaningStats()
        lines = ["Cover design by Artist", "Cover art by Painter", "Cover illustration by Drawer"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 3

    def test_blank_lines_after_copyright_removed(self):
        """Blank lines following copyright block should also be removed."""
        stats = CleaningStats()
        lines = ["Copyright \u00a9 2024", "All rights reserved.", "", "", "Story begins"]
        result = _remove_copyright(lines, stats)
        assert "Story begins" in result
        # Blank lines between copyright and content should be removed
        assert result[0] == "Story begins"

    def test_case_insensitive(self):
        stats = CleaningStats()
        lines = ["COPYRIGHT \u00a9 2024 BY AUTHOR", "ALL RIGHTS RESERVED"]
        result = _remove_copyright(lines, stats)
        assert stats.copyright_lines_removed == 2

    def test_non_copyright_preserved(self):
        stats = CleaningStats()
        lines = ["The copyright of this story is contested.", "Normal text"]
        # This should NOT match because it doesn't match the pattern exactly
        # (the pattern requires copyright followed by symbol + year)
        result = _remove_copyright(lines, stats)
        assert len(result) == 2


# ============================================================================
# TOC removal
# ============================================================================

class TestTOCRemoval:

    def test_consecutive_toc_lines_removed(self):
        """Two or more consecutive 'Chapter X  N' lines should be removed."""
        stats = CleaningStats()
        lines = [
            "Chapter I    1",
            "Chapter II   15",
            "Chapter III  42",
            "",
            "The story begins here.",
        ]
        result = _remove_toc(lines, stats)
        assert stats.toc_lines_removed == 3
        assert "The story begins here." in result

    def test_single_chapter_heading_preserved(self):
        """A single 'Chapter X N' line should NOT be removed (false positive guard)."""
        stats = CleaningStats()
        lines = [
            "Chapter I    1",
            "",
            "The story begins here.",
        ]
        result = _remove_toc(lines, stats)
        # Single TOC-like line should be put back
        assert stats.toc_lines_removed == 0
        # The actual line content must be preserved, not duplicated or lost
        assert result == lines

    def test_single_toc_line_at_end_of_input(self):
        """A single TOC-like line at end of input should be preserved."""
        stats = CleaningStats()
        lines = ["Content here.", "Chapter I    1"]
        result = _remove_toc(lines, stats)
        assert stats.toc_lines_removed == 0
        assert result == lines

    def test_no_line_duplication(self):
        """Ensure the put-back logic doesn't duplicate lines."""
        stats = CleaningStats()
        lines = [
            "Chapter I    1",
            "The story begins here.",
            "More content.",
        ]
        result = _remove_toc(lines, stats)
        assert result.count("The story begins here.") == 1
        assert result.count("Chapter I    1") == 1
        assert len(result) == 3

    def test_roman_numerals(self):
        stats = CleaningStats()
        lines = [
            "Chapter IV   45",
            "Chapter V    67",
            "Content",
        ]
        result = _remove_toc(lines, stats)
        assert stats.toc_lines_removed == 2

    def test_arabic_numerals(self):
        stats = CleaningStats()
        lines = [
            "Chapter 1    5",
            "Chapter 2    20",
            "Content",
        ]
        result = _remove_toc(lines, stats)
        assert stats.toc_lines_removed == 2

    def test_non_toc_chapter_headings_preserved(self):
        """A line like 'Chapter One' (without page number) should not match."""
        stats = CleaningStats()
        lines = ["Chapter One", "The story begins."]
        result = _remove_toc(lines, stats)
        assert len(result) == 2


# ============================================================================
# Epigraph protection
# ============================================================================

class TestEpigraphProtection:
    """Per plan: KEEP epigraphs (quoted text at chapter starts)."""

    def test_quoted_epigraph_protected(self):
        text = '"To be or not to be, that is the question."\n\nThe chapter begins.'
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 1
        # Placeholder should be in the text
        assert "__EPIGRAPH_0__" in protected

    def test_unicode_quoted_epigraph(self):
        text = '\u201cFancy quote epigraph.\u201d\n\nText follows.'
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 1

    def test_em_dash_attribution_protected(self):
        text = '\u2014 Famous Author\n\nThe chapter.'
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 1

    def test_restore_epigraphs(self):
        original = '"An epigraph."'
        text = "before __EPIGRAPH_0__ after"
        placeholders = {"__EPIGRAPH_0__": original}
        restored = _restore_epigraphs(text, placeholders)
        assert original in restored
        assert "__EPIGRAPH_0__" not in restored

    def test_only_first_20_lines_protected(self):
        """Epigraphs should only be protected in the first 20 lines."""
        lines = ["Normal text."] * 25
        lines[22] = '"This quoted text at line 23 should NOT be protected."'
        text = "\n".join(lines)
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 0

    def test_epigraph_in_line_1(self):
        text = '"Opening quote."\nRegular content.'
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 1

    def test_no_epigraph(self):
        text = "Just regular text.\nMore regular text."
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 0

    def test_multiple_epigraphs(self):
        text = '"First epigraph."\n"Second epigraph."\n\nContent.'
        protected, placeholders = _protect_epigraphs(text)
        assert len(placeholders) == 2


# ============================================================================
# Whitespace normalization
# ============================================================================

class TestWhitespaceNormalization:

    def test_trailing_whitespace_stripped(self):
        result = _normalize_whitespace("hello   \nworld  ")
        assert "hello\nworld\n" == result

    def test_three_plus_blank_lines_collapsed(self):
        result = _normalize_whitespace("a\n\n\n\nb")
        assert result == "a\n\nb\n"

    def test_two_blank_lines_preserved(self):
        result = _normalize_whitespace("a\n\nb")
        assert result == "a\n\nb\n"

    def test_leading_blank_lines_stripped(self):
        result = _normalize_whitespace("\n\n\nContent")
        assert result == "Content\n"

    def test_trailing_newline_added(self):
        result = _normalize_whitespace("text")
        assert result.endswith("\n")


# ============================================================================
# Section break handling
# ============================================================================

class TestSectionBreaks:
    """Per plan: KEEP section breaks (lines of asterisks, dashes, or blank-line separators)."""

    def test_asterisks_preserved_by_default(self):
        text = "Before\n\n* * *\n\nAfter"
        result = clean_text(text)
        assert "* * *" in result

    def test_dashes_preserved_by_default(self):
        text = "Before\n\n---\n\nAfter"
        result = clean_text(text)
        assert "---" in result

    def test_equals_preserved_by_default(self):
        text = "Before\n\n===\n\nAfter"
        result = clean_text(text)
        assert "===" in result

    def test_tildes_preserved_by_default(self):
        text = "Before\n\n~~~\n\nAfter"
        result = clean_text(text)
        assert "~~~" in result

    def test_section_breaks_removed_when_configured(self):
        config = CleaningConfig(keep_section_breaks=False)
        text = "Before\n\n* * *\n\nAfter"
        result = clean_text(text, config)
        assert "* * *" not in result

    def test_hash_breaks_preserved(self):
        text = "Before\n\n###\n\nAfter"
        result = clean_text(text)
        assert "###" in result


# ============================================================================
# Full clean_text integration tests
# ============================================================================

class TestCleanTextIntegration:
    """End-to-end tests combining multiple cleaning passes."""

    def test_all_passes_combined(self):
        """The sample from the module's __main__ block."""
        text = (
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

        result = clean_text(text)

        # HTML entities decoded
        assert "&amp;" not in result
        assert "&lt;" not in result
        assert "& Some text" in result or "& Some" in result

        # Page number removed
        lines = result.split("\n")
        assert not any(line.strip() == "42" for line in lines)

        # Copyright removed
        assert "Copyright" not in result
        assert "All rights reserved" not in result
        assert "Published by" not in result

        # TOC removed (3 consecutive TOC lines)
        assert "Chapter I    1" not in result
        assert "Chapter III  42" not in result

        # Section break preserved
        assert "* * *" in result

        # nbsp replaced
        assert "\u00a0" not in result
        assert "more text" in result

        # Excess blank lines collapsed
        assert "\n\n\n" not in result

        # Story content preserved
        assert "The actual story begins here" in result
        assert "Too many blank lines" in result

    def test_strip_html_disabled(self):
        config = CleaningConfig(strip_html=False)
        text = "&amp; text"
        result = clean_text(text, config)
        assert "&amp;" in result  # Not decoded

    def test_remove_copyright_disabled(self):
        config = CleaningConfig(remove_copyright=False)
        text = "Copyright \u00a9 2024 by Author\nStory text."
        result = clean_text(text, config)
        assert "Copyright" in result

    def test_remove_toc_disabled(self):
        config = CleaningConfig(remove_toc=False)
        text = "Chapter I    1\nChapter II   15\nContent."
        result = clean_text(text, config)
        assert "Chapter I" in result

    def test_keep_epigraphs_disabled(self):
        """When keep_epigraphs=False, no placeholder protection occurs."""
        config = CleaningConfig(keep_epigraphs=False)
        # Epigraph that is also a page-number candidate shouldn't be affected
        text = '"Epigraph text."\n\nContent here.'
        result = clean_text(text, config)
        # The text should still be present since it's not a page number
        assert "Content here." in result

    def test_empty_input(self):
        result = clean_text("")
        assert result == "\n"  # Just the trailing newline from normalization

    def test_only_whitespace(self):
        result = clean_text("   \n\n   \n  ")
        assert result.strip() == ""

    def test_preserves_normal_content(self):
        text = "The quick brown fox jumped over the lazy dog.\nThe end."
        result = clean_text(text)
        assert "The quick brown fox" in result
        assert "The end." in result

    def test_epigraph_survives_page_number_removal(self):
        """An epigraph in first 20 lines should not be removed by other passes."""
        text = (
            '"To be or not to be."\n'
            "\n"
            "The story continues with actual text.\n"
        )
        result = clean_text(text)
        assert '"To be or not to be."' in result

    def test_returns_string(self):
        result = clean_text("test")
        assert isinstance(result, str)


# ============================================================================
# clean_chapters batch tests
# ============================================================================

class TestCleanChapters:

    def test_cleans_multiple_chapters(self):
        chapters = [
            "Chapter one content &amp; more.",
            "Chapter two with\u00a0nbsp.",
            "Chapter three with \u201cfancy quotes.\u201d",
        ]
        result = clean_chapters(chapters)
        assert len(result) == 3
        assert "&amp;" not in result[0]
        assert "\u00a0" not in result[1]

    def test_empty_list(self):
        result = clean_chapters([])
        assert result == []

    def test_single_chapter(self):
        result = clean_chapters(["Just some text."])
        assert len(result) == 1

    def test_config_propagated(self):
        config = CleaningConfig(strip_html=False)
        chapters = ["&amp; entity"]
        result = clean_chapters(chapters, config)
        assert "&amp;" in result[0]

    def test_chapters_cleaned_independently(self):
        """Copyright in ch1 shouldn't affect ch2."""
        chapters = [
            "Copyright \u00a9 2024\nAll rights reserved.\n\nStory one.",
            "Story two continues.",
        ]
        result = clean_chapters(chapters)
        assert "Copyright" not in result[0]
        assert "Story two continues." in result[1]


# ============================================================================
# Slice 3 — Extreme inputs
# ============================================================================


class TestExtremeInputs:
    """Slice 3: real-world edge cases that weren't covered by the
    ASCII-focused fixtures above — megabyte paragraphs, embedded null bytes,
    unbalanced HTML, NBSP-only content, all-whitespace chapters."""

    def test_clean_text_handles_megabyte_paragraph(self):
        """A >1 MiB single-paragraph block must not hang or OOM; content
        survives intact."""
        big = "Scrooge sat in his counting-house. " * 30_000  # ~1.08 MiB
        out = clean_text(big)
        assert len(out) > 0
        assert "Scrooge" in out
        # Ratio check: the cleaner must not delete the whole block
        assert len(out) > len(big) // 2

    def test_clean_text_strips_or_preserves_null_byte(self):
        """Null bytes are rare but some EPUBs carry them. Pin the current
        behavior: clean_text does not crash, and surrounding content
        survives (null either passes through or gets dropped)."""
        text = "Before.\x00After."
        out = clean_text(text)
        # Content either side of the null byte must survive regardless of
        # whether the null itself is stripped.
        assert "Before" in out
        assert "After" in out

    def test_clean_text_malformed_html_nesting(self):
        """Unbalanced HTML tags must not crash the cleaner. The textual
        content survives regardless of tag balance (the cleaner focuses on
        entity unescaping, not full tag stripping)."""
        text = "<p>First <b>bold <i>italic</b> unclosed</p> <span>"
        out = clean_text(text)
        assert "First" in out
        assert "bold" in out
        assert "italic" in out

    def test_clean_text_all_whitespace_chapter_returns_empty(self):
        """A chapter containing only spaces, tabs, and newlines cleans down
        to an effectively empty string."""
        text = "   \t\n\n  \n\t\t  \n"
        out = clean_text(text)
        assert out.strip() == ""

    def test_clean_text_nbsp_only_chapter_returns_empty(self):
        """A chapter that is all NBSP runs (U+00A0) cleans to empty — NBSPs
        are normalized to regular spaces, then stripped."""
        text = "   \n  \n "
        out = clean_text(text)
        assert out.strip() == ""
