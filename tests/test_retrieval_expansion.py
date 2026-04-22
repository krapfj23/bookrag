"""Phase A Stage 4 / Item 10 — keyword_rank_results + two-hop expansion.

Integration tests for the retrieval-side neighbor expansion: keyword rank
picks seeds, expand_neighbors pulls in 1-hop graph neighbors, expansion
cap trims the final list.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _write_batch(tmp_path: Path, book_id: str, datapoints: list[dict]):
    d = tmp_path / book_id / "batches" / "batch_01"
    d.mkdir(parents=True, exist_ok=True)
    (d / "extracted_datapoints.json").write_text(json.dumps(datapoints))


def _char(name: str, desc: str = "", ch: int = 1) -> dict:
    return {
        "type": "Character", "name": name, "description": desc,
        "first_chapter": ch, "last_known_chapter": ch,
    }


def _rel(src: str, tgt: str, rt: str = "family", ch: int = 1) -> dict:
    return {
        "type": "Relationship",
        "source": {"name": src, "first_chapter": ch},
        "target": {"name": tgt, "first_chapter": ch},
        "relation_type": rt,
        "first_chapter": ch, "last_known_chapter": ch,
    }


@pytest.fixture
def book_with_cratchit_family(tmp_path):
    """Bob Cratchit has keyword 'dinner' in description; his family members do not."""
    _write_batch(tmp_path, "carol", [
        _char("Bob Cratchit", desc="prepares the Christmas dinner for his family"),
        _char("Mrs. Cratchit", desc="wife"),
        _char("Tiny Tim", desc="youngest son"),
        _char("Martha Cratchit", desc="eldest daughter"),
        _char("Unrelated Noodle", desc="a stranger"),
        _rel("Bob Cratchit", "Mrs. Cratchit"),
        _rel("Bob Cratchit", "Tiny Tim"),
        _rel("Bob Cratchit", "Martha Cratchit"),
    ])
    return tmp_path


@pytest.fixture
def enable_expansion(monkeypatch):
    """Force retrieval_expand_neighbors=True regardless of loaded config."""
    class _Cfg:
        retrieval_expand_neighbors = True
        retrieval_seed_count = 5
        retrieval_expansion_cap = 20

    monkeypatch.setattr("api.query.synthesis.load_config", lambda: _Cfg(), raising=False)
    # Fall back path: patch models.config.load_config too, since the helper
    # imports it lazily.
    import models.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load_config", lambda: _Cfg())


@pytest.fixture
def disable_expansion(monkeypatch):
    class _Cfg:
        retrieval_expand_neighbors = False
        retrieval_seed_count = 5
        retrieval_expansion_cap = 20

    import models.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load_config", lambda: _Cfg())


def test_expansion_disabled_returns_keyword_hits_only(book_with_cratchit_family, disable_expansion):
    from api.query.synthesis import answer_from_allowed_nodes

    results = answer_from_allowed_nodes(
        book_id="carol", question="dinner",
        graph_max_chapter=5, processed_dir=book_with_cratchit_family,
    )
    names = [item.content.split(" — ", 1)[0] for item in results]
    # Only Bob Cratchit mentions 'dinner' in description
    assert names == ["Bob Cratchit"]


def test_expansion_enabled_surfaces_1_hop_neighbors(book_with_cratchit_family, enable_expansion):
    from api.query.synthesis import answer_from_allowed_nodes

    results = answer_from_allowed_nodes(
        book_id="carol", question="dinner",
        graph_max_chapter=5, processed_dir=book_with_cratchit_family,
    )
    names = [item.content.split(" — ", 1)[0] for item in results]

    # Bob is the keyword seed, keeps first position
    assert names[0] == "Bob Cratchit"
    # Family members appear via 1-hop expansion
    assert "Mrs. Cratchit" in names
    assert "Tiny Tim" in names
    assert "Martha Cratchit" in names
    # Unrelated character NOT surfaced (not a neighbor)
    assert "Unrelated Noodle" not in names


def test_expansion_preserves_keyword_hit_at_top(book_with_cratchit_family, enable_expansion):
    """Neighbors should rank below keyword-matched entities."""
    from api.query.synthesis import answer_from_allowed_nodes

    results = answer_from_allowed_nodes(
        book_id="carol", question="dinner",
        graph_max_chapter=5, processed_dir=book_with_cratchit_family,
    )
    # First item = keyword hit; subsequent items = expanded neighbors
    assert results[0].content.startswith("Bob Cratchit")


def test_expansion_respects_cap(tmp_path, monkeypatch):
    """retrieval_expansion_cap trims the final list."""
    # 10 family members
    dps = [_char("Parent", desc="head of family")]
    for i in range(10):
        dps.append(_char(f"Child{i}"))
        dps.append(_rel("Parent", f"Child{i}"))
    _write_batch(tmp_path, "big", dps)

    class _Cfg:
        retrieval_expand_neighbors = True
        retrieval_seed_count = 5
        retrieval_expansion_cap = 3

    import models.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load_config", lambda: _Cfg())

    from api.query.synthesis import answer_from_allowed_nodes
    results = answer_from_allowed_nodes(
        book_id="big", question="family",
        graph_max_chapter=5, processed_dir=tmp_path,
    )
    # cap = 3: Parent + 2 children
    assert len(results) == 3


def test_expansion_returns_empty_when_no_seeds(tmp_path, enable_expansion):
    """Question with no keyword matches means no seeds means empty result."""
    from api.query.synthesis import answer_from_allowed_nodes

    _write_batch(tmp_path, "empty", [
        _char("Alice"),
        _rel("Alice", "Bob"),
    ])
    results = answer_from_allowed_nodes(
        book_id="empty", question="zzz_nothing_matches",
        graph_max_chapter=5, processed_dir=tmp_path,
    )
    assert results == []
