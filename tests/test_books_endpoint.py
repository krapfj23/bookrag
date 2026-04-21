"""Tests for GET /books.

Covers:
- Empty processed_dir → returns [].
- One ready book on disk → returns a Book record with derived title,
  chapter count from raw/chapters/chapter_*.txt, and current_chapter
  from reading_progress.json (defaulting to 1 if missing).
- Books whose pipeline_state.json has ready_for_query=false are excluded.
- Directories missing or with corrupt pipeline_state.json are skipped
  (endpoint never 500s) and a warning is logged.

Aligned with:
- docs/superpowers/specs/2026-04-21-slice-1-scaffold-library.md acceptance
  criteria 5, 7, 8, 9.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mirror the cognee mock setup used by tests/test_main.py so importing
# main.py does not fail when cognee is absent.
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


def _write_ready_book(
    processed_dir: Path,
    book_id: str,
    *,
    chapter_count: int,
    current_chapter: int | None = None,
) -> None:
    """Write a pipeline_state.json with ready_for_query=true plus chapter files."""
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    for i in range(1, chapter_count + 1):
        (book_dir / "raw" / "chapters" / f"chapter_{i:02d}.txt").write_text(
            f"chapter {i} body", encoding="utf-8"
        )
    state = PipelineState.new(book_id, ["parse_epub", "validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    if current_chapter is not None:
        (book_dir / "reading_progress.json").write_text(
            json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
            encoding="utf-8",
        )


def _write_in_progress_book(processed_dir: Path, book_id: str) -> None:
    """Write a pipeline_state.json with ready_for_query=false."""
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text(
        "c1", encoding="utf-8"
    )
    state = PipelineState.new(book_id, ["parse_epub"])
    state.status = "processing"
    state.ready_for_query = False
    save_state(state, book_dir / "pipeline_state.json")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fresh TestClient pointing main.config at tmp_path."""
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

        yield TestClient(main_module.app), config


class TestListBooksEndpoint:
    def test_empty_returns_empty_list(self, client):
        test_client, _ = client
        resp = test_client.get("/books")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_one_ready_book(self, client):
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir),
            "christmas_carol_e6ddcd76",
            chapter_count=3,
            current_chapter=2,
        )
        resp = test_client.get("/books")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        book = body[0]
        assert book["book_id"] == "christmas_carol_e6ddcd76"
        assert book["title"] == "Christmas Carol"
        assert book["total_chapters"] == 3
        assert book["current_chapter"] == 2
        assert book["ready_for_query"] is True

    def test_current_chapter_defaults_to_one(self, client):
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir),
            "red_rising_abc12345",
            chapter_count=5,
        )
        resp = test_client.get("/books")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["current_chapter"] == 1

    def test_excludes_not_ready_books(self, client):
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir),
            "done_book_deadbeef",
            chapter_count=2,
        )
        _write_in_progress_book(Path(config.processed_dir), "wip_book_12345678")
        resp = test_client.get("/books")
        ids = [b["book_id"] for b in resp.json()]
        assert ids == ["done_book_deadbeef"]

    def test_skips_directory_without_pipeline_state(self, client):
        test_client, config = client
        (Path(config.processed_dir) / "orphan_dir").mkdir(parents=True)
        _write_ready_book(
            Path(config.processed_dir),
            "ok_book_11111111",
            chapter_count=1,
        )
        resp = test_client.get("/books")
        assert resp.status_code == 200
        ids = [b["book_id"] for b in resp.json()]
        assert ids == ["ok_book_11111111"]

    def test_skips_corrupt_pipeline_state(self, client):
        test_client, config = client
        bad_dir = Path(config.processed_dir) / "bad_book_22222222"
        bad_dir.mkdir(parents=True)
        (bad_dir / "pipeline_state.json").write_text(
            "{this is not valid json", encoding="utf-8"
        )
        _write_ready_book(
            Path(config.processed_dir),
            "ok_book_33333333",
            chapter_count=1,
        )
        resp = test_client.get("/books")
        assert resp.status_code == 200
        ids = [b["book_id"] for b in resp.json()]
        assert ids == ["ok_book_33333333"]

    def test_title_preserves_ids_without_hex_suffix(self, client):
        """book_id 'christmas_carol' (no suffix) should keep all parts in the title."""
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir), "christmas_carol", chapter_count=1
        )
        body = test_client.get("/books").json()
        assert body[0]["title"] == "Christmas Carol"

    def test_title_only_strips_8_hex_suffix(self, client):
        """'_demo' (4 chars) is not a hex suffix — the title should keep 'Demo'."""
        test_client, config = client
        _write_ready_book(
            Path(config.processed_dir), "christmas_carol_demo", chapter_count=1
        )
        body = test_client.get("/books").json()
        assert body[0]["title"] == "Christmas Carol Demo"
