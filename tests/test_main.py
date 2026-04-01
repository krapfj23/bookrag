"""Comprehensive tests for main.py (FastAPI application).

Covers:
- POST /books/upload: EPUB validation, book_id generation, file save, pipeline launch,
  non-EPUB rejection, missing filename
- GET /books/{book_id}/status: returns state JSON, 404 for unknown book
- GET /books/{book_id}/validation: returns validation JSON, 404 when missing
- POST /books/{book_id}/progress: set reading progress, 404 for unknown, invalid chapter
- GET /health: returns status and version
- CORS middleware is configured
- Response models match spec

Aligned with:
- CLAUDE.md: "FastAPI endpoints"
- Plan: "POST /books/upload — multipart EPUB file → { book_id, status: processing }"
- Plan: "GET /books/{book_id}/status — Returns current pipeline state with batch-level progress"
- Plan: "GET /books/{book_id}/validation — Returns known-answer test results"
- Plan: "POST /books/{book_id}/progress — Set reading progress"
- Plan: "API-only (curl/Postman) — No frontend for MVP"
"""
from __future__ import annotations

import json
import sys
import types
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock cognee modules before main.py imports
# ---------------------------------------------------------------------------
_mock_modules = {
    "cognee": types.ModuleType("cognee"),
    "cognee.infrastructure": types.ModuleType("cognee.infrastructure"),
    "cognee.infrastructure.llm": types.ModuleType("cognee.infrastructure.llm"),
    "cognee.infrastructure.llm.LLMGateway": types.ModuleType("cognee.infrastructure.llm.LLMGateway"),
    "cognee.modules": types.ModuleType("cognee.modules"),
    "cognee.modules.pipelines": types.ModuleType("cognee.modules.pipelines"),
    "cognee.modules.pipelines.tasks": types.ModuleType("cognee.modules.pipelines.tasks"),
    "cognee.modules.pipelines.tasks.task": types.ModuleType("cognee.modules.pipelines.tasks.task"),
    "cognee.tasks": types.ModuleType("cognee.tasks"),
    "cognee.tasks.storage": types.ModuleType("cognee.tasks.storage"),
}
_mock_modules["cognee.infrastructure.llm.LLMGateway"].LLMGateway = MagicMock()
_mock_modules["cognee.modules.pipelines"].run_pipeline = MagicMock()
_mock_modules["cognee.modules.pipelines.tasks.task"].Task = MagicMock()
_mock_modules["cognee.tasks.storage"].add_data_points = MagicMock()

for name, mod in _mock_modules.items():
    sys.modules.setdefault(name, mod)

# Now we can import main and its test client
from fastapi.testclient import TestClient

