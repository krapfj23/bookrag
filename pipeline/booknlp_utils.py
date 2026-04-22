"""Shared helpers for converting BookNLPOutput-like objects into the plain-dict
shape the Cognee pipeline formatters expect.

Kept here (rather than on BookNLPOutput itself) because re-extraction scripts
and ad-hoc tools may load BookNLP-shaped data from disk without reconstructing
the full dataclass hierarchy.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def booknlp_output_to_dict(output) -> dict[str, Any]:
    """Normalize BookNLPOutput (dataclass) into the dict shape
    run_bookrag_pipeline expects: {'entities': [...], 'quotes': [...]}
    where each element is a plain dict with the fields the cognee_pipeline
    formatters look up (prop, cat, text for entities; speaker, text for quotes).
    """

    def _to_dict(obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, dict):
            return obj
        return dict(obj.__dict__) if hasattr(obj, "__dict__") else {}

    entities = [_to_dict(e) for e in getattr(output, "entities", [])]
    raw_quotes = [_to_dict(q) for q in getattr(output, "quotes", [])]
    # Resolve speaker_coref_id -> name for the prompt formatter
    coref_to_name = getattr(output, "coref_id_to_name", {}) or {}
    for q in raw_quotes:
        cid = q.get("speaker_coref_id")
        if cid is not None and cid in coref_to_name:
            q["speaker_name"] = coref_to_name[cid]

    return {
        "entities": entities,
        "entities_tsv": entities,
        "quotes": raw_quotes,
    }
