"""Quality-control tests for the BookRAG ingestion pipeline.

These tests validate cross-module data contracts, structural invariants,
and end-to-end data flow between pipeline stages. They use realistic
synthetic data modeled on A Christmas Carol (the project's test book).

Categories:
  1. ParsedBook ↔ text_cleaner contract
  2. ParsedBook ↔ BookNLP contract (chapter boundaries → token offsets)
  3. BookNLP internal consistency (tokens ↔ entities ↔ quotes ↔ characters)
  4. Text cleaner idempotency and content preservation
  5. Output file structure compliance with plan
  6. Serialization round-trip fidelity
  7. Realistic A Christmas Carol data smoke tests

Alignment:
  - CLAUDE.md: "Save all intermediate outputs to disk", "Build incrementally, test as you go"
  - bookrag_pipeline_plan.md: File output structure, Pipeline architecture steps 1–2
  - bookrag_deep_research_context.md: BookNLP output file specs, entity types, coref approach
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.epub_parser import ParsedBook, _slugify, _extract_text_from_html
from pipeline.text_cleaner import CleaningConfig, clean_text, clean_chapters
from pipeline.booknlp_runner import (
    Token,
    EntityMention,
    Quote,
    CharacterProfile,
    BookNLPOutput,
    _parse_book_json,
    _parse_tokens,
    _parse_entities,
    _parse_quotes,
    parse_booknlp_outputs,
)


# ============================================================================
# Helpers — build realistic A Christmas Carol pipeline data
# ============================================================================

def _build_christmas_carol_chapters() -> list[str]:
    """Five chapters of A Christmas Carol with realistic structure."""
    return [
        # Stave 1: Marley's Ghost
        (
            "Marley was dead: to begin with. There is no doubt whatever about that. "
            "Old Marley was as dead as a door-nail.\n\n"
            "Scrooge knew he was dead. Of course he did. Scrooge and he were partners "
            "for I don't know how many years.\n\n"
            "Oh! But he was a tight-fisted hand at the grindstone, Scrooge! "
            "A squeezing, wrenching, grasping, scraping, clutching, covetous old sinner!\n\n"
            "The door of Scrooge's counting-house was open that he might keep his eye "
            "upon his clerk, who in a dismal little cell beyond was copying letters.\n\n"
            "'A merry Christmas, uncle! God save you!' cried a cheerful voice."
        ),
        # Stave 2: The First of the Three Spirits
        (
            "When Scrooge awoke, it was so dark, that looking out of bed, he could "
            "scarcely distinguish the transparent window from the opaque walls of his chamber.\n\n"
            "The curtains of his bed were drawn aside by a strange figure — like a child: "
            "yet not so like a child as like an old man.\n\n"
            "'I am the Ghost of Christmas Past,' said the Spirit. 'Rise! and walk with me!'\n\n"
            "They flew together through the night sky to visit scenes from Scrooge's youth "
            "in the countryside."
        ),
        # Stave 3: The Second of the Three Spirits
        (
            "Awaking in the middle of a prodigiously tough snore, Scrooge had no occasion "
            "to be told that the bell was again upon the stroke of One.\n\n"
            "'I am the Ghost of Christmas Present,' said the Spirit. 'Look upon me!'\n\n"
            "The Spirit showed Scrooge the Cratchit family gathered around their meager "
            "Christmas dinner. Tiny Tim sat close to his father's side.\n\n"
            "'God bless us, every one!' said Tiny Tim."
        ),
        # Stave 4: The Last of the Spirits
        (
            "The Phantom slowly, gravely, silently, approached. It was shrouded in a deep "
            "black garment, which concealed its head, its face, its form.\n\n"
            "The Ghost of Christmas Yet to Come pointed silently at a gravestone bearing "
            "the name Ebenezer Scrooge.\n\n"
            "'Spirit!' he cried, tight clutching at its robe, 'hear me! I am not the man "
            "I was. I will not be the man I must have been.'"
        ),
        # Stave 5: The End of It
        (
            "Scrooge was better than his word. He did it all, and infinitely more; "
            "and to Tiny Tim, who did NOT die, he was a second father.\n\n"
            "He became as good a friend, as good a master, and as good a man, as the "
            "good old city knew.\n\n"
            "Scrooge raised Bob Cratchit's salary and kept Christmas well from that day forward.\n\n"
            "'God bless us, every one!' said Tiny Tim, the last of all."
        ),
    ]


def _build_parsed_book(chapters: list[str], book_id: str = "a_christmas_carol") -> ParsedBook:
    """Construct a ParsedBook exactly as parse_epub would."""
    parts: list[str] = []
    boundaries: list[tuple[int, int]] = []
    cursor = 0
    for idx, ch in enumerate(chapters, start=1):
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
    return ParsedBook(
        book_id=book_id,
        chapter_count=len(chapters),
        chapter_texts=chapters,
        full_text=full,
        chapter_boundaries=boundaries,
    )


def _write_booknlp_fixtures(tmp_path: Path, book_id: str) -> Path:
    """Write realistic BookNLP output files to tmp_path. Returns the directory."""
    out = tmp_path / "booknlp"
    out.mkdir()

    # .tokens — a small subset
    (out / f"{book_id}.tokens").write_text(
        "token_ID_within_document\tsentence_ID\ttoken_offset_begin\ttoken_offset_end\t"
        "word\tlemma\tPOS_tag\tdependency_relation\tdependency_head_ID\tcoref_id\tevent\n"
        "0\t0\t0\t6\tMarley\tmarley\tNNP\tnsubj\t1\t2\t-1\n"
        "1\t0\t7\t10\twas\tbe\tVBD\troot\t-1\t-1\t-1\n"
        "2\t0\t11\t15\tdead\tdead\tJJ\tacomp\t1\t-1\ttrigger\n"
        "3\t0\t17\t19\tto\tto\tTO\tmark\t4\t-1\t-1\n"
        "4\t0\t20\t25\tbegin\tbegin\tVB\tadvcl\t1\t-1\t-1\n"
        "5\t1\t45\t52\tScrooge\tscrooge\tNNP\tnsubj\t6\t0\t-1\n"
        "6\t1\t53\t57\tknew\tknow\tVBD\troot\t-1\t-1\t-1\n"
        "7\t1\t58\t60\the\the\tPRP\tnsubj\t8\t0\t-1\n"
        "8\t1\t61\t64\twas\tbe\tVBD\tccomp\t6\t-1\t-1\n"
        "9\t1\t65\t69\tdead\tdead\tJJ\tacomp\t8\t-1\t-1\n"
        "10\t5\t400\t403\tBob\tbob\tNNP\tcompound\t11\t1\t-1\n"
        "11\t5\t404\t412\tCratchit\tcratchit\tNNP\tnsubj\t12\t1\t-1\n"
        "12\t5\t413\t417\twent\tgo\tVBD\troot\t-1\t-1\t-1\n"
        "13\t8\t600\t604\tTiny\ttiny\tNNP\tcompound\t14\t3\t-1\n"
        "14\t8\t605\t608\tTim\ttim\tNNP\tnsubj\t15\t3\t-1\n"
        "15\t8\t609\t612\tsat\tsit\tVBD\troot\t-1\t-1\t-1\n",
        encoding="utf-8",
    )

    # .entities
    (out / f"{book_id}.entities").write_text(
        "COREF\tstart_token\tend_token\tprop\tcat\ttext\n"
        "0\t5\t6\tPROP\tPER\tScrooge\n"
        "0\t7\t8\tPRON\tPER\the\n"
        "1\t10\t12\tPROP\tPER\tBob Cratchit\n"
        "2\t0\t1\tPROP\tPER\tMarley\n"
        "3\t13\t15\tPROP\tPER\tTiny Tim\n"
        "100\t200\t201\tPROP\tLOC\tLondon\n"
        "101\t210\t213\tPROP\tFAC\tScrooge's counting-house\n",
        encoding="utf-8",
    )

    # .quotes
    (out / f"{book_id}.quotes").write_text(
        "quote_start\tquote_end\tquote\tchar_id\n"
        "250\t280\tA merry Christmas, uncle! God save you!\t4\n"
        "350\t390\tI am the Ghost of Christmas Past. Rise! and walk with me!\t5\n"
        "500\t530\tGod bless us, every one!\t3\n"
        "550\t600\tI am not the man I was. I will not be the man I must have been.\t0\n",
        encoding="utf-8",
    )

    # .book JSON
    book_data = [
        {
            "id": 0,
            "names": {
                "proper": [{"n": "Scrooge", "c": 150}, {"n": "Ebenezer", "c": 12}],
                "common": [{"n": "old sinner", "c": 3}],
            },
            "g": "male",
            "agent": [{"w": "said", "c": 30}, {"w": "muttered", "c": 5}],
            "patient": [{"w": "visited", "c": 3}],
            "poss": [{"w": "counting-house", "c": 8}],
            "mod": [{"w": "old", "c": 10}, {"w": "covetous", "c": 4}],
            "count": 170,
        },
        {
            "id": 1,
            "names": {
                "proper": [{"n": "Bob Cratchit", "c": 40}, {"n": "Cratchit", "c": 25}],
            },
            "g": "male",
            "agent": [{"w": "said", "c": 12}],
            "patient": [],
            "poss": [{"w": "desk", "c": 2}],
            "mod": [{"w": "poor", "c": 3}],
            "count": 65,
        },
        {
            "id": 2,
            "names": {
                "proper": [{"n": "Marley", "c": 35}, {"n": "Jacob Marley", "c": 20}],
            },
            "g": "male",
            "agent": [{"w": "warned", "c": 3}],
            "patient": [],
            "poss": [{"w": "chains", "c": 2}],
            "mod": [{"w": "dead", "c": 5}],
            "count": 55,
        },
        {
            "id": 3,
            "names": {
                "proper": [{"n": "Tiny Tim", "c": 15}, {"n": "Tim", "c": 8}],
            },
            "g": "male",
            "agent": [{"w": "said", "c": 2}],
            "patient": [],
            "poss": [{"w": "crutch", "c": 1}],
            "mod": [{"w": "little", "c": 3}],
            "count": 23,
        },
    ]
    (out / f"{book_id}.book").write_text(json.dumps(book_data), encoding="utf-8")

    return out


# ============================================================================
# 1. ParsedBook ↔ text_cleaner contract
# ============================================================================

class TestParserCleanerContract:
    """Verify that text_cleaner operates correctly on ParsedBook outputs."""

    def test_cleaned_chapters_same_count(self):
        """Cleaning should never add or remove chapters."""
        chapters = _build_christmas_carol_chapters()
        cleaned = clean_chapters(chapters)
        assert len(cleaned) == len(chapters)

    def test_cleaned_text_is_nonempty(self):
        """Cleaning should not destroy all content from any chapter."""
        chapters = _build_christmas_carol_chapters()
        cleaned = clean_chapters(chapters)
        for i, ch in enumerate(cleaned):
            assert len(ch.strip()) > 0, f"Chapter {i+1} was emptied by cleaning"

    def test_cleaning_preserves_story_content(self):
        """Key narrative words should survive cleaning."""
        chapters = _build_christmas_carol_chapters()
        cleaned = clean_chapters(chapters)
        full_cleaned = " ".join(cleaned)
        for keyword in ["Scrooge", "Marley", "Cratchit", "Christmas", "Ghost", "Tiny Tim"]:
            assert keyword in full_cleaned, f"'{keyword}' missing after cleaning"

    def test_cleaning_preserves_dialogue(self):
        """Quoted dialogue should survive cleaning."""
        chapters = _build_christmas_carol_chapters()
        cleaned = clean_chapters(chapters)
        full_cleaned = " ".join(cleaned)
        assert "God bless us, every one!" in full_cleaned
        assert "merry Christmas" in full_cleaned

    def test_cleaning_preserves_section_breaks(self):
        """Section breaks in chapter text should survive default cleaning."""
        text_with_breaks = "First section.\n\n* * *\n\nSecond section.\n\n---\n\nThird."
        result = clean_text(text_with_breaks)
        assert "* * *" in result
        assert "---" in result

    def test_clean_then_rebuild_boundaries(self):
        """After cleaning, a new ParsedBook can be built with valid boundaries."""
        chapters = _build_christmas_carol_chapters()
        cleaned = clean_chapters(chapters)
        pb = _build_parsed_book(cleaned)

        assert pb.chapter_count == len(cleaned)
        for i, (start, end) in enumerate(pb.chapter_boundaries):
            assert pb.full_text[start:end] == cleaned[i]

    def test_idempotent_cleaning(self):
        """Cleaning already-clean text should be a no-op (minus trailing newline)."""
        chapters = _build_christmas_carol_chapters()
        once = clean_chapters(chapters)
        twice = clean_chapters(once)
        for a, b in zip(once, twice):
            assert a == b, "Cleaning is not idempotent"

    def test_unicode_quotes_in_dialogue(self):
        """Unicode quotes should be normalized to ASCII for downstream LLM consumption."""
        text = "\u201cBah!\u201d said Scrooge. \u201cHumbug!\u201d"
        result = clean_text(text)
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert "Bah!" in result
        assert "Humbug!" in result


# ============================================================================
# 2. ParsedBook ↔ BookNLP contract (chapter boundaries → token offsets)
# ============================================================================

class TestParserBookNLPContract:
    """Verify that chapter_boundaries can map BookNLP token offsets to chapters.

    Per CLAUDE.md: coref resolver depends on chapter_boundaries to map tokens
    back to chapters. Per deep_research_context.md: token_offset_begin/end are
    byte offsets into the original text.
    """

    def test_token_offset_to_chapter_mapping(self):
        """Every token offset should map to exactly one chapter."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        # Simulate token offsets at known positions in each chapter
        for ch_idx, (start, end) in enumerate(pb.chapter_boundaries):
            mid = (start + end) // 2
            # This offset should map to ch_idx
            mapped = None
            for i, (s, e) in enumerate(pb.chapter_boundaries):
                if s <= mid < e:
                    mapped = i
                    break
            assert mapped == ch_idx, f"Offset {mid} mapped to chapter {mapped}, expected {ch_idx}"

    def test_no_gap_between_chapter_content_and_marker(self):
        """Chapter boundaries should immediately follow the chapter marker."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        for i, (start, _end) in enumerate(pb.chapter_boundaries):
            marker = f"=== CHAPTER {i+1} ===\n\n"
            marker_start = pb.full_text.rfind(marker, 0, start)
            assert marker_start >= 0, f"Marker not found before chapter {i+1}"
            assert marker_start + len(marker) == start, \
                f"Gap between marker and chapter {i+1} content"

    def test_chapter_text_recoverable_from_full_text(self):
        """Slicing full_text with boundaries must reproduce chapter_texts exactly."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        for i, (start, end) in enumerate(pb.chapter_boundaries):
            assert pb.full_text[start:end] == pb.chapter_texts[i], \
                f"Chapter {i+1} text mismatch when recovered from full_text"

    def test_boundaries_cover_all_content(self):
        """Sum of chapter lengths should equal total content in full_text (minus markers/separators)."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        total_chapter_chars = sum(end - start for start, end in pb.chapter_boundaries)
        total_from_texts = sum(len(ch) for ch in pb.chapter_texts)
        assert total_chapter_chars == total_from_texts

    def test_offset_before_first_chapter_maps_to_none(self):
        """Offsets in the marker region should not map to any chapter."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        # Offset 0 is inside "=== CHAPTER 1 ===" marker
        for i, (s, e) in enumerate(pb.chapter_boundaries):
            if s <= 0 < e:
                pytest.fail("Offset 0 should not be inside any chapter boundary")


