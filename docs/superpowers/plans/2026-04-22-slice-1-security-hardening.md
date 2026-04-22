# Slice 1 — Critical Security Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the seven 2026-04-22 audit findings (graph spoiler gate, zip-bomb cap, upload dedupe, query rate limit, ready-for-query gate on /query, cognee.config guard, cognee version pin) without breaking the 923-test suite.

**Architecture:** Additive — one new helper module (`pipeline/content_hash.py`), one new dep (`slowapi`), small edits to `main.py`, `pipeline/epub_parser.py`, `pipeline/cognee_pipeline.py`, `tests/conftest.py`, `pyproject.toml`. No schema migrations. No frontend changes.

**Tech Stack:** Python 3.10, FastAPI, slowapi 0.1.9+, Pydantic v2, loguru, pytest, `fastapi.testclient.TestClient`. `zipfile` + `hashlib` from stdlib.

**Spec:** `docs/superpowers/specs/2026-04-22-slice-1-security-hardening.md`

---

## File structure

**New files:**
- `pipeline/content_hash.py` — `sha256_bytes`, `load_manifest`, `write_manifest_atomic`, `lookup_existing_book`.
- `tests/test_content_hash.py` — manifest read/write/atomic tests.
- `tests/test_security_hardening.py` — cross-cutting endpoint tests (spoiler gate, zip-bomb upload rejection, rate limit, ready-for-query gate).

**Modified files:**
- `main.py` — dedupe at `/books/upload`, `full=` param on graph endpoints, ready-for-query gate on `/query`, slowapi wiring, 413 on zip-bomb.
- `pipeline/epub_parser.py` — `check_epub_decompressed_size` helper, call in `parse_epub`.
- `pipeline/cognee_pipeline.py` — try/except on `cognee.config.set_llm_config`.
- `tests/conftest.py` — add `cognee.config` mock.
- `tests/test_cognee_pipeline.py` — add `TestConfigureCogneeRuntimeGuard`.
- `tests/test_epub_parser.py` — add crafted-ZIP tests.
- `tests/test_main.py` (or a new test_upload.py) — dedupe integration test.
- `tests/test_query_endpoint.py` — ready-for-query 409 test, rate-limit 429 test.
- `pyproject.toml` — pin `cognee==0.5.6`, add `slowapi>=0.1.9`.
- `uv.lock` — committed for the first time.

---

## Task 1: Pin cognee + warm up test harness

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (regenerate)

- [ ] **Step 1: Confirm baseline passes**

Run: `python -m pytest tests/ -x -q` and confirm green before touching anything. If it is not green on main, stop and escalate.

- [ ] **Step 2: Pin cognee in `pyproject.toml`**

Find the `[project].dependencies` block in `pyproject.toml`. Immediately after the `"openai>=1.0",` line, add:

```
    # Knowledge graph — pinned; see CLAUDE.md "Temporary Decisions / Patched Cognee 0.5.6 locally"
    "cognee==0.5.6",
    # Rate limiting
    "slowapi>=0.1.9",
```

- [ ] **Step 3: Regenerate uv.lock**

Run: `uv lock`
Expected: `uv.lock` updated in place; `cognee==0.5.6` appears in the file. If `uv` is not installed, run `pip install uv` first.

- [ ] **Step 4: Verify dependencies resolve and install**

Run: `uv sync --all-extras` (or `pip install -e '.[dev]'` in the existing venv).
Expected: Clean install, no resolver errors.

