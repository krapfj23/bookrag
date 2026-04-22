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


def load_allowed_nodes(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
) -> list[dict]:
    """Return the latest per-identity snapshot visible at `cursor`.

    Walks every batch JSON under {processed_dir}/{book_id}/batches/. For each
    node whose effective_latest_chapter <= cursor, keeps only the one with
    the greatest effective_latest_chapter per identity key (see _identity_key).

    Missing book directory returns []. Nodes with no chapter info are dropped.
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    latest: dict[tuple, tuple[int, dict]] = {}

    for batch_file in sorted(batches_dir.glob("*.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for collection, type_label in _NODE_COLLECTIONS.items():
            for node in payload.get(collection, []) or []:
                ch = effective_latest_chapter(node)
                if ch is None or ch > cursor:
                    continue
                enriched = dict(node)
                enriched["_type"] = type_label
                key = _identity_key(enriched)
                prev = latest.get(key)
                if prev is None or ch > prev[0]:
                    latest[key] = (ch, enriched)

    return [node for _, node in latest.values()]


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