# ============================================================================
# 3. BookNLP internal consistency
# ============================================================================

class TestBookNLPInternalConsistency:
    """Verify structural invariants within BookNLP parsed output."""

    def test_entity_coref_ids_match_characters(self, tmp_path):
        """Every PER entity coref_id should appear in characters (or be unresolved)."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        char_ids = {c.coref_id for c in result.characters}
        for entity in result.entities:
            if entity.cat == "PER":
                assert entity.coref_id in char_ids, \
                    f"Entity '{entity.text}' (coref={entity.coref_id}) has no matching character"

    def test_quote_speakers_resolve_to_characters(self, tmp_path):
        """Every quote with a known speaker should have speaker_name populated."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        char_ids = {c.coref_id for c in result.characters}
        for quote in result.quotes:
            if quote.speaker_coref_id in char_ids:
                assert quote.speaker_name != "", \
                    f"Quote '{quote.quote_text[:30]}...' has coref_id={quote.speaker_coref_id} " \
                    f"but speaker_name is empty"

    def test_entity_start_before_end(self, tmp_path):
        """start_token must be <= end_token for every entity."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for entity in result.entities:
            assert entity.start_token <= entity.end_token, \
                f"Entity '{entity.text}' has start={entity.start_token} > end={entity.end_token}"

    def test_quote_start_before_end(self, tmp_path):
        """quote_start must be <= quote_end for every quote."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for quote in result.quotes:
            assert quote.quote_start <= quote.quote_end, \
                f"Quote has start={quote.quote_start} > end={quote.quote_end}"

    def test_token_ids_are_sequential(self, tmp_path):
        """Token IDs should be monotonically non-decreasing."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for i in range(1, len(result.tokens)):
            assert result.tokens[i].token_id >= result.tokens[i - 1].token_id, \
                f"Token ID not sequential at index {i}: " \
                f"{result.tokens[i-1].token_id} → {result.tokens[i].token_id}"

    def test_token_offsets_non_negative(self, tmp_path):
        """All token byte offsets should be >= 0."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for token in result.tokens:
            assert token.token_offset_begin >= 0, \
                f"Token '{token.word}' has negative offset_begin={token.token_offset_begin}"
            assert token.token_offset_end >= token.token_offset_begin, \
                f"Token '{token.word}' offset_end < offset_begin"

    def test_character_canonical_name_not_empty(self, tmp_path):
        """Every character must have a non-empty canonical name."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for char in result.characters:
            assert char.name, f"Character coref_id={char.coref_id} has empty name"
            assert not char.name.startswith("CHARACTER_"), \
                f"Character coref_id={char.coref_id} fell back to placeholder name"

    def test_entity_types_valid(self, tmp_path):
        """Per deep_research_context.md: entity cat must be PER, LOC, FAC, GPE, VEH, ORG (or empty)."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        valid_cats = {"PER", "LOC", "FAC", "GPE", "VEH", "ORG", ""}
        for entity in result.entities:
            assert entity.cat in valid_cats, \
                f"Entity '{entity.text}' has invalid cat='{entity.cat}'"

    def test_entity_prop_types_valid(self, tmp_path):
        """Per deep_research_context.md: prop must be PROP, NOM, or PRON."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        valid_props = {"PROP", "NOM", "PRON"}
        for entity in result.entities:
            assert entity.prop in valid_props, \
                f"Entity '{entity.text}' has invalid prop='{entity.prop}'"

    def test_mention_count_positive_for_named_characters(self, tmp_path):
        """Characters with proper names should have mention_count > 0."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for char in result.characters:
            assert char.mention_count > 0, \
                f"Character '{char.name}' has zero mention_count"


