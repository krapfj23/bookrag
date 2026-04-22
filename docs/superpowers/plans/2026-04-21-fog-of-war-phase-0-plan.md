# Fog-of-War Phase 0: Leak-Proof Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate two concrete spoiler leaks in the query path: (1) `first_chapter`-only filtering lets node descriptions that were informed by post-progress chapters pass through, and (2) `cognee.search` retrieves over the entire graph before post-hoc result trimming, so graph-completion answers can be influenced by future content.

**Architecture:** Add `last_known_chapter` to every temporally-scoped DataPoint (Character/Location/Faction/Theme/Relationship), update the extraction prompt + converter so the LLM populates it, and replace the `/books/{id}/query` implementation with a pre-filter path. The pre-filter path walks `batches/*.json`, builds a set of node IDs whose *effective latest chapter* is ≤ the reader's cursor, then answers from that allowlisted subgraph — bypassing Cognee's default retrieval for graph-completion queries and feeding only allowed context into the LLM.

Phase 0 stays chapter-granular on both the progress cursor and the extraction window. Paragraph-level progress and per-paragraph node snapshots are out of scope (Phase 1 and Phase 2 respectively).

**Tech Stack:** FastAPI, Pydantic v2, Cognee 0.5.6 (LLMGateway only — not default search), disk-based batch JSON, loguru. Existing pytest suite.

## File Structure

**New files:**
- `pipeline/spoiler_filter.py` — all filtering logic. `effective_latest_chapter(obj)`, `build_allowed_node_ids(book_id, cursor)`, `load_allowed_nodes(book_id, cursor)`. One module, one responsibility.
- `tests/test_spoiler_filter.py` — unit tests for the filter module.
- `scripts/backfill_last_known_chapter.py` — one-shot backfill for existing batch JSON files on disk so the filter works on already-ingested books without full re-extraction.

**Modified files:**
- `models/datapoints.py` — add `last_known_chapter` to Character, Location, Faction, Theme, Relationship (DataPoint classes + Extraction classes). Update `to_datapoints()` to plumb it.
- `prompts/extraction_prompt.txt` — document the new field and its meaning, update the JSON schema example.
- `main.py` — replace `query_book` internals and `_extract_chapter` to use `effective_latest_chapter`. Add a custom LLM-completion path for `GRAPH_COMPLETION` that sees only allowed nodes.
- `tests/test_datapoints.py` — cover the new field and converter behavior.
- `tests/test_extraction_prompt.py` — assert the new field is referenced.
- `tests/test_main.py` — add integration tests proving spoiler containment.

---

## Task 1: Add `last_known_chapter` to DataPoint schema

**Files:**
- Modify: `models/datapoints.py:26-72`
- Test: `tests/test_datapoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datapoints.py`:

```python
class TestLastKnownChapter:
    """Every temporally-scoped DataPoint carries last_known_chapter."""

    def test_character_has_last_known_chapter(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1, last_known_chapter=3)
        assert c.last_known_chapter == 3

    def test_last_known_chapter_defaults_to_first_chapter(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1)
        assert c.last_known_chapter == 1

    def test_location_faction_theme_relationship_all_have_it(self):
        from models.datapoints import Location, Faction, Theme, Relationship, Character
        assert Location(name="L", first_chapter=2).last_known_chapter == 2
        assert Faction(name="F", first_chapter=2).last_known_chapter == 2
        assert Theme(name="T", first_chapter=2).last_known_chapter == 2
        a = Character(name="A", first_chapter=1)
        b = Character(name="B", first_chapter=1)
        r = Relationship(source=a, target=b, relation_type="x", first_chapter=2)
        assert r.last_known_chapter == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_datapoints.py::TestLastKnownChapter -v`
Expected: FAIL — `last_known_chapter` is not a known field.

- [ ] **Step 3: Add the field to each DataPoint**

Edit `models/datapoints.py`. For each of `Character`, `Location`, `Faction`, `Theme`, `Relationship` add:

```python
    last_known_chapter: int | None = None
```

immediately after the `first_chapter: int` line. Do NOT add to `PlotEvent` — `PlotEvent.chapter` is already a single point in time.

Then add a Pydantic model validator (once, at the bottom of the class set or per-class) to default `last_known_chapter` to `first_chapter` when omitted. Use a `model_validator(mode="after")` so it fires after field parsing:

