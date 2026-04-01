"""Custom Cognee pipeline with chapter-aware chunking and enriched graph extraction.

Defines two custom Cognee tasks:
  1. chunk_with_chapter_awareness — paragraph-respecting chunking tagged with chapter info
  2. extract_enriched_graph — LLM-driven knowledge extraction using BookNLP annotations

These tasks are assembled into a pipeline alongside Cognee's built-in add_data_points.
"""
from __future__ import annotations

import asyncio
import json
import string
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from loguru import logger

from cognee.infrastructure.llm.LLMGateway import LLMGateway
from cognee.modules.pipelines import run_pipeline
from cognee.modules.pipelines.tasks.task import Task
from cognee.tasks.storage import add_data_points
from pydantic import BaseModel

from pipeline.batcher import Batch


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


class EntityNode(BaseModel):
    """An entity extracted from a chunk."""

    name: str
    entity_type: str
    description: str = ""
    chapter_numbers: list[int] = []
    aliases: list[str] = []


class RelationEdge(BaseModel):
    """A relationship between two entities."""

    source: str
    target: str
    relation_type: str
    description: str = ""
    chapter_numbers: list[int] = []
    evidence: str = ""


class ExtractionResult(BaseModel):
    """Structured output from the LLM extraction call."""

    entities: list[EntityNode] = []
    relations: list[RelationEdge] = []


# ---------------------------------------------------------------------------
# Task 1: Chapter-aware chunking
# ---------------------------------------------------------------------------

def chunk_with_chapter_awareness(
    text: str,
    chunk_size: int = 1500,
    chapter_numbers: list[int] | None = None,
) -> list[ChapterChunk]:
    """Split batch text into chunks that respect paragraph boundaries.

    Each chunk is tagged with the chapter number(s) it spans.  Chunks target
    roughly ``chunk_size`` tokens (estimated as chars/4) and never split
    mid-paragraph.

    Args:
        text: The combined batch text (may contain multiple chapters).
        chunk_size: Target chunk size in approximate tokens.
        chapter_numbers: Chapter numbers covered by this text.

    Returns:
        Ordered list of ``ChapterChunk`` objects.
    """
    if chapter_numbers is None:
        chapter_numbers = [1]

    target_chars = chunk_size * 4  # rough token-to-char conversion
    paragraphs = text.split("\n\n")

    chunks: list[ChapterChunk] = []
    current_paragraphs: list[str] = []
    current_chars = 0
    chunk_start = 0
    cursor = 0

    for para in paragraphs:
        para_len = len(para)

        # If adding this paragraph would exceed budget, flush current chunk
        if current_paragraphs and (current_chars + para_len + 2) > target_chars:
            chunk_text = "\n\n".join(current_paragraphs)
            chunks.append(
                ChapterChunk(
                    text=chunk_text,
                    chapter_numbers=list(chapter_numbers),
                    start_char=chunk_start,
                    end_char=chunk_start + len(chunk_text),
                )
            )
            chunk_start = cursor
            current_paragraphs = []
            current_chars = 0

        current_paragraphs.append(para)
        current_chars += para_len + 2  # account for "\n\n" join separator
        cursor += para_len + 2  # advance past paragraph + separator

    # Flush remaining paragraphs
    if current_paragraphs:
        chunk_text = "\n\n".join(current_paragraphs)
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
        len(chunks),
        chunk_size,
        chapter_numbers,
    )
    for i, c in enumerate(chunks):
        logger.debug(
            "  Chunk {}: ~{} tokens, chars [{}, {})",
            i + 1,
            c.token_estimate,
            c.start_char,
            c.end_char,
        )

    return chunks


# ---------------------------------------------------------------------------
# Prompt rendering
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