# ============================================================================
# 4. Text cleaner content-preservation QC
# ============================================================================

class TestCleanerContentPreservation:
    """Verify the cleaner doesn't destroy legitimate literary content."""

    def test_short_chapter_survives(self):
        """A short but legitimate chapter should not be emptied."""
        short_chapter = (
            "It was the best of times, it was the worst of times, it was the age of "
            "wisdom, it was the age of foolishness."
        )
        result = clean_text(short_chapter)
        assert len(result.strip()) > 50

    def test_chapter_with_numbers_in_text(self):
        """In-text numbers (years, ages, addresses) should survive."""
        text = (
            "In the year 1843, Scrooge was 67 years old. "
            "He lived at 42 Baker Street.\n\n"
            "The clock struck 12."
        )
        result = clean_text(text)
        assert "1843" in result
        assert "67" in result
        assert "42 Baker Street" in result
        assert "12" in result

    def test_standalone_page_numbers_removed_but_text_numbers_kept(self):
        """Only standalone number lines are removed, not numbers in sentences."""
        text = "The story continues.\n42\nHe counted 42 coins.\n\n15\nFifteen shillings."
        result = clean_text(text)
        assert "42 coins" in result
        assert "Fifteen shillings" in result
        # Standalone numbers should be gone
        lines = result.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.isdigit():
                pytest.fail(f"Standalone page number '{stripped}' was not removed")

    def test_copyright_at_start_removed_content_preserved(self):
        """A real copyright block followed by story text."""
        text = (
            "Copyright \u00a9 2024 by Charles Dickens Estate\n"
            "All rights reserved.\n"
            "Published by Penguin Classics\n"
            "ISBN 978-0-14-043843-4\n"
            "\n"
            "Marley was dead: to begin with."
        )
        result = clean_text(text)
        assert "Copyright" not in result
        assert "ISBN" not in result
        assert "Marley was dead" in result

    def test_chapter_heading_not_false_positive_removed(self):
        """A chapter heading like 'Chapter 1' in text should not be removed."""
        text = "Chapter One\n\nScrooge sat in his counting-house."
        result = clean_text(text)
        assert "Scrooge sat" in result

    def test_em_dash_dialogue_attribution(self):
        """Em-dash dialogue attribution should be normalized but preserved."""
        text = "\u2014 Charles Dickens, A Christmas Carol"
        result = clean_text(text)
        assert "Charles Dickens" in result

    def test_multiple_consecutive_cleans_stable(self):
        """Applying clean_text N times should converge (no oscillation)."""
        text = (
            "&amp; Copyright \u00a9 2024\n\n42\n\n"
            "\u201cHello,\u201d said Scrooge.\n\n"
            "* * *\n\n"
            "The end."
        )
        prev = text
        for _ in range(5):
            prev = clean_text(prev)
        final = clean_text(prev)
        assert final == prev, "Cleaning has not converged after 5 iterations"