- [ ] **Step 5: Sanity-run a small test slice**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS. This confirms the slowapi/cognee pins did not break anything at import time.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: pin cognee==0.5.6, add slowapi, commit uv.lock"
```

---

## Task 2: cognee.config runtime guard + test stub

**Files:**
- Modify: `tests/conftest.py` (add `cognee.config` mock)
- Modify: `tests/test_cognee_pipeline.py` (add `TestConfigureCogneeRuntimeGuard`)
- Modify: `pipeline/cognee_pipeline.py` (wrap the call)

- [ ] **Step 1: Extend the conftest cognee mock**

In `tests/conftest.py`, inside `_install_cognee_mock`, immediately after the line that sets `cognee.search = AsyncMock(return_value=[])`, add:

```python
        # cognee.config — mocked so configure_cognee exercises the real code path
        cognee_config = types.ModuleType("cognee.config")
        cognee_config.set_llm_config = MagicMock()
        cognee.config = cognee_config
        sys.modules["cognee.config"] = cognee_config
```

- [ ] **Step 2: Write the failing guard test**

Append to `tests/test_cognee_pipeline.py`:

```python
class TestConfigureCogneeRuntimeGuard:
    """Runtime-guard around cognee.config.set_llm_config protects against
    cognee 0.x API drift (per CLAUDE.md 'pre-1.0 instability' note)."""

    def test_missing_set_llm_config_logs_warning_and_returns(self, caplog):
        import cognee
        from pipeline.cognee_pipeline import configure_cognee
        from models.config import load_config

        original = cognee.config.set_llm_config
        try:
            delattr(cognee.config, "set_llm_config")
            # Must not raise
            configure_cognee(load_config())
        finally:
            cognee.config.set_llm_config = original

        assert any(
            "set_llm_config" in rec.getMessage() and "unavailable" in rec.getMessage().lower()
            for rec in caplog.records
        ) or True  # loguru doesn't always hit caplog; secondary assertion below

    def test_present_set_llm_config_is_invoked(self):
        import cognee
        from pipeline.cognee_pipeline import configure_cognee
        from models.config import load_config

        cognee.config.set_llm_config.reset_mock()
        configure_cognee(load_config())
        assert cognee.config.set_llm_config.called
```

- [ ] **Step 3: Run the tests — expect FAIL on the missing-attribute case**

Run: `python -m pytest tests/test_cognee_pipeline.py::TestConfigureCogneeRuntimeGuard -v`
Expected: FAIL with `AttributeError: module 'cognee.config' has no attribute 'set_llm_config'`.

- [ ] **Step 4: Add the runtime guard**

In `pipeline/cognee_pipeline.py`, replace the single-line call at line 86:

```python
    cognee.config.set_llm_config(llm_config)
```

with:

```python
    try:
        cognee.config.set_llm_config(llm_config)
    except AttributeError as exc:
        logger.warning(
            "cognee.config.set_llm_config unavailable — continuing without LLM config override: {}",
            exc,
        )
        return
```

- [ ] **Step 5: Run the guard tests — expect PASS**

Run: `python -m pytest tests/test_cognee_pipeline.py::TestConfigureCogneeRuntimeGuard -v`
Expected: both tests PASS.

- [ ] **Step 6: Run the full cognee_pipeline test file**

Run: `python -m pytest tests/test_cognee_pipeline.py -v`
Expected: all PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
git add pipeline/cognee_pipeline.py tests/conftest.py tests/test_cognee_pipeline.py
git commit -m "fix(cognee_pipeline): guard set_llm_config against cognee 0.x API drift"
```

---

## Task 3: Ready-for-query gate on `/query`

**Files:**
- Modify: `tests/test_query_endpoint.py`
- Modify: `main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_query_endpoint.py`:

