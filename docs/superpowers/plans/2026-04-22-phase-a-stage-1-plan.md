# Phase A Stage 1 — Schema Bundle

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the four Phase-A schema extensions (items 2, 8, 11, 12 from the roadmap) plus the strict-mode compliance fix deferred from Stage 0. Bundled so one migration of `data/processed/*/batches/*.json` covers all changes.

**Architecture:** Additive field extensions on `Character`, `Relationship`, `PlotEvent`, `Location`, `Faction`, `Theme`, and `ExtractionResult`. Every new field is nullable-with-default so old artifacts still deserialize. A one-shot migrator stamps `extractor_version="pre-phase-a"` on existing batch JSONs.

**Tech stack:** Pydantic v2, Cognee `DataPoint`, BookNLP TSV `COREF` column.

**Source:** `docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md` § Stage 1.

**Baseline:** 1083 passing tests at start of Stage 1.

---

## Task order and coupling

1. **Task 1:** `Provenance` model + `provenance: list[Provenance] = []` on every DataPoint. Foundation for Task 3 validator.
2. **Task 2:** `RelationshipType` enum + `valence: float` + `confidence: float` on `Relationship`. Independent of Task 1.
3. **Task 3:** Substring validator in `_validate_relationships`. Depends on Task 1.
4. **Task 4:** `booknlp_coref_id: int | None` on `Character` + surface from `coref_resolver.py`. Independent.
5. **Task 5:** `extractor_version`, `prompt_hash`, `model_id`, `schema_version`, `cache_key`, `created_at` on `ExtractionResult`. Independent.
6. **Task 6:** Content-addressed batch cache (reads/writes `data/cache/extractions/{cache_key}.json`). Depends on Task 5.
7. **Task 7:** Strict-mode schema compliance pass (`additionalProperties=False`, all-required, inline `$ref`). Runs last — covers everything added in Tasks 1-5.
8. **Task 8:** Migrator `scripts/migrate_batches_to_phase_a_schema.py`. Stamps old batch JSONs with `extractor_version="pre-phase-a"`.

Prompt updates (to `prompts/extraction_prompt.txt`) accompany Tasks 1, 2, 4 — the LLM needs to know about the new fields.

---

### Task 1 — Provenance field

**Why:** Every extraction claim should carry evidence. Enables Task 3 validator and future hallucination audits.

**Files:**
- Modify: `models/datapoints.py` (add `Provenance`, extend all DataPoints and extraction models)
- Modify: `prompts/extraction_prompt.txt` (instruct LLM to emit `provenance`)
- Test: `tests/test_datapoints.py` (new)
- Test: `tests/test_provenance.py` (new file)

- [ ] **Step 1: Write the failing tests**

In `tests/test_provenance.py` (new file):

```python
"""Provenance model and substring validator — Phase A Stage 1 Task 1/3."""
import pytest
from models.datapoints import Provenance, Character, Relationship


def test_provenance_model_required_fields():
    p = Provenance(chunk_id="b::chunk_0001", quote="hello", char_start=0, char_end=5)
    assert p.chunk_id == "b::chunk_0001"
    assert p.quote == "hello"


def test_provenance_quote_max_length():
    """Keep quotes compact. 200 chars is the cap."""
    with pytest.raises(ValueError):
        Provenance(
            chunk_id="b::chunk_0001",
            quote="x" * 201,
            char_start=0,
            char_end=201,
        )


def test_character_has_provenance_field():
    c = Character(name="Scrooge", first_chapter=1)
    assert c.provenance == []

    c.provenance.append(
        Provenance(chunk_id="b::chunk_0001", quote="Scrooge!", char_start=0, char_end=8)
    )
    assert len(c.provenance) == 1


def test_relationship_has_provenance_field():
    from uuid import uuid4
    r = Relationship(source_id=uuid4(), target_id=uuid4(), relation_type="ALLY")
    assert r.provenance == []
```

- [ ] **Step 2: Run — verify failures**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/test_provenance.py -v
```

Expected: all 4 fail (Provenance doesn't exist, DataPoints lack `provenance` field).

- [ ] **Step 3: Add Provenance model**

Insert near top of `models/datapoints.py` (after imports, before DataPoint subclasses):

```python
from pydantic import BaseModel, Field, field_validator


