"""Unit tests for pipeline.benchmark_eval — Phase A Stage 3 harness.

Pure-function tests: no LLM, no pipeline runs. Verifies the scorers pick up
canonical/alias matches, undirected relationship matching, tier filtering,
provenance coverage, and the winner-picker acceptance criteria.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.benchmark_eval import (
    compute_entity_recall,
    compute_provenance_pass_rate,
    compute_relationship_recall,
    load_gold,
    pick_winner,
    summarize_run,
)


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


def _gold_fixture() -> dict:
    return {
        "book_id": "toy",
        "characters": [
            {"name": "Scrooge", "aliases": ["Ebenezer"], "first_chapter": 1, "tier": "major"},
            {"name": "Bob Cratchit", "aliases": ["Bob"], "first_chapter": 1, "tier": "major"},
            {"name": "Fezziwig", "aliases": ["Mr. Fezziwig"], "first_chapter": 2, "tier": "minor"},
            {"name": "Belle", "aliases": [], "first_chapter": 2, "tier": "minor"},
        ],
        "relationships": [
            {"source": "Scrooge", "target": "Bob Cratchit", "type": "ally", "first_chapter": 1},
            {"source": "Scrooge", "target": "Belle", "type": "romantic", "first_chapter": 2},
        ],
    }


# -------------------------------------------------------------------------
# Entity recall
# -------------------------------------------------------------------------


def test_entity_recall_all_canonical_match():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Scrooge"},
        {"type": "Character", "name": "Bob Cratchit"},
        {"type": "Character", "name": "Fezziwig"},
        {"type": "Character", "name": "Belle"},
    ]
    result = compute_entity_recall(extracted, gold)
    assert result["recall"] == 1.0
    assert result["found"] == 4
    assert result["total"] == 4
    assert result["missed"] == []


def test_entity_recall_half_missed():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Scrooge"},
        {"type": "Character", "name": "Bob Cratchit"},
    ]
    result = compute_entity_recall(extracted, gold)
    assert result["recall"] == 0.5
    assert result["found"] == 2
    assert set(result["missed"]) == {"Fezziwig", "Belle"}


def test_entity_recall_alias_in_gold_matches():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Ebenezer"},    # alias of Scrooge in gold
        {"type": "Character", "name": "Mr. Fezziwig"}, # alias of Fezziwig
    ]
    result = compute_entity_recall(extracted, gold)
    assert result["found"] == 2
    assert "Scrooge" not in result["missed"]


def test_entity_recall_alias_in_extraction_matches():
    """Extracted entity emits its canonical name AND aliases — either should hit."""
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Ebby", "aliases": ["Scrooge"]},
    ]
    result = compute_entity_recall(extracted, gold)
    assert "Scrooge" not in result["missed"]


def test_entity_recall_case_and_punctuation_insensitive():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "SCROOGE"},
        {"type": "Character", "name": "Bob  Cratchit!"},  # extra space + punct
    ]
    result = compute_entity_recall(extracted, gold)
    assert result["found"] == 2


def test_entity_recall_ignores_non_character_types():
    gold = _gold_fixture()
    extracted = [
        {"type": "Location", "name": "Scrooge"},  # wrong type
        {"type": "Character", "name": "Scrooge"},
    ]
    result = compute_entity_recall(extracted, gold)
    assert result["found"] == 1


def test_entity_recall_tier_filter_major_only():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Scrooge"},
        {"type": "Character", "name": "Bob Cratchit"},
    ]
    result = compute_entity_recall(extracted, gold, tier="major")
    assert result["total"] == 2
    assert result["recall"] == 1.0


def test_entity_recall_tier_filter_minor_only():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Fezziwig"},
    ]
    result = compute_entity_recall(extracted, gold, tier="minor")
    assert result["total"] == 2
    assert result["recall"] == 0.5
    assert result["missed"] == ["Belle"]


def test_entity_recall_empty_extracted():
    gold = _gold_fixture()
    result = compute_entity_recall([], gold)
    assert result["recall"] == 0.0
    assert result["found"] == 0


def test_entity_recall_empty_gold():
    result = compute_entity_recall(
        [{"type": "Character", "name": "Scrooge"}],
        {"characters": []},
    )
    assert result["recall"] == 0.0
    assert result["total"] == 0


# -------------------------------------------------------------------------
# Relationship recall
# -------------------------------------------------------------------------


def test_relationship_recall_flat_shape():
    gold = _gold_fixture()
    extracted = [
        {"type": "Relationship", "source_name": "Scrooge", "target_name": "Bob Cratchit"},
        {"type": "Relationship", "source_name": "Scrooge", "target_name": "Belle"},
    ]
    result = compute_relationship_recall(extracted, gold)
    assert result["recall"] == 1.0
    assert result["found"] == 2


def test_relationship_recall_nested_shape():
    gold = _gold_fixture()
    extracted = [
        {"type": "Relationship",
         "source": {"name": "Scrooge"}, "target": {"name": "Bob Cratchit"}},
    ]
    result = compute_relationship_recall(extracted, gold)
    assert result["found"] == 1


def test_relationship_recall_undirected_match():
    """(A, B) in extracted should hit (B, A) in gold and vice versa."""
    gold = _gold_fixture()
    extracted = [
        {"type": "Relationship", "source_name": "Bob Cratchit", "target_name": "Scrooge"},
    ]
    result = compute_relationship_recall(extracted, gold)
    assert result["found"] == 1


def test_relationship_recall_alias_match():
    gold = _gold_fixture()
    extracted = [
        {"type": "Relationship", "source_name": "Ebenezer", "target_name": "Bob"},
    ]
    result = compute_relationship_recall(extracted, gold)
    assert result["found"] == 1


def test_relationship_recall_ignores_non_relationship_types():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "source_name": "Scrooge", "target_name": "Bob Cratchit"},
    ]
    result = compute_relationship_recall(extracted, gold)
    assert result["found"] == 0


# -------------------------------------------------------------------------
# Provenance pass rate
# -------------------------------------------------------------------------


def test_provenance_rate_all_have_quotes():
    extracted = [
        {"type": "Character", "name": "A", "provenance": [{"quote": "x"}]},
        {"type": "Location", "name": "B", "provenance": [{"quote": "y"}]},
    ]
    result = compute_provenance_pass_rate(extracted)
    assert result["rate"] == 1.0
    assert result["total"] == 2


def test_provenance_rate_none_have_quotes():
    extracted = [
        {"type": "Character", "name": "A", "provenance": []},
        {"type": "Location", "name": "B"},  # field absent
    ]
    result = compute_provenance_pass_rate(extracted)
    assert result["rate"] == 0.0


def test_provenance_rate_mixed():
    extracted = [
        {"type": "Character", "name": "A", "provenance": [{"quote": "x"}]},
        {"type": "Character", "name": "B", "provenance": []},
    ]
    result = compute_provenance_pass_rate(extracted)
    assert result["rate"] == 0.5


def test_provenance_rate_ignores_untyped():
    extracted = [{"foo": "bar"}]
    result = compute_provenance_pass_rate(extracted)
    assert result["total"] == 0


# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------


def test_summarize_run_has_all_sections():
    gold = _gold_fixture()
    extracted = [
        {"type": "Character", "name": "Scrooge", "provenance": [{"quote": "q"}]},
    ]
    summary = summarize_run(extracted, gold, extra={"chunk_size": 1500})
    assert "entity_recall_all" in summary
    assert "entity_recall_major" in summary
    assert "entity_recall_minor" in summary
    assert "relationship_recall" in summary
    assert "provenance_pass_rate" in summary
    assert summary["counts"]["characters"] == 1
    assert summary["extra"]["chunk_size"] == 1500


# -------------------------------------------------------------------------
# Winner picker
# -------------------------------------------------------------------------


def test_pick_winner_prefers_highest_minor_recall():
    def _s(size, minor_recall, cost, prov=0.9):
        return {
            "entity_recall_minor": {"recall": minor_recall},
            "provenance_pass_rate": {"rate": prov},
            "extra": {"chunk_size": size, "cost_usd": cost},
        }

    summaries = [
        _s(1500, 0.50, 1.00),
        _s(1000, 0.70, 1.20),
        _s(750,  0.80, 1.40),
        _s(500,  0.90, 3.00),  # above 1.5x baseline cost — excluded
    ]
    winner = pick_winner(summaries)
    assert winner["extra"]["chunk_size"] == 750


def test_pick_winner_excludes_low_provenance():
    def _s(size, minor_recall, cost, prov):
        return {
            "entity_recall_minor": {"recall": minor_recall},
            "provenance_pass_rate": {"rate": prov},
            "extra": {"chunk_size": size, "cost_usd": cost},
        }

    summaries = [
        _s(1500, 0.50, 1.00, 0.95),
        _s(750,  0.90, 1.40, 0.70),  # high recall but provenance < 0.80
    ]
    winner = pick_winner(summaries)
    assert winner["extra"]["chunk_size"] == 1500


def test_pick_winner_none_when_no_candidate_qualifies():
    summaries = [
        {
            "entity_recall_minor": {"recall": 0.9},
            "provenance_pass_rate": {"rate": 0.5},
            "extra": {"chunk_size": 750, "cost_usd": 5.0},
        },
    ]
    assert pick_winner(summaries) is None


def test_pick_winner_handles_empty_list():
    assert pick_winner([]) is None


def test_pick_winner_requires_cost_field():
    summaries = [{
        "entity_recall_minor": {"recall": 1.0},
        "provenance_pass_rate": {"rate": 1.0},
        "extra": {"chunk_size": 750},  # no cost_usd
    }]
    assert pick_winner(summaries) is None


# -------------------------------------------------------------------------
# Gold file loading — smoke test on the shipped Christmas Carol gold
# -------------------------------------------------------------------------


def test_shipped_christmas_carol_gold_loads():
    path = Path(__file__).parent / "golds" / "christmas_carol_gold.json"
    gold = load_gold(path)
    assert gold["book_id"] == "christmas_carol"
    # Must have at least Scrooge, Bob Cratchit, Fred
    names = {c["name"] for c in gold["characters"]}
    assert {"Scrooge", "Bob Cratchit", "Fred", "Tiny Tim"}.issubset(names)
    assert any(c["tier"] == "minor" for c in gold["characters"])
    assert len(gold["relationships"]) >= 5
