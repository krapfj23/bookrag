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


class TestLoadAllowedRelationships:
    """A Relationship is only visible to the reader when BOTH endpoints are
    already visible (entity-level chapter filter passes) AND the relationship's
    own chapter is <= cursor."""

    def _write_batch(self, tmp_path, book_id, name, payload):
        batch_dir = tmp_path / book_id / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / name).write_text(json.dumps(payload))

    def test_returns_relationship_when_both_endpoints_allowed(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_relationships

        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                {"name": "Scrooge", "first_chapter": 1, "last_known_chapter": 1},
                {"name": "Marley", "first_chapter": 1, "last_known_chapter": 1},
            ],
            "relationships": [
                {
                    "source_name": "Scrooge",
                    "target_name": "Marley",
                    "relation_type": "business partner of",
                    "description": "Long-time partners",
                    "chapter": 1,
                    "first_chapter": 1,
                    "last_known_chapter": 1,
                },
            ],
        })
        rels = load_allowed_relationships("bk", cursor=3, processed_dir=tmp_path)
        assert len(rels) == 1
        assert rels[0]["source_name"] == "Scrooge"
        assert rels[0]["target_name"] == "Marley"

    def test_drops_relationship_when_source_is_unseen(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_relationships

        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                # Source appears in ch.5 — reader is on ch.3, so Scrooge unseen
                {"name": "Scrooge", "first_chapter": 5, "last_known_chapter": 5},
                {"name": "Marley", "first_chapter": 1, "last_known_chapter": 1},
            ],
            "relationships": [
                {
                    "source_name": "Scrooge",
                    "target_name": "Marley",
                    "relation_type": "business partner of",
                    "chapter": 1,
                    "first_chapter": 1,
                    "last_known_chapter": 1,
                },
            ],
        })
        rels = load_allowed_relationships("bk", cursor=3, processed_dir=tmp_path)
        assert rels == []

    def test_drops_relationship_when_target_is_unseen(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_relationships

        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                {"name": "Scrooge", "first_chapter": 1, "last_known_chapter": 1},
                {"name": "GhostOfFuture", "first_chapter": 4, "last_known_chapter": 4},
            ],
            "relationships": [
                {
                    "source_name": "Scrooge",
                    "target_name": "GhostOfFuture",
                    "relation_type": "haunted by",
                    "chapter": 1,
                    "first_chapter": 1,
                    "last_known_chapter": 1,
                },
            ],
        })
        rels = load_allowed_relationships("bk", cursor=3, processed_dir=tmp_path)
        assert rels == []

    def test_drops_relationship_when_relationship_chapter_is_future(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_relationships

        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                {"name": "Scrooge", "first_chapter": 1, "last_known_chapter": 1},
                {"name": "Marley", "first_chapter": 1, "last_known_chapter": 1},
            ],
            "relationships": [
                {
                    "source_name": "Scrooge",
                    "target_name": "Marley",
                    "relation_type": "remembers fondly",
                    "chapter": 7,  # past the reader's cursor
                    "first_chapter": 7,
                    "last_known_chapter": 7,
                },
            ],
        })
        rels = load_allowed_relationships("bk", cursor=3, processed_dir=tmp_path)
        assert rels == []

    def test_reuses_precomputed_allowed_nodes_when_passed(self, tmp_path):
        """Callers can pass a pre-computed allowlist to skip the extra walk."""
        from pipeline.spoiler_filter import load_allowed_relationships

        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                {"name": "A", "first_chapter": 1, "last_known_chapter": 1},
                {"name": "B", "first_chapter": 1, "last_known_chapter": 1},
            ],
            "relationships": [
                {
                    "source_name": "A",
                    "target_name": "B",
                    "relation_type": "knows",
                    "chapter": 1,
                    "first_chapter": 1,
                    "last_known_chapter": 1,
                },
            ],
        })
        # Pre-computed allowed nodes (simulates caller already did load_allowed_nodes)
        allowed_nodes = [
            {"_type": "Character", "name": "A", "first_chapter": 1, "last_known_chapter": 1},
            {"_type": "Character", "name": "B", "first_chapter": 1, "last_known_chapter": 1},
        ]
        rels = load_allowed_relationships(
            "bk", cursor=3, processed_dir=tmp_path, allowed_nodes=allowed_nodes
        )
        assert len(rels) == 1

    def test_nested_endpoint_shape_is_supported(self, tmp_path):
        """Cognee's DataPoint serialization stores relationship endpoints as
        nested {name: ..., first_chapter: ...} dicts under source/target,
        not flat source_name/target_name strings. Both must work."""
        from pipeline.spoiler_filter import load_allowed_relationships

        batch_dir = tmp_path / "bk" / "batches" / "batch_01"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "extracted_datapoints.json").write_text(json.dumps([
            {"type": "Character", "name": "Scrooge", "first_chapter": 1, "last_known_chapter": 1},
            {"type": "Character", "name": "Marley", "first_chapter": 1, "last_known_chapter": 1},
            {
                "type": "Relationship",
                "source": {"type": "Character", "name": "Scrooge", "first_chapter": 1},
                "target": {"type": "Character", "name": "Marley", "first_chapter": 1},
                "relation_type": "business partner of",
                "description": "Long-time partners",
                # Note: no top-level chapter/first_chapter — must derive from endpoints
            },
        ]))
        rels = load_allowed_relationships("bk", cursor=3, processed_dir=tmp_path)
        assert len(rels) == 1
        rel = rels[0]
        # Normalization: flat names are attached even when source is nested
        assert rel["source_name"] == "Scrooge"
        assert rel["target_name"] == "Marley"
        assert rel["chapter"] == 1  # derived from max(source, target) first_chapter

    def test_nested_shape_drops_when_target_first_chapter_exceeds_cursor(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_relationships

        batch_dir = tmp_path / "bk" / "batches" / "batch_01"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "extracted_datapoints.json").write_text(json.dumps([
            {"type": "Character", "name": "Scrooge", "first_chapter": 1, "last_known_chapter": 1},
            # Future character only in ch 5
            {"type": "Character", "name": "Future", "first_chapter": 5, "last_known_chapter": 5},
            {
                "type": "Relationship",
                "source": {"name": "Scrooge", "first_chapter": 1},
                "target": {"name": "Future", "first_chapter": 5},
                "relation_type": "haunted by",
            },
        ]))
        rels = load_allowed_relationships("bk", cursor=2, processed_dir=tmp_path)
        assert rels == []

    def test_flat_list_shape_is_also_supported(self, tmp_path):
        """Current pipeline output uses batches/batch_NN/extracted_datapoints.json
        as a flat list with a `type` field; the relationship filter must handle
        both shapes just like load_allowed_nodes does."""
        from pipeline.spoiler_filter import load_allowed_relationships

        batch_dir = tmp_path / "bk" / "batches" / "batch_01"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "extracted_datapoints.json").write_text(json.dumps([
            {"type": "Character", "name": "Scrooge", "first_chapter": 1, "last_known_chapter": 1},
            {"type": "Character", "name": "Marley", "first_chapter": 1, "last_known_chapter": 1},
            {
                "type": "Relationship",
                "source_name": "Scrooge",
                "target_name": "Marley",
                "relation_type": "partner",
                "chapter": 1,
                "first_chapter": 1,
                "last_known_chapter": 1,
            },
        ]))
        rels = load_allowed_relationships("bk", cursor=3, processed_dir=tmp_path)
        assert len(rels) == 1
        assert rels[0]["relation_type"] == "partner"