from models.pipeline_state import PipelineState, StageStatus, save_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Override config to use temp directories."""
    monkeypatch.setenv("BOOKRAG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BOOKRAG_BOOKS_DIR", str(tmp_path / "data" / "books"))
    monkeypatch.setenv("BOOKRAG_PROCESSED_DIR", str(tmp_path / "data" / "processed"))
    return tmp_path


@pytest.fixture
def client(tmp_config, monkeypatch):
    """Fresh test client with mocked orchestrator."""
    # Reimport to pick up env vars
    import importlib
    import models.config
    importlib.reload(models.config)

    # Patch load_config to use tmp dirs
    config = models.config.BookRAGConfig(
        data_dir=tmp_config / "data",
        books_dir=tmp_config / "data" / "books",
        processed_dir=tmp_config / "data" / "processed",
    )
    (tmp_config / "data").mkdir(parents=True, exist_ok=True)
    (tmp_config / "data" / "books").mkdir(parents=True, exist_ok=True)
    (tmp_config / "data" / "processed").mkdir(parents=True, exist_ok=True)

    with patch("main.load_config", return_value=config), \
         patch("main.config", config), \
         patch("main.PipelineOrchestrator") as MockOrch:

        mock_orch = MockOrch.return_value
        mock_orch.run_in_background = MagicMock()
        mock_orch.get_state = MagicMock(return_value=None)

        import main as main_module
        main_module.config = config
        main_module.orchestrator = mock_orch

        yield TestClient(main_module.app), mock_orch, config


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        test_client, _, _ = client
        resp = test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class TestUploadEndpoint:
    def test_upload_epub(self, client):
        """Plan: 'POST /books/upload — multipart EPUB file → { book_id, status }'."""
        test_client, mock_orch, config = client
        epub_content = b"PK\x03\x04fake epub content"
        resp = test_client.post(
            "/books/upload",
            files={"file": ("my_book.epub", BytesIO(epub_content), "application/epub+zip")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "book_id" in data
        assert data["book_id"].startswith("my_book_")
        assert data["message"] == "Pipeline started"
        mock_orch.run_in_background.assert_called_once()

    def test_upload_path_traversal_sanitized(self, client):
        """Vuln fix: crafted filenames like '../../etc/passwd.epub' must be sanitized."""
        test_client, mock_orch, _ = client
        epub_content = b"PK\x03\x04fake epub"
        resp = test_client.post(
            "/books/upload",
            files={"file": ("../../etc/passwd.epub", BytesIO(epub_content), "application/epub+zip")},
        )
        assert resp.status_code == 200
        book_id = resp.json()["book_id"]
        # No path separators or dots in the book_id
        assert "/" not in book_id
        assert ".." not in book_id

    def test_upload_invalid_zip_header_rejected(self, client):
        """Vuln fix: file must start with ZIP magic bytes."""
        test_client, _, _ = client
        resp = test_client.post(
            "/books/upload",
            files={"file": ("fake.epub", BytesIO(b"NOT A ZIP FILE"), "application/epub+zip")},
        )
        assert resp.status_code == 400
        assert "invalid ZIP header" in resp.json()["detail"]

    def test_upload_too_large_rejected(self, client):
        """Vuln fix: uploads exceeding MAX_UPLOAD_BYTES must be rejected."""
        import main as main_module
        original = main_module.MAX_UPLOAD_BYTES
        main_module.MAX_UPLOAD_BYTES = 100  # temporarily shrink limit

        test_client, _, _ = client
        epub_content = b"PK\x03\x04" + b"x" * 200
        resp = test_client.post(
            "/books/upload",
            files={"file": ("big.epub", BytesIO(epub_content), "application/epub+zip")},
        )
        assert resp.status_code == 413

        main_module.MAX_UPLOAD_BYTES = original  # restore

    def test_upload_concurrent_limit(self, client):
        """Vuln fix: too many concurrent pipelines returns 429."""
        test_client, mock_orch, _ = client
        # Simulate MAX_CONCURRENT_PIPELINES alive threads
        import main as main_module
        from unittest.mock import MagicMock as MM
        mock_orch._threads = {
            f"book_{i}": MM(is_alive=MM(return_value=True))
            for i in range(main_module.MAX_CONCURRENT_PIPELINES)
        }
        epub_content = b"PK\x03\x04fake"
        resp = test_client.post(
            "/books/upload",
            files={"file": ("extra.epub", BytesIO(epub_content), "application/epub+zip")},
        )
        assert resp.status_code == 429

    def test_upload_non_epub_rejected(self, client):
        """Only .epub files accepted."""
        test_client, _, _ = client
        resp = test_client.post(
            "/books/upload",
            files={"file": ("book.pdf", BytesIO(b"pdf content"), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "epub" in resp.json()["detail"].lower()

    def test_upload_no_filename_rejected(self, client):
        test_client, _, _ = client
        resp = test_client.post(
            "/books/upload",
            files={"file": ("", BytesIO(b"content"), "application/octet-stream")},
        )
        # FastAPI may return 400 (our check) or 422 (validation error) for empty filename
        assert resp.status_code in (400, 422)

    def test_upload_txt_rejected(self, client):
        test_client, _, _ = client
        resp = test_client.post(
            "/books/upload",
            files={"file": ("book.txt", BytesIO(b"text"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_saves_file(self, client):
        test_client, mock_orch, config = client
        epub_content = b"PK\x03\x04fake epub content here"
        resp = test_client.post(
            "/books/upload",
            files={"file": ("saved.epub", BytesIO(epub_content), "application/epub+zip")},
        )
        book_id = resp.json()["book_id"]
        saved_path = Path(config.books_dir) / f"{book_id}.epub"
        assert saved_path.exists()
        assert saved_path.read_bytes() == epub_content

    def test_upload_case_insensitive_epub(self, client):
        """Should accept .EPUB, .Epub, etc."""
        test_client, _, _ = client
        epub_content = b"PK\x03\x04case test"
        resp = test_client.post(
            "/books/upload",
            files={"file": ("BOOK.EPUB", BytesIO(epub_content), "application/epub+zip")},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestStatusEndpoint:
    def test_status_found(self, client):
        test_client, mock_orch, _ = client
        state = PipelineState.new("testbook", ["parse_epub", "validate"])
        state.status = "processing"
        mock_orch.get_state.return_value = state

        resp = test_client.get("/books/testbook/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["book_id"] == "testbook"
        assert data["status"] == "processing"
        assert "stages" in data

    def test_status_not_found(self, client):
        test_client, mock_orch, _ = client
        mock_orch.get_state.return_value = None

        resp = test_client.get("/books/unknown/status")
        assert resp.status_code == 404

    def test_status_includes_batch_progress(self, client):
        """Plan: 'batch-level: Cognee: batch 2/3 (chapters 4-5 of 5)'."""
        test_client, mock_orch, _ = client
        state = PipelineState.new("batchbook", ["run_cognee_batches"])
        state.status = "processing"
        state.current_batch = 2
        state.total_batches = 3
        mock_orch.get_state.return_value = state

        resp = test_client.get("/books/batchbook/status")
        data = resp.json()
        assert data["current_batch"] == 2
        assert data["total_batches"] == 3

    def test_status_ready_for_query(self, client):
        test_client, mock_orch, _ = client
        state = PipelineState.new("done", ["validate"])
        state.status = "complete"
        state.ready_for_query = True
        mock_orch.get_state.return_value = state

        data = test_client.get("/books/done/status").json()
        assert data["ready_for_query"] is True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidationEndpoint:
    def test_validation_found(self, client):
        test_client, _, config = client
        val_dir = Path(config.processed_dir) / "valbook" / "validation"
        val_dir.mkdir(parents=True, exist_ok=True)
        results = {"graph_populated": True, "orphan_check": "pass"}
        (val_dir / "validation_results.json").write_text(json.dumps(results))

        resp = test_client.get("/books/valbook/validation")
        assert resp.status_code == 200
        assert resp.json()["graph_populated"] is True

    def test_validation_not_found(self, client):
        test_client, _, _ = client
        resp = test_client.get("/books/nobook/validation")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Reading Progress
# ---------------------------------------------------------------------------

class TestProgressEndpoint:
    def test_set_progress(self, client):
        """Plan: 'POST /books/{id}/progress — Set reading progress'."""
        test_client, mock_orch, config = client
        state = PipelineState.new("progbook", ["validate"])
        mock_orch.get_state.return_value = state

        resp = test_client.post(
            "/books/progbook/progress",
            json={"current_chapter": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["book_id"] == "progbook"
        assert data["current_chapter"] == 3

        # Check file was written
        progress_path = Path(config.processed_dir) / "progbook" / "reading_progress.json"
        assert progress_path.exists()
        saved = json.loads(progress_path.read_text())
        assert saved["current_chapter"] == 3

    def test_progress_unknown_book(self, client):
        test_client, mock_orch, _ = client
        mock_orch.get_state.return_value = None

        resp = test_client.post(
            "/books/nobook/progress",
            json={"current_chapter": 1},
        )
        assert resp.status_code == 404

    def test_progress_invalid_chapter(self, client):
        test_client, mock_orch, _ = client
        state = PipelineState.new("progbook", ["validate"])
        mock_orch.get_state.return_value = state

        resp = test_client.post(
            "/books/progbook/progress",
            json={"current_chapter": 0},
        )
        assert resp.status_code == 400
        assert "must be >= 1" in resp.json()["detail"]

    def test_progress_negative_chapter(self, client):
        test_client, mock_orch, _ = client
        state = PipelineState.new("progbook", ["validate"])
        mock_orch.get_state.return_value = state

        resp = test_client.post(
            "/books/progbook/progress",
            json={"current_chapter": -5},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

class TestCORS:
    def test_cors_allowed_origin(self, client):
        """Vuln fix: CORS restricted to localhost origins only."""
        test_client, _, _ = client
        resp = test_client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200

    def test_cors_disallows_arbitrary_origin(self, client):
        """Vuln fix: external origins should not get CORS headers."""
        test_client, _, _ = client
        resp = test_client.get(
            "/health",
            headers={"Origin": "https://evil.com"},
        )
        # The response should not include the evil origin
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert "evil.com" not in allow_origin