```python
from pydantic import model_validator

# In each of Character, Location, Faction, Theme, Relationship:
    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_datapoints.py::TestLastKnownChapter -v`
Expected: PASS (all three).

- [ ] **Step 5: Run the full datapoints test file to make sure nothing else broke**

Run: `pytest tests/test_datapoints.py -v`
Expected: all tests PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add models/datapoints.py tests/test_datapoints.py
git commit -m "feat(datapoints): add last_known_chapter field with first_chapter default"
```

---

## Task 2: Add `last_known_chapter` to Extraction models

**Files:**
- Modify: `models/datapoints.py:83-140`
- Test: `tests/test_datapoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datapoints.py`:

```python
class TestExtractionLastKnownChapter:
    """LLM extraction models accept last_known_chapter and default to first_chapter."""

    def test_character_extraction_accepts_field(self):
        from models.datapoints import CharacterExtraction
        c = CharacterExtraction(name="Scrooge", first_chapter=1, last_known_chapter=3)
        assert c.last_known_chapter == 3

    def test_extraction_default_equals_first_chapter(self):
        from models.datapoints import CharacterExtraction, LocationExtraction, FactionExtraction, ThemeExtraction, RelationshipExtraction
        assert CharacterExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert LocationExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert FactionExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert ThemeExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert RelationshipExtraction(
            source_name="a", target_name="b", relation_type="x", first_chapter=2
        ).last_known_chapter == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_datapoints.py::TestExtractionLastKnownChapter -v`
Expected: FAIL — unknown field on the extraction models.

- [ ] **Step 3: Add the field to each Extraction model**

Edit `models/datapoints.py`. For `CharacterExtraction`, `LocationExtraction`, `FactionExtraction`, `ThemeExtraction`, `RelationshipExtraction` add immediately after `first_chapter: int`:

```python
    last_known_chapter: int | None = Field(
        default=None,
        description="Latest chapter (in this extraction batch) whose text contributed to this entity's description. Defaults to first_chapter when omitted.",
    )
```

Add the same `model_validator(mode="after")` default-to-`first_chapter` hook used in Task 1 for each class.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_datapoints.py::TestExtractionLastKnownChapter -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add models/datapoints.py tests/test_datapoints.py
git commit -m "feat(datapoints): add last_known_chapter to extraction models"
```

---

## Task 3: Plumb `last_known_chapter` through `to_datapoints()`

**Files:**
- Modify: `models/datapoints.py:158-251`
- Test: `tests/test_datapoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_datapoints.py`:

```python
class TestToDatapointsPreservesLastKnownChapter:
    def test_character_last_known_chapter_copied(self):
        from models.datapoints import ExtractionResult, CharacterExtraction
        result = ExtractionResult(characters=[
            CharacterExtraction(name="Scrooge", first_chapter=1, last_known_chapter=4)
        ])
        dps = result.to_datapoints()
        char = next(d for d in dps if d.__class__.__name__ == "Character")
        assert char.last_known_chapter == 4

    def test_all_types_preserve_last_known_chapter(self):
        from models.datapoints import (
            ExtractionResult, CharacterExtraction, LocationExtraction,
            FactionExtraction, ThemeExtraction, RelationshipExtraction,
        )
        result = ExtractionResult(
            characters=[
                CharacterExtraction(name="A", first_chapter=1, last_known_chapter=5),
                CharacterExtraction(name="B", first_chapter=1, last_known_chapter=5),
            ],
            locations=[LocationExtraction(name="L", first_chapter=2, last_known_chapter=6)],
            factions=[FactionExtraction(name="F", first_chapter=3, last_known_chapter=7)],
            themes=[ThemeExtraction(name="T", first_chapter=4, last_known_chapter=8)],
            relationships=[RelationshipExtraction(
                source_name="A", target_name="B", relation_type="loves",
                first_chapter=2, last_known_chapter=9,
            )],
        )
        dps = {d.__class__.__name__: d for d in result.to_datapoints() if d.__class__.__name__ != "Character"}
        assert dps["Location"].last_known_chapter == 6
        assert dps["Faction"].last_known_chapter == 7
        assert dps["Theme"].last_known_chapter == 8
        assert dps["Relationship"].last_known_chapter == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_datapoints.py::TestToDatapointsPreservesLastKnownChapter -v`
