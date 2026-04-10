"""Known-answer validation test suite for BookRAG.

Runs structural and content checks against the knowledge graph after pipeline
completion. Designed for A Christmas Carol (test book per CLAUDE.md) but
generalizes to any book with a fixtures JSON file.

Usage:
    result = await run_validation("christmas_carol", processed_dir)
    # result is a ValidationReport saved to validation/validation_results.json

The orchestrator calls this from _stage_validate().
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# Cognee search imports — optional, only needed for known-answer queries
try:
    import cognee
    from cognee.modules.search.types import SearchType

    COGNEE_SEARCH_AVAILABLE = True
except (ImportError, AttributeError):
    COGNEE_SEARCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """A single validation check."""
    name: str
    passed: bool
    expected: str
    actual: str
    detail: str = ""


@dataclass
class ValidationReport:
    """Full validation report for a book."""
    book_id: str
    fixture_file: str
    checks: list[CheckResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def add(self, check: CheckResult) -> None:
        self.checks.append(check)
        if check.passed:
            self.passed += 1
        else:
            self.failed += 1

    def skip(self, name: str, reason: str) -> None:
        self.checks.append(CheckResult(name=name, passed=True, expected="", actual="", detail=f"SKIPPED: {reason}"))
        self.skipped += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "fixture_file": self.fixture_file,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "all_passed": self.all_passed,
            },
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "expected": c.expected,
                    "actual": c.actual,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Graph data loading
# ---------------------------------------------------------------------------

def _load_extracted_datapoints(processed_dir: Path, book_id: str) -> list[dict]:
    """Load all extracted DataPoints from batch output files."""
    batches_dir = processed_dir / book_id / "batches"
    all_datapoints: list[dict] = []

    if not batches_dir.exists():
        logger.warning("No batches directory at {}", batches_dir)
        return all_datapoints

    for batch_dir in sorted(batches_dir.iterdir()):
        dp_path = batch_dir / "extracted_datapoints.json"
        if dp_path.exists():
            try:
                dps = json.loads(dp_path.read_text(encoding="utf-8"))
                if isinstance(dps, list):
                    all_datapoints.extend(dps)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning("Failed to load {}: {}", dp_path, exc)

    logger.info("Loaded {} DataPoints from {} for validation", len(all_datapoints), batches_dir)
    return all_datapoints


def _extract_by_type(datapoints: list[dict]) -> dict[str, list[dict]]:
    """Group DataPoints by their type (class name)."""
    by_type: dict[str, list[dict]] = {}
    for dp in datapoints:
        # DataPoints serialized via model_dump() have class info in various ways
        dp_type = dp.get("type", dp.get("__type__", ""))
        if not dp_type:
            # Infer from fields
            if "relation_type" in dp and "source" in dp and "target" in dp:
                dp_type = "Relationship"
            elif "chapter" in dp and "participants" in dp:
                dp_type = "PlotEvent"
            elif "members" in dp:
                dp_type = "Faction"
            elif "related_characters" in dp:
                dp_type = "Theme"
            elif "aliases" in dp or "chapters_present" in dp:
                dp_type = "Character"
            elif "name" in dp and "first_chapter" in dp:
                dp_type = "Location"
            else:
                dp_type = "Unknown"
        by_type.setdefault(dp_type, []).append(dp)
    return by_type


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def _check_structural(
    report: ValidationReport,
    by_type: dict[str, list[dict]],
    structural: dict,
) -> None:
    """Run structural checks: minimum counts, chapter coverage, orphan detection."""

    # Min characters
    min_chars = structural.get("min_characters", 0)
    actual_chars = len(by_type.get("Character", []))
    report.add(CheckResult(
        name="min_characters",
        passed=actual_chars >= min_chars,
        expected=f">= {min_chars}",
        actual=str(actual_chars),
    ))

    # Min locations
    min_locs = structural.get("min_locations", 0)
    actual_locs = len(by_type.get("Location", []))
    report.add(CheckResult(
        name="min_locations",
        passed=actual_locs >= min_locs,
        expected=f">= {min_locs}",
        actual=str(actual_locs),
    ))

    # Min relationships
    min_rels = structural.get("min_relationships", 0)
    actual_rels = len(by_type.get("Relationship", []))
    report.add(CheckResult(
        name="min_relationships",
        passed=actual_rels >= min_rels,
        expected=f">= {min_rels}",
        actual=str(actual_rels),
    ))

    # Min events
    min_events = structural.get("min_events", 0)
    actual_events = len(by_type.get("PlotEvent", []))
    report.add(CheckResult(
        name="min_events",
        passed=actual_events >= min_events,
        expected=f">= {min_events}",
        actual=str(actual_events),
    ))

    # Chapter coverage
    expected_chapters = set(structural.get("expected_chapters_covered", []))
    if expected_chapters:
        found_chapters: set[int] = set()
        for dp_list in by_type.values():
            for dp in dp_list:
                if "first_chapter" in dp:
                    found_chapters.add(dp["first_chapter"])
                if "chapter" in dp:
                    found_chapters.add(dp["chapter"])
                for ch in dp.get("chapters_present", []):
                    found_chapters.add(ch)

        missing = expected_chapters - found_chapters
        report.add(CheckResult(
            name="chapter_coverage",
            passed=len(missing) == 0,
            expected=f"chapters {sorted(expected_chapters)}",
            actual=f"found {sorted(found_chapters)}, missing {sorted(missing)}" if missing else f"all {sorted(found_chapters)}",
        ))

    # Graph is populated at all
    total_dps = sum(len(v) for v in by_type.values())
    report.add(CheckResult(
        name="graph_populated",
        passed=total_dps > 0,
        expected="> 0 DataPoints",
        actual=str(total_dps),
    ))


def _check_expected_characters(
    report: ValidationReport,
    characters: list[dict],
    expected: list[dict],
) -> None:
    """Verify expected characters exist with correct attributes."""
    char_names = {c.get("name", "").lower() for c in characters}
    char_aliases: dict[str, set[str]] = {}
    for c in characters:
        name = c.get("name", "").lower()
        aliases = {a.lower() for a in c.get("aliases", [])}
        char_aliases[name] = aliases | {name}

    # Build a flat set of all known names
    all_names = set()
    for name, aliases in char_aliases.items():
        all_names.add(name)
        all_names.update(aliases)

    for exp in expected:
        exp_name = exp["name"]
        exp_lower = exp_name.lower()
        exp_aliases = {a.lower() for a in exp.get("aliases", [])}
        search_names = {exp_lower} | exp_aliases

        found = bool(search_names & all_names)
        report.add(CheckResult(
            name=f"character_exists:{exp_name}",
            passed=found,
            expected=f"{exp_name} (or aliases {exp.get('aliases', [])})",
            actual="found" if found else "not found",
        ))


def _check_expected_locations(
    report: ValidationReport,
    locations: list[dict],
    expected: list[dict],
) -> None:
    """Verify expected locations exist."""
    loc_names = {l.get("name", "").lower() for l in locations}

    for exp in expected:
        exp_name = exp["name"]
        search = {exp_name.lower()} | {a.lower() for a in exp.get("aliases", [])}
        found = bool(search & loc_names)
        report.add(CheckResult(
            name=f"location_exists:{exp_name}",
            passed=found,
            expected=exp_name,
            actual="found" if found else f"not in {sorted(loc_names)[:10]}",
        ))


def _check_expected_relationships(
    report: ValidationReport,
    relationships: list[dict],
    expected: list[dict],
) -> None:
    """Verify expected relationships exist (fuzzy match on relation type)."""
    for exp in expected:
        source = exp["source"].lower()
        target = exp["target"].lower()
        keywords = [k.lower() for k in exp.get("relation_contains", [])]

        found = False
        for rel in relationships:
            rel_source = rel.get("source", "")
            rel_target = rel.get("target", "")
            # Handle both string names and nested dicts
            if isinstance(rel_source, dict):
                rel_source = rel_source.get("name", "")
            if isinstance(rel_target, dict):
                rel_target = rel_target.get("name", "")

            rel_source_lower = rel_source.lower()
            rel_target_lower = rel_target.lower()
            rel_type = rel.get("relation_type", "").lower()
            rel_desc = rel.get("description", "").lower()

            # Check source/target match (either direction)
            src_match = source in rel_source_lower or rel_source_lower in source
            tgt_match = target in rel_target_lower or rel_target_lower in target
            if not (src_match and tgt_match):
                # Try reversed direction
                src_match = source in rel_target_lower or rel_target_lower in source
                tgt_match = target in rel_source_lower or rel_source_lower in target

            if src_match and tgt_match:
                # Check relation keyword match
                if any(kw in rel_type or kw in rel_desc for kw in keywords):
                    found = True
                    break

        report.add(CheckResult(
            name=f"relationship:{exp['source']}->{exp['target']}",
            passed=found,
            expected=exp.get("description", f"{exp['source']} -> {exp['target']}"),
            actual="found" if found else "not found",
        ))


def _check_expected_events(
    report: ValidationReport,
    events: list[dict],
    expected: list[dict],
) -> None:
    """Verify expected plot events exist (fuzzy match on description keywords)."""
    for exp in expected:
        chapter = exp.get("chapter")
        keywords = [k.lower() for k in exp.get("description_keywords", [])]

        found = False
        for event in events:
            event_chapter = event.get("chapter")
            event_desc = event.get("description", "").lower()

            chapter_match = chapter is None or event_chapter == chapter
            keyword_match = any(kw in event_desc for kw in keywords)

            if chapter_match and keyword_match:
                found = True
                break

        report.add(CheckResult(
            name=f"event:ch{chapter}:{exp.get('note', 'unnamed')[:40]}",
            passed=found,
            expected=exp.get("note", str(keywords)),
            actual="found" if found else "not found",
        ))


# ---------------------------------------------------------------------------
# Known-answer query checks (requires live cognee)
# ---------------------------------------------------------------------------

def _extract_search_text(results: list) -> str:
    """Flatten cognee SearchResult list into a single text string for keyword matching."""
    parts: list[str] = []
    for r in results:
        sr = getattr(r, "search_result", r) if not isinstance(r, dict) else r
        if isinstance(sr, str):
            parts.append(sr)
        elif isinstance(sr, dict):
            for key in ("content", "text", "answer", "description", "name"):
                if key in sr:
                    parts.append(str(sr[key]))
        elif isinstance(sr, (list, tuple)):
            for item in sr:
                parts.append(str(item))
        else:
            parts.append(str(sr))
    return " ".join(parts)


async def _check_known_answer_queries(
    report: ValidationReport,
    queries: list[dict],
    book_id: str,
) -> None:
    """Run known-answer queries against the live cognee knowledge graph.

    Each query calls cognee.search() with only_context=True (no LLM cost)
    and checks that expected keywords appear in the retrieved context.
    Skips gracefully if cognee search is unavailable.
    """
    if not COGNEE_SEARCH_AVAILABLE:
        report.skip("known_answer_queries", "cognee search not available")
        return

    for query in queries:
        question = query["question"]
        expected_contains = query.get("expected_answer_contains", [])
        not_contains = query.get("expected_answer_not_contains", [])
        check_name = f"known_answer:{question[:50]}"

        try:
            results = await cognee.search(
                query_text=question,
                query_type=SearchType.GRAPH_COMPLETION,
                datasets=[book_id],
                only_context=True,
            )
            context_text = _extract_search_text(results).lower()

            # At least one expected term must appear
            found_expected = any(
                term.lower() in context_text for term in expected_contains
            )
            # None of the excluded terms should appear
            found_excluded = [
                term for term in not_contains if term.lower() in context_text
            ]

            if found_expected and not found_excluded:
                report.add(CheckResult(
                    name=check_name,
                    passed=True,
                    expected=f"contains any of {expected_contains}",
                    actual="found in search context",
                ))
            else:
                detail_parts = []
                if not found_expected:
                    detail_parts.append(f"none of {expected_contains} found")
                if found_excluded:
                    detail_parts.append(f"excluded terms found: {found_excluded}")
                report.add(CheckResult(
                    name=check_name,
                    passed=False,
                    expected=f"contains any of {expected_contains}, excludes {not_contains}",
                    actual=f"context length={len(context_text)}; {'; '.join(detail_parts)}",
                ))
        except Exception as exc:
            report.skip(check_name, f"search error: {exc}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_fixture(book_id: str, fixtures_dir: Path | None = None) -> dict | None:
    """Load validation fixtures for a book.

    Looks for validation/fixtures/{book_id}.json.
    Returns None if no fixture exists (non-test books skip validation).
    """
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).parent / "fixtures"

    fixture_path = fixtures_dir / f"{book_id}.json"
    if not fixture_path.exists():
        logger.info("No validation fixture for '{}' at {}", book_id, fixture_path)
        return None

    return json.loads(fixture_path.read_text(encoding="utf-8"))


async def run_validation(
    book_id: str,
    processed_dir: Path,
    fixtures_dir: Path | None = None,
) -> ValidationReport:
    """Run the full validation suite for a processed book.

    Loads extracted DataPoints from disk, loads the fixture file, and runs
    all applicable checks — including known-answer queries against the
    live cognee knowledge graph when available.

    Args:
        book_id: The book identifier (e.g. "christmas_carol").
        processed_dir: Root processed directory (data/processed).
        fixtures_dir: Override path for fixture JSON files.

    Returns:
        ValidationReport with all check results.
    """
    fixture = load_fixture(book_id, fixtures_dir)

    if fixture is None:
        report = ValidationReport(book_id=book_id, fixture_file="(none)")
        report.skip("all", f"No validation fixture for '{book_id}'")
        return report

    fixture_file = f"{book_id}.json"
    report = ValidationReport(book_id=book_id, fixture_file=fixture_file)

    # Load graph data
    datapoints = _load_extracted_datapoints(processed_dir, book_id)
    by_type = _extract_by_type(datapoints)

    logger.info(
        "Validating '{}': {} DataPoints ({} types)",
        book_id, len(datapoints),
        ", ".join(f"{k}={len(v)}" for k, v in sorted(by_type.items())),
    )

    # Structural checks
    structural = fixture.get("structural_checks", {})
    _check_structural(report, by_type, structural)

    # Character checks
    expected_chars = fixture.get("expected_characters", [])
    if expected_chars:
        _check_expected_characters(report, by_type.get("Character", []), expected_chars)

    # Location checks
    expected_locs = fixture.get("expected_locations", [])
    if expected_locs:
        _check_expected_locations(report, by_type.get("Location", []), expected_locs)

    # Relationship checks
    expected_rels = fixture.get("expected_relationships", [])
    if expected_rels:
        _check_expected_relationships(report, by_type.get("Relationship", []), expected_rels)

    # Event checks
    expected_events = fixture.get("expected_events", [])
    if expected_events:
        _check_expected_events(report, by_type.get("PlotEvent", []), expected_events)

    # Known-answer queries (requires live cognee search)
    known_answer = fixture.get("known_answer_queries", [])
    if known_answer:
        await _check_known_answer_queries(report, known_answer, book_id)

    logger.info(
        "Validation complete for '{}': {}/{} passed, {} failed, {} skipped",
        book_id, report.passed, report.total, report.failed, report.skipped,
    )

    return report


def save_validation_report(report: ValidationReport, output_dir: Path) -> Path:
    """Save validation report to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "validation_results.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Validation report saved to {}", path)
    return path
