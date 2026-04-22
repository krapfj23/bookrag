"""Stamp existing batch JSONs with Phase A Stage 1 schema fields.

Walks ``data/processed/*/batches/*/extracted_datapoints.json`` and adds
the new fields introduced in Phase A Stage 1 (see
``docs/superpowers/plans/2026-04-22-phase-a-stage-1-plan.md``):

- `provenance: []` on every DataPoint dict that lacks it
- `booknlp_coref_id: null` on Character dicts that lack it
- `valence: 0.0`, `confidence: 1.0` on Relationship dicts that lack them

Idempotent: re-running leaves already-migrated files unchanged.
Pre-Phase-A values are preserved wherever present.

Usage::

    python -m scripts.migrate_batches_to_phase_a_schema --data-dir data/processed
    python -m scripts.migrate_batches_to_phase_a_schema --dry-run

The ``--dry-run`` flag prints the diff plan without writing.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


PHASE_A_FIELD_DEFAULTS: dict[str, dict[str, Any]] = {
    "Character":    {"provenance": [], "booknlp_coref_id": None},
    "Location":     {"provenance": []},
    "Faction":      {"provenance": []},
    "PlotEvent":    {"provenance": []},
    "Theme":        {"provenance": []},
    "Relationship": {"provenance": [], "valence": 0.0, "confidence": 1.0},
}


def _migrate_datapoint(dp: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (updated_dp, changed)."""
    dp_type = dp.get("type")
    defaults = PHASE_A_FIELD_DEFAULTS.get(dp_type, {"provenance": []})
    changed = False
    for field, default in defaults.items():
        if field not in dp:
            dp[field] = default
            changed = True
    return dp, changed


def migrate_file(path: Path, *, dry_run: bool = False) -> dict[str, int]:
    """Migrate a single extracted_datapoints.json file.

    Returns a stats dict with counts of total dps, migrated dps, types touched.
    """
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        return {"total": 0, "migrated": 0, "skipped_non_list": 1}

    migrated_count = 0
    for i, dp in enumerate(payload):
        if not isinstance(dp, dict):
            continue
        _, changed = _migrate_datapoint(dp)
        if changed:
            migrated_count += 1

    if not dry_run and migrated_count > 0:
        _atomic_write(path, payload)

    return {
        "total": len(payload),
        "migrated": migrated_count,
        "skipped_non_list": 0,
    }


def _atomic_write(path: Path, payload: list[dict]) -> None:
    """Write JSON via tempfile+rename to avoid half-written files on crash."""
    tmp = tempfile.NamedTemporaryFile(
        "w", delete=False, dir=path.parent, suffix=".tmp"
    )
    try:
        json.dump(payload, tmp, indent=2)
        tmp.flush()
        tmp.close()
        Path(tmp.name).replace(path)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def migrate_book(book_dir: Path, *, dry_run: bool = False) -> dict[str, int]:
    """Migrate all batches/*/extracted_datapoints.json under a book directory."""
    totals = {"files": 0, "total_dps": 0, "migrated_dps": 0}
    for path in sorted(book_dir.glob("batches/*/extracted_datapoints.json")):
        stats = migrate_file(path, dry_run=dry_run)
        totals["files"] += 1
        totals["total_dps"] += stats["total"]
        totals["migrated_dps"] += stats["migrated"]
    return totals


def migrate_all(data_dir: Path, *, dry_run: bool = False) -> dict[str, int]:
    """Walk every book directory under data_dir."""
    grand = {"books": 0, "files": 0, "total_dps": 0, "migrated_dps": 0}
    for book_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        stats = migrate_book(book_dir, dry_run=dry_run)
        if stats["files"] == 0:
            continue
        grand["books"] += 1
        grand["files"] += stats["files"]
        grand["total_dps"] += stats["total_dps"]
        grand["migrated_dps"] += stats["migrated_dps"]
        print(
            f"  {book_dir.name}: {stats['files']} files, "
            f"{stats['migrated_dps']}/{stats['total_dps']} dps migrated"
        )
    return grand


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/processed"),
        help="Path to data/processed (default: data/processed)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print counts without writing",
    )
    args = parser.parse_args(argv)

    if not args.data_dir.exists():
        print(f"error: {args.data_dir} does not exist", file=sys.stderr)
        return 1

    mode = "dry-run" if args.dry_run else "writing"
    print(f"Migrating batches under {args.data_dir} ({mode})...")
    totals = migrate_all(args.data_dir, dry_run=args.dry_run)
    print(
        f"Done. {totals['books']} books, {totals['files']} files, "
        f"{totals['migrated_dps']}/{totals['total_dps']} datapoints touched."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