def _render_prompt(
    chunk: ChapterChunk,
    booknlp_output: dict[str, Any],
    ontology: dict[str, Any],
) -> str:
    """Render the extraction prompt with chunk context, BookNLP annotations, and ontology.

    Template placeholders (string.Template / $ syntax):
        $chunk_text           — the raw chunk text
        $chapter_numbers      — comma-separated chapter numbers
        $booknlp_entities     — relevant BookNLP entities for this range
        $booknlp_quotes       — relevant BookNLP quotes for this range
        $ontology_classes     — ontology entity classes
        $ontology_relations   — ontology relation types
    """
    template = _load_extraction_prompt()

    # Filter BookNLP annotations to the chunk's character range
    entities = booknlp_output.get("entities", [])
    quotes = booknlp_output.get("quotes", [])

    relevant_entities = [
        e for e in entities
        if _ranges_overlap(
            e.get("start_char", 0), e.get("end_char", 0),
            chunk.start_char, chunk.end_char,
        )
    ]
    relevant_quotes = [
        q for q in quotes
        if _ranges_overlap(
            q.get("start_char", 0), q.get("end_char", 0),
            chunk.start_char, chunk.end_char,
        )
    ]

    ontology_classes = ontology.get("entity_classes", [])
    ontology_relations = ontology.get("relation_types", [])

    # Use string.Template ($ placeholders) to avoid format-string injection
    # from user-controlled book text containing {__class__} etc.
    tmpl = string.Template(template)
    rendered = tmpl.safe_substitute(
        chunk_text=chunk.text,
        chapter_numbers=", ".join(str(n) for n in chunk.chapter_numbers),
        booknlp_entities=json.dumps(relevant_entities, indent=2) if relevant_entities else "[]",
        booknlp_quotes=json.dumps(relevant_quotes, indent=2) if relevant_quotes else "[]",
        ontology_classes=json.dumps(ontology_classes, indent=2) if ontology_classes else "[]",
        ontology_relations=json.dumps(ontology_relations, indent=2) if ontology_relations else "[]",
    )
    return rendered


