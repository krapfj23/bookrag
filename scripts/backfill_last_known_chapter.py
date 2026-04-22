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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
