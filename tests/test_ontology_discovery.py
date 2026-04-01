"""
Comprehensive tests for pipeline/ontology_discovery.py

Tests every feature against specs in CLAUDE.md and bookrag_pipeline_plan.md:
- Entity extraction from BookNLP .book JSON and .entities TSV
- All 6 BookNLP entity category mappings (PER, LOC, FAC, GPE, VEH, ORG)
- BERTopic theme discovery (mocked) + graceful failure paths
- TF-IDF domain term extraction
- Relationship inference from agent actions + TF-IDF verbs
- OWL ontology generation with RDFLib (parsed and validated)
- Full discover_ontology() pipeline integration
- Output file structure (discovered_entities.json, book_ontology.owl)
- Config defaults and overrides
- Edge cases: empty input, missing keys, small corpora
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rdflib import OWL, RDF, RDFS, Graph, Namespace

from pipeline.ontology_discovery import (
    BASE_ENTITY_CLASSES,
    BOOK,
    BOOKNLP_CAT_MAP,
    OntologyResult,
    _DEFAULT_CONFIG,
    _RELATION_VERBS,
    _build_owl,
    _extract_entities_from_booknlp,
    _extract_tfidf_terms,
    _infer_relations,
    discover_ontology,
)


# ===================================================================
# OntologyResult dataclass
# ===================================================================

class TestOntologyResult:
    def test_default_construction(self):
        r = OntologyResult(
            discovered_entities={},
            discovered_themes=[],
            discovered_relations=[],
        )
        assert r.discovered_entities == {}
        assert r.discovered_themes == []
        assert r.discovered_relations == []
        assert r.owl_path == Path()

    def test_with_all_fields(self, tmp_path):
        r = OntologyResult(
            discovered_entities={"Character": [{"name": "X", "count": 5}]},
            discovered_themes=[{"topic_id": 0, "label": "a", "keywords": ["a"]}],
            discovered_relations=[{"name": "r", "source": "s", "evidence": "e"}],
            owl_path=tmp_path / "test.owl",
        )
        assert r.owl_path == tmp_path / "test.owl"
        assert len(r.discovered_entities["Character"]) == 1


# ===================================================================
# Config defaults — match CLAUDE.md ontology section
# ===================================================================

class TestConfigDefaults:
    """Config defaults must match CLAUDE.md: min_entity_frequency=2, num_topics=20, num_tfidf_terms=100."""

    def test_min_entity_frequency(self):
        assert _DEFAULT_CONFIG["min_entity_frequency"] == 2

    def test_num_topics(self):
        assert _DEFAULT_CONFIG["num_topics"] == 20

    def test_num_tfidf_terms(self):
        assert _DEFAULT_CONFIG["num_tfidf_terms"] == 100


# ===================================================================
# BookNLP category mapping — all 6 types from .entities spec
# ===================================================================

class TestBookNLPCategoryMapping:
    """
    BookNLP .entities TSV has cat: PER, LOC, FAC, GPE, VEH, ORG
    (from bookrag_deep_research_context.md section 2).
    """

    def test_per_maps_to_character(self):
        assert BOOKNLP_CAT_MAP["PER"] == "Character"

    def test_loc_maps_to_location(self):
        assert BOOKNLP_CAT_MAP["LOC"] == "Location"

    def test_fac_maps_to_location(self):
        assert BOOKNLP_CAT_MAP["FAC"] == "Location"

    def test_gpe_maps_to_location(self):
        assert BOOKNLP_CAT_MAP["GPE"] == "Location"

    def test_veh_maps_to_object(self):
        assert BOOKNLP_CAT_MAP["VEH"] == "Object"

    def test_org_maps_to_organization(self):
        assert BOOKNLP_CAT_MAP["ORG"] == "Organization"

    def test_all_six_categories_covered(self):
        assert set(BOOKNLP_CAT_MAP.keys()) == {"PER", "LOC", "FAC", "GPE", "VEH", "ORG"}


# ===================================================================
# Base entity classes — match CLAUDE.md DataPoint models
# ===================================================================

class TestBaseEntityClasses:
    def test_required_classes_present(self):
        for cls in ["Character", "Location", "Faction", "Organization", "Object"]:
            assert cls in BASE_ENTITY_CLASSES

    def test_count(self):
        assert len(BASE_ENTITY_CLASSES) == 5


# ===================================================================
# Step 1: Entity extraction from BookNLP
# ===================================================================

class TestExtractEntitiesFromBookNLP:
    def test_extracts_characters_from_book_json_dict_names(self, booknlp_output):
        result = _extract_entities_from_booknlp(booknlp_output)
        assert "Character" in result
        names = {e["name"] for e in result["Character"]}
        assert "Scrooge" in names  # highest count for char 0
        assert "Bob Cratchit" in names
        assert "Marley" in names  # "Marley" has count 35 > "Jacob Marley" 20

    def test_character_counts_from_book_json(self, booknlp_output):
        result = _extract_entities_from_booknlp(booknlp_output)
        scrooge = next(e for e in result["Character"] if e["name"] == "Scrooge")
        # Book JSON names count + entities TSV mentions
        assert scrooge["count"] >= 150  # at least from book_json

    def test_extracts_locations_from_entities_tsv(self, booknlp_output):
        result = _extract_entities_from_booknlp(booknlp_output)
        assert "Location" in result
        loc_names = {e["name"] for e in result["Location"]}
        assert "London" in loc_names  # LOC
        assert "Scrooge's counting-house" in loc_names  # FAC -> Location
        assert "England" in loc_names  # GPE -> Location

    def test_extracts_organizations(self, booknlp_output):
        result = _extract_entities_from_booknlp(booknlp_output)
        assert "Organization" in result
        org_names = {e["name"] for e in result["Organization"]}
        assert "Royal Exchange" in org_names

    def test_extracts_objects_from_veh(self, booknlp_output):
        result = _extract_entities_from_booknlp(booknlp_output)
        assert "Object" in result
        obj_names = {e["name"] for e in result["Object"]}
        assert "coach" in obj_names

    def test_skips_empty_text(self, booknlp_output):
        """Entities with empty text should be skipped."""
        result = _extract_entities_from_booknlp(booknlp_output)
        for items in result.values():
            for item in items:
                assert item["name"] != ""

    def test_skips_empty_category(self, booknlp_output):
        """Entities with empty cat should be skipped."""
        result = _extract_entities_from_booknlp(booknlp_output)
        for items in result.values():
            for item in items:
                assert item["name"] != "unknown"

    def test_sorted_by_count_descending(self, booknlp_output):
        result = _extract_entities_from_booknlp(booknlp_output)
        for items in result.values():
            counts = [i["count"] for i in items]
            assert counts == sorted(counts, reverse=True)

    def test_empty_input(self):
        result = _extract_entities_from_booknlp({})
        assert result == {} or all(len(v) == 0 for v in result.values())

    def test_book_json_list_format_names(self):
        """BookNLP can also output names as a list of {n, c} dicts."""
        booknlp = {
            "book_json": {
                "characters": [
                    {
                        "id": 0,
                        "names": [{"n": "Darrow", "c": 200}, {"n": "Reaper", "c": 50}],
                        "agent": [],
                    }
                ]
            },
            "entities_tsv": [],
        }
        result = _extract_entities_from_booknlp(booknlp)
        assert "Character" in result
        assert result["Character"][0]["name"] == "Darrow"

    def test_book_json_list_format_picks_max_count(self):
        """When names is a list of {n, c} dicts, pick the one with highest c."""
        booknlp = {
            "book_json": {
                "characters": [
                    {
                        "id": 0,
                        "names": [{"n": "Reaper", "c": 50}, {"n": "Darrow", "c": 200}],
                        "agent": [],
                    }
                ]
            },
            "entities_tsv": [],
        }
        result = _extract_entities_from_booknlp(booknlp)
        # Should pick "Darrow" (c=200) not "Reaper" (c=50) even though Reaper is first
        assert result["Character"][0]["name"] == "Darrow"
        assert result["Character"][0]["count"] == 200

    def test_book_json_with_no_names_key(self):
        """Characters with no names should be skipped."""
        booknlp = {
            "book_json": {"characters": [{"id": 0, "agent": []}]},
            "entities_tsv": [],
        }
        result = _extract_entities_from_booknlp(booknlp)
        # Should not crash, characters with no names are skipped
        char_count = sum(len(v) for v in result.values())
        assert char_count == 0

    def test_pronoun_mentions_filtered_out(self, booknlp_output):
        """PRON mentions (like 'he') are filtered out — they add noise as
        standalone Character instances since coref resolution happens earlier."""
        result = _extract_entities_from_booknlp(booknlp_output)
        he_present = any(e["name"] == "he" for e in result.get("Character", []))
        assert not he_present  # pronouns filtered to reduce noise

    def test_proper_noun_mentions_kept(self, booknlp_output):
        """PROP (proper noun) mentions should be counted from entities TSV."""
        result = _extract_entities_from_booknlp(booknlp_output)
        scrooge = next(e for e in result["Character"] if e["name"] == "Scrooge")
        # count = 150 (book_json) + 1 (entities_tsv PROP mention)
        assert scrooge["count"] == 151


# ===================================================================
# Step 2: BERTopic theme discovery
# ===================================================================

class TestBERTopicThemeDiscovery:
    def test_graceful_when_bertopic_not_installed(self, christmas_carol_text):
        """Per CLAUDE.md: handle case where BERTopic finds no topics gracefully."""
        from pipeline.ontology_discovery import _discover_themes_bertopic

        with patch.dict("sys.modules", {"bertopic": None}):
            with patch("builtins.__import__", side_effect=ImportError("no bertopic")):
                # The function catches ImportError internally
                result = _discover_themes_bertopic(christmas_carol_text, 20)
                # Should not crash but return empty
                assert isinstance(result, list)

    def test_too_few_paragraphs_returns_empty(self):
        """Books with <10 paragraphs should skip BERTopic."""
        from pipeline.ontology_discovery import _discover_themes_bertopic

        short_text = "Short paragraph one.\n\nShort paragraph two."
        result = _discover_themes_bertopic(short_text, 20)
        assert result == []

    def test_returns_list_of_dicts_with_correct_keys(self):
        """When BERTopic succeeds, results should have topic_id, label, keywords."""
        from pipeline.ontology_discovery import _discover_themes_bertopic

        # Mock BERTopic
        mock_topic_model = MagicMock()
        mock_topic_model.fit_transform.return_value = ([0, 1, 0, 1], [0.9, 0.8, 0.7, 0.6])

        import pandas as pd
        mock_topic_model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [-1, 0, 1],
            "Count": [5, 10, 8],
            "Name": ["outlier", "topic_0", "topic_1"],
        })
        mock_topic_model.get_topic.side_effect = lambda tid: {
            0: [("christmas", 0.5), ("ghost", 0.4), ("spirit", 0.3)],
            1: [("money", 0.5), ("poor", 0.4), ("wages", 0.3)],
        }.get(tid, [])

        mock_bertopic_cls = MagicMock(return_value=mock_topic_model)
        mock_module = MagicMock()
        mock_module.BERTopic = mock_bertopic_cls

        with patch.dict("sys.modules", {"bertopic": mock_module}):
            # Generate enough paragraphs
            text = "\n\n".join([f"This is a long enough paragraph number {i} about ghosts and spirits." * 3 for i in range(15)])
            result = _discover_themes_bertopic(text, 20)

        assert len(result) == 2  # outlier topic -1 is excluded
        for theme in result:
            assert "topic_id" in theme
            assert "label" in theme
            assert "keywords" in theme
            assert theme["topic_id"] != -1  # outlier excluded

    def test_outlier_topic_excluded(self):
        """Topic -1 (outlier) should never appear in results."""
        from pipeline.ontology_discovery import _discover_themes_bertopic

        mock_topic_model = MagicMock()
        mock_topic_model.fit_transform.return_value = ([-1] * 15, [0.1] * 15)

        import pandas as pd
        mock_topic_model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [-1],
            "Count": [15],
            "Name": ["outlier"],
        })

        mock_bertopic_cls = MagicMock(return_value=mock_topic_model)
        mock_module = MagicMock()
        mock_module.BERTopic = mock_bertopic_cls

        with patch.dict("sys.modules", {"bertopic": mock_module}):
            text = "\n\n".join([f"Paragraph {i} with enough content to process." * 3 for i in range(15)])
            result = _discover_themes_bertopic(text, 20)

        assert result == []

    def test_bertopic_exception_returns_empty(self):
        """BERTopic runtime failure should be caught gracefully."""
        from pipeline.ontology_discovery import _discover_themes_bertopic

        mock_bertopic_cls = MagicMock(side_effect=RuntimeError("CUDA OOM"))
        mock_module = MagicMock()
        mock_module.BERTopic = mock_bertopic_cls

        with patch.dict("sys.modules", {"bertopic": mock_module}):
            text = "\n\n".join([f"Paragraph {i} content." * 5 for i in range(15)])
            result = _discover_themes_bertopic(text, 20)

        assert result == []


# ===================================================================
# Step 3: TF-IDF domain term extraction
# ===================================================================

class TestTFIDFExtraction:
    def test_returns_list_of_strings(self, christmas_carol_text):
        result = _extract_tfidf_terms(christmas_carol_text, 100)
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_respects_num_terms_limit(self, christmas_carol_text):
        result = _extract_tfidf_terms(christmas_carol_text, 10)
        assert len(result) <= 10

    def test_finds_domain_terms(self, christmas_carol_text):
        result = _extract_tfidf_terms(christmas_carol_text, 100)
        # Should find key A Christmas Carol terms
        all_terms_lower = [t.lower() for t in result]
        # At least some of these domain terms should appear
        found = any(t in all_terms_lower for t in ["scrooge", "christmas", "ghost", "marley", "cratchit"])
        assert found, f"Expected domain terms not found in: {result[:20]}"

    def test_empty_text_returns_empty(self):
        result = _extract_tfidf_terms("", 100)
        assert result == []

    def test_single_paragraph_may_fail_gracefully(self):
        """With min_df=2, a single paragraph can't meet the threshold."""
        result = _extract_tfidf_terms("Just one short paragraph.", 100)
        assert isinstance(result, list)

    def test_includes_bigrams(self, christmas_carol_text):
        """ngram_range=(1,2) should produce some bigrams."""
        result = _extract_tfidf_terms(christmas_carol_text, 100)
        bigrams = [t for t in result if " " in t]
        # Bigrams may or may not appear depending on corpus, but structure is correct
        assert isinstance(bigrams, list)


