"""Pipeline state persistence — thread-safe load/save to JSON.

Provides ``PipelineState`` and ``StageStatus`` dataclasses plus helper
functions for atomic reads and writes so the orchestrator and API server
can safely share state via the filesystem.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# Module-level lock for thread-safe file I/O
_file_lock = threading.Lock()


@dataclass
class StageStatus:
    """Status of an individual pipeline stage."""

    status: str = "pending"  # "pending" | "running" | "complete" | "failed"
    duration_seconds: float | None = None
    error: str | None = None

    def to_dict(self, sanitize: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.duration_seconds is not None:
            d["duration_seconds"] = self.duration_seconds
        if self.error is not None:
            if sanitize:
                # Strip internal paths and stack traces from API responses
                lines = self.error.strip().splitlines()
                d["error"] = lines[-1] if lines else "Unknown error"
            else:
                d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageStatus:
        return cls(
            status=data.get("status", "pending"),
            duration_seconds=data.get("duration_seconds"),
            error=data.get("error"),
        )


@dataclass
class PipelineState:
    """Full pipeline state for a single book, serializable to JSON."""

    book_id: str
    status: str = "pending"  # "pending" | "processing" | "complete" | "failed"
    stages: dict[str, StageStatus] = field(default_factory=dict)
    current_batch: int | None = None
    total_batches: int | None = None
    ready_for_query: bool = False

    @classmethod
    def new(cls, book_id: str, stage_names: list[str]) -> PipelineState:
        """Create a fresh pipeline state with all stages set to pending."""
        stages = {name: StageStatus() for name in stage_names}
        return cls(book_id=book_id, stages=stages)

    def to_dict(self, sanitize: bool = False) -> dict[str, Any]:
        """Serialize to a plain dict (JSON-safe).

        Args:
            sanitize: If True, strip stack traces from error messages
                (safe for API responses). Full traces are still saved on disk.
        """
        return {
            "book_id": self.book_id,
            "status": self.status,
            "stages": {k: v.to_dict(sanitize=sanitize) for k, v in self.stages.items()},
            "current_batch": self.current_batch,
            "total_batches": self.total_batches,
            "ready_for_query": self.ready_for_query,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineState:
        """Deserialize from a plain dict."""
        stages_raw = data.get("stages", {})
        stages = {k: StageStatus.from_dict(v) for k, v in stages_raw.items()}
        return cls(
            book_id=data["book_id"],
            status=data.get("status", "pending"),
            stages=stages,
            current_batch=data.get("current_batch"),
            total_batches=data.get("total_batches"),
            ready_for_query=data.get("ready_for_query", False),
        )


def save_state(state: PipelineState, path: Path) -> None:
    """Atomically write pipeline state to a JSON file.

    Writes to a temporary file first, then renames, so a crash during
    write never corrupts the state file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")

    payload = json.dumps(state.to_dict(), indent=2)

    with _file_lock:
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(path)

    logger.debug("Saved pipeline state to {}", path)


def load_state(path: Path) -> PipelineState:
    """Load pipeline state from a JSON file (thread-safe read).

    Args:
        path: Path to the pipeline_state.json file.

    Returns:
        Deserialized ``PipelineState``.

    Raises:
        FileNotFoundError: If the state file doesn't exist.
        json.JSONDecodeError: If the file is corrupted.
    """
    path = Path(path)
    with _file_lock:
        raw = path.read_text(encoding="utf-8")

    data = json.loads(raw)
    state = PipelineState.from_dict(data)
    logger.debug("Loaded pipeline state from {} (status={})", path, state.status)
    return state
