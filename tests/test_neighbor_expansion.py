"""Phase A Stage 4 / Item 10 — expand_neighbors helper."""
from __future__ import annotations

import pytest


def _rel(src: str, tgt: str, rt: str = "ally") -> dict:
    return {
        "source_name": src, "target_name": tgt, "relation_type": rt,
        "_type": "Relationship",
    }


def test_empty_seeds_returns_empty_set():
    from pipeline.spoiler_filter import expand_neighbors
    assert expand_neighbors(set(), [_rel("A", "B")]) == set()


def test_seed_with_no_relationships_returns_just_seed():
    from pipeline.spoiler_filter import expand_neighbors
    assert expand_neighbors({"Scrooge"}, []) == {"Scrooge"}


def test_single_seed_expands_to_one_hop():
    from pipeline.spoiler_filter import expand_neighbors
    rels = [
        _rel("Scrooge", "Marley"),
        _rel("Scrooge", "Fred"),
        _rel("Scrooge", "Bob Cratchit"),
    ]
    result = expand_neighbors({"Scrooge"}, rels)
    assert result == {"Scrooge", "Marley", "Fred", "Bob Cratchit"}


def test_seed_expansion_is_undirected():
    """source OR target match should expand the neighbor on the other side."""
    from pipeline.spoiler_filter import expand_neighbors
    rels = [_rel("Fred", "Scrooge")]  # Scrooge is target
    result = expand_neighbors({"Scrooge"}, rels)
    assert result == {"Scrooge", "Fred"}


def test_self_loops_ignored():
    from pipeline.spoiler_filter import expand_neighbors
    rels = [_rel("Scrooge", "Scrooge"), _rel("Scrooge", "Fred")]
    assert expand_neighbors({"Scrooge"}, rels) == {"Scrooge", "Fred"}


def test_multiple_seeds_union_no_duplicates():
    from pipeline.spoiler_filter import expand_neighbors
    rels = [
        _rel("Scrooge", "Fred"),
        _rel("Bob Cratchit", "Fred"),  # Fred is neighbor of both seeds
    ]
    result = expand_neighbors({"Scrooge", "Bob Cratchit"}, rels)
    assert result == {"Scrooge", "Bob Cratchit", "Fred"}


def test_hub_seed_not_expanded():
    """A seed with fan > degree_cap keeps itself but expansion is skipped."""
    from pipeline.spoiler_filter import expand_neighbors
    rels = [_rel("Hub", f"N{i}") for i in range(60)]
    result = expand_neighbors({"Hub"}, rels, degree_cap=50)
    assert result == {"Hub"}


def test_below_degree_cap_still_expands():
    from pipeline.spoiler_filter import expand_neighbors
    rels = [_rel("X", f"N{i}") for i in range(5)]
    result = expand_neighbors({"X"}, rels, degree_cap=50)
    assert result == {"X", "N0", "N1", "N2", "N3", "N4"}


def test_max_result_caps_total():
    from pipeline.spoiler_filter import expand_neighbors
    rels = [_rel("X", f"N{i}") for i in range(100)]
    result = expand_neighbors({"X"}, rels, degree_cap=1000, max_result=5)
    assert len(result) == 5
    assert "X" in result  # seed preserved under cap


def test_endpoint_name_from_nested_shape():
    """relationships may serialize as {source: {name:X}, target: {name:Y}}."""
    from pipeline.spoiler_filter import expand_neighbors
    rels = [{
        "source": {"name": "Scrooge"},
        "target": {"name": "Marley"},
        "_type": "Relationship",
    }]
    result = expand_neighbors({"Scrooge"}, rels)
    assert result == {"Scrooge", "Marley"}
