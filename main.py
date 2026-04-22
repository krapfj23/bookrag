"""FastAPI application for BookRAG — spoiler-free AI chatbot for literature.

Endpoints:
  POST /books/upload          — Upload an EPUB, kick off pipeline
  GET  /books/{book_id}/status — Pipeline progress
  GET  /books/{book_id}/validation — Validation results
  POST /books/{book_id}/progress — Set reading progress
  GET  /health                — Health check
"""
from __future__ import annotations

import html as html_mod
import json
import re
import shutil
import sys

from dotenv import load_dotenv
load_dotenv()
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Path as FPath, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field
from typing import Annotated, Any

from fastapi.responses import HTMLResponse

from models.config import load_config, ensure_directories, BookRAGConfig
from pipeline.orchestrator import PipelineOrchestrator

# Cognee search imports — optional at import time, configured at startup
try:
    import cognee
    from cognee.modules.search.types import SearchType
    from pipeline.cognee_pipeline import configure_cognee

    COGNEE_AVAILABLE = True
except (ImportError, AttributeError):
    COGNEE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_CONCURRENT_PIPELINES = 5
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_]")
_EPUB_ZIP_MAGIC = b"PK\x03\x04"
_SAFE_BOOK_ID_RE = re.compile(r"^[a-z0-9_-]+$")

# Type alias for validated book_id path parameters
SafeBookId = Annotated[str, FPath(pattern=r"^[a-z0-9_-]+$")]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan> — {message}",
)
logger.add(
    "logs/bookrag.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

config: BookRAGConfig = load_config()
ensure_directories(config)

app = FastAPI(
    title="BookRAG",
    description="Spoiler-free AI chatbot for literature",
    version="0.1.0",
)

_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

orchestrator = PipelineOrchestrator(config)

if COGNEE_AVAILABLE:
    try:
        configure_cognee(config)
        logger.info("Cognee configured for search at startup")
    except (AttributeError, Exception) as exc:
        logger.warning("Cognee configuration skipped at startup: {}", exc)
        COGNEE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    book_id: str
    message: str


class ProgressRequest(BaseModel):
    current_chapter: int
    current_paragraph: int | None = None


class ProgressResponse(BaseModel):
    book_id: str
    current_chapter: int
    current_paragraph: int | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


class BookSummary(BaseModel):
    book_id: str
    title: str
    total_chapters: int
    current_chapter: int
    ready_for_query: bool


class ChapterSummary(BaseModel):
    num: int
    title: str
    word_count: int


class Chapter(BaseModel):
    num: int
    title: str
    paragraphs: list[str]
    has_prev: bool
    has_next: bool
    total_chapters: int


class QueryRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    search_type: str = "GRAPH_COMPLETION"
    max_chapter: int | None = Field(default=None, ge=1)


class QueryResultItem(BaseModel):
    content: str
    entity_type: str | None = None
    chapter: int | None = None


class QueryResponse(BaseModel):
    book_id: str
    question: str
    search_type: str
    current_chapter: int
    # LLM-synthesized answer from the graph context (empty string if the
    # synthesis call failed and we fell back to raw sources).
    answer: str
    results: list[QueryResultItem]
    result_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to a safe slug (alphanumeric + underscore only).

    Prevents path traversal via crafted filenames like '../../etc/passwd.epub'.
    """
    stem = Path(filename).stem.lower()
    slug = _SAFE_SLUG_RE.sub("_", stem)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "book"


@app.post("/books/upload", response_model=UploadResponse)
async def upload_book(file: UploadFile = File(...)) -> UploadResponse:
    """Upload an EPUB file and start the processing pipeline.

    Returns immediately with a ``book_id`` that can be used to poll status.
    """
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are accepted")

    # Read with size limit to prevent OOM
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    # Validate EPUB magic bytes (EPUBs are ZIP files)
    if not content.startswith(_EPUB_ZIP_MAGIC):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid EPUB (invalid ZIP header)",
        )

    # Check concurrent pipeline limit
    active = sum(1 for t in orchestrator._tasks.values() if not t.done())
    if active >= MAX_CONCURRENT_PIPELINES:
        raise HTTPException(
            status_code=429,
            detail=f"Too many pipelines running ({active}/{MAX_CONCURRENT_PIPELINES}). Try again later.",
        )

    # Generate safe book_id from sanitized filename
    slug = _sanitize_filename(file.filename)
    book_id = f"{slug}_{uuid.uuid4().hex[:8]}"

    # Save uploaded file
    books_dir = Path(config.books_dir)
    books_dir.mkdir(parents=True, exist_ok=True)
    epub_path = books_dir / f"{book_id}.epub"

    try:
        epub_path.write_bytes(content)
        logger.info("Saved EPUB: {} ({} bytes)", epub_path, len(content))
    except Exception as exc:
        logger.error("Failed to save upload: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Launch pipeline in background
    orchestrator.run_in_background(book_id, epub_path)

    return UploadResponse(book_id=book_id, message="Pipeline started")


@app.get("/books", response_model=list[BookSummary])
async def list_books() -> list[BookSummary]:
    """List every book whose pipeline has completed and is ready for query."""
    return _list_ready_books()


@app.get("/books/{book_id}/status")
async def get_status(book_id: SafeBookId) -> dict:
    """Return the current pipeline state as JSON."""
    state = orchestrator.get_state(book_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    return state.to_dict(sanitize=True)


@app.get("/books/{book_id}/validation")
async def get_validation(book_id: SafeBookId) -> dict:
    """Return validation test results for a processed book."""
    validation_path = (
        Path(config.processed_dir) / book_id / "validation" / "validation_results.json"
    )
    if not validation_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Validation results not found for '{book_id}'. Pipeline may still be running.",
        )
    return json.loads(validation_path.read_text(encoding="utf-8"))


@app.get("/books/{book_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(book_id: SafeBookId) -> list[ChapterSummary]:
    """List chapter metadata for a ready book."""
    files = _list_chapter_files(book_id)
    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"Book '{book_id}' not found or not ready for query",
        )
    summaries: list[ChapterSummary] = []
    for idx, path in enumerate(files, start=1):
        raw_text = path.read_text(encoding="utf-8")
        summaries.append(
            ChapterSummary(
                num=idx,
                title=_derive_chapter_title(raw_text, idx),
                word_count=len(raw_text.split()),
            )
        )
    return summaries


@app.get("/books/{book_id}/chapters/{n}", response_model=Chapter)
async def get_chapter(book_id: SafeBookId, n: int) -> Chapter:
    """Load a single chapter's body as paragraph-split text."""
    chapter = _load_chapter(book_id, n)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {n} not found for book '{book_id}'",
        )
    return chapter


