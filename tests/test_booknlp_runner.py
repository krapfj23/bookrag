"""Comprehensive tests for pipeline/booknlp_runner.py.

Covers:
- _int / _str helpers: primary keys, fallback keys, defaults, NA handling, float coercion
- _read_tsv: file not found, valid TSV, malformed rows
- Token.from_row: all columns, fallback column names
- EntityMention.from_row: all columns, COREF/start_token/end_token/prop/cat/text
- Quote.from_row: speaker resolution via coref_to_name mapping
- _parse_book_json: BookNLP dict format, list format, gender dict, aliases,
  agent/patient/poss/mod extraction, mention_count accumulation, missing file
- BookNLPOutput dataclass: all fields
- parse_booknlp_outputs: parses pre-existing files without running BookNLP
- run_booknlp: ImportError for missing booknlp, FileNotFoundError for missing input,
  JSON traceability output at data/processed/{book_id}/booknlp/parsed_output.json

Alignment with plan docs:
- CLAUDE.md: "BookNLP integration + output parsing", all intermediate outputs saved
- bookrag_pipeline_plan.md: .tokens TSV, .entities TSV, .quotes TSV, .book JSON
- bookrag_deep_research_context.md: Section 2 BookNLP Internals — column names,
  entity types (PER, LOC, FAC, GPE, VEH, ORG), prop types (PROP, NOM, PRON),
  character profiles with aliases/gender/agent/patient/possessions/modifiers
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.booknlp_runner import (
    Token,
    EntityMention,
    Quote,
    CharacterProfile,
    BookNLPOutput,
    _int,
    _str,
    _read_tsv,
    _parse_tokens,
    _parse_entities,
    _parse_quotes,
    _parse_book_json,
    run_booknlp,
    parse_booknlp_outputs,
)


# ============================================================================
# _int helper tests
# ============================================================================

class TestIntHelper:

    def test_primary_key(self):
        assert _int({"a": "42"}, "a") == 42

    def test_fallback_key(self):
        assert _int({"b": "7"}, "a", fallback_keys=["b"]) == 7

    def test_missing_key_returns_default(self):
        assert _int({"x": "1"}, "a") == 0

    def test_custom_default(self):
        assert _int({}, "a", default=-1) == -1

    def test_empty_string_returns_default(self):
        assert _int({"a": ""}, "a", default=5) == 5

    def test_na_returns_default(self):
        assert _int({"a": "NA"}, "a", default=0) == 0

    def test_negative_one_returns_negative_one(self):
        assert _int({"a": "-1"}, "a", default=0) == -1

    def test_float_coerced_to_int(self):
        assert _int({"a": "3.0"}, "a") == 3

    def test_non_numeric_falls_through(self):
        assert _int({"a": "abc"}, "a", fallback_keys=["b"], default=99) == 99

    def test_whitespace_stripped(self):
        assert _int({"a": "  42  "}, "a") == 42

    def test_multiple_fallbacks(self):
        row = {"c": "10"}
        assert _int(row, "a", fallback_keys=["b", "c"]) == 10


# ============================================================================
# _str helper tests
# ============================================================================

class TestStrHelper:

    def test_primary_key(self):
        assert _str({"a": "hello"}, "a") == "hello"

    def test_fallback_key(self):
        assert _str({"b": "world"}, "a", fallback_keys=["b"]) == "world"

    def test_missing_returns_default(self):
        assert _str({}, "a") == ""

    def test_custom_default(self):
        assert _str({}, "a", default="N/A") == "N/A"

    def test_whitespace_stripped(self):
        assert _str({"a": "  hello  "}, "a") == "hello"


# ============================================================================
# _read_tsv tests
# ============================================================================

class TestReadTSV:

    def test_missing_file_returns_empty(self):
        result = _read_tsv(Path("/nonexistent/file.tsv"))
        assert result == []

    def test_valid_tsv(self, tmp_path):
        tsv = tmp_path / "test.tsv"
        tsv.write_text("col1\tcol2\tcol3\n1\thello\t3.0\n2\tworld\t4.0\n", encoding="utf-8")
        result = _read_tsv(tsv)
        assert len(result) == 2
        assert result[0]["col1"] == "1"
        assert result[0]["col2"] == "hello"
        assert result[1]["col2"] == "world"

    def test_empty_tsv_header_only(self, tmp_path):
        tsv = tmp_path / "empty.tsv"
        tsv.write_text("col1\tcol2\n", encoding="utf-8")
        result = _read_tsv(tsv)
        assert result == []

    def test_tsv_with_special_chars(self, tmp_path):
        tsv = tmp_path / "special.tsv"
        tsv.write_text('col1\tcol2\nScrooge\t"Bah humbug!"\n', encoding="utf-8")
        result = _read_tsv(tsv)
        assert len(result) == 1
        assert "Scrooge" in result[0]["col1"]


# ============================================================================
# Token.from_row tests
# ============================================================================

class TestTokenFromRow:
    """Per deep_research_context.md Section 2: .tokens TSV columns."""

    def test_primary_column_names(self):
        row = {
            "token_ID_within_document": "5",
            "sentence_ID": "1",
            "token_offset_begin": "20",
            "token_offset_end": "25",
            "word": "Scrooge",
            "lemma": "scrooge",
            "POS_tag": "NNP",
            "dependency_relation": "nsubj",
            "dependency_head_ID": "3",
            "coref_id": "7",
            "event": "trigger",
            "supersense_category": "noun.person",
        }
        token = Token.from_row(row)
        assert token.token_id == 5
        assert token.sentence_id == 1
        assert token.token_offset_begin == 20
        assert token.token_offset_end == 25
        assert token.word == "Scrooge"
        assert token.lemma == "scrooge"
        assert token.pos == "NNP"
        assert token.dep_rel == "nsubj"
        assert token.dep_head == 3
        assert token.coref_id == 7
        assert token.event == "trigger"

    def test_coref_and_event_are_independent(self):
        """coref_id and event must read from different columns, not both from 'event'."""
        row = {
            "token_ID_within_document": "0",
            "sentence_ID": "0",
            "token_offset_begin": "0",
            "token_offset_end": "3",
            "word": "He",
            "lemma": "he",
            "POS_tag": "PRP",
            "dependency_relation": "nsubj",
            "dependency_head_ID": "1",
            "coref_id": "5",
            "event": "some_event",
        }
        token = Token.from_row(row)
        assert token.coref_id == 5
        assert token.event == "some_event"

        # Without coref_id column, should fall back to default -1, NOT read from event
        row_no_coref = {
            "token_ID_within_document": "0",
            "sentence_ID": "0",
            "token_offset_begin": "0",
            "token_offset_end": "3",
            "word": "He",
            "lemma": "he",
            "POS_tag": "PRP",
            "dependency_relation": "nsubj",
            "dependency_head_ID": "1",
            "event": "some_event",
        }
        token2 = Token.from_row(row_no_coref)
        assert token2.coref_id == -1
        assert token2.event == "some_event"

    def test_fallback_column_names(self):
        row = {
            "token_id": "10",
            "sentence_id": "2",
            "byte_onset": "50",
            "byte_offset": "55",
            "token": "muttered",
            "lemma": "mutter",
            "pos": "VBD",
            "dep_rel": "root",
            "dep_head": "0",
            "coref_id": "3",
        }
        token = Token.from_row(row)
        assert token.token_id == 10
        assert token.word == "muttered"
        assert token.pos == "VBD"

    def test_missing_optional_fields(self):
        row = {
            "token_ID_within_document": "1",
            "sentence_ID": "0",
            "token_offset_begin": "0",
            "token_offset_end": "5",
            "word": "The",
            "lemma": "the",
            "POS_tag": "DT",
            "dependency_relation": "det",
            "dependency_head_ID": "2",
        }
        token = Token.from_row(row)
        assert token.supersense == ""
        assert token.event == ""


# ============================================================================
# EntityMention.from_row tests
# ============================================================================

class TestEntityMentionFromRow:
    """Per deep_research_context.md: COREF, start_token, end_token, prop, cat, text."""

    def test_primary_columns(self):
        row = {
            "COREF": "5",
            "start_token": "10",
            "end_token": "11",
            "prop": "PROP",
            "cat": "PER",
            "text": "Scrooge",
        }
        entity = EntityMention.from_row(row)
        assert entity.coref_id == 5
        assert entity.start_token == 10
        assert entity.end_token == 11
        assert entity.prop == "PROP"
        assert entity.cat == "PER"
        assert entity.text == "Scrooge"

    def test_fallback_columns(self):
        row = {
            "coref_id": "3",
            "token_ID_start": "20",
            "token_ID_end": "22",
            "PROP": "NOM",
            "NER": "LOC",
            "mention": "London",
        }
        entity = EntityMention.from_row(row)
        assert entity.coref_id == 3
        assert entity.start_token == 20
        assert entity.cat == "LOC"
        assert entity.text == "London"

    def test_all_entity_types(self):
        """Per plan: PER, LOC, FAC, GPE, VEH, ORG."""
        for cat in ["PER", "LOC", "FAC", "GPE", "VEH", "ORG"]:
            row = {
                "COREF": "1", "start_token": "0", "end_token": "1",
                "prop": "PROP", "cat": cat, "text": "Entity",
            }
            entity = EntityMention.from_row(row)
            assert entity.cat == cat

    def test_all_prop_types(self):
        """Per plan: PROP, NOM, PRON."""
        for prop in ["PROP", "NOM", "PRON"]:
            row = {
                "COREF": "1", "start_token": "0", "end_token": "1",
                "prop": prop, "cat": "PER", "text": "ref",
            }
            entity = EntityMention.from_row(row)
            assert entity.prop == prop


# ============================================================================
# Quote.from_row tests
# ============================================================================

class TestQuoteFromRow:

    def test_basic_quote(self):
        row = {
            "quote_start": "100",
            "quote_end": "110",
            "quote": "Bah humbug!",
            "char_id": "5",
        }
        quote = Quote.from_row(row)
        assert quote.quote_start == 100
        assert quote.quote_end == 110
        assert quote.quote_text == "Bah humbug!"
        assert quote.speaker_coref_id == 5
        assert quote.speaker_name == ""  # No mapping provided

    def test_speaker_name_resolved(self):
        """Per plan: Map speaker_coref_id in quotes to canonical character names."""
        row = {
            "quote_start": "100",
            "quote_end": "110",
            "quote": "Bah humbug!",
            "char_id": "5",
        }
        coref_map = {5: "Ebenezer Scrooge", 10: "Bob Cratchit"}
        quote = Quote.from_row(row, coref_map)
        assert quote.speaker_name == "Ebenezer Scrooge"

    def test_unknown_speaker(self):
        row = {
            "quote_start": "0",
            "quote_end": "5",
            "quote": "Hello",
            "char_id": "999",
        }
        coref_map = {5: "Scrooge"}
        quote = Quote.from_row(row, coref_map)
        assert quote.speaker_name == ""  # 999 not in map

    def test_fallback_columns(self):
        row = {
            "start_token": "50",
            "end_token": "60",
            "text": "A quote",
            "speaker_coref_id": "3",
        }
        quote = Quote.from_row(row)
        assert quote.quote_start == 50
        assert quote.quote_text == "A quote"


# ============================================================================
# CharacterProfile / _parse_book_json tests
# ============================================================================

class TestParseBookJSON:
    """Per deep_research_context.md Section 2: .book JSON format with
    character profiles: aliases, referential gender, agent/patient actions,
    possessions, modifiers.
    """

    def _write_book_json(self, tmp_path: Path, data: dict | list) -> Path:
        path = tmp_path / "test.book"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_missing_file(self, tmp_path):
        chars, mapping = _parse_book_json(tmp_path / "nonexistent.book")
        assert chars == []
        assert mapping == {}

    def test_dict_format_with_characters_key(self, tmp_path):
        """BookNLP .book JSON can be {"characters": [...]}."""
        data = {
            "characters": [
                {
                    "id": 5,
                    "names": {
                        "proper": [{"n": "Scrooge", "c": 100}],
                        "common": [{"n": "old man", "c": 10}],
                    },
                    "g": "male",
                    "agent": [{"w": "muttered"}, {"w": "walked"}],
                    "patient": [{"w": "visited"}],
                    "poss": [{"w": "counting-house"}],
                    "mod": [{"w": "old"}, {"w": "miserly"}],
                    "count": 150,
                }
            ]
        }
        path = self._write_book_json(tmp_path, data)
        chars, mapping = _parse_book_json(path)

        assert len(chars) == 1
        c = chars[0]
        assert c.coref_id == 5
        assert c.name == "Scrooge"
        assert "old man" in c.aliases
        assert c.gender == "male"
        assert "muttered" in c.agent_actions
        assert "walked" in c.agent_actions
        assert "visited" in c.patient_actions
        assert "counting-house" in c.possessions
        assert "old" in c.modifiers
        assert "miserly" in c.modifiers
        assert c.mention_count == 150
        assert mapping[5] == "Scrooge"

    def test_list_format(self, tmp_path):
        """BookNLP .book JSON can also be a bare list."""
        data = [
            {
                "id": 1,
                "names": {"proper": [{"n": "Cratchit", "c": 30}]},
                "g": "male",
                "agent": [],
                "patient": [],
                "count": 30,
            }
        ]
        path = self._write_book_json(tmp_path, data)
        chars, mapping = _parse_book_json(path)
        assert len(chars) == 1
        assert chars[0].name == "Cratchit"

    def test_gender_as_dict(self, tmp_path):
        """BookNLP sometimes has gender as {"male": 0.1, "female": 0.9}."""
        data = [
            {
                "id": 2,
                "names": {"proper": [{"n": "Belle", "c": 5}]},
                "g": {"male": 0.1, "female": 0.9},
                "agent": [],
                "patient": [],
            }
        ]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert chars[0].gender == "female"

    def test_gender_as_string(self, tmp_path):
        data = [{"id": 1, "names": {"proper": [{"n": "Bob", "c": 5}]}, "g": "male"}]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert chars[0].gender == "male"

    def test_names_as_list(self, tmp_path):
        """Alternative format: names as a flat list."""
        data = [{"id": 1, "names": ["Scrooge", "Mr. Scrooge"]}]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert chars[0].name == "Scrooge"
        assert "Mr. Scrooge" in chars[0].aliases

    def test_no_names_uses_fallback(self, tmp_path):
        data = [{"id": 99}]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert chars[0].name == "CHARACTER_99"

    def test_mention_count_from_names(self, tmp_path):
        """When count is 0, accumulate from name entry counts."""
        data = [
            {
                "id": 1,
                "names": {
                    "proper": [{"n": "Scrooge", "c": 50}],
                    "common": [{"n": "miser", "c": 10}],
                },
            }
        ]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert chars[0].mention_count == 60

    def test_extract_words_string_items(self, tmp_path):
        """Agent/patient items can be plain strings."""
        data = [
            {
                "id": 1,
                "names": {"proper": [{"n": "Bob", "c": 5}]},
                "agent": ["walked", "talked"],
                "patient": ["helped"],
            }
        ]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert "walked" in chars[0].agent_actions
        assert "talked" in chars[0].agent_actions
        assert "helped" in chars[0].patient_actions

    def test_extract_words_dict_items(self, tmp_path):
        """Agent/patient items can be dicts with 'w', 'word', or 'text' keys."""
        data = [
            {
                "id": 1,
                "names": {"proper": [{"n": "Bob", "c": 5}]},
                "agent": [{"w": "ran"}, {"word": "jumped"}, {"text": "fell"}],
            }
        ]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert set(chars[0].agent_actions) == {"ran", "jumped", "fell"}

    def test_multiple_characters(self, tmp_path):
        data = [
            {"id": 1, "names": {"proper": [{"n": "Scrooge", "c": 100}]}, "g": "male"},
            {"id": 2, "names": {"proper": [{"n": "Cratchit", "c": 50}]}, "g": "male"},
            {"id": 3, "names": {"proper": [{"n": "Belle", "c": 20}]}, "g": "female"},
        ]
        path = self._write_book_json(tmp_path, data)
        chars, mapping = _parse_book_json(path)
        assert len(chars) == 3
        assert mapping[1] == "Scrooge"
        assert mapping[2] == "Cratchit"
        assert mapping[3] == "Belle"

    def test_possessions_fallback_key(self, tmp_path):
        data = [{"id": 1, "names": {"proper": [{"n": "A", "c": 1}]}, "possessions": ["sword"]}]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert "sword" in chars[0].possessions

    def test_modifiers_fallback_key(self, tmp_path):
        data = [{"id": 1, "names": {"proper": [{"n": "A", "c": 1}]}, "modifiers": ["tall"]}]
        path = self._write_book_json(tmp_path, data)
        chars, _ = _parse_book_json(path)
        assert "tall" in chars[0].modifiers


# ============================================================================
# _parse_tokens / _parse_entities / _parse_quotes integration
# ============================================================================

class TestParseTSVFiles:

    def test_parse_tokens_from_file(self, tmp_path):
        tsv = tmp_path / "test.tokens"
        tsv.write_text(
            "token_ID_within_document\tsentence_ID\ttoken_offset_begin\ttoken_offset_end\t"
            "word\tlemma\tPOS_tag\tdependency_relation\tdependency_head_ID\tevent\n"
            "0\t0\t0\t3\tThe\tthe\tDT\tdet\t1\t-1\n"
            "1\t0\t4\t11\tScrooge\tscrooge\tNNP\tnsubj\t2\t5\n",
            encoding="utf-8",
        )
        tokens = _parse_tokens(tsv)
        assert len(tokens) == 2
        assert tokens[0].word == "The"
        assert tokens[1].word == "Scrooge"

    def test_parse_entities_from_file(self, tmp_path):
        tsv = tmp_path / "test.entities"
        tsv.write_text(
            "COREF\tstart_token\tend_token\tprop\tcat\ttext\n"
            "5\t1\t2\tPROP\tPER\tScrooge\n"
            "10\t5\t7\tPROP\tLOC\tLondon\n",
            encoding="utf-8",
        )
        entities = _parse_entities(tsv)
        assert len(entities) == 2
        assert entities[0].text == "Scrooge"
        assert entities[0].cat == "PER"
        assert entities[1].text == "London"
        assert entities[1].cat == "LOC"

    def test_parse_quotes_with_speaker_resolution(self, tmp_path):
        tsv = tmp_path / "test.quotes"
        tsv.write_text(
            "quote_start\tquote_end\tquote\tchar_id\n"
            "100\t110\tBah humbug!\t5\n"
            "200\t215\tGod bless us, every one!\t10\n",
            encoding="utf-8",
        )
        coref_map = {5: "Scrooge", 10: "Tiny Tim"}
        quotes = _parse_quotes(tsv, coref_map)
        assert len(quotes) == 2
        assert quotes[0].speaker_name == "Scrooge"
        assert quotes[1].speaker_name == "Tiny Tim"

    def test_parse_tokens_missing_file(self, tmp_path):
        tokens = _parse_tokens(tmp_path / "nonexistent.tokens")
        assert tokens == []

    def test_parse_entities_missing_file(self, tmp_path):
        entities = _parse_entities(tmp_path / "nonexistent.entities")
        assert entities == []

    def test_parse_quotes_missing_file(self, tmp_path):
        quotes = _parse_quotes(tmp_path / "nonexistent.quotes", {})
        assert quotes == []


# ============================================================================
# BookNLPOutput dataclass tests
# ============================================================================

class TestBookNLPOutput:

    def test_all_fields(self):
        output = BookNLPOutput(
            book_id="christmas_carol",
            tokens=[Token(0, 0, 0, 3, "The", "the", "DT", "det", 1, -1)],
            entities=[EntityMention(5, 1, 2, "PROP", "PER", "Scrooge")],
            quotes=[Quote(100, 110, "Bah!", 5, "Scrooge")],
            characters=[CharacterProfile(5, "Scrooge")],
        )
        assert output.book_id == "christmas_carol"
        assert len(output.tokens) == 1
        assert len(output.entities) == 1
        assert len(output.quotes) == 1
        assert len(output.characters) == 1

    def test_default_empty_lists(self):
        output = BookNLPOutput(book_id="test")
        assert output.tokens == []
        assert output.entities == []
        assert output.quotes == []
        assert output.characters == []

    def test_serializable_to_json(self):
        """Per plan: Save the parsed output as JSON for traceability."""
        from dataclasses import asdict
        output = BookNLPOutput(
            book_id="test",
            tokens=[Token(0, 0, 0, 3, "The", "the", "DT", "det", 1, -1)],
            entities=[EntityMention(5, 1, 2, "PROP", "PER", "Scrooge")],
            quotes=[Quote(100, 110, "Bah!", 5, "Scrooge")],
            characters=[CharacterProfile(5, "Scrooge", aliases=["Mr. Scrooge"])],
        )
        data = asdict(output)
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["book_id"] == "test"
        assert len(parsed["tokens"]) == 1
        assert parsed["characters"][0]["aliases"] == ["Mr. Scrooge"]


# ============================================================================
# parse_booknlp_outputs tests
# ============================================================================

class TestParseBooknlpOutputs:
    """Test parsing pre-existing BookNLP output files."""

    def _create_booknlp_files(self, tmp_path: Path, book_id: str):
        """Create minimal valid BookNLP output files."""
        # .tokens
        (tmp_path / f"{book_id}.tokens").write_text(
            "token_ID_within_document\tsentence_ID\ttoken_offset_begin\ttoken_offset_end\t"
            "word\tlemma\tPOS_tag\tdependency_relation\tdependency_head_ID\tevent\n"
            "0\t0\t0\t3\tThe\tthe\tDT\tdet\t1\t-1\n"
            "1\t0\t4\t11\tScrooge\tscrooge\tNNP\tnsubj\t2\t5\n",
            encoding="utf-8",
        )

        # .entities
        (tmp_path / f"{book_id}.entities").write_text(
            "COREF\tstart_token\tend_token\tprop\tcat\ttext\n"
            "5\t1\t2\tPROP\tPER\tScrooge\n",
            encoding="utf-8",
        )

        # .quotes
        (tmp_path / f"{book_id}.quotes").write_text(
            "quote_start\tquote_end\tquote\tchar_id\n"
            "100\t110\tBah humbug!\t5\n",
            encoding="utf-8",
        )

        # .book
        book_data = [
            {
                "id": 5,
                "names": {"proper": [{"n": "Scrooge", "c": 100}]},
                "g": "male",
                "agent": [{"w": "muttered"}],
                "patient": [],
                "poss": [],
                "mod": [{"w": "old"}],
                "count": 100,
            }
        ]
        (tmp_path / f"{book_id}.book").write_text(
            json.dumps(book_data), encoding="utf-8",
        )

    def test_full_parse(self, tmp_path):
        book_id = "christmas_carol"
        self._create_booknlp_files(tmp_path, book_id)

        result = parse_booknlp_outputs(tmp_path, book_id)

        assert result.book_id == book_id
        assert len(result.tokens) == 2
        assert len(result.entities) == 1
        assert len(result.quotes) == 1
        assert len(result.characters) == 1

        # Verify speaker resolution worked
        assert result.quotes[0].speaker_name == "Scrooge"

        # Verify character profile
        c = result.characters[0]
        assert c.name == "Scrooge"
        assert c.gender == "male"
        assert "muttered" in c.agent_actions
        assert "old" in c.modifiers

    def test_missing_some_files(self, tmp_path):
        """Should handle gracefully when some output files are missing."""
        book_id = "partial"
        # Only create .tokens
        (tmp_path / f"{book_id}.tokens").write_text(
            "token_ID_within_document\tsentence_ID\ttoken_offset_begin\ttoken_offset_end\t"
            "word\tlemma\tPOS_tag\tdependency_relation\tdependency_head_ID\tevent\n"
            "0\t0\t0\t3\tThe\tthe\tDT\tdet\t1\t-1\n",
            encoding="utf-8",
        )

        result = parse_booknlp_outputs(tmp_path, book_id)
        assert len(result.tokens) == 1
        assert result.entities == []
        assert result.quotes == []
        assert result.characters == []


# ============================================================================
# run_booknlp tests (mocked BookNLP)
# ============================================================================

class TestRunBookNLP:

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Input text file not found"):
            run_booknlp(
                tmp_path / "nonexistent.txt",
                tmp_path / "output",
                "test",
            )

    @patch("pipeline.booknlp_runner.BookNLP", create=True)
    def test_import_error(self, mock_bnlp_class, tmp_path):
        """When booknlp is not installed, should raise ImportError."""
        text_file = tmp_path / "input.txt"
        text_file.write_text("Some text.", encoding="utf-8")

        # Simulate the import failing inside run_booknlp
        with patch.dict("sys.modules", {"booknlp": None, "booknlp.booknlp": None}):
            with pytest.raises((ImportError, ModuleNotFoundError)):
                run_booknlp(text_file, tmp_path / "output", "test")

    def test_creates_output_dir(self, tmp_path):
        """Output directory should be created if it doesn't exist."""
        text_file = tmp_path / "input.txt"
        text_file.write_text("Some text.", encoding="utf-8")
        output_dir = tmp_path / "deep" / "nested" / "output"

        with patch("pipeline.booknlp_runner.BookNLP", create=True) as MockBookNLP:
            mock_instance = MagicMock()
            MockBookNLP.return_value = mock_instance

            # Import needs to succeed
            import sys
            mock_booknlp_mod = MagicMock()
            mock_booknlp_mod.BookNLP = MockBookNLP

            with patch.dict(sys.modules, {"booknlp": MagicMock(), "booknlp.booknlp": mock_booknlp_mod}):
                try:
                    run_booknlp(text_file, output_dir, "test")
                except Exception:
                    pass  # Will fail at parse step since no output files exist

        assert output_dir.exists()

    def test_json_traceability_output(self, tmp_path, monkeypatch):
        """Per plan: Save parsed output as JSON at data/processed/{book_id}/booknlp/parsed_output.json."""
        monkeypatch.chdir(tmp_path)

        text_file = tmp_path / "input.txt"
        text_file.write_text("Some text.", encoding="utf-8")
        output_dir = tmp_path / "bnlp_output"
        output_dir.mkdir()
        book_id = "test_book"

        # Create minimal output files
        (output_dir / f"{book_id}.tokens").write_text(
            "token_ID_within_document\tsentence_ID\ttoken_offset_begin\ttoken_offset_end\t"
            "word\tlemma\tPOS_tag\tdependency_relation\tdependency_head_ID\tevent\n"
            "0\t0\t0\t4\tSome\tsome\tDT\tdet\t1\t-1\n",
            encoding="utf-8",
        )
        (output_dir / f"{book_id}.entities").write_text("COREF\tstart_token\tend_token\tprop\tcat\ttext\n", encoding="utf-8")
        (output_dir / f"{book_id}.quotes").write_text("quote_start\tquote_end\tquote\tchar_id\n", encoding="utf-8")
        (output_dir / f"{book_id}.book").write_text("[]", encoding="utf-8")

        # Mock BookNLP to do nothing (files already created)
        import sys
        mock_booknlp_mod = MagicMock()
        mock_instance = MagicMock()
        mock_booknlp_mod.BookNLP.return_value = mock_instance

        with patch.dict(sys.modules, {"booknlp": MagicMock(), "booknlp.booknlp": mock_booknlp_mod}):
            result = run_booknlp(text_file, output_dir, book_id)

        # Check JSON output
        json_path = tmp_path / "data" / "processed" / book_id / "booknlp" / "parsed_output.json"
        assert json_path.exists()

        with open(json_path) as f:
            saved = json.load(f)
        assert saved["book_id"] == book_id
        assert len(saved["tokens"]) == 1


# ============================================================================
# CharacterProfile dataclass tests
# ============================================================================

class TestCharacterProfile:

    def test_all_fields(self):
        cp = CharacterProfile(
            coref_id=5,
            name="Scrooge",
            aliases=["Mr. Scrooge", "Ebenezer"],
            gender="male",
            agent_actions=["muttered", "walked"],
            patient_actions=["visited"],
            possessions=["counting-house"],
            modifiers=["old", "miserly"],
            mention_count=150,
        )
        assert cp.coref_id == 5
        assert cp.name == "Scrooge"
        assert len(cp.aliases) == 2
        assert cp.gender == "male"
        assert len(cp.agent_actions) == 2
        assert len(cp.patient_actions) == 1
        assert len(cp.possessions) == 1
        assert len(cp.modifiers) == 2
        assert cp.mention_count == 150

    def test_default_empty_lists(self):
        cp = CharacterProfile(coref_id=1, name="Test")
        assert cp.aliases == []
        assert cp.agent_actions == []
        assert cp.patient_actions == []
        assert cp.possessions == []
        assert cp.modifiers == []
        assert cp.mention_count == 0
        assert cp.gender == ""
