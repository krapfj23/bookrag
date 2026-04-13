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

from jinja2 import BaseLoader, Environment
from loguru import logger

import os

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

    Reads llm_provider, llm_model from our config and the API key from
    the corresponding environment variable (OPENAI_API_KEY or ANTHROPIC_API_KEY).
    Must be called before any Cognee LLM operations.
    """
    import cognee

    provider = getattr(config, "llm_provider", "openai")
    model = getattr(config, "llm_model", "gpt-4.1-mini")

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

    cognee.config.set_llm_config({
        "llm_provider": provider,
        "llm_model": f"{provider}/{model}" if "/" not in model else model,
        "llm_api_key": api_key,
    })

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

    env = Environment(loader=BaseLoader(), keep_trailing_newline=True)
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

        # Accumulate stats
        extraction_stats["characters"] += len(extraction.characters)
        extraction_stats["locations"] += len(extraction.locations)
        extraction_stats["events"] += len(extraction.events)
        extraction_stats["relationships"] += len(extraction.relationships)
        extraction_stats["themes"] += len(extraction.themes)
        extraction_stats["factions"] += len(extraction.factions)

        # Convert to interconnected DataPoints
        datapoints = extraction.to_datapoints()
        all_datapoints.extend(datapoints)

        logger.info(
            "  Chunk {}: extracted {} characters, {} events, {} relationships -> {} DataPoints",
            i + 1, len(extraction.characters), len(extraction.events),
            len(extraction.relationships), len(datapoints),
        )

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


async def run_bookrag_pipeline(
    batch: Batch,
    booknlp_output: dict[str, Any],
    ontology: dict[str, Any],
    book_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    output_dir: Path | None = None,
) -> list[DataPoint]:
    """Run the full BookRAG Cognee pipeline for a single batch.

    Pipeline stages:
      1. chunk_with_chapter_awareness — split into paragraph-respecting chunks
      2. extract_enriched_graph — LLM extraction with BookNLP + ontology context
      3. add_data_points — persist to Cognee's graph/vector stores (Kuzu + LanceDB)

    Also saves batch artifacts (input_text.txt, annotations.json,
    extracted_datapoints.json) to data/processed/{book_id}/batches/.

    Args:
        batch: A Batch of chapters to process.
        booknlp_output: BookNLP annotations dict (book_json, entities_tsv, quotes).
        ontology: Ontology dict from OntologyResult or discovery JSON.
        book_id: Book identifier for dataset naming and output paths.
        chunk_size: Target tokens per chunk (default 1500).
        max_retries: LLM retry count per chunk (default 3, per CLAUDE.md).
        output_dir: Override output directory. Defaults to data/processed/{book_id}/batches.

    Returns:
        List of DataPoint objects that were extracted and stored.
    """
    logger.info(
        "Starting BookRAG pipeline for batch (chapters {}, book_id='{}')",
        batch.chapter_numbers, book_id,
    )

    # Stage 1: Chunk
    chunks = chunk_with_chapter_awareness(
        text=batch.combined_text,
        chunk_size=chunk_size,
        chapter_numbers=batch.chapter_numbers,
    )

    # Stage 2: Extract
    datapoints = await extract_enriched_graph(
        chunks=chunks,
        booknlp=booknlp_output,
        ontology=ontology,
        max_retries=max_retries,
    )

    # Save batch artifacts to disk first (before Cognee persistence which may fail)
    if output_dir is None:
        output_dir = Path("data/processed") / book_id / "batches"
    _save_batch_artifacts(batch, booknlp_output, datapoints, output_dir)

    # Stage 3: Persist via Cognee (best-effort — extraction data is already saved)
    if datapoints:
        logger.info("Persisting {} DataPoints via Cognee add_data_points...", len(datapoints))
        try:
            tasks = [
                Task(add_data_points, task_config={"batch_size": 30}),
            ]
            async for status in run_pipeline(
                tasks=tasks, data=datapoints, datasets=[book_id]
            ):
                logger.debug("Cognee pipeline status: {}", status)
        except Exception as exc:
            logger.warning(
                "Cognee add_data_points failed (extraction data saved to disk): {}", exc
            )
    else:
        logger.warning("No DataPoints extracted for batch chapters {}", batch.chapter_numbers)

    logger.info(
        "Pipeline complete for batch chapters {} — {} DataPoints",
        batch.chapter_numbers, len(datapoints),
    )
    return datapoints
