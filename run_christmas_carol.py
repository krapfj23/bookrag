"""End-to-end Phase 1 pipeline run on A Christmas Carol.

Runs: EPUB parse → text clean → stave split → BookNLP → Coref Resolution → Ontology
Skips Phase 2 (Cognee) since cognee is not installed.

Outputs to data/processed/christmas_carol/
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

EPUB_PATH = Path("data/books/christmas_carol.epub")
BOOK_ID = "christmas_carol"
OUTPUT_BASE = Path("data/processed") / BOOK_ID


def banner(msg: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {msg}")
    print(f"{'=' * 70}\n")


def split_into_staves(text: str) -> list[str]:
    """Split A Christmas Carol text into 5 staves using heading markers.

    The Gutenberg EPUB puts the whole book in one spine item, so we
    split on 'STAVE I/ONE' headings.  Returns only chunks with real
    content (> 200 chars) to avoid fragments.
    """
    # Split on lines that start with STAVE
    parts = re.split(r'(?=\n\s*STAVE\s+)', text, flags=re.IGNORECASE)
    staves = [p.strip() for p in parts if len(p.strip()) > 200]
    # Drop the first part if it's preamble (before any STAVE heading)
    if staves and not re.match(r'(?i)\s*STAVE\s+', staves[0]):
        staves = staves[1:]
    return staves if staves else [text]


def strip_gutenberg_boilerplate(text: str) -> str:
    """Remove Project Gutenberg header and footer."""
    # Standard Gutenberg markers
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG EBOOK",
        "*** START OF THIS PROJECT GUTENBERG EBOOK",
        "***START OF THE PROJECT GUTENBERG",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG EBOOK",
        "*** END OF THIS PROJECT GUTENBERG EBOOK",
        "***END OF THE PROJECT GUTENBERG",
        "End of the Project Gutenberg",
        "End of Project Gutenberg",
    ]

    for marker in start_markers:
        idx = text.upper().find(marker.upper())
        if idx != -1:
            # Find next newline after the marker
            nl = text.find("\n", idx)
            if nl != -1:
                text = text[nl + 1:]
            break

    for marker in end_markers:
        idx = text.upper().find(marker.upper())
        if idx != -1:
            text = text[:idx]
            break

    return text.strip()


async def main() -> None:
    total_t0 = time.monotonic()

    if not EPUB_PATH.exists():
        print(f"ERROR: EPUB not found at {EPUB_PATH}")
        sys.exit(1)

    # ==================================================================
    # Stage 1: EPUB Parsing + Text Cleaning
    # ==================================================================
    banner("STAGE 1: EPUB PARSING + TEXT CLEANING")

    from pipeline.epub_parser import parse_epub

    t0 = time.monotonic()
    raw_dir = OUTPUT_BASE / "raw"
    parsed = parse_epub(EPUB_PATH, output_dir=raw_dir)

    # The Gutenberg EPUB has everything in one spine item.
    # Extract the actual book text and split by stave headings.
    combined_text = "\n\n".join(parsed.chapter_texts)
    cleaned_text = strip_gutenberg_boilerplate(combined_text)
    staves = split_into_staves(cleaned_text)

    # Write cleaned staves as the real chapters
    chapters_dir = OUTPUT_BASE / "raw" / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for i, stave in enumerate(staves):
        (chapters_dir / f"chapter_{i+1:02d}.txt").write_text(stave, encoding="utf-8")

    # Build full text with chapter markers and boundaries
    full_parts = []
    chapter_boundaries = []
    cursor = 0
    for i, stave in enumerate(staves):
        marker = f"=== CHAPTER {i+1} ===\n\n"
        full_parts.append(marker)
        cursor += len(marker)
        start = cursor
        full_parts.append(stave)
        cursor += len(stave)
        chapter_boundaries.append((start, cursor))
        full_parts.append("\n\n")
        cursor += 2

    full_text = "".join(full_parts)
    (OUTPUT_BASE / "raw" / "full_text.txt").write_text(full_text, encoding="utf-8")

    elapsed = time.monotonic() - t0

    print(f"  Staves found: {len(staves)}")
    print(f"  Full text:    {len(full_text):,} chars")
    for i, stave in enumerate(staves):
        words = len(stave.split())
        print(f"    Stave {i+1}: {words:,} words, {len(stave):,} chars")
    print(f"  Time:         {elapsed:.1f}s")

    # ==================================================================
    # Stage 2: BookNLP
    # ==================================================================
    banner("STAGE 2: BOOKNLP")

    from pipeline.booknlp_runner import run_booknlp, parse_booknlp_output

    booknlp_dir = OUTPUT_BASE / "booknlp"
    booknlp_dir.mkdir(parents=True, exist_ok=True)

    # BookNLP needs clean text without our chapter markers
    booknlp_input_text = "\n\n".join(staves)

    book_file = booknlp_dir / f"{BOOK_ID}.book"
    if book_file.exists():
        print("  BookNLP outputs exist — re-parsing from disk")
        t0 = time.monotonic()
        booknlp_result = parse_booknlp_output(booknlp_dir, BOOK_ID)
        elapsed = time.monotonic() - t0
    else:
        print("  Running BookNLP (may take several minutes)...")
        t0 = time.monotonic()
        # Write the clean input text for BookNLP
        (booknlp_dir / "input.txt").write_text(booknlp_input_text, encoding="utf-8")
        booknlp_result = await run_booknlp(
            booknlp_input_text, booknlp_dir, BOOK_ID, model_size="small"
        )
        elapsed = time.monotonic() - t0

    print(f"  Characters:  {booknlp_result.character_count}")
    print(f"  Entities:    {booknlp_result.entity_count:,}")
    print(f"  Quotes:      {booknlp_result.quote_count}")
    print(f"  Tokens:      {len(booknlp_result.tokens):,}")
    print(f"  Time:        {elapsed:.1f}s")

    print("\n  Top characters:")
    for ch in booknlp_result.characters[:10]:
        top_aliases = sorted(ch.aliases.items(), key=lambda x: -x[1])[:4]
        aliases_str = ", ".join(f"{k}({v})" for k, v in top_aliases)
        print(f"    [{ch.coref_id}] {ch.canonical_name}: {aliases_str}")

    # ==================================================================
    # Stage 3: Coreference Resolution
    # ==================================================================
    banner("STAGE 3: COREFERENCE RESOLUTION")

    from pipeline.coref_resolver import (
        Token as CorefToken,
        EntityMention as CorefEntityMention,
        CharacterProfile as CorefCharacterProfile,
        CorefConfig,
        resolve_coreferences,
        save_coref_outputs,
    )

    t0 = time.monotonic()

    # Parse sentence IDs from .tokens TSV
    sentence_ids: dict[int, int] = {}
    tokens_tsv_path = booknlp_dir / f"{BOOK_ID}.tokens"
    if tokens_tsv_path.exists():
        lines = tokens_tsv_path.read_text(encoding="utf-8").strip().split("\n")
        if len(lines) > 1:
            headers = lines[0].split("\t")
            sent_col = None
            tid_col = None
            for i, h in enumerate(headers):
                if "sentence" in h.lower() and sent_col is None:
                    sent_col = i
                if h == "token_ID_within_document" or h == "token_id":
                    tid_col = i
            if sent_col is not None:
                for line in lines[1:]:
                    vals = line.split("\t")
                    if sent_col < len(vals):
                        try:
                            row_tid = int(vals[tid_col]) if tid_col and tid_col < len(vals) else -1
                            sentence_ids[row_tid] = int(vals[sent_col])
                        except ValueError:
                            pass
            print(f"  Parsed {len(sentence_ids):,} sentence IDs from .tokens")

    # Convert BookNLP tokens → coref tokens
    coref_tokens = []
    for t in booknlp_result.tokens:
        coref_tokens.append(CorefToken(
            token_id=t.token_id,
            sentence_id=sentence_ids.get(t.token_id, 0),
            token_offset_begin=t.start_char,
            token_offset_end=t.end_char,
            word=t.text,
            pos=t.pos,
            coref_id=t.coref_id if t.coref_id is not None else -1,
        ))

    # Convert entities
    coref_entities = [
        CorefEntityMention(
            coref_id=e.coref_id, start_token=e.start_token, end_token=e.end_token,
            prop=e.prop, cat=e.cat, text=e.text,
        )
        for e in booknlp_result.entities
    ]

    # Convert characters
    coref_characters = [
        CorefCharacterProfile(
            coref_id=ch.coref_id, name=ch.canonical_name, aliases=list(ch.aliases.keys()),
        )
        for ch in booknlp_result.characters
    ]

    # Build chapter boundaries in token space
    # Map BookNLP char offsets back to stave boundaries
    stave_char_boundaries = []
    cursor = 0
    for stave in staves:
        stave_char_boundaries.append((cursor, cursor + len(stave)))
        cursor += len(stave) + 2  # +2 for "\n\n" join separator

    chapter_token_boundaries = []
    for ch_start, ch_end in stave_char_boundaries:
        start_tid = None
        end_tid = None
        for tok in coref_tokens:
            if tok.token_offset_begin >= ch_start and start_tid is None:
                start_tid = tok.token_id
            if tok.token_offset_begin < ch_end:
                end_tid = tok.token_id + 1
        if start_tid is not None and end_tid is not None:
            chapter_token_boundaries.append((start_tid, end_tid))

    print(f"  Tokens:      {len(coref_tokens):,}")
    print(f"  Entities:    {len(coref_entities):,}")
    print(f"  Characters:  {len(coref_characters)}")
    print(f"  Staves:      {len(chapter_token_boundaries)}")

    config = CorefConfig(distance_threshold=3, ambiguity_window=2, annotate_ambiguous=True)
    result = resolve_coreferences(
        tokens=coref_tokens,
        entities=coref_entities,
        characters=coref_characters,
        chapter_texts=staves,
        chapter_boundaries=chapter_token_boundaries,
        config=config,
        source_text=booknlp_input_text,
    )
    elapsed = time.monotonic() - t0

    save_coref_outputs(result, BOOK_ID, base_dir=OUTPUT_BASE.parent)

    print(f"\n  Total insertions: {len(result.resolution_log):,}")
    rules = Counter(ev.rule_triggered for ev in result.resolution_log)
    print(f"  Rule breakdown:  {dict(rules)}")
    print(f"  Clusters:        {len(result.clusters)}")

    print("\n  Top resolved clusters:")
    sorted_clusters = sorted(result.clusters.items(), key=lambda x: -x[1].resolution_count)
    for cid, cl in sorted_clusters[:10]:
        print(f"    [{cid}] {cl.canonical_name}: {len(cl.mentions)} mentions, {cl.resolution_count} resolved")

    print(f"\n  Per-stave insertions:")
    for ci in range(len(chapter_token_boundaries)):
        chap_count = sum(1 for ev in result.resolution_log if ev.chapter == ci)
        chap_words = len(result.resolved_chapters[ci].split()) if ci < len(result.resolved_chapters) else 0
        print(f"    Stave {ci+1}: {chap_count} insertions ({chap_words:,} words)")

    # Show sample resolved text
    print("\n  Sample resolved text (first 400 chars of Stave 1):")
    if result.resolved_chapters:
        preview = result.resolved_chapters[0][:400]
        print(f"    {preview}")

    print(f"\n  Time: {elapsed:.1f}s")

    # ==================================================================
    # Stage 4: Ontology Discovery
    # ==================================================================
    banner("STAGE 4: ONTOLOGY DISCOVERY")

    from pipeline.ontology_discovery import discover_ontology

    t0 = time.monotonic()
    ontology_dir = OUTPUT_BASE / "ontology"
    ontology_dir.mkdir(parents=True, exist_ok=True)

    booknlp_dict = booknlp_result.to_pipeline_dict()
    ontology_result = discover_ontology(
        booknlp_output={
            "book_json": {"characters": booknlp_dict["characters"]},
            "entities_tsv": booknlp_dict["entities"],
        },
        full_text=booknlp_input_text,
        book_id=BOOK_ID,
    )
    elapsed = time.monotonic() - t0

    print(f"  Entity types: {list(ontology_result.discovered_entities.keys())}")
    for etype, ents in ontology_result.discovered_entities.items():
        print(f"    {etype}: {len(ents)} entities")
        for e in ents[:3]:
            print(f"      - {e['name']} (count={e.get('count', '?')})")

    print(f"\n  Themes: {len(ontology_result.discovered_themes)}")
    for theme in ontology_result.discovered_themes[:5]:
        print(f"    - {theme.get('label', '?')}: {', '.join(theme.get('keywords', [])[:5])}")

    print(f"\n  OWL file: {ontology_result.owl_path}")
    print(f"  Time: {elapsed:.1f}s")

    # ==================================================================
    # Summary
    # ==================================================================
    total_elapsed = time.monotonic() - total_t0
    banner("PIPELINE COMPLETE")
    print(f"  Total time: {total_elapsed:.1f}s")
    print(f"  Output dir: {OUTPUT_BASE}")
    print(f"\n  Output files:")
    for p in sorted(OUTPUT_BASE.rglob("*")):
        if p.is_file():
            size = p.stat().st_size
            rel = p.relative_to(OUTPUT_BASE)
            print(f"    {rel}: {size:,} bytes")


if __name__ == "__main__":
    asyncio.run(main())
