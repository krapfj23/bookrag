"""Test Cognee Phase 2 pipeline on one batch of A Christmas Carol resolved text.

Runs: chunk → LLM extraction → add_data_points
Uses resolved text from the Phase 1 run.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

OUTPUT_BASE = Path("data/processed/christmas_carol")


async def main() -> None:
    # Verify resolved text exists
    resolved_dir = OUTPUT_BASE / "resolved" / "chapters"
    if not resolved_dir.exists():
        print("ERROR: Run run_christmas_carol.py first to generate Phase 1 outputs")
        sys.exit(1)

    # Load first stave (chapter 2 has the main Scrooge content)
    ch2_path = resolved_dir / "chapter_02.txt"
    if not ch2_path.exists():
        print(f"ERROR: {ch2_path} not found")
        sys.exit(1)

    chapter_text = ch2_path.read_text(encoding="utf-8")
    print(f"Loaded Stave 1 (Marley's Ghost): {len(chapter_text):,} chars, {len(chapter_text.split()):,} words")

    # Load ontology
    ontology_path = OUTPUT_BASE / "ontology" / "discovered_entities.json"
    if ontology_path.exists():
        ontology_raw = json.loads(ontology_path.read_text())
        ontology = {
            "entity_classes": list(ontology_raw.keys()),
            "relation_types": [
                "ALLIES_WITH", "OPPOSES", "LOCATED_IN", "MEMBER_OF",
                "POSSESSES", "PARTICIPATES_IN", "CAUSES", "PRECEDES",
                "RELATED_TO", "SPEAKS_TO", "KNOWS", "EMPLOYS",
            ],
        }
    else:
        ontology = {"entity_classes": ["Character", "Location", "Organization"], "relation_types": []}

    # Load BookNLP output
    booknlp_output = {"entities": [], "quotes": [], "characters": []}

    print(f"\n--- Testing Cognee Pipeline Components ---\n")

    # Step 1: Test chunking — use smaller chunk size to actually get multiple chunks
    print("STEP 1: Chapter-aware chunking")
    from pipeline.cognee_pipeline import chunk_with_chapter_awareness
    chunks = chunk_with_chapter_awareness(
        text=chapter_text,
        chunk_size=500,  # ~500 tokens = ~2000 chars per chunk
        chapter_numbers=[1],
    )
    print(f"  Produced {len(chunks)} chunks")
    for i, c in enumerate(chunks[:5]):
        print(f"    Chunk {i+1}: ~{c.token_estimate} tokens, {len(c.text)} chars")
    if len(chunks) > 5:
        print(f"    ... and {len(chunks) - 5} more")

    # Step 2: Test LLM extraction on first chunk only (to save cost)
    print(f"\nSTEP 2: LLM extraction (first chunk only, ~{chunks[0].token_estimate} tokens)")

    from pipeline.cognee_pipeline import render_prompt, ExtractionResult
    from cognee.infrastructure.llm.LLMGateway import LLMGateway

    system_prompt, text_input = render_prompt(chunks[0], booknlp_output, ontology)
    print(f"  System prompt: {len(system_prompt):,} chars")
    print(f"  Text input:    {len(text_input):,} chars")
    print(f"  First 300 chars of system prompt:\n    {system_prompt[:300]}...")

    print("\n  Calling LLMGateway.acreate_structured_output...")
    t0 = time.monotonic()
    try:
        extraction = await LLMGateway.acreate_structured_output(
            text_input=text_input,
            system_prompt=system_prompt,
            response_model=ExtractionResult,
        )
        elapsed = time.monotonic() - t0

        print(f"  Success! ({elapsed:.1f}s)")
        print(f"  Entities: {len(extraction.entities)}")
        for ent in extraction.entities[:10]:
            print(f"    - {ent.name} ({ent.entity_type}): {ent.description[:80]}...")
        print(f"  Relations: {len(extraction.relations)}")
        for rel in extraction.relations[:10]:
            print(f"    - {rel.source} --{rel.relation_type}--> {rel.target}: {rel.description[:60]}...")

        # Save extraction result
        result_path = OUTPUT_BASE / "batches" / "test_extraction.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(extraction.model_dump_json(indent=2))
        print(f"\n  Saved to {result_path}")

    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"  FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()

    # Step 3: Test full pipeline assembly (if extraction worked)
    print(f"\nSTEP 3: Full pipeline (all {len(chunks)} chunks)")
    from pipeline.cognee_pipeline import run_bookrag_pipeline
    from pipeline.batcher import Batch

    batch = Batch(
        chapter_numbers=[1],
        chapter_texts=[chapter_text],
        combined_text=chapter_text,
    )

    class FakeConfig:
        book_id = "christmas_carol_test"
        chunk_size = 1500
        max_retries = 2

    t0 = time.monotonic()
    try:
        async for status in run_bookrag_pipeline(
            batch=batch,
            booknlp_output=booknlp_output,
            ontology=ontology,
            config=FakeConfig(),
        ):
            if isinstance(status, dict):
                logger.debug("Pipeline status: {}", status)
            elif isinstance(status, list):
                logger.info("Pipeline returned {} items", len(status))

        elapsed = time.monotonic() - t0
        print(f"\n  Full pipeline completed in {elapsed:.1f}s")

    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"\n  Full pipeline FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
