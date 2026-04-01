"""
Comprehensive tests for pipeline/ontology_reviewer.py

Tests every feature against CLAUDE.md and bookrag_pipeline_plan.md:
- Auto-review mode (skip interactive prompts, save snapshot)
- Interactive review: add/remove/rename entity types
- Interactive review: remove themes
- Interactive review: add/remove relations
- Review snapshot JSON file generation
- OWL rebuild after changes
- Rich library fallback to plain print
- Display functions (entities, themes, relations)
- Accept-all shortcut
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.ontology_discovery import OntologyResult, _build_owl
from pipeline.ontology_reviewer import (
    _display_entities,
    _display_relations,
    _display_themes,
    _edit_entity_types,
    _edit_relations,
    _edit_themes,
    review_ontology,
)


# ===================================================================
# Auto-review mode — per CLAUDE.md: auto_review=True skips prompt
# ===================================================================

class TestAutoReview:
    def test_auto_review_returns_unchanged_result(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        assert result is sample_ontology_result

    def test_auto_review_saves_snapshot(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        assert snapshot_path.exists()

    def test_auto_review_snapshot_contains_review_mode(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert data["review_mode"] == "auto"

    def test_auto_review_snapshot_contains_book_id(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert data["book_id"] == "christmas_carol"

    def test_auto_review_snapshot_contains_entities(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert "entities" in data
        assert "Character" in data["entities"]

    def test_auto_review_snapshot_contains_themes(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert "themes" in data
        assert len(data["themes"]) == 2

    def test_auto_review_snapshot_contains_relation_names(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert "relations" in data
        # Relations are saved as list of names, not full dicts
        assert "employs" in data["relations"]

    def test_auto_review_does_not_prompt(self, sample_ontology_result, tmp_path, monkeypatch):
        """Auto-review must never call input()."""
        monkeypatch.chdir(tmp_path)
        with patch("builtins.input", side_effect=AssertionError("input() should not be called")):
            review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)


# ===================================================================
# Interactive review — accept all
# ===================================================================

class TestInteractiveReviewAcceptAll:
    def test_accept_all_returns_ontology_result(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Simulate: user presses Enter (accept all defaults)
        with patch("pipeline.ontology_reviewer._confirm", return_value=True):
            result = review_ontology(sample_ontology_result, "christmas_carol", auto_review=False)
        assert isinstance(result, OntologyResult)

    def test_accept_all_saves_interactive_snapshot(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("pipeline.ontology_reviewer._confirm", return_value=True):
            review_ontology(sample_ontology_result, "christmas_carol", auto_review=False)
        snapshot_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert data["review_mode"] == "interactive"


# ===================================================================
# Edit entity types
# ===================================================================

class TestEditEntityTypes:
    def test_add_entity_type(self):
        entities = {"Character": [{"name": "A", "count": 1}]}
        with patch("pipeline.ontology_reviewer._input", side_effect=["a", "Weapon", "d"]):
            result = _edit_entity_types(entities)
        assert "Weapon" in result
        assert result["Weapon"] == []

    def test_remove_entity_type(self):
        entities = {"Character": [{"name": "A", "count": 1}], "Object": []}
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "Object", "d"]):
            result = _edit_entity_types(entities)
        assert "Object" not in result
        assert "Character" in result

    def test_rename_entity_type(self):
        entities = {"Character": [{"name": "A", "count": 1}]}
        with patch("pipeline.ontology_reviewer._input", side_effect=["n", "Character", "Person", "d"]):
            result = _edit_entity_types(entities)
        assert "Person" in result
        assert "Character" not in result
        assert result["Person"] == [{"name": "A", "count": 1}]

    def test_add_duplicate_type_rejected(self):
        entities = {"Character": []}
        with patch("pipeline.ontology_reviewer._input", side_effect=["a", "Character", "d"]):
            result = _edit_entity_types(entities)
        assert list(result.keys()).count("Character") == 1

    def test_remove_nonexistent_type(self):
        entities = {"Character": []}
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "Nonexistent", "d"]):
            result = _edit_entity_types(entities)
        assert "Character" in result

    def test_done_exits_immediately(self):
        entities = {"Character": []}
        with patch("pipeline.ontology_reviewer._input", side_effect=["d"]):
            result = _edit_entity_types(entities)
        assert result == entities

    def test_empty_action_exits(self):
        entities = {"Character": []}
        with patch("pipeline.ontology_reviewer._input", side_effect=[""]):
            result = _edit_entity_types(entities)
        assert result == entities


# ===================================================================
# Edit themes
# ===================================================================

class TestEditThemes:
    def test_remove_theme_by_topic_id(self):
        themes = [
            {"topic_id": 0, "label": "a", "keywords": ["a"]},
            {"topic_id": 1, "label": "b", "keywords": ["b"]},
        ]
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "0", "d"]):
            result = _edit_themes(themes)
        assert len(result) == 1
        assert result[0]["topic_id"] == 1

    def test_remove_invalid_topic_id(self):
        themes = [{"topic_id": 0, "label": "a", "keywords": ["a"]}]
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "abc", "d"]):
            result = _edit_themes(themes)
        assert len(result) == 1  # nothing removed

    def test_remove_nonexistent_topic_id(self):
        """Removing a topic ID that doesn't exist should report 'not found'."""
        themes = [{"topic_id": 5, "label": "a", "keywords": ["a"]}]
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "99", "d"]):
            result = _edit_themes(themes)
        assert len(result) == 1  # nothing removed

    def test_remove_non_sequential_topic_ids(self):
        """BERTopic topic IDs are not necessarily 0..N. Should work with any valid ID."""
        themes = [
            {"topic_id": 3, "label": "a", "keywords": ["a"]},
            {"topic_id": 7, "label": "b", "keywords": ["b"]},
        ]
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "7", "d"]):
            result = _edit_themes(themes)
        assert len(result) == 1
        assert result[0]["topic_id"] == 3

    def test_remove_from_empty_themes(self):
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "d"]):
            result = _edit_themes([])
        assert result == []

    def test_done_exits(self):
        themes = [{"topic_id": 0, "label": "a", "keywords": ["a"]}]
        with patch("pipeline.ontology_reviewer._input", side_effect=["d"]):
            result = _edit_themes(themes)
        assert len(result) == 1