Expected: FAIL — `last_known_chapter` is not passed in `to_datapoints()`.

- [ ] **Step 3: Update `to_datapoints()` to pass the field**

In `models/datapoints.py`, inside `ExtractionResult.to_datapoints()`, add `last_known_chapter=<source>.last_known_chapter,` to each of the five DataPoint constructions (Character, Location, Faction, Theme, Relationship). Do NOT modify `PlotEvent` construction.

Example for Character (line ~171):

```python
dp = Character(
    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"character:{c.name}"),
    name=c.name,
    aliases=c.aliases,
    description=c.description,
    first_chapter=c.first_chapter,
    last_known_chapter=c.last_known_chapter,
    chapters_present=c.chapters_present,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_datapoints.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add models/datapoints.py tests/test_datapoints.py
git commit -m "feat(datapoints): plumb last_known_chapter through to_datapoints()"
```

---

## Task 4: Update the extraction prompt to request `last_known_chapter`

**Files:**
- Modify: `prompts/extraction_prompt.txt`
- Test: `tests/test_extraction_prompt.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_extraction_prompt.py`:

```python
class TestLastKnownChapterInPrompt:
    """Prompt must instruct the LLM to populate last_known_chapter."""

    def test_field_appears_in_json_schema(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text()
        assert "last_known_chapter" in prompt, "prompt must document last_known_chapter"

    def test_prompt_explains_semantics(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text().lower()
        # must mention that the field tracks the latest contributing chapter
        assert "latest chapter" in prompt or "last chapter" in prompt
```

