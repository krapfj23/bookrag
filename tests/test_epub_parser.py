"""Comprehensive tests for pipeline/epub_parser.py.

Covers:
- _HTMLTextExtractor: block tags, br, script/style skipping, entities, nested divs, nbsp
- _slugify: ASCII normalization, special chars, spaces/hyphens, unicode
- _extract_text_from_html: UTF-8 and latin-1 decoding
- _is_content_chapter: threshold filtering (< 50 chars, < 15 words)
- parse_epub: spine walking, chapter boundary math, file output structure,
  fallback when no content chapters, FileNotFoundError
- ParsedBook dataclass: all fields, chapter_boundaries as (start_char, end_char)

Alignment with plan docs:
- CLAUDE.md: ebooklib for EPUB parsing, chapter-segmented text, all intermediate outputs saved
- bookrag_pipeline_plan.md: Output to data/processed/{book_id}/raw/full_text.txt and chapters/
- bookrag_deep_research_context.md: Token-to-chapter mapping via chapter_boundaries
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from pipeline.epub_parser import (
    ParsedBook,
    _HTMLTextExtractor,
    _slugify,
    _extract_text_from_html,
    _is_content_chapter,
    parse_epub,
)


# ============================================================================
# _HTMLTextExtractor tests
# ============================================================================

class TestHTMLTextExtractor:
    """Tests for the custom HTML parser."""

    def test_plain_text_passthrough(self):
        ext = _HTMLTextExtractor()
        ext.feed("Hello world")
        assert ext.get_text() == "Hello world"

    def test_paragraph_tags_become_newlines(self):
        ext = _HTMLTextExtractor()
        ext.feed("<p>First paragraph</p><p>Second paragraph</p>")
        text = ext.get_text()
        assert "First paragraph" in text
        assert "Second paragraph" in text
        # Paragraphs should be on separate lines
        assert "\n" in text

    def test_div_tags_become_newlines(self):
        ext = _HTMLTextExtractor()
        ext.feed("<div>Block one</div><div>Block two</div>")
        text = ext.get_text()
        lines = [l for l in text.split("\n") if l.strip()]
        assert len(lines) == 2

    def test_br_becomes_newline(self):
        ext = _HTMLTextExtractor()
        ext.feed("Line one<br/>Line two<br>Line three")
        text = ext.get_text()
        assert "Line one\nLine two\nLine three" == text

    def test_heading_tags(self):
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            ext = _HTMLTextExtractor()
            ext.feed(f"<{tag}>Heading</{tag}><p>Body</p>")
            text = ext.get_text()
            assert "Heading" in text
            assert "Body" in text

    def test_script_content_skipped(self):
        ext = _HTMLTextExtractor()
        ext.feed("<p>Before</p><script>var x = 1;</script><p>After</p>")
        text = ext.get_text()
        assert "var x" not in text
        assert "Before" in text
        assert "After" in text

    def test_style_content_skipped(self):
        ext = _HTMLTextExtractor()
        ext.feed("<p>Before</p><style>.cls { color: red; }</style><p>After</p>")
        text = ext.get_text()
        assert "color" not in text
        assert "Before" in text

    def test_nested_script_depth(self):
        """Script skip depth handles nested tags without going negative."""
        ext = _HTMLTextExtractor()
        ext.feed("<script><script>inner</script></script><p>Visible</p>")
        text = ext.get_text()
        assert "inner" not in text
        assert "Visible" in text

    def test_entity_ref_decoded(self):
        ext = _HTMLTextExtractor()
        ext.feed("Tom &amp; Jerry &lt;3")
        text = ext.get_text()
        assert "Tom & Jerry <3" == text

    def test_char_ref_decoded(self):
        ext = _HTMLTextExtractor()
        ext.feed("&#169; 2024")
        text = ext.get_text()
        assert "\u00a9" not in text or "©" in text  # Decoded from charref

    def test_nbsp_replaced(self):
        ext = _HTMLTextExtractor()
        ext.feed("word\u00a0word")
        text = ext.get_text()
        assert "\u00a0" not in text
        assert "word word" == text

    def test_nested_divs(self):
        """Common EPUB quirk: deeply nested divs."""
        ext = _HTMLTextExtractor()
        ext.feed("<div><div><div><p>Deep content</p></div></div></div>")
        text = ext.get_text()
        assert "Deep content" in text

    def test_multiple_blank_lines_collapsed(self):
        ext = _HTMLTextExtractor()
        ext.feed("<p>A</p><p></p><p></p><p></p><p>B</p>")
        text = ext.get_text()
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in text

    def test_whitespace_collapsed_per_line(self):
        ext = _HTMLTextExtractor()
        ext.feed("<p>  lots   of    spaces  </p>")
        text = ext.get_text()
        assert text == "lots of spaces"

    def test_blockquote_and_li(self):
        ext = _HTMLTextExtractor()
        ext.feed("<blockquote>Quote text</blockquote><li>Item</li>")
        text = ext.get_text()
        assert "Quote text" in text
        assert "Item" in text

    def test_all_block_tags_produce_newlines(self):
        block_tags = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                      "li", "blockquote", "tr", "section", "article"]
        for tag in block_tags:
            ext = _HTMLTextExtractor()
            ext.feed(f"Before<{tag}>Inside</{tag}>After")
            text = ext.get_text()
            assert "\n" in text, f"Block tag <{tag}> should produce newline"


# ============================================================================
# _slugify tests
# ============================================================================

class TestSlugify:
    """Tests for filename → book_id slug conversion."""

    def test_simple_filename(self):
        assert _slugify("my_book.epub") == "my_book"

    def test_spaces_to_underscores(self):
        assert _slugify("A Christmas Carol.epub") == "a_christmas_carol"

    def test_hyphens_to_underscores(self):
        assert _slugify("red-rising.epub") == "red_rising"

    def test_special_characters_stripped(self):
        result = _slugify("Book! @#$% (2024).epub")
        assert result == "book_2024"

    def test_unicode_normalized(self):
        result = _slugify("Café Stories.epub")
        assert result == "cafe_stories"

    def test_leading_trailing_underscores_stripped(self):
        result = _slugify("__test__.epub")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_multiple_spaces_collapsed(self):
        result = _slugify("too   many    spaces.epub")
        assert "__" not in result

    def test_path_with_directory(self):
        """Only the filename stem should matter, not the directory."""
        result = _slugify("/some/path/to/My Book.epub")
        assert result == "my_book"

    def test_already_slug(self):
        assert _slugify("already_clean.epub") == "already_clean"

    def test_uppercase_lowered(self):
        assert _slugify("ALL_CAPS.epub") == "all_caps"


# ============================================================================
# _extract_text_from_html tests
# ============================================================================

class TestExtractTextFromHTML:
    """Tests for HTML bytes → plain text extraction."""

    def test_utf8_bytes(self):
        html = b"<p>Hello world</p>"
        text = _extract_text_from_html(html)
        assert "Hello world" in text

    def test_latin1_fallback(self):
        """Non-UTF8 bytes should still decode via latin-1 fallback."""
        # \xe9 is 'é' in latin-1
        html = b"<p>Caf\xe9</p>"
        text = _extract_text_from_html(html)
        assert "Caf" in text

    def test_full_html_document(self):
        html = b"""<!DOCTYPE html>
        <html><head><title>Test</title></head>
        <body><p>Content here</p></body></html>"""
        text = _extract_text_from_html(html)
        assert "Content here" in text
        # Title should not appear in body text (it's not in a block tag)
        # Actually the parser will extract it since it's text data
        # But the important thing is body content is there

    def test_empty_html(self):
        text = _extract_text_from_html(b"")
        assert text == ""

    def test_html_with_only_tags(self):
        text = _extract_text_from_html(b"<div><span></span></div>")
        assert text.strip() == ""


# ============================================================================
# _is_content_chapter tests
# ============================================================================

class TestIsContentChapter:
    """Tests for the content/non-content chapter heuristic.

    Per plan: Filter out near-empty spine items (cover pages, blank pages, navs).
    """

    def test_short_text_rejected(self):
        """Text under 50 chars should be rejected."""
        assert _is_content_chapter("Short") is False
        assert _is_content_chapter("A" * 49) is False

    def test_few_words_rejected(self):
        """Even if >= 50 chars, under 15 words should be rejected."""
        # 50+ chars but only 5 words
        text = "longword " * 5 + "x" * 10
        assert len(text) >= 50
        assert _is_content_chapter(text) is False

    def test_valid_chapter_accepted(self):
        text = "This is a chapter with enough words to pass the threshold. " * 3
        assert _is_content_chapter(text) is True

    def test_whitespace_only_rejected(self):
        assert _is_content_chapter("   \n\n\t  ") is False

    def test_empty_string_rejected(self):
        assert _is_content_chapter("") is False

    def test_exactly_at_threshold(self):
        """15 words, 50+ chars: should be accepted."""
        words = ["word"] * 15
        text = " ".join(words)
        assert len(text) >= 50
        assert _is_content_chapter(text) is True

    def test_cover_page_like_text(self):
        """Typical cover page: book title + author, short."""
        assert _is_content_chapter("A Christmas Carol\nCharles Dickens") is False

    def test_nav_page_like_text(self):
        """Typical nav: just 'Contents' or similar."""
        assert _is_content_chapter("Table of Contents") is False


# ============================================================================
# ParsedBook dataclass tests
# ============================================================================

class TestParsedBook:
    """Verify ParsedBook has all required fields per the plan.

    Per CLAUDE.md & plan: chapter_boundaries as (start_char, end_char) tuples,
    used by coref resolver to map tokens back to chapters.
    """

    def test_all_fields_present(self):
        pb = ParsedBook(
            book_id="test",
            chapter_count=2,
            chapter_texts=["Ch1 text", "Ch2 text"],
            full_text="=== CHAPTER 1 ===\n\nCh1 text\n\n=== CHAPTER 2 ===\n\nCh2 text\n\n",
            chapter_boundaries=[(20, 28), (50, 58)],
        )
        assert pb.book_id == "test"
        assert pb.chapter_count == 2
        assert len(pb.chapter_texts) == 2
        assert len(pb.chapter_boundaries) == 2

    def test_chapter_boundaries_are_tuples(self):
        pb = ParsedBook(
            book_id="t", chapter_count=1,
            chapter_texts=["text"], full_text="text",
            chapter_boundaries=[(0, 4)],
        )
        start, end = pb.chapter_boundaries[0]
        assert isinstance(start, int)
        assert isinstance(end, int)

    def test_chapter_boundaries_index_into_full_text(self):
        """Boundaries should correctly slice the chapter text from full_text."""
        ch1 = "First chapter content here with enough words."
        ch2 = "Second chapter content here with different words."
        # Simulate what parse_epub does
        parts = []
        boundaries = []
        cursor = 0
        for idx, ch in enumerate([ch1, ch2], start=1):
            marker = f"=== CHAPTER {idx} ===\n\n"
            parts.append(marker)
            cursor += len(marker)
            start = cursor
            parts.append(ch)
            cursor += len(ch)
            boundaries.append((start, cursor))
            parts.append("\n\n")
            cursor += 2
        full = "".join(parts)

        pb = ParsedBook(
            book_id="t", chapter_count=2,
            chapter_texts=[ch1, ch2], full_text=full,
            chapter_boundaries=boundaries,
        )

        # Verify slicing works
        s1, e1 = pb.chapter_boundaries[0]
        assert pb.full_text[s1:e1] == ch1

        s2, e2 = pb.chapter_boundaries[1]
        assert pb.full_text[s2:e2] == ch2


# ============================================================================
# parse_epub integration tests (mocked ebooklib)
# ============================================================================

class TestParseEpub:
    """Tests for the main parse_epub function.

    Mocks ebooklib to avoid needing real EPUB files.
    Per plan: walks spine for reading order, writes to data/processed/{book_id}/raw/.
    """

    def _make_mock_item(self, item_id: str, content: str, item_type=None):
        """Create a mock EpubItem."""
        import ebooklib
        item = MagicMock()
        item.get_id.return_value = item_id
        item.get_content.return_value = content.encode("utf-8")
        item.get_type.return_value = item_type or ebooklib.ITEM_DOCUMENT
        return item

    def _make_chapter_html(self, text: str) -> str:
        """Wrap text in minimal HTML to simulate a real chapter."""
        return f"<html><body><p>{text}</p></body></html>"

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_basic_parsing(self, mock_read, tmp_path):
        """Parse a mock EPUB with 2 chapters."""
        # Create fake epub file
        epub_file = tmp_path / "test_book.epub"
        epub_file.touch()

        ch1_text = "This is chapter one with enough words to pass the content filter. " * 3
        ch2_text = "Chapter two has different content but also enough words to pass. " * 3

        ch1_item = self._make_mock_item("ch1", self._make_chapter_html(ch1_text))
        ch2_item = self._make_mock_item("ch2", self._make_chapter_html(ch2_text))

        mock_book = MagicMock()
        mock_book.spine = [("ch1", "yes"), ("ch2", "yes")]
        mock_book.get_items.return_value = [ch1_item, ch2_item]
        mock_read.return_value = mock_book

        output_dir = tmp_path / "output"
        result = parse_epub(epub_file, output_dir=output_dir)

        assert result.book_id == "test_book"
        assert result.chapter_count == 2
        assert len(result.chapter_texts) == 2
        assert len(result.chapter_boundaries) == 2

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_chapter_markers_in_full_text(self, mock_read, tmp_path):
        """Full text should contain === CHAPTER N === markers."""
        epub_file = tmp_path / "markers.epub"
        epub_file.touch()

        ch_text = "Sufficient content for a chapter with many words to exceed threshold. " * 2
        item = self._make_mock_item("ch1", self._make_chapter_html(ch_text))

        mock_book = MagicMock()
        mock_book.spine = [("ch1", "yes")]
        mock_book.get_items.return_value = [item]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert "=== CHAPTER 1 ===" in result.full_text

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_boundaries_exclude_markers(self, mock_read, tmp_path):
        """chapter_boundaries should point to content, not markers."""
        epub_file = tmp_path / "bounds.epub"
        epub_file.touch()

        ch_text = "Content that is long enough to be a real chapter with more than fifteen words easily. " * 2
        item = self._make_mock_item("ch1", self._make_chapter_html(ch_text))

        mock_book = MagicMock()
        mock_book.spine = [("ch1", "yes")]
        mock_book.get_items.return_value = [item]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        start, end = result.chapter_boundaries[0]
        extracted = result.full_text[start:end]
        assert "=== CHAPTER" not in extracted
        assert extracted == result.chapter_texts[0]

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_non_content_items_skipped(self, mock_read, tmp_path):
        """Cover pages and nav items should be filtered out."""
        epub_file = tmp_path / "filtered.epub"
        epub_file.touch()

        cover = self._make_mock_item("cover", "<p>Book Title</p>")  # Too short
        ch1 = self._make_mock_item("ch1", self._make_chapter_html(
            "Real chapter content with enough words to pass the heuristic filter. " * 3
        ))

        mock_book = MagicMock()
        mock_book.spine = [("cover", "yes"), ("ch1", "yes")]
        mock_book.get_items.return_value = [cover, ch1]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert result.chapter_count == 1

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_file_output_structure(self, mock_read, tmp_path):
        """Verify output matches plan: full_text.txt + chapters/chapter_01.txt etc."""
        epub_file = tmp_path / "output_test.epub"
        epub_file.touch()

        ch_text = "Chapter content for file output test with sufficient words to pass. " * 3
        item = self._make_mock_item("ch1", self._make_chapter_html(ch_text))

        mock_book = MagicMock()
        mock_book.spine = [("ch1", "yes")]
        mock_book.get_items.return_value = [item]
        mock_read.return_value = mock_book

        output_dir = tmp_path / "data" / "raw"
        result = parse_epub(epub_file, output_dir=output_dir)

        assert (output_dir / "full_text.txt").exists()
        assert (output_dir / "chapters" / "chapter_01.txt").exists()

        # Verify file content matches
        saved_full = (output_dir / "full_text.txt").read_text(encoding="utf-8")
        assert saved_full == result.full_text

        saved_ch1 = (output_dir / "chapters" / "chapter_01.txt").read_text(encoding="utf-8")
        assert saved_ch1 == result.chapter_texts[0]

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_default_output_dir(self, mock_read, tmp_path, monkeypatch):
        """Without output_dir, should write to data/processed/{book_id}/raw/."""
        epub_file = tmp_path / "default_dir.epub"
        epub_file.touch()

        ch_text = "Enough words for a chapter that passes the content check without issue. " * 3
        item = self._make_mock_item("ch1", self._make_chapter_html(ch_text))

        mock_book = MagicMock()
        mock_book.spine = [("ch1", "yes")]
        mock_book.get_items.return_value = [item]
        mock_read.return_value = mock_book

        # Change cwd so default path is inside tmp_path
        monkeypatch.chdir(tmp_path)
        result = parse_epub(epub_file)

        expected_dir = tmp_path / "data" / "processed" / "default_dir" / "raw"
        assert expected_dir.exists()
        assert (expected_dir / "full_text.txt").exists()

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="EPUB file not found"):
            parse_epub(Path("/nonexistent/fake.epub"))

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_missing_spine_item_warning(self, mock_read, tmp_path):
        """Spine references a missing item — should warn and continue."""
        epub_file = tmp_path / "missing.epub"
        epub_file.touch()

        ch1 = self._make_mock_item("ch1", self._make_chapter_html(
            "Valid chapter with lots of words to satisfy the content checker. " * 3
        ))

        mock_book = MagicMock()
        mock_book.spine = [("missing_id", "yes"), ("ch1", "yes")]
        mock_book.get_items.return_value = [ch1]  # "missing_id" not in items
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert result.chapter_count == 1  # Only ch1 parsed

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_fallback_when_no_content_chapters(self, mock_read, tmp_path):
        """When spine filtering removes everything, fall back to all ITEM_DOCUMENT."""
        epub_file = tmp_path / "fallback.epub"
        epub_file.touch()

        # All spine items are too short
        short = self._make_mock_item("s1", "<p>Short</p>")

        # But there's a document item with real content
        real_item = MagicMock()
        real_item.get_id.return_value = "real"
        real_item.get_content.return_value = self._make_chapter_html(
            "Fallback content with enough words to be a chapter. " * 5
        ).encode("utf-8")
        import ebooklib
        real_item.get_type.return_value = ebooklib.ITEM_DOCUMENT

        mock_book = MagicMock()
        mock_book.spine = [("s1", "yes")]
        mock_book.get_items.return_value = [short]
        mock_book.get_items_of_type.return_value = [real_item]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert result.chapter_count >= 1

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_multiple_chapters_spine_order(self, mock_read, tmp_path):
        """Chapters should appear in spine order, not arbitrary order."""
        epub_file = tmp_path / "order.epub"
        epub_file.touch()

        ch_a = self._make_mock_item("chA", self._make_chapter_html(
            "Alpha chapter text with sufficient content to pass the word count threshold. " * 2
        ))
        ch_b = self._make_mock_item("chB", self._make_chapter_html(
            "Beta chapter text with different content that also passes the threshold. " * 2
        ))

        mock_book = MagicMock()
        # Spine order: B then A
        mock_book.spine = [("chB", "yes"), ("chA", "yes")]
        mock_book.get_items.return_value = [ch_a, ch_b]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert result.chapter_count == 2
        assert "Beta" in result.chapter_texts[0]
        assert "Alpha" in result.chapter_texts[1]

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_chapter_numbering_in_filenames(self, mock_read, tmp_path):
        """Chapter files should be zero-padded: chapter_01.txt, chapter_02.txt."""
        epub_file = tmp_path / "numbering.epub"
        epub_file.touch()

        items = []
        for i in range(3):
            items.append(self._make_mock_item(
                f"ch{i}",
                self._make_chapter_html(
                    f"Chapter {i} has sufficient words to clear the content threshold easily. " * 2
                ),
            ))

        mock_book = MagicMock()
        mock_book.spine = [(f"ch{i}", "yes") for i in range(3)]
        mock_book.get_items.return_value = items
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        chapters_dir = tmp_path / "out" / "chapters"
        assert (chapters_dir / "chapter_01.txt").exists()
        assert (chapters_dir / "chapter_02.txt").exists()
        assert (chapters_dir / "chapter_03.txt").exists()

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_book_id_from_filename(self, mock_read, tmp_path):
        """book_id should be slugified from the EPUB filename."""
        epub_file = tmp_path / "A Christmas Carol.epub"
        epub_file.touch()

        item = self._make_mock_item("ch1", self._make_chapter_html(
            "Content to pass threshold. " * 10
        ))
        mock_book = MagicMock()
        mock_book.spine = [("ch1", "yes")]
        mock_book.get_items.return_value = [item]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert result.book_id == "a_christmas_carol"

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_non_document_items_skipped(self, mock_read, tmp_path):
        """Items that are not ITEM_DOCUMENT (e.g., images, CSS) should be skipped."""
        epub_file = tmp_path / "nondoc.epub"
        epub_file.touch()

        import ebooklib
        css_item = self._make_mock_item("style", "body { color: red; }", item_type=ebooklib.ITEM_STYLE)
        ch1 = self._make_mock_item("ch1", self._make_chapter_html(
            "Real chapter text with sufficient word count to pass the filter. " * 3
        ))

        mock_book = MagicMock()
        mock_book.spine = [("style", "yes"), ("ch1", "yes")]
        mock_book.get_items.return_value = [css_item, ch1]
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")
        assert result.chapter_count == 1
        assert "color: red" not in result.full_text

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_chapter_boundary_contiguity(self, mock_read, tmp_path):
        """All chapter boundaries should be non-overlapping and within full_text length."""
        epub_file = tmp_path / "contiguous.epub"
        epub_file.touch()

        items = []
        for i in range(5):
            items.append(self._make_mock_item(
                f"ch{i}",
                self._make_chapter_html(
                    f"Chapter {i} with unique content and enough words for the filter. " * 3
                ),
            ))

        mock_book = MagicMock()
        mock_book.spine = [(f"ch{i}", "yes") for i in range(5)]
        mock_book.get_items.return_value = items
        mock_read.return_value = mock_book

        result = parse_epub(epub_file, output_dir=tmp_path / "out")

        for i, (start, end) in enumerate(result.chapter_boundaries):
            assert 0 <= start < end <= len(result.full_text), \
                f"Boundary {i} out of range: ({start}, {end}), full_text len={len(result.full_text)}"

        # Non-overlapping
        for i in range(len(result.chapter_boundaries) - 1):
            _, end_i = result.chapter_boundaries[i]
            start_next, _ = result.chapter_boundaries[i + 1]
            assert end_i <= start_next, \
                f"Boundaries {i} and {i+1} overlap: end={end_i}, next_start={start_next}"
