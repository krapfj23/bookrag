"""Comprehensive tests for models/pipeline_state.py.

Covers:
- StageStatus: defaults, to_dict, from_dict, all status values, optional fields
- PipelineState: defaults, new() factory, to_dict, from_dict, all fields
- save_state: atomic write (tmp file + rename), creates parent dirs, thread safety
- load_state: reads JSON, FileNotFoundError, corrupted JSON
- Thread safety: concurrent save/load
- Round-trip: save → load preserves all data

Aligned with:
- CLAUDE.md: "Pipeline orchestrator (background threads, retry, progress)"
- Plan: "PipelineState persisted to pipeline_state.json"
- Plan: "Stage status: pending | running | complete | failed"
- Plan: "Pipeline status: processing | complete | failed"
- Plan: "Progress tracking: stage + batch-level granularity"
- Plan: "ready_for_query: false until validation complete"
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from models.pipeline_state import (
    StageStatus,
    PipelineState,
    save_state,
    load_state,
    _file_lock,
)


# ---------------------------------------------------------------------------
# StageStatus
# ---------------------------------------------------------------------------

class TestStageStatus:
    def test_defaults(self):
        ss = StageStatus()
        assert ss.status == "pending"
        assert ss.duration_seconds is None
        assert ss.error is None

    def test_all_valid_statuses(self):
        """Plan: 'pending | running | complete | failed'."""
        for status in ("pending", "running", "complete", "failed"):
            ss = StageStatus(status=status)
            assert ss.status == status

    def test_with_duration(self):
        ss = StageStatus(status="complete", duration_seconds=12.5)
        assert ss.duration_seconds == 12.5

    def test_with_error(self):
        ss = StageStatus(status="failed", error="OOM killed")
        assert ss.error == "OOM killed"

    def test_to_dict_minimal(self):
        d = StageStatus().to_dict()
        assert d == {"status": "pending"}
        assert "duration_seconds" not in d
        assert "error" not in d

    def test_to_dict_full(self):
        ss = StageStatus(status="failed", duration_seconds=5.0, error="timeout")
        d = ss.to_dict()
        assert d == {"status": "failed", "duration_seconds": 5.0, "error": "timeout"}

    def test_from_dict_minimal(self):
        ss = StageStatus.from_dict({"status": "running"})
        assert ss.status == "running"
        assert ss.duration_seconds is None

    def test_from_dict_full(self):
        ss = StageStatus.from_dict({
            "status": "complete",
            "duration_seconds": 3.14,
            "error": None,
        })
        assert ss.status == "complete"
        assert ss.duration_seconds == 3.14

    def test_from_dict_empty(self):
        ss = StageStatus.from_dict({})
        assert ss.status == "pending"

    def test_roundtrip(self):
        original = StageStatus(status="failed", duration_seconds=42.0, error="crash")
        restored = StageStatus.from_dict(original.to_dict())
        assert restored.status == original.status
        assert restored.duration_seconds == original.duration_seconds
        assert restored.error == original.error

    def test_to_dict_sanitize_strips_traceback(self):
        """Vuln fix: sanitize=True should strip internal paths from error."""
        full_traceback = (
            'Traceback (most recent call last):\n'
            '  File "/Users/jeff/Documents/bookrag/pipeline/orchestrator.py", line 137\n'
            '    await self._execute_stage(stage_name, state, ctx, log_ctx)\n'
            'RuntimeError: EPUB corrupt'
        )
        ss = StageStatus(status="failed", error=full_traceback)
        d = ss.to_dict(sanitize=True)
        assert d["error"] == "RuntimeError: EPUB corrupt"
        assert "/Users/" not in d["error"]
        assert "orchestrator.py" not in d["error"]

    def test_to_dict_sanitize_false_preserves_full_error(self):
        full_error = "Traceback...\nRuntimeError: boom"
        ss = StageStatus(status="failed", error=full_error)
        d = ss.to_dict(sanitize=False)
        assert d["error"] == full_error

    def test_to_dict_sanitize_with_none_error(self):
        ss = StageStatus(status="complete")
        d = ss.to_dict(sanitize=True)
        assert "error" not in d


# ---------------------------------------------------------------------------
# PipelineState
# ---------------------------------------------------------------------------

class TestPipelineState:
    STAGES = ["parse_epub", "run_booknlp", "validate"]

    def test_defaults(self):
        ps = PipelineState(book_id="test")
        assert ps.book_id == "test"
        assert ps.status == "pending"
        assert ps.stages == {}
        assert ps.current_batch is None
        assert ps.total_batches is None
        assert ps.ready_for_query is False

    def test_new_factory(self):
        """Plan: all stages start as 'pending'."""
        ps = PipelineState.new("mybook", self.STAGES)
        assert ps.book_id == "mybook"
        assert ps.status == "pending"
        assert set(ps.stages.keys()) == set(self.STAGES)
        for stage_status in ps.stages.values():
            assert stage_status.status == "pending"

    def test_new_preserves_order(self):
        ps = PipelineState.new("mybook", self.STAGES)
        assert list(ps.stages.keys()) == self.STAGES

    def test_to_dict(self):
        ps = PipelineState.new("mybook", ["stage1"])
        ps.status = "processing"
        ps.current_batch = 2
        ps.total_batches = 5
        ps.ready_for_query = False

        d = ps.to_dict()
        assert d["book_id"] == "mybook"
        assert d["status"] == "processing"
        assert d["current_batch"] == 2
        assert d["total_batches"] == 5
        assert d["ready_for_query"] is False
        assert "stage1" in d["stages"]
        assert d["stages"]["stage1"]["status"] == "pending"

    def test_from_dict(self):
        data = {
            "book_id": "restored",
            "status": "complete",
            "stages": {
                "parse": {"status": "complete", "duration_seconds": 1.0},
                "validate": {"status": "complete", "duration_seconds": 0.5},
            },
            "current_batch": None,
            "total_batches": None,
            "ready_for_query": True,
        }
        ps = PipelineState.from_dict(data)
        assert ps.book_id == "restored"
        assert ps.status == "complete"
        assert ps.ready_for_query is True
        assert ps.stages["parse"].status == "complete"
        assert ps.stages["parse"].duration_seconds == 1.0

    def test_from_dict_missing_optional_fields(self):
        data = {"book_id": "minimal"}
        ps = PipelineState.from_dict(data)
        assert ps.status == "pending"
        assert ps.stages == {}
        assert ps.current_batch is None
        assert ps.ready_for_query is False

    def test_roundtrip(self):
        original = PipelineState.new("roundtrip", self.STAGES)
        original.status = "processing"
        original.current_batch = 3
        original.total_batches = 10
        original.stages["parse_epub"] = StageStatus(status="complete", duration_seconds=2.5)
        original.stages["run_booknlp"] = StageStatus(status="failed", error="OOM")

        restored = PipelineState.from_dict(original.to_dict())
        assert restored.book_id == original.book_id
        assert restored.status == original.status
        assert restored.current_batch == original.current_batch
        assert restored.total_batches == original.total_batches
        assert restored.stages["parse_epub"].status == "complete"
        assert restored.stages["run_booknlp"].error == "OOM"

    def test_all_pipeline_status_values(self):
        """Plan: 'processing | complete | failed'."""
        for status in ("pending", "processing", "complete", "failed"):
            ps = PipelineState(book_id="test", status=status)
            assert ps.status == status

    def test_batch_progress_tracking(self):
        """Plan: 'Progress tracking: stage + batch-level granularity'."""
        ps = PipelineState(book_id="test")
        ps.current_batch = 2
        ps.total_batches = 15
        d = ps.to_dict()
        assert d["current_batch"] == 2
        assert d["total_batches"] == 15


# ---------------------------------------------------------------------------
# save_state / load_state
# ---------------------------------------------------------------------------

class TestSaveLoadState:
    def test_save_creates_file(self, tmp_path):
        state = PipelineState.new("saveme", ["s1"])
        path = tmp_path / "state.json"
        save_state(state, path)
        assert path.exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        state = PipelineState.new("deep", ["s1"])
        path = tmp_path / "a" / "b" / "c" / "state.json"
        save_state(state, path)
        assert path.exists()

    def test_load_reads_saved_state(self, tmp_path):
        state = PipelineState.new("loadme", ["s1", "s2"])
        state.status = "processing"
        state.stages["s1"] = StageStatus(status="complete", duration_seconds=5.0)
        path = tmp_path / "state.json"
        save_state(state, path)

        loaded = load_state(path)
        assert loaded.book_id == "loadme"
        assert loaded.status == "processing"
        assert loaded.stages["s1"].status == "complete"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_state(tmp_path / "nope.json")

    def test_load_corrupted_raises(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_state(path)

    def test_atomic_write_no_tmp_leftover(self, tmp_path):
        """Atomic write: tmp file should be renamed, not left behind."""
        state = PipelineState.new("atomic", ["s1"])
        path = tmp_path / "state.json"
        save_state(state, path)
        tmp_file = path.with_suffix(".json.tmp")
        assert not tmp_file.exists()

    def test_overwrite_existing(self, tmp_path):
        path = tmp_path / "state.json"
        state1 = PipelineState.new("v1", ["s1"])
        state1.status = "processing"
        save_state(state1, path)

        state2 = PipelineState.new("v2", ["s1"])
        state2.status = "complete"
        save_state(state2, path)

        loaded = load_state(path)
        assert loaded.book_id == "v2"
        assert loaded.status == "complete"

    def test_full_roundtrip_with_all_fields(self, tmp_path):
        """Plan: all intermediate outputs saved. Full state roundtrip."""
        state = PipelineState(
            book_id="christmas_carol",
            status="processing",
            stages={
                "parse_epub": StageStatus(status="complete", duration_seconds=2.1),
                "run_booknlp": StageStatus(status="complete", duration_seconds=340.5),
                "resolve_coref": StageStatus(status="complete", duration_seconds=5.2),
                "discover_ontology": StageStatus(status="complete", duration_seconds=12.8),
                "review_ontology": StageStatus(status="complete", duration_seconds=0.0),
                "run_cognee_batches": StageStatus(status="running"),
                "validate": StageStatus(status="pending"),
            },
            current_batch=2,
            total_batches=2,
            ready_for_query=False,
        )

        path = tmp_path / "state.json"
        save_state(state, path)
        loaded = load_state(path)

        assert loaded.book_id == "christmas_carol"
        assert loaded.status == "processing"
        assert loaded.current_batch == 2
        assert loaded.total_batches == 2
        assert loaded.ready_for_query is False
        assert loaded.stages["parse_epub"].duration_seconds == 2.1
        assert loaded.stages["run_cognee_batches"].status == "running"
        assert loaded.stages["validate"].status == "pending"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_saves(self, tmp_path):
        """Multiple threads saving state should not corrupt the file."""
        path = tmp_path / "concurrent.json"
        errors: list[Exception] = []

        def save_fn(book_id: str):
            try:
                for i in range(20):
                    state = PipelineState.new(book_id, ["s1"])
                    state.current_batch = i
                    save_state(state, path)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=save_fn, args=(f"book_{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # File should be valid JSON after all writes
        loaded = load_state(path)
        assert loaded.book_id is not None

    def test_concurrent_save_and_load(self, tmp_path):
        """Save and load from multiple threads should not crash."""
        path = tmp_path / "rw.json"
        state = PipelineState.new("init", ["s1"])
        save_state(state, path)

        errors: list[Exception] = []

        def writer():
            try:
                for i in range(20):
                    s = PipelineState.new("writer", ["s1"])
                    s.current_batch = i
                    save_state(s, path)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    load_state(path)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# JSON output structure matches plan
# ---------------------------------------------------------------------------

class TestJsonStructureMatchesPlan:
    def test_status_response_shape(self):
        """Plan shows specific JSON shape for GET /books/{id}/status."""
        state = PipelineState(
            book_id="christmas_carol",
            status="processing",
            stages={
                "epub_parsing": StageStatus(status="complete", duration_seconds=2.1),
                "cognee_ingestion": StageStatus(status="running"),
                "validation": StageStatus(status="pending"),
            },
            current_batch=2,
            total_batches=2,
            ready_for_query=False,
        )
        d = state.to_dict()

        # Verify structure
        assert isinstance(d["book_id"], str)
        assert isinstance(d["status"], str)
        assert isinstance(d["stages"], dict)
        assert isinstance(d["ready_for_query"], bool)
        for stage_name, stage_data in d["stages"].items():
            assert "status" in stage_data
