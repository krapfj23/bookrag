#!/usr/bin/env python3
"""GraphRAG evaluation runner for BookRAG.

Runs a fixture of questions against a live /query endpoint and reports:
  - answer_similarity   cosine similarity of OpenAI embedding(answer) vs
                        embedding(expected_answer_gist). Soft signal.
  - source_chapter_precision   fraction of returned source chapters that
                        fall inside expected_source_chapters.
  - entity_recall       fraction of expected_entities found (case-insensitive)
                        anywhere in answer or any source content.
  - spoiler_safety      1.0 iff every source chapter <= max_chapter, else 0.0.
  - latency_ms          wall-clock ms per /query POST.

Modes:
  - baseline   BOOKRAG_USE_TRIPLETS unset (or "0")
  - triplets   BOOKRAG_USE_TRIPLETS=1

The backend environment must already be set the way you want it. This
script does NOT restart the server; it ONLY posts to /query. To A/B,
restart the backend between runs with the env var flipped.

Usage:
    python scripts/eval_query.py \\
        --fixture evaluations/christmas_carol_questions.json \\
        --backend http://localhost:8000 \\
        --mode baseline \\
        --out evaluations/results/2026-04-22-baseline.md
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import request as urlreq
from urllib.error import URLError

# Pick up OPENAI_API_KEY from .env if python-dotenv is available so
# the eval can score answer_similarity without the caller setting env manually.
try:
    from dotenv import load_dotenv
    _repo_root = Path(__file__).resolve().parent.parent
    load_dotenv(_repo_root / ".env")
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Embedding helper — used for answer_similarity. Optional; if OPENAI_API_KEY
# isn't set or the lib is missing we emit NaN for that metric.
# ---------------------------------------------------------------------------

def _embed_texts(texts: list[str]) -> list[list[float]] | None:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    client = OpenAI(api_key=api_key)
    try:
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
    except Exception as exc:
        print(f"[warn] embedding call failed: {exc}", file=sys.stderr)
        return None
    return [d.embedding for d in resp.data]


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    status_code: int
    body: dict[str, Any]
    latency_ms: float


def post_query(backend: str, book_id: str, question: str, max_chapter: int) -> QueryResult:
    url = f"{backend.rstrip('/')}/books/{book_id}/query"
    payload = {
        "question": question,
        "search_type": "GRAPH_COMPLETION",
        "max_chapter": max_chapter,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlreq.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urlreq.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            latency_ms = (time.perf_counter() - start) * 1000
            return QueryResult(
                status_code=resp.status,
                body=json.loads(raw.decode("utf-8")),
                latency_ms=latency_ms,
            )
    except URLError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return QueryResult(
            status_code=0,
            body={"error": str(exc)},
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class QuestionMetrics:
    id: str
    question: str
    answer_similarity: float | None
    source_chapter_precision: float
    entity_recall: float
    spoiler_safety: float
    latency_ms: float
    answer: str = ""
    sources_preview: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def evaluate_one(
    q: dict[str, Any],
    resp_body: dict[str, Any],
    latency_ms: float,
    embeddings: dict[str, list[float]] | None,
) -> QuestionMetrics:
    answer: str = resp_body.get("answer") or ""
    results: list[dict[str, Any]] = resp_body.get("results") or []
    max_chapter: int = q["max_chapter"]
    expected_chapters = set(q.get("expected_source_chapters") or [])
    expected_entities = [e.lower() for e in q.get("expected_entities") or []]

    # source_chapter_precision
    src_chapters = [r.get("chapter") for r in results if r.get("chapter") is not None]
    if src_chapters:
        hits = sum(1 for c in src_chapters if c in expected_chapters)
        precision = hits / len(src_chapters)
    else:
        precision = 0.0

    # entity_recall (soft, case-insensitive substring search over answer+sources)
    haystack = answer.lower() + "\n" + "\n".join(
        (r.get("content") or "").lower() for r in results
    )
    if expected_entities:
        recalled = sum(1 for e in expected_entities if e in haystack)
        entity_recall = recalled / len(expected_entities)
    else:
        entity_recall = 1.0

    # spoiler_safety: HARD rule
    spoiler_leaks = [
        r for r in results
        if r.get("chapter") is not None and r["chapter"] > max_chapter
    ]
    spoiler_safety = 0.0 if spoiler_leaks else 1.0

    # answer_similarity (cosine on OpenAI embedding vs expected_answer_gist)
    sim: float | None = None
    if embeddings and q["id"] in embeddings and "gist:" + q["id"] in embeddings:
        sim = _cosine(embeddings[q["id"]], embeddings["gist:" + q["id"]])

    notes: list[str] = []
    if spoiler_leaks:
        notes.append(
            f"SPOILER LEAK: {len(spoiler_leaks)} source(s) past ch.{max_chapter}: "
            + ", ".join(
                f"ch.{r['chapter']} [{(r.get('content') or '')[:40]}...]"
                for r in spoiler_leaks[:3]
            )
        )

    return QuestionMetrics(
        id=q["id"],
        question=q["question"],
        answer_similarity=sim,
        source_chapter_precision=precision,
        entity_recall=entity_recall,
        spoiler_safety=spoiler_safety,
        latency_ms=latency_ms,
        answer=answer,
        sources_preview=[(r.get("content") or "")[:80] for r in results[:3]],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_markdown(
    out_path: Path,
    metrics: list[QuestionMetrics],
    mode: str,
    backend: str,
    book_id: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Aggregates
    sims = [m.answer_similarity for m in metrics if m.answer_similarity is not None]
    precisions = [m.source_chapter_precision for m in metrics]
    recalls = [m.entity_recall for m in metrics]
    safeties = [m.spoiler_safety for m in metrics]
    latencies = [m.latency_ms for m in metrics]

    def _mean(xs): return statistics.fmean(xs) if xs else float("nan")
    def _median(xs): return statistics.median(xs) if xs else float("nan")

    spoiler_leak_count = sum(1 for s in safeties if s < 1.0)

    lines = [
        f"# GraphRAG eval — {mode}",
        "",
        f"- **Backend:** `{backend}`",
        f"- **Book:** `{book_id}`",
        f"- **Mode:** `{mode}` (BOOKRAG_USE_TRIPLETS "
        f"{'=1' if mode == 'triplets' else 'unset'})",
        f"- **Questions:** {len(metrics)}",
        "",
        "## Aggregates",
        "",
        "| Metric | Mean | Median |",
        "|---|---|---|",
        f"| answer_similarity | {_mean(sims):.3f} | {_median(sims):.3f} |",
        f"| source_chapter_precision | {_mean(precisions):.3f} | {_median(precisions):.3f} |",
        f"| entity_recall | {_mean(recalls):.3f} | {_median(recalls):.3f} |",
        f"| spoiler_safety | {_mean(safeties):.3f} | {_median(safeties):.3f} |",
        f"| latency_ms | {_mean(latencies):.0f} | {_median(latencies):.0f} |",
        "",
        f"**Spoiler leaks:** {spoiler_leak_count} / {len(metrics)}",
        "",
        "## Per-question",
        "",
        "| id | similarity | prec | recall | safe | ms |",
        "|---|---|---|---|---|---|",
    ]
    for m in metrics:
        sim_str = f"{m.answer_similarity:.3f}" if m.answer_similarity is not None else "—"
        lines.append(
            f"| {m.id} | {sim_str} | {m.source_chapter_precision:.2f} | "
            f"{m.entity_recall:.2f} | {m.spoiler_safety:.1f} | {m.latency_ms:.0f} |"
        )

    lines.append("")
    lines.append("## Details")
    for m in metrics:
        lines.append("")
        lines.append(f"### {m.id} — {m.question}")
        lines.append("")
        lines.append(f"**Answer:** {m.answer}")
        lines.append("")
        if m.sources_preview:
            lines.append("**Top sources:**")
            for s in m.sources_preview:
                lines.append(f"- {s}")
        if m.notes:
            lines.append("")
            lines.append("**Flags:**")
            for n in m.notes:
                lines.append(f"- {n}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--mode", choices=["baseline", "triplets"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip the OpenAI embedding call for answer_similarity (faster, free).",
    )
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    book_id = fixture["book_id"]
    questions: list[dict[str, Any]] = fixture["questions"]

    print(f"Running {len(questions)} questions against {args.backend} ({args.mode} mode)")

    responses: list[tuple[dict[str, Any], QueryResult]] = []
    for q in questions:
        print(f"  [{q['id']}] {q['question'][:70]}...", end=" ", flush=True)
        result = post_query(args.backend, book_id, q["question"], q["max_chapter"])
        print(f"{result.latency_ms:.0f}ms")
        responses.append((q, result))

    # Batch embed answers + gists in one call for speed + cost
    embeddings: dict[str, list[float]] | None = None
    if not args.skip_embeddings:
        to_embed: list[str] = []
        ids: list[str] = []
        for q, r in responses:
            if r.status_code == 200:
                ans = r.body.get("answer") or ""
                gist = q.get("expected_answer_gist") or ""
                if ans.strip() and gist.strip():
                    to_embed.append(ans)
                    ids.append(q["id"])
                    to_embed.append(gist)
                    ids.append("gist:" + q["id"])
        if to_embed:
            vecs = _embed_texts(to_embed)
            if vecs:
                embeddings = dict(zip(ids, vecs))
                print(f"Embedded {len(to_embed)} texts.")
            else:
                print("[warn] embeddings unavailable; answer_similarity will be —")

    metrics: list[QuestionMetrics] = []
    for q, r in responses:
        if r.status_code != 200:
            metrics.append(QuestionMetrics(
                id=q["id"],
                question=q["question"],
                answer_similarity=None,
                source_chapter_precision=0.0,
                entity_recall=0.0,
                spoiler_safety=0.0,
                latency_ms=r.latency_ms,
                notes=[f"HTTP {r.status_code}: {r.body}"],
            ))
            continue
        metrics.append(evaluate_one(q, r.body, r.latency_ms, embeddings))

    write_markdown(args.out, metrics, args.mode, args.backend, book_id)
    print(f"Wrote {args.out}")

    leaks = sum(1 for m in metrics if m.spoiler_safety < 1.0)
    if leaks:
        print(f"[FAIL] {leaks} spoiler leaks", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