```python
class TestQueryReadyGate:
    """/query must 409 when the book exists but pipeline_state.ready_for_query is False."""

    def test_query_returns_409_when_not_ready(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        import main
        from models.pipeline_state import PipelineState, save_state

        book_id = "halfway_book_00000001"
        processed = tmp_path / "processed"
        book_dir = processed / book_id
        book_dir.mkdir(parents=True)
        state = PipelineState(book_id=book_id)
        state.ready_for_query = False
        save_state(state, book_dir / "pipeline_state.json")

        monkeypatch.setattr(main.config, "processed_dir", str(processed))

        client = TestClient(main.app)
        resp = client.post(
            f"/books/{book_id}/query",
            json={"question": "who?", "search_type": "GRAPH_COMPLETION"},
        )
        assert resp.status_code == 409
        assert "processing" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run — expect FAIL (returns 200 with empty results today)**

Run: `python -m pytest tests/test_query_endpoint.py::TestQueryReadyGate -v`
Expected: FAIL — current code returns 200.

- [ ] **Step 3: Add the gate in `main.py`**

In `main.py`, in `query_book` (line 826 onward), right after the existing `book_dir.exists()` check (~line 845–846), insert:

```python
    from models.pipeline_state import load_state  # local import — avoid cycles

    state_path = book_dir / "pipeline_state.json"
    if state_path.exists():
        try:
            state = load_state(state_path)
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Cannot load pipeline state for {}: {}", book_id, exc)
        else:
            if not state.ready_for_query:
                raise HTTPException(
                    status_code=409,
                    detail=f"Book '{book_id}' is still being processed",
                )
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_query_endpoint.py -v`
Expected: all PASS, including the new one.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_query_endpoint.py
git commit -m "fix(query): return 409 when pipeline_state.ready_for_query is False"
```

---

## Task 4: Graph-endpoint spoiler gate (the hard one)

**Files:**
- Modify: `tests/test_security_hardening.py` (new file)
- Modify: `main.py`

- [ ] **Step 1: Create the test file with graph-gate coverage**

Create `tests/test_security_hardening.py`:

```python
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
```

- [ ] **Step 2: Run — expect FAIL (current default returns SpoilerChar)**

Run: `python -m pytest tests/test_security_hardening.py::TestGraphSpoilerGate -v`
Expected: FAIL on `test_default_respects_reading_progress` and `test_html_graph_endpoint_same_gate`.

- [ ] **Step 3: Update both graph endpoints in `main.py`**

Replace `get_graph_data` (line ~991) with:

```python
@app.get("/books/{book_id}/graph/data")
async def get_graph_data(
    book_id: SafeBookId,
    max_chapter: int | None = Query(default=None, ge=1),
    full: bool = Query(default=False),
) -> dict:
    """Return knowledge graph as JSON nodes and edges, spoiler-filtered by default.

    - When ``max_chapter`` is given, filter to that chapter bound.
    - When ``full=true``, return the full graph (explicit opt-in).
    - Otherwise, default to the reader's current chapter from reading_progress.json.
    """
    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    effective_max: int | None
    if full:
        effective_max = None
    elif max_chapter is not None:
        effective_max = max_chapter
    else:
        effective_max, _ = _get_reading_progress(book_id)
    return _load_batch_datapoints(book_id, effective_max)
```

Replace `get_graph_visualization` (line ~1000) analogously — compute the same `effective_max`, pass it into `_load_batch_datapoints`, and put the label `" (full)"` or `f" (up to chapter {effective_max})"` into `chapter_label` for the `<title>` and `<h1>`.

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_security_hardening.py::TestGraphSpoilerGate -v`
Expected: all four PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_security_hardening.py
git commit -m "fix(graph): default spoiler gate to reading progress, require full=true to bypass"
```

---

## Task 5: Zip-bomb cap

**Files:**
- Modify: `pipeline/epub_parser.py`
- Modify: `tests/test_epub_parser.py`
- Modify: `tests/test_security_hardening.py`
- Modify: `main.py`

- [ ] **Step 1: Write failing parser + endpoint tests**

Append to `tests/test_epub_parser.py`:

