"""
Interactive CLI for reviewing and editing the discovered ontology before KG construction.

Uses rich for terminal formatting when available, falls back to plain print.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from pipeline.ontology_discovery import BOOK, OntologyResult, _build_owl

# ---------------------------------------------------------------------------
# Rich fallback
# ---------------------------------------------------------------------------

try:
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import Prompt, Confirm

    _HAS_RICH = True
    _console = Console()
except ImportError:
    _HAS_RICH = False
    _console = None


def _print(msg: str = "") -> None:
    if _HAS_RICH:
        _console.print(msg)
    else:
        print(msg)


def _input(prompt: str) -> str:
    if _HAS_RICH:
        return Prompt.ask(prompt)
    return input(prompt + " ").strip()


def _confirm(prompt: str, default: bool = True) -> bool:
    if _HAS_RICH:
        return Confirm.ask(prompt, default=default)
    answer = input(f"{prompt} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_entities(entities: dict[str, list[dict]]) -> None:
    """Show discovered entity types and their top instances."""
    _print("\n[bold underline]Discovered Entity Types[/bold underline]" if _HAS_RICH else "\n=== Discovered Entity Types ===")

    if _HAS_RICH:
        table = Table(title="Entities")
        table.add_column("Type", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_column("Top Instances", style="white")
        for etype, items in entities.items():
            top = ", ".join(f"{it['name']} ({it['count']})" for it in items[:5])
            table.add_row(etype, str(len(items)), top)
        _console.print(table)
    else:
        for etype, items in entities.items():
            top = ", ".join(f"{it['name']} ({it['count']})" for it in items[:5])
            print(f"  {etype} ({len(items)} instances): {top}")


def _display_themes(themes: list[dict]) -> None:
    """Show discovered BERTopic themes."""
    _print("\n[bold underline]Discovered Themes[/bold underline]" if _HAS_RICH else "\n=== Discovered Themes ===")

    if not themes:
        _print("  (none discovered — book may be too short for BERTopic)")
        return

    if _HAS_RICH:
        table = Table(title="Themes")
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Label", style="green")
        table.add_column("Keywords", style="white")
        for t in themes:
            table.add_row(str(t["topic_id"]), t["label"], ", ".join(t["keywords"][:6]))
        _console.print(table)
    else:
        for t in themes:
            kw = ", ".join(t["keywords"][:6])
            print(f"  Topic {t['topic_id']}: {t['label']}  ({kw})")


def _display_relations(relations: list[dict]) -> None:
    """Show discovered relationship types."""
    _print("\n[bold underline]Discovered Relationship Types[/bold underline]" if _HAS_RICH else "\n=== Discovered Relationship Types ===")

    if _HAS_RICH:
        table = Table(title="Relations")
        table.add_column("Name", style="cyan")
        table.add_column("Source", style="green")
        table.add_column("Evidence", style="white")
        for r in relations[:30]:  # cap display at 30
            table.add_row(r["name"], r["source"], r.get("evidence", ""))
        _console.print(table)
    else:
        for r in relations[:30]:
            print(f"  {r['name']:25s} [{r['source']}] {r.get('evidence', '')}")

    if len(relations) > 30:
        _print(f"  ... and {len(relations) - 30} more")


# ---------------------------------------------------------------------------
# Edit operations
# ---------------------------------------------------------------------------

def _edit_entity_types(entities: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Interactive loop for editing entity types."""
    while True:
        _print("\n[bold]Entity type actions:[/bold]" if _HAS_RICH else "\nEntity type actions:")
        _print("  [a]dd a type  |  [r]emove a type  |  [n]ame a type  |  [d]one")
        action = _input("Action").lower()

        if action in ("d", "done", ""):
            break
        elif action in ("a", "add"):
            name = _input("New entity type name")
            if name and name not in entities:
                entities[name] = []
                _print(f"  Added type: {name}")
            elif name in entities:
                _print(f"  Type '{name}' already exists")
        elif action in ("r", "remove"):
            name = _input(f"Type to remove ({', '.join(entities.keys())})")
            if name in entities:
                del entities[name]
                _print(f"  Removed type: {name}")
            else:
                _print(f"  Type '{name}' not found")
        elif action in ("n", "rename"):
            old = _input(f"Type to rename ({', '.join(entities.keys())})")
            if old in entities:
                new = _input("New name")
                if new and new not in entities:
                    entities[new] = entities.pop(old)
                    _print(f"  Renamed: {old} -> {new}")
                else:
                    _print("  Invalid new name or already exists")
            else:
                _print(f"  Type '{old}' not found")

    return entities


