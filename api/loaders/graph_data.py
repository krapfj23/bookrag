"""Disk loader for knowledge-graph data built from batch output files.

Loads extracted DataPoints and emits the nodes+edges JSON shape consumed by
the graph endpoints. ``processed_dir`` is passed in explicitly to keep this
usable outside the FastAPI request lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_batch_datapoints(
    book_id: str, processed_dir: Path, max_chapter: int | None = None
) -> dict:
    """Load extracted DataPoints from batch output files and build graph data."""
    batches_dir = processed_dir / book_id / "batches"
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    type_colors = {
        "Character": "#4363d8",
        "Location": "#3cb44b",
        "Faction": "#911eb4",
        "Theme": "#e6194b",
        "PlotEvent": "#f58231",
    }

    if not batches_dir.exists():
        return {"nodes": [], "edges": []}

    for dp_file in sorted(batches_dir.glob("batch_*/extracted_datapoints.json")):
        data = json.loads(dp_file.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("datapoints", [])

        for dp in items:
            dp_type = dp.get("type") or dp.get("__type__") or "Unknown"
            first_ch = dp.get("first_chapter") or dp.get("chapter")

            if max_chapter and first_ch and int(first_ch) > max_chapter:
                continue

            name = dp.get("name") or dp.get("description", "")[:40]
            node_id = f"{dp_type}:{name}"

            if dp_type in ("Character", "Location", "Faction", "Theme"):
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "label": name,
                        "type": dp_type,
                        "color": type_colors.get(dp_type, "#aaaaaa"),
                        "description": dp.get("description", ""),
                        "chapter": first_ch,
                    }

            if dp_type == "Relationship":
                src = dp.get("source", {})
                tgt = dp.get("target", {})
                src_name = src.get("name", "") if isinstance(src, dict) else str(src)
                tgt_name = tgt.get("name", "") if isinstance(tgt, dict) else str(tgt)
                if src_name and tgt_name:
                    edges.append({
                        "from": f"Character:{src_name}",
                        "to": f"Character:{tgt_name}",
                        "label": dp.get("relation_type", ""),
                    })

            if dp_type == "PlotEvent":
                event_id = f"PlotEvent:{name}"
                if event_id not in nodes:
                    nodes[event_id] = {
                        "id": event_id,
                        "label": name[:30] + "..." if len(name) > 30 else name,
                        "type": "PlotEvent",
                        "color": type_colors["PlotEvent"],
                        "description": dp.get("description", ""),
                        "chapter": first_ch,
                    }
                for participant in dp.get("participants", []):
                    p_name = participant.get("name", "") if isinstance(participant, dict) else str(participant)
                    if p_name:
                        edges.append({
                            "from": f"Character:{p_name}",
                            "to": event_id,
                            "label": "participates_in",
                        })

    return {"nodes": list(nodes.values()), "edges": edges}
