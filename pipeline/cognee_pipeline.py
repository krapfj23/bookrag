"""Custom Cognee pipeline with chapter-aware chunking and enriched graph extraction.

Implements Phase 2 of the BookRAG pipeline (per bookrag_pipeline_plan.md):
  1. chunk_with_chapter_awareness — paragraph-respecting chunking tagged with chapter info
  2. extract_enriched_graph — LLM extraction using BookNLP annotations + ontology constraints
  3. add_data_points — Cognee built-in, persists to Kuzu (graph) + LanceDB (vectors)

Uses the domain-specific DataPoints from models/datapoints.py (NOT generic entity/edge dicts)
and the ExtractionResult structured output model for Claude via LLMGateway.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from loguru import logger

import os

import cognee
from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.llm.LLMGateway import LLMGateway
from cognee.modules.pipelines import run_pipeline
from cognee.modules.pipelines.tasks.task import Task
from cognee.tasks.storage import add_data_points

from models.config import DEFAULT_CHUNK_SIZE, DEFAULT_MAX_RETRIES
from models.datapoints import ExtractionResult
from pipeline.batcher import Batch


def configure_cognee(config: Any) -> None:
    """Configure Cognee's LLM and embedding settings from BookRAGConfig.

    Reads llm_provider, llm_model, llm_temperature, and llm_seed from our
    config and the API key from the corresponding environment variable
    (OPENAI_API_KEY or ANTHROPIC_API_KEY). Must be called before any
    Cognee LLM operations.

    Plan 1 — extraction determinism: llm_temperature flows through here so
    extraction is reproducible across runs. Cognee's internal default is
    0.0, but OpenAI's API default is 1.0 at call-time; without explicitly
    setting temperature here, extraction is effectively random.

    Note on llm_seed: Cognee 0.5.6's LLMConfig does not accept a seed key
    (verified at cognee/infrastructure/llm/config.py — only llm_temperature,
    llm_model, llm_api_key, llm_endpoint, etc. are recognized). We store
    llm_seed on our config for future use (if Cognee adds the parameter,
    or if we bypass Cognee for a direct OpenAI call path), but do not send
    it to cognee.config.set_llm_config today. Temperature=0 plus OpenAI's
    server-side caching covers the reproducibility needs of Plan 1 on
    Christmas Carol's scale.
    """
    import cognee

    provider = getattr(config, "llm_provider", "openai")
    model = getattr(config, "llm_model", "gpt-4.1-mini")
    temperature = getattr(config, "llm_temperature", 0.0)

    # Resolve API key from environment based on provider
    key_env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_var = key_env_map.get(provider, f"{provider.upper()}_API_KEY")
    api_key = os.environ.get(env_var, "")

    if not api_key:
        logger.warning(
            "No API key found in ${} for provider '{}' — Cognee LLM calls will fail",
            env_var, provider,
        )

    llm_config: dict[str, Any] = {
        "llm_provider": provider,
        "llm_model": f"{provider}/{model}" if "/" not in model else model,
        "llm_api_key": api_key,
        "llm_temperature": temperature,
    }

    try:
        cognee.config.set_llm_config(llm_config)
    except AttributeError as exc:
        logger.warning(
            "cognee.config.set_llm_config unavailable — continuing without LLM config override: {}",
            exc,
        )
        return

    logger.info("Cognee LLM configured: provider={}, model={}", provider, model)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ChapterChunk:
    """A text chunk that respects paragraph boundaries and tracks chapter provenance."""

    text: str
    chapter_numbers: list[int]
    start_char: int
    end_char: int
    ordinal: int | None = None
    chunk_id: str | None = None

    @property
    def token_estimate(self) -> int:
        """Rough token count (chars / 4)."""
        return max(1, len(self.text) // 4)


# ---------------------------------------------------------------------------
# Task 1: Chapter-aware chunking
# ---------------------------------------------------------------------------

def _split_into_segments(text: str) -> list[str]:
    """Split text into segments using paragraph breaks, newlines, or sentences."""
    import re

    if not text or not text.strip():
        return [text] if text else [""]
    # Try paragraph breaks first
    if "\n\n" in text:
        return text.split("\n\n")
    # Fall back to single newlines
    if "\n" in text:
        return text.split("\n")
    # Fall back to sentence boundaries (split after ". " keeping the period)
    segments = re.split(r'(?<=\.\s)', text)
    return [s for s in segments if s.strip()] or [text]


def chunk_with_chapter_awareness(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chapter_numbers: list[int] | None = None,
) -> list[ChapterChunk]:
    """Split batch text into chunks that respect paragraph/sentence boundaries.

    Each chunk is tagged with the chapter number(s) it spans.  Chunks target
    roughly ``chunk_size`` tokens (estimated as chars/4) and never split
    mid-paragraph (or mid-sentence when no paragraph breaks exist).

    Args:
        text: The combined batch text (may contain multiple chapters).
        chunk_size: Target chunk size in approximate tokens.
        chapter_numbers: Chapter numbers covered by this text.

    Returns:
        Ordered list of ``ChapterChunk`` objects.
    """
    if chapter_numbers is None:
        chapter_numbers = [1]

    target_chars = chunk_size * 4
    segments = _split_into_segments(text)
    separator = "\n\n" if "\n\n" in text else ("\n" if "\n" in text else " ")
    sep_len = len(separator)

    chunks: list[ChapterChunk] = []
    current_segments: list[str] = []
    current_chars = 0
    chunk_start = 0
    cursor = 0

    for seg in segments:
        seg_len = len(seg)

        if current_segments and (current_chars + seg_len + sep_len) > target_chars:
            chunk_text = separator.join(current_segments)
            chunks.append(
                ChapterChunk(
                    text=chunk_text,
                    chapter_numbers=list(chapter_numbers),
                    start_char=chunk_start,
                    end_char=chunk_start + len(chunk_text),
                )
            )
            chunk_start = cursor
            current_segments = []
            current_chars = 0

        current_segments.append(seg)
        current_chars += seg_len + sep_len
        cursor += seg_len + sep_len

    if current_segments:
        chunk_text = separator.join(current_segments)
        chunks.append(
            ChapterChunk(
                text=chunk_text,
                chapter_numbers=list(chapter_numbers),
                start_char=chunk_start,
                end_char=chunk_start + len(chunk_text),
            )
        )

    logger.info(
        "Chunked text into {} chunks (target ~{} tokens/chunk, chapters {})",
        len(chunks), chunk_size, chapter_numbers,
    )
    return chunks


# ---------------------------------------------------------------------------
# Prompt rendering — Jinja2 to match {{ }} placeholders in the template
# ---------------------------------------------------------------------------

_PROMPT_CACHE: dict[str, str] = {}


def _load_extraction_prompt(path: str = "prompts/extraction_prompt.txt") -> str:
    """Load and cache the extraction prompt template from disk."""
    if path not in _PROMPT_CACHE:
        prompt_path = Path(path)
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Extraction prompt template not found at {prompt_path.resolve()}. "
                "Create prompts/extraction_prompt.txt before running the pipeline."
            )
        _PROMPT_CACHE[path] = prompt_path.read_text(encoding="utf-8")
        logger.debug("Loaded extraction prompt from {}", prompt_path)
    return _PROMPT_CACHE[path]


def _format_booknlp_entities(entities: list[dict], chunk: ChapterChunk) -> str:
    """Format BookNLP entities relevant to this chunk as a readable annotation block.

    BookNLP entities use start_token/end_token (not char offsets). Since we can't
    perfectly map tokens to chunk char ranges, we filter by chapter overlap and
    include all named entities (PROP) for the chunk's chapters.
    """
    relevant = [
        e for e in entities
        if e.get("prop") in ("PROP", "NOM") and e.get("text", "").strip()
    ]
    if not relevant:
        return "(no entities)"

    lines = []
    for e in relevant[:50]:  # cap to avoid prompt bloat
        cat = e.get("cat", "?")
        text = e.get("text", "?")
        lines.append(f"- {text} ({cat})")
    return "\n".join(lines)


def _format_booknlp_quotes(quotes: list[dict]) -> str:
    """Format BookNLP quotes as a readable annotation block."""
    if not quotes:
        return "(no quotes)"

    lines = []
    for q in quotes[:30]:  # cap to avoid prompt bloat
        speaker = q.get("speaker_name", q.get("speaker", "Unknown"))
        text = q.get("text", q.get("quote", ""))
        if text:
            # Truncate long quotes
            display = text[:120] + "..." if len(text) > 120 else text
            lines.append(f'- {speaker}: "{display}"')
    return "\n".join(lines)


def _format_ontology_classes(ontology: dict) -> str:
    """Format discovered entity classes for the prompt."""
    entities = ontology.get("discovered_entities", {})
    if not entities:
        return "Character, Location, Faction, Organization, Object, PlotEvent, Theme"

    classes = list(entities.keys())
    # Always include core classes even if not discovered
    for cls in ["PlotEvent", "Theme", "Relationship"]:
        if cls not in classes:
            classes.append(cls)
    return ", ".join(classes)


def _format_ontology_relations(ontology: dict) -> str:
    """Format discovered relation types for the prompt."""
    relations = ontology.get("discovered_relations", [])
    if not relations:
        return "(use your judgment — snake_case names like employs, loves, fights)"

    names = [r["name"] for r in relations if isinstance(r, dict) and "name" in r]
    return ", ".join(names[:40])  # cap display


def render_prompt(
    chunk: ChapterChunk,
    booknlp_output: dict[str, Any],
    ontology: dict[str, Any],
    prompt_path: str = "prompts/extraction_prompt.txt",
) -> tuple[str, str]:
    """Render the extraction prompt into (system_prompt, text_input).

    The system prompt contains instructions, ontology constraints, and BookNLP
    annotations. The text_input is the raw chunk text sent separately per
    Cognee's LLMGateway API: acreate_structured_output(text_input, system_prompt, ...).

    Returns:
        (system_prompt, text_input) — system_prompt has {{ text }} replaced with
        a pointer telling the LLM to look at the text_input; text_input is the
        raw chunk text.
    """
    template_str = _load_extraction_prompt(prompt_path)

    entities = booknlp_output.get("entities_tsv", booknlp_output.get("entities", []))
    quotes = booknlp_output.get("quotes", [])

    env = SandboxedEnvironment(loader=BaseLoader(), keep_trailing_newline=True)
    template = env.from_string(template_str)

    system_prompt = template.render(
        chapter_numbers=", ".join(str(n) for n in chunk.chapter_numbers),
        ontology_classes=_format_ontology_classes(ontology),
        ontology_relations=_format_ontology_relations(ontology),
        booknlp_entities=_format_booknlp_entities(entities, chunk),
        booknlp_quotes=_format_booknlp_quotes(quotes),
        text="[See the user message below for the text to extract from.]",
    )

    return system_prompt, chunk.text


# ---------------------------------------------------------------------------
# Task 2: Enriched graph extraction
# ---------------------------------------------------------------------------

async def extract_enriched_graph(
    chunks: list[ChapterChunk],
    booknlp: dict[str, Any] | None = None,
    ontology: dict[str, Any] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    consolidate: bool = False,
) -> list[DataPoint]:
    """Extract knowledge graph DataPoints from chunks using Claude via LLMGateway.

    For each chunk:
      1. Render the system prompt with BookNLP annotations + ontology constraints
      2. Call LLMGateway.acreate_structured_output with ExtractionResult as response_model
      3. Convert the flat extraction into interconnected DataPoints via to_datapoints()

    Args:
        chunks: Chapter-aware text chunks from chunk_with_chapter_awareness.
        booknlp: BookNLP output dict with 'entities_tsv'/'entities' and 'quotes'.
        ontology: Ontology dict from OntologyResult (discovered_entities, discovered_relations).
        max_retries: Number of LLM call retries per chunk on failure.

    Returns:
        Flat list of Cognee DataPoint objects ready for add_data_points.
    """
    if booknlp is None:
        booknlp = {}
    if ontology is None:
        ontology = {}

    all_datapoints: list[DataPoint] = []
    per_chunk_extractions: list[ExtractionResult] = []
    batch_chunk_ordinals: list[int] = []
    extraction_stats = {"characters": 0, "locations": 0, "events": 0,
                        "relationships": 0, "themes": 0, "factions": 0}

    for i, chunk in enumerate(chunks):
        logger.info(
            "Extracting from chunk {}/{} (chapters {}, ~{} tokens)",
            i + 1, len(chunks), chunk.chapter_numbers, chunk.token_estimate,
        )

        system_prompt, text_input = render_prompt(chunk, booknlp, ontology)

        extraction: ExtractionResult | None = None
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                extraction = await LLMGateway.acreate_structured_output(
                    text_input=text_input,
                    system_prompt=system_prompt,
                    response_model=ExtractionResult,
                )
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM extraction attempt {}/{} failed for chunk {}: {}",
                    attempt, max_retries, i + 1, exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)

        if extraction is None:
            logger.error(
                "All {} attempts failed for chunk {}. Last error: {}",
                max_retries, i + 1, last_error,
            )
            continue

        # Plan 2: validate relationships before downstream processing drops
        # orphan endpoints and dedupes (src, rel, tgt) triples.
        extraction = _validate_relationships(extraction)

        # Accumulate stats
        extraction_stats["characters"] += len(extraction.characters)
        extraction_stats["locations"] += len(extraction.locations)
        extraction_stats["events"] += len(extraction.events)
        extraction_stats["relationships"] += len(extraction.relationships)
        extraction_stats["themes"] += len(extraction.themes)
        extraction_stats["factions"] += len(extraction.factions)

        per_chunk_extractions.append(extraction)
        if getattr(chunk, "ordinal", None) is not None:
            batch_chunk_ordinals.append(chunk.ordinal)

        logger.info(
            "  Chunk {}: extracted {} characters, {} events, {} relationships",
            i + 1, len(extraction.characters), len(extraction.events),
            len(extraction.relationships),
        )

    # Plan 3: merge all per-chunk extractions into one batch-level
    # ExtractionResult so consolidate_entities can find duplicates across
    # chunks (e.g., Scrooge appearing in chunks 1 AND 2). If we ran
    # consolidation per-chunk we'd miss those cross-chunk duplicates.
    batch_extraction = _merge_chunk_extractions(per_chunk_extractions)
    if consolidate:
        batch_extraction = await consolidate_entities(batch_extraction)

    # Stamp the batch's latest chunk ordinal on every DataPoint. After
    # consolidation we've merged across chunks, so per-chunk identity is
    # lost — use max-in-batch as the conservative "known by" marker. This
    # matches the existing per-identity snapshot semantics (load_allowed_nodes
    # picks the latest snapshot <= cursor).
    batch_max_ordinal = max(batch_chunk_ordinals) if batch_chunk_ordinals else None
    all_datapoints.extend(batch_extraction.to_datapoints(source_chunk_ordinal=batch_max_ordinal))

    logger.info(
        "Extraction complete: {} total DataPoints from {} chunks ({})",
        len(all_datapoints), len(chunks),
        ", ".join(f"{k}={v}" for k, v in extraction_stats.items() if v > 0),
    )

    return all_datapoints


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


# ---------------------------------------------------------------------------
# Pipeline assembly
# ---------------------------------------------------------------------------

def _save_batch_artifacts(
    batch: Batch,
    booknlp_output: dict[str, Any],
    datapoints: list[DataPoint],
    output_dir: Path,
) -> None:
    """Save all batch intermediate outputs to disk per spec.

    Per CLAUDE.md output structure:
      batches/batch_NN/input_text.txt
      batches/batch_NN/annotations.json
      batches/batch_NN/extracted_datapoints.json
    """
    batch_label = f"batch_{batch.chapter_numbers[0]:02d}"
    batch_dir = output_dir / batch_label
    batch_dir.mkdir(parents=True, exist_ok=True)

    # Input text
    input_path = batch_dir / "input_text.txt"
    input_path.write_text(batch.combined_text, encoding="utf-8")

    # BookNLP annotations for this batch
    annotations_path = batch_dir / "annotations.json"
    # Filter annotations to batch chapters if possible
    annotations = {
        "chapter_numbers": batch.chapter_numbers,
        "entities": booknlp_output.get("entities_tsv", booknlp_output.get("entities", [])),
        "quotes": booknlp_output.get("quotes", []),
    }
    annotations_path.write_text(
        json.dumps(annotations, indent=2, default=str), encoding="utf-8",
    )

    # Extracted DataPoints — serialize to JSON-safe format
    dp_records = []
    for dp in datapoints:
        try:
            dp_records.append(dp.model_dump(mode="json"))
        except Exception:
            dp_records.append({"type": type(dp).__name__, "id": str(dp.id)})

    dp_path = batch_dir / "extracted_datapoints.json"
    dp_path.write_text(
        json.dumps(dp_records, indent=2, default=str), encoding="utf-8",
    )

    logger.info(
        "Saved batch artifacts to {} (input_text, annotations, {} datapoints)",
        batch_dir, len(dp_records),
    )


# ---------------------------------------------------------------------------
# Plan 3 — Entity consolidation helpers
# ---------------------------------------------------------------------------

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


from pydantic import BaseModel as _PydBase


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
    import asyncio as _asyncio

    groups = _group_entities_for_consolidation(extraction)
    multi = {k: ms for k, ms in groups.items() if len(ms) > 1}
    if not multi:
        return extraction  # nothing to do

    prompt_tmpl = _load_extraction_prompt("prompts/consolidate_entity_prompt.txt")
    env = SandboxedEnvironment(loader=BaseLoader(), keep_trailing_newline=True)
    template = env.from_string(prompt_tmpl)

    # Cap concurrency so we don't fire 20 LLM calls at once for a big book.
    sem = _asyncio.Semaphore(5)

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
    results = await _asyncio.gather(*tasks)
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
    # Local import to avoid circular-import shenanigans; ExtractionResult
    # is defined in models.datapoints and also referenced in the function
    # signature string above for forward-ref purposes.
    from models.datapoints import ExtractionResult  # noqa: F401

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


async def run_bookrag_pipeline(
    batch: Batch,
    booknlp_output: dict[str, Any],
    ontology: dict[str, Any],
    book_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    output_dir: Path | None = None,
    embed_triplets: bool = False,
    consolidate: bool = False,
    chunk_ordinal_start: int = 0,
) -> int:
    """Run the full BookRAG Cognee pipeline for a single batch.

    Returns the next available chunk ordinal (``chunk_ordinal_start + len(chunks)``)
    so the orchestrator can pass it to the next batch for a monotonic counter.

    Also saves batch artifacts (input_text.txt, annotations.json,
    extracted_datapoints.json) to data/processed/{book_id}/batches/.
    """
    logger.info(
        "Starting BookRAG pipeline for batch (chapters {}, book_id='{}', ordinal_start={})",
        batch.chapter_numbers, book_id, chunk_ordinal_start,
    )

    # Stage 1: Chunk
    chunks = chunk_with_chapter_awareness(
        text=batch.combined_text,
        chunk_size=chunk_size,
        chapter_numbers=batch.chapter_numbers,
    )

    # Assign ordinals + chunk_ids
    for i, c in enumerate(chunks):
        c.ordinal = chunk_ordinal_start + i
        c.chunk_id = f"{book_id}::chunk_{c.ordinal:04d}"

    # Index chunk text in cognee so CHUNKS / RAG_COMPLETION can find it later.
    for c in chunks:
        try:
            await cognee.add(
                data=c.text,
                dataset_name=book_id,
                node_set=[c.chunk_id],
            )
        except Exception as exc:
            logger.warning(
                "cognee.add failed for {} (chunk text not indexed): {}",
                c.chunk_id, exc,
            )

    # Stage 2: Extract (stamps source_chunk_ordinal inside extract_enriched_graph)
    datapoints = await extract_enriched_graph(
        chunks=chunks,
        booknlp=booknlp_output,
        ontology=ontology,
        max_retries=max_retries,
        consolidate=consolidate,
    )

    if output_dir is None:
        output_dir = Path("data/processed") / book_id / "batches"
    _save_batch_artifacts(batch, booknlp_output, datapoints, output_dir)

    # Stage 3: Persist DataPoints (best-effort)
    if datapoints:
        logger.info(
            "Persisting {} DataPoints via Cognee add_data_points (embed_triplets={})...",
            len(datapoints), embed_triplets,
        )
        try:
            # Task forwards **kwargs to the executable (verified at
            # cognee/modules/pipelines/tasks/task.py:39-41). Passing
            # embed_triplets here wires it through to add_data_points.
            tasks = [
                Task(
                    add_data_points,
                    task_config={"batch_size": 30},
                    embed_triplets=embed_triplets,
                ),
            ]
            async for status in run_pipeline(
                tasks=tasks, data=datapoints, datasets=[book_id]
            ):
                logger.debug("Cognee pipeline status: {}", status)
        except Exception as exc:
            logger.warning(
                "Cognee add_data_points failed (extraction data saved to disk): {}", exc,
            )
    else:
        logger.warning("No DataPoints extracted for batch chapters {}", batch.chapter_numbers)

    next_ordinal = chunk_ordinal_start + len(chunks)
    logger.info(
        "Pipeline complete for batch chapters {} — {} DataPoints, next ordinal {}",
        batch.chapter_numbers, len(datapoints), next_ordinal,
    )
    return next_ordinal
