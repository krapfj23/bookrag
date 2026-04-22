"""Knowledge-graph visualization routes.

Two endpoints:
  * ``GET /books/{id}/graph/data`` — JSON nodes+edges
  * ``GET /books/{id}/graph`` — interactive vis.js HTML page

The inline HTML template stays an f-string (Jinja conversion is out of scope
for Slice 2).
"""

from __future__ import annotations

import html as html_mod
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from api.loaders.book_data import get_reading_progress
from api.loaders.graph_data import load_batch_datapoints
from api.routes.books import SafeBookId


router = APIRouter()


def _resolve_graph_max_chapter(
    book_id: str,
    max_chapter: int | None,
    full: bool,
    processed_dir: Path,
) -> int | None:
    """Priority: full=true wins (→None); explicit max_chapter next; else reader progress."""
    if full:
        return None
    if max_chapter is not None:
        return max_chapter
    effective_max, _ = get_reading_progress(book_id, processed_dir)
    return effective_max


@router.get("/books/{book_id}/graph/data")
async def get_graph_data(
    book_id: SafeBookId,
    max_chapter: int | None = Query(default=None, ge=1),
    full: bool = Query(default=False),
) -> dict:
    """Return knowledge graph as JSON nodes and edges, spoiler-filtered by default.

    - When ``max_chapter`` is given, filter to that chapter bound.
    - When ``full=true``, return the full graph (explicit opt-in).
    - Otherwise, default to the reader's current chapter from reading_progress.json.
    """
    from main import config

    processed_dir = Path(config.processed_dir)
    book_dir = processed_dir / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    effective_max = _resolve_graph_max_chapter(book_id, max_chapter, full, processed_dir)
    return load_batch_datapoints(book_id, processed_dir, effective_max)


@router.get("/books/{book_id}/graph", response_class=HTMLResponse)
async def get_graph_visualization(
    book_id: SafeBookId,
    max_chapter: int | None = Query(default=None, ge=1),
    full: bool = Query(default=False),
) -> HTMLResponse:
    """Return an interactive HTML visualization of the knowledge graph, spoiler-filtered by default.

    - When ``max_chapter`` is given, filter to that chapter bound.
    - When ``full=true``, return the full graph (explicit opt-in).
    - Otherwise, default to the reader's current chapter from reading_progress.json.
    """
    from main import config

    processed_dir = Path(config.processed_dir)
    book_dir = processed_dir / book_id
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    effective_max = _resolve_graph_max_chapter(book_id, max_chapter, full, processed_dir)
    graph_data = load_batch_datapoints(book_id, processed_dir, effective_max)

    if not graph_data["nodes"]:
        return HTMLResponse(
            content="<html><body><h2>No graph data available.</h2>"
            "<p>The pipeline may not have completed Phase 2 (Cognee extraction) yet.</p>"
            "</body></html>"
        )

    # Escape JSON for safe embedding in <script type="application/json"> (prevent </script> breakout)
    safe_graph_json = json.dumps(graph_data).replace("</", "<\\/")
    safe_book_id = html_mod.escape(book_id)
    if full:
        chapter_label = " (full)"
    else:
        chapter_label = html_mod.escape(f" (up to chapter {effective_max})")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>BookRAG Knowledge Graph — {safe_book_id}{chapter_label}</title>
    <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
            integrity="sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"
            crossorigin="anonymous"></script>
    <style>
        body {{ margin: 0; font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; }}
        #graph {{ width: 100vw; height: 85vh; }}
        #header {{ padding: 12px 20px; background: #16213e; display: flex; align-items: center; gap: 20px; }}
        #header h1 {{ margin: 0; font-size: 1.3em; }}
        .legend {{ display: flex; gap: 16px; font-size: 0.85em; }}
        .legend-item {{ display: flex; align-items: center; gap: 4px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
        #info {{ padding: 8px 20px; font-size: 0.85em; opacity: 0.7; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>{safe_book_id}{chapter_label}</h1>
        <div class="legend">
            <span class="legend-item"><span class="legend-dot" style="background:#4363d8"></span> Character</span>
            <span class="legend-item"><span class="legend-dot" style="background:#3cb44b"></span> Location</span>
            <span class="legend-item"><span class="legend-dot" style="background:#911eb4"></span> Faction</span>
            <span class="legend-item"><span class="legend-dot" style="background:#e6194b"></span> Theme</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f58231"></span> Event</span>
        </div>
    </div>
    <div id="graph"></div>
    <div id="info">Click a node to see details. Scroll to zoom. Drag to pan.</div>
    <script type="application/json" id="graph-data">{safe_graph_json}</script>
    <script>
        function esc(s) {{ return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }}
        var gd = JSON.parse(document.getElementById('graph-data').textContent);
        var rawNodes = gd.nodes;
        var rawEdges = gd.edges;

        var nodes = new vis.DataSet(rawNodes.map(function(n) {{
            return {{
                id: n.id,
                label: n.label,
                color: {{ background: n.color, border: n.color, highlight: {{ background: '#fff', border: n.color }} }},
                font: {{ color: '#eee', size: 14 }},
                title: '<b>' + esc(n.type) + ':</b> ' + esc(n.label) + (n.description ? '<br>' + esc(n.description) : '') + (n.chapter ? '<br>Ch. ' + n.chapter : ''),
                shape: n.type === 'PlotEvent' ? 'diamond' : 'dot',
                size: n.type === 'Character' ? 20 : 14
            }};
        }}));

        var edges = new vis.DataSet(rawEdges.map(function(e, i) {{
            return {{
                id: i,
                from: e.from,
                to: e.to,
                label: e.label,
                font: {{ color: '#999', size: 10, strokeWidth: 0 }},
                color: {{ color: '#555', highlight: '#aaa' }},
                arrows: 'to'
            }};
        }}));

        var container = document.getElementById('graph');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            physics: {{
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{ gravitationalConstant: -50, centralGravity: 0.01, springLength: 150 }},
                stabilization: {{ iterations: 200 }}
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }},
            layout: {{ improvedLayout: true }}
        }};
        new vis.Network(container, data, options);
    </script>
</body>
</html>"""

    return HTMLResponse(content=html)
