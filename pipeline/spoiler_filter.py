"""Spoiler filtering primitives for the BookRAG query path.

Every temporally-scoped entity in the graph has one or more chapter-like
fields. `effective_latest_chapter` collapses them into a single "this node
becomes visible at chapter N" value used for pre-filtering retrieval.
"""

from __future__ import annotations

from typing import Any

_CHAPTER_FIELDS = ("first_chapter", "last_known_chapter", "chapter")


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def effective_latest_chapter(obj: Any) -> int | None:
    """Return the largest chapter number this node depends on, or None.

    Considers first_chapter, last_known_chapter, and chapter (PlotEvent).
    A node is only safe to show a reader whose progress is >= this value.
    """
    values = [_get(obj, f) for f in _CHAPTER_FIELDS]
    ints = [int(v) for v in values if v is not None]
    return max(ints) if ints else None


import json
from pathlib import Path

# Every key in a batch JSON file that holds temporally-scoped nodes.
# Values are the node-type label we attach when merging.
_NODE_COLLECTIONS = {
    "characters": "Character",
    "locations": "Location",
    "factions": "Faction",
    "themes": "Theme",
    "events": "PlotEvent",
    "relationships": "Relationship",
}


def _load_allowed_nodes_by_chapter_legacy(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
    realis_filter: bool = True,
) -> list[dict]:
    """Return the latest per-identity snapshot visible at `cursor`.

    Walks every batch JSON under {processed_dir}/{book_id}/batches/. For each
    node whose effective_latest_chapter <= cursor, keeps only the one with
    the greatest effective_latest_chapter per identity key (see _identity_key).

    Supports BOTH on-disk shapes:
      1. Collection-keyed: batches/*.json with {"characters": [...], ...}
      2. Current pipeline:  batches/batch_NN/extracted_datapoints.json as a
         flat list with a "type" field per item.

    Missing book directory returns []. Nodes with no chapter info are dropped.
    ``realis_filter`` (default True, Item 9 Phase A Stage 2) drops
    PlotEvent nodes whose realis is not "actual".
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    latest: dict[tuple, tuple[int, dict]] = {}

    def _merge(enriched: dict) -> None:
        ch = effective_latest_chapter(enriched)
        if ch is None or ch > cursor:
            return
        if realis_filter and enriched.get("_type") == "PlotEvent":
            realis = enriched.get("realis", "actual")
            if realis != "actual":
                return
        key = _identity_key(enriched)
        prev = latest.get(key)
        if prev is None or ch > prev[0]:
            latest[key] = (ch, enriched)

    # Shape 1: collection-keyed top-level batch files
    for batch_file in sorted(batches_dir.glob("*.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for collection, type_label in _NODE_COLLECTIONS.items():
            for node in payload.get(collection, []) or []:
                enriched = dict(node)
                enriched["_type"] = type_label
                _merge(enriched)

    # Shape 2: per-batch subdirectories with extracted_datapoints.json
    for dp_file in sorted(batches_dir.glob("batch_*/extracted_datapoints.json")):
        try:
            payload = json.loads(dp_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = payload if isinstance(payload, list) else payload.get("datapoints", [])
        for node in items:
            if not isinstance(node, dict):
                continue
            enriched = dict(node)
            # Prefer explicit type; fall back to __type__ or "Entity"
            enriched["_type"] = enriched.get("type") or enriched.get("__type__") or "Entity"
            _merge(enriched)

    return [node for _, node in latest.values()]


def _relationship_endpoint_name(rel: dict, field: str) -> str | None:
    """Extract a relationship endpoint's name from either the flat or nested shape.

    Flat (our test fixtures): {"source_name": "Scrooge", ...}
    Nested (Cognee DataPoint serialization): {"source": {"name": "Scrooge", ...}}
    """
    flat = rel.get(f"{field}_name")
    if flat:
        return flat
    nested = rel.get(field)
    if isinstance(nested, dict):
        return nested.get("name")
    return None


def _relationship_endpoint_first_chapter(rel: dict, field: str) -> int | None:
    """Return the first_chapter of an endpoint when available (nested shape only)."""
    nested = rel.get(field)
    if isinstance(nested, dict):
        v = nested.get("first_chapter")
        if v is not None:
            return int(v)
    return None


def _relationship_effective_chapter(rel: dict) -> int | None:
    """Return the chapter at which this relationship becomes visible.

    Prefer the relationship's own chapter fields (first_chapter, chapter,
    last_known_chapter). Fall back to the later of the two endpoints'
    first_chapter values (a relationship is only meaningful once both
    endpoints exist).
    """
    own = effective_latest_chapter(rel)
    if own is not None:
        return own
    src_ch = _relationship_endpoint_first_chapter(rel, "source")
    tgt_ch = _relationship_endpoint_first_chapter(rel, "target")
    if src_ch is None or tgt_ch is None:
        return None
    return max(src_ch, tgt_ch)


def expand_neighbors(
    seed_names: set[str],
    relationships: list[dict],
    degree_cap: int = 50,
    max_result: int = 20,
) -> set[str]:
    """Return seed names ∪ 1-hop neighbors via the given relationships.

    Item 10 (Phase A Stage 4): surfaces peripheral entities that are
    connected to keyword-matched seeds but don't themselves match the
    query words. Lets a question like "what happens at dinner?" pull in
    family members of the Cratchit found via the keyword pass.

    Args:
        seed_names: Entity names to expand from.
        relationships: Relationship dicts with source_name/target_name
            fields (either flat or nested — ``_relationship_endpoint_name``
            handles both shapes).
        degree_cap: Seeds whose 1-hop fan exceeds this are kept as seeds
            but NOT expanded (prevents hub blow-up).
        max_result: Final result cap. Seeds win over neighbors when the
            cap trims.

    Returns:
        Set of names including all seeds and their non-hub 1-hop neighbors.
    """
    if not seed_names:
        return set()

    neighbor_counts: dict[str, int] = {name: 0 for name in seed_names}
    edges_by_seed: dict[str, list[str]] = {name: [] for name in seed_names}

    for rel in relationships:
        src = _relationship_endpoint_name(rel, "source")
        tgt = _relationship_endpoint_name(rel, "target")
        if not src or not tgt or src == tgt:
            continue
        for seed, other in ((src, tgt), (tgt, src)):
            if seed in seed_names:
                neighbor_counts[seed] += 1
                edges_by_seed[seed].append(other)

    result: list[str] = []
    seen: set[str] = set()
    for name in seed_names:
        if name not in seen:
            result.append(name)
            seen.add(name)

    for seed in seed_names:
        if neighbor_counts[seed] > degree_cap:
            continue
        for other in edges_by_seed[seed]:
            if other not in seen:
                result.append(other)
                seen.add(other)
                if len(result) >= max_result:
                    return set(result)

    return set(result[:max_result])


def load_allowed_relationships(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
    allowed_nodes: list[dict] | None = None,
) -> list[dict]:
    """Return Relationship DataPoints where BOTH endpoints are visible to the reader.

    The spoiler rule:
      - The relationship's effective chapter must be <= cursor, where
        effective chapter is the relationship's own chapter if present,
        otherwise max(source.first_chapter, target.first_chapter).
      - Both endpoint names must exist in the allowed-node set for this
        book + cursor.

    Supports both on-disk shapes:
      * Collection-keyed: batches/*.json with {"relationships": [...]}
      * Flat-list:        batches/batch_NN/extracted_datapoints.json

    And both relationship field shapes:
      * Flat:   {"source_name": "X", "target_name": "Y"}
      * Nested: {"source": {"name": "X"}, "target": {"name": "Y"}}

    Callers that have already computed the allowed nodes can pass them in
    via ``allowed_nodes`` to skip the extra walk.
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    if allowed_nodes is None:
        allowed_nodes = load_allowed_nodes(book_id, cursor, processed_dir)

    allowed_names: set[str] = {
        n.get("name", "")
        for n in allowed_nodes
        if n.get("name") and n.get("_type") != "Relationship"
    }

    latest: dict[tuple, tuple[int, dict]] = {}

    def _consider(rel: dict) -> None:
        ch = _relationship_effective_chapter(rel)
        if ch is None or ch > cursor:
            return
        src = _relationship_endpoint_name(rel, "source")
        tgt = _relationship_endpoint_name(rel, "target")
        if not src or not tgt:
            return
        if src not in allowed_names or tgt not in allowed_names:
            return
        # Normalize to the flat shape so downstream code sees a single
        # consistent payload regardless of serialization origin.
        enriched = dict(rel)
        enriched["_type"] = "Relationship"
        enriched["source_name"] = src
        enriched["target_name"] = tgt
        if "chapter" not in enriched or enriched["chapter"] is None:
            enriched["chapter"] = ch
        key = _identity_key(enriched)
        prev = latest.get(key)
        if prev is None or ch > prev[0]:
            latest[key] = (ch, enriched)

    # Shape 1: collection-keyed top-level batch files
    for batch_file in sorted(batches_dir.glob("*.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for rel in payload.get("relationships", []) or []:
            _consider(rel)

    # Shape 2: flat-list extracted_datapoints.json per batch subdir
    for dp_file in sorted(batches_dir.glob("batch_*/extracted_datapoints.json")):
        try:
            payload = json.loads(dp_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = payload if isinstance(payload, list) else payload.get("datapoints", [])
        for node in items:
            if isinstance(node, dict) and node.get("type") == "Relationship":
                _consider(node)

    return [rel for _, rel in latest.values()]


def _identity_key(node: dict) -> tuple:
    """Return a stable identity tuple for grouping snapshots of the same entity.

    - Named entities (Character/Location/Faction/Theme): (type, name)
    - Relationships: (type, source_name, relation_type, target_name)
    - PlotEvents: (type, chapter, description) — events are inherently tied to a
      moment; we key by chapter + description to let identical events in
      different chapters remain distinct.
    """
    t = node.get("_type", "")
    if t == "Relationship":
        return (t, node.get("source_name", ""), node.get("relation_type", ""), node.get("target_name", ""))
    if t == "PlotEvent":
        return (t, node.get("chapter"), node.get("description", ""))
    return (t, node.get("name", ""))


def _effective_ordinal(node: dict, book_id: str, processed_dir: Path | str) -> int | None:
    """Return the node's source_chunk_ordinal, or — if missing — the last ordinal
    of the chapter derived from effective_latest_chapter. None if neither works.
    """
    ord_val = node.get("source_chunk_ordinal")
    if ord_val is not None:
        return int(ord_val)
    ch = effective_latest_chapter(node)
    if ch is None:
        return None
    # Import here to avoid circular imports at module load.
    from pipeline.chunk_index import load_chapter_index
    idx = load_chapter_index(book_id, processed_dir)
    entry = idx.get(str(ch))
    if entry is None:
        return None
    return int(entry["last_ordinal"])


def load_allowed_nodes_by_chunk(
    book_id: str,
    chunk_ordinal_cursor: int,
    processed_dir: Path | str,
    realis_filter: bool = True,
) -> list[dict]:
    """Ordinal-based variant of load_allowed_nodes.

    Keeps the latest per-identity snapshot whose source_chunk_ordinal
    (or chapter-fallback ordinal) <= cursor.

    When ``realis_filter`` is True (default, Item 9 Phase A Stage 2),
    PlotEvent nodes whose ``realis`` field is not ``"actual"`` are dropped
    from the result — canonical retrieval shouldn't surface hypothetical
    or counterfactual events as facts. Pre-Phase-A PlotEvents without a
    realis field pass through (they predate the field and are assumed
    actual in legacy data).
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    latest: dict[tuple, tuple[int, dict]] = {}

    def _merge(enriched: dict) -> None:
        ord_ = _effective_ordinal(enriched, book_id, processed_dir)
        if ord_ is None or ord_ > chunk_ordinal_cursor:
            return
        if realis_filter and enriched.get("_type") == "PlotEvent":
            realis = enriched.get("realis", "actual")
            if realis != "actual":
                return
        key = _identity_key(enriched)
        prev = latest.get(key)
        if prev is None or ord_ > prev[0]:
            latest[key] = (ord_, enriched)

    for batch_file in sorted(batches_dir.glob("*.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for collection, type_label in _NODE_COLLECTIONS.items():
            for node in payload.get(collection, []) or []:
                enriched = dict(node)
                enriched["_type"] = type_label
                _merge(enriched)

    for dp_file in sorted(batches_dir.glob("batch_*/extracted_datapoints.json")):
        try:
            payload = json.loads(dp_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = payload if isinstance(payload, list) else payload.get("datapoints", [])
        for node in items:
            if not isinstance(node, dict):
                continue
            enriched = dict(node)
            enriched["_type"] = enriched.get("type") or enriched.get("__type__") or "Entity"
            _merge(enriched)

    return [node for _, node in latest.values()]


def load_allowed_nodes(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
    realis_filter: bool = True,
) -> list[dict]:
    """Chapter-cursor variant. Delegates to load_allowed_nodes_by_chunk when
    the chunk index is present; otherwise falls back to the legacy
    chapter-based walk.

    ``realis_filter`` (default True) drops PlotEvent nodes whose ``realis``
    is not ``"actual"`` — see load_allowed_nodes_by_chunk for detail.
    """
    from pipeline.chunk_index import load_chapter_index
    idx = load_chapter_index(book_id, processed_dir)
    if idx:
        entry = idx.get(str(cursor))
        if entry is not None:
            return load_allowed_nodes_by_chunk(
                book_id=book_id,
                chunk_ordinal_cursor=entry["last_ordinal"],
                processed_dir=processed_dir,
                realis_filter=realis_filter,
            )
        # Chapter not in index — find the largest indexed chapter <= cursor
        prior = [int(v["last_ordinal"]) for k, v in idx.items() if int(k) <= cursor]
        if prior:
            return load_allowed_nodes_by_chunk(
                book_id=book_id,
                chunk_ordinal_cursor=max(prior),
                processed_dir=processed_dir,
                realis_filter=realis_filter,
            )
        return []

    # Legacy path: no chunk index, walk batches and compare by chapter
    return _load_allowed_nodes_by_chapter_legacy(
        book_id, cursor, processed_dir, realis_filter=realis_filter,
    )
