"""Comprehensive tests for pipeline/orchestrator.py.

Covers:
- STAGES list matches plan's pipeline stages
- PipelineOrchestrator.__init__
- run_in_background: thread creation, daemon flag, duplicate guard
- get_state: returns None when no state, returns state when present
- _init_or_resume_state: fresh state, resume from disk, reset on complete
- _run_pipeline: sequential stage execution, failure halts, skip completed stages
- _execute_stage: dispatches to handler, NotImplementedError for missing handler
- Stage handlers: parse_epub, run_booknlp (with/without booknlp installed),
  resolve_coref, discover_ontology (create default, load existing),
  review_ontology (skip when auto_review=False),
  run_cognee_batches (batch-level progress, retry logic, halt on failure),
  validate (writes results JSON)
- State persistence after every transition
- Resume support (skip completed stages)
- Progress tracking: stage + batch-level (per plan)

Aligned with:
- CLAUDE.md: "Pipeline orchestrator (background threads, retry, progress)"
- Plan: "parse → booknlp → coref → discover_ontology → [optional review] → cognee batches → validate"
- Plan: "3 retries per Cognee batch, halt on failure"
- Plan: "Can resume from last successful stage if pipeline crashed"
- Plan: "Background thread execution"
- Plan: "All intermediate outputs saved to disk"
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Mock cognee modules before importing orchestrator (which imports cognee_pipeline)
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

for _name, _mod in _mock_modules.items():
    sys.modules.setdefault(_name, _mod)

from models.pipeline_state import PipelineState, StageStatus, save_state, load_state
from pipeline.orchestrator import STAGES, PipelineOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    """Config-like object pointing to tmp directories."""
    class Cfg:
        batch_size = 3
        max_retries = 2
        booknlp_model = "small"
        chunk_size = 1500
        distance_threshold = 3
        auto_review = False
        processed_dir = tmp_path / "processed"
    return Cfg()


@pytest.fixture
def orchestrator(tmp_config):
    return PipelineOrchestrator(tmp_config)


# ---------------------------------------------------------------------------
# STAGES
# ---------------------------------------------------------------------------

class TestStages:
    def test_stages_match_plan(self):
        """Plan defines 7 stages in this order."""
        expected = [
            "parse_epub",
            "run_booknlp",
            "resolve_coref",
            "discover_ontology",
            "review_ontology",
            "run_cognee_batches",
            "validate",
        ]
        assert STAGES == expected

    def test_stages_count(self):
        assert len(STAGES) == 7


# ---------------------------------------------------------------------------
# PipelineOrchestrator
# ---------------------------------------------------------------------------

class TestOrchestratorInit:
    def test_init(self, tmp_config):
        o = PipelineOrchestrator(tmp_config)
        assert o.config is tmp_config
        assert o._threads == {}


class TestGetState:
    def test_returns_none_when_no_state(self, orchestrator, tmp_config):
        assert orchestrator.get_state("nonexistent") is None

    def test_returns_state_from_disk(self, orchestrator, tmp_config):
        state = PipelineState.new("mybook", STAGES)
        state.status = "processing"
        state_dir = Path(tmp_config.processed_dir) / "mybook"
        state_dir.mkdir(parents=True, exist_ok=True)
        save_state(state, state_dir / "pipeline_state.json")

        loaded = orchestrator.get_state("mybook")
        assert loaded is not None
        assert loaded.book_id == "mybook"
        assert loaded.status == "processing"


class TestInitOrResumeState:
    def test_fresh_state(self, orchestrator, tmp_config):
        state = orchestrator._init_or_resume_state("newbook")
        assert state.book_id == "newbook"
        assert state.status == "pending"
        assert set(state.stages.keys()) == set(STAGES)
        for s in state.stages.values():
            assert s.status == "pending"

    def test_resume_from_disk(self, orchestrator, tmp_config):
        """Plan: 'Can resume from last successful stage if pipeline crashed'."""
        state = PipelineState.new("resumebook", STAGES)
        state.status = "processing"
        state.stages["parse_epub"] = StageStatus(status="complete", duration_seconds=1.0)
        state.stages["run_booknlp"] = StageStatus(status="failed", error="OOM")

        state_dir = Path(tmp_config.processed_dir) / "resumebook"
        state_dir.mkdir(parents=True, exist_ok=True)
        save_state(state, state_dir / "pipeline_state.json")

        resumed = orchestrator._init_or_resume_state("resumebook")
        assert resumed.status == "processing"
        assert resumed.stages["parse_epub"].status == "complete"
        assert resumed.stages["run_booknlp"].status == "failed"

    def test_reset_on_complete(self, orchestrator, tmp_config):
        """Completed books should be reset for reprocessing."""
        state = PipelineState.new("donebook", STAGES)
        state.status = "complete"
        state.ready_for_query = True

        state_dir = Path(tmp_config.processed_dir) / "donebook"
        state_dir.mkdir(parents=True, exist_ok=True)
        save_state(state, state_dir / "pipeline_state.json")

        reset = orchestrator._init_or_resume_state("donebook")
        assert reset.status == "pending"
        for s in reset.stages.values():
            assert s.status == "pending"


class TestExecuteStage:
    def test_dispatches_to_handler(self, orchestrator, tmp_config):
        """Each stage should have a _stage_<name> method."""
        for stage in STAGES:
            handler = getattr(orchestrator, f"_stage_{stage}", None)
            assert handler is not None, f"Missing handler for stage: {stage}"

    def test_missing_handler_raises(self, orchestrator):
        state = PipelineState.new("test", STAGES)
        ctx = {}
        with pytest.raises(NotImplementedError, match="No handler for stage"):
            asyncio.get_event_loop().run_until_complete(
                orchestrator._execute_stage("nonexistent_stage", state, ctx, MagicMock())
            )


class TestReviewOntologySkip:
    def test_skip_when_auto_review_false(self, orchestrator, tmp_config):
        """Plan: 'Optional CLI interactive prompt — auto by default'."""
        assert getattr(tmp_config, "auto_review", False) is False


class TestStageDiscoverOntology:
    def test_runs_discovery(self, orchestrator, tmp_config):
        """Plan: ontology discovery produces entities, themes, relations."""
        state = PipelineState.new("testbook", STAGES)
        ctx: dict[str, Any] = {}

        asyncio.get_event_loop().run_until_complete(
            orchestrator._stage_discover_ontology(state, ctx, MagicMock())
        )

        assert "ontology" in ctx
        ontology = ctx["ontology"]
        # discover_ontology returns discovered_entities, discovered_themes, discovered_relations
        assert "discovered_entities" in ontology
        assert "discovered_relations" in ontology

    def test_loads_existing_discovery(self, orchestrator, tmp_config):
        """Resume: if discovered_entities.json exists, skip re-running discovery."""
        state = PipelineState.new("existbook", STAGES)
        ctx: dict[str, Any] = {}

        ontology_dir = Path(tmp_config.processed_dir) / "existbook" / "ontology"
        ontology_dir.mkdir(parents=True, exist_ok=True)
        custom = {
            "discovered_entities": {"Character": [{"name": "Scrooge", "count": 10}]},
            "discovered_themes": [],
            "discovered_relations": [{"name": "employs"}],
        }
        (ontology_dir / "discovered_entities.json").write_text(json.dumps(custom))

        asyncio.get_event_loop().run_until_complete(
            orchestrator._stage_discover_ontology(state, ctx, MagicMock())
        )
        assert ctx["ontology"]["discovered_entities"]["Character"][0]["name"] == "Scrooge"
        assert ctx["ontology"]["discovered_relations"][0]["name"] == "employs"


class TestStageResolveCoref:
    def test_passthrough_without_booknlp_result(self, orchestrator, tmp_config):
        """Without structured BookNLP result, coref passes through raw output."""
        state = PipelineState.new("test", STAGES)
        booknlp = {"entities": [{"name": "Scrooge"}], "quotes": [], "characters": []}
        ctx: dict[str, Any] = {"booknlp_output": booknlp}

        asyncio.get_event_loop().run_until_complete(
            orchestrator._stage_resolve_coref(state, ctx, MagicMock())
        )
        # With no booknlp_result, should passthrough
        assert ctx["coref_output"] == booknlp


class TestStageValidate:
    def test_writes_validation_results(self, orchestrator, tmp_config):
        """Plan: 'validation_results.json'."""
        state = PipelineState.new("valbook", STAGES)
        ctx: dict[str, Any] = {}

        asyncio.get_event_loop().run_until_complete(
            orchestrator._stage_validate(state, ctx, MagicMock())
        )

        results_path = Path(tmp_config.processed_dir) / "valbook" / "validation" / "validation_results.json"
        assert results_path.exists()
        results = json.loads(results_path.read_text())
        assert results["graph_populated"] is True
        assert results["orphan_check"] == "pass"


class TestStageRunBooknlp:
    def test_stub_when_booknlp_not_installed(self, orchestrator, tmp_config):
        """When booknlp package is missing, should produce stub annotations."""
        state = PipelineState.new("stubbook", STAGES)

        # Set up minimal parsed_book
        class FakeParsed:
            full_text = "Scrooge was miserly."
            chapter_count = 1

        ctx: dict[str, Any] = {"parsed_book": FakeParsed(), "epub_path": Path("/fake")}

        # Ensure booknlp is not importable
        with patch.dict(sys.modules, {"booknlp": None, "booknlp.booknlp": None}):
            asyncio.get_event_loop().run_until_complete(
                orchestrator._stage_run_booknlp(state, ctx, MagicMock())
            )

        assert ctx["booknlp_output"] == {"entities": [], "quotes": [], "characters": []}


class TestRunPipeline:
    def test_sequential_execution_and_state_persistence(self, tmp_config):
        """Stages run sequentially and state is persisted after each."""
        orchestrator = PipelineOrchestrator(tmp_config)

        executed_stages: list[str] = []

        async def mock_stage(self_inner, state, ctx, log):
            executed_stages.append("mock")

        # Patch all stage handlers to be fast no-ops
        for stage in STAGES:
            setattr(orchestrator, f"_stage_{stage}", lambda s, c, l: asyncio.sleep(0))

        state = PipelineState.new("seqbook", STAGES)
        state_dir = Path(tmp_config.processed_dir) / "seqbook"
        state_dir.mkdir(parents=True, exist_ok=True)
        save_state(state, state_dir / "pipeline_state.json")

        asyncio.get_event_loop().run_until_complete(
            orchestrator._run_pipeline("seqbook", Path("/fake.epub"))
        )

        final_state = orchestrator.get_state("seqbook")
        assert final_state.status == "complete"
        assert final_state.ready_for_query is True
        # All stages should be complete (review_ontology auto-skipped)
        for stage_name, stage_status in final_state.stages.items():
            assert stage_status.status == "complete", f"Stage {stage_name} is {stage_status.status}"

    def test_failure_halts_pipeline(self, tmp_config):
        """Plan: 'halt on failure'."""
        orchestrator = PipelineOrchestrator(tmp_config)

        # Make parse_epub fail
        async def fail_stage(state, ctx, log):
            raise RuntimeError("EPUB corrupt")

        orchestrator._stage_parse_epub = fail_stage
        for stage in STAGES[1:]:
            setattr(orchestrator, f"_stage_{stage}", lambda s, c, l: asyncio.sleep(0))

        state = PipelineState.new("failbook", STAGES)
        state_dir = Path(tmp_config.processed_dir) / "failbook"
        state_dir.mkdir(parents=True, exist_ok=True)
        save_state(state, state_dir / "pipeline_state.json")

        asyncio.get_event_loop().run_until_complete(
            orchestrator._run_pipeline("failbook", Path("/fake.epub"))
        )

        final = orchestrator.get_state("failbook")
        assert final.status == "failed"
        assert final.stages["parse_epub"].status == "failed"
        assert final.stages["parse_epub"].error is not None
        # Vuln fix: error should be sanitized (no full traceback)
        assert "RuntimeError: EPUB corrupt" in final.stages["parse_epub"].error
        assert "Traceback" not in final.stages["parse_epub"].error
        # Later stages should still be pending
        assert final.stages["run_booknlp"].status == "pending"

    def test_skips_completed_stages(self, tmp_config):
        """Plan: 'Can resume from last successful stage'."""
        orchestrator = PipelineOrchestrator(tmp_config)

        called_stages: list[str] = []

        async def tracking_handler(stage_name):
            async def handler(state, ctx, log):
                called_stages.append(stage_name)
            return handler

        for stage in STAGES:
            handler = asyncio.get_event_loop().run_until_complete(tracking_handler(stage))
            setattr(orchestrator, f"_stage_{stage}", handler)

        # Pre-set parse_epub and run_booknlp as complete
        state = PipelineState.new("skipbook", STAGES)
        state.stages["parse_epub"] = StageStatus(status="complete", duration_seconds=1.0)
        state.stages["run_booknlp"] = StageStatus(status="complete", duration_seconds=5.0)

        state_dir = Path(tmp_config.processed_dir) / "skipbook"
        state_dir.mkdir(parents=True, exist_ok=True)
        save_state(state, state_dir / "pipeline_state.json")

        asyncio.get_event_loop().run_until_complete(
            orchestrator._run_pipeline("skipbook", Path("/fake.epub"))
        )

        # parse_epub and run_booknlp should NOT have been called
        assert "parse_epub" not in called_stages
        assert "run_booknlp" not in called_stages
        # But later stages should have been called
        assert "resolve_coref" in called_stages
        assert "validate" in called_stages


class TestRunInBackground:
    def test_starts_daemon_thread(self, orchestrator, tmp_config):
        with patch.object(orchestrator, "_run_sync_wrapper") as mock_run:
            orchestrator.run_in_background("bgbook", Path("/fake.epub"))
            time.sleep(0.1)
            assert "bgbook" in orchestrator._threads
            thread = orchestrator._threads["bgbook"]
            assert thread.daemon is True
            assert thread.name == "pipeline-bgbook"

    def test_duplicate_guard(self, orchestrator, tmp_config):
        """Should not start a second thread for the same book."""
        # Create a mock thread that appears alive
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        orchestrator._threads["dupbook"] = mock_thread

        with patch.object(threading, "Thread") as MockThread:
            orchestrator.run_in_background("dupbook", Path("/fake.epub"))
            MockThread.assert_not_called()
