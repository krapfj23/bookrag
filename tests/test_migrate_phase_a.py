"""Phase A Stage 1 Task 8 — migrator idempotency + field stamping."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.migrate_batches_to_phase_a_schema import (
    migrate_book,
    migrate_file,
    migrate_all,
)


def _write_batch(tmp_path: Path, payload: list[dict]) -> Path:
    batch_dir = tmp_path / "batches" / "batch_01"
    batch_dir.mkdir(parents=True)
    path = batch_dir / "extracted_datapoints.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def test_migrator_stamps_provenance_on_character(tmp_path):
    path = _write_batch(tmp_path, [
        {"id": "x", "type": "Character", "name": "Scrooge", "first_chapter": 1},
    ])
    migrate_book(tmp_path)
    payload = json.loads(path.read_text())
    assert payload[0]["provenance"] == []
    assert payload[0]["booknlp_coref_id"] is None


def test_migrator_stamps_provenance_valence_on_relationship(tmp_path):
    path = _write_batch(tmp_path, [
        {"id": "r", "type": "Relationship", "relation_type": "employs"},
    ])
    migrate_book(tmp_path)
    payload = json.loads(path.read_text())
    assert payload[0]["provenance"] == []
    assert payload[0]["valence"] == 0.0
    assert payload[0]["confidence"] == 1.0
    assert payload[0]["relation_type"] == "employs"  # preserved


def test_migrator_stamps_provenance_on_location_faction_event_theme(tmp_path):
    path = _write_batch(tmp_path, [
        {"id": "l", "type": "Location", "name": "London"},
        {"id": "f", "type": "Faction", "name": "Cratchits"},
        {"id": "e", "type": "PlotEvent", "description": "ate dinner"},
        {"id": "t", "type": "Theme", "name": "redemption"},
    ])
    migrate_book(tmp_path)
    payload = json.loads(path.read_text())
    for dp in payload:
        assert dp["provenance"] == []


def test_migrator_preserves_existing_provenance(tmp_path):
    path = _write_batch(tmp_path, [
        {
            "id": "x", "type": "Character", "name": "Scrooge",
            "provenance": [
                {"chunk_id": "b::chunk_0001", "quote": "Scrooge",
                 "char_start": 0, "char_end": 7}
            ],
        },
    ])
    migrate_book(tmp_path)
    payload = json.loads(path.read_text())
    assert len(payload[0]["provenance"]) == 1


def test_migrator_preserves_existing_valence(tmp_path):
    path = _write_batch(tmp_path, [
        {"id": "r", "type": "Relationship", "valence": -0.7, "confidence": 0.8},
    ])
    migrate_book(tmp_path)
    payload = json.loads(path.read_text())
    assert payload[0]["valence"] == -0.7
    assert payload[0]["confidence"] == 0.8


def test_migrator_idempotent(tmp_path):
    path = _write_batch(tmp_path, [
        {"id": "x", "type": "Character", "name": "Scrooge", "first_chapter": 1},
    ])
    migrate_book(tmp_path)
    first = path.read_text()
    migrate_book(tmp_path)
    second = path.read_text()
    assert first == second


def test_dry_run_does_not_write(tmp_path):
    original_payload = [{"id": "x", "type": "Character", "name": "Scrooge"}]
    path = _write_batch(tmp_path, original_payload)
    migrate_file(path, dry_run=True)
    assert json.loads(path.read_text()) == original_payload


def test_migrate_all_handles_empty_data_dir(tmp_path):
    totals = migrate_all(tmp_path)
    assert totals["books"] == 0


def test_migrate_all_skips_books_without_batches(tmp_path):
    (tmp_path / "empty_book").mkdir()
    totals = migrate_all(tmp_path)
    assert totals["books"] == 0
