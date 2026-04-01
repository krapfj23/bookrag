"""Shared TSV parsing utilities for BookNLP output files.

BookNLP outputs .tokens, .entities, .quotes, and .supersense files as
tab-separated values. These helpers parse them into Python dicts.
"""
from __future__ import annotations

from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a TSV file into a list of dicts (header -> value)."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    lines = text.split("\n")
    if len(lines) < 2:
        return []

    headers = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        rows.append(dict(zip(headers, values)))
    return rows


def safe_int(value: str) -> int:
    """Parse an int, returning -1 for non-numeric values."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return -1
