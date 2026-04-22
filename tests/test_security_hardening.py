"""Cross-cutting security tests for Slice 1 hardening."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def _fake_ready_book(tmp_path, book_id, current_chapter=2):
    """Materialize a minimal 'ready' book dir with one batch of DataPoints
    spanning chapters 1..3 so we can test chapter-bounded filtering."""
    from models.pipeline_state import PipelineState, save_state

    root = tmp_path / "processed" / book_id
    (root / "batches" / "batch_01").mkdir(parents=True)
    (root / "batches" / "batch_01" / "extracted_datapoints.json").write_text(json.dumps([
        {"type": "Character", "name": "EarlyChar", "first_chapter": 1},
        {"type": "Character", "name": "MidChar", "first_chapter": 2},
        {"type": "Character", "name": "SpoilerChar", "first_chapter": 3},
    ]))
    state = PipelineState(book_id=book_id)
    state.ready_for_query = True
    save_state(state, root / "pipeline_state.json")
    (root / "reading_progress.json").write_text(
        json.dumps({"book_id": book_id, "current_chapter": current_chapter})
    )
    return root


class TestGraphSpoilerGate:
    """When max_chapter is omitted, /graph/data defaults to reader progress.
    full=true bypasses the gate."""

    def test_default_respects_reading_progress(self, tmp_path, monkeypatch):
        import main
        _fake_ready_book(tmp_path, "book_abc12345", current_chapter=2)
        monkeypatch.setattr(main.config, "processed_dir", str(tmp_path / "processed"))

        client = TestClient(main.app)
        resp = client.get("/books/book_abc12345/graph/data")
        assert resp.status_code == 200
        names = {n["label"] for n in resp.json()["nodes"]}
        assert "EarlyChar" in names
        assert "MidChar" in names
        assert "SpoilerChar" not in names, "Chapter 3 character must not leak"

    def test_explicit_max_chapter_still_wins(self, tmp_path, monkeypatch):
        import main
        _fake_ready_book(tmp_path, "book_abc12345", current_chapter=2)
        monkeypatch.setattr(main.config, "processed_dir", str(tmp_path / "processed"))

        client = TestClient(main.app)
        resp = client.get("/books/book_abc12345/graph/data?max_chapter=1")
        names = {n["label"] for n in resp.json()["nodes"]}
        assert names == {"EarlyChar"}

    def test_full_true_bypasses_gate(self, tmp_path, monkeypatch):
        import main
        _fake_ready_book(tmp_path, "book_abc12345", current_chapter=2)
        monkeypatch.setattr(main.config, "processed_dir", str(tmp_path / "processed"))

        client = TestClient(main.app)
        resp = client.get("/books/book_abc12345/graph/data?full=true")
        names = {n["label"] for n in resp.json()["nodes"]}
        assert "SpoilerChar" in names

    def test_html_graph_endpoint_same_gate(self, tmp_path, monkeypatch):
        import main
        _fake_ready_book(tmp_path, "book_abc12345", current_chapter=2)
        monkeypatch.setattr(main.config, "processed_dir", str(tmp_path / "processed"))

        client = TestClient(main.app)
        default_html = client.get("/books/book_abc12345/graph").text
        full_html = client.get("/books/book_abc12345/graph?full=true").text
        assert "SpoilerChar" not in default_html
        assert "SpoilerChar" in full_html
