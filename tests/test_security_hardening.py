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


class TestZipBombUploadRejection:
    """Upload endpoint must return 413 when decompressed size exceeds per-entry cap."""

    def test_oversized_decompressed_entry_rejected(self, tmp_path):
        import io
        import zipfile
        import main
        from fastapi.testclient import TestClient

        # Build a ZIP with one 15 MB entry (exceeds DEFAULT_MAX_ENTRY_BYTES = 10 MB in test caps)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("mimetype", b"application/epub+zip")
            data = b"\x00" * (15 * 1024 * 1024)
            info = zipfile.ZipInfo("huge.html")
            info.file_size = len(data)
            zf.writestr(info, data)
        content = buf.getvalue()

        # Patch caps so test is fast (10 MB entry cap, 50 MB total cap)
        monkeypatch_env = {
            "BOOKRAG_MAX_DECOMPRESSED_BYTES": str(50 * 1024 * 1024),
            "BOOKRAG_MAX_ENTRY_BYTES": str(10 * 1024 * 1024),
        }

        import os
        old_env = {k: os.environ.get(k) for k in monkeypatch_env}
        try:
            os.environ.update(monkeypatch_env)
            client = TestClient(main.app)
            resp = client.post(
                "/books/upload",
                files={"file": ("bomb.epub", content, "application/epub+zip")},
            )
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        assert resp.status_code == 413
        detail = resp.json().get("detail", "")
        assert "decompressed" in detail.lower() or "too large" in detail.lower() or "entry" in detail.lower()


class TestUploadDedupe:
    def test_same_epub_twice_returns_same_id_when_ready(self, tmp_path, monkeypatch):
        import io, zipfile, main
        from models.pipeline_state import PipelineState, save_state

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", b"application/epub+zip")
            zf.writestr("OEBPS/content.xhtml", b"<html>x</html>")
        payload = buf.getvalue()

        processed = tmp_path / "processed"
        processed.mkdir()
        monkeypatch.setattr(main.config, "books_dir", str(tmp_path / "books"))
        monkeypatch.setattr(main.config, "processed_dir", str(processed))

        # Patch orchestrator to not actually run pipeline
        monkeypatch.setattr(main.orchestrator, "run_in_background", lambda *a, **k: None)

        client = TestClient(main.app)
        r1 = client.post("/books/upload",
                         files={"file": ("same.epub", payload, "application/epub+zip")})
        assert r1.status_code == 200
        bid = r1.json()["book_id"]
        assert r1.json()["reused"] is False

        # Simulate pipeline completion
        (processed / bid).mkdir(exist_ok=True)
        s = PipelineState(book_id=bid); s.ready_for_query = True
        save_state(s, processed / bid / "pipeline_state.json")

        r2 = client.post("/books/upload",
                         files={"file": ("same.epub", payload, "application/epub+zip")})
        assert r2.status_code == 200
        assert r2.json()["book_id"] == bid
        assert r2.json()["reused"] is True