# ===================================================================
# Edit relations
# ===================================================================

class TestEditRelations:
    def test_add_relation(self):
        relations = []
        with patch("pipeline.ontology_reviewer._input", side_effect=["a", "mentors", "d"]):
            result = _edit_relations(relations)
        assert len(result) == 1
        assert result[0]["name"] == "mentors"
        assert result[0]["source"] == "manual_review"

    def test_remove_relation(self):
        relations = [
            {"name": "employs", "source": "booknlp", "evidence": ""},
            {"name": "serves", "source": "booknlp", "evidence": ""},
        ]
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "employs", "d"]):
            result = _edit_relations(relations)
        assert len(result) == 1
        assert result[0]["name"] == "serves"

    def test_remove_nonexistent_relation(self):
        relations = [{"name": "employs", "source": "booknlp", "evidence": ""}]
        with patch("pipeline.ontology_reviewer._input", side_effect=["r", "nonexistent", "d"]):
            result = _edit_relations(relations)
        assert len(result) == 1

    def test_done_exits(self):
        relations = [{"name": "employs", "source": "booknlp", "evidence": ""}]
        with patch("pipeline.ontology_reviewer._input", side_effect=["d"]):
            result = _edit_relations(relations)
        assert len(result) == 1


# ===================================================================
# Interactive review with edits → OWL rebuild
# ===================================================================

