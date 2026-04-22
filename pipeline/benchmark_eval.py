"""Evaluation helpers for the chunk-size ablation benchmark.

Pure-function scorers — take extracted DataPoints and a gold JSON, return
recall / precision / hallucination metrics. See
``docs/superpowers/plans/2026-04-22-phase-a-integration-roadmap.md`` § Stage 3
for the benchmarking methodology.

Keeping these decoupled from run_bookrag_pipeline means we can unit-test the
scorers with synthetic data — no LLM required.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace for matching."""
    if not s:
        return ""
    out = []
    for c in s.lower():
        if c.isalnum() or c == " ":
            out.append(c)
    return " ".join("".join(out).split())


def _all_forms(entry: dict) -> set[str]:
    """All acceptable names for a gold character/entity: canonical + aliases."""
    forms = {_normalize(entry.get("name", ""))}
    for a in entry.get("aliases", []):
        forms.add(_normalize(a))
    forms.discard("")
    return forms


def _entity_matches_gold(extracted_name: str, gold_entry: dict) -> bool:
    """True if ``extracted_name`` matches the gold entry's canonical name or
    any of its aliases under normalized comparison.
    """
    n = _normalize(extracted_name)
    if not n:
        return False
    return n in _all_forms(gold_entry)


# ---------------------------------------------------------------------------
# Entity recall
# ---------------------------------------------------------------------------


def compute_entity_recall(
    extracted: list[dict],
    gold: dict,
    tier: str | None = None,
) -> dict[str, float]:
    """Fraction of gold characters whose name or alias appears in extracted.

    Args:
        extracted: List of DataPoint dicts (as serialized to
            ``extracted_datapoints.json``). Only items with ``type ==
            "Character"`` are considered.
        gold: Parsed gold JSON (see ``tests/golds/christmas_carol_gold.json``).
        tier: Optional filter — "major" or "minor". When set, recall is
            computed only against gold entries of that tier.

    Returns:
        ``{"recall": float, "found": int, "total": int, "missed": [names]}``.
    """
    gold_chars = gold.get("characters", [])
    if tier:
        gold_chars = [g for g in gold_chars if g.get("tier") == tier]
    if not gold_chars:
        return {"recall": 0.0, "found": 0, "total": 0, "missed": []}

    extracted_chars = [e for e in extracted if e.get("type") == "Character"]

    found = []
    missed = []
    for gold_entry in gold_chars:
        hit = any(
            _entity_matches_gold(e.get("name", ""), gold_entry)
            or any(
                _entity_matches_gold(a, gold_entry)
                for a in e.get("aliases", []) or []
            )
            for e in extracted_chars
        )
        if hit:
            found.append(gold_entry["name"])
        else:
            missed.append(gold_entry["name"])

    total = len(gold_chars)
    return {
        "recall": len(found) / total if total else 0.0,
        "found": len(found),
        "total": total,
        "missed": missed,
    }


# ---------------------------------------------------------------------------
# Relationship recall
# ---------------------------------------------------------------------------


def compute_relationship_recall(
    extracted: list[dict],
    gold: dict,
) -> dict[str, float]:
    """Fraction of gold relationships whose (source, target) pair appears in
    extracted. Type and direction are NOT required to match — narrative
    "who knows who" is the minimum bar; valence/type accuracy is a separate
    metric that tends to vary by model.

    Relationships in ``extracted`` may use either the nested shape
    (``{"source": {"name": ...}, ...}``) or flat (``{"source_name": ...}``).
    """
    gold_rels = gold.get("relationships", [])
    if not gold_rels:
        return {"recall": 0.0, "found": 0, "total": 0, "missed": []}

    gold_chars = {g["name"]: g for g in gold.get("characters", [])}

    def _endpoint_name(rel: dict, field: str) -> str | None:
        flat = rel.get(f"{field}_name")
        if isinstance(flat, str) and flat:
            return flat
        nested = rel.get(field)
        if isinstance(nested, dict):
            return nested.get("name")
        return None

    extracted_pairs: set[tuple[str, str]] = set()
    for rel in extracted:
        if rel.get("type") != "Relationship":
            continue
        s = _endpoint_name(rel, "source")
        t = _endpoint_name(rel, "target")
        if s and t:
            extracted_pairs.add((_normalize(s), _normalize(t)))
            extracted_pairs.add((_normalize(t), _normalize(s)))  # undirected match

    def _gold_forms(name: str) -> set[str]:
        g = gold_chars.get(name)
        return _all_forms(g) if g else {_normalize(name)}

    found = []
    missed = []
    for gold_rel in gold_rels:
        src_forms = _gold_forms(gold_rel["source"])
        tgt_forms = _gold_forms(gold_rel["target"])
        hit = any(
            (s, t) in extracted_pairs
            for s in src_forms for t in tgt_forms
        )
        tag = f"{gold_rel['source']} → {gold_rel['target']} ({gold_rel.get('type','?')})"
        if hit:
            found.append(tag)
        else:
            missed.append(tag)

    total = len(gold_rels)
    return {
        "recall": len(found) / total if total else 0.0,
        "found": len(found),
        "total": total,
        "missed": missed,
    }


