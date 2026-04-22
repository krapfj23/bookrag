# Fog-of-War Phase 2: Per-Identity Snapshot Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When multiple batches extract the same entity (e.g., "Scrooge" appears in batches covering chapters 1-3, 4-6, and 7-9), retrieval should return the latest snapshot whose `last_known_chapter` ≤ reader cursor — not every snapshot, and not the first one. Combined with `batch_size=1` in `config.yaml`, this produces per-chapter snapshots with chapter-granular description accuracy.

**Architecture:** Refactor `pipeline/spoiler_filter.py:load_allowed_nodes` to group nodes by a stable identity key (`(type, name)` for named entities, `(type, chapter, description_slug)` for events) and return only the latest snapshot per key within the cursor bound. No schema migration required — this is pure read-side logic over existing batch JSON.

**Scope:** Per-identity selection at retrieval + docs for batch_size=1 stricter mode. **Out of scope** (future work): true per-paragraph extraction (10-100× LLM cost multiplier on ingest), and schema changes to formally version nodes (`CharacterIdentity` / `CharacterSnapshot` split). The read-side dedup here gives most of the benefit with no re-ingest cost.

**Tech Stack:** Existing `pipeline/spoiler_filter.py`, no new modules.

---

## Task 1: Identity key helper

**Files:**
- Modify: `pipeline/spoiler_filter.py`
- Test: `tests/test_spoiler_filter.py`

- [ ] **Step 1: Failing test**

Append to `tests/test_spoiler_filter.py`:

```python
class TestIdentityKey:
    """_identity_key groups nodes by stable identity regardless of which batch they came from."""

    def test_character_keyed_by_name(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "Character", "name": "Scrooge", "last_known_chapter": 1}
        b = {"_type": "Character", "name": "Scrooge", "last_known_chapter": 5}
        assert _identity_key(a) == _identity_key(b)

    def test_different_names_different_keys(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "Character", "name": "Scrooge"}
        b = {"_type": "Character", "name": "Marley"}
        assert _identity_key(a) != _identity_key(b)

    def test_same_name_different_type_different_keys(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "Character", "name": "London"}
        b = {"_type": "Location", "name": "London"}
        assert _identity_key(a) != _identity_key(b)

    def test_plotevent_keyed_by_chapter_and_description(self):
        from pipeline.spoiler_filter import _identity_key
        a = {"_type": "PlotEvent", "chapter": 2, "description": "Scrooge meets Marley's ghost"}
        b = {"_type": "PlotEvent", "chapter": 2, "description": "Scrooge meets Marley's ghost"}
        c = {"_type": "PlotEvent", "chapter": 2, "description": "Different event"}
        assert _identity_key(a) == _identity_key(b)
        assert _identity_key(a) != _identity_key(c)
```

- [ ] **Step 2: Confirm FAIL**

`pytest tests/test_spoiler_filter.py::TestIdentityKey -v`

- [ ] **Step 3: Implement**

Append to `pipeline/spoiler_filter.py`:

```python
def _identity_key(node: dict) -> tuple:
    """Return a stable identity tuple for grouping snapshots of the same entity.

    - Named entities (Character/Location/Faction/Theme): (type, name)
    - Relationships: (type, source_name, relation_type, target_name)
    - PlotEvents: (type, chapter, description) — events are inherently tied to a
      moment; we key by chapter + description to let identical events in
      different chapters remain distinct.
    """
    t = node.get("_type", "")
    if t == "Relationship":
        return (t, node.get("source_name", ""), node.get("relation_type", ""), node.get("target_name", ""))
    if t == "PlotEvent":
        return (t, node.get("chapter"), node.get("description", ""))
    return (t, node.get("name", ""))
```

- [ ] **Step 4: Verify**

