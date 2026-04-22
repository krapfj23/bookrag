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