def _edit_themes(themes: list[dict]) -> list[dict]:
    """Interactive loop for editing themes."""
    while True:
        _print("\n[bold]Theme actions:[/bold]" if _HAS_RICH else "\nTheme actions:")
        _print("  [r]emove a theme  |  [d]one")
        action = _input("Action").lower()

        if action in ("d", "done", ""):
            break
        elif action in ("r", "remove"):
            if not themes:
                _print("  No themes to remove")
                continue
            valid_ids = [str(t["topic_id"]) for t in themes]
            idx_str = _input(f"Topic ID to remove ({', '.join(valid_ids)})")
            try:
                idx = int(idx_str)
                before = len(themes)
                themes = [t for t in themes if t["topic_id"] != idx]
                if len(themes) < before:
                    _print(f"  Removed topic {idx}")
                else:
                    _print(f"  Topic {idx} not found")
            except ValueError:
                _print("  Invalid topic ID")

    return themes


def _edit_relations(relations: list[dict]) -> list[dict]:
    """Interactive loop for editing relationship types."""
    while True:
        _print("\n[bold]Relation actions:[/bold]" if _HAS_RICH else "\nRelation actions:")
        _print("  [a]dd  |  [r]emove  |  [d]one")
        action = _input("Action").lower()

        if action in ("d", "done", ""):
            break
        elif action in ("a", "add"):
            name = _input("New relation name (snake_case)")
            if name:
                relations.append({
                    "name": name,
                    "source": "manual_review",
                    "evidence": "added during ontology review",
                })
                _print(f"  Added relation: {name}")
        elif action in ("r", "remove"):
            name = _input("Relation name to remove")
            before = len(relations)
            relations = [r for r in relations if r["name"] != name]
            if len(relations) < before:
                _print(f"  Removed relation: {name}")
            else:
                _print(f"  Relation '{name}' not found")

    return relations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def review_ontology(
    ontology_result: OntologyResult,
    book_id: str,
    auto_review: bool = False,
    min_entity_frequency: int = 2,
) -> OntologyResult:
    """
    Interactive CLI review of the discovered ontology.

    If auto_review is True, accepts all discoveries without prompting.
    min_entity_frequency should match the value used during discovery
    so the OWL rebuild is consistent.
    Returns the (possibly modified) OntologyResult.
    """
    output_dir = Path(f"data/processed/{book_id}/ontology")
    output_dir.mkdir(parents=True, exist_ok=True)

    entities = ontology_result.discovered_entities
    themes = ontology_result.discovered_themes
    relations = ontology_result.discovered_relations

    if auto_review:
        logger.info("Auto-review enabled — accepting all discovered ontology elements")
        snapshot = {
            "book_id": book_id,
            "review_mode": "auto",
            "changes": [],
            "entities": entities,
            "themes": themes,
            "relations": [r["name"] for r in relations],
        }
        (output_dir / "review_snapshot.json").write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False)
        )
        return ontology_result

    # --- Interactive review ---
    _print("\n" + "=" * 60)
    _print("[bold]Ontology Review[/bold]" if _HAS_RICH else "ONTOLOGY REVIEW")
    _print("=" * 60)

    _display_entities(entities)
    _display_themes(themes)
    _display_relations(relations)

    _print("")
    if _confirm("Accept all without changes?", default=True):
        logger.info("User accepted ontology without changes")
    else:
        # Edit entities
        if _confirm("Edit entity types?", default=False):
            entities = _edit_entity_types(entities)

        # Edit themes
        if themes and _confirm("Edit themes?", default=False):
            themes = _edit_themes(themes)

        # Edit relations
        if _confirm("Edit relationship types?", default=False):
            relations = _edit_relations(relations)

        # Rebuild OWL with changes
        logger.info("Rebuilding OWL ontology with review changes...")
        owl_path = output_dir / "book_ontology.owl"
        _build_owl(entities, themes, relations, owl_path, min_entity_frequency)

    # Save review snapshot
    snapshot = {
        "book_id": book_id,
        "review_mode": "interactive",
        "entities": entities,
        "themes": themes,
        "relations": [r["name"] for r in relations],
    }
    snapshot_path = output_dir / "review_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    logger.info("Review snapshot saved to {}", snapshot_path)

    return OntologyResult(
        discovered_entities=entities,
        discovered_themes=themes,
        discovered_relations=relations,
        owl_path=ontology_result.owl_path,
    )
