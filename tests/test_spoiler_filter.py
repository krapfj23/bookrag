"""Tests for pipeline/spoiler_filter.py — chapter filtering primitives."""

import pytest


class TestEffectiveLatestChapter:
    """effective_latest_chapter returns the greatest chapter value a node 'knows about'."""

    def test_uses_last_known_when_greater_than_first(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 1, "last_known_chapter": 5}
        assert effective_latest_chapter(node) == 5

    def test_uses_first_when_last_known_missing(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 3}
        assert effective_latest_chapter(node) == 3

    def test_uses_chapter_for_plot_events(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"chapter": 7}
        assert effective_latest_chapter(node) == 7

    def test_returns_none_when_no_chapter_info(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        assert effective_latest_chapter({}) is None

    def test_accepts_pydantic_like_object(self):
        from pipeline.spoiler_filter import effective_latest_chapter

        class Fake:
            first_chapter = 1
            last_known_chapter = 4

        assert effective_latest_chapter(Fake()) == 4

    def test_max_across_all_fields(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 1, "chapter": 9, "last_known_chapter": 3}
        assert effective_latest_chapter(node) == 9


import json
from pathlib import Path


class TestLoadAllowedNodes:
    """load_allowed_nodes walks batches/*.json and returns only nodes visible at cursor."""

    def _write_batch(self, tmp_path: Path, name: str, payload: dict):
        batch_dir = tmp_path / "book-1" / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / name).write_text(json.dumps(payload))

    def test_filters_by_cursor(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes

        self._write_batch(tmp_path, "batch_01.json", {
            "characters": [
                {"id": "c1", "name": "Early", "first_chapter": 1, "last_known_chapter": 2},
                {"id": "c2", "name": "Late",  "first_chapter": 1, "last_known_chapter": 8},
            ],
            "events": [
                {"id": "e1", "description": "ev", "chapter": 1},
                {"id": "e2", "description": "ev", "chapter": 9},
            ],
        })

        allowed = load_allowed_nodes("book-1", cursor=3, processed_dir=tmp_path)

        ids = {n["id"] for n in allowed}
        assert ids == {"c1", "e1"}, f"got {ids}"

    def test_empty_when_no_batches(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        assert load_allowed_nodes("nonexistent", cursor=10, processed_dir=tmp_path) == []

    def test_merges_multiple_batches(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "batch_01.json", {
            "characters": [{"id": "a", "name": "A", "first_chapter": 1, "last_known_chapter": 1}],
        })
        self._write_batch(tmp_path, "batch_02.json", {
            "characters": [{"id": "b", "name": "B", "first_chapter": 4, "last_known_chapter": 4}],
        })
        allowed = load_allowed_nodes("book-1", cursor=5, processed_dir=tmp_path)
        assert {n["id"] for n in allowed} == {"a", "b"}


class TestIdentityKey:
    """_identity_key groups nodes by stable identity regardless of which batch they came from."""

    def test_character_keyed_by_name(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "Character", "name": "Scrooge", "last_known_chapter": 1}
        b = {"_type": "Character", "name": "Scrooge", "last_known_chapter": 5}
        assert _identity_key(a) == _identity_key(b)

    def test_different_names_different_keys(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "Character", "name": "Scrooge"}
        b = {"_type": "Character", "name": "Marley"}
        assert _identity_key(a) != _identity_key(b)

    def test_same_name_different_type_different_keys(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "Character", "name": "London"}
        b = {"_type": "Location", "name": "London"}
        assert _identity_key(a) != _identity_key(b)

    def test_plotevent_keyed_by_chapter_and_description(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "PlotEvent", "chapter": 2, "description": "Scrooge meets Marley's ghost"}
        b = {"_type": "PlotEvent", "chapter": 2, "description": "Scrooge meets Marley's ghost"}
        c = {"_type": "PlotEvent", "chapter": 2, "description": "Different event"}
        assert _identity_key(a) == _identity_key(b)
        assert _identity_key(a) != _identity_key(c)


class TestLoadAllowedNodesDedup:
    """When the same identity appears in multiple batches, return the latest allowed snapshot."""

    def _write_batch(self, tmp_path, book_id, name, payload):
        batch_dir = tmp_path / book_id / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / name).write_text(json.dumps(payload))

    def test_takes_latest_snapshot_within_bound(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [{"name": "Scrooge", "description": "a miser",
                            "first_chapter": 1, "last_known_chapter": 1}],
        })
        self._write_batch(tmp_path, "bk", "b2.json", {
            "characters": [{"name": "Scrooge", "description": "a miser haunted by Marley",
                            "first_chapter": 1, "last_known_chapter": 3}],
        })
        self._write_batch(tmp_path, "bk", "b3.json", {
            "characters": [{"name": "Scrooge", "description": "a reformed miser",
                            "first_chapter": 1, "last_known_chapter": 5}],
        })

        allowed = load_allowed_nodes("bk", cursor=2, processed_dir=tmp_path)
        assert len(allowed) == 1
        assert allowed[0]["description"] == "a miser"

        allowed = load_allowed_nodes("bk", cursor=4, processed_dir=tmp_path)
        assert len(allowed) == 1
        assert allowed[0]["description"] == "a miser haunted by Marley"

        allowed = load_allowed_nodes("bk", cursor=9, processed_dir=tmp_path)
        assert len(allowed) == 1
        assert allowed[0]["description"] == "a reformed miser"

    def test_distinct_entities_all_return(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                {"name": "Scrooge", "description": "miser", "first_chapter": 1, "last_known_chapter": 1},
                {"name": "Marley", "description": "ghost", "first_chapter": 1, "last_known_chapter": 1},
            ],
        })
        allowed = load_allowed_nodes("bk", cursor=5, processed_dir=tmp_path)
        names = {n["name"] for n in allowed}
        assert names == {"Scrooge", "Marley"}

    def test_plot_events_not_deduped_across_chapters(self, tmp_path):
        """Identical event descriptions in different chapters are distinct."""
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "bk", "b1.json", {
            "events": [
                {"description": "Scrooge wakes", "chapter": 1},
                {"description": "Scrooge wakes", "chapter": 4},
            ],
        })
        allowed = load_allowed_nodes("bk", cursor=5, processed_dir=tmp_path)
        assert len(allowed) == 2