@app.post("/books/{book_id}/progress", response_model=ProgressResponse)
async def set_progress(book_id: SafeBookId, req: ProgressRequest) -> ProgressResponse:
    """Set the reader's current chapter + optional paragraph cursor."""
    if req.current_chapter < 1:
        raise HTTPException(status_code=400, detail="current_chapter must be >= 1")
    if req.current_paragraph is not None and req.current_paragraph < 0:
        raise HTTPException(status_code=400, detail="current_paragraph must be >= 0")

    state = orchestrator.get_state(book_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    progress_path = Path(config.processed_dir) / book_id / "reading_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"book_id": book_id, "current_chapter": req.current_chapter}
    if req.current_paragraph is not None:
        payload["current_paragraph"] = req.current_paragraph
    progress_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info(
        "Updated reading progress: book_id={}, chapter={}, paragraph={}",
        book_id, req.current_chapter, req.current_paragraph,
    )

    return ProgressResponse(
        book_id=book_id,
        current_chapter=req.current_chapter,
        current_paragraph=req.current_paragraph,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check."""
    return HealthResponse(status="ok", version="0.1.0")


# ---------------------------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------------------------

_ALLOWED_SEARCH_TYPES = {
    "GRAPH_COMPLETION", "CHUNKS", "SUMMARIES", "RAG_COMPLETION",
}


_BOOK_ID_HEX_SUFFIX_RE = re.compile(r"_[0-9a-f]{8}$")


def _derive_title(book_id: str) -> str:
    """Strip an optional trailing _<8-hex> id and title-case the remaining slug."""
    slug = _BOOK_ID_HEX_SUFFIX_RE.sub("", book_id)
    words = [w for w in slug.split("_") if w]
    return " ".join(w.capitalize() for w in words) if words else book_id


def _list_ready_books() -> list[BookSummary]:
    """Scan processed_dir for books ready for query.

    Skips directories whose pipeline_state.json is missing or unreadable
    and logs a warning; never raises.
    """
    from models.pipeline_state import load_state  # local import — avoid cycles

    processed_dir = Path(config.processed_dir)
    if not processed_dir.exists():
        return []

    books: list[BookSummary] = []
    for child in sorted(processed_dir.iterdir()):
        if not child.is_dir():
            continue
        state_path = child / "pipeline_state.json"
        if not state_path.exists():
            logger.warning("Skipping {}: pipeline_state.json missing", child.name)
            continue
        try:
            state = load_state(state_path)
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Skipping {}: cannot load pipeline state ({})", child.name, exc)
            continue
        if not state.ready_for_query:
            continue
        chapters_dir = child / "raw" / "chapters"
        total_chapters = (
            len(list(chapters_dir.glob("chapter_*.txt"))) if chapters_dir.exists() else 0
        )
        current_chapter, _ = _get_reading_progress(child.name)
        books.append(
            BookSummary(
                book_id=child.name,
                title=_derive_title(child.name),
                total_chapters=total_chapters,
                current_chapter=current_chapter,
                ready_for_query=True,
            )
        )
    return books


def _list_chapter_files(book_id: str) -> list[Path]:
    """Return sorted chapter_*.txt paths for a ready book.

    Prefers raw/chapters/ (which preserves \\n\\n paragraph breaks).
    Returns [] if the book dir is missing OR ready_for_query is false.
    """
    from models.pipeline_state import load_state  # local import — avoid cycles

    book_dir = Path(config.processed_dir) / book_id
    state_path = book_dir / "pipeline_state.json"
    if not state_path.exists():
        return []
    try:
        state = load_state(state_path)
    except (json.JSONDecodeError, KeyError, OSError):
        return []
    if not state.ready_for_query:
        return []
    chapters_dir = book_dir / "raw" / "chapters"
    if not chapters_dir.exists():
        return []
    return sorted(chapters_dir.glob("chapter_*.txt"))


_TITLE_TERMINATORS = ".!?:"


def _derive_chapter_title(raw_text: str, n: int) -> str:
    """First non-empty stripped line if short + not sentence-terminated + no special chars, else 'Chapter N'.

    Rejects lines containing '*' or '#' (Gutenberg boilerplate markers).
    """
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            len(stripped) < 80
            and stripped[-1] not in _TITLE_TERMINATORS
            and "*" not in stripped
            and "#" not in stripped
        ):
            return stripped
        break
    return f"Chapter {n}"


def _load_chapter(book_id: str, n: int) -> Chapter | None:
    """Load a single chapter. Returns None if the book isn't ready or n is out of range."""
    files = _list_chapter_files(book_id)
    if not files:
        return None
    if n < 1 or n > len(files):
        return None
    raw_text = files[n - 1].read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    title = _derive_chapter_title(raw_text, n)
    return Chapter(
        num=n,
        title=title,
        paragraphs=paragraphs,
        has_prev=n > 1,
        has_next=n < len(files),
        total_chapters=len(files),
    )


def _get_reading_progress(book_id: str) -> tuple[int, int | None]:
    """Load current reading progress. Returns (chapter, paragraph_or_None).

    Paragraph is 0-indexed when present. None means "paragraph cursor not
    recorded" — callers treat that as Phase-0-compatible chapter-only progress.
    """
    progress_path = Path(config.processed_dir) / book_id / "reading_progress.json"
    if not progress_path.exists():
        return 1, None
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1, None
    chapter = int(data.get("current_chapter", 1))
    paragraph = data.get("current_paragraph")
    paragraph = int(paragraph) if paragraph is not None else None
    return chapter, paragraph


def _extract_chapter(item: Any) -> int | None:
    """Return the effective latest chapter for a retrieval result item."""
    from pipeline.spoiler_filter import effective_latest_chapter

    obj = item
    if hasattr(item, "search_result"):
        obj = item.search_result
    return effective_latest_chapter(obj)


def _result_to_text(item: Any) -> str:
    """Convert a search result item to a displayable text string."""
    obj = item
    if hasattr(item, "search_result"):
        obj = item.search_result
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("description") or obj.get("name") or obj.get("text") or json.dumps(obj)
    for attr in ("description", "name", "text"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if val:
                return str(val)
    return str(obj)


def _result_entity_type(item: Any) -> str | None:
    """Extract entity type name from a search result item."""
    obj = item
    if hasattr(item, "search_result"):
        obj = item.search_result
    return type(obj).__name__ if not isinstance(obj, (str, dict)) else None


def _search_datapoints_on_disk(book_id: str, question: str, max_chapter: int) -> list[QueryResultItem]:
    """Search extracted DataPoints on disk using keyword matching + spoiler filtering."""
    graph_data = _load_batch_datapoints(book_id, max_chapter)
    if not graph_data["nodes"]:
        return []

    keywords = [w.lower() for w in question.split() if len(w) > 2]
    results: list[QueryResultItem] = []

    for node in graph_data["nodes"]:
        label = (node.get("label") or "").lower()
        desc = (node.get("description") or "").lower()
        searchable = f"{label} {desc}"

        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            content = node.get("label", "")
            if node.get("description"):
                content += f" — {node['description']}"
            results.append(QueryResultItem(
                content=content,
                entity_type=node.get("type"),
                chapter=node.get("chapter"),
            ))

    # Sort by relevance (more keyword hits first)
    results.sort(key=lambda r: sum(1 for kw in keywords if kw in r.content.lower()), reverse=True)
    return results


class _SpoilerSafeAnswer(BaseModel):
    answer: str


async def _complete_over_context(question: str, context: list[str]) -> str:
    """Ask the configured LLM to answer `question` using ONLY `context`.

    Context is the stringified allowed-node content list. No retrieval
    happens inside this function — the caller owns the fog-of-war guarantee.
    """
    from cognee.infrastructure.llm.LLMGateway import LLMGateway

    if not context:
        return "I don't have information about that yet based on your reading progress."

    system = (
        "You are a spoiler-free literary assistant. Answer the user's question "
        "using ONLY the provided knowledge-graph context. If the context does "
        "not contain the answer, say you don't know yet. Never invent events "
        "or use prior knowledge of the book."
    )
    user = (
        f"Question: {question}\n\n"
        "Context (allowed nodes from the reader's current progress):\n"
        + "\n".join(f"- {c}" for c in context)
    )
    response = await LLMGateway.acreate_structured_output(
        text_input=user,
        system_prompt=system,
        response_model=_SpoilerSafeAnswer,
    )
    return response.answer


def _answer_from_allowed_nodes(
    book_id: str,
    question: str,
    cursor: int,
) -> list[QueryResultItem]:
    """Pre-filtered keyword retrieval. Walks disk batch JSON, keeps only
    nodes whose effective latest chapter is <= cursor, then ranks by
    keyword overlap with the question."""
    from pipeline.spoiler_filter import load_allowed_nodes, effective_latest_chapter

    nodes = load_allowed_nodes(book_id, cursor, processed_dir=Path(config.processed_dir))
    if not nodes:
        return []

    keywords = [w.lower() for w in question.split() if len(w) > 2]
    ranked: list[tuple[int, QueryResultItem]] = []
    for node in nodes:
        label = (node.get("name") or node.get("description") or "").lower()
        desc = (node.get("description") or "").lower()
        haystack = f"{label} {desc}"
        score = sum(1 for kw in keywords if kw in haystack) if keywords else 0
        if keywords and score == 0:
            continue
        content = node.get("name") or node.get("description") or ""
        if node.get("name") and node.get("description"):
            content = f"{node['name']} — {node['description']}"
        ranked.append((score, QueryResultItem(
            content=content,
            entity_type=node.get("_type"),
            chapter=effective_latest_chapter(node),
        )))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked]


@app.post("/books/{book_id}/query", response_model=QueryResponse)
async def query_book(book_id: SafeBookId, req: QueryRequest) -> QueryResponse:
    """Query the knowledge graph with reader-progress fog-of-war.

    Retrieval is PRE-FILTERED: a node allowlist is computed from disk based
    on the reader's current chapter, and only allowed nodes are ever
    considered. No Cognee default search is run, because it retrieves over
    the full dataset before we can filter and may leak spoilers through
    graph-completion reasoning.
    """
    if req.search_type not in _ALLOWED_SEARCH_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search_type '{req.search_type}'. Allowed: {sorted(_ALLOWED_SEARCH_TYPES)}",
        )

    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    disk_max, _ = _get_reading_progress(book_id)
    current_chapter = (
        min(req.max_chapter, disk_max) if req.max_chapter is not None else disk_max
    )

    results = _answer_from_allowed_nodes(book_id, req.question, current_chapter)

    answer = ""
    if req.search_type == "GRAPH_COMPLETION":
        context = [r.content for r in results[:15]]
        answer = await _complete_over_context(req.question, context)

    return QueryResponse(
        book_id=book_id,
        question=req.question,
        search_type=req.search_type,
        current_chapter=current_chapter,
        answer=answer,
        results=results,
        result_count=len(results),
    )


# ---------------------------------------------------------------------------
# Graph visualization endpoints
# ---------------------------------------------------------------------------


def _load_batch_datapoints(book_id: str, max_chapter: int | None = None) -> dict:
    """Load extracted DataPoints from batch output files and build graph data."""
    batches_dir = Path(config.processed_dir) / book_id / "batches"
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    type_colors = {
        "Character": "#4363d8",
        "Location": "#3cb44b",
        "Faction": "#911eb4",
        "Theme": "#e6194b",
        "PlotEvent": "#f58231",
    }

    if not batches_dir.exists():
        return {"nodes": [], "edges": []}

    for dp_file in sorted(batches_dir.glob("batch_*/extracted_datapoints.json")):
        data = json.loads(dp_file.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("datapoints", [])

        for dp in items:
            dp_type = dp.get("type") or dp.get("__type__") or "Unknown"
            first_ch = dp.get("first_chapter") or dp.get("chapter")

            if max_chapter and first_ch and int(first_ch) > max_chapter:
                continue

            name = dp.get("name") or dp.get("description", "")[:40]
            node_id = f"{dp_type}:{name}"

            if dp_type in ("Character", "Location", "Faction", "Theme"):
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "label": name,
                        "type": dp_type,
                        "color": type_colors.get(dp_type, "#aaaaaa"),
                        "description": dp.get("description", ""),
                        "chapter": first_ch,
                    }

            if dp_type == "Relationship":
                src = dp.get("source", {})
                tgt = dp.get("target", {})
                src_name = src.get("name", "") if isinstance(src, dict) else str(src)
                tgt_name = tgt.get("name", "") if isinstance(tgt, dict) else str(tgt)
                if src_name and tgt_name:
                    edges.append({
                        "from": f"Character:{src_name}",
                        "to": f"Character:{tgt_name}",
                        "label": dp.get("relation_type", ""),
                    })

            if dp_type == "PlotEvent":
                event_id = f"PlotEvent:{name}"
                if event_id not in nodes:
                    nodes[event_id] = {
                        "id": event_id,
                        "label": name[:30] + "..." if len(name) > 30 else name,
                        "type": "PlotEvent",
                        "color": type_colors["PlotEvent"],
                        "description": dp.get("description", ""),
                        "chapter": first_ch,
                    }
                for participant in dp.get("participants", []):
                    p_name = participant.get("name", "") if isinstance(participant, dict) else str(participant)
                    if p_name:
                        edges.append({
                            "from": f"Character:{p_name}",
                            "to": event_id,
                            "label": "participates_in",
                        })

    return {"nodes": list(nodes.values()), "edges": edges}


@app.get("/books/{book_id}/graph/data")
async def get_graph_data(book_id: SafeBookId, max_chapter: int | None = Query(default=None, ge=1)) -> dict:
    """Return knowledge graph as JSON nodes and edges, optionally spoiler-filtered."""
    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    return _load_batch_datapoints(book_id, max_chapter)


@app.get("/books/{book_id}/graph", response_class=HTMLResponse)
async def get_graph_visualization(book_id: SafeBookId, max_chapter: int | None = Query(default=None, ge=1)) -> HTMLResponse:
    """Return an interactive HTML visualization of the knowledge graph."""
    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    graph_data = _load_batch_datapoints(book_id, max_chapter)

    if not graph_data["nodes"]:
        return HTMLResponse(
            content="<html><body><h2>No graph data available.</h2>"
            "<p>The pipeline may not have completed Phase 2 (Cognee extraction) yet.</p>"
            "</body></html>"
        )

    # Escape JSON for safe embedding in <script type="application/json"> (prevent </script> breakout)
    safe_graph_json = json.dumps(graph_data).replace("</", "<\\/")
    safe_book_id = html_mod.escape(book_id)
    chapter_label = html_mod.escape(f" (up to chapter {max_chapter})") if max_chapter else ""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>BookRAG Knowledge Graph — {safe_book_id}{chapter_label}</title>
    <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
            integrity="sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"
            crossorigin="anonymous"></script>
    <style>
        body {{ margin: 0; font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; }}
        #graph {{ width: 100vw; height: 85vh; }}
        #header {{ padding: 12px 20px; background: #16213e; display: flex; align-items: center; gap: 20px; }}
        #header h1 {{ margin: 0; font-size: 1.3em; }}
        .legend {{ display: flex; gap: 16px; font-size: 0.85em; }}
        .legend-item {{ display: flex; align-items: center; gap: 4px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
        #info {{ padding: 8px 20px; font-size: 0.85em; opacity: 0.7; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>{safe_book_id}{chapter_label}</h1>
        <div class="legend">
            <span class="legend-item"><span class="legend-dot" style="background:#4363d8"></span> Character</span>
            <span class="legend-item"><span class="legend-dot" style="background:#3cb44b"></span> Location</span>
            <span class="legend-item"><span class="legend-dot" style="background:#911eb4"></span> Faction</span>
            <span class="legend-item"><span class="legend-dot" style="background:#e6194b"></span> Theme</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f58231"></span> Event</span>
        </div>
    </div>
    <div id="graph"></div>
    <div id="info">Click a node to see details. Scroll to zoom. Drag to pan.</div>
    <script type="application/json" id="graph-data">{safe_graph_json}</script>
    <script>
        function esc(s) {{ return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }}
        var gd = JSON.parse(document.getElementById('graph-data').textContent);
        var rawNodes = gd.nodes;
        var rawEdges = gd.edges;

        var nodes = new vis.DataSet(rawNodes.map(function(n) {{
            return {{
                id: n.id,
                label: n.label,
                color: {{ background: n.color, border: n.color, highlight: {{ background: '#fff', border: n.color }} }},
                font: {{ color: '#eee', size: 14 }},
                title: '<b>' + esc(n.type) + ':</b> ' + esc(n.label) + (n.description ? '<br>' + esc(n.description) : '') + (n.chapter ? '<br>Ch. ' + n.chapter : ''),
                shape: n.type === 'PlotEvent' ? 'diamond' : 'dot',
                size: n.type === 'Character' ? 20 : 14
            }};
        }}));

        var edges = new vis.DataSet(rawEdges.map(function(e, i) {{
            return {{
                id: i,
                from: e.from,
                to: e.to,
                label: e.label,
                font: {{ color: '#999', size: 10, strokeWidth: 0 }},
                color: {{ color: '#555', highlight: '#aaa' }},
                arrows: 'to'
            }};
        }}));

        var container = document.getElementById('graph');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            physics: {{
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{ gravitationalConstant: -50, centralGravity: 0.01, springLength: 150 }},
                stabilization: {{ iterations: 200 }}
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }},
            layout: {{ improvedLayout: true }}
        }};
        new vis.Network(container, data, options);
    </script>
</body>
</html>"""

    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