`pytest tests/test_spoiler_filter.py -v` → all pass (existing + 4 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/jeffreykrapf/Documents/thefinalbookrag
git add pipeline/spoiler_filter.py tests/test_spoiler_filter.py
git commit -m "feat(spoiler): add _identity_key for per-identity snapshot grouping"
```

---

## Task 2: Refactor load_allowed_nodes to pick latest-per-identity

**Files:**
- Modify: `pipeline/spoiler_filter.py:load_allowed_nodes`
- Test: `tests/test_spoiler_filter.py`

- [ ] **Step 1: Failing test**

Append to `tests/test_spoiler_filter.py`:

```python
class TestLoadAllowedNodesDedup:
    """When the same identity appears in multiple batches, return the latest allowed snapshot."""

    def _write_batch(self, tmp_path, book_id, name, payload):
        batch_dir = tmp_path / book_id / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / name).write_text(json.dumps(payload))

    def test_takes_latest_snapshot_within_bound(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        # Scrooge extracted three times; descriptions reflect increasing knowledge.
        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [{"name": "Scrooge", "description": "a miser",
                            "first_chapter": 1, "last_known_chapter": 1}],
        })
        self._write_batch(tmp_path, "bk", "b2.json", {
            "characters": [{"name": "Scrooge", "description": "a miser haunted by Marley",
                            "first_chapter": 1, "last_known_chapter": 3}],
        })
        self._write_batch(tmp_path, "bk", "b3.json", {
            "characters": [{"name": "Scrooge", "description": "a reformed miser",
                            "first_chapter": 1, "last_known_chapter": 5}],
        })

        # Cursor 2: only the chapter-1 snapshot qualifies.
        allowed = load_allowed_nodes("bk", cursor=2, processed_dir=tmp_path)
        assert len(allowed) == 1
        assert allowed[0]["description"] == "a miser"

        # Cursor 4: chapter-3 snapshot wins over chapter-1.
        allowed = load_allowed_nodes("bk", cursor=4, processed_dir=tmp_path)
        assert len(allowed) == 1
        assert allowed[0]["description"] == "a miser haunted by Marley"

        # Cursor 9: all three snapshots qualify, latest wins.
        allowed = load_allowed_nodes("bk", cursor=9, processed_dir=tmp_path)
        assert len(allowed) == 1
        assert allowed[0]["description"] == "a reformed miser"

    def test_distinct_entities_all_return(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "bk", "b1.json", {
            "characters": [
                {"name": "Scrooge", "description": "miser", "first_chapter": 1, "last_known_chapter": 1},
                {"name": "Marley", "description": "ghost", "first_chapter": 1, "last_known_chapter": 1},
            ],
        })
        allowed = load_allowed_nodes("bk", cursor=5, processed_dir=tmp_path)
        names = {n["name"] for n in allowed}
        assert names == {"Scrooge", "Marley"}

    def test_plot_events_not_deduped_across_chapters(self, tmp_path):
        """Identical event descriptions in different chapters are distinct."""
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "bk", "b1.json", {
            "events": [
                {"description": "Scrooge wakes", "chapter": 1},
                {"description": "Scrooge wakes", "chapter": 4},
            ],
        })
        allowed = load_allowed_nodes("bk", cursor=5, processed_dir=tmp_path)
        assert len(allowed) == 2
```

- [ ] **Step 2: Confirm FAIL**

`pytest tests/test_spoiler_filter.py::TestLoadAllowedNodesDedup -v`

- [ ] **Step 3: Refactor `load_allowed_nodes`**

In `pipeline/spoiler_filter.py`, replace the body of `load_allowed_nodes` with:

```python
def load_allowed_nodes(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
) -> list[dict]:
    """Return the latest per-identity snapshot visible at `cursor`.

    Walks every batch JSON under {processed_dir}/{book_id}/batches/. For each
    node whose effective_latest_chapter <= cursor, keeps only the one with
    the greatest effective_latest_chapter per identity key (see _identity_key).

    Missing book directory returns []. Nodes with no chapter info are dropped.
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    # identity_key -> (effective_chapter, node)
    latest: dict[tuple, tuple[int, dict]] = {}

    for batch_file in sorted(batches_dir.glob("*.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for collection, type_label in _NODE_COLLECTIONS.items():
            for node in payload.get(collection, []) or []:
                ch = effective_latest_chapter(node)
                if ch is None or ch > cursor:
                    continue
                enriched = dict(node)
                enriched["_type"] = type_label
                key = _identity_key(enriched)
                prev = latest.get(key)
                if prev is None or ch > prev[0]:
                    latest[key] = (ch, enriched)

    return [node for _, node in latest.values()]
```

- [ ] **Step 4: Verify**

`pytest tests/test_spoiler_filter.py -v` → all pass.
`pytest tests/ -q` → full suite green. If any pre-existing test relied on duplicate-emission behavior, investigate and report.

- [ ] **Step 5: Commit**

```bash
git add pipeline/spoiler_filter.py tests/test_spoiler_filter.py
git commit -m "feat(spoiler): load_allowed_nodes returns latest per-identity snapshot"
```

---

## Task 3: Document per-chapter snapshot mode in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Run full sweep**

`pytest tests/ -v --tb=short 2>&1 | tail -5` — expect all PASS.

- [ ] **Step 2: Update CLAUDE.md**

Find the `### Fog-of-War Retrieval (Phases 0 + 1)` subsection. Replace its heading with `### Fog-of-War Retrieval (Phases 0 + 1 + 2)`, and append the following paragraph to its body (keep everything else):

```markdown
**Phase 2 — Per-identity snapshot selection.** When the same entity is extracted by multiple batches, `load_allowed_nodes` now returns the latest snapshot per identity within the cursor bound. For the strictest fidelity, set `batch_size: 1` in `config.yaml` before ingesting a book — each chapter becomes its own snapshot window, and retrieval can surface the description that reflects only what the reader has seen. Larger batch sizes still work (existing books don't need re-ingestion) but the `last_known_chapter` signal is coarser.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document Phase 2 per-identity snapshot selection"
```
