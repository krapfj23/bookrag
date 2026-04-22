# Slice 1 — Critical Security Hardening PRD

**Date:** 2026-04-22
**Parent:** Security audit (2026-04-22)
**Followed by:** Prompt-injection mitigation slice (separate)

## Goal

Close the seven findings from the 2026-04-22 security audit — four critical (spoiler-leak graph endpoints, zip-bomb, uncapped LLM cost from re-upload, unlimited /query) and three supporting items (ready-for-query gate on /query, cognee.config runtime guard, cognee version pin) — without regressing any existing behavior.

## Threat model recap

BookRAG is, per CLAUDE.md, a **single-user, localhost-only** app: FastAPI on 127.0.0.1:8000, CORS scoped to localhost:3000/5173/8000, no authentication, single-operator M4 Pro Mac. The dominant threats in this model are **self-inflicted** (accidentally uploading a hostile or oversized EPUB, accidentally browsing a graph endpoint that leaks spoilers, paying OpenAI twice for the same book), not adversarial network attackers. This slice treats the operator's *future self* as the primary protected party: spoiler integrity, LLM spend, pipeline liveness. Full auth/JWT, CORS tightening, and prompt-injection are intentionally out of scope — they belong to the multi-user phase.

## The seven in-scope fixes

### 1. Graph-endpoint spoiler gate

**Problem.** `main.py:991` (`GET /books/{id}/graph/data`) and `main.py:1000` (`GET /books/{id}/graph`) accept an optional `max_chapter` query param. When omitted, `_load_batch_datapoints` is called with `max_chapter=None` and returns every node in the book — including characters, plot events, and relationships from chapters the reader has not reached. This silently defeats the core spoiler-filtering guarantee for anyone who navigates to `/books/{id}/graph` in a browser.

