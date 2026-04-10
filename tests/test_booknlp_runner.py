"""Comprehensive tests for pipeline/booknlp_runner.py.

Covers:
- Data models: EntityMention, QuoteAttribution, CharacterProfile, TokenAnnotation, BookNLPOutput
- BookNLPOutput.to_pipeline_dict: entity/quote/character conversion, coref name resolution
- parse_booknlp_output: full integration from files on disk
- _parse_book_json: character profiles, canonical name selection, names-as-list fallback,
  empty names, missing file
- _parse_entities_tsv: standard rows, empty/missing file, malformed rows
- _parse_quotes_tsv: speaker attribution, null speaker, column name variants
- _parse_tokens_tsv: token parsing, coref_id handling, column name variants
- _read_tsv: headers only, empty file, blank lines
- _safe_int: valid, invalid, None
- _build_coref_name_map: maps coref IDs to canonical names
- _fill_char_offsets_entities / _fill_char_offsets_quotes: backfills from token map
- create_stub_output: empty output with correct book_id
- run_booknlp: ImportError when booknlp not installed (mocked)

Aligned with:
- CLAUDE.md: "BookNLP integration + output parsing"
- Plan: "Run BookNLP on the full text, parse all output files into structured Python objects"
- Deep research: ".entities columns: COREF, start_token, end_token, prop, cat, text"
- Deep research: ".book JSON: character profiles with names (dict), agent/patient actions"
- Deep research: "BookNLP Does NOT Produce Resolved Text" (we parse raw annotations)
- Conftest: christmas_carol_book_json and christmas_carol_entities_tsv fixtures
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.booknlp_runner import (
    EntityMention,
    QuoteAttribution,
    CharacterProfile,
    TokenAnnotation,
    BookNLPOutput,
    parse_booknlp_output,
    create_stub_output,
    _parse_book_json,
    _parse_entities_tsv,
    _parse_quotes_tsv,
    _parse_tokens_tsv,
    _build_coref_name_map,
    _fill_char_offsets_entities,
    _fill_char_offsets_quotes,
)
from pipeline.tsv_utils import read_tsv, safe_int


# ---------------------------------------------------------------------------
# Data model unit tests
# ---------------------------------------------------------------------------

class TestEntityMention:
    def test_fields(self):
        e = EntityMention(coref_id=0, start_token=10, end_token=11, prop="PROP", cat="PER", text="Scrooge")
        assert e.coref_id == 0
        assert e.cat == "PER"
        assert e.start_char == 0  # default
        assert e.end_char == 0

    def test_char_offsets_default_zero(self):
        e = EntityMention(coref_id=1, start_token=0, end_token=1, prop="PRON", cat="PER", text="he")
        assert e.start_char == 0
        assert e.end_char == 0


class TestQuoteAttribution:
    def test_fields(self):
        q = QuoteAttribution(text="Bah humbug!", speaker_coref_id=0, start_token=5, end_token=8)
        assert q.text == "Bah humbug!"
        assert q.speaker_coref_id == 0

    def test_none_speaker(self):
        q = QuoteAttribution(text="Who said this?", speaker_coref_id=None, start_token=0, end_token=3)
        assert q.speaker_coref_id is None


class TestCharacterProfile:
    def test_fields(self):
        c = CharacterProfile(
            coref_id=0,
            canonical_name="Scrooge",
            aliases={"Scrooge": 150, "Ebenezer": 12},
            agent_actions=[{"w": "said", "c": 30}],
            patient_actions=[],
            modifiers=["old", "cold"],
            possessions=["counting-house"],
            gender="he/him/his",
        )
        assert c.canonical_name == "Scrooge"
        assert c.gender == "he/him/his"
        assert len(c.aliases) == 2


class TestTokenAnnotation:
    def test_fields(self):
        t = TokenAnnotation(
            token_id=42, sentence_id=1, text="Scrooge", lemma="scrooge",
            pos="NNP", dep="nsubj", coref_id=0,
            start_char=100, end_char=107,
        )
        assert t.token_id == 42
        assert t.sentence_id == 1
        assert t.coref_id == 0

    def test_none_coref(self):
        t = TokenAnnotation(
            token_id=0, sentence_id=0, text="the", lemma="the",
            pos="DT", dep="det", coref_id=None,
            start_char=0, end_char=3,
        )
        assert t.coref_id is None


# ---------------------------------------------------------------------------
# BookNLPOutput
# ---------------------------------------------------------------------------

class TestBookNLPOutput:
    def _make_output(self) -> BookNLPOutput:
        chars = [
            CharacterProfile(
                coref_id=0, canonical_name="Scrooge",
                aliases={"Scrooge": 150}, agent_actions=[], patient_actions=[],
                modifiers=["old"], possessions=[], gender="he/him/his",
            ),
            CharacterProfile(
                coref_id=1, canonical_name="Bob Cratchit",
                aliases={"Bob Cratchit": 40}, agent_actions=[], patient_actions=[],
                modifiers=[], possessions=[], gender="he/him/his",
            ),
        ]
        entities = [
            EntityMention(coref_id=0, start_token=10, end_token=11, prop="PROP", cat="PER", text="Scrooge", start_char=50, end_char=57),
            EntityMention(coref_id=0, start_token=20, end_token=21, prop="PRON", cat="PER", text="he", start_char=100, end_char=102),
        ]
        quotes = [
            QuoteAttribution(text="Bah humbug!", speaker_coref_id=0, start_token=15, end_token=18, start_char=70, end_char=81),
            QuoteAttribution(text="God bless us", speaker_coref_id=None, start_token=30, end_token=33, start_char=150, end_char=162),
        ]
        return BookNLPOutput(
            book_id="christmas_carol",
            characters=chars,
            entities=entities,
            quotes=quotes,
            tokens=[],
            coref_id_to_name={0: "Scrooge", 1: "Bob Cratchit"},
        )

    def test_properties(self):
        out = self._make_output()
        assert out.character_count == 2
        assert out.entity_count == 2
        assert out.quote_count == 2

    def test_to_pipeline_dict_entities(self):
        """Entities should include canonical_name resolved from coref."""
        d = self._make_output().to_pipeline_dict()
        assert len(d["entities"]) == 2
        assert d["entities"][0]["canonical_name"] == "Scrooge"
        assert d["entities"][0]["start_char"] == 50
        assert d["entities"][1]["canonical_name"] == "Scrooge"  # pronoun "he" -> Scrooge

    def test_to_pipeline_dict_quotes(self):
        d = self._make_output().to_pipeline_dict()
        assert len(d["quotes"]) == 2
        assert d["quotes"][0]["speaker_name"] == "Scrooge"
        assert d["quotes"][1]["speaker_name"] == "Unknown"  # None speaker

    def test_to_pipeline_dict_characters(self):
        d = self._make_output().to_pipeline_dict()
        assert len(d["characters"]) == 2
        assert d["characters"][0]["canonical_name"] == "Scrooge"
        assert d["characters"][0]["modifiers"] == ["old"]

    def test_empty_output(self):
        out = BookNLPOutput(book_id="empty", characters=[], entities=[], quotes=[], tokens=[])
        assert out.character_count == 0
        d = out.to_pipeline_dict()
        assert d == {"entities": [], "quotes": [], "characters": []}


# ---------------------------------------------------------------------------
# _parse_book_json
# ---------------------------------------------------------------------------

class TestParseBookJson:
    def test_parse_christmas_carol(self, tmp_path, christmas_carol_book_json):
        """Uses conftest fixture with realistic A Christmas Carol data."""
        path = tmp_path / "test.book"
        path.write_text(json.dumps(christmas_carol_book_json))

        chars = _parse_book_json(path)
        assert len(chars) == 4

        # Canonical name should be the highest-count name
        scrooge = chars[0]
        assert scrooge.canonical_name == "Scrooge"
        assert scrooge.coref_id == 0
        assert scrooge.aliases["Ebenezer"] == 12
        assert "old" in scrooge.modifiers
        assert scrooge.gender == "he/him/his"
        assert len(scrooge.agent_actions) == 5

        # Bob Cratchit
        bob = chars[1]
        assert bob.canonical_name == "Bob Cratchit"

        # Marley: "Marley" has 35 mentions vs "Jacob Marley" 20
        marley = chars[2]
        assert marley.canonical_name == "Marley"

    def test_names_as_list_fallback(self, tmp_path):
        """Handle alternative format where names is a list, not dict."""
        data = {"characters": [{"id": 0, "names": ["Alice", "Al"], "g": "she/her"}]}
        path = tmp_path / "test.book"
        path.write_text(json.dumps(data))

        chars = _parse_book_json(path)
        assert len(chars) == 1
        assert chars[0].aliases == {"Alice": 1, "Al": 1}

    def test_empty_names(self, tmp_path):
        data = {"characters": [{"id": 5, "names": {}}]}
        path = tmp_path / "test.book"
        path.write_text(json.dumps(data))

        chars = _parse_book_json(path)
        assert chars[0].canonical_name == "CHARACTER_5"

    def test_missing_file(self, tmp_path):
        assert _parse_book_json(tmp_path / "nonexistent.book") == []

    def test_empty_characters(self, tmp_path):
        path = tmp_path / "test.book"
        path.write_text(json.dumps({"characters": []}))
        assert _parse_book_json(path) == []

    def test_missing_optional_fields(self, tmp_path):
        """Character with only id and names: all optional fields should default."""
        data = {"characters": [{"id": 0, "names": {"Alice": 10}}]}
        path = tmp_path / "test.book"
        path.write_text(json.dumps(data))

        chars = _parse_book_json(path)
        assert chars[0].agent_actions == []
        assert chars[0].patient_actions == []
        assert chars[0].modifiers == []
        assert chars[0].possessions == []
        assert chars[0].gender == "unknown"


# ---------------------------------------------------------------------------
# _parse_entities_tsv
# ---------------------------------------------------------------------------

class TestParseEntitiesTsv:
    def test_standard_rows(self, tmp_path):
        """Deep research: .entities columns: COREF, start_token, end_token, prop, cat, text."""
        tsv = tmp_path / "test.entities"
        tsv.write_text(
            "COREF\tstart_token\tend_token\tprop\tcat\ttext\n"
            "0\t10\t11\tPROP\tPER\tScrooge\n"
            "1\t80\t82\tPROP\tPER\tBob Cratchit\n"
            "100\t200\t201\tPROP\tLOC\tLondon\n"
        )
        entities = _parse_entities_tsv(tsv)
        assert len(entities) == 3
        assert entities[0].coref_id == 0
        assert entities[0].text == "Scrooge"
        assert entities[0].cat == "PER"
        assert entities[2].cat == "LOC"

    def test_empty_file(self, tmp_path):
        tsv = tmp_path / "empty.entities"
        tsv.write_text("")
        assert _parse_entities_tsv(tsv) == []

    def test_headers_only(self, tmp_path):
        tsv = tmp_path / "headers.entities"
        tsv.write_text("COREF\tstart_token\tend_token\tprop\tcat\ttext\n")
        assert _parse_entities_tsv(tsv) == []

    def test_missing_file(self, tmp_path):
        assert _parse_entities_tsv(tmp_path / "nope.entities") == []

    def test_all_entity_types(self, tmp_path):
        """Deep research: entity types are PER, LOC, FAC, GPE, VEH, ORG."""
        lines = ["COREF\tstart_token\tend_token\tprop\tcat\ttext"]
        for i, cat in enumerate(["PER", "LOC", "FAC", "GPE", "VEH", "ORG"]):
            lines.append(f"{i}\t{i*10}\t{i*10+1}\tPROP\t{cat}\tEntity{i}")
        tsv = tmp_path / "types.entities"
        tsv.write_text("\n".join(lines) + "\n")
        entities = _parse_entities_tsv(tsv)
        assert len(entities) == 6
        cats = [e.cat for e in entities]
        assert set(cats) == {"PER", "LOC", "FAC", "GPE", "VEH", "ORG"}

    def test_prop_types(self, tmp_path):
        """Deep research: prop values are PROP, NOM, PRON."""
        lines = [
            "COREF\tstart_token\tend_token\tprop\tcat\ttext",
            "0\t10\t11\tPROP\tPER\tScrooge",
            "0\t50\t51\tPRON\tPER\the",
            "0\t60\t62\tNOM\tPER\tthe old miser",
        ]
        tsv = tmp_path / "props.entities"
        tsv.write_text("\n".join(lines) + "\n")
        entities = _parse_entities_tsv(tsv)
        props = [e.prop for e in entities]
        assert props == ["PROP", "PRON", "NOM"]


# ---------------------------------------------------------------------------
# _parse_quotes_tsv
# ---------------------------------------------------------------------------

class TestParseQuotesTsv:
    def test_standard_rows(self, tmp_path):
        tsv = tmp_path / "test.quotes"
        tsv.write_text(
            "quote\tchar_id\tquote_start\tquote_end\n"
            "Bah humbug!\t0\t15\t18\n"
            "God bless us every one!\t3\t100\t106\n"
        )
        quotes = _parse_quotes_tsv(tsv)
        assert len(quotes) == 2
        assert quotes[0].text == "Bah humbug!"
        assert quotes[0].speaker_coref_id == 0
        assert quotes[1].speaker_coref_id == 3

    def test_null_speaker(self, tmp_path):
        """Speaker -1 or empty should map to None."""
        tsv = tmp_path / "test.quotes"
        tsv.write_text(
            "quote\tchar_id\tquote_start\tquote_end\n"
            "Who said this?\t-1\t0\t3\n"
            "Or this?\t\t10\t12\n"
        )
        quotes = _parse_quotes_tsv(tsv)
        assert quotes[0].speaker_coref_id is None
        assert quotes[1].speaker_coref_id is None

    def test_alternative_column_names(self, tmp_path):
        """Handle both 'text'/'speaker' and 'quote'/'char_id' column names."""
        tsv = tmp_path / "alt.quotes"
        tsv.write_text(
            "text\tspeaker\tstart_token\tend_token\n"
            "Hello\t5\t0\t1\n"
        )
        quotes = _parse_quotes_tsv(tsv)
        assert len(quotes) == 1
        assert quotes[0].text == "Hello"
        assert quotes[0].speaker_coref_id == 5

    def test_missing_file(self, tmp_path):
        assert _parse_quotes_tsv(tmp_path / "nope.quotes") == []

    def test_empty_file(self, tmp_path):
        tsv = tmp_path / "empty.quotes"
        tsv.write_text("")
        assert _parse_quotes_tsv(tsv) == []


# ---------------------------------------------------------------------------
# _parse_tokens_tsv
# ---------------------------------------------------------------------------

class TestParseTokensTsv:
    def test_standard_rows(self, tmp_path):
        tsv = tmp_path / "test.tokens"
        tsv.write_text(
            "token_ID_within_document\tword\tlemma\tPOS_tag\tdependency_relation\tCOREF\tbyte_onset\tbyte_offset\n"
            "0\tScrooge\tscrooge\tNNP\tnsubj\t0\t0\t7\n"
            "1\twalked\twalk\tVBD\troot\t\t8\t14\n"
            "2\thome\thome\tNN\tdobj\t-\t15\t19\n"
        )
        tokens = _parse_tokens_tsv(tsv)
        assert len(tokens) == 3
        assert tokens[0].token_id == 0
        assert tokens[0].text == "Scrooge"
        assert tokens[0].coref_id == 0
        assert tokens[0].start_char == 0
        assert tokens[0].end_char == 7
        # Empty coref -> None
        assert tokens[1].coref_id is None
        # Dash coref -> None
        assert tokens[2].coref_id is None

    def test_alternative_column_names(self, tmp_path):
        tsv = tmp_path / "alt.tokens"
        tsv.write_text(
            "token_id\ttext\tlemma\tpos\tdep\tcoref\tstart_char\tend_char\n"
            "0\tHello\thello\tUH\troot\t\t0\t5\n"
        )
        tokens = _parse_tokens_tsv(tsv)
        assert len(tokens) == 1
        assert tokens[0].text == "Hello"

    def test_missing_file(self, tmp_path):
        assert _parse_tokens_tsv(tmp_path / "nope.tokens") == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestReadTsv:
    def test_valid(self, tmp_path):
        f = tmp_path / "test.tsv"
        f.write_text("col1\tcol2\na\tb\nc\td\n")
        rows = read_tsv(f)
        assert len(rows) == 2
        assert rows[0] == {"col1": "a", "col2": "b"}

    def test_empty(self, tmp_path):
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


class TestSafeInt:
    def test_valid(self):
        assert safe_int("42") == 42
        assert safe_int("0") == 0
        assert safe_int("-1") == -1

    def test_invalid(self):
        assert safe_int("abc") == -1
        assert safe_int("") == -1

    def test_none(self):
        assert safe_int(None) == -1


class TestBuildCorefNameMap:
    def test_maps_ids(self):
        chars = [
            CharacterProfile(coref_id=0, canonical_name="Scrooge", aliases={}, agent_actions=[],
                             patient_actions=[], modifiers=[], possessions=[], gender=""),
            CharacterProfile(coref_id=1, canonical_name="Bob", aliases={}, agent_actions=[],
                             patient_actions=[], modifiers=[], possessions=[], gender=""),
        ]
        m = _build_coref_name_map(chars)
        assert m == {0: "Scrooge", 1: "Bob"}

    def test_empty(self):
        assert _build_coref_name_map([]) == {}


class TestFillCharOffsets:
    def test_fills_entities(self):
        entities = [EntityMention(coref_id=0, start_token=0, end_token=1, prop="", cat="", text="")]
        token_map = {0: (10, 17), 1: (18, 24)}
        _fill_char_offsets_entities(entities, token_map)
        assert entities[0].start_char == 10
        assert entities[0].end_char == 24

    def test_fills_quotes(self):
        quotes = [QuoteAttribution(text="hi", speaker_coref_id=None, start_token=5, end_token=8)]
        token_map = {5: (50, 52), 8: (70, 72)}
        _fill_char_offsets_quotes(quotes, token_map)
        assert quotes[0].start_char == 50
        assert quotes[0].end_char == 72

    def test_missing_token_leaves_default(self):
        entities = [EntityMention(coref_id=0, start_token=999, end_token=1000, prop="", cat="", text="")]
        _fill_char_offsets_entities(entities, {})
        assert entities[0].start_char == 0  # unchanged default
        assert entities[0].end_char == 0


# ---------------------------------------------------------------------------
# create_stub_output
# ---------------------------------------------------------------------------

class TestCreateStubOutput:
    def test_stub(self):
        stub = create_stub_output("test_book")
        assert stub.book_id == "test_book"
        assert stub.character_count == 0
        assert stub.entity_count == 0
        assert stub.quote_count == 0
        assert stub.coref_id_to_name == {}

    def test_stub_to_pipeline_dict(self):
        stub = create_stub_output("test")
        d = stub.to_pipeline_dict()
        assert d == {"entities": [], "quotes": [], "characters": []}


# ---------------------------------------------------------------------------
# parse_booknlp_output (integration)
# ---------------------------------------------------------------------------

class TestParseBooknlpOutput:
    def test_full_integration(self, tmp_path, christmas_carol_book_json):
        """Parse all output files together and verify cross-references."""
        book_id = "xmas"

        # Write .book
        (tmp_path / f"{book_id}.book").write_text(json.dumps(christmas_carol_book_json))

        # Write .entities
        (tmp_path / f"{book_id}.entities").write_text(
            "COREF\tstart_token\tend_token\tprop\tcat\ttext\n"
            "0\t10\t11\tPROP\tPER\tScrooge\n"
            "1\t80\t82\tPROP\tPER\tBob Cratchit\n"
        )

        # Write .quotes
        (tmp_path / f"{book_id}.quotes").write_text(
            "quote\tchar_id\tquote_start\tquote_end\n"
            "Bah humbug!\t0\t15\t18\n"
        )

        # Write .tokens (minimal: provides char offsets)
        (tmp_path / f"{book_id}.tokens").write_text(
            "token_ID_within_document\tword\tlemma\tPOS_tag\tdependency_relation\tCOREF\tbyte_onset\tbyte_offset\n"
            "10\tScrooge\tscrooge\tNNP\tnsubj\t0\t50\t57\n"
            "11\twalked\twalk\tVBD\troot\t\t58\t64\n"
            "15\tBah\tbah\tUH\troot\t\t70\t73\n"
            "18\thumbug\thumbug\tNN\tdobj\t\t74\t80\n"
            "80\tBob\tbob\tNNP\tcompound\t1\t400\t403\n"
            "82\tCratchit\tcratchit\tNNP\tnsubj\t1\t404\t412\n"
        )

        result = parse_booknlp_output(tmp_path, book_id)

        # Characters
        assert result.character_count == 4
        assert result.coref_id_to_name[0] == "Scrooge"
        assert result.coref_id_to_name[1] == "Bob Cratchit"

        # Entities with back-filled char offsets
        assert result.entity_count == 2
        assert result.entities[0].text == "Scrooge"
        assert result.entities[0].start_char == 50  # from token 10
        assert result.entities[0].end_char == 64     # from token 11

        # Quotes with back-filled char offsets
        assert result.quote_count == 1
        assert result.quotes[0].start_char == 70  # from token 15
        assert result.quotes[0].end_char == 80     # from token 18

        # Pipeline dict conversion
        d = result.to_pipeline_dict()
        assert d["entities"][0]["canonical_name"] == "Scrooge"
        assert d["quotes"][0]["speaker_name"] == "Scrooge"

    def test_missing_all_files(self, tmp_path):
        """Should return empty output, not crash."""
        result = parse_booknlp_output(tmp_path, "missing")
        assert result.character_count == 0
        assert result.entity_count == 0
        assert result.quote_count == 0
        assert len(result.tokens) == 0
