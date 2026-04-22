"""Plan 3 — entity consolidation helpers.

Extracted from cognee_pipeline.py so the merging rule set evolves
independently from extraction/persistence code.

Responsibilities:
  * ``_merge_chunk_extractions`` — concatenate per-chunk ExtractionResults into
    a batch-level result (no dedup).
  * ``_group_entities_for_consolidation`` — bucket extracted entities by
    (type, name, last_known_chapter) while respecting the spoiler invariant
    that entities in different chapter buckets must NOT be merged.
  * ``_merge_group`` — produce a single canonical record from a group.
  * ``consolidate_entities`` — LLM-backed consolidation pass over grouped
    duplicates.

``_load_consolidation_prompt`` is inlined here to avoid a circular import with
``cognee_pipeline._load_extraction_prompt``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from loguru import logger
from pydantic import BaseModel as _PydBase

from cognee.infrastructure.llm.LLMGateway import LLMGateway

if TYPE_CHECKING:
    from models.datapoints import ExtractionResult


_CONSOLIDATION_PROMPT_CACHE: dict[str, str] = {}


def _load_consolidation_prompt(
    path: str = "prompts/consolidate_entity_prompt.txt",
) -> str:
    """Load and cache the consolidation prompt template from disk.

    Kept local to this module to avoid a circular import with
    ``cognee_pipeline._load_extraction_prompt``.
    """
    if path not in _CONSOLIDATION_PROMPT_CACHE:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"Consolidation prompt not found at {p.resolve()}."
            )
        _CONSOLIDATION_PROMPT_CACHE[path] = p.read_text(encoding="utf-8")
    return _CONSOLIDATION_PROMPT_CACHE[path]


def _merge_chunk_extractions(
    extractions: list["ExtractionResult"],
) -> "ExtractionResult":
    """Concatenate per-chunk ExtractionResults into one batch-level result.

    Entities, events, and relationships are simply concatenated — no dedup
    happens here. Dedup happens in _validate_relationships (relationships,
    per-chunk) and consolidate_entities (entities, per-batch).
    """
    from models.datapoints import ExtractionResult

    merged = ExtractionResult()
    for e in extractions:
        merged.characters.extend(e.characters)
        merged.locations.extend(e.locations)
        merged.events.extend(e.events)
        merged.relationships.extend(e.relationships)
        merged.themes.extend(e.themes)
        merged.factions.extend(e.factions)
    return merged


def _group_entities_for_consolidation(
    extraction: "ExtractionResult",
) -> dict[tuple[str, str, int], list]:
    """Group extracted entities by (type, name, last_known_chapter).

    Plan 3's spoiler invariant: NEVER merge across chapter buckets. Two
    records for the same character but with different last_known_chapter
    values describe the character at different points in the narrative
    and must remain distinct retrieval targets.

    Relationships are NOT grouped here — they have their own dedup logic
    in _validate_relationships. Events are per-scene, also not grouped.

    Returns: dict keyed by ("Character"|"Location"|"Faction"|"Theme", name,
    last_known_chapter) → list of extraction objects sharing that key.
    """
    groups: dict[tuple[str, str, int], list] = {}
    for entity in extraction.characters:
        key = ("Character", entity.name, entity.last_known_chapter or entity.first_chapter)
        groups.setdefault(key, []).append(entity)
    for entity in extraction.locations:
        key = ("Location", entity.name, entity.last_known_chapter or entity.first_chapter)
        groups.setdefault(key, []).append(entity)
    for entity in extraction.factions:
        key = ("Faction", entity.name, entity.last_known_chapter or entity.first_chapter)
        groups.setdefault(key, []).append(entity)
    for entity in extraction.themes:
        key = ("Theme", entity.name, entity.last_known_chapter or entity.first_chapter)
        groups.setdefault(key, []).append(entity)
    return groups


def _merge_group(members: list, consolidated_description: str):
    """Produce a single canonical record from a group of same-entity extractions.

    Copies the first member, overwrites its ``description`` with the
    consolidated text, and sets ``first_chapter`` to the minimum across
    members (so retrieval sees the earliest chapter this entity was
    grounded in). ``last_known_chapter`` stays at the group key's value,
    which is shared across all members by construction.

    All other fields (name, aliases, related_character_names, etc.) come
    from the first member. This is arbitrary but deterministic; if the
    first member is missing data, it stays missing — the tradeoff is
    simplicity vs per-field merging, and Plan 3's scope limits this to
    description consolidation only.
    """
    if not members:
        raise ValueError("_merge_group requires at least one member")
    canonical = members[0].model_copy() if hasattr(members[0], "model_copy") else members[0]
    canonical.description = consolidated_description
    canonical.first_chapter = min(m.first_chapter for m in members)
    return canonical


class _ConsolidatedDescription(_PydBase):
    """Structured output for consolidate_entities' LLM call."""
    answer: str


