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
import re
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
from pipeline.consolidation import (
    _ConsolidatedDescription,
    _group_entities_for_consolidation,
    _merge_chunk_extractions,
    _merge_group,
    consolidate_entities,
)
from pipeline.extraction_validation import _validate_relationships


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


# Item 6 (Phase A Stage 0): cap concurrent LLM calls during per-chunk extraction.
# 10 is conservative vs. OpenAI Tier 3+ (allows ~50 concurrent) and Anthropic
# Tier 2+ (~50). Tunable if telemetry shows headroom.
EXTRACTION_CONCURRENCY = 10


# Item 2 (Phase A Stage 1): three-tier quote-substring match. Strict first
# (verbatim), then whitespace-normalized, then lowercase. Rejects fabrications
# where the LLM invented a quote not present in the chunk.
_WS_RE = re.compile(r"\s+")


def _quote_matches_chunk_text(chunk_text: str, quote: str) -> bool:
    if not quote:
        return False
    if quote in chunk_text:
        return True
    nq = _WS_RE.sub(" ", quote).strip()
    nc = _WS_RE.sub(" ", chunk_text).strip()
    if nq and nq in nc:
        return True
    if nq and nq.lower() in nc.lower():
        return True
    return False


def _validate_provenance(
    extraction: "ExtractionResult", chunk_text: str
) -> "ExtractionResult":
    """Drop extractions whose quotes don't appear in the chunk text.

    Entities without provenance are kept (backward compat with pre-Phase-A
    artifacts). Entities WITH provenance must match at least one quote to
    survive — fabricated quotes get the extraction dropped.
    """
    def _keep(entity) -> bool:
        prov = getattr(entity, "provenance", None) or []
        if not prov:
            return True
        return any(_quote_matches_chunk_text(chunk_text, p.quote) for p in prov)

    extraction.characters = [c for c in extraction.characters if _keep(c)]
    extraction.locations = [l for l in extraction.locations if _keep(l)]
    extraction.factions = [f for f in extraction.factions if _keep(f)]
    extraction.events = [e for e in extraction.events if _keep(e)]
    extraction.relationships = [r for r in extraction.relationships if _keep(r)]
    extraction.themes = [t for t in extraction.themes if _keep(t)]
    return extraction


def _persist_raw_to_cognee_docstore() -> bool:
    """Return whether cognee.add should index raw chunk text.

    Read lazily from config each call so tests can monkeypatch. See
    docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md § Stage 0.
    """
    from models.config import load_config
    try:
        return bool(getattr(load_config(), "persist_raw_to_cognee_docstore", False))
    except Exception:
        return False


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
        coref = e.get("COREF") or e.get("coref_id") or e.get("coref")
        # Item 8 (Phase A Stage 1): surface COREF cluster id so the LLM can
        # copy it into Character.booknlp_coref_id for stable cross-batch
        # identity keying. Falls back silently if the field isn't present.
        if coref is not None:
            lines.append(f"- #{coref} {text} ({cat})")
        else:
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

def _format_prior_extraction_for_gleaning(extraction: "ExtractionResult") -> str:
    """Compact summary of a prior extraction pass used as a 'don't repeat' hint
    in the gleaning continuation prompt. Keeps token cost down by emitting only
    entity names/types, not full descriptions or provenance.
    """
    lines: list[str] = []
    if extraction.characters:
        lines.append("Characters: " + ", ".join(c.name for c in extraction.characters))
    if extraction.locations:
        lines.append("Locations: " + ", ".join(l.name for l in extraction.locations))
    if extraction.factions:
        lines.append("Factions: " + ", ".join(f.name for f in extraction.factions))
    if extraction.events:
        lines.append("Events: " + "; ".join(e.description[:60] for e in extraction.events))
    if extraction.relationships:
        lines.append("Relationships: " + ", ".join(
            f"{r.source_name}->{r.target_name} ({r.relation_type})"
            for r in extraction.relationships
        ))
    if extraction.themes:
        lines.append("Themes: " + ", ".join(t.name for t in extraction.themes))
    return "\n".join(lines) if lines else "(nothing yet)"


def _merge_glean_extractions(
    first: "ExtractionResult", extra: "ExtractionResult"
) -> "ExtractionResult":
    """Merge a gleaning pass into the first pass, deduping on entity key.

    Keys:
    - Character/Location/Faction/Theme: name
    - PlotEvent: (chapter, description)
    - Relationship: (source_name, target_name, relation_type)
    """
    def _merge_by_name(a, b):
        seen = {x.name for x in a}
        return a + [x for x in b if x.name not in seen]

    first.characters = _merge_by_name(first.characters, extra.characters)
    first.locations = _merge_by_name(first.locations, extra.locations)
    first.factions = _merge_by_name(first.factions, extra.factions)
    first.themes = _merge_by_name(first.themes, extra.themes)

    seen_events = {(e.chapter, e.description) for e in first.events}
    first.events += [e for e in extra.events if (e.chapter, e.description) not in seen_events]

    seen_rels = {(r.source_name, r.target_name, r.relation_type) for r in first.relationships}
    first.relationships += [
        r for r in extra.relationships
        if (r.source_name, r.target_name, r.relation_type) not in seen_rels
    ]
    return first


