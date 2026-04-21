"""Tests for GET /books/{book_id}/chapters and /books/{book_id}/chapters/{n}.

Covers:
- Happy path: 3 raw chapter files -> 3 ChapterSummary entries in order.
- ready_for_query=False -> 404.
- Unknown book_id -> 404.
- Out-of-range n -> 404 (n < 1 or n > total).
- Title heuristic: short first line without sentence terminator is used
  (chapter_02.txt 'The Last of the Spirits'); else 'Chapter N'.
- Paragraph split: backend splits raw text on '\\n\\n' and drops empties.
- POST /progress regression: the reading_progress.json file reflects
  the posted current_chapter.

Aligned with:
- docs/superpowers/specs/2026-04-21-slice-3-reading-chapter-serving.md
  acceptance criteria 3, 5, 9, 11, 12.
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


CH1_BODY = (
    "The Project Gutenberg eBook header line.\n\n"
    "Marley was dead: to begin with.\n\n"
    "Oh! But he was a tight-fisted hand at the grindstone, Scrooge!\n\n"
    "External heat and cold had little influence on Scrooge."
)

CH2_BODY = (
    "The Last of the Spirits\n\n"
    "“Am I that man who lay upon the bed?” he cried, upon his knees.\n\n"
    "The finger pointed from the grave to him, and back again."
)

CH3_BODY = (
    "*** END OF THE PROJECT GUTENBERG EBOOK ***\n\n"
    "Updated editions will replace the previous one."
)


def _write_ready_carol(processed_dir: Path, book_id: str, current_chapter: int = 1) -> None:
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text(CH1_BODY, encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_02.txt").write_text(CH2_BODY, encoding="utf-8")
    (book_dir / "raw" / "chapters" / "chapter_03.txt").write_text(CH3_BODY, encoding="utf-8")
    state = PipelineState.new(book_id, ["parse_epub", "validate"])
    state.status = "complete"
    state.ready_for_query = True
    save_state(state, book_dir / "pipeline_state.json")
    (book_dir / "reading_progress.json").write_text(
        json.dumps({"book_id": book_id, "current_chapter": current_chapter}),
        encoding="utf-8",
    )


def _write_not_ready(processed_dir: Path, book_id: str) -> None:
    book_dir = processed_dir / book_id
    (book_dir / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book_dir / "raw" / "chapters" / "chapter_01.txt").write_text("c1", encoding="utf-8")
    state = PipelineState.new(book_id, ["parse_epub"])
    state.status = "processing"
    state.ready_for_query = False
    save_state(state, book_dir / "pipeline_state.json")


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

        yield TestClient(main_module.app), config, mock_orch


class TestListChapters:
    def test_happy_path_three_chapters(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3
        assert [c["num"] for c in body] == [1, 2, 3]
        assert body[1]["title"] == "The Last of the Spirits"
        assert body[0]["title"] == "Chapter 1"
        assert body[2]["title"] == "Chapter 3"
        assert all("word_count" in c and c["word_count"] > 0 for c in body)

    def test_unknown_book_returns_404(self, client):
        test_client, _, _ = client
        resp = test_client.get("/books/nosuch_book/chapters")
        assert resp.status_code == 404

    def test_not_ready_book_returns_404(self, client):
        test_client, config, _ = client
        _write_not_ready(Path(config.processed_dir), "wip_book_11111111")
        resp = test_client.get("/books/wip_book_11111111/chapters")
        assert resp.status_code == 404


class TestLoadChapter:
    def test_happy_path_chapter_one(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["num"] == 1
        assert body["title"] == "Chapter 1"  # first line too long + non-terminator-check fails
        assert len(body["paragraphs"]) == 4
        assert body["paragraphs"][1].startswith("Marley was dead")
        assert body["has_prev"] is False
        assert body["has_next"] is True
        assert body["total_chapters"] == 3

    def test_happy_path_chapter_two_title_heuristic(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["num"] == 2
        assert body["title"] == "The Last of the Spirits"
        assert body["has_prev"] is True
        assert body["has_next"] is True

    def test_chapter_three_has_next_false(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_prev"] is True
        assert body["has_next"] is False

    def test_n_zero_returns_404(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/0")
        assert resp.status_code == 404

    def test_n_too_large_returns_404(self, client):
        test_client, config, _ = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        resp = test_client.get("/books/christmas_carol_e6ddcd76/chapters/99")
        assert resp.status_code == 404

    def test_unknown_book_returns_404(self, client):
        test_client, _, _ = client
        resp = test_client.get("/books/nosuch_book/chapters/1")
        assert resp.status_code == 404


class TestProgressFileShape:
    """Regression for POST /progress — confirm the persisted JSON shape."""

    def test_progress_write_shape(self, client):
        test_client, config, mock_orch = client
        _write_ready_carol(Path(config.processed_dir), "christmas_carol_e6ddcd76")
        mock_orch.get_state.return_value = PipelineState.new(
            "christmas_carol_e6ddcd76", ["validate"]
        )
        resp = test_client.post(
            "/books/christmas_carol_e6ddcd76/progress",
            json={"current_chapter": 2},
        )
        assert resp.status_code == 200
        path = (
            Path(config.processed_dir)
            / "christmas_carol_e6ddcd76"
            / "reading_progress.json"
        )
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["current_chapter"] == 2
        assert saved["book_id"] == "christmas_carol_e6ddcd76"