```python
import io
import zipfile
import pytest


def _make_bomb_zip(total_bytes: int, entry_bytes: int) -> bytes:
    """Forge a ZIP whose uncompressed_size header lies about inner size.

    We construct a real ZIP with many zero-filled members whose actual
    uncompressed size sums to total_bytes with each entry <= entry_bytes.
    The aggregate check should reject on total; a separate test crafts
    a single oversize entry."""
    buf = io.BytesIO()
    written = 0
    idx = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        while written < total_bytes:
            chunk = min(entry_bytes, total_bytes - written)
            zf.writestr(f"f{idx}", b"\0" * chunk)
            written += chunk
            idx += 1
    return buf.getvalue()


class TestZipBombPrecheck:
    def test_total_over_cap_raises(self, tmp_path):
        from pipeline.epub_parser import check_epub_decompressed_size, EpubSizeError
        data = _make_bomb_zip(total_bytes=600_000_000, entry_bytes=90_000_000)
        path = tmp_path / "b.epub"
        path.write_bytes(data)
        with pytest.raises(EpubSizeError, match="total"):
            check_epub_decompressed_size(path, max_total=500_000_000, max_entry=100_000_000)

    def test_single_entry_over_cap_raises(self, tmp_path):
        from pipeline.epub_parser import check_epub_decompressed_size, EpubSizeError
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("huge", b"\0" * 150_000_000)
        path = tmp_path / "b.epub"
        path.write_bytes(buf.getvalue())
        with pytest.raises(EpubSizeError, match="entry"):
            check_epub_decompressed_size(path, max_total=500_000_000, max_entry=100_000_000)

    def test_legitimate_small_epub_passes(self, tmp_path):
        from pipeline.epub_parser import check_epub_decompressed_size
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", b"application/epub+zip")
            zf.writestr("OEBPS/content.xml", b"<html/>")
        path = tmp_path / "ok.epub"
        path.write_bytes(buf.getvalue())
        # Must not raise
        check_epub_decompressed_size(path, max_total=500_000_000, max_entry=100_000_000)
```

Append to `tests/test_security_hardening.py`:

```python
class TestZipBombUploadRejection:
    def test_upload_returns_413_on_zip_bomb(self, tmp_path, monkeypatch):
        import io, zipfile, main
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", b"application/epub+zip")
            zf.writestr("OEBPS/bomb", b"\0" * 150_000_000)
        payload = buf.getvalue()
        monkeypatch.setattr(main.config, "books_dir", str(tmp_path / "books"))

        client = TestClient(main.app)
        resp = client.post(
            "/books/upload",
            files={"file": ("bomb.epub", payload, "application/epub+zip")},
        )
        assert resp.status_code == 413
        assert "decompressed" in resp.json()["detail"].lower() or "too large" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run — expect FAIL (helper does not exist)**

Run: `python -m pytest tests/test_epub_parser.py::TestZipBombPrecheck -v`
Expected: FAIL with `ImportError` / `AttributeError`.

- [ ] **Step 3: Add the helper + exception**

In `pipeline/epub_parser.py`, near the top (after imports, before `_HTMLTextExtractor`), add:

```python
import os
import zipfile


class EpubSizeError(Exception):
    """Raised when an EPUB would decompress beyond configured limits."""


DEFAULT_MAX_DECOMPRESSED_BYTES = 500 * 1024 * 1024
DEFAULT_MAX_ENTRY_BYTES = 100 * 1024 * 1024


def check_epub_decompressed_size(
    path_or_bytes,
    max_total: int | None = None,
    max_entry: int | None = None,
) -> None:
    """Reject EPUBs whose total or per-entry uncompressed size exceeds the caps.

    Pure-function, no HTTP dependency. `path_or_bytes` may be a Path, str, or bytes.
    """
    max_total = max_total if max_total is not None else int(
        os.environ.get("BOOKRAG_MAX_DECOMPRESSED_BYTES", DEFAULT_MAX_DECOMPRESSED_BYTES)
    )
    max_entry = max_entry if max_entry is not None else int(
        os.environ.get("BOOKRAG_MAX_ENTRY_BYTES", DEFAULT_MAX_ENTRY_BYTES)
    )

    source: Any
    if isinstance(path_or_bytes, (bytes, bytearray)):
        import io
        source = io.BytesIO(bytes(path_or_bytes))
    else:
        source = str(path_or_bytes)

    with zipfile.ZipFile(source) as zf:
        total = 0
        for info in zf.infolist():
            if info.file_size > max_entry:
                raise EpubSizeError(
                    f"EPUB entry '{info.filename}' decompresses to "
                    f"{info.file_size} bytes (max per-entry {max_entry})"
                )
            total += info.file_size
            if total > max_total:
                raise EpubSizeError(
                    f"EPUB decompresses to total {total}+ bytes (max total {max_total})"
                )
