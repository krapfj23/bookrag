"""Quality-control tests for the BookRAG ingestion pipeline.

These tests validate cross-module data contracts, structural invariants,
and end-to-end data flow between pipeline stages. They use realistic
synthetic data modeled on A Christmas Carol (the project's test book).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.epub_parser import ParsedBook, _slugify
from pipeline.text_cleaner import CleaningConfig, clean_text, clean_chapters
from pipeline.booknlp_runner import (
    TokenAnnotation,
    EntityMention,
    QuoteAttribution,
    CharacterProfile,
    BookNLPOutput,
    parse_booknlp_output,
)


# ============================================================================
# Helpers
# ============================================================================

def _build_christmas_carol_chapters() -> list[str]:
    return [
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
        (
            "When Scrooge awoke, it was so dark, that looking out of bed, he could "
            "scarcely distinguish the transparent window from the opaque walls of his chamber.\n\n"
            "'I am the Ghost of Christmas Past,' said the Spirit. 'Rise! and walk with me!'\n\n"
            "They flew together through the night sky to visit scenes from Scrooge's youth."
        ),
        (
            "Awaking in the middle of a prodigiously tough snore, Scrooge had no occasion "
            "to be told that the bell was again upon the stroke of One.\n\n"
            "'I am the Ghost of Christmas Present,' said the Spirit. 'Look upon me!'\n\n"
            "The Spirit showed Scrooge the Cratchit family gathered around their meager "
            "Christmas dinner. Tiny Tim sat close to his father's side.\n\n"
            "'God bless us, every one!' said Tiny Tim."
        ),
        (
            "The Phantom slowly, gravely, silently, approached. It was shrouded in a deep "
            "black garment, which concealed its head, its face, its form.\n\n"
            "The Ghost of Christmas Yet to Come pointed silently at a gravestone bearing "
            "the name Ebenezer Scrooge.\n\n"
            "'Spirit!' he cried, 'hear me! I am not the man I was.'"
        ),
        (
            "Scrooge was better than his word. He did it all, and infinitely more; "
            "and to Tiny Tim, who did NOT die, he was a second father.\n\n"
            "Scrooge raised Bob Cratchit's salary and kept Christmas well from that day forward.\n\n"
            "'God bless us, every one!' said Tiny Tim, the last of all."
        ),
    ]


def _build_parsed_book(chapters: list[str], book_id: str = "a_christmas_carol") -> ParsedBook:
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
    return ParsedBook(
        book_id=book_id, chapter_count=len(chapters),
        chapter_texts=chapters, full_text="".join(parts),
        chapter_boundaries=boundaries,
    )


def _write_booknlp_fixtures(tmp_path: Path, book_id: str) -> Path:
    out = tmp_path / "booknlp"
    out.mkdir()

    (out / f"{book_id}.tokens").write_text(
        "token_ID_within_document\tsentence_ID\tbyte_onset\tbyte_offset\t"
        "word\tlemma\tPOS_tag\tdependency_relation\tCOREF\n"
        "0\t0\t0\t6\tMarley\tmarley\tNNP\tnsubj\t2\n"
        "1\t0\t7\t10\twas\tbe\tVBD\troot\t-1\n"
        "5\t1\t45\t52\tScrooge\tscrooge\tNNP\tnsubj\t0\n"
        "7\t1\t58\t60\the\the\tPRP\tnsubj\t0\n"
        "10\t5\t400\t403\tBob\tbob\tNNP\tcompound\t1\n"
        "11\t5\t404\t412\tCratchit\tcratchit\tNNP\tnsubj\t1\n"
        "13\t8\t600\t604\tTiny\ttiny\tNNP\tcompound\t3\n"
        "14\t8\t605\t608\tTim\ttim\tNNP\tnsubj\t3\n",
        encoding="utf-8",
    )
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
    (out / f"{book_id}.quotes").write_text(
        "quote_start\tquote_end\tquote\tchar_id\n"
        "250\t280\tA merry Christmas, uncle!\t-1\n"
        "500\t530\tGod bless us, every one!\t3\n"
        "550\t600\tI am not the man I was.\t0\n",
        encoding="utf-8",
    )
    book_data = {
        "characters": [
            {"id": 0, "names": {"Scrooge": 150, "Ebenezer": 12, "Mr. Scrooge": 8},
             "g": "male", "agent": [{"w": "said", "c": 30}], "patient": [{"w": "visited", "c": 3}],
             "poss": ["counting-house"], "mod": ["old", "covetous"]},
            {"id": 1, "names": {"Bob Cratchit": 40, "Cratchit": 25, "Bob": 18},
             "g": "male", "agent": [{"w": "said", "c": 12}], "patient": [],
             "poss": ["desk"], "mod": ["poor"]},
            {"id": 2, "names": {"Marley": 35, "Jacob Marley": 20},
             "g": "male", "agent": [{"w": "warned", "c": 3}], "patient": [],
             "poss": ["chains"], "mod": ["dead"]},
            {"id": 3, "names": {"Tiny Tim": 15, "Tim": 8},
             "g": "male", "agent": [{"w": "said", "c": 2}], "patient": [],
             "poss": ["crutch"], "mod": ["little"]},
        ]
    }
    (out / f"{book_id}.book").write_text(json.dumps(book_data), encoding="utf-8")
    return out


# ============================================================================
# 1. ParsedBook <-> text_cleaner contract
# ============================================================================

class TestParserCleanerContract:
    def test_cleaned_chapters_same_count(self):
        chapters = _build_christmas_carol_chapters()
        assert len(clean_chapters(chapters)) == len(chapters)

    def test_cleaned_text_is_nonempty(self):
        for i, ch in enumerate(clean_chapters(_build_christmas_carol_chapters())):
            assert len(ch.strip()) > 0, f"Chapter {i+1} emptied"

    def test_cleaning_preserves_story_content(self):
        full = " ".join(clean_chapters(_build_christmas_carol_chapters()))
        for kw in ["Scrooge", "Marley", "Cratchit", "Christmas", "Ghost", "Tiny Tim"]:
            assert kw in full

    def test_cleaning_preserves_dialogue(self):
        full = " ".join(clean_chapters(_build_christmas_carol_chapters()))
        assert "God bless us, every one!" in full

    def test_cleaning_canonicalizes_section_breaks(self):
        result = clean_text("First.\n\n* * *\n\nSecond.\n\n---\n\nThird.")
        # Scene breaks survive cleaning, rewritten to the canonical *** sentinel.
        assert result.count("***") == 2
        assert "* * *" not in result
        assert "---" not in result

    def test_clean_then_rebuild_boundaries(self):
        cleaned = clean_chapters(_build_christmas_carol_chapters())
        pb = _build_parsed_book(cleaned)
        for i, (s, e) in enumerate(pb.chapter_boundaries):
            assert pb.full_text[s:e] == cleaned[i]

    def test_idempotent_cleaning(self):
        once = clean_chapters(_build_christmas_carol_chapters())
        twice = clean_chapters(once)
        assert once == twice

    def test_unicode_quotes_preserved_by_default(self):
        # Smart quotes survive cleaning so BookNLP's dialogue/speaker detection
        # works and the reader can style them natively. ASCII folding is opt-in.
        result = clean_text("\u201cBah!\u201d said Scrooge.")
        assert "\u201c" in result
        assert "\u201d" in result
        assert "Bah!" in result

    def test_unicode_quotes_normalized_when_opted_in(self):
        from pipeline.text_cleaner import CleaningConfig
        result = clean_text(
            "\u201cBah!\u201d said Scrooge.",
            CleaningConfig(ascii_quotes=True),
        )
        assert "\u201c" not in result
        assert '"Bah!"' in result


# ============================================================================
# 2. ParsedBook <-> BookNLP contract
# ============================================================================

class TestParserBookNLPContract:
    def test_token_offset_to_chapter_mapping(self):
        pb = _build_parsed_book(_build_christmas_carol_chapters())
        for ch_idx, (start, end) in enumerate(pb.chapter_boundaries):
            mid = (start + end) // 2
            mapped = next(i for i, (s, e) in enumerate(pb.chapter_boundaries) if s <= mid < e)
            assert mapped == ch_idx

    def test_chapter_text_recoverable_from_full_text(self):
        pb = _build_parsed_book(_build_christmas_carol_chapters())
        for i, (s, e) in enumerate(pb.chapter_boundaries):
            assert pb.full_text[s:e] == pb.chapter_texts[i]

    def test_boundaries_cover_all_content(self):
        pb = _build_parsed_book(_build_christmas_carol_chapters())
        assert sum(e - s for s, e in pb.chapter_boundaries) == sum(len(c) for c in pb.chapter_texts)

    def test_offset_before_first_chapter_maps_to_none(self):
        pb = _build_parsed_book(_build_christmas_carol_chapters())
        for s, e in pb.chapter_boundaries:
            assert not (s <= 0 < e), "Offset 0 should be in marker, not chapter"


# ============================================================================
# 3. BookNLP internal consistency
# ============================================================================

class TestBookNLPInternalConsistency:
    def test_entity_coref_ids_match_characters(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        char_ids = {c.coref_id for c in result.characters}
        for e in result.entities:
            if e.cat == "PER":
                assert e.coref_id in char_ids, f"'{e.text}' coref={e.coref_id} unmatched"

    def test_quote_speakers_resolve(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for q in result.quotes:
            if q.speaker_coref_id is not None and q.speaker_coref_id in result.coref_id_to_name:
                assert result.coref_id_to_name[q.speaker_coref_id] != ""

    def test_entity_start_before_end(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for e in result.entities:
            assert e.start_token <= e.end_token

    def test_token_ids_sequential(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for i in range(1, len(result.tokens)):
            assert result.tokens[i].token_id >= result.tokens[i - 1].token_id

    def test_token_offsets_non_negative(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for t in result.tokens:
            assert t.start_char >= 0 and t.end_char >= t.start_char

    def test_character_names_not_empty(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for c in result.characters:
            assert c.canonical_name and not c.canonical_name.startswith("CHARACTER_")

    def test_entity_types_valid(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for e in result.entities:
            assert e.cat in {"PER", "LOC", "FAC", "GPE", "VEH", "ORG", ""}

    def test_entity_prop_types_valid(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for e in result.entities:
            assert e.prop in {"PROP", "NOM", "PRON"}

    def test_coref_id_to_name_populated(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for c in result.characters:
            assert result.coref_id_to_name[c.coref_id] == c.canonical_name


# ============================================================================
# 4. Content preservation
# ============================================================================

class TestCleanerContentPreservation:
    def test_short_chapter_survives(self):
        assert len(clean_text("It was the best of times, it was the worst of times, it was.").strip()) > 30

    def test_numbers_in_text_kept(self):
        result = clean_text("In 1843, Scrooge was 67. He lived at 42 Baker Street.")
        assert "1843" in result and "67" in result and "42 Baker Street" in result

    def test_standalone_page_numbers_removed(self):
        result = clean_text("Story.\n42\nHe counted 42 coins.\n15\nFifteen.")
        assert "42 coins" in result
        lines = result.strip().split("\n")
        assert not any(l.strip().isdigit() for l in lines)

    def test_copyright_removed_content_kept(self):
        text = "Copyright \u00a9 2024 by Author\nAll rights reserved.\n\nMarley was dead."
        result = clean_text(text)
        assert "Copyright" not in result and "Marley was dead" in result

    def test_cleaning_converges(self):
        text = "&amp; \u201cHello\u201d\n42\n* * *\nThe end."
        prev = text
        for _ in range(5):
            prev = clean_text(prev)
        assert clean_text(prev) == prev


# ============================================================================
# 5. Output structure
# ============================================================================

class TestOutputFileStructure:
    @patch("pipeline.epub_parser.check_epub_decompressed_size")
    @patch("pipeline.epub_parser.epub.read_epub")
    def test_epub_output_structure(self, mock_read, mock_size_check, tmp_path):
        import ebooklib
        from pipeline.epub_parser import parse_epub

        epub_file = tmp_path / "test.epub"
        epub_file.touch()
        items = []
        for i in range(5):
            item = MagicMock()
            item.get_id.return_value = f"ch{i}"
            item.get_content.return_value = (
                f"<html><body><p>Chapter {i+1} of the story begins here with plenty of words "
                f"so the content detection heuristic is satisfied. The protagonist walked "
                f"through the cold dark streets of London on a foggy evening in December.</p></body></html>"
            ).encode("utf-8")
            item.get_type.return_value = ebooklib.ITEM_DOCUMENT
            items.append(item)
        mock_book = MagicMock()
        mock_book.spine = [(f"ch{i}", "yes") for i in range(5)]
        mock_book.get_items.return_value = items
        mock_read.return_value = mock_book

        out = tmp_path / "raw"
        parse_epub(epub_file, output_dir=out)
        assert (out / "full_text.txt").exists()
        assert len(list((out / "chapters").glob("chapter_*.txt"))) == 5

    def test_to_pipeline_dict_structure(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        d = result.to_pipeline_dict()
        assert {"entities", "quotes", "characters"} <= d.keys()
        assert len(d["entities"]) == len(result.entities)

    def test_pipeline_dict_entities_have_canonical_name(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for ent in result.to_pipeline_dict()["entities"]:
            assert isinstance(ent.get("canonical_name"), str)


# ============================================================================
# 6. Serialization round-trip
# ============================================================================

class TestSerializationRoundTrip:
    def test_pipeline_dict_json_roundtrip(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        restored = json.loads(json.dumps(result.to_pipeline_dict()))
        assert len(restored["entities"]) == len(result.entities)
        assert len(restored["characters"]) == len(result.characters)

    def test_parsed_book_full_text_matches_chapters(self):
        chapters = _build_christmas_carol_chapters()
        pb = _build_parsed_book(chapters)
        parts = []
        for i, ch in enumerate(chapters, 1):
            parts += [f"=== CHAPTER {i} ===\n\n", ch, "\n\n"]
        assert pb.full_text == "".join(parts)


# ============================================================================
# 7. A Christmas Carol smoke tests
# ============================================================================

class TestChristmasCarolSmoke:
    def test_five_staves(self):
        assert _build_parsed_book(_build_christmas_carol_chapters()).chapter_count == 5

    def test_book_id_slug(self):
        assert _slugify("A Christmas Carol.epub") == "a_christmas_carol"

    def test_known_characters(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        names = {c.canonical_name for c in result.characters}
        assert {"Scrooge", "Bob Cratchit", "Marley", "Tiny Tim"} <= names

    def test_scrooge_most_mentioned(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        scrooge = next(c for c in result.characters if c.canonical_name == "Scrooge")
        s_total = sum(scrooge.aliases.values())
        assert all(s_total >= sum(c.aliases.values()) for c in result.characters)

    def test_scrooge_aliases(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        scrooge = next(c for c in result.characters if c.canonical_name == "Scrooge")
        assert "Ebenezer" in scrooge.aliases and "Mr. Scrooge" in scrooge.aliases

    def test_scrooge_modifiers(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        scrooge = next(c for c in result.characters if c.canonical_name == "Scrooge")
        assert "old" in scrooge.modifiers and "covetous" in scrooge.modifiers

    def test_scrooge_possessions(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        scrooge = next(c for c in result.characters if c.canonical_name == "Scrooge")
        assert "counting-house" in scrooge.possessions

    def test_scrooge_quote(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        sq = [q for q in result.quotes if result.coref_id_to_name.get(q.speaker_coref_id) == "Scrooge"]
        assert any("I am not the man I was" in q.text for q in sq)

    def test_tiny_tim_quote(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        tq = [q for q in result.quotes if result.coref_id_to_name.get(q.speaker_coref_id) == "Tiny Tim"]
        assert any("God bless us" in q.text for q in tq)

    def test_entity_types(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        cats = {e.cat for e in result.entities}
        assert {"PER", "LOC", "FAC"} <= cats

    def test_all_male(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        assert all(c.gender == "male" for c in result.characters)

    def test_marley_is_dead(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        marley = next(c for c in result.characters if c.canonical_name == "Marley")
        assert "dead" in marley.modifiers

    def test_key_passages_survive_cleaning(self):
        cleaned = clean_chapters(_build_christmas_carol_chapters())
        assert "dead as a door-nail" in cleaned[0]
        assert "Ghost of Christmas Past" in cleaned[1]
        assert "Ghost of Christmas Present" in cleaned[2]
        assert "gravestone" in cleaned[3]
        assert "NOT die" in cleaned[4]


# ============================================================================
# 8. Cross-module data shape
# ============================================================================

class TestCrossModuleDataShape:
    def test_chapter_count_consistent(self):
        pb = _build_parsed_book(_build_christmas_carol_chapters())
        assert pb.chapter_count == len(pb.chapter_texts) == len(pb.chapter_boundaries)

    def test_boundaries_monotonic(self):
        pb = _build_parsed_book(_build_christmas_carol_chapters())
        prev = 0
        for s, e in pb.chapter_boundaries:
            assert s >= prev and e > s
            prev = e

    def test_full_text_ends_with_newlines(self):
        assert _build_parsed_book(_build_christmas_carol_chapters()).full_text.endswith("\n\n")

    def test_book_id_propagated(self, tmp_path):
        assert parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc").book_id == "cc"

    def test_config_defaults_match_plan(self):
        cfg = CleaningConfig()
        assert cfg.strip_html and cfg.remove_toc and cfg.remove_copyright
        assert cfg.keep_epigraphs and cfg.keep_section_breaks

    def test_book_id_valid_path(self):
        for name in ["A Christmas Carol.epub", "Red Rising.epub", "Les Misérables.epub"]:
            slug = _slugify(name)
            assert "/" not in slug and " " not in slug and slug == slug.lower() and slug

    def test_pipeline_dict_quotes_have_speaker_name(self, tmp_path):
        result = parse_booknlp_output(_write_booknlp_fixtures(tmp_path, "cc"), "cc")
        for q in result.to_pipeline_dict()["quotes"]:
            assert isinstance(q.get("speaker_name"), str)
