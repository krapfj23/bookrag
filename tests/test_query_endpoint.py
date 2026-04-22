"""Tests for POST /books/{book_id}/query — the additive max_chapter field.

Covers:
- Backward compat: request without max_chapter still uses disk progress.
- Client can lower the ceiling (smaller max_chapter is respected).
- Server clamps at disk: a request with max_chapter > disk is reduced to disk.
- Invalid search_type still returns 400.
- Unknown book_id still returns 404.

Aligned with:
- docs/superpowers/specs/2026-04-21-slice-4-chat-query-wiring.md
  acceptance criteria 4, 9, 13 and "Backend scope" section.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_mock_modules = {
    "cognee": types.ModuleType("cognee"),
    "cognee.infrastructure": types.ModuleType("cognee.infrastructure"),
    "cognee.infrastructure.llm": types.ModuleType("cognee.infrastructure.llm"),
    "cognee.infrastructure.llm.LLMGateway": types.ModuleType(
        "cognee.infrastructure.llm.LLMGateway"
    ),
    "cognee.modules": types.ModuleType("cognee.modules"),
    "cognee.modules.pipelines": types.ModuleType("cognee.modules.pipelines"),
    "cognee.modules.pipelines.tasks": types.ModuleType(
        "cognee.modules.pipelines.tasks"
    ),
    "cognee.modules.pipelines.tasks.task": types.ModuleType(
        "cognee.modules.pipelines.tasks.task"
    ),
    "cognee.tasks": types.ModuleType("cognee.tasks"),
    "cognee.tasks.storage": types.ModuleType("cognee.tasks.storage"),
}
# LLMGateway.acreate_structured_output is awaited inside the /query path.
# Provide an AsyncMock that returns an object with an `.answer` string.
_llm_gateway_stub = MagicMock()
_stub_response = MagicMock()
_stub_response.answer = "stub synthesis"
_llm_gateway_stub.acreate_structured_output = AsyncMock(return_value=_stub_response)
_mock_modules["cognee.infrastructure.llm.LLMGateway"].LLMGateway = _llm_gateway_stub
_mock_modules["cognee.modules.pipelines"].run_pipeline = MagicMock()
_mock_modules["cognee.modules.pipelines.tasks.task"].Task = MagicMock()
_mock_modules["cognee.tasks.storage"].add_data_points = MagicMock()
for name, mod in _mock_modules.items():
    sys.modules.setdefault(name, mod)

from fastapi.testclient import TestClient

from models.pipeline_state import PipelineState, save_state


BOOK_ID = "christmas_carol_e6ddcd76"


def _write_ready_book(processed_dir: Path, book_id: str, current_chapter: int) -> None:
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text("c1 body", encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_02.txt").write_text("c2 body", encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_03.txt").write_text("c3 body", encoding="utf-8")
    state = PipelineState.new(book_id, ["validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    (book_dir / "reading_progress.json").write_text(
        json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
        encoding="utf-8",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    import importlib
    import models.config
    importlib.reload(models.config)
    config = models.config.BookRAGConfig(
        data_dir=tmp_path / "data",
        books_dir=tmp_path / "data" / "books",
        processed_dir=tmp_path / "data" / "processed",
    )
    (tmp_path / "data" / "processed").mkdir(parents=True, exist_ok=True)

    with patch("main.load_config", return_value=config), patch(
        "main.config", config
    ), patch("main.PipelineOrchestrator") as MockOrch:
        mock_orch = MockOrch.return_value
        mock_orch.run_in_background = MagicMock()
        mock_orch.get_state = MagicMock(return_value=None)

        import main as main_module
        main_module.config = config
        main_module.orchestrator = mock_orch
        # Force disk-fallback path; Cognee disabled so search hits _search_datapoints_on_disk.
        main_module.COGNEE_AVAILABLE = False

        yield TestClient(main_module.app), config, mock_orch


class TestQueryMaxChapter:
    def test_omitted_max_chapter_uses_disk(self, client):
        """AC (backend scope): when max_chapter is omitted, behavior matches slice-3."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "Who is Marley?", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 2

    def test_client_smaller_max_chapter_respected(self, client):
        """AC 4 + 9: client lowering the ceiling is honored."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=3)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={
                "question": "Who is Marley?",
                "search_type": "GRAPH_COMPLETION",
                "max_chapter": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Response echoes the clamped effective chapter (min of disk and client).
        assert body["current_chapter"] == 1

    def test_client_larger_max_chapter_is_clamped_to_disk(self, client):
        """AC 9: client cannot raise the ceiling above disk; server clamps down."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={
                "question": "Who is Marley?",
                "search_type": "GRAPH_COMPLETION",
                "max_chapter": 99,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 2

    def test_equal_max_chapter_is_passthrough(self, client):
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={
                "question": "Who is Marley?",
                "search_type": "GRAPH_COMPLETION",
                "max_chapter": 2,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["current_chapter"] == 2

    def test_invalid_search_type_still_400(self, client):
        """Existing behavior unchanged."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=1)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "x", "search_type": "NONSENSE"},
        )
        assert resp.status_code == 400

    def test_unknown_book_still_404(self, client):
        """Existing behavior unchanged."""
        test_client, _, _ = client
        resp = test_client.post(
            "/books/nosuch_book/query",
            json={"question": "x", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 404

    def test_response_shape_has_all_fields(self, client):
        """Regression: QueryResponse shape is preserved."""
        test_client, config, _ = client
        _write_ready_book(Path(config.processed_dir), BOOK_ID, current_chapter=2)

        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "empty search", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["book_id"] == BOOK_ID
        assert body["question"] == "empty search"
        assert body["search_type"] == "GRAPH_COMPLETION"
        assert isinstance(body["current_chapter"], int)
        assert isinstance(body["results"], list)
        assert body["result_count"] == len(body["results"])
        # GraphRAG synthesis: response must include an answer field (may be
        # empty string when Cognee is mocked out).
        assert "answer" in body
        assert isinstance(body["answer"], str)


def _write_batch_with_relationship(
    processed_dir: Path,
    book_id: str,
    current_chapter: int,
) -> None:
    """Write a ready book with two Characters + one Relationship in the flat-list shape."""
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    for n in range(1, current_chapter + 1):
        (book_dir / "raw" / "chapters" / f"chapter_{n:02d}.txt").write_text(
            f"ch {n}", encoding="utf-8"
        )
    state = PipelineState.new(book_id, ["validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    (book_dir / "reading_progress.json").write_text(
        json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
        encoding="utf-8",
    )
    batch_dir = book_dir / "batches" / "batch_01"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "extracted_datapoints.json").write_text(json.dumps([
        {"type": "Character", "name": "Scrooge",
         "description": "A miserly old man.", "first_chapter": 1, "last_known_chapter": 1},
        {"type": "Character", "name": "Marley",
         "description": "Scrooge's dead partner.", "first_chapter": 1, "last_known_chapter": 1},
        {"type": "Relationship", "source_name": "Scrooge", "target_name": "Marley",
         "relation_type": "business partner of",
         "description": "Long-time partners before Marley's death.",
         "chapter": 1, "first_chapter": 1, "last_known_chapter": 1},
    ]))


class TestTripletRetrieval:
    """When BOOKRAG_USE_TRIPLETS=1, the /query response includes Relationship
    triplets as first-class results with arrow-shaped content."""

    def _stub_synthesis(self, monkeypatch):
        """Replace the async synthesis call with a fixed string.

        These tests care about retrieval (which results land), not the
        LLM completion step. Bypassing LLMGateway keeps them hermetic.
        """
        async def fake(*_args, **_kwargs):
            return "stub answer"
        monkeypatch.setattr("main._complete_over_context", fake)

    def test_triplet_flag_off_omits_relationship_results(self, client, monkeypatch):
        self._stub_synthesis(monkeypatch)
        monkeypatch.delenv("BOOKRAG_USE_TRIPLETS", raising=False)
        test_client, config, _ = client
        _write_batch_with_relationship(
            Path(config.processed_dir), BOOK_ID, current_chapter=2
        )
        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "Tell me about Scrooge's partner",
                  "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        entity_types = {r.get("entity_type") for r in body["results"]}
        assert "Relationship" not in entity_types, (
            "with flag off, Relationships must NOT appear as results"
        )

    def test_triplet_flag_on_includes_relationship_as_arrow_content(
        self, client, monkeypatch
    ):
        self._stub_synthesis(monkeypatch)
        monkeypatch.setenv("BOOKRAG_USE_TRIPLETS", "1")
        test_client, config, _ = client
        _write_batch_with_relationship(
            Path(config.processed_dir), BOOK_ID, current_chapter=2
        )
        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "Tell me about Scrooge's partner",
                  "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        triplet_results = [r for r in body["results"]
                           if r.get("entity_type") == "Relationship"]
        assert len(triplet_results) >= 1, (
            f"expected at least one Relationship in results; got {body['results']}"
        )
        # Content should be the arrow form
        assert "→" in triplet_results[0]["content"], (
            f"expected arrow format, got {triplet_results[0]['content']!r}"
        )
        assert "Scrooge" in triplet_results[0]["content"]
        assert "Marley" in triplet_results[0]["content"]
        assert triplet_results[0]["chapter"] == 1

    def test_triplet_flag_on_still_spoiler_safe(self, client, monkeypatch):
        """Even with triplets on, a Relationship whose target first appears
        after the cursor must NOT be returned."""
        self._stub_synthesis(monkeypatch)
        monkeypatch.setenv("BOOKRAG_USE_TRIPLETS", "1")
        test_client, config, _ = client
        book_dir = Path(config.processed_dir) / BOOK_ID
        (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
        for n in range(1, 4):
            (book_dir / "raw" / "chapters" / f"chapter_{n:02d}.txt").write_text(
                f"ch {n}", encoding="utf-8"
            )
        state = PipelineState.new(BOOK_ID, ["validate"])
        state.status = "complete"
        state.ready_for_query = True
        save_state(state, book_dir / "pipeline_state.json")
        (book_dir / "reading_progress.json").write_text(
            json.dumps({"book_id": BOOK_ID, "current_chapter": 1}),
            encoding="utf-8",
        )
        batch_dir = book_dir / "batches" / "batch_01"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "extracted_datapoints.json").write_text(json.dumps([
            {"type": "Character", "name": "Scrooge",
             "first_chapter": 1, "last_known_chapter": 1},
            # Future character — not visible at cursor=1
            {"type": "Character", "name": "GhostOfFuture",
             "first_chapter": 3, "last_known_chapter": 3},
            {"type": "Relationship", "source_name": "Scrooge",
             "target_name": "GhostOfFuture", "relation_type": "haunted by",
             "chapter": 1, "first_chapter": 1, "last_known_chapter": 1},
        ]))
        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "ghost", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        triplet_results = [r for r in body["results"]
                           if r.get("entity_type") == "Relationship"]
        assert triplet_results == [], (
            f"relationship with unseen target must not leak; got {triplet_results}"
        )


class TestVectorTripletFallback:
    """Plan 2 T4 — vector triplet path with keyword fallback.

    When BOOKRAG_USE_TRIPLETS=1:
    - If Cognee's vector search succeeds, its results are spliced in at
      the front of the response (after spoiler-filtering).
    - If it raises (no DB, Cognee unavailable, etc.), the endpoint still
      succeeds using the existing keyword-based triplet path.
    - Spoiler safety is invariant either way.
    """

    def _stub_synthesis(self, monkeypatch):
        async def fake(*_args, **_kwargs):
            return "stub answer"
        monkeypatch.setattr("main._complete_over_context", fake)

    def test_vector_search_failure_falls_back_to_keyword(self, client, monkeypatch):
        """Cognee raises SearchPreconditionError (or any exception) from
        cognee.search → endpoint must return 200 with keyword-based triplet
        results, not 500."""
        self._stub_synthesis(monkeypatch)
        monkeypatch.setenv("BOOKRAG_USE_TRIPLETS", "1")

        async def broken_search(**_kwargs):
            raise RuntimeError("Search prerequisites not met: no database")

        monkeypatch.setattr("main.cognee.search", broken_search)
        monkeypatch.setattr("main.COGNEE_AVAILABLE", True)

        test_client, config, _ = client
        _write_batch_with_relationship(
            Path(config.processed_dir), BOOK_ID, current_chapter=2
        )
        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "Tell me about Scrooge's partner",
                  "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        triplet_results = [r for r in body["results"]
                           if r.get("entity_type") == "Relationship"]
        # Keyword fallback should still produce at least one triplet
        assert len(triplet_results) >= 1, (
            f"keyword fallback must produce triplets when vector fails; "
            f"got {body['results']}"
        )

    def test_vector_search_success_frontloads_triplets(self, client, monkeypatch):
        """When Cognee returns triplets, they appear first in results."""
        self._stub_synthesis(monkeypatch)
        monkeypatch.setenv("BOOKRAG_USE_TRIPLETS", "1")

        # Cognee returns one extra triplet the keyword path wouldn't find
        async def fake_search(**_kwargs):
            return [{
                "source": {"name": "Scrooge"},
                "target": {"name": "Marley"},
                "relationship_name": "was_partner_of",
                "description": "Long-time partners before Marley's death.",
                "chapter": 1,
            }]

        monkeypatch.setattr("main.cognee.search", fake_search)
        monkeypatch.setattr("main.COGNEE_AVAILABLE", True)

        test_client, config, _ = client
        _write_batch_with_relationship(
            Path(config.processed_dir), BOOK_ID, current_chapter=2
        )
        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "Scrooge partner",
                  "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # First result should be a Relationship with "was_partner_of" (the
        # vector-search-only relation); the keyword path's "business partner of"
        # would come after.
        assert body["results"], "must return at least one result"
        first = body["results"][0]
        assert first["entity_type"] == "Relationship", (
            f"vector triplet should be front-loaded; got {first}"
        )

    def test_vector_search_result_still_spoiler_filtered(self, client, monkeypatch):
        """Even a Cognee vector hit must pass through load_allowed_relationships.
        A triplet whose target entity is past the cursor must NOT leak."""
        self._stub_synthesis(monkeypatch)
        monkeypatch.setenv("BOOKRAG_USE_TRIPLETS", "1")

        async def fake_search(**_kwargs):
            # Cognee returns a triplet to a future character — this MUST be filtered
            return [{
                "source": {"name": "Scrooge"},
                "target": {"name": "GhostOfFuture"},
                "relationship_name": "haunted_by",
                "chapter": 1,
            }]

        monkeypatch.setattr("main.cognee.search", fake_search)
        monkeypatch.setattr("main.COGNEE_AVAILABLE", True)

        test_client, config, _ = client
        book_dir = Path(config.processed_dir) / BOOK_ID
        (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
        for n in range(1, 4):
            (book_dir / "raw" / "chapters" / f"chapter_{n:02d}.txt").write_text(
                f"ch {n}", encoding="utf-8"
            )
        state = PipelineState.new(BOOK_ID, ["validate"])
        state.status = "complete"
        state.ready_for_query = True
        save_state(state, book_dir / "pipeline_state.json")
        (book_dir / "reading_progress.json").write_text(
            json.dumps({"book_id": BOOK_ID, "current_chapter": 1}),
            encoding="utf-8",
        )
        batch_dir = book_dir / "batches" / "batch_01"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "extracted_datapoints.json").write_text(json.dumps([
            {"type": "Character", "name": "Scrooge",
             "first_chapter": 1, "last_known_chapter": 1},
            {"type": "Character", "name": "GhostOfFuture",
             "first_chapter": 3, "last_known_chapter": 3},
        ]))
        resp = test_client.post(
            f"/books/{BOOK_ID}/query",
            json={"question": "ghost", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # No triplet involving GhostOfFuture may reach the response
        assert not any(
            "GhostOfFuture" in r.get("content", "")
            for r in body["results"]
        ), f"spoiler leak: {body['results']}"