# ============================================================================
# 5. Output file structure compliance
# ============================================================================

class TestOutputFileStructure:
    """Verify outputs match the plan's file structure spec.

    Per bookrag_pipeline_plan.md:
    data/processed/{book_id}/
    ├── raw/full_text.txt
    ├── raw/chapters/chapter_01.txt ...
    ├── booknlp/parsed_output.json
    """

    @patch("pipeline.epub_parser.epub.read_epub")
    def test_epub_output_structure(self, mock_read, tmp_path):
        """EPUB parser must produce raw/full_text.txt and raw/chapters/chapter_NN.txt."""
        import ebooklib
        from pipeline.epub_parser import parse_epub

        epub_file = tmp_path / "test.epub"
        epub_file.touch()

        chapters_html = []
        for i in range(5):
            item = MagicMock()
            item.get_id.return_value = f"ch{i}"
            item.get_content.return_value = (
                f"<html><body><p>Chapter {i+1} text with enough words to pass the "
                f"content filter for chapter detection heuristic number {i}.</p></body></html>"
            ).encode("utf-8")
            item.get_type.return_value = ebooklib.ITEM_DOCUMENT
            chapters_html.append(item)

        mock_book = MagicMock()
        mock_book.spine = [(f"ch{i}", "yes") for i in range(5)]
        mock_book.get_items.return_value = chapters_html
        mock_read.return_value = mock_book

        output_dir = tmp_path / "data" / "processed" / "test" / "raw"
        result = parse_epub(epub_file, output_dir=output_dir)

        # Verify structure
        assert (output_dir / "full_text.txt").exists()
        assert (output_dir / "full_text.txt").stat().st_size > 0

        chapters_dir = output_dir / "chapters"
        assert chapters_dir.is_dir()
        for i in range(1, 6):
            ch_file = chapters_dir / f"chapter_{i:02d}.txt"
            assert ch_file.exists(), f"Missing {ch_file}"
            assert ch_file.stat().st_size > 0, f"Empty {ch_file}"

        # No extra chapter files
        ch_files = list(chapters_dir.glob("chapter_*.txt"))
        assert len(ch_files) == 5

    def test_booknlp_json_output_structure(self, tmp_path):
        """Parsed BookNLP JSON should contain all expected top-level keys."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        data = asdict(result)
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert "book_id" in parsed
        assert "tokens" in parsed
        assert "entities" in parsed
        assert "quotes" in parsed
        assert "characters" in parsed
        assert parsed["book_id"] == "christmas_carol"

    def test_chapter_filenames_zero_padded(self):
        """Chapter files must be zero-padded: chapter_01.txt, not chapter_1.txt."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)
        for i in range(1, pb.chapter_count + 1):
            expected = f"chapter_{i:02d}.txt"
            assert re.match(r"chapter_\d{2,}\.txt", expected)


