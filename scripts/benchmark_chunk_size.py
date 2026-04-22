"""Chunk-size ablation sweep — Phase A Stage 3.

Sweeps ``chunk_size`` across a list of candidate values, re-extracts Phase 2
(``extract_enriched_graph``) for a book whose Phase-1 artifacts are already on
disk, and emits per-run scores to
``data/benchmarks/chunk_size_YYYY-MM-DD/run.jsonl`` for comparison.

Designed to run AFTER all other Phase A improvements are in place (strict
provenance, gleaning, valence, etc.), so the baseline being ablated is the
final pipeline — not a moving target.

Usage::

    # typical — sweep default grid on Christmas Carol, use existing gold set
    python -m scripts.benchmark_chunk_size --book-id christmas_carol

    # custom grid + custom gold path
    python -m scripts.benchmark_chunk_size \\
        --book-id red_rising \\
        --sizes 1500 1000 750 500 \\
        --gold tests/golds/red_rising_gold.json

    # dry-run prints the plan without running the pipeline
    python -m scripts.benchmark_chunk_size --book-id christmas_carol --dry-run

Prerequisites for a non-dry run:
- Phase-1 artifacts already exist under ``data/processed/{book_id}/``:
  ``booknlp/``, ``coref/``, ``ontology/``.
- OPENAI_API_KEY (or equivalent) set so extraction can call the LLM.
- Gold JSON for the book at ``tests/golds/{book_id}_gold.json`` (default) or
  ``--gold`` override.

Each run writes its extracted DataPoints to
``data/benchmarks/chunk_size_YYYY-MM-DD/size_{N}/extracted_datapoints.json``
and appends a one-line JSON summary to ``run.jsonl``. A final line in
``run.jsonl`` records the winner (or "no-winner" when no size meets the
acceptance constraints).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from loguru import logger

from pipeline.benchmark_eval import (
    load_gold,
    pick_winner,
    summarize_run,
)


DEFAULT_SIZES = [1500, 1000, 750, 500]
DEFAULT_MODEL_COST_PER_1K_INPUT = 0.00015   # gpt-4o-mini input, USD
DEFAULT_MODEL_COST_PER_1K_OUTPUT = 0.0006   # gpt-4o-mini output, USD


async def _extract_for_size(
    *,
    book_id: str,
    chunk_size: int,
    processed_dir: Path,
    output_dir: Path,
    max_gleanings: int,
) -> tuple[list[dict], dict]:
    """Re-run Phase 2 extraction at ``chunk_size`` using existing Phase-1
    artifacts. Returns (serialized datapoints, run_metrics).

    Imported here (not at module top) so --dry-run doesn't need BookNLP/
    Cognee to load.
    """
    from pipeline.batcher import FixedSizeBatcher
    from pipeline.cognee_pipeline import run_bookrag_pipeline, configure_cognee
    from models.config import load_config

    config = load_config()
    configure_cognee(config)

    chapters_dir = processed_dir / book_id / "resolved"
    if not chapters_dir.exists():
        chapters_dir = processed_dir / book_id / "raw" / "chapters"
    if not chapters_dir.exists():
        raise FileNotFoundError(
            f"No resolved/ or raw/chapters/ under {processed_dir / book_id} "
            f"— run Phase 1 before benchmarking."
        )

    chapter_files = sorted(chapters_dir.glob("chapter_*.txt"))
    if not chapter_files:
        raise FileNotFoundError(f"No chapter_*.txt under {chapters_dir}")

    chapter_texts: list[str] = []
    chapter_numbers: list[int] = []
    for f in chapter_files:
        try:
            num = int(f.stem.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        chapter_texts.append(f.read_text(encoding="utf-8"))
        chapter_numbers.append(num)

    booknlp_output_path = processed_dir / book_id / "booknlp" / "booknlp_output.json"
    ontology_path = processed_dir / book_id / "ontology" / "ontology.json"

    booknlp_output = (
        json.loads(booknlp_output_path.read_text(encoding="utf-8"))
        if booknlp_output_path.exists() else {}
    )
    ontology = (
        json.loads(ontology_path.read_text(encoding="utf-8"))
        if ontology_path.exists() else {}
    )

    batcher = FixedSizeBatcher(batch_size=config.batch_size)
    batches = batcher.make_batches(
        chapter_texts=chapter_texts,
        chapter_numbers=chapter_numbers,
    )

    size_dir = output_dir / f"size_{chunk_size}"
    size_dir.mkdir(parents=True, exist_ok=True)

    chunk_ordinal_counter = 0
    all_datapoints_path = size_dir / "extracted_datapoints.json"
    aggregated: list[dict] = []
    started = time.time()
    for batch in batches:
        chunk_ordinal_counter = await run_bookrag_pipeline(
            batch=batch,
            booknlp_output=booknlp_output,
            ontology=ontology,
            book_id=f"{book_id}__bench_{chunk_size}",
            chunk_size=chunk_size,
            max_retries=config.max_retries,
            output_dir=size_dir / "batches",
            embed_triplets=False,  # benchmark extraction only, skip vector load
            consolidate=config.consolidate_entities,
            chunk_ordinal_start=chunk_ordinal_counter,
            max_gleanings=max_gleanings,
        )
    elapsed = time.time() - started

    # Gather all per-batch extracted_datapoints.json under size_dir/batches/
    for batch_file in sorted((size_dir / "batches").glob("batch_*/extracted_datapoints.json")):
        try:
            payload = json.loads(batch_file.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                aggregated.extend(payload)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load {}: {}", batch_file, exc)

    all_datapoints_path.write_text(json.dumps(aggregated, indent=2, default=str))

    metrics = {
        "chunk_size": chunk_size,
        "elapsed_seconds": round(elapsed, 2),
        "total_chunks": chunk_ordinal_counter,
        "total_datapoints": len(aggregated),
        # Cost is an estimate — the pipeline itself doesn't emit token telemetry
        # today. When Stage 0 concurrency/caching lands usage metrics, surface
        # them here; for now we compute a floor-approximation from chunk count
        # and assumed 1500 tokens/chunk input × model rate.
        "cost_usd": round(
            chunk_ordinal_counter * (chunk_size * DEFAULT_MODEL_COST_PER_1K_INPUT / 1000 + 500 * DEFAULT_MODEL_COST_PER_1K_OUTPUT / 1000),
            4,
        ),
    }
    return aggregated, metrics


def _plan_only(sizes: list[int], book_id: str, gold_path: Path, output_dir: Path) -> None:
    print(f"Benchmark plan — {book_id}")
    print(f"  sizes:       {sizes}")
    print(f"  gold:        {gold_path}")
    print(f"  output_dir:  {output_dir}")
    print(f"  per size:    re-chunk + extract Phase 2 + score vs gold")
    print(f"  writes:      {output_dir}/size_<N>/extracted_datapoints.json")
    print(f"               {output_dir}/run.jsonl (summary lines)")


async def _run_sweep(
    *,
    book_id: str,
    sizes: list[int],
    gold_path: Path,
    processed_dir: Path,
    output_dir: Path,
    max_gleanings: int,
) -> list[dict]:
    gold = load_gold(gold_path)
    summaries: list[dict] = []
    run_jsonl = output_dir / "run.jsonl"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_jsonl.write_text("")  # truncate

    for size in sizes:
        logger.info("Ablating chunk_size={}", size)
        try:
            datapoints, metrics = await _extract_for_size(
                book_id=book_id,
                chunk_size=size,
                processed_dir=processed_dir,
                output_dir=output_dir,
                max_gleanings=max_gleanings,
            )
        except Exception as exc:
            logger.error("chunk_size={} failed: {}", size, exc)
            summary = {
                "chunk_size": size,
                "error": str(exc),
            }
            with run_jsonl.open("a") as fh:
                fh.write(json.dumps(summary) + "\n")
            continue

        summary = summarize_run(datapoints, gold, extra=metrics)
        summaries.append(summary)
        with run_jsonl.open("a") as fh:
            fh.write(json.dumps(summary, default=str) + "\n")

        rec = summary["entity_recall_all"]["recall"]
        minor = summary["entity_recall_minor"]["recall"]
        rel = summary["relationship_recall"]["recall"]
        prov = summary["provenance_pass_rate"]["rate"]
        logger.info(
            "  size={}: recall_all={:.2f} recall_minor={:.2f} rel_recall={:.2f} prov={:.2f} cost=${:.3f}",
            size, rec, minor, rel, prov, metrics["cost_usd"],
        )

    winner = pick_winner(summaries)
    with run_jsonl.open("a") as fh:
        fh.write(json.dumps({
            "winner": winner["extra"]["chunk_size"] if winner else None,
            "summaries_count": len(summaries),
        }) + "\n")

    if winner:
        logger.info("Winner: chunk_size={}", winner["extra"]["chunk_size"])
    else:
        logger.warning("No winner — no size met the acceptance constraints.")

    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", required=True, help="Book id under data/processed/")
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES,
                        help=f"Chunk sizes to sweep (default {DEFAULT_SIZES})")
    parser.add_argument("--gold", type=Path, default=None,
                        help="Gold JSON path (default tests/golds/{book_id}_gold.json)")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write benchmark outputs (default data/benchmarks/chunk_size_YYYY-MM-DD)")
    parser.add_argument("--max-gleanings", type=int, default=None,
                        help="Override config.max_gleanings for the sweep")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan without running the pipeline")
    args = parser.parse_args(argv)

    gold_path = args.gold or Path("tests/golds") / f"{args.book_id}_gold.json"
    if not gold_path.exists():
        print(f"error: gold file not found: {gold_path}", file=sys.stderr)
        return 1

    output_dir = args.output_dir or (
        Path("data/benchmarks") / f"chunk_size_{date.today().isoformat()}"
    )

    if args.dry_run:
        _plan_only(args.sizes, args.book_id, gold_path, output_dir)
        return 0

    if args.max_gleanings is None:
        from models.config import load_config
        args.max_gleanings = int(getattr(load_config(), "max_gleanings", 0))

    asyncio.run(_run_sweep(
        book_id=args.book_id,
        sizes=args.sizes,
        gold_path=gold_path,
        processed_dir=args.processed_dir,
        output_dir=output_dir,
        max_gleanings=args.max_gleanings,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