**Fix.** When `max_chapter is None`, default to `_get_reading_progress(book_id)[0]` (the reader's current chapter from `reading_progress.json`). Require an explicit `full=true` query param to bypass the gate and see the complete graph. Apply to both `/graph/data` and `/graph` endpoints. Propagate `full` into the HTML graph's title label so the UI makes the override visible.

**Why this is the right fix.** It matches the fog-of-war contract already implemented in `/query` and `_list_chapter_files`. Defaulting to progress (not refusing the request) keeps the endpoint useful; requiring an explicit opt-in ensures the author has to *ask* for spoilers. No new auth surface.

**Non-goals.** Per-paragraph graph filtering (Phase-1 behavior for graph is future work). Hiding the `full` param from the UI (single-user — the operator can opt in when they want).

### 2. Zip-bomb cap on EPUB upload

**Problem.** `pipeline/epub_parser.py:142` calls `epub.read_epub` directly. EPUBs are ZIP archives; a 10 MB EPUB whose members decompress to 50 GB will OOM the process. The existing 500 MB check at `main.py:214` only bounds the *compressed* size.

**Fix.** Add a pure-function precheck `check_epub_decompressed_size(path_or_bytes, max_total, max_entry)` in `pipeline/epub_parser.py` that opens the upload as a `zipfile.ZipFile`, sums `file_size` over all members, and raises a structured `EpubSizeError` if total > `MAX_DECOMPRESSED_BYTES` (default 500 MB, configurable via `BOOKRAG_MAX_DECOMPRESSED_BYTES`) or any single entry > 100 MB (`BOOKRAG_MAX_ENTRY_BYTES`). Call it from `parse_epub` before `epub.read_epub`, and from the `/books/upload` endpoint right after the magic-bytes check — raise `HTTPException(413)` with a clear message in the endpoint path.

**Why this is the right fix.** Pure-function helper is unit-testable with a crafted in-memory ZIP. Two-layer defense (endpoint + parser) matches the existing pattern for the 500 MB compressed cap.

**Non-goals.** Detection of bombs that rely on nested archives. ZIP-slip path-traversal (ebooklib handles this on read). Streaming parse of huge legit EPUBs (our test book is 28 k words; 100 MB/entry is vastly overscaled).

### 3. Content-hash dedupe on upload

**Problem.** `main.py:238` builds `book_id = f"{slug}_{uuid.uuid4().hex[:8]}"`. Re-uploading the same EPUB creates a brand-new `book_id` and triggers Phase 1 (BookNLP, coref, ontology — minutes on Red Rising) and Phase 2 (Cognee extraction — dollars on OpenAI) from scratch.

**Fix.** Before generating a new `book_id`, compute `sha256(content)`. Maintain `data/processed/_content_hashes.json` as `{"sha256_hex": "book_id"}`. If a match is found AND the mapped book's `pipeline_state.ready_for_query` is true, return `UploadResponse(book_id=<existing>, message="already processed", reused=True)`. Otherwise, write the new book_id to the manifest and proceed with ingest. Atomic write: tmp file + `os.replace`. Tolerate missing/malformed manifest (treat as empty; log warning).

**Why this is the right fix.** Content-hash is deterministic, cheap, and survives renames. Only reusing when the existing pipeline is *complete* avoids returning a half-processed book. A manifest file (not a DB) keeps with the "save intermediate outputs to disk" style from CLAUDE.md.

**Non-goals.** De-duping partially-processed books (edge case; operator can delete the broken dir and re-upload). Cross-machine sync of the manifest. Content-based detection of EPUBs that differ only in metadata.

### 4. Rate limit on `/query`

**Problem.** `main.py:826` has no rate limit. A runaway client (or a frontend bug) can burn through `OPENAI_API_KEY` quota in seconds.

**Fix.** Add `slowapi>=0.1.9` to `pyproject.toml`. Register a `Limiter(key_func=get_remote_address)` on app startup; decorate `/books/{book_id}/query` with `@limiter.limit(os.environ.get("BOOKRAG_QUERY_RATE_LIMIT", "30/minute"))`. Install `RateLimitExceeded` handler that returns `429` with a `Retry-After` header.

**Why this is the right fix.** slowapi is the de-facto Starlette/FastAPI rate-limit library, supports env-override out of the box, works with the existing `TestClient` suite. Per-IP is fine in single-user; the env var lets us tighten to 5/minute on deploy or loosen for load tests.

**Non-goals.** Per-book or per-book-owner rate limits. Token-bucket burst tuning (the library default is fine).

### 5. Ready-for-query gate on `/query`

**Problem.** `main.py:844` only checks `book_dir.exists()`. A book whose Phase 1 completed but Phase 2 is still running has a directory — but `allowed_nodes` will be empty and `/query` returns an empty graph-completion answer with no signal that the pipeline isn't done.

**Fix.** Load `pipeline_state.json` via `models.pipeline_state.load_state`; if `state.ready_for_query is False`, raise `HTTPException(409, "Book is still being processed")`. Mirror the pattern in `_list_chapter_files` at `main.py:437`.

**Why this is the right fix.** 409 Conflict is the correct semantic for "resource exists but not in a state that allows this operation." Identical to what `/chapters` already does.

**Non-goals.** A client-side poll-until-ready UX (the frontend already polls `/status`).

### 6. `cognee.config` runtime guard + test stub

**Problem.** `pipeline/cognee_pipeline.py:86` calls `cognee.config.set_llm_config(llm_config)` with no guard. CLAUDE.md flags Cognee pre-1.0 API instability; if `set_llm_config` is removed or renamed in a patch release, `configure_cognee` crashes at FastAPI startup. The mocked `cognee` in `tests/conftest.py` currently has no `config` attribute, so tests silently skip this code path.

**Fix.** Wrap the call in `try/except AttributeError` — log `logger.warning("cognee.config.set_llm_config unavailable — continuing without LLM config override: {}", exc)` and continue. Add a `cognee.config` stub to `tests/conftest.py` adjacent to the existing Cognee mock (`cognee.config = MagicMock(); cognee.config.set_llm_config = MagicMock()`) so tests exercise the happy path. Add a new test class `TestConfigureCogneeRuntimeGuard` in `tests/test_cognee_pipeline.py` with a test that monkeypatches `delattr(cognee.config, "set_llm_config")` and asserts `configure_cognee(config)` logs a warning and does not raise.

**Why this is the right fix.** CLAUDE.md "Style" mandates flagging Cognee API instability proactively. The guard is three lines; the test stub closes a real testing gap.

**Non-goals.** A full compatibility shim for Cognee future versions (we're pinned to 0.5.6 anyway — see item 7).

### 7. Pin `cognee==0.5.6`

**Problem.** `pyproject.toml` (lines 37–39) comments "Install separately: pip install cognee". No version pin anywhere. CLAUDE.md *explicitly* calls out "Temporary Decisions — Patched Cognee 0.5.6 locally" with local patches to `upsert_edges.py` and `upsert_nodes.py`. A pip-install by a new contributor will fetch whatever is on PyPI, breaking the build.

**Fix.** Add `"cognee==0.5.6",` to `[project].dependencies` with an inline comment: `# Pinned — see CLAUDE.md "Temporary Decisions / Patched Cognee 0.5.6 locally"`. Regenerate `uv.lock` with `uv lock`. Commit `uv.lock` (currently untracked) alongside the `pyproject.toml` change.

**Why this is the right fix.** Aligns the dependency file with the documented reality. Locks the patch surface we depend on. `uv.lock` is the authoritative snapshot.

**Non-goals.** Publishing the patched cognee as a fork on GitHub (separate effort). Removing the CLAUDE.md "Temporary" note (keep — it's still true).

## Dependencies & risks

- **New dep: `slowapi>=0.1.9`** — lightweight, pure-python, no C extensions. Low risk.
- **Manifest file format** (`_content_hashes.json`) — JSON object. Atomic writes via `tempfile` + `os.replace`. Concurrent-upload race is mitigated by writing *after* the ingest decision (double-upload creates two book dirs; the second overwrites the manifest entry — harmless and caught by the `ready_for_query` check on the next round-trip).
- **Cognee pin** — may block a future cognee upgrade. Tracked in CLAUDE.md "Temporary Decisions" already.
- **`slowapi` + `TestClient`** — slowapi requires `Request` in the endpoint signature for key extraction. Verify `test_query_endpoint.py` still passes after adding the `request: Request` parameter.

## Exit criteria

Every item below is a manual or automated check the implementer must pass before claiming Slice 1 done.

1. **`pytest tests/ -v --tb=short` green** — all 923 existing tests plus the new ones for this slice (T1–T7 below) pass.
2. **Graph gate manual.** `curl -s http://127.0.0.1:8000/books/christmas_carol_e6ddcd76/graph/data | jq '.nodes | length'` returns the count for chapters 1..current_chapter only (assuming reading_progress points there). Adding `?full=true` returns strictly more nodes.
3. **Zip-bomb.** Uploading a crafted 1 KB ZIP whose inner entry claims `file_size=600_000_000` returns `HTTP 413`.
4. **Dedupe.** `curl -F file=@xmas.epub /books/upload` twice in a row returns the same `book_id` on the second call and `reused: true` (after the first one's pipeline completes).
5. **Rate limit.** Running `for i in {1..40}; do curl -s -o /dev/null -w "%{http_code}\n" -X POST .../query -d '...'; done` shows at least one `429` with a `Retry-After` header.
6. **Ready-for-query gate.** Querying a book whose `pipeline_state.ready_for_query=false` returns 409, not a success with empty results.
7. **Cognee guard.** `python -c "import cognee; delattr(cognee.config, 'set_llm_config'); from pipeline.cognee_pipeline import configure_cognee; from models.config import load_config; configure_cognee(load_config())"` prints a warning and exits 0.
8. **Version pin.** `grep 'cognee==0.5.6' pyproject.toml` returns a hit; `uv.lock` contains `cognee==0.5.6` and is tracked in git.
