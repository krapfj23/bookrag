"""Provenance model + substring validator — Phase A Stage 1 Tasks 1, 3."""
from __future__ import annotations

import pytest

from models.datapoints import (
    Character,
    CharacterExtraction,
    ExtractionResult,
    Provenance,
    Relationship,
    RelationshipExtraction,
)


# =======================================================================
# Task 1 — Provenance model + field presence
# =======================================================================


def test_provenance_model_required_fields():
    p = Provenance(chunk_id="b::chunk_0001", quote="hello", char_start=0, char_end=5)
    assert p.chunk_id == "b::chunk_0001"
    assert p.quote == "hello"
    assert p.char_start == 0
    assert p.char_end == 5


def test_provenance_quote_max_length():
    """Keep quotes compact. 200 chars is the cap."""
    with pytest.raises(ValueError):
        Provenance(
            chunk_id="b::chunk_0001",
            quote="x" * 201,
            char_start=0,
            char_end=201,
        )


def test_provenance_rejects_negative_offsets():
    with pytest.raises(ValueError):
        Provenance(chunk_id="b::chunk_0001", quote="x", char_start=-1, char_end=0)


def test_character_has_provenance_field():
    c = Character(name="Scrooge", first_chapter=1)
    assert c.provenance == []

    c.provenance.append(
        Provenance(chunk_id="b::chunk_0001", quote="Scrooge!", char_start=0, char_end=8)
    )
    assert len(c.provenance) == 1


def test_relationship_has_provenance_field():
    src = Character(name="Scrooge", first_chapter=1)
    tgt = Character(name="Marley", first_chapter=1)
    r = Relationship(
        source=src, target=tgt, relation_type="employs", first_chapter=1,
    )
    assert r.provenance == []


def test_character_extraction_has_provenance_field():
    c = CharacterExtraction(name="Scrooge", first_chapter=1)
    assert c.provenance == []

    c.provenance = [
        Provenance(chunk_id="b::chunk_0001", quote="Scrooge", char_start=0, char_end=7)
    ]
    assert len(c.provenance) == 1


def test_to_datapoints_propagates_provenance():
    prov = Provenance(chunk_id="b::chunk_0001", quote="Scrooge", char_start=0, char_end=7)
    ex = ExtractionResult(
        characters=[CharacterExtraction(name="Scrooge", first_chapter=1, provenance=[prov])],
    )
    dps = ex.to_datapoints(source_chunk_ordinal=0)
    char = next(dp for dp in dps if isinstance(dp, Character))
    assert char.provenance == [prov]


# =======================================================================
# Task 3 — substring validator (helpers live in pipeline.cognee_pipeline)
# =======================================================================


def test_validator_accepts_exact_substring():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    chunk_text = "It was a cold December morning. Scrooge walked to the office."
    assert _quote_matches_chunk_text(chunk_text, "Scrooge walked")
    assert _quote_matches_chunk_text(chunk_text, "cold December morning")


def test_validator_accepts_normalized_whitespace():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    assert _quote_matches_chunk_text(
        "He said  hello  world",
        "He said hello world",
    )


def test_validator_rejects_fabrication():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    chunk_text = "Scrooge walked to the office."
    assert not _quote_matches_chunk_text(chunk_text, "Scrooge flew to Mars")


def test_validator_empty_quote_rejects():
    from pipeline.cognee_pipeline import _quote_matches_chunk_text
    assert not _quote_matches_chunk_text("hello world", "")


def test_validate_extraction_drops_fabricated_entities():
    from pipeline.cognee_pipeline import _validate_provenance
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


def test_validate_extraction_keeps_entities_without_provenance():
    """Old artifacts have no provenance; the validator must not nuke them."""
    from pipeline.cognee_pipeline import _validate_provenance
    extraction = ExtractionResult(
        characters=[
            CharacterExtraction(name="Legacy", first_chapter=1, provenance=[]),
        ],
    )
    filtered = _validate_provenance(extraction, "anything")
    assert [c.name for c in filtered.characters] == ["Legacy"]