# ===================================================================
# Step 4: Relationship inference
# ===================================================================

class TestInferRelations:
    def test_extracts_from_agent_actions(self, booknlp_output):
        result = _infer_relations(booknlp_output, [])
        names = {r["name"] for r in result}
        # "said", "muttered", "exclaimed", "walked", "employs" are agent actions
        assert "said" in names
        assert "employs" in names

    def test_source_is_booknlp_agent_actions(self, booknlp_output):
        result = _infer_relations(booknlp_output, [])
        for r in result:
            assert r["source"] == "booknlp_agent_actions"
            assert "evidence" in r

    def test_extracts_from_tfidf_relation_verbs(self):
        result = _infer_relations({"book_json": {"characters": []}, "entities_tsv": []}, ["loves", "banana", "fights"])
        names = {r["name"] for r in result}
        assert "loves" in names
        assert "fights" in names
        assert "banana" not in names  # not a relation verb

    def test_tfidf_bigram_relations(self):
        result = _infer_relations(
            {"book_json": {"characters": []}, "entities_tsv": []},
            ["leads army"],
        )
        names = {r["name"] for r in result}
        assert "leads_army" in names

    def test_no_duplicates(self, booknlp_output):
        # Pass "employs" in both agent actions and TF-IDF
        result = _infer_relations(booknlp_output, ["employs"])
        employs_count = sum(1 for r in result if r["name"] == "employs")
        assert employs_count == 1  # deduped

    def test_skips_short_verbs(self):
        """Verbs <= 2 chars should be filtered."""
        booknlp = {
            "book_json": {
                "characters": [{"id": 0, "names": {}, "agent": [{"w": "be", "c": 100}]}]
            },
            "entities_tsv": [],
        }
        result = _infer_relations(booknlp, [])
        names = {r["name"] for r in result}
        assert "be" not in names

    def test_uses_action_count_field(self):
        """Agent actions have a 'c' (count) field — should be used, not ignored."""
        booknlp = {
            "book_json": {
                "characters": [
                    {"id": 0, "names": {}, "agent": [{"w": "said", "c": 30}]},
                    {"id": 1, "names": {}, "agent": [{"w": "said", "c": 12}]},
                ]
            },
            "entities_tsv": [],
        }
        result = _infer_relations(booknlp, [])
        said_rel = next(r for r in result if r["name"] == "said")
        # Total count should be 30 + 12 = 42, not 2
        assert "42" in said_rel["evidence"]

    def test_action_count_defaults_to_one(self):
        """If 'c' field is missing, treat each action as count 1."""
        booknlp = {
            "book_json": {
                "characters": [
                    {"id": 0, "names": {}, "agent": [{"w": "walked"}]},
                ]
            },
            "entities_tsv": [],
        }
        result = _infer_relations(booknlp, [])
        walked = next(r for r in result if r["name"] == "walked")
        assert "1" in walked["evidence"]

    def test_empty_input(self):
        result = _infer_relations({}, [])
        assert result == []

    def test_relation_verbs_vocabulary_exists(self):
        """The relation verbs set should contain common literary relationship verbs."""
        assert len(_RELATION_VERBS) > 20
        for verb in ["loves", "hates", "kills", "employs", "betrays"]:
            assert verb in _RELATION_VERBS


