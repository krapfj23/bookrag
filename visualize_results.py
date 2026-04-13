"""Generate an HTML visualization of the coref resolution results.

Produces:
  data/processed/christmas_carol/visualization/report.html

Features:
  - Resolved text with color-coded [annotations]
  - Character legend with mention/resolution counts
  - Per-chapter stats
  - Rule breakdown chart
  - Clickable chapter navigation
"""
from __future__ import annotations

import json
import re
import html as html_mod
from collections import Counter, defaultdict
from pathlib import Path

OUTPUT_BASE = Path("data/processed/christmas_carol_e6ddcd76")

# Assign consistent colors to top characters
COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#dcbeff", "#9A6324", "#800000", "#aaffc3", "#808000",
    "#ffd8b1", "#000075", "#a9a9a9",
]


def load_data():
    clusters = json.loads((OUTPUT_BASE / "coref" / "clusters.json").read_text())
    log = json.loads((OUTPUT_BASE / "coref" / "resolution_log.json").read_text())

    chapters = []
    chapters_dir = OUTPUT_BASE / "resolved" / "chapters"
    for p in sorted(chapters_dir.glob("chapter_*.txt")):
        chapters.append(p.read_text(encoding="utf-8"))

    return clusters, log, chapters


def build_color_map(clusters: dict) -> dict[str, str]:
    """Map canonical names to colors, top characters first."""
    sorted_names = sorted(
        clusters.values(),
        key=lambda c: c["resolution_count"],
        reverse=True,
    )
    color_map = {}
    for i, cl in enumerate(sorted_names):
        name = cl["canonical_name"]
        if name not in color_map:
            color_map[name] = COLORS[i % len(COLORS)]
    return color_map


def colorize_text(text: str, color_map: dict[str, str]) -> str:
    """Replace [Name] annotations with colored HTML spans."""
    escaped = html_mod.escape(text)

    def replace_annotation(m):
        name = html_mod.unescape(m.group(1))
        color = color_map.get(name, "#888")
        return (
            f'<span class="annot" style="background:{color}20;'
            f'border-bottom:2px solid {color};color:{color};'
            f'font-weight:600" title="{html_mod.escape(name)}">'
            f'[{html_mod.escape(name)}]</span>'
        )

    return re.sub(r"\[([^\]]+)\]", replace_annotation, escaped)