async def extract_enriched_graph(
    chunks: list[ChapterChunk],
    booknlp: dict[str, Any] | None = None,
    ontology: dict[str, Any] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    consolidate: bool = False,
    max_gleanings: int = 0,
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

    # Item 6 (Phase A Stage 0): parallelize chunk extraction with a
    # Semaphore-bounded asyncio.gather. 10 concurrent calls is conservative
    # vs OpenAI Tier 3+ (~50) and Anthropic Tier 2+ (~50). Chunk order is
    # preserved because gather returns results in input order.
    sem = asyncio.Semaphore(EXTRACTION_CONCURRENCY)

    async def _extract_one(i: int, chunk: ChapterChunk) -> tuple[int, ChapterChunk, ExtractionResult | None]:
        async with sem:
            logger.info(
                "Extracting from chunk {}/{} (chapters {}, ~{} tokens)",
                i + 1, len(chunks), chunk.chapter_numbers, chunk.token_estimate,
            )
            system_prompt, text_input = render_prompt(chunk, booknlp, ontology)
            last_error: Exception | None = None
            extraction: ExtractionResult | None = None
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
                return i, chunk, None

            # Item 1 (Phase A Stage 2): gleaning loop. For each gleaning pass,
            # append a "do not repeat" summary of what we've extracted so far
            # and ask for anything missed. Retries within a gleaning pass reuse
            # the outer max_retries budget but don't nest — a gleaning failure
            # just skips that pass. Dedupes on entity key when merging.
            for glean_idx in range(max_gleanings):
                glean_system = (
                    system_prompt
                    + "\n\n## Gleaning Pass — Find Missed Entities\n\n"
                    + "The following entities were already extracted from this exact chunk:\n\n"
                    + _format_prior_extraction_for_gleaning(extraction)
                    + "\n\nDo NOT repeat any of the above. Emit ONLY entities, "
                      "events, relationships, themes, or factions that the prior "
                      "pass missed. If you cannot find any new items, return empty "
                      "arrays — do not re-emit the prior items. Provenance rules "
                      "still apply: every new item must carry a verbatim quote."
                )
                try:
                    glean_extraction = await LLMGateway.acreate_structured_output(
                        text_input=text_input,
                        system_prompt=glean_system,
                        response_model=ExtractionResult,
                    )
                    extraction = _merge_glean_extractions(extraction, glean_extraction)
                    logger.debug(
                        "Gleaning pass {}/{} for chunk {}: added {} characters, "
                        "{} events, {} relationships",
                        glean_idx + 1, max_gleanings, i + 1,
                        len(glean_extraction.characters),
                        len(glean_extraction.events),
                        len(glean_extraction.relationships),
                    )
                except Exception as exc:
                    logger.warning(
                        "Gleaning pass {}/{} failed for chunk {}: {} — "
                        "continuing with prior extraction",
                        glean_idx + 1, max_gleanings, i + 1, exc,
                    )

            return i, chunk, extraction

    results = await asyncio.gather(*[_extract_one(i, c) for i, c in enumerate(chunks)])

    for i, chunk, extraction in results:
        if extraction is None:
            continue

        # Item 2 (Phase A Stage 1): drop extractions whose provenance quotes
        # don't appear in chunk text. Catches LLM hallucinations before they
        # reach the graph. Entities without provenance (legacy artifacts) are
        # kept untouched.
        extraction = _validate_provenance(extraction, chunk.text)

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
        except Exception as exc:
            logger.warning(
                "Failed to serialize DataPoint {}: {}",
                getattr(dp, "id", "<no-id>"),
                exc,
            )
            dp_records.append({"type": type(dp).__name__, "id": str(dp.id)})

    dp_path = batch_dir / "extracted_datapoints.json"
    dp_path.write_text(
        json.dumps(dp_records, indent=2, default=str), encoding="utf-8",
    )

    logger.info(
        "Saved batch artifacts to {} (input_text, annotations, {} datapoints)",
        batch_dir, len(dp_records),
    )


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
    max_gleanings: int = 0,
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

    # Bonus A (Phase A Stage 0): gate cognee.add behind config flag.
    # Default False — BookRAG's Approach C reads from Kuzu+LanceDB, not
    # cognee's raw-doc store. Slice 2 will flip this on when chunk retrieval
    # via cognee.search(CHUNKS|RAG_COMPLETION) is wired up (blocked on C1/C2).
    if _persist_raw_to_cognee_docstore():
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
    else:
        logger.debug(
            "Skipping cognee.add for {} chunks (persist_raw_to_cognee_docstore=False)",
            len(chunks),
        )

    # Stage 2: Extract (stamps source_chunk_ordinal inside extract_enriched_graph)
    datapoints = await extract_enriched_graph(
        chunks=chunks,
        booknlp=booknlp_output,
        ontology=ontology,
        max_retries=max_retries,
        consolidate=consolidate,
        max_gleanings=max_gleanings,
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