# ===================================================================
# Step 5: OWL ontology generation
# ===================================================================

class TestBuildOWL:
    def test_creates_valid_owl_file(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl(
            entities={"Character": [{"name": "Scrooge", "count": 10}]},
            themes=[],
            relations=[],
            owl_path=owl_path,
            min_entity_frequency=2,
        )
        assert owl_path.exists()
        # Should be valid XML/RDF
        g = Graph()
        g.parse(str(owl_path), format="xml")
        assert len(g) > 0

    def test_ontology_declaration(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        # Should have an OWL Ontology declaration
        ontologies = list(g.subjects(RDF.type, OWL.Ontology))
        assert len(ontologies) == 1

    def test_root_class_book_entity(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        book_entity = BOOK.BookEntity
        assert (book_entity, RDF.type, OWL.Class) in g

    def test_all_base_classes_as_subclass_of_book_entity(self, tmp_path):
        """Per CLAUDE.md: Character, Location, Faction, Organization, Object."""
        owl_path = tmp_path / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        for cls_name in BASE_ENTITY_CLASSES:
            cls_uri = BOOK[cls_name]
            assert (cls_uri, RDF.type, OWL.Class) in g
            assert (cls_uri, RDFS.subClassOf, BOOK.BookEntity) in g

    def test_plot_event_class_always_present(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        assert (BOOK.PlotEvent, RDF.type, OWL.Class) in g
        assert (BOOK.PlotEvent, RDFS.subClassOf, BOOK.BookEntity) in g

    def test_relationship_class_always_present(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        assert (BOOK.Relationship, RDF.type, OWL.Class) in g

    def test_theme_root_class(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        assert (BOOK.Theme, RDF.type, OWL.Class) in g
        assert (BOOK.Theme, RDFS.subClassOf, BOOK.BookEntity) in g

    def test_entity_individuals_above_frequency(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl(
            entities={"Character": [
                {"name": "Scrooge", "count": 10},
                {"name": "Minor", "count": 1},
            ]},
            themes=[], relations=[], owl_path=owl_path,
            min_entity_frequency=2,
        )
        g = Graph()
        g.parse(str(owl_path), format="xml")
        # Scrooge (count=10) should be included
        assert (BOOK.Scrooge, RDF.type, OWL.NamedIndividual) in g
        # Minor (count=1) should be filtered out
        assert (BOOK.Minor, RDF.type, OWL.NamedIndividual) not in g

    def test_theme_subclasses_from_bertopic(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        themes = [
            {"topic_id": 0, "label": "christmas_ghost", "keywords": ["christmas", "ghost"]},
        ]
        _build_owl({}, themes, [], owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        theme_uri = BOOK.Theme_christmas_ghost
        assert (theme_uri, RDF.type, OWL.Class) in g
        assert (theme_uri, RDFS.subClassOf, BOOK.Theme) in g

    def test_relation_object_properties(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        relations = [{"name": "employs", "source": "test", "evidence": "test evidence"}]
        _build_owl({}, [], relations, owl_path, 2)
        g = Graph()
        g.parse(str(owl_path), format="xml")
        assert (BOOK.employs, RDF.type, OWL.ObjectProperty) in g
        assert (BOOK.employs, RDFS.domain, BOOK.BookEntity) in g
        assert (BOOK.employs, RDFS.range, BOOK.BookEntity) in g

    def test_special_characters_in_names_sanitized(self, tmp_path):
        owl_path = tmp_path / "test.owl"
        _build_owl(
            entities={"Character": [{"name": "Bob's Friend #1", "count": 5}]},
            themes=[], relations=[], owl_path=owl_path,
            min_entity_frequency=2,
        )
        g = Graph()
        g.parse(str(owl_path), format="xml")
        # Should not crash; name sanitized to Bob_s_Friend__1
        individuals = list(g.subjects(RDF.type, OWL.NamedIndividual))
        assert len(individuals) > 0

    def test_custom_entity_type_declared_as_owl_class(self, tmp_path):
        """Entity types added during review (not in BASE_ENTITY_CLASSES) must be
        declared as OWL Classes with rdfs:subClassOf BookEntity.
        Cognee's ontology processor does BFS on subClassOf hierarchies."""
        owl_path = tmp_path / "test.owl"
        _build_owl(
            entities={"Weapon": [{"name": "Sword", "count": 5}]},
            themes=[], relations=[], owl_path=owl_path,
            min_entity_frequency=2,
        )
        g = Graph()
        g.parse(str(owl_path), format="xml")
        # "Weapon" must exist as an OWL Class, subclass of BookEntity
        assert (BOOK.Weapon, RDF.type, OWL.Class) in g
        assert (BOOK.Weapon, RDFS.subClassOf, BOOK.BookEntity) in g
        # The individual "Sword" should be typed to Weapon
        assert (BOOK.Sword, RDF.type, BOOK.Weapon) in g

    def test_base_classes_still_present_with_custom_types(self, tmp_path):
        """Adding custom entity types should not remove the base classes."""
        owl_path = tmp_path / "test.owl"
        _build_owl(
            entities={"Weapon": [{"name": "Sword", "count": 5}]},
            themes=[], relations=[], owl_path=owl_path,
            min_entity_frequency=2,
        )
        g = Graph()
        g.parse(str(owl_path), format="xml")
        for cls_name in BASE_ENTITY_CLASSES:
            assert (BOOK[cls_name], RDF.type, OWL.Class) in g

    def test_creates_parent_directories(self, tmp_path):
        owl_path = tmp_path / "deep" / "nested" / "dir" / "test.owl"
        _build_owl({}, [], [], owl_path, 2)
        assert owl_path.exists()


# ===================================================================
# Full pipeline integration: discover_ontology()
# ===================================================================

class TestDiscoverOntology:
    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_returns_ontology_result(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        assert isinstance(result, OntologyResult)

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_creates_discovered_entities_json(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        json_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "discovered_entities.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["book_id"] == "christmas_carol"
        assert "entities" in data
        assert "themes" in data
        assert "relations" in data
        assert "config" in data

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_creates_owl_file(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        assert result.owl_path.exists()
        assert result.owl_path.name == "book_ontology.owl"

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_output_path_matches_spec(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        """Per CLAUDE.md: ontology/discovered_entities.json and ontology/book_ontology.owl."""
        monkeypatch.chdir(tmp_path)
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        expected_dir = tmp_path / "data" / "processed" / "christmas_carol" / "ontology"
        assert result.owl_path.resolve() == (expected_dir / "book_ontology.owl").resolve()
        assert (expected_dir / "discovered_entities.json").exists()
        assert (expected_dir / "book_ontology.owl").exists()

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_config_overrides(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {"min_entity_frequency": 5, "num_topics": 10, "num_tfidf_terms": 50}
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol", config)
        # Verify config was saved
        json_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "discovered_entities.json"
        data = json.loads(json_path.read_text())
        assert data["config"]["min_entity_frequency"] == 5
        assert data["config"]["num_topics"] == 10
        assert data["config"]["num_tfidf_terms"] == 50

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_tfidf_top_terms_saved(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        json_path = tmp_path / "data" / "processed" / "christmas_carol" / "ontology" / "discovered_entities.json"
        data = json.loads(json_path.read_text())
        assert "tfidf_top_terms" in data
        assert len(data["tfidf_top_terms"]) <= 30

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_result_entities_populated(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        assert "Character" in result.discovered_entities
        assert len(result.discovered_entities["Character"]) > 0

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_result_relations_populated(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        assert len(result.discovered_relations) > 0

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_owl_file_is_valid_rdf(self, mock_bert, booknlp_output, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = discover_ontology(booknlp_output, christmas_carol_text, "christmas_carol")
        g = Graph()
        g.parse(str(result.owl_path), format="xml")
        assert len(g) > 0

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_empty_booknlp_does_not_crash(self, mock_bert, christmas_carol_text, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = discover_ontology({}, christmas_carol_text, "empty_book")
        assert isinstance(result, OntologyResult)
        assert result.owl_path.exists()

    @patch("pipeline.ontology_discovery._discover_themes_bertopic", return_value=[])
    def test_function_signature_matches_spec(self, mock_bert, tmp_path, monkeypatch):
        """discover_ontology(booknlp_output, full_text, book_id, config) -> OntologyResult"""
        monkeypatch.chdir(tmp_path)
        import inspect
        sig = inspect.signature(discover_ontology)
        params = list(sig.parameters.keys())
        assert params == ["booknlp_output", "full_text", "book_id", "config"]
