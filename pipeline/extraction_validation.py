"""Plan 2 relationship validation — drop orphan/duplicate relationships before
persisting an ExtractionResult.

Separated from cognee_pipeline so the rule set evolves independently from the
rest of the extraction/persistence code.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from models.datapoints import ExtractionResult


def _validate_relationships(extraction: "ExtractionResult") -> "ExtractionResult":
    """Plan 2 — drop orphan + duplicate relationships before persistence.

    Invariants after this pass:

    1. Every surviving Relationship's ``source_name`` AND ``target_name`` match
       a ``name`` field on some extracted Character, Location, or Faction in
       the same ExtractionResult. Relationships whose endpoints don't appear
       in the extracted entity set are dropped — the LLM hallucinated a name
       that isn't grounded in this batch.

    2. Duplicates — multiple Relationships with the same
       ``(source_name, relation_type, target_name)`` — are collapsed to a
       single record. When descriptions differ, keep the longest (most
       information-dense). When all descriptions are None/empty, keep the
       first one encountered.

    This mirrors Cognee's cascade-extract validation pattern (dedup by triple
    key, validate endpoints against discovered nodes) — see
    cognee/tasks/graph/cascade_extract/utils/extract_edge_triplets.py.

    Non-Relationship DataPoints are passed through unchanged.
    """
    # Build the allowed-name set from the extracted entities.
    allowed_names = set()
    for collection in (extraction.characters, extraction.locations, extraction.factions):
        for entity in collection:
            name = getattr(entity, "name", None)
            if name:
                allowed_names.add(name)

    # Dedupe by (source, relation, target). When a duplicate is seen, keep
    # whichever has the longer description.
    kept: dict[tuple[str, str, str], Any] = {}
    dropped_orphans = 0
    for rel in extraction.relationships:
        if rel.source_name not in allowed_names or rel.target_name not in allowed_names:
            dropped_orphans += 1
            continue
        key = (rel.source_name, rel.relation_type, rel.target_name)
        existing = kept.get(key)
        if existing is None:
            kept[key] = rel
            continue
        new_desc_len = len(rel.description or "")
        old_desc_len = len(existing.description or "")
        if new_desc_len > old_desc_len:
            kept[key] = rel

    surviving = list(kept.values())
    n_before = len(extraction.relationships)
    n_after = len(surviving)
    if dropped_orphans or n_after != n_before:
        logger.info(
            "Relationship validation: {} → {} (dropped {} orphans, collapsed {} duplicates)",
            n_before, n_after, dropped_orphans,
            n_before - dropped_orphans - n_after,
        )
    extraction.relationships = surviving
    return extraction
