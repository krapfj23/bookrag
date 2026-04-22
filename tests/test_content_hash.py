import json
from pathlib import Path


class TestContentHash:
    def test_sha256_bytes_deterministic(self):
        from pipeline.content_hash import sha256_bytes
        assert sha256_bytes(b"abc") == sha256_bytes(b"abc")
        assert sha256_bytes(b"abc") != sha256_bytes(b"abd")
        assert len(sha256_bytes(b"")) == 64  # hex length

    def test_load_missing_manifest_returns_empty(self, tmp_path):
        from pipeline.content_hash import load_manifest
        assert load_manifest(tmp_path / "processed") == {}

    def test_load_malformed_manifest_returns_empty_and_warns(self, tmp_path, caplog):
        from pipeline.content_hash import load_manifest
        (tmp_path / "processed").mkdir()
        (tmp_path / "processed" / "_content_hashes.json").write_text("{not json")
        assert load_manifest(tmp_path / "processed") == {}

    def test_write_manifest_atomic(self, tmp_path):
        from pipeline.content_hash import write_manifest_atomic, load_manifest
        processed = tmp_path / "processed"
        processed.mkdir()
        write_manifest_atomic(processed, {"abc": "book_1"})
        assert load_manifest(processed) == {"abc": "book_1"}
        # No temp leftover
        assert not (processed / "_content_hashes.json.tmp").exists()

    def test_lookup_existing_returns_book_id_only_when_ready(self, tmp_path):
        from pipeline.content_hash import write_manifest_atomic, lookup_existing_book
        from models.pipeline_state import PipelineState, save_state

        processed = tmp_path / "processed"
        processed.mkdir()
        write_manifest_atomic(processed, {"hhh": "ready_book", "iii": "broken_book"})

        (processed / "ready_book").mkdir()
        s_ready = PipelineState(book_id="ready_book"); s_ready.ready_for_query = True
        save_state(s_ready, processed / "ready_book" / "pipeline_state.json")

        (processed / "broken_book").mkdir()
        s_broken = PipelineState(book_id="broken_book"); s_broken.ready_for_query = False
        save_state(s_broken, processed / "broken_book" / "pipeline_state.json")

        assert lookup_existing_book(processed, "hhh") == "ready_book"
        assert lookup_existing_book(processed, "iii") is None
        assert lookup_existing_book(processed, "unknown") is None
