"""Query-time synthesis helpers.

Pulls the retrieval + LLM-synthesis machinery out of main.py so the route
handler stays thin. Every function that touches disk takes ``processed_dir:
Path`` explicitly — no module-level dependency on FastAPI config.

Cognee is imported here (not shared with main.py) so the query path remains
independent of the app shell.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


# Cognee is optional at import time — only the vector-triplet search path needs it.
try:
    import cognee
    from cognee.modules.search.types import SearchType

    COGNEE_AVAILABLE = True
except (ImportError, AttributeError):
    COGNEE_AVAILABLE = False


ALLOWED_SEARCH_TYPES = {
    "GRAPH_COMPLETION", "CHUNKS", "SUMMARIES", "RAG_COMPLETION",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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
    current_paragraph: int | None = None
    # LLM-synthesized answer from the graph context (empty string if the
    # synthesis call failed and we fell back to raw sources).
    answer: str
    results: list[QueryResultItem]
    result_count: int


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def extract_chapter(item: Any) -> int | None:
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


def _search_datapoints_on_disk(
    book_id: str, question: str, max_chapter: int, processed_dir: Path
) -> list[QueryResultItem]:
    """Search extracted DataPoints on disk using keyword matching + spoiler filtering."""
    from api.loaders.graph_data import load_batch_datapoints

    graph_data = load_batch_datapoints(book_id, processed_dir, max_chapter)
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


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------

class _SpoilerSafeAnswer(BaseModel):
    answer: str


async def complete_over_context(question: str, context: list[str]) -> str:
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


def answer_from_allowed_nodes(
    book_id: str,
    question: str,
    graph_max_chapter: int,
    processed_dir: Path,
) -> list[QueryResultItem]:
    """Pre-filtered keyword retrieval. Walks disk batch JSON, keeps only
    nodes whose effective latest chapter is <= graph_max_chapter, then ranks
    by keyword overlap with the question.

    When ``BOOKRAG_USE_TRIPLETS=1`` (or ``=true``), Relationship DataPoints
    are also surfaced as first-class results — but only when both endpoints
    are within the reader's allowlist (spoiler invariant enforced by
    ``load_allowed_relationships``).
    """
    from pipeline.spoiler_filter import (
        effective_latest_chapter,
        load_allowed_nodes,
        load_allowed_relationships,
    )

    nodes = load_allowed_nodes(book_id, cursor=graph_max_chapter, processed_dir=processed_dir)
    if not nodes:
        return []

    use_triplets = os.environ.get("BOOKRAG_USE_TRIPLETS", "").lower() in ("1", "true", "yes")

    # Tokenize by alphanumeric runs, not whitespace — otherwise 'Marley?' has
    # the trailing question mark attached and fails to match 'marley' anywhere.
    keywords = [
        w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]+", question)
        if len(w) > 2
    ]
    ranked: list[tuple[int, QueryResultItem]] = []

    # Entity nodes — existing behavior
    for node in nodes:
        if node.get("_type") == "Relationship":
            # Relationships are handled in the triplet pass when the flag is on;
            # never surfaced via the node loop because their content format is
            # different (arrow) and their spoiler rule is stricter.
            continue
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

    # Triplet (Relationship) results — gated by env flag
    if use_triplets:
        relationships = load_allowed_relationships(
            book_id,
            cursor=graph_max_chapter,
            processed_dir=processed_dir,
            allowed_nodes=nodes,
        )
        for rel in relationships:
            src = rel.get("source_name", "")
            tgt = rel.get("target_name", "")
            relation = rel.get("relation_type", "")
            desc = rel.get("description", "")
            # Rank triplets by keyword match across endpoints, relation label,
            # and description — give endpoint hits extra weight so asking
            # about Scrooge surfaces his relationships even when the relation
            # word isn't in the query.
            haystack = f"{src.lower()} {tgt.lower()} {relation.lower()} {desc.lower()}"
            score = sum(1 for kw in keywords if kw in haystack) if keywords else 0
            if keywords and score == 0:
                continue
            content = f"{src} → {relation} → {tgt}"
            if desc:
                content = f"{content} — {desc}"
            ranked.append((score, QueryResultItem(
                content=content,
                entity_type="Relationship",
                chapter=effective_latest_chapter(rel),
            )))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked]


async def vector_triplet_search(
    book_id: str,
    question: str,
    graph_max_chapter: int,
    processed_dir: Path,
) -> list[QueryResultItem]:
    """Plan 2 retrieval path — semantic search over Cognee's triplet vector
    index, post-filtered by the reader's allowed-entity set.

    Returns a list of Relationship-typed QueryResultItems. Runs ONLY when:
      1. ``BOOKRAG_USE_TRIPLETS=1`` is set (caller checks this)
      2. Cognee is available and its search is initialized
      3. add_data_points was called with ``embed_triplets=True`` during
         ingestion (otherwise the triplet collection is empty and Cognee
         either errors or returns nothing)

    Spoiler safety: the vector index may contain ANY triplet regardless of
    chapter. We apply ``load_allowed_relationships`` to the returned set so
    no triplet whose endpoints are past the reader's cursor reaches the
    answer-synthesis LLM. The filter is the sole spoiler guarantee.

    Returns an empty list on any Cognee error — the caller handles fallback.
    """
    from pipeline.spoiler_filter import (
        load_allowed_nodes,
    )

    if not COGNEE_AVAILABLE:
        return []

    # Cognee 0.5.6 uses TRIPLET_COMPLETION as the query_type that surfaces
    # Edge objects from the triplet vector index. only_context=True tells
    # Cognee to return the raw context (edges/nodes) instead of running
    # its own answer-synthesis LLM — we do our own synthesis downstream.
    try:
        query_type = getattr(SearchType, "TRIPLET_COMPLETION", None) or SearchType.GRAPH_COMPLETION
        raw_results = await cognee.search(
            query_text=question,
            query_type=query_type,
            datasets=[book_id],
            only_context=True,
        )
    except Exception as exc:
        logger.warning(
            "Cognee triplet vector search unavailable, falling back to keyword path: {}",
            exc,
        )
        return []

    if not raw_results:
        return []

    # Spoiler filter: endpoints must be visible at the reader's cursor.
    # We use the entity-name allowlist as the primary gate. A chapter-level
    # check on the triplet itself is secondary — if the triplet carries a
    # chapter field, it must be <= cursor. We DO NOT require the triple to
    # appear in the pre-computed allowed_rel_keys because vector search may
    # surface valid triplets whose exact (src, rel, tgt) tuple wasn't
    # enumerated by the keyword path (relation-label drift, paraphrase).
    allowed_nodes = load_allowed_nodes(
        book_id, cursor=graph_max_chapter, processed_dir=processed_dir
    )
    allowed_names = {
        n.get("name", "")
        for n in allowed_nodes
        if n.get("name") and n.get("_type") != "Relationship"
    }

    items: list[QueryResultItem] = []
    for raw in raw_results:
        src = None
        tgt = None
        relation = None
        desc = ""
        ch = None
        # Cognee returns Edge-ish objects or dicts depending on the search
        # path. Handle both shapes defensively.
        if isinstance(raw, dict):
            src = (raw.get("source") or {}).get("name") or raw.get("source_name")
            tgt = (raw.get("target") or {}).get("name") or raw.get("target_name")
            relation = raw.get("relationship_name") or raw.get("relation_type")
            desc = raw.get("description") or ""
            ch = extract_chapter(raw)
        else:
            src = getattr(getattr(raw, "source", None), "name", None) or getattr(raw, "source_name", None)
            tgt = getattr(getattr(raw, "target", None), "name", None) or getattr(raw, "target_name", None)
            relation = getattr(raw, "relationship_name", None) or getattr(raw, "relation_type", None)
            desc = getattr(raw, "description", "") or ""
            ch = extract_chapter(raw)

        if not src or not tgt or not relation:
            continue
        # Endpoint allowlist gate
        if src not in allowed_names or tgt not in allowed_names:
            continue
        # Chapter-level gate (only when the triplet carries a chapter)
        if ch is not None and ch > graph_max_chapter:
            continue

        content = f"{src} → {relation} → {tgt}"
        if desc:
            content = f"{content} — {desc}"
        items.append(QueryResultItem(
            content=content,
            entity_type="Relationship",
            chapter=ch,
        ))

    return items