# ============================================================================
# 6. Serialization round-trip fidelity
# ============================================================================

class TestSerializationRoundTrip:
    """Verify data survives JSON serialization and deserialization."""

    def test_booknlp_output_roundtrip(self, tmp_path):
        """BookNLPOutput → JSON → reconstruct should be lossless."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        original = parse_booknlp_outputs(out, "christmas_carol")

        data = asdict(original)
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        restored = json.loads(json_str)

        assert restored["book_id"] == original.book_id
        assert len(restored["tokens"]) == len(original.tokens)
        assert len(restored["entities"]) == len(original.entities)
        assert len(restored["quotes"]) == len(original.quotes)
        assert len(restored["characters"]) == len(original.characters)

        # Spot-check a character
        orig_char = original.characters[0]
        rest_char = restored["characters"][0]
        assert rest_char["name"] == orig_char.name
        assert rest_char["coref_id"] == orig_char.coref_id
        assert rest_char["aliases"] == orig_char.aliases
        assert rest_char["agent_actions"] == orig_char.agent_actions
        assert rest_char["modifiers"] == orig_char.modifiers

    def test_token_roundtrip_preserves_types(self, tmp_path):
        """Token fields should preserve their types through JSON serialization."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        original = parse_booknlp_outputs(out, "christmas_carol")

        data = asdict(original)
        restored = json.loads(json.dumps(data))

        for tok_dict in restored["tokens"]:
            assert isinstance(tok_dict["token_id"], int)
            assert isinstance(tok_dict["sentence_id"], int)
            assert isinstance(tok_dict["word"], str)
            assert isinstance(tok_dict["coref_id"], int)

    def test_parsed_book_full_text_matches_chapters(self):
        """ParsedBook full_text must be reconstructable from chapter_texts + markers."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        reconstructed_parts: list[str] = []
        for i, ch in enumerate(chapters, start=1):
            reconstructed_parts.append(f"=== CHAPTER {i} ===\n\n")
            reconstructed_parts.append(ch)
            reconstructed_parts.append("\n\n")

        assert pb.full_text == "".join(reconstructed_parts)


# ============================================================================
# 7. Realistic A Christmas Carol smoke tests
# ============================================================================

class TestChristmasCarolSmoke:
    """End-to-end smoke tests with A Christmas Carol fixture data."""

    def test_five_staves(self):
        """A Christmas Carol has 5 staves (chapters)."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)
        assert pb.chapter_count == 5

    def test_book_id_slug(self):
        """book_id for 'A Christmas Carol.epub' should be 'a_christmas_carol'."""
        assert _slugify("A Christmas Carol.epub") == "a_christmas_carol"

    def test_known_characters_present(self, tmp_path):
        """The four main characters should be in BookNLP output."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        names = {c.name for c in result.characters}
        assert "Scrooge" in names
        assert "Bob Cratchit" in names
        assert "Marley" in names
        assert "Tiny Tim" in names

    def test_scrooge_is_most_mentioned(self, tmp_path):
        """Scrooge should have the highest mention_count."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        scrooge = next(c for c in result.characters if c.name == "Scrooge")
        for char in result.characters:
            assert scrooge.mention_count >= char.mention_count, \
                f"'{char.name}' ({char.mention_count}) has more mentions than Scrooge ({scrooge.mention_count})"

    def test_scrooge_has_aliases(self, tmp_path):
        """Scrooge should have 'Ebenezer' and 'old sinner' as aliases."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        scrooge = next(c for c in result.characters if c.name == "Scrooge")
        assert "Ebenezer" in scrooge.aliases
        assert "old sinner" in scrooge.aliases

    def test_scrooge_modifiers(self, tmp_path):
        """Scrooge should have 'old' and 'covetous' as modifiers."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        scrooge = next(c for c in result.characters if c.name == "Scrooge")
        assert "old" in scrooge.modifiers
        assert "covetous" in scrooge.modifiers

    def test_scrooge_possessions(self, tmp_path):
        """Scrooge should possess the 'counting-house'."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        scrooge = next(c for c in result.characters if c.name == "Scrooge")
        assert "counting-house" in scrooge.possessions

    def test_scrooge_quote_attributed(self, tmp_path):
        """Scrooge's 'I am not the man I was' quote should have his name."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        scrooge_quotes = [q for q in result.quotes if q.speaker_name == "Scrooge"]
        assert len(scrooge_quotes) >= 1
        texts = " ".join(q.quote_text for q in scrooge_quotes)
        assert "I am not the man I was" in texts

    def test_tiny_tim_quote(self, tmp_path):
        """Tiny Tim's 'God bless us, every one!' should be attributed."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        tim_quotes = [q for q in result.quotes if q.speaker_name == "Tiny Tim"]
        assert len(tim_quotes) >= 1
        assert any("God bless us" in q.quote_text for q in tim_quotes)

    def test_entity_types_present(self, tmp_path):
        """Multiple entity types should be represented: PER, LOC, FAC."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        cats = {e.cat for e in result.entities}
        assert "PER" in cats
        assert "LOC" in cats
        assert "FAC" in cats

    def test_all_characters_male(self, tmp_path):
        """All four main characters in A Christmas Carol are male."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        for char in result.characters:
            assert char.gender == "male", \
                f"'{char.name}' has gender='{char.gender}', expected 'male'"

    def test_marley_is_dead(self, tmp_path):
        """Marley should have 'dead' as a modifier."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")

        marley = next(c for c in result.characters if c.name == "Marley")
        assert "dead" in marley.modifiers

    def test_cleaned_christmas_carol_has_key_passages(self):
        """After full cleaning, key passages from each stave should survive."""
        chapters = _build_christmas_carol_chapters()
        cleaned = clean_chapters(chapters)

        # Stave 1
        assert "dead as a door-nail" in cleaned[0]
        assert "counting-house" in cleaned[0]
        # Stave 2
        assert "Ghost of Christmas Past" in cleaned[1]
        # Stave 3
        assert "Ghost of Christmas Present" in cleaned[2]
        assert "God bless us" in cleaned[2]
        # Stave 4
        assert "gravestone" in cleaned[3]
        # Stave 5
        assert "NOT die" in cleaned[4]
        assert "salary" in cleaned[4]