def build_html(clusters, log, chapters, color_map) -> str:
    # Stats
    total_insertions = len(log)
    rules = Counter(e["rule_triggered"] for e in log)
    per_chapter = Counter(e["chapter"] for e in log)

    top_clusters = sorted(
        clusters.items(),
        key=lambda x: x[1]["resolution_count"],
        reverse=True,
    )[:20]

    # Build legend
    legend_rows = []
    for cid, cl in top_clusters:
        name = cl["canonical_name"]
        color = color_map.get(name, "#888")
        legend_rows.append(
            f'<tr>'
            f'<td><span style="color:{color};font-weight:700">●</span> {html_mod.escape(name)}</td>'
            f'<td>{cl["mention_count"]}</td>'
            f'<td>{cl["resolution_count"]}</td>'
            f'</tr>'
        )

    # Build chapter sections
    chapter_sections = []
    for i, ch_text in enumerate(chapters):
        count = per_chapter.get(i, 0)
        words = len(ch_text.split())
        colored = colorize_text(ch_text, color_map)
        # Preserve newlines as HTML
        colored = colored.replace("\n\n", "</p><p>").replace("\n", "<br>")

        chapter_sections.append(f"""
        <div class="chapter" id="ch{i+1}">
            <h2>Chapter {i+1}
                <span class="chip">{count} annotations</span>
                <span class="chip">{words:,} words</span>
            </h2>
            <div class="text"><p>{colored}</p></div>
        </div>
        """)

    # Chapter nav
    ch_nav = " ".join(
        f'<a href="#ch{i+1}" class="nav-link">Ch {i+1}</a>'
        for i in range(len(chapters))
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>BookRAG — A Christmas Carol Coref Visualization</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Georgia', serif; background: #fafaf8; color: #222; max-width: 1000px; margin: 0 auto; padding: 20px; }}
    h1 {{ font-size: 1.8em; margin-bottom: 5px; }}
    .subtitle {{ color: #666; margin-bottom: 20px; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }}
    .stat-card {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
    .stat-card .num {{ font-size: 2em; font-weight: 700; color: #4363d8; }}
    .stat-card .label {{ color: #888; font-size: 0.85em; }}
    .legend {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 20px 0; }}
    .legend h3 {{ margin-bottom: 10px; }}
    .legend table {{ width: 100%; border-collapse: collapse; }}
    .legend th, .legend td {{ text-align: left; padding: 4px 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }}
    .legend th {{ color: #888; font-weight: 600; }}
    .nav {{ position: sticky; top: 0; background: #fafaf8; padding: 10px 0; border-bottom: 1px solid #ddd; margin: 20px 0 10px; z-index: 10; }}
    .nav-link {{ display: inline-block; padding: 4px 12px; margin: 2px; border-radius: 4px; background: white; border: 1px solid #ddd; text-decoration: none; color: #333; font-size: 0.85em; }}
    .nav-link:hover {{ background: #4363d8; color: white; }}
    .chapter {{ margin: 30px 0; }}
    .chapter h2 {{ font-size: 1.3em; border-bottom: 2px solid #4363d8; padding-bottom: 6px; margin-bottom: 12px; }}
    .chip {{ display: inline-block; background: #eef; color: #4363d8; font-size: 0.6em; padding: 2px 8px; border-radius: 10px; vertical-align: middle; font-weight: 400; margin-left: 8px; }}
    .text {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); line-height: 1.8; font-size: 0.95em; }}
    .text p {{ margin-bottom: 1em; }}
    .annot {{ padding: 1px 2px; border-radius: 3px; font-size: 0.85em; cursor: help; }}
    .rules {{ display: flex; gap: 20px; margin: 10px 0; }}
    .rule-bar {{ flex: 1; background: white; border-radius: 8px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .rule-bar .bar {{ height: 24px; border-radius: 4px; margin-top: 6px; display: flex; align-items: center; padding-left: 8px; color: white; font-size: 0.8em; font-weight: 600; }}
</style>
</head>
<body>
<h1>A Christmas Carol — Coreference Resolution</h1>
<p class="subtitle">BookRAG Pipeline Phase 1 Output Visualization</p>

<div class="stats">
    <div class="stat-card"><div class="num">{total_insertions:,}</div><div class="label">Total Annotations</div></div>
    <div class="stat-card"><div class="num">{len(clusters)}</div><div class="label">Coref Clusters</div></div>
    <div class="stat-card"><div class="num">{len(chapters)}</div><div class="label">Chapters</div></div>
    <div class="stat-card"><div class="num">{sum(len(c.split()) for c in chapters):,}</div><div class="label">Total Words</div></div>
</div>

<div class="rules">
    <div class="rule-bar">
        <div>Ambiguity: {rules.get('ambiguity', 0):,}</div>
        <div class="bar" style="width:{rules.get('ambiguity',0)/max(total_insertions,1)*100:.0f}%;background:#f58231;">
            {rules.get('ambiguity',0)/max(total_insertions,1)*100:.0f}%
        </div>
    </div>
    <div class="rule-bar">
        <div>Both: {rules.get('both', 0):,}</div>
        <div class="bar" style="width:{rules.get('both',0)/max(total_insertions,1)*100:.0f}%;background:#4363d8;">
            {rules.get('both',0)/max(total_insertions,1)*100:.0f}%
        </div>
    </div>
    <div class="rule-bar">
        <div>Distance: {rules.get('distance', 0):,}</div>
        <div class="bar" style="width:max(3%,{rules.get('distance',0)/max(total_insertions,1)*100:.0f}%);background:#3cb44b;">
            {rules.get('distance',0)/max(total_insertions,1)*100:.0f}%
        </div>
    </div>
</div>

<div class="legend">
    <h3>Top Characters</h3>
    <table>
        <tr><th>Character</th><th>Mentions</th><th>Resolved</th></tr>
        {"".join(legend_rows)}
    </table>
</div>

<div class="nav">{ch_nav}</div>

{"".join(chapter_sections)}

<p style="margin-top:40px;color:#aaa;font-size:0.8em;text-align:center;">
    Generated by BookRAG Pipeline Visualizer
</p>
</body>
</html>"""


def main():
    clusters, log, chapters = load_data()
    color_map = build_color_map(clusters)
    html_content = build_html(clusters, log, chapters, color_map)

    out_dir = OUTPUT_BASE / "visualization"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report.html"
    out_path.write_text(html_content, encoding="utf-8")
    print(f"Visualization saved to {out_path}")
    print(f"Open with: open {out_path}")


if __name__ == "__main__":
    main()
