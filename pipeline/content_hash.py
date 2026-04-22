"""Content-hash dedupe for EPUB uploads.

Maintains data/processed/_content_hashes.json mapping sha256(EPUB bytes)
to an existing book_id whose pipeline is complete. Atomic writes via
tempfile + os.replace.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from loguru import logger


MANIFEST_FILENAME = "_content_hashes.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_path(processed_dir: Path | str) -> Path:
    return Path(processed_dir) / MANIFEST_FILENAME


def load_manifest(processed_dir: Path | str) -> dict[str, str]:
    path = _manifest_path(processed_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Content-hash manifest at {} is not a JSON object; ignoring", path)
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Content-hash manifest at {} unreadable: {}; ignoring", path, exc)
        return {}


def write_manifest_atomic(processed_dir: Path | str, manifest: dict[str, str]) -> None:
    Path(processed_dir).mkdir(parents=True, exist_ok=True)
    path = _manifest_path(processed_dir)
    fd, tmp = tempfile.mkstemp(prefix="_content_hashes.", suffix=".tmp", dir=str(processed_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def lookup_existing_book(processed_dir: Path | str, sha256_hex: str) -> str | None:
    """Return an existing book_id for this sha256 iff its pipeline is ready_for_query."""
    from models.pipeline_state import load_state  # local import — avoid cycle

    manifest = load_manifest(processed_dir)
    book_id = manifest.get(sha256_hex)
    if not book_id:
        return None
    state_path = Path(processed_dir) / book_id / "pipeline_state.json"
    if not state_path.exists():
        return None
    try:
        state = load_state(state_path)
    except (json.JSONDecodeError, KeyError, OSError):
        return None
    return book_id if state.ready_for_query else None


def record_book(processed_dir: Path | str, sha256_hex: str, book_id: str) -> None:
    manifest = load_manifest(processed_dir)
    manifest[sha256_hex] = book_id
    write_manifest_atomic(processed_dir, manifest)
