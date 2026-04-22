#!/usr/bin/env python3
"""Re-run Phase 2 (batching + LLM extraction + Cognee persistence) for a book
whose Phase 1 artifacts (BookNLP, coref, ontology, resolved chapters) are
already on disk.

Use this when the extraction prompt or extraction code changes but the
upstream NLP work is still good — skips ~minutes of BookNLP + coref.

Before-state is preserved: the existing batches/ directory is renamed to
batches.bak.<timestamp> so you can diff old vs new extractions.

Usage:
    python scripts/reextract_book.py christmas_carol_e6ddcd76

Exits 0 on success, 1 on any batch failure.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

# Make project imports work whether this script is invoked from the
# repo root (python scripts/reextract_book.py) or from scripts/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from models.config import load_config, ensure_directories
from pipeline.batcher import get_batcher
from pipeline.booknlp_runner import parse_booknlp_output
from pipeline.booknlp_utils import booknlp_output_to_dict
from pipeline.cognee_pipeline import configure_cognee, run_bookrag_pipeline
from loguru import logger


async def reextract(book_id: str) -> int:
    config = load_config()
    ensure_directories(config)
    configure_cognee(config)

    book_dir = Path(config.processed_dir) / book_id
    if not book_dir.exists():
        logger.error("Book directory not found: {}", book_dir)
        return 1

    # 1. Load resolved chapters (prefer) or raw chapters
    resolved_dir = book_dir / "resolved" / "chapters"
    raw_dir = book_dir / "raw" / "chapters"
    if resolved_dir.exists() and list(resolved_dir.glob("chapter_*.txt")):
        chapter_files = sorted(resolved_dir.glob("chapter_*.txt"))
        source_label = "resolved"
    elif raw_dir.exists():
        chapter_files = sorted(raw_dir.glob("chapter_*.txt"))
        source_label = "raw"
    else:
        logger.error("No chapter files under {}", book_dir)
        return 1
    chapter_texts = [f.read_text(encoding="utf-8") for f in chapter_files]
    logger.info("Loaded {} {} chapters", len(chapter_texts), source_label)

    # 2. Load BookNLP output from disk
    booknlp_dir = book_dir / "booknlp"
    if booknlp_dir.exists():
        parsed = parse_booknlp_output(booknlp_dir, book_id)
        booknlp_output = booknlp_output_to_dict(parsed)
        logger.info(
            "Loaded BookNLP: {} entity rows, {} quotes",
            len(booknlp_output.get("entities_tsv") or booknlp_output.get("entities") or []),
            len(booknlp_output.get("quotes") or []),
        )
    else:
        logger.warning("No BookNLP dir at {}; proceeding without", booknlp_dir)
        booknlp_output = {}

    # 3. Load ontology from disk
    ontology: dict = {}
    ontology_json = book_dir / "ontology" / "discovered_entities.json"
    if ontology_json.exists():
        ontology = json.loads(ontology_json.read_text(encoding="utf-8"))
        classes = (
            len(ontology.get("entity_classes", []))
            if isinstance(ontology, dict) else 0
        )
        logger.info("Loaded ontology: {} classes", classes)
    else:
        logger.warning("No ontology at {}; proceeding without", ontology_json)

    # 4. Back up existing batches/ so we can diff
    batches_dir = book_dir / "batches"
    if batches_dir.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup = book_dir / f"batches.bak.{ts}"
        shutil.move(str(batches_dir), str(backup))
        logger.info("Backed up existing batches -> {}", backup)

    # 5. Batch + run extraction
    batcher = get_batcher(config)
    batches = batcher.batch(chapter_texts)
    logger.info("Running {} batch(es) through extraction...", len(batches))

    max_retries = getattr(config, "max_retries", 3)
    chunk_size = getattr(config, "chunk_size", 1500)

    for idx, batch in enumerate(batches, start=1):
        logger.info(
            "Batch {}/{} (chapters {})",
            idx, len(batches), batch.chapter_numbers,
        )
        try:
            await run_bookrag_pipeline(
                batch=batch,
                booknlp_output=booknlp_output,
                ontology=ontology,
                book_id=book_id,
                chunk_size=chunk_size,
                max_retries=max_retries,
                embed_triplets=getattr(config, "embed_triplets", False),
                consolidate=getattr(config, "consolidate_entities", False),
            )
        except Exception as exc:
            logger.exception("Batch {} failed: {}", idx, exc)
            return 1

    logger.info("Re-extraction complete for {}", book_id)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    book_id = sys.argv[1]
    return asyncio.run(reextract(book_id))


if __name__ == "__main__":
    sys.exit(main())