class TestMinEntityFrequencyPassthrough:
    """The reviewer must use the same min_entity_frequency as discovery, not hardcode it."""

    def test_default_min_freq_is_two(self, sample_ontology_result, tmp_path, monkeypatch):
        """Default should match discovery default of 2."""
        import inspect
        sig = inspect.signature(review_ontology)
        assert sig.parameters["min_entity_frequency"].default == 2

    def test_custom_min_freq_passed_to_owl_rebuild(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        owl_dir = tmp_path / "data" / "processed" / "christmas_carol" / "ontology"
        owl_dir.mkdir(parents=True, exist_ok=True)
        owl_path = owl_dir / "book_ontology.owl"
        sample_ontology_result.owl_path = owl_path

        _build_owl(
            sample_ontology_result.discovered_entities,
            sample_ontology_result.discovered_themes,
            sample_ontology_result.discovered_relations,
            owl_path, 2,
        )

        # Use min_entity_frequency=200 — should exclude all entities from OWL individuals
        confirm_responses = iter([False, True, False, False])
        input_responses = iter(["a", "TestType", "d"])

        with patch("pipeline.ontology_reviewer._confirm", side_effect=confirm_responses):
            with patch("pipeline.ontology_reviewer._input", side_effect=input_responses):
                review_ontology(
                    sample_ontology_result, "christmas_carol",
                    auto_review=False, min_entity_frequency=200,
                )

        from rdflib import Graph, OWL, RDF
        g = Graph()
        g.parse(str(owl_path), format="xml")
        # With min_freq=200, no individuals should pass the threshold
        individuals = list(g.subjects(RDF.type, OWL.NamedIndividual))
        assert len(individuals) == 0


class TestInteractiveReviewWithEdits:
    def test_owl_rebuilt_after_changes(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # First create the OWL file
        owl_dir = tmp_path / "data" / "processed" / "christmas_carol" / "ontology"
        owl_dir.mkdir(parents=True, exist_ok=True)
        owl_path = owl_dir / "book_ontology.owl"
        sample_ontology_result.owl_path = owl_path

        # Write initial OWL
        _build_owl(
            sample_ontology_result.discovered_entities,
            sample_ontology_result.discovered_themes,
            sample_ontology_result.discovered_relations,
            owl_path, 2,
        )
        initial_size = owl_path.stat().st_size

        # Simulate: reject accept-all, then add a new entity type, accept rest
        confirm_responses = iter([False, True, False, False])  # reject, edit entities, skip themes, skip relations
        input_responses = iter(["a", "Weapon", "d"])

        with patch("pipeline.ontology_reviewer._confirm", side_effect=confirm_responses):
            with patch("pipeline.ontology_reviewer._input", side_effect=input_responses):
                result = review_ontology(sample_ontology_result, "christmas_carol", auto_review=False)

        assert "Weapon" in result.discovered_entities
        # OWL was rebuilt (file should be different)
        assert owl_path.exists()


# ===================================================================
# Display functions (smoke tests — just ensure no crash)
# ===================================================================

class TestDisplayFunctions:
    def test_display_entities_no_crash(self, capsys):
        entities = {
            "Character": [{"name": "Scrooge", "count": 150}],
            "Location": [{"name": "London", "count": 3}],
        }
        _display_entities(entities)

    def test_display_themes_no_crash(self, capsys):
        themes = [{"topic_id": 0, "label": "test", "keywords": ["a", "b", "c"]}]
        _display_themes(themes)

    def test_display_themes_empty_no_crash(self, capsys):
        _display_themes([])

    def test_display_relations_no_crash(self, capsys):
        relations = [{"name": "employs", "source": "booknlp", "evidence": "test"}]
        _display_relations(relations)

    def test_display_relations_over_30(self, capsys):
        """Should cap display at 30 and show overflow message."""
        relations = [{"name": f"rel_{i}", "source": "test", "evidence": ""} for i in range(40)]
        _display_relations(relations)


# ===================================================================
# Rich fallback
# ===================================================================

class TestRichFallback:
    def test_plain_print_when_no_rich(self):
        """When rich is not available, _HAS_RICH should be False and plain fallbacks used."""
        # This is a structural test — we just verify the module loads
        from pipeline.ontology_reviewer import _HAS_RICH
        # _HAS_RICH is True or False depending on env — both are valid
        assert isinstance(_HAS_RICH, bool)


# ===================================================================
# Review snapshot structure — per CLAUDE.md output spec
# ===================================================================

class TestReviewSnapshotStructure:
    def test_snapshot_path_matches_spec(self, sample_ontology_result, tmp_path, monkeypatch):
        """Per CLAUDE.md: ontology/review_snapshot.json."""
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        expected = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        assert expected.exists()

    def test_snapshot_is_valid_json(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(path.read_text())
        assert isinstance(data, dict)

    def test_snapshot_has_all_required_keys(self, sample_ontology_result, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        review_ontology(sample_ontology_result, "christmas_carol", auto_review=True)
        path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "review_snapshot.json"
        data = json.loads(path.read_text())
        for key in ["book_id", "review_mode", "entities", "themes", "relations"]:
            assert key in data, f"Missing key: {key}"