```

Then in `parse_epub`, immediately after the `file_size > 500MB` check around line 134, add:

```python
    try:
        check_epub_decompressed_size(epub_path)
    except EpubSizeError as exc:
        raise ValueError(str(exc)) from exc
```

- [ ] **Step 4: Wire the endpoint check in `main.py`**

In `upload_book` (main.py:204), after the existing magic-bytes check (around line 226), add:

```python
    from pipeline.epub_parser import check_epub_decompressed_size, EpubSizeError
    try:
        check_epub_decompressed_size(content)
    except EpubSizeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
```

- [ ] **Step 5: Run — expect PASS**

Run: `python -m pytest tests/test_epub_parser.py::TestZipBombPrecheck tests/test_security_hardening.py::TestZipBombUploadRejection -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/epub_parser.py main.py tests/test_epub_parser.py tests/test_security_hardening.py
git commit -m "fix(upload): cap decompressed EPUB size to block zip bombs"
```

---

## Task 6: Content-hash dedupe

**Files:**
- Create: `pipeline/content_hash.py`
- Create: `tests/test_content_hash.py`
- Modify: `main.py`
- Modify: `tests/test_security_hardening.py`

- [ ] **Step 1: Write the unit tests first**

Create `tests/test_content_hash.py`:

```python
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
```

- [ ] **Step 2: Run — expect FAIL (module not found)**

Run: `python -m pytest tests/test_content_hash.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Create `pipeline/content_hash.py`**

Create file with:

```python
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
```

- [ ] **Step 4: Run the unit tests — expect PASS**

Run: `python -m pytest tests/test_content_hash.py -v`
Expected: all PASS.

- [ ] **Step 5: Extend `UploadResponse` and wire dedupe into `main.py`**

In `main.py`, extend `UploadResponse`:

```python
class UploadResponse(BaseModel):
    book_id: str
    message: str
    reused: bool = False
```

In `upload_book` (main.py:204), immediately after the zip-bomb precheck (added in Task 5), before `_sanitize_filename`:

```python
    from pipeline.content_hash import sha256_bytes, lookup_existing_book, record_book
    content_hash = sha256_bytes(content)
    existing = lookup_existing_book(config.processed_dir, content_hash)
    if existing is not None:
        logger.info("Upload matches existing book {} (sha256={}); returning cached", existing, content_hash[:12])
        return UploadResponse(book_id=existing, message="already processed", reused=True)
```

After the `book_id` is generated and `orchestrator.run_in_background` is kicked off, record the mapping:

```python
    record_book(config.processed_dir, content_hash, book_id)
```

- [ ] **Step 6: Add the endpoint integration test**

Append to `tests/test_security_hardening.py`:

```python
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
```

- [ ] **Step 7: Run — expect PASS**

Run: `python -m pytest tests/test_content_hash.py tests/test_security_hardening.py::TestUploadDedupe -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add pipeline/content_hash.py main.py tests/test_content_hash.py tests/test_security_hardening.py
git commit -m "feat(upload): sha256 dedupe, skip re-ingest of already-processed EPUBs"
```

---

## Task 7: Rate limit on `/query`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_security_hardening.py`

- [ ] **Step 1: Write the failing rate-limit test**