def _ranges_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Check if two character ranges overlap."""
    return s1 < e2 and s2 < e1


# ---------------------------------------------------------------------------
# Task 2: Enriched graph extraction
# ---------------------------------------------------------------------------

async def extract_enriched_graph(
    chunks: list[ChapterChunk],
    booknlp: dict[str, Any] | None = None,
    ontology: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> list[Any]:
    """Extract knowledge graph data points from chunks using an LLM.

    For each chunk, renders a prompt with BookNLP annotations and ontology
    context, calls Cognee's LLMGateway for structured extraction, and
    converts results into DataPoints.

    Args:
        chunks: Chapter-aware text chunks.
        booknlp: BookNLP output dict with 'entities' and 'quotes' lists.
        ontology: Ontology dict with 'entity_classes' and 'relation_types'.
        max_retries: Number of LLM call retries on failure.

    Returns:
        Flat list of Cognee DataPoint objects.
    """
    if booknlp is None:
        booknlp = {"entities": [], "quotes": []}
    if ontology is None:
        ontology = {"entity_classes": [], "relation_types": []}

    all_datapoints: list[Any] = []
    total_entities = 0
    total_relations = 0

    for i, chunk in enumerate(chunks):
        logger.debug(
            "Extracting graph from chunk {}/{} (chapters {}, ~{} tokens)",
            i + 1,
            len(chunks),
            chunk.chapter_numbers,
            chunk.token_estimate,
        )

        rendered_prompt = _render_prompt(chunk, booknlp, ontology)

        extraction: ExtractionResult | None = None
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                extraction = await LLMGateway.acreate_structured_output(
                    text_input=chunk.text,
                    system_prompt=rendered_prompt,
                    response_model=ExtractionResult,
                )
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM extraction attempt {}/{} failed for chunk {}: {}",
                    attempt,
                    max_retries,
                    i + 1,
                    exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)

        if extraction is None:
            logger.error(
                "All {} attempts failed for chunk {}. Last error: {}",
                max_retries,
                i + 1,
                last_error,
            )
            continue

        total_entities += len(extraction.entities)
        total_relations += len(extraction.relations)

        datapoints = _to_datapoints(extraction, chunk)
        all_datapoints.extend(datapoints)
        logger.debug(
            "  Chunk {}: {} entities, {} relations -> {} datapoints",
            i + 1,
            len(extraction.entities),
            len(extraction.relations),
            len(datapoints),
        )

    logger.info(
        "Extraction complete: {} entities, {} relations, {} datapoints from {} chunks",
        total_entities,
        total_relations,
        len(all_datapoints),
        len(chunks),
    )

    return all_datapoints


def _to_datapoints(result: ExtractionResult, chunk: ChapterChunk) -> list[dict[str, Any]]:
    """Convert an ExtractionResult into a list of dict-based data points.

    Each data point is a dict suitable for Cognee's add_data_points task.
    """
    datapoints: list[dict[str, Any]] = []

    for entity in result.entities:
        datapoints.append({
            "type": "entity",
            "name": entity.name,
            "entity_type": entity.entity_type,
            "description": entity.description,
            "chapter_numbers": entity.chapter_numbers or chunk.chapter_numbers,
            "aliases": entity.aliases,
            "source_start_char": chunk.start_char,
            "source_end_char": chunk.end_char,
        })

    for relation in result.relations:
        datapoints.append({
            "type": "relation",
            "source": relation.source,
            "target": relation.target,
            "relation_type": relation.relation_type,
            "description": relation.description,
            "chapter_numbers": relation.chapter_numbers or chunk.chapter_numbers,
            "evidence": relation.evidence,
            "source_start_char": chunk.start_char,
            "source_end_char": chunk.end_char,
        })

    return datapoints


# ---------------------------------------------------------------------------
# Pipeline assembly
# ---------------------------------------------------------------------------

async def run_bookrag_pipeline(
    batch: Batch,
    booknlp_output: dict[str, Any],
    ontology: dict[str, Any],
    config: Any,
    output_dir: Path | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the full BookRAG Cognee pipeline for a single batch.

    Pipeline stages:
      1. chunk_with_chapter_awareness — split into paragraph-respecting chunks
      2. extract_enriched_graph — LLM extraction with BookNLP + ontology context
      3. add_data_points — persist to Cognee's graph/vector stores

    Args:
        batch: A Batch of chapters to process.
        booknlp_output: BookNLP annotations dict.
        ontology: Ontology dict with classes and relations.
        config: BookRAGConfig or similar with book_id, chunk_size, max_retries.
        output_dir: Optional directory to save extracted datapoints JSON.

    Yields:
        Status dicts from the Cognee pipeline runner.
    """
    book_id = getattr(config, "book_id", "unknown")
    chunk_size = getattr(config, "chunk_size", 1500)
    max_retries = getattr(config, "max_retries", 3)

    logger.info(
        "Starting BookRAG pipeline for batch (chapters {}, book_id={})",
        batch.chapter_numbers,
        book_id,
    )

    tasks = [
        Task(
            chunk_with_chapter_awareness,
            task_config={
                "chunk_size": chunk_size,
                "chapter_numbers": batch.chapter_numbers,
            },
        ),
        Task(
            extract_enriched_graph,
            task_config={
                "booknlp": booknlp_output,
                "ontology": ontology,
                "max_retries": max_retries,
            },
        ),
        Task(
            add_data_points,
            task_config={"batch_size": 30},
        ),
    ]

    extracted_datapoints: list[dict[str, Any]] = []

    async for status in run_pipeline(
        tasks=tasks, data=batch.combined_text, datasets=[book_id]
    ):
        # Capture datapoints from extract stage for persistence
        if isinstance(status, list):
            extracted_datapoints.extend(
                item for item in status if isinstance(item, dict)
            )
        yield status

    # Persist extracted datapoints to disk
    if output_dir is None:
        output_dir = Path("data/processed") / book_id / "batches"

    batch_label = f"batch_{batch.chapter_numbers[0]:02d}"
    batch_dir = output_dir / batch_label
    batch_dir.mkdir(parents=True, exist_ok=True)

    dp_path = batch_dir / "extracted_datapoints.json"
    dp_path.write_text(
        json.dumps(extracted_datapoints, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(
        "Saved {} datapoints to {}",
        len(extracted_datapoints),
        dp_path,
    )
