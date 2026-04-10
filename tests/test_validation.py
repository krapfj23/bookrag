"""
Comprehensive tests for validation/test_suite.py

Covers:
- CheckResult and ValidationReport data structures
- Fixture loading (exists, missing, invalid)
- Structural checks: min counts, chapter coverage, graph populated
- Character existence checks with aliases
- Location existence checks with aliases
- Relationship checks with fuzzy matching
- Event checks with chapter + keyword matching
- Known-answer query checks against cognee search
- Full run_validation integration (fixture + extracted DataPoints)
- Report serialization and saving
- No-fixture graceful skip
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from validation.test_suite import (
    CheckResult,
    ValidationReport,
    _check_expected_characters,
    _check_expected_events,
    _check_expected_locations,
    _check_expected_relationships,
    _check_known_answer_queries,
    _check_structural,
    _extract_by_type,
    _extract_search_text,
    _load_extracted_datapoints,
    load_fixture,
    run_validation,
    save_validation_report,
)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def sample_characters() -> list[dict]:
    return [
        {"name": "Scrooge", "aliases": ["Ebenezer", "Mr. Scrooge"], "first_chapter": 1, "chapters_present": [1, 2, 3, 4, 5]},
        {"name": "Bob Cratchit", "aliases": ["Bob"], "first_chapter": 1},
        {"name": "Jacob Marley", "aliases": ["Marley"], "first_chapter": 1},
        {"name": "Tiny Tim", "aliases": ["Tim"], "first_chapter": 3},
        {"name": "Fred", "aliases": [], "first_chapter": 1},
    ]


@pytest.fixture
def sample_locations() -> list[dict]:
    return [
        {"name": "London", "first_chapter": 1},
        {"name": "Scrooge's counting-house", "first_chapter": 1},
    ]


@pytest.fixture
def sample_relationships() -> list[dict]:
    return [
        {"source": "Scrooge", "target": "Bob Cratchit", "relation_type": "employs", "description": "Scrooge employs Bob as clerk"},
        {"source": "Scrooge", "target": "Jacob Marley", "relation_type": "business_partner", "description": "former business partners"},
        {"source": "Fred", "target": "Scrooge", "relation_type": "nephew_of", "description": "Fred is Scrooge's nephew"},
        {"source": "Bob Cratchit", "target": "Tiny Tim", "relation_type": "father_of", "description": "Bob is Tiny Tim's father"},
    ]


@pytest.fixture
def sample_events() -> list[dict]:
    return [
        {"description": "Marley's ghost appears to Scrooge", "chapter": 1, "participants": []},
        {"description": "Scrooge wakes transformed on Christmas morning", "chapter": 5, "participants": []},
        {"description": "Ghost of Christmas Past shows Scrooge his youth", "chapter": 2, "participants": []},
    ]


@pytest.fixture
def sample_datapoints(sample_characters, sample_locations, sample_relationships, sample_events) -> list[dict]:
    """Combined DataPoints list."""
    return sample_characters + sample_locations + sample_relationships + sample_events


@pytest.fixture
def fixture_dir(tmp_path) -> Path:
    d = tmp_path / "fixtures"
    d.mkdir()
    return d


@pytest.fixture
def christmas_carol_fixture(fixture_dir) -> Path:
    """Create a minimal Christmas Carol fixture file."""
    fixture = {
        "expected_characters": [
            {"name": "Scrooge", "aliases": ["Ebenezer"], "should_exist": True},
            {"name": "Bob Cratchit", "aliases": ["Bob"], "should_exist": True},
        ],
        "expected_locations": [
            {"name": "London", "should_exist": True},
        ],
        "expected_relationships": [
            {"source": "Scrooge", "target": "Bob Cratchit", "relation_contains": ["employ", "clerk"]},
        ],
        "expected_events": [
            {"chapter": 1, "description_keywords": ["ghost", "appears"], "note": "Ghost visit"},
        ],
        "structural_checks": {
            "min_characters": 2,
            "min_locations": 1,
            "min_relationships": 1,
            "min_events": 1,
            "expected_chapters_covered": [1, 2, 3, 4, 5],
        },
    }
    path = fixture_dir / "christmas_carol.json"
    path.write_text(json.dumps(fixture))
    return path


# ===================================================================
# CheckResult
# ===================================================================

class TestCheckResult:
    def test_construction(self):
        c = CheckResult(name="test", passed=True, expected="x", actual="x")
        assert c.passed
        assert c.name == "test"

    def test_failed_check(self):
        c = CheckResult(name="test", passed=False, expected="x", actual="y", detail="mismatch")
        assert not c.passed
        assert c.detail == "mismatch"


# ===================================================================
# ValidationReport
# ===================================================================

class TestValidationReport:
    def test_empty_report(self):
        r = ValidationReport(book_id="test", fixture_file="test.json")
        assert r.total == 0
        assert r.passed == 0
        assert r.failed == 0
        assert r.all_passed

    def test_add_passed(self):
        r = ValidationReport(book_id="test", fixture_file="test.json")
        r.add(CheckResult(name="a", passed=True, expected="", actual=""))
        assert r.passed == 1
        assert r.failed == 0
        assert r.all_passed

    def test_add_failed(self):
        r = ValidationReport(book_id="test", fixture_file="test.json")
        r.add(CheckResult(name="a", passed=False, expected="x", actual="y"))
        assert r.failed == 1
        assert not r.all_passed

    def test_skip(self):
        r = ValidationReport(book_id="test", fixture_file="test.json")
        r.skip("test", "no fixture")
        assert r.skipped == 1
        assert r.total == 1

    def test_to_dict(self):
        r = ValidationReport(book_id="test", fixture_file="test.json")
        r.add(CheckResult(name="a", passed=True, expected="1", actual="1"))
        d = r.to_dict()
        assert d["book_id"] == "test"
        assert d["summary"]["passed"] == 1
        assert len(d["checks"]) == 1

    def test_mixed_results(self):
        r = ValidationReport(book_id="test", fixture_file="test.json")
        r.add(CheckResult(name="a", passed=True, expected="", actual=""))
        r.add(CheckResult(name="b", passed=False, expected="", actual=""))
        r.skip("c", "reason")
        assert r.total == 3
        assert r.passed == 1
        assert r.failed == 1
        assert r.skipped == 1
        assert not r.all_passed


# ===================================================================
# Fixture loading
# ===================================================================

class TestLoadFixture:
    def test_loads_existing_fixture(self, christmas_carol_fixture, fixture_dir):
        result = load_fixture("christmas_carol", fixture_dir)
        assert result is not None
        assert "expected_characters" in result

    def test_returns_none_for_missing(self, fixture_dir):
        result = load_fixture("nonexistent_book", fixture_dir)
        assert result is None

    def test_real_christmas_carol_fixture_exists(self):
        """The actual fixtures/christmas_carol.json should exist in the repo."""
        path = Path(__file__).parent.parent / "validation" / "fixtures" / "christmas_carol.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "expected_characters" in data
        assert "structural_checks" in data
        assert "known_answer_queries" in data


# ===================================================================
# DataPoint loading from disk
# ===================================================================

class TestLoadExtractedDatapoints:
    def test_loads_from_batch_dirs(self, tmp_path):
        batch_dir = tmp_path / "test_book" / "batches" / "batch_01"
        batch_dir.mkdir(parents=True)
        (batch_dir / "extracted_datapoints.json").write_text(
            json.dumps([{"name": "Scrooge", "type": "Character"}])
        )
        result = _load_extracted_datapoints(tmp_path, "test_book")
        assert len(result) == 1

    def test_multiple_batches_merged(self, tmp_path):
        for i in range(3):
            bd = tmp_path / "book" / "batches" / f"batch_{i:02d}"
            bd.mkdir(parents=True)
            (bd / "extracted_datapoints.json").write_text(
                json.dumps([{"name": f"Char_{i}", "type": "Character"}])
            )
        result = _load_extracted_datapoints(tmp_path, "book")
        assert len(result) == 3

    def test_missing_batches_dir(self, tmp_path):
        result = _load_extracted_datapoints(tmp_path, "nonexistent")
        assert result == []

    def test_corrupt_json_skipped(self, tmp_path):
        bd = tmp_path / "book" / "batches" / "batch_01"
        bd.mkdir(parents=True)
        (bd / "extracted_datapoints.json").write_text("NOT JSON")
        result = _load_extracted_datapoints(tmp_path, "book")
        assert result == []


# ===================================================================
# Type extraction
# ===================================================================

class TestExtractByType:
    def test_groups_by_explicit_type(self):
        dps = [
            {"type": "Character", "name": "A"},
            {"type": "Location", "name": "B"},
            {"type": "Character", "name": "C"},
        ]
        result = _extract_by_type(dps)
        assert len(result["Character"]) == 2
        assert len(result["Location"]) == 1

    def test_infers_character_from_aliases(self):
        dps = [{"name": "A", "aliases": ["B"], "first_chapter": 1}]
        result = _extract_by_type(dps)
        assert "Character" in result

    def test_infers_relationship_from_fields(self):
        dps = [{"source": "A", "target": "B", "relation_type": "loves"}]
        result = _extract_by_type(dps)
        assert "Relationship" in result

    def test_infers_plot_event_from_fields(self):
        dps = [{"chapter": 1, "participants": [], "description": "stuff"}]
        result = _extract_by_type(dps)
        assert "PlotEvent" in result


# ===================================================================
# Structural checks
# ===================================================================

class TestStructuralChecks:
    def test_min_characters_pass(self, sample_characters):
        report = ValidationReport(book_id="t", fixture_file="t")
        by_type = {"Character": sample_characters}
        _check_structural(report, by_type, {"min_characters": 3})
        check = next(c for c in report.checks if c.name == "min_characters")
        assert check.passed

    def test_min_characters_fail(self):
        report = ValidationReport(book_id="t", fixture_file="t")
        _check_structural(report, {"Character": [{"name": "A"}]}, {"min_characters": 5})
        check = next(c for c in report.checks if c.name == "min_characters")
        assert not check.passed

    def test_chapter_coverage_pass(self):
        report = ValidationReport(book_id="t", fixture_file="t")
        by_type = {"Character": [
            {"first_chapter": 1, "chapters_present": [1, 2, 3]},
            {"first_chapter": 4},
            {"first_chapter": 5},
        ]}
        _check_structural(report, by_type, {"expected_chapters_covered": [1, 2, 3, 4, 5]})
        check = next(c for c in report.checks if c.name == "chapter_coverage")
        assert check.passed

    def test_chapter_coverage_fail(self):
        report = ValidationReport(book_id="t", fixture_file="t")
        by_type = {"Character": [{"first_chapter": 1}]}
        _check_structural(report, by_type, {"expected_chapters_covered": [1, 2, 3]})
        check = next(c for c in report.checks if c.name == "chapter_coverage")
        assert not check.passed

    def test_graph_populated(self, sample_characters):
        report = ValidationReport(book_id="t", fixture_file="t")
        _check_structural(report, {"Character": sample_characters}, {})
        check = next(c for c in report.checks if c.name == "graph_populated")
        assert check.passed

    def test_graph_empty(self):
        report = ValidationReport(book_id="t", fixture_file="t")
        _check_structural(report, {}, {})
        check = next(c for c in report.checks if c.name == "graph_populated")
        assert not check.passed


# ===================================================================
# Character checks
# ===================================================================

class TestCharacterChecks:
    def test_finds_by_name(self, sample_characters):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"name": "Scrooge", "aliases": []}]
        _check_expected_characters(report, sample_characters, expected)
        assert report.checks[0].passed

    def test_finds_by_alias(self, sample_characters):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"name": "Ebenezer Scrooge", "aliases": ["Scrooge"]}]
        _check_expected_characters(report, sample_characters, expected)
        assert report.checks[0].passed

    def test_missing_character(self, sample_characters):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"name": "Darrow", "aliases": []}]
        _check_expected_characters(report, sample_characters, expected)
        assert not report.checks[0].passed

    def test_case_insensitive(self, sample_characters):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"name": "scrooge", "aliases": []}]
        _check_expected_characters(report, sample_characters, expected)
        assert report.checks[0].passed


# ===================================================================
# Location checks
# ===================================================================

class TestLocationChecks:
    def test_finds_location(self, sample_locations):
        report = ValidationReport(book_id="t", fixture_file="t")
        _check_expected_locations(report, sample_locations, [{"name": "London"}])
        assert report.checks[0].passed

    def test_finds_by_alias(self, sample_locations):
        report = ValidationReport(book_id="t", fixture_file="t")
        _check_expected_locations(report, sample_locations, [
            {"name": "counting-house", "aliases": ["Scrooge's counting-house"]}
        ])
        assert report.checks[0].passed

    def test_missing_location(self, sample_locations):
        report = ValidationReport(book_id="t", fixture_file="t")
        _check_expected_locations(report, sample_locations, [{"name": "Paris"}])
        assert not report.checks[0].passed


# ===================================================================
# Relationship checks
# ===================================================================

class TestRelationshipChecks:
    def test_finds_relationship(self, sample_relationships):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"source": "Scrooge", "target": "Bob Cratchit", "relation_contains": ["employ"]}]
        _check_expected_relationships(report, sample_relationships, expected)
        assert report.checks[0].passed

    def test_finds_by_description_keyword(self, sample_relationships):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"source": "Fred", "target": "Scrooge", "relation_contains": ["nephew"]}]
        _check_expected_relationships(report, sample_relationships, expected)
        assert report.checks[0].passed

    def test_missing_relationship(self, sample_relationships):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"source": "Scrooge", "target": "Tiny Tim", "relation_contains": ["kills"]}]
        _check_expected_relationships(report, sample_relationships, expected)
        assert not report.checks[0].passed

    def test_handles_nested_dict_source_target(self):
        """DataPoints may serialize source/target as nested dicts."""
        rels = [{"source": {"name": "Scrooge"}, "target": {"name": "Bob Cratchit"}, "relation_type": "employs", "description": ""}]
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"source": "Scrooge", "target": "Bob Cratchit", "relation_contains": ["employ"]}]
        _check_expected_relationships(report, rels, expected)
        assert report.checks[0].passed


# ===================================================================
# Event checks
# ===================================================================

class TestEventChecks:
    def test_finds_event(self, sample_events):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"chapter": 1, "description_keywords": ["ghost", "appears"], "note": "ghost visit"}]
        _check_expected_events(report, sample_events, expected)
        assert report.checks[0].passed

    def test_missing_event(self, sample_events):
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"chapter": 4, "description_keywords": ["battle"], "note": "battle"}]
        _check_expected_events(report, sample_events, expected)
        assert not report.checks[0].passed

    def test_event_without_chapter_constraint(self, sample_events):
        """If chapter is None, match by keywords across all chapters."""
        report = ValidationReport(book_id="t", fixture_file="t")
        expected = [{"chapter": None, "description_keywords": ["transform"], "note": "transformation"}]
        _check_expected_events(report, sample_events, expected)
        assert report.checks[0].passed


# ===================================================================
# Full run_validation
# ===================================================================

class TestRunValidation:
    @pytest.mark.asyncio
    async def test_with_fixture_and_data(self, christmas_carol_fixture, fixture_dir, tmp_path, sample_datapoints):
        # Write sample DataPoints to batch dir
        batch_dir = tmp_path / "christmas_carol" / "batches" / "batch_01"
        batch_dir.mkdir(parents=True)
        (batch_dir / "extracted_datapoints.json").write_text(json.dumps(sample_datapoints))

        report = await run_validation("christmas_carol", tmp_path, fixture_dir)
        assert report.total > 0
        assert report.book_id == "christmas_carol"

    @pytest.mark.asyncio
    async def test_no_fixture_skips(self, fixture_dir, tmp_path):
        report = await run_validation("unknown_book", tmp_path, fixture_dir)
        assert report.skipped > 0
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_no_data_fails_structural(self, christmas_carol_fixture, fixture_dir, tmp_path):
        """With fixture but no extracted DataPoints, structural checks should fail."""
        report = await run_validation("christmas_carol", tmp_path, fixture_dir)
        assert report.failed > 0


# ===================================================================
# Report saving
# ===================================================================

class TestSaveValidationReport:
    def test_saves_json(self, tmp_path):
        report = ValidationReport(book_id="test", fixture_file="test.json")
        report.add(CheckResult(name="a", passed=True, expected="", actual=""))
        path = save_validation_report(report, tmp_path / "validation")
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["summary"]["passed"] == 1

    def test_creates_directory(self, tmp_path):
        report = ValidationReport(book_id="test", fixture_file="test.json")
        save_validation_report(report, tmp_path / "deep" / "nested")
        assert (tmp_path / "deep" / "nested" / "validation_results.json").exists()

    def test_output_filename(self, tmp_path):
        report = ValidationReport(book_id="test", fixture_file="test.json")
        path = save_validation_report(report, tmp_path)
        assert path.name == "validation_results.json"


# ===================================================================
# Search text extraction
# ===================================================================

class TestExtractSearchText:
    """Tests for _extract_search_text which flattens cognee SearchResult lists."""

    def test_string_results(self):
        results = [SimpleNamespace(search_result="Bob Cratchit is the clerk")]
        assert "Bob Cratchit" in _extract_search_text(results)

    def test_dict_results_with_content_key(self):
        results = [SimpleNamespace(search_result={"content": "Scrooge employs Bob"})]
        assert "Scrooge" in _extract_search_text(results)

    def test_dict_results_with_multiple_keys(self):
        results = [SimpleNamespace(search_result={"name": "Scrooge", "description": "a miser"})]
        text = _extract_search_text(results)
        assert "Scrooge" in text
        assert "miser" in text

    def test_list_results(self):
        results = [SimpleNamespace(search_result=["Bob Cratchit", "clerk"])]
        text = _extract_search_text(results)
        assert "Bob Cratchit" in text
        assert "clerk" in text

    def test_empty_results(self):
        assert _extract_search_text([]) == ""

    def test_fallback_to_str(self):
        results = [SimpleNamespace(search_result=42)]
        assert "42" in _extract_search_text(results)


# ===================================================================
# Known-answer query checks
# ===================================================================

class TestKnownAnswerQueries:
    """Tests for _check_known_answer_queries against mocked cognee.search."""

    @pytest.mark.asyncio
    async def test_correct_answer_passes(self):
        """When search returns context containing the expected term, check passes."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [{"question": "Who is Scrooge's clerk?", "expected_answer_contains": ["Bob Cratchit"], "expected_answer_not_contains": []}]

        mock_result = SimpleNamespace(search_result="Bob Cratchit serves as Scrooge's clerk")
        with patch("validation.test_suite.cognee") as mock_cognee:
            mock_cognee.search = AsyncMock(return_value=[mock_result])
            with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", True):
                await _check_known_answer_queries(report, queries, "christmas_carol")

        assert report.passed == 1
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_missing_answer_fails(self):
        """When search returns context without expected terms, check fails."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [{"question": "Who is Scrooge's clerk?", "expected_answer_contains": ["Bob Cratchit"], "expected_answer_not_contains": []}]

        mock_result = SimpleNamespace(search_result="Scrooge is a miserly old man")
        with patch("validation.test_suite.cognee") as mock_cognee:
            mock_cognee.search = AsyncMock(return_value=[mock_result])
            with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", True):
                await _check_known_answer_queries(report, queries, "christmas_carol")

        assert report.failed == 1

    @pytest.mark.asyncio
    async def test_excluded_term_fails(self):
        """When search returns excluded terms, check fails."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [{
            "question": "Who is Scrooge's clerk?",
            "expected_answer_contains": ["Bob Cratchit"],
            "expected_answer_not_contains": ["Marley"],
        }]

        mock_result = SimpleNamespace(search_result="Bob Cratchit and Marley were both associated with Scrooge")
        with patch("validation.test_suite.cognee") as mock_cognee:
            mock_cognee.search = AsyncMock(return_value=[mock_result])
            with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", True):
                await _check_known_answer_queries(report, queries, "christmas_carol")

        assert report.failed == 1

    @pytest.mark.asyncio
    async def test_skips_when_cognee_unavailable(self):
        """When cognee search is not available, queries are skipped."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [{"question": "test?", "expected_answer_contains": ["x"], "expected_answer_not_contains": []}]

        with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", False):
            await _check_known_answer_queries(report, queries, "test")

        assert report.skipped == 1
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_search_error_skips_query(self):
        """When cognee.search raises, the query is skipped (not failed)."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [{"question": "test?", "expected_answer_contains": ["x"], "expected_answer_not_contains": []}]

        with patch("validation.test_suite.cognee") as mock_cognee:
            mock_cognee.search = AsyncMock(side_effect=RuntimeError("connection failed"))
            with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", True):
                await _check_known_answer_queries(report, queries, "test")

        assert report.skipped == 1
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_multiple_queries(self):
        """Multiple queries are each checked independently."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [
            {"question": "Q1", "expected_answer_contains": ["Alice"], "expected_answer_not_contains": []},
            {"question": "Q2", "expected_answer_contains": ["Bob"], "expected_answer_not_contains": []},
        ]

        results_map = {
            "Q1": [SimpleNamespace(search_result="Alice is here")],
            "Q2": [SimpleNamespace(search_result="No match at all")],
        }

        async def mock_search(query_text, **kwargs):
            return results_map.get(query_text, [])

        with patch("validation.test_suite.cognee") as mock_cognee:
            mock_cognee.search = mock_search
            with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", True):
                await _check_known_answer_queries(report, queries, "test")

        assert report.passed == 1
        assert report.failed == 1

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self):
        """Keyword matching should be case-insensitive."""
        report = ValidationReport(book_id="test", fixture_file="test.json")
        queries = [{"question": "test", "expected_answer_contains": ["bob cratchit"], "expected_answer_not_contains": []}]

        mock_result = SimpleNamespace(search_result="BOB CRATCHIT is the clerk")
        with patch("validation.test_suite.cognee") as mock_cognee:
            mock_cognee.search = AsyncMock(return_value=[mock_result])
            with patch("validation.test_suite.COGNEE_SEARCH_AVAILABLE", True):
                await _check_known_answer_queries(report, queries, "test")

        assert report.passed == 1