class Provenance(BaseModel):
    """Evidence for an extracted entity/event/relationship.

    Emitted by the LLM alongside each DataPoint so downstream validators
    can confirm the extraction is grounded in actual text (not hallucinated).
    See Task 3 for the substring validator that consumes this.
    """

    chunk_id: str = Field(..., description="<book_id>::chunk_<ordinal:04d>")
    quote: str = Field(..., description="Verbatim snippet from chunk text, <=200 chars")
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., ge=0)

    @field_validator("quote")
    @classmethod
    def _quote_bounded(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError(f"quote must be <=200 chars, got {len(v)}")
        return v
```

- [ ] **Step 4: Add `provenance` field to DataPoints and extraction models**

Extend `Character`, `Location`, `Faction`, `PlotEvent`, `Relationship`, `Theme`, and their `*Extraction` mirrors:

```python
    provenance: list[Provenance] = []
```

For the `*Extraction` classes (LLM-facing), mirror the same field. `to_datapoints()` should propagate `provenance` through.

- [ ] **Step 5: Update `to_datapoints` to copy provenance**

At every `Character(...)`, `PlotEvent(...)`, etc. constructor inside `to_datapoints`, pass `provenance=<extraction>.provenance`.

- [ ] **Step 6: Update extraction prompt**

In `prompts/extraction_prompt.txt`, add a new section after the "Relation Labels" block:

```
## Provenance

For every Character, Location, Faction, PlotEvent, Relationship, and Theme
you extract, emit at least one `provenance` entry that evidences it. Each
provenance entry has:

- `chunk_id`: use the exact chunk id shown in the user message header
- `quote`: the verbatim text (<=200 chars) from the chunk that supports
  the extraction. Copy it character-for-character — do NOT paraphrase or
  "tidy up" punctuation.
- `char_start`, `char_end`: the character offsets of the quote within the
  chunk text.

If you cannot find a supporting quote, do NOT extract the entity. Fabricated
provenance is worse than missing data.
```

- [ ] **Step 7: Run new tests — verify pass**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/test_provenance.py -v
```

Expected: all 4 pass.

- [ ] **Step 8: Run full suite — no regressions**

```
/Users/jeffreykrapf/anaconda3/bin/python -m pytest tests/ -q --tb=short
```

Expected: 1087 passing (1083 + 4 new).

- [ ] **Step 9: Commit**

```
git add models/datapoints.py prompts/extraction_prompt.txt tests/test_provenance.py
git commit -m "feat(datapoints): add Provenance model and provenance field on all DataPoints

Every DataPoint (Character, Location, Faction, PlotEvent, Relationship,
Theme) and its *Extraction mirror now carries provenance: list[Provenance].
Provenance has chunk_id, quote (<=200 chars, verbatim), char_start, char_end.

Prompt updated: LLM instructed to emit at least one provenance entry per
extraction and not paraphrase quotes. Task 3 will add a substring validator
that drops extractions whose quotes don't match chunk text.

Phase A Stage 1 / Item 2."
```

---

### Task 2 — `RelationshipType` enum + signed valence

**Why:** Free-string `relation_type` admits LLM drift (\"employs\", \"is_nephew_of\", \"worked_for\" all for ~same concept). Enum of ~10 canonical narrative relations + a `valence` float in `[-1, 1]` lets us aggregate cleanly and reason about arcs.

**Files:**
- Modify: `models/datapoints.py` (new `RelationshipType`, add `valence`/`confidence` to `Relationship` + `RelationshipExtraction`)
- Modify: `prompts/extraction_prompt.txt` (swap free-string label list for enum + anchored valence scale)
- Test: `tests/test_datapoints.py` (enum cases + valence bounds)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_datapoints.py — append
def test_relationship_type_enum_values():
    from models.datapoints import RelationshipType
    assert RelationshipType.ALLY.value == "ally"
    assert set(RelationshipType) >= {
        RelationshipType.FAMILY, RelationshipType.ROMANTIC, RelationshipType.FRIEND,
        RelationshipType.ALLY, RelationshipType.MENTOR, RelationshipType.SUBORDINATE,
        RelationshipType.RIVAL, RelationshipType.ENEMY,
        RelationshipType.ACQUAINTANCE, RelationshipType.UNKNOWN,
    }


def test_relationship_valence_bounds():
    import pytest
    from uuid import uuid4
    from models.datapoints import Relationship, RelationshipType
    with pytest.raises(ValueError):
        Relationship(
            source_id=uuid4(), target_id=uuid4(),
            relation_type=RelationshipType.ALLY, valence=1.5,
        )
    with pytest.raises(ValueError):
        Relationship(
            source_id=uuid4(), target_id=uuid4(),
            relation_type=RelationshipType.ALLY, valence=-1.1,
        )


def test_relationship_valence_default_zero():
    from uuid import uuid4
    from models.datapoints import Relationship, RelationshipType
    r = Relationship(
        source_id=uuid4(), target_id=uuid4(), relation_type=RelationshipType.ALLY,
    )
    assert r.valence == 0.0
    assert r.confidence == 1.0


def test_relationship_accepts_string_enum_value():
    """Backward compat: old batch JSONs serialize relation_type as string."""
    from uuid import uuid4
    from models.datapoints import Relationship, RelationshipType
    r = Relationship(
        source_id=uuid4(), target_id=uuid4(), relation_type="ally",
    )
    assert r.relation_type == RelationshipType.ALLY
```

- [ ] **Step 2: Run — verify failures**

- [ ] **Step 3: Add the enum and fields**

```python
# models/datapoints.py
from enum import Enum
from pydantic import Field, field_validator


class RelationshipType(str, Enum):
    """Canonical narrative relationship categories.

    Kept small (10 entries) so the LLM reliably picks the best fit in
    strict-mode structured output. MENTOR/SUBORDINATE encode direction
    in (source, target); FAMILY/ROMANTIC/ENEMY are symmetric.
    """
    FAMILY       = "family"
    ROMANTIC     = "romantic"
    FRIEND       = "friend"
    ALLY         = "ally"
    MENTOR       = "mentor"
    SUBORDINATE  = "subordinate"
    RIVAL        = "rival"
    ENEMY        = "enemy"
    ACQUAINTANCE = "acquaintance"
    UNKNOWN      = "unknown"
```

In `Relationship` (DataPoint subclass) and `RelationshipExtraction`:

```python
    relation_type: RelationshipType = RelationshipType.UNKNOWN
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
```

- [ ] **Step 4: Update prompt**

In `prompts/extraction_prompt.txt`, replace the existing "Relation Labels" section with:

```
## Relationship Type

Classify every relationship into ONE of these 10 types:

- `family` — blood or marriage ties (symmetric)
- `romantic` — romantic partners (symmetric)
- `friend` — personal friendship
- `ally` — cooperative non-friend (political, situational)
- `mentor` — teacher → student (directional: source = mentor)
- `subordinate` — subordinate → superior (directional: source = subordinate)
- `rival` — competitive (symmetric)
- `enemy` — hostile (symmetric)
- `acquaintance` — knows, no deeper bond
- `unknown` — insufficient evidence

## Valence

Assign each relationship a `valence` in [-1.0, +1.0]:

-1.0 = murderous hatred
-0.5 = rivalry, contempt
 0.0 = neutral, formal, professional
+0.5 = friendship, respect
+1.0 = devoted love

Prefer the midpoints (-0.5, 0.5) unless the text is unambiguous at the
extremes.

Also emit `confidence` in [0.0, 1.0] reflecting your certainty in the
(type, valence) assignment.
```

- [ ] **Step 5-7: Run tests, full suite, commit**

Expected: 1091 passing (1087 + 4 new).

Commit message:
```
feat(datapoints): RelationshipType enum + signed valence + confidence

Replaces free-string relation_type with a 10-entry enum (family, romantic,
friend, ally, mentor, subordinate, rival, enemy, acquaintance, unknown).
Adds valence ∈ [-1, 1] (anchored: murderous=-1, neutral=0, devoted love=+1)
and confidence ∈ [0, 1].

Backward compat: Pydantic accepts string enum values, so old batch JSONs
deserialize. Prompt updated with the enum + anchored valence scale.

Phase A Stage 1 / Item 11.
```

---

### Task 3 — Substring validator

**Why:** Catches hallucinated extractions before they enter the graph.

**Files:**
- Modify: `pipeline/cognee_pipeline.py` (extend `_validate_relationships` and add a new `_validate_provenance`)
- Test: `tests/test_provenance.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_provenance.py — append
def test_validator_accepts_exact_substring():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    chunk_text = "It was a cold December morning. Scrooge walked to the office."
    assert _quote_matches_chunk_text(chunk_text, "Scrooge walked")
    assert _quote_matches_chunk_text(chunk_text, "cold December morning")


def test_validator_accepts_normalized_whitespace():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    assert _quote_matches_chunk_text(
        "He said  hello  world",  # double-spaced
        "He said hello world",     # single-spaced
    )


def test_validator_rejects_fabrication():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    chunk_text = "Scrooge walked to the office."
    assert not _quote_matches_chunk_text(chunk_text, "Scrooge flew to Mars")


def test_validate_extraction_drops_fabricated_entities():
    from pipeline.cognee_pipeline import _validate_provenance
    from models.datapoints import CharacterExtraction, Provenance, ExtractionResult

    chunk_text = "Scrooge walked to the office."
    extraction = ExtractionResult(
        characters=[
            CharacterExtraction(
                name="Scrooge", first_chapter=1,
                provenance=[Provenance(
                    chunk_id="b::chunk_0001", quote="Scrooge walked",
                    char_start=0, char_end=14,
                )],
            ),
            CharacterExtraction(
                name="Fabricated", first_chapter=1,
                provenance=[Provenance(
                    chunk_id="b::chunk_0001", quote="never said this",
                    char_start=0, char_end=15,
                )],
            ),
        ],
    )
    filtered = _validate_provenance(extraction, chunk_text)
    names = {c.name for c in filtered.characters}
    assert names == {"Scrooge"}
```

- [ ] **Step 2: Implement the validator**

```python
# pipeline/cognee_pipeline.py
import re

def _quote_matches_chunk_text(chunk_text: str, quote: str) -> bool:
    """Three-tier match: exact substring → whitespace-normalized → lowercase."""
    if not quote:
        return False
    if quote in chunk_text:
        return True
    normalize = lambda s: re.sub(r"\s+", " ", s).strip()
    if normalize(quote) in normalize(chunk_text):
        return True
    if normalize(quote).lower() in normalize(chunk_text).lower():
        return True
    return False


def _validate_provenance(
    extraction: ExtractionResult, chunk_text: str
) -> ExtractionResult:
    """Drop extractions whose quotes don't appear in the chunk text.

    Entities without provenance are kept (the field is optional on old
    artifacts). Entities with provenance are required to match.
    """
    def _keep(entity):
        if not getattr(entity, "provenance", None):
            return True
        return any(
            _quote_matches_chunk_text(chunk_text, p.quote)
            for p in entity.provenance
        )

    extraction.characters = [c for c in extraction.characters if _keep(c)]
    extraction.locations = [l for l in extraction.locations if _keep(l)]
    extraction.factions = [f for f in extraction.factions if _keep(f)]
    extraction.events = [e for e in extraction.events if _keep(e)]
    extraction.relationships = [r for r in extraction.relationships if _keep(r)]
    extraction.themes = [t for t in extraction.themes if _keep(t)]
    return extraction
```

Call it in `extract_enriched_graph` right before `_validate_relationships`:

```python
    extraction = _validate_provenance(extraction, chunk.text)
    extraction = _validate_relationships(extraction)
```

- [ ] **Step 3-5: Run tests, full suite, commit**

Expected: 1095 passing (1091 + 4 new).

---

### Task 4 — BookNLP `cluster_id` on Character

**Why:** Disambiguates \"Ebenezer\", \"Scrooge\", \"Mr. Scrooge\" into one identity keyed by BookNLP's `COREF` column — more reliable than name-fuzz matching.

**Files:**
- Modify: `models/datapoints.py` (`Character.booknlp_coref_id: int | None`)
- Modify: `pipeline/coref_resolver.py` (already populates clusters — surface `cluster_id` on the sidecar passed to extraction)
- Modify: `pipeline/cognee_pipeline.py` (thread coref hints through `render_prompt`)
- Modify: `prompts/extraction_prompt.txt` (instruct LLM to emit `booknlp_coref_id` when known)
- Test: `tests/test_datapoints.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_datapoints.py — append
def test_character_has_booknlp_coref_id_field():
    from models.datapoints import Character
    c = Character(name="Scrooge", first_chapter=1, booknlp_coref_id=42)
    assert c.booknlp_coref_id == 42


def test_character_coref_id_defaults_to_none():
    from models.datapoints import Character
    c = Character(name="Scrooge", first_chapter=1)
    assert c.booknlp_coref_id is None
```

- [ ] **Step 2: Implementation**

Add `booknlp_coref_id: int | None = None` to `Character` and `CharacterExtraction`. Propagate in `to_datapoints`.

In `_format_booknlp_entities`, expose `COREF` id alongside entity name so the LLM sees it. Update `prompts/extraction_prompt.txt`:

```
When the BookNLP entity hint includes a coref id (format: `#42 Scrooge`),
copy that id into the character's `booknlp_coref_id` field. This helps
downstream merging pick the right identity.
```

- [ ] **Step 3-5: Run tests, full suite, commit**

Expected: 1097 passing (1095 + 2).

---

### Task 5 — `ExtractionResult` version + cache-key metadata

**Why:** Content-addressed extraction cache needs a stable cache key. Every field here is input to the key.

**Files:**
- Modify: `models/datapoints.py` (`ExtractionResult` gains 6 fields)
- Modify: `pipeline/cognee_pipeline.py` (compute + stamp cache key)
- Test: `tests/test_datapoints.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_datapoints.py — append
def test_extraction_result_has_version_metadata():
    from datetime import datetime, timezone
    from models.datapoints import ExtractionResult
    er = ExtractionResult(
        characters=[], locations=[], events=[],
        relationships=[], themes=[], factions=[],
        extractor_version="phase-a@2026-04-22",
        prompt_hash="deadbeef",
        model_id="openai/gpt-4o-mini",
        schema_version="v1",
        cache_key="abc123",
        created_at=datetime.now(timezone.utc),
    )
    assert er.extractor_version == "phase-a@2026-04-22"


def test_extraction_result_metadata_defaults_empty():
    """Old batch JSONs deserialize with empty strings/None."""
    from models.datapoints import ExtractionResult
    er = ExtractionResult(
        characters=[], locations=[], events=[],
        relationships=[], themes=[], factions=[],
    )
    assert er.extractor_version == ""
    assert er.cache_key == ""
```

- [ ] **Step 2: Implementation**

```python
# models/datapoints.py — inside ExtractionResult
    extractor_version: str = ""
    prompt_hash: str = ""
    model_id: str = ""
    schema_version: str = "v1"
    cache_key: str = ""
    created_at: datetime | None = None
```

- [ ] **Step 3-5: Run tests, full suite, commit**

Expected: 1099 passing.

---

### Task 6 — Content-addressed batch cache

**Why:** Re-runs should skip chunks that have already been extracted with an identical (prompt, model, ontology, text).

**Files:**
- Modify: `pipeline/cognee_pipeline.py` (helpers `_compute_cache_key`, `_cache_read`, `_cache_write`; wire into `_extract_one`)
- Test: `tests/test_cognee_pipeline.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_cognee_pipeline.py — append
def test_compute_cache_key_deterministic():
    from pipeline.cognee_pipeline import _compute_cache_key
    k1 = _compute_cache_key(
        prompt_hash="a", model_id="m", schema_version="v1",
        ontology_hash="o", chunk_text_hash="t", max_gleanings=0,
    )
    k2 = _compute_cache_key(
        prompt_hash="a", model_id="m", schema_version="v1",
        ontology_hash="o", chunk_text_hash="t", max_gleanings=0,
    )
    assert k1 == k2


def test_compute_cache_key_sensitive_to_prompt():
    from pipeline.cognee_pipeline import _compute_cache_key
    k1 = _compute_cache_key(prompt_hash="a", model_id="m",
                            schema_version="v1", ontology_hash="o",
                            chunk_text_hash="t", max_gleanings=0)
    k2 = _compute_cache_key(prompt_hash="a-modified", model_id="m",
                            schema_version="v1", ontology_hash="o",
                            chunk_text_hash="t", max_gleanings=0)
    assert k1 != k2
```

- [ ] **Step 2: Implementation**

```python
# pipeline/cognee_pipeline.py
import hashlib
import json

def _compute_cache_key(
    *, prompt_hash: str, model_id: str, schema_version: str,
    ontology_hash: str, chunk_text_hash: str, max_gleanings: int,
) -> str:
    parts = [
        prompt_hash, model_id, schema_version,
        ontology_hash, chunk_text_hash, str(max_gleanings),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return Path("data/cache/extractions") / f"{cache_key}.json"


def _cache_read(cache_key: str) -> ExtractionResult | None:
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        return ExtractionResult.model_validate_json(path.read_text())
    except Exception:
        return None


def _cache_write(cache_key: str, extraction: ExtractionResult) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(extraction.model_dump_json())
```

Wire into `_extract_one`: compute `cache_key` from the chunk + prompt + ontology + model; read from cache; on miss, call LLM and write back.

- [ ] **Step 3-5: Tests, full suite, commit**

---

### Task 7 — Strict-mode schema compliance

**Why:** Deferred from Stage 0. Now that every DataPoint is stable, fix once.

**Files:**
- Modify: `models/datapoints.py` (`ConfigDict(extra="forbid")` on every model; audit optional fields)
- Test: `tests/test_datapoints.py` (new schema compliance validator)

- [ ] **Step 1: Failing test — schema compliance walker**

(See the test shape in `docs/superpowers/plans/2026-04-22-phase-a-stage-0-plan.md` § Task 3a.)

- [ ] **Step 2: Fixes**

Add `model_config = ConfigDict(extra="forbid")` to `Character`, `Location`, `Faction`, `PlotEvent`, `Relationship`, `Theme`, `Provenance`, `ExtractionResult`, and all `*Extraction` mirrors. Audit `Optional[X]` → `X | None` with explicit `default=None`, `required=True`.

Flatten `$ref` in the emitted schema only at the LLM call site (don't change the model definitions). Add a helper `_extraction_result_strict_schema()` that returns the inlined schema JSON.

- [ ] **Step 3-5: Tests, full suite, commit**

---

### Task 8 — Migrator

**Why:** Existing `data/processed/*/batches/*/extracted_datapoints.json` files lack the new fields. Stamp them so they round-trip through the now-stricter Pydantic validation.

**Files:**
- New: `scripts/migrate_batches_to_phase_a_schema.py`
- Test: `tests/test_migrate_phase_a.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_migrate_phase_a.py
import json
from pathlib import Path
from scripts.migrate_batches_to_phase_a_schema import migrate_book


def test_migrator_stamps_extractor_version(tmp_path):
    batch_dir = tmp_path / "batches" / "batch_01"
    batch_dir.mkdir(parents=True)
    (batch_dir / "extracted_datapoints.json").write_text(json.dumps({
        "characters": [{"name": "Scrooge", "first_chapter": 1}],
        "locations": [], "events": [], "relationships": [],
        "themes": [], "factions": [],
    }))
    migrate_book(tmp_path)
    payload = json.loads((batch_dir / "extracted_datapoints.json").read_text())
    assert payload.get("extractor_version") == "pre-phase-a"
    assert "provenance" in payload["characters"][0]
    assert payload["characters"][0]["provenance"] == []


def test_migrator_idempotent(tmp_path):
    batch_dir = tmp_path / "batches" / "batch_01"
    batch_dir.mkdir(parents=True)
    (batch_dir / "extracted_datapoints.json").write_text(json.dumps({
        "characters": [],
        "extractor_version": "phase-a@2026-04-22",
        "locations": [], "events": [], "relationships": [],
        "themes": [], "factions": [],
    }))
    migrate_book(tmp_path)
    payload = json.loads((batch_dir / "extracted_datapoints.json").read_text())
    # Already stamped — don't overwrite a newer version
    assert payload["extractor_version"] == "phase-a@2026-04-22"
```

- [ ] **Step 2: Implement migrator**

Walk `data/processed/*/batches/*/extracted_datapoints.json`. For each file:
- Load JSON
- If `extractor_version` missing or empty, set `extractor_version = "pre-phase-a"`
- Add `provenance: []` to every entity lacking the field
- Add `valence: 0.0`, `confidence: 1.0`, `relation_type: "unknown"` defaults to relationships lacking them
- Add `booknlp_coref_id: None` to characters lacking it
- Write back atomically (temp file + rename)

- [ ] **Step 3-5: Tests, commit**

- [ ] **Step 6: Smoke-run the migrator on the current `data/processed/`**

```
/Users/jeffreykrapf/anaconda3/bin/python -m scripts.migrate_batches_to_phase_a_schema --dry-run
```

Review output. If the diff looks safe, run without `--dry-run`.

---

## Acceptance — end of Stage 1

- All ~20 new tests pass. Expected total ~1105 tests passing.
- Full Christmas Carol ingestion produces valid new-schema JSON; query endpoints still return 200.
- Migrator runs on existing `data/processed/` without data loss.
- `models/datapoints.py` emits a strict-mode-compatible schema when flattened.

## Out of scope (Stage 2)

- Gleaning loop (item 1)
- Realis constraint (item 9)
- Chunk-size ablation (item 3)
- Two-hop spoiler filter (item 10)