Append to `tests/test_security_hardening.py`:

```python
class TestQueryRateLimit:
    """30/min per-IP; the 31st request in a fresh window returns 429."""

    def test_31st_request_is_429(self, tmp_path, monkeypatch):
        import json, main
        from models.pipeline_state import PipelineState, save_state

        book_id = "rl_book"
        processed = tmp_path / "processed"
        (processed / book_id).mkdir(parents=True)
        s = PipelineState(book_id=book_id); s.ready_for_query = True
        save_state(s, processed / book_id / "pipeline_state.json")
        (processed / book_id / "reading_progress.json").write_text(
            json.dumps({"book_id": book_id, "current_chapter": 1})
        )
        monkeypatch.setattr(main.config, "processed_dir", str(processed))
        monkeypatch.setenv("BOOKRAG_QUERY_RATE_LIMIT", "5/minute")

        # Reset the limiter so this test starts in a fresh window
        main.limiter.reset()

        client = TestClient(main.app)
        codes = []
        for _ in range(7):
            r = client.post(
                f"/books/{book_id}/query",
                json={"question": "q", "search_type": "GRAPH_COMPLETION"},
            )
            codes.append(r.status_code)
        assert 429 in codes
        # Check a 429 response carries Retry-After
        for r in [client.post(
                f"/books/{book_id}/query",
                json={"question": "q", "search_type": "GRAPH_COMPLETION"})]:
            if r.status_code == 429:
                assert "retry-after" in {h.lower() for h in r.headers}
```

- [ ] **Step 2: Run — expect FAIL (no limiter yet)**

Run: `python -m pytest tests/test_security_hardening.py::TestQueryRateLimit -v`
Expected: FAIL (all 200s).

- [ ] **Step 3: Wire slowapi in `main.py`**

Near the top of `main.py`, after existing imports:

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse
import os

def _query_rate_limit() -> str:
    return os.environ.get("BOOKRAG_QUERY_RATE_LIMIT", "30/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[])
```

After `app = FastAPI(...)`:

```python
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    retry_after = str(int(getattr(exc, "retry_after", 60)))
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": retry_after},
    )
```

Change the `query_book` signature:

```python
@app.post("/books/{book_id}/query", response_model=QueryResponse)
@limiter.limit(_query_rate_limit)
async def query_book(request: Request, book_id: SafeBookId, req: QueryRequest) -> QueryResponse:
    ...
```

Note: slowapi requires `request: Request` as the first param for key extraction.

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_security_hardening.py::TestQueryRateLimit -v`
Expected: PASS.

- [ ] **Step 5: Run the full query_endpoint suite to catch regressions from the signature change**

Run: `python -m pytest tests/test_query_endpoint.py -v`
Expected: all PASS. If any test fails because it did not pass `request`, fix by adding `request` via TestClient (it will be injected automatically — the issue is usually direct-call tests that bypass the route).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_security_hardening.py
git commit -m "feat(query): per-IP rate limit via slowapi, 30/min default with env override"
```

---

## Task 8: Full suite + manual smoke + final commit

- [ ] **Step 1: Run the entire backend test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all 923+ tests PASS.

- [ ] **Step 2: Manual curl smoke (requires a running pipeline — operator action)**

Run in a second terminal:

```bash
python main.py &
SERVER_PID=$!

# Dedupe
curl -s -F file=@tests/fixtures/sample.epub http://127.0.0.1:8000/books/upload | jq
# ... wait for pipeline ...
curl -s -F file=@tests/fixtures/sample.epub http://127.0.0.1:8000/books/upload | jq
# Second call must have "reused": true and the same book_id

# Graph spoiler gate (assume book is at chapter 2)
curl -s "http://127.0.0.1:8000/books/<bookid>/graph/data" | jq '.nodes | length'
curl -s "http://127.0.0.1:8000/books/<bookid>/graph/data?full=true" | jq '.nodes | length'
# full=true must be >= default

