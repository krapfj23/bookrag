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
from unittest.mock import MagicMock, patch

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
_mock_modules["cognee.infrastructure.llm.LLMGateway"].LLMGateway = MagicMock()
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