async def consolidate_entities(extraction: "ExtractionResult") -> "ExtractionResult":
    """Plan 3 — merge duplicate same-bucket entity descriptions via LLM.

    For each (type, name, last_known_chapter) group with 2+ members, call
    the LLM once to produce a consolidated description. Replace the group
    with a single canonical record (first member + consolidated description).

    Never merges across chapter buckets — see _group_entities_for_consolidation.

    LLM failures fall back to keeping the first member's description
    unchanged. The pass is best-effort: an extraction with failed
    consolidation is still better than an extraction with duplicates.

    Mutates ``extraction`` in place (and also returns it for chaining).
    """
    groups = _group_entities_for_consolidation(extraction)
    multi = {k: ms for k, ms in groups.items() if len(ms) > 1}
    if not multi:
        return extraction  # nothing to do

    prompt_tmpl = _load_consolidation_prompt("prompts/consolidate_entity_prompt.txt")
    env = SandboxedEnvironment(loader=BaseLoader(), keep_trailing_newline=True)
    template = env.from_string(prompt_tmpl)

    # Cap concurrency so we don't fire 20 LLM calls at once for a big book.
    sem = asyncio.Semaphore(5)

    async def _consolidate_one(key, members):
        async with sem:
            descriptions = [m.description for m in members if m.description]
            if not descriptions:
                # Nothing to consolidate
                return key, members[0]
            prompt = template.render(
                entity_type=key[0],
                entity_name=key[1],
                last_known_chapter=key[2],
                descriptions=descriptions,
            )
            try:
                response = await LLMGateway.acreate_structured_output(
                    text_input=prompt,
                    system_prompt="You are a literary knowledge-graph assistant consolidating entity descriptions.",
                    response_model=_ConsolidatedDescription,
                )
                merged_desc = response.answer.strip()
            except Exception as exc:
                logger.warning(
                    "Consolidation LLM call failed for {}/{} — keeping first description: {}",
                    key[0], key[1], exc,
                )
                merged_desc = members[0].description or ""
            canonical = _merge_group(members, merged_desc)
            return key, canonical

    tasks = [_consolidate_one(k, ms) for k, ms in multi.items()]
    results = await asyncio.gather(*tasks)
    replacements = {k: c for k, c in results}

    # Rebuild the four entity lists: singletons pass through; multi-member
    # groups get replaced with their canonical member.
    def _rebuild(members_list, type_label):
        out = []
        seen_keys: set = set()
        for m in members_list:
            key = (type_label, m.name, m.last_known_chapter or m.first_chapter)
            if key in replacements:
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                out.append(replacements[key])
            else:
                out.append(m)
        return out

    extraction.characters = _rebuild(extraction.characters, "Character")
    extraction.locations = _rebuild(extraction.locations, "Location")
    extraction.factions = _rebuild(extraction.factions, "Faction")
    extraction.themes = _rebuild(extraction.themes, "Theme")
    return extraction