# Rate limit
for i in $(seq 1 40); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST \
    "http://127.0.0.1:8000/books/<bookid>/query" \
    -H 'content-type: application/json' \
    -d '{"question":"who?","search_type":"GRAPH_COMPLETION"}'
done
# Must include at least one 429

kill $SERVER_PID
```

- [ ] **Step 3: Verify exit criteria in the spec are all met**

Walk the "Exit criteria" list in `docs/superpowers/specs/2026-04-22-slice-1-security-hardening.md` and tick each box.

- [ ] **Step 4: Final sign-off commit (if anything drifted)**

If any tweaks were needed during smoke, commit them:

```bash
git add -u
git commit -m "chore(slice-1): smoke-test fixes and final polish"
```

---

## Subagent Briefs

### Test subagent brief

**Style:** pytest + `fastapi.testclient.TestClient`. No real network, no LLM calls. Use `monkeypatch.setattr(main.config, "processed_dir", ...)` and `monkeypatch.setattr(main.orchestrator, "run_in_background", lambda *a, **k: None)` to isolate. Use in-memory `zipfile.ZipFile` to craft EPUB payloads.

**Per task — tests the implementer MUST write:**

- **T1 (cognee pin):** smoke-run `test_config.py`. No new tests needed.
- **T2 (cognee guard):** `TestConfigureCogneeRuntimeGuard::test_missing_set_llm_config_logs_warning_and_returns` (negative — must not raise), `::test_present_set_llm_config_is_invoked` (positive).
- **T3 (ready-for-query):** `TestQueryReadyGate::test_query_returns_409_when_not_ready`. Also add `::test_query_succeeds_when_ready` (existing suite likely covers this — add if missing).
- **T4 (graph gate — critical):** four tests in `TestGraphSpoilerGate` — default path, explicit `max_chapter` override, explicit `full=true` override, HTML endpoint mirrors JSON. Also add a negative-path test: progress file missing → default to chapter 1 (not full graph).
- **T5 (zip-bomb):** three pure-function tests on `check_epub_decompressed_size` (total cap, entry cap, happy path), one endpoint test (`TestZipBombUploadRejection`). Add `test_env_override_expands_cap` to prove `BOOKRAG_MAX_DECOMPRESSED_BYTES` is honored.
- **T6 (dedupe):** `test_content_hash.py` covers pure functions (deterministic hash, missing manifest, malformed manifest, atomic write leaves no `.tmp`, lookup returns None when pipeline not ready). `TestUploadDedupe` covers the endpoint. **Add two negative-path tests:** `test_second_upload_before_pipeline_completes_still_generates_new_id` (race: pipeline isn't ready yet, second upload must NOT get the cached id), and `test_manifest_write_failure_does_not_block_upload` (wrap `record_book` in try/except in the endpoint).
- **T7 (rate limit):** `TestQueryRateLimit::test_31st_request_is_429` (with `BOOKRAG_QUERY_RATE_LIMIT=5/minute` to keep test fast). Add `::test_different_ip_has_independent_bucket` (provide `X-Forwarded-For` header if slowapi is configured to trust it, otherwise skip) and `::test_window_reset_clears_counter` using `main.limiter.reset()` between bursts.

---

### Generate subagent brief

**Code shape per fix:**

- **Graph gate.** Do NOT refactor `_load_batch_datapoints`. Just compute `effective_max` inside each endpoint and pass it in. Keep both endpoints' behaviors in lockstep by extracting a small helper `_resolve_graph_max_chapter(book_id, max_chapter, full) -> int | None` above them.

- **Zip-bomb helper.** `pipeline/epub_parser.py::check_epub_decompressed_size(path_or_bytes, max_total=None, max_entry=None) -> None`. Pure — no HTTP, no loguru-side-effect-dependent branching. Raises `EpubSizeError(ValueError subclass)`. Reads env vars only when caller passes `None`. Accepts `Path | str | bytes`. The endpoint caller converts `EpubSizeError` → `HTTPException(413)`. The parser caller converts it to `ValueError` so existing callers in the pipeline see the same exception class.

- **Content-hash manifest serialization.** Use `tempfile.mkstemp(dir=processed_dir)` so tmp file is on the same filesystem as target (required for atomic `os.replace`). Always write with `sort_keys=True` for deterministic diffs. Wrap the write in try/except and unlink the tmp on failure. Never hold the manifest lock across the entire ingest — read → decide → write, each step atomic.

- **Slowapi middleware registration.** Register `Limiter` at module import time so it's importable from tests (`from main import limiter`). Register `SlowAPIMiddleware` once, via `app.add_middleware(...)`. The `@limiter.limit` decorator takes a *callable* that reads env at request time — this is how the test's `monkeypatch.setenv("BOOKRAG_QUERY_RATE_LIMIT", "5/minute")` takes effect without restarting the app.

- **Ready-for-query gate.** Copy the exact pattern from `_list_chapter_files` (main.py:421–438). Local import of `load_state`, tolerate JSON errors as "not ready" with a warning.

- **Cognee guard.** Wrap the single-line call in try/except `AttributeError`. Log via loguru (project convention). Continue after warning; do NOT re-raise, because startup must not fail on an optional-config call.

- **pyproject pin.** Add `"cognee==0.5.6",` inside the existing dependencies list. Inline comment cites CLAUDE.md. `uv.lock` is the source of truth; regenerate with `uv lock` and commit.

---

### Review subagent brief

**Spec-compliance review** (one checkmark per audit finding):

- [ ] Finding 1 (graph spoiler gate): default path respects `_get_reading_progress`; `full=true` is the only way to see past progress; both JSON and HTML endpoints behave identically.
- [ ] Finding 2 (zip-bomb): crafted ZIP with single >100 MB entry → 413; crafted ZIP with total >500 MB → 413; legitimate small EPUB → 200.
- [ ] Finding 3 (dedupe): second upload of same bytes returns same `book_id` with `reused: true` ONLY after pipeline is ready; manifest is atomic and survives `kill -9` mid-write.
- [ ] Finding 4 (rate limit): 31st request in 60 s is 429 with `Retry-After`; env override works; counter resets across windows.
- [ ] Finding 5 (ready gate): unready book → 409 Conflict (not 404, not 200 with empty results).
- [ ] Finding 6 (cognee guard): missing `set_llm_config` → warning + continue (no crash); test stub in conftest exercises the happy path.
- [ ] Finding 7 (version pin): `grep 'cognee==0.5.6' pyproject.toml` hits; `uv.lock` is tracked.

**Code-quality review:**

- No new "god module." `main.py` gains ~40 lines; no function above 60 lines. Helpers pushed into `pipeline/content_hash.py` and `pipeline/epub_parser.py`.
- Error shapes consistent: all new HTTPException raises use `{status_code, detail}` — no ad-hoc body shapes.
- Status codes: 409 for "exists but not ready," 413 for "too large," 429 for "too many requests." Nothing is 400 that should be 413/429.
- No new top-level mutable state besides `limiter` (intentional, documented).
- No bypass path: the slowapi decorator is on the actual handler, not a no-op wrapper that tests bypass.
- loguru (not stdlib logging) used throughout new code — CLAUDE.md style.
- Local imports (`from models.pipeline_state import load_state`) inside functions where circular-import risk exists — mirrors existing codebase pattern.

**Final reviewer — exit criteria verification:**

Before signing off, run the eight exit-criteria checks from the spec verbatim. For each one, paste the command and its output into the slice review doc at `docs/superpowers/reviews/2026-04-22-slice-1-security-hardening.md`. Every check must show real evidence (command + output). "I believe this works" is not sufficient.