(Ensure `from pathlib import Path` is imported at the top of the test file — add if missing.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_prompt.py::TestLastKnownChapterInPrompt -v`
Expected: FAIL.

- [ ] **Step 3: Update the prompt**

Edit `prompts/extraction_prompt.txt`. In the section under `## Extraction Rules` → `### General`, add a new bullet:

```
- For each character/location/faction/theme/relationship, include `last_known_chapter`: the LATEST chapter number from the current batch whose text contributed evidence for this entity's description. If the entity only appears in one chapter of this batch, `last_known_chapter` equals `first_chapter`. This is used for reader-progress filtering — do not set it higher than chapters actually shown in the input.
```

Then in the `## Output Format` JSON schema example, add `"last_known_chapter": 1,` to every object that currently has `"first_chapter": 1,` EXCEPT the plot event objects.

For example, the `characters` schema becomes:

```json
{
  "name": "canonical name",
  "aliases": ["alias1", "alias2"],
  "description": "brief description based on this text",
  "first_chapter": 1,
  "last_known_chapter": 1,
  "chapters_present": [1, 2]
}
```

Apply the same addition to `locations`, `factions`, `themes`, and `relationships` in the schema example. Leave `events` alone.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_extraction_prompt.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add prompts/extraction_prompt.txt tests/test_extraction_prompt.py
git commit -m "feat(prompt): instruct LLM to populate last_known_chapter"
```

---

## Task 5: Create `pipeline/spoiler_filter.py` with `effective_latest_chapter`

**Files:**
- Create: `pipeline/spoiler_filter.py`
- Test: `tests/test_spoiler_filter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_spoiler_filter.py`:

```python
"""Tests for pipeline/spoiler_filter.py — chapter filtering primitives."""

import pytest


class TestEffectiveLatestChapter:
    """effective_latest_chapter returns the greatest chapter value a node 'knows about'."""

    def test_uses_last_known_when_greater_than_first(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 1, "last_known_chapter": 5}
        assert effective_latest_chapter(node) == 5

    def test_uses_first_when_last_known_missing(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 3}
        assert effective_latest_chapter(node) == 3

    def test_uses_chapter_for_plot_events(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"chapter": 7}
        assert effective_latest_chapter(node) == 7

    def test_returns_none_when_no_chapter_info(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        assert effective_latest_chapter({}) is None

    def test_accepts_pydantic_like_object(self):
        from pipeline.spoiler_filter import effective_latest_chapter

        class Fake:
            first_chapter = 1
            last_known_chapter = 4

        assert effective_latest_chapter(Fake()) == 4

    def test_max_across_all_fields(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        # both first_chapter and chapter set — take the max
        node = {"first_chapter": 1, "chapter": 9, "last_known_chapter": 3}
        assert effective_latest_chapter(node) == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_spoiler_filter.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create the module**

Create `pipeline/spoiler_filter.py`:

```python
"""Spoiler filtering primitives for the BookRAG query path.

Every temporally-scoped entity in the graph has one or more chapter-like
fields. `effective_latest_chapter` collapses them into a single "this node
becomes visible at chapter N" value used for pre-filtering retrieval.
"""

from __future__ import annotations

from typing import Any

_CHAPTER_FIELDS = ("first_chapter", "last_known_chapter", "chapter")


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def effective_latest_chapter(obj: Any) -> int | None:
    """Return the largest chapter number this node depends on, or None.

    Considers first_chapter, last_known_chapter, and chapter (PlotEvent).
    A node is only safe to show a reader whose progress is >= this value.
    """
    values = [_get(obj, f) for f in _CHAPTER_FIELDS]
    ints = [int(v) for v in values if v is not None]
    return max(ints) if ints else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spoiler_filter.py::TestEffectiveLatestChapter -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/spoiler_filter.py tests/test_spoiler_filter.py
git commit -m "feat(spoiler): add effective_latest_chapter primitive"
```

---

## Task 6: Add `load_allowed_nodes(book_id, cursor)` disk walker

**Files:**
- Modify: `pipeline/spoiler_filter.py`
- Test: `tests/test_spoiler_filter.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_spoiler_filter.py`:

```python
import json
from pathlib import Path


class TestLoadAllowedNodes:
    """load_allowed_nodes walks batches/*.json and returns only nodes visible at cursor."""

    def _write_batch(self, tmp_path: Path, name: str, payload: dict):
        batch_dir = tmp_path / "book-1" / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / name).write_text(json.dumps(payload))

    def test_filters_by_cursor(self, tmp_path, monkeypatch):
        from pipeline.spoiler_filter import load_allowed_nodes

        self._write_batch(tmp_path, "batch_01.json", {
            "characters": [
                {"id": "c1", "name": "Early", "first_chapter": 1, "last_known_chapter": 2},
                {"id": "c2", "name": "Late",  "first_chapter": 1, "last_known_chapter": 8},
            ],
            "events": [
                {"id": "e1", "description": "ev", "chapter": 1},
                {"id": "e2", "description": "ev", "chapter": 9},
            ],
        })

        allowed = load_allowed_nodes("book-1", cursor=3, processed_dir=tmp_path)

        ids = {n["id"] for n in allowed}
        assert ids == {"c1", "e1"}, f"got {ids}"

    def test_empty_when_no_batches(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        assert load_allowed_nodes("nonexistent", cursor=10, processed_dir=tmp_path) == []

    def test_merges_multiple_batches(self, tmp_path):
        from pipeline.spoiler_filter import load_allowed_nodes
        self._write_batch(tmp_path, "batch_01.json", {
            "characters": [{"id": "a", "name": "A", "first_chapter": 1, "last_known_chapter": 1}],
        })
        self._write_batch(tmp_path, "batch_02.json", {
            "characters": [{"id": "b", "name": "B", "first_chapter": 4, "last_known_chapter": 4}],
        })
        allowed = load_allowed_nodes("book-1", cursor=5, processed_dir=tmp_path)
        assert {n["id"] for n in allowed} == {"a", "b"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_spoiler_filter.py::TestLoadAllowedNodes -v`
Expected: FAIL — `load_allowed_nodes` not defined.

- [ ] **Step 3: Implement `load_allowed_nodes`**

Append to `pipeline/spoiler_filter.py`:

```python
import json
from pathlib import Path

# Every key in a batch JSON file that holds temporally-scoped nodes.
# Values are the node-type label we attach when merging.
_NODE_COLLECTIONS = {
    "characters": "Character",
    "locations": "Location",
    "factions": "Faction",
    "themes": "Theme",
    "events": "PlotEvent",
    "relationships": "Relationship",
}


def load_allowed_nodes(
    book_id: str,
    cursor: int,
    processed_dir: Path | str,
) -> list[dict]:
    """Return every node in `book_id`'s batch JSONs whose effective latest
    chapter is <= cursor. Each returned dict has an added "_type" field.

    Missing book directory returns []. Nodes with no chapter info are dropped
    (safer to hide an uncategorized node than leak one).
    """
    batches_dir = Path(processed_dir) / book_id / "batches"
    if not batches_dir.exists():
        return []

    allowed: list[dict] = []
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
                allowed.append(enriched)
    return allowed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spoiler_filter.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/spoiler_filter.py tests/test_spoiler_filter.py
git commit -m "feat(spoiler): add load_allowed_nodes disk walker"
```

---

## Task 7: Replace `_extract_chapter` in main.py

**Files:**
- Modify: `main.py:484-496`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py` (inside any existing `TestQueryEndpoint`-style class, or a new one):

```python
class TestExtractChapterUsesEffectiveLatest:
    def test_prefers_last_known_over_first(self):
        from main import _extract_chapter

        class Node:
            first_chapter = 1
            last_known_chapter = 7

        assert _extract_chapter(Node()) == 7

    def test_falls_back_to_first_chapter(self):
        from main import _extract_chapter

        class Node:
            first_chapter = 4

        assert _extract_chapter(Node()) == 4

    def test_handles_plot_event_chapter(self):
        from main import _extract_chapter
        assert _extract_chapter({"chapter": 9}) == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestExtractChapterUsesEffectiveLatest -v`
Expected: FAIL — current impl returns `first_chapter`, not the max.

- [ ] **Step 3: Rewrite `_extract_chapter` to delegate**

In `main.py`, replace the body of `_extract_chapter` (roughly lines 484–496) with:

```python
def _extract_chapter(item: Any) -> int | None:
    """Return the effective latest chapter for a retrieval result item."""
    from pipeline.spoiler_filter import effective_latest_chapter

    obj = item
    if hasattr(item, "search_result"):
        obj = item.search_result
    return effective_latest_chapter(obj)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "fix(query): use effective_latest_chapter instead of first_chapter"
```

---

## Task 8: Write the pre-filter retrieval helper in `main.py`

**Files:**
- Modify: `main.py` — add a new helper `_answer_from_allowed_nodes` near `query_book`.
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
import json


class TestAnswerFromAllowedNodes:
    """The pre-filter retrieval path never returns nodes beyond the cursor."""

    def _seed_book(self, tmp_path, book_id: str):
        batches = tmp_path / book_id / "batches"
        batches.mkdir(parents=True)
        (batches / "b1.json").write_text(json.dumps({
            "characters": [
                {"id": "c1", "name": "Scrooge", "description": "miser",
                 "first_chapter": 1, "last_known_chapter": 1},
                {"id": "c2", "name": "Ghost of Future", "description": "spoiler",
                 "first_chapter": 1, "last_known_chapter": 5},
            ],
            "events": [
                {"id": "e1", "description": "meets ghost", "chapter": 2},
                {"id": "e3", "description": "dies", "chapter": 5},
            ],
        }))
        (tmp_path / book_id / "pipeline_state.json").write_text(json.dumps({
            "book_id": book_id, "ready_for_query": True, "current_stage": "complete",
            "stages": {},
        }))

    def test_cursor_2_hides_chapter_5_nodes(self, tmp_path, monkeypatch):
        from main import _answer_from_allowed_nodes, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed_book(tmp_path, "bk")

        items = _answer_from_allowed_nodes("bk", question="what happens", cursor=2)
        contents = [i.content for i in items]
        assert not any("spoiler" in c.lower() for c in contents)
        assert not any("dies" in c.lower() for c in contents)

    def test_cursor_5_reveals_chapter_5_nodes(self, tmp_path, monkeypatch):
        from main import _answer_from_allowed_nodes, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed_book(tmp_path, "bk")

        items = _answer_from_allowed_nodes("bk", question="dies", cursor=5)
        assert any("dies" in i.content.lower() for i in items)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestAnswerFromAllowedNodes -v`
Expected: FAIL — `_answer_from_allowed_nodes` not defined.

- [ ] **Step 3: Implement the helper**

Add to `main.py` above `query_book`:

```python
def _answer_from_allowed_nodes(
    book_id: str,
    question: str,
    cursor: int,
) -> list[QueryResultItem]:
    """Pre-filtered keyword retrieval. Walks disk batch JSON, keeps only
    nodes whose effective latest chapter is <= cursor, then ranks by
    keyword overlap with the question."""
    from pipeline.spoiler_filter import load_allowed_nodes, effective_latest_chapter

    nodes = load_allowed_nodes(book_id, cursor, processed_dir=Path(config.processed_dir))
    if not nodes:
        return []

    keywords = [w.lower() for w in question.split() if len(w) > 2]
    ranked: list[tuple[int, QueryResultItem]] = []
    for node in nodes:
        label = (node.get("name") or node.get("description") or "").lower()
        desc = (node.get("description") or "").lower()
        haystack = f"{label} {desc}"
        score = sum(1 for kw in keywords if kw in haystack) if keywords else 0
        if keywords and score == 0:
            continue
        content = node.get("name") or node.get("description") or ""
        if node.get("name") and node.get("description"):
            content = f"{node['name']} — {node['description']}"
        ranked.append((score, QueryResultItem(
            content=content,
            entity_type=node.get("_type"),
            chapter=effective_latest_chapter(node),
        )))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py::TestAnswerFromAllowedNodes -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(query): pre-filter retrieval helper using allowed-node set"
```

---

## Task 9: Rewire `query_book` to use the pre-filter path

**Files:**
- Modify: `main.py:554-611`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_main.py`:

```python
class TestQueryEndpointFogOfWar:
    """End-to-end: /books/{id}/query never returns content past the cursor."""

    def _seed(self, tmp_path, book_id):
        batches = tmp_path / book_id / "batches"
        batches.mkdir(parents=True)
        (batches / "b1.json").write_text(json.dumps({
            "characters": [
                {"id": "c1", "name": "Marley", "description": "dead partner",
                 "first_chapter": 1, "last_known_chapter": 1},
                {"id": "c2", "name": "Tiny Tim", "description": "dies in stave 4",
                 "first_chapter": 1, "last_known_chapter": 4},
            ],
        }))
        (tmp_path / book_id / "pipeline_state.json").write_text(json.dumps({
            "book_id": book_id, "ready_for_query": True, "current_stage": "complete",
            "stages": {},
        }))
        (tmp_path / book_id / "reading_progress.json").write_text(json.dumps({
            "book_id": book_id, "current_chapter": 2,
        }))

    def test_query_hides_future_character_description(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))
        self._seed(tmp_path, "carol")

        client = TestClient(app)
        resp = client.post("/books/carol/query", json={
            "question": "Tiny Tim",
            "search_type": "GRAPH_COMPLETION",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_chapter"] == 2
        for r in body["results"]:
            assert "dies in stave 4" not in r["content"], f"SPOILER: {r}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestQueryEndpointFogOfWar -v`
Expected: FAIL — current `query_book` retrieves from Cognee (which isn't sandboxed against our fixture data) OR leaks Tiny Tim's description through `first_chapter=1`.

- [ ] **Step 3: Replace `query_book` internals**

In `main.py`, replace the body of `query_book` (lines 554–611) with:

```python
@app.post("/books/{book_id}/query", response_model=QueryResponse)
async def query_book(book_id: SafeBookId, req: QueryRequest) -> QueryResponse:
    """Query the knowledge graph with reader-progress fog-of-war.

    Retrieval is PRE-FILTERED: a node allowlist is computed from disk based
    on the reader's current chapter, and only allowed nodes are ever
    considered. No Cognee default search is run, because it retrieves across
    the full dataset before we can filter and may leak spoilers through
    graph-completion reasoning.
    """
    if req.search_type not in _ALLOWED_SEARCH_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search_type '{req.search_type}'. Allowed: {sorted(_ALLOWED_SEARCH_TYPES)}",
        )

    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    disk_max = _get_reading_progress(book_id)
    current_chapter = (
        min(req.max_chapter, disk_max) if req.max_chapter is not None else disk_max
    )

    results = _answer_from_allowed_nodes(book_id, req.question, current_chapter)

    return QueryResponse(
        book_id=book_id,
        question=req.question,
        search_type=req.search_type,
        current_chapter=current_chapter,
        results=results,
        result_count=len(results),
    )
```

Note: this temporarily drops the Cognee LLM-completion output. Task 10 adds it back in a spoiler-safe way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "fix(query): pre-filter allowlist replaces post-filter Cognee search"
```

---

## Task 10: Re-introduce LLM completion over the filtered context

**Files:**
- Modify: `main.py` — add `_complete_over_context` and use it when `search_type == "GRAPH_COMPLETION"`.
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
class TestGraphCompletionUsesOnlyAllowed:
    """GRAPH_COMPLETION calls the LLM with ONLY allowed context."""

    def test_llm_prompt_does_not_contain_future_content(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from main import app, config as main_config
        import main as main_mod

        monkeypatch.setattr(main_config, "processed_dir", str(tmp_path))

        captured: dict = {}

        async def fake_complete(question: str, context: list[str]) -> str:
            captured["context"] = context
            captured["question"] = question
            return "stub answer"

        monkeypatch.setattr(main_mod, "_complete_over_context", fake_complete)

        batches = tmp_path / "bk" / "batches"
        batches.mkdir(parents=True)
        (batches / "b1.json").write_text(json.dumps({
            "characters": [
                {"id": "c1", "name": "Early", "description": "safe",
                 "first_chapter": 1, "last_known_chapter": 1},
                {"id": "c2", "name": "Future", "description": "SPOILER_MARKER",
                 "first_chapter": 1, "last_known_chapter": 9},
            ],
        }))
        (tmp_path / "bk" / "pipeline_state.json").write_text(json.dumps({
            "book_id": "bk", "ready_for_query": True, "current_stage": "complete", "stages": {},
        }))
        (tmp_path / "bk" / "reading_progress.json").write_text(json.dumps({
            "book_id": "bk", "current_chapter": 2,
        }))

        client = TestClient(app)
        resp = client.post("/books/bk/query", json={
            "question": "tell me about future events",
            "search_type": "GRAPH_COMPLETION",
        })
        assert resp.status_code == 200
        assert captured, "LLM completion was not invoked"
        combined = " ".join(captured["context"])
        assert "SPOILER_MARKER" not in combined, f"context leaked: {combined}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestGraphCompletionUsesOnlyAllowed -v`
Expected: FAIL — `_complete_over_context` not defined; GRAPH_COMPLETION still returns only keyword results.

- [ ] **Step 3: Implement `_complete_over_context` and wire it up**

Add to `main.py` above `query_book`:

```python
from pydantic import BaseModel


class _SpoilerSafeAnswer(BaseModel):
    answer: str


async def _complete_over_context(question: str, context: list[str]) -> str:
    """Ask the configured LLM to answer `question` using ONLY `context`.

    Context is the stringified allowed-node content list. No retrieval
    happens inside this function — the caller owns the fog-of-war guarantee.
    """
    from cognee.infrastructure.llm.LLMGateway import LLMGateway

    if not context:
        return "I don't have information about that yet based on your reading progress."

    system = (
        "You are a spoiler-free literary assistant. Answer the user's question "
        "using ONLY the provided knowledge-graph context. If the context does "
        "not contain the answer, say you don't know yet. Never invent events "
        "or use prior knowledge of the book."
    )
    user = (
        f"Question: {question}\n\n"
        "Context (allowed nodes from the reader's current progress):\n"
        + "\n".join(f"- {c}" for c in context)
    )
    response = await LLMGateway.acreate_structured_output(
        text_input=user,
        system_prompt=system,
        response_model=_SpoilerSafeAnswer,
    )
    return response.answer
```

Then modify `query_book` to call it for `GRAPH_COMPLETION`. Replace the `results = _answer_from_allowed_nodes(...)` line and the return statement with:

```python
    results = _answer_from_allowed_nodes(book_id, req.question, current_chapter)

    if req.search_type == "GRAPH_COMPLETION" and results:
        context = [r.content for r in results[:15]]
        answer = await _complete_over_context(req.question, context)
        results = [QueryResultItem(content=answer, entity_type=None, chapter=None)] + results

    return QueryResponse(
        book_id=book_id,
        question=req.question,
        search_type=req.search_type,
        current_chapter=current_chapter,
        results=results,
        result_count=len(results),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(query): LLM completion over pre-filtered context"
```

---

## Task 11: Write a backfill script for existing batch JSONs

**Files:**
- Create: `scripts/backfill_last_known_chapter.py`
- Test: none (one-shot script; tested by running it)

- [ ] **Step 1: Create the script**

Create `scripts/backfill_last_known_chapter.py`:

```python
"""One-shot backfill: add last_known_chapter = first_chapter to every node
in every batch JSON under data/processed/*/batches/ that doesn't already
have it. Safe to re-run (idempotent).

Usage:
    python scripts/backfill_last_known_chapter.py              # all books
    python scripts/backfill_last_known_chapter.py --book BOOK_ID
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.config import BookRAGConfig

_NODE_COLLECTIONS = ("characters", "locations", "factions", "themes", "relationships")


def backfill_file(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for collection in _NODE_COLLECTIONS:
        for node in data.get(collection, []) or []:
            if "first_chapter" in node and "last_known_chapter" not in node:
                node["last_known_chapter"] = node["first_chapter"]
                changed += 1
    if changed:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", help="Book ID (default: all)")
    args = parser.parse_args()

    config = BookRAGConfig()
    root = Path(config.processed_dir)
    targets = [root / args.book] if args.book else list(root.iterdir())

    total = 0
    for book_dir in targets:
        batches = book_dir / "batches"
        if not batches.exists():
            continue
        for f in batches.glob("*.json"):
            n = backfill_file(f)
            if n:
                print(f"{f}: {n} nodes updated")
            total += n
    print(f"Done. {total} nodes backfilled.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it runs against an existing book (if any)**

Run: `python scripts/backfill_last_known_chapter.py`
Expected: either "Done. 0 nodes backfilled." (clean state) or a list of files updated plus a total count. No stack trace.

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_last_known_chapter.py
git commit -m "chore: backfill script for last_known_chapter on existing batch JSONs"
```

---

## Task 12: Full test sweep + update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Run full backend test suite**

Run: `pytest tests/ -v --tb=short`
Expected: all previously-passing tests still pass; new tests added in this plan also pass. If any pre-existing test breaks, stop and investigate before continuing.

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, under `## Architecture`, add a subsection immediately after "Key Design Pattern: Parenthetical Coref Insertion":

```markdown
### Fog-of-War Retrieval (Phase 0)

Reader progress is persisted per book in `reading_progress.json` (chapter-granular). At query time, `pipeline/spoiler_filter.py` walks `data/processed/{book_id}/batches/*.json` and builds an allowlist of nodes whose `effective_latest_chapter` (= max of `first_chapter`, `last_known_chapter`, `chapter`) is ≤ the reader's cursor. Retrieval runs ONLY over this allowlist — Cognee's default graph search is bypassed because it retrieves over the full dataset before filtering, which leaks spoilers through graph-completion reasoning.

For `GRAPH_COMPLETION` queries, the top-K allowed nodes are passed as context to the LLM via `_complete_over_context`. The LLM never sees post-progress content.

Limitations (addressed in later phases):
- Progress is chapter-granular, not paragraph-granular (Phase 1).
- Each entity has one DataPoint with a single `last_known_chapter`. If the entity's description was written from chapter-5 evidence, a reader at chapter-5 sees the full description; we can't rewind to a "chapter-3 snapshot" of the same entity (Phase 2).
```

Also update the "Temporary Decisions" section: if a decision here resolves something listed there, remove it. (The existing three Temporary Decisions are unrelated — leave them.)

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document Phase 0 fog-of-war retrieval in CLAUDE.md"
```

---

## Self-Review Checklist

Before declaring done:

- [ ] Every DataPoint class (Character, Location, Faction, Theme, Relationship) has `last_known_chapter`; PlotEvent does NOT (intentionally — it has `chapter`).
- [ ] The extraction prompt explicitly requests `last_known_chapter` and explains its semantics.
- [ ] `query_book` no longer calls `cognee.search`; the only retrieval path is `_answer_from_allowed_nodes`.
- [ ] `GRAPH_COMPLETION` still produces an LLM-generated narrative answer, but the LLM prompt only contains allowed-node strings.
- [ ] A test directly asserts that a spoiler-marked chapter-9 node is NOT present in either the returned `results` list or the LLM's context for a cursor of 2.
- [ ] `pytest tests/ -v` passes clean.
- [ ] The backfill script runs idempotently and updates existing batch files on disk.

## Out of Scope (Future Phases)

- **Phase 1:** paragraph-level progress cursor. Frontend sends `{chapter, paragraph}`; backend persists and filters by paragraph within the current chapter using the raw resolved text (not the graph) for within-chapter content.
- **Phase 2:** per-paragraph node snapshots. Re-extraction at paragraph granularity, new versioned schema (`CharacterSnapshot` keyed by identity + window), retrieval scoped to the latest snapshot ≤ cursor. Large cost/time commitment — only pursue if Phase 0+1 aren't sufficient.
