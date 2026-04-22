"""Query route — fog-of-war knowledge-graph retrieval + LLM synthesis.

The slowapi rate-limit decorator is applied here, binding to the app's
``limiter`` via a late import. The alternative would be attaching the
decorator in main.py post-registration, but FastAPI doesn't support that
cleanly; keeping it here simplifies the call graph at the cost of a one-liner
late import.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from api.loaders.book_data import (
    get_reading_progress,
    load_paragraphs_up_to,
)
from api.query.synthesis import (
    ALLOWED_SEARCH_TYPES,
    QueryRequest,
    QueryResponse,
    answer_from_allowed_nodes,
    complete_over_context,
    vector_triplet_search,
)
from api.routes.books import SafeBookId


router = APIRouter()


# The @limiter.limit decorator needs to fire at function-definition time. We
# late-import the limiter and the rate-limit callable from main to avoid a
# circular import (main includes this router at startup — this module is
# imported while main is still executing). If main hasn't finished loading
# when this module is first imported, we fall back to an identity decorator;
# the production path always hits the real limiter because main imports this
# router AFTER creating `limiter`.
try:
    from main import limiter as _limiter, _query_rate_limit as _rate_limit_fn

    _rate_decorator = _limiter.limit(_rate_limit_fn)
except Exception:  # pragma: no cover — startup ordering safety net
    def _rate_decorator(fn):
        return fn


@router.post("/books/{book_id}/query", response_model=QueryResponse)
@_rate_decorator
async def query_book(request: Request, book_id: SafeBookId, req: QueryRequest) -> QueryResponse:
    """Query the knowledge graph with reader-progress fog-of-war.

    Filter semantics:
    - If current_paragraph is set, the graph is filtered to chapters
      STRICTLY BEFORE current_chapter, and paragraphs 0..current_paragraph
      of the current chapter are loaded from raw text and injected as
      additional context.
    - If current_paragraph is not set, Phase 0 behavior applies:
      graph is filtered INCLUSIVE of current_chapter, no raw-text injection.
    """
    from main import config

    processed_dir = Path(config.processed_dir)

    if req.search_type not in ALLOWED_SEARCH_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search_type '{req.search_type}'. Allowed: {sorted(ALLOWED_SEARCH_TYPES)}",
        )

    book_dir = processed_dir / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    from models.pipeline_state import load_state  # local import — avoid cycles

    state_path = book_dir / "pipeline_state.json"
    if state_path.exists():
        try:
            state = load_state(state_path)
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Cannot load pipeline state for {}: {}", book_id, exc)
        else:
            if not state.ready_for_query:
                raise HTTPException(
                    status_code=409,
                    detail=f"Book '{book_id}' is still processing",
                )

    disk_chapter, disk_paragraph = get_reading_progress(book_id, processed_dir)
    current_chapter = (
        min(req.max_chapter, disk_chapter) if req.max_chapter is not None else disk_chapter
    )

    if disk_paragraph is not None:
        graph_max_chapter = max(current_chapter - 1, 0)
        current_chapter_paragraphs = load_paragraphs_up_to(
            book_id, current_chapter, disk_paragraph, processed_dir
        )
    else:
        graph_max_chapter = current_chapter
        current_chapter_paragraphs = []

    results = answer_from_allowed_nodes(
        book_id, req.question, graph_max_chapter=graph_max_chapter,
        processed_dir=processed_dir,
    )

    # Plan 2: when BOOKRAG_USE_TRIPLETS is on, try Cognee's vector triplet
    # search. If it returns results, splice them in at the front of `results`
    # (vector-ranked Relationship hits are likely more semantically relevant
    # than keyword-ranked entity hits). If Cognee is unavailable or returns
    # empty, keep the keyword-based triplet results already in `results`.
    if os.environ.get("BOOKRAG_USE_TRIPLETS", "").lower() in ("1", "true", "yes"):
        try:
            vector_triplets = await vector_triplet_search(
                book_id, req.question, graph_max_chapter, processed_dir
            )
        except Exception as exc:
            logger.warning("vector triplet search raised unexpectedly: {}", exc)
            vector_triplets = []
        if vector_triplets:
            # Deduplicate against keyword-retrieved triplets by arrow content
            seen_contents = {
                r.content for r in results if r.entity_type == "Relationship"
            }
            new_vec = [
                v for v in vector_triplets if v.content not in seen_contents
            ]
            # Front-load vector triplets so synthesis sees them first
            results = new_vec + results

    answer = ""
    if req.search_type == "GRAPH_COMPLETION":
        graph_context = [r.content for r in results[:15]]
        combined = graph_context + current_chapter_paragraphs
        # Delegate to main._complete_over_context so tests that monkeypatch it
        # still intercept the synthesis call.
        import main as _main
        answer = await _main._complete_over_context(req.question, combined)

    return QueryResponse(
        book_id=book_id,
        question=req.question,
        search_type=req.search_type,
        current_chapter=current_chapter,
        current_paragraph=disk_paragraph,
        answer=answer,
        results=results,
        result_count=len(results),
    )