# ============================================================================
# 8. Cross-module data shape validation
# ============================================================================

class TestCrossModuleDataShape:
    """Validate the data shape contracts between pipeline stages."""

    def test_parsed_book_chapter_count_matches_texts(self):
        """chapter_count must equal len(chapter_texts) and len(chapter_boundaries)."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)
        assert pb.chapter_count == len(pb.chapter_texts)
        assert pb.chapter_count == len(pb.chapter_boundaries)

    def test_boundaries_monotonically_increasing(self):
        """Chapter boundaries must be strictly increasing and non-overlapping."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)

        prev_end = 0
        for i, (start, end) in enumerate(pb.chapter_boundaries):
            assert start >= prev_end, \
                f"Chapter {i+1} start={start} overlaps with prev end={prev_end}"
            assert end > start, f"Chapter {i+1} has zero or negative length"
            prev_end = end

    def test_full_text_ends_with_double_newline(self):
        """full_text should end with the trailing separator."""
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)
        assert pb.full_text.endswith("\n\n")

    def test_booknlp_output_book_id_propagated(self, tmp_path):
        """book_id in BookNLPOutput should match what was passed in."""
        out = _write_booknlp_fixtures(tmp_path, "christmas_carol")
        result = parse_booknlp_outputs(out, "christmas_carol")
        assert result.book_id == "christmas_carol"

    def test_cleaning_config_defaults_match_plan_yaml(self):
        """CleaningConfig defaults must match the config.yaml spec in the plan doc.

        Per bookrag_pipeline_plan.md:
        cleaning:
          strip_html: true
          remove_toc: true
          remove_copyright: true
          keep_epigraphs: true
          keep_section_breaks: true
        """
        cfg = CleaningConfig()
        assert cfg.strip_html is True
        assert cfg.remove_toc is True
        assert cfg.remove_copyright is True
        assert cfg.keep_epigraphs is True
        assert cfg.keep_section_breaks is True

    def test_book_id_is_valid_path_component(self):
        """book_id must be safe for use in file paths (no spaces, slashes, etc.)."""
        test_names = [
            "A Christmas Carol.epub",
            "Red Rising.epub",
            "Les Misérables.epub",
            "Book: A Story (2024).epub",
        ]
        for name in test_names:
            slug = _slugify(name)
            assert "/" not in slug, f"Slash in slug for '{name}': {slug}"
            assert " " not in slug, f"Space in slug for '{name}': {slug}"
            assert "\\" not in slug, f"Backslash in slug for '{name}': {slug}"
            assert slug == slug.lower(), f"Uppercase in slug for '{name}': {slug}"
            assert len(slug) > 0, f"Empty slug for '{name}'"