# ---------------------------------------------------------------------------
# Provenance pass rate
# ---------------------------------------------------------------------------


def compute_provenance_pass_rate(extracted: list[dict]) -> dict[str, float]:
    """Fraction of extracted items that carry at least one provenance quote.

    Phase A Stage 1 validator drops items with fabricated quotes, so if
    provenance coverage is low here it's usually because the LLM didn't emit
    any — a prompt-compliance signal more than a hallucination signal.
    """
    considered = [
        e for e in extracted
        if e.get("type") in (
            "Character", "Location", "Faction",
            "PlotEvent", "Relationship", "Theme",
        )
    ]
    if not considered:
        return {"rate": 0.0, "with_provenance": 0, "total": 0}

    with_prov = sum(1 for e in considered if e.get("provenance"))
    return {
        "rate": with_prov / len(considered),
        "with_provenance": with_prov,
        "total": len(considered),
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_run(
    extracted: list[dict],
    gold: dict,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One-shot score summary for a single chunk_size ingestion run."""
    return {
        "entity_recall_all": compute_entity_recall(extracted, gold),
        "entity_recall_major": compute_entity_recall(extracted, gold, tier="major"),
        "entity_recall_minor": compute_entity_recall(extracted, gold, tier="minor"),
        "relationship_recall": compute_relationship_recall(extracted, gold),
        "provenance_pass_rate": compute_provenance_pass_rate(extracted),
        "counts": {
            "characters": sum(1 for e in extracted if e.get("type") == "Character"),
            "locations": sum(1 for e in extracted if e.get("type") == "Location"),
            "events": sum(1 for e in extracted if e.get("type") == "PlotEvent"),
            "relationships": sum(1 for e in extracted if e.get("type") == "Relationship"),
            "themes": sum(1 for e in extracted if e.get("type") == "Theme"),
        },
        "extra": extra or {},
    }


def load_gold(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def pick_winner(
    summaries: list[dict],
    cost_ceiling_multiplier: float = 1.5,
    min_provenance_rate: float = 0.80,
) -> dict | None:
    """Apply the acceptance criterion from the Stage-3 plan:
      winner = argmax(minor_char_recall)
      subject to (cost_usd <= 1.5 * baseline) AND (provenance_rate >= 0.80)

    ``summaries`` must each include ``extra.chunk_size`` and ``extra.cost_usd``.
    Returns the winning summary or None if no candidate meets the constraints.
    The baseline cost is the summary with the smallest ``chunk_size`` (= highest
    cost), which provides a conservative ceiling.
    """
    if not summaries:
        return None

    with_cost = [
        s for s in summaries
        if s.get("extra", {}).get("cost_usd") is not None
    ]
    if not with_cost:
        return None

    baseline_cost = min(s["extra"]["cost_usd"] for s in with_cost)
    if baseline_cost <= 0:
        baseline_cost = 1e-9
    ceiling = cost_ceiling_multiplier * baseline_cost

    eligible = [
        s for s in with_cost
        if s["extra"]["cost_usd"] <= ceiling
        and s["provenance_pass_rate"]["rate"] >= min_provenance_rate
    ]
    if not eligible:
        return None

    return max(eligible, key=lambda s: s["entity_recall_minor"]["recall"])
