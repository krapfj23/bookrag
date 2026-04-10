"""BookNLP runner — execute BookNLP and parse its output files.

Wraps BookNLP execution and provides structured parsing of all output
files (.tokens, .entities, .quotes, .supersense, .book) into Python
dataclasses for downstream pipeline consumption.

BookNLP output format reference (from deep research doc):
  - .tokens  — TSV, every token: POS, dependency, coref ID, event triggers
  - .entities — TSV, entity mentions: COREF cluster ID, token span, type, prop
  - .quotes  — TSV, quotation text + attributed speaker (coref ID)
  - .supersense — TSV, WordNet semantic categories
  - .book    — JSON, character profiles: names, actions, modifiers, gender
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from pipeline.tsv_utils import read_tsv, safe_int


# ---------------------------------------------------------------------------
# Parsed data models
# ---------------------------------------------------------------------------

@dataclass
class EntityMention:
    """A single entity mention from BookNLP's .entities file."""

    coref_id: int
    start_token: int
    end_token: int
    prop: str           # PROP | NOM | PRON
    cat: str            # PER | LOC | FAC | GPE | VEH | ORG
    text: str
    start_char: int = 0
    end_char: int = 0


@dataclass
class QuoteAttribution:
    """A quotation with speaker attribution from BookNLP's .quotes file."""

    text: str
    speaker_coref_id: int | None
    start_token: int
    end_token: int
    start_char: int = 0
    end_char: int = 0


@dataclass
class CharacterProfile:
    """A character profile from BookNLP's .book JSON."""

    coref_id: int
    canonical_name: str
    aliases: dict[str, int]    # name → mention count
    agent_actions: list[dict[str, Any]]
    patient_actions: list[dict[str, Any]]
    modifiers: list[str]
    possessions: list[str]
    gender: str

    @property
    def name(self) -> str:
        return self.canonical_name

    @property
    def mention_count(self) -> int:
        return sum(self.aliases.values())


@dataclass
class TokenAnnotation:
    """A single token annotation from BookNLP's .tokens file."""

    token_id: int
    sentence_id: int       # sentence_ID column from .tokens TSV
    text: str
    lemma: str
    pos: str               # POS tag
    dep: str               # dependency relation
    coref_id: int | None
    start_char: int
    end_char: int


@dataclass
class BookNLPOutput:
    """Complete parsed output from a BookNLP run.

    This is the primary data structure passed to downstream stages
    (coref resolver, ontology discovery, cognee pipeline).
    """

    book_id: str
    characters: list[CharacterProfile]
    entities: list[EntityMention]
    quotes: list[QuoteAttribution]
    tokens: list[TokenAnnotation]
    coref_id_to_name: dict[int, str] = field(default_factory=dict)

    @property
    def character_count(self) -> int:
        return len(self.characters)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def quote_count(self) -> int:
        return len(self.quotes)

    def to_pipeline_dict(self) -> dict[str, Any]:
        """Convert to the dict format expected by the cognee pipeline.

        Returns dict with 'entities' and 'quotes' lists containing dicts
        with start_char/end_char for range-based filtering.
        """
        entities = [
            {
                "coref_id": e.coref_id,
                "start_char": e.start_char,
                "end_char": e.end_char,
                "text": e.text,
                "cat": e.cat,
                "prop": e.prop,
                "canonical_name": self.coref_id_to_name.get(e.coref_id, e.text),
            }
            for e in self.entities
        ]
        quotes = [
            {
                "text": q.text,
                "speaker_coref_id": q.speaker_coref_id,
                "speaker_name": (
                    self.coref_id_to_name.get(q.speaker_coref_id, "Unknown")
                    if q.speaker_coref_id is not None
                    else "Unknown"
                ),
                "start_char": q.start_char,
                "end_char": q.end_char,
            }
            for q in self.quotes
        ]
        return {
            "entities": entities,
            "quotes": quotes,
            "characters": [
                {
                    "coref_id": c.coref_id,
                    "canonical_name": c.canonical_name,
                    "aliases": c.aliases,
                    "gender": c.gender,
                    "modifiers": c.modifiers,
                }
                for c in self.characters
            ],
        }


# ---------------------------------------------------------------------------
# BookNLP execution
# ---------------------------------------------------------------------------

async def run_booknlp(
    full_text: str,
    output_dir: Path,
    book_id: str,
    model_size: str = "small",
) -> BookNLPOutput:
    """Run BookNLP on the full text and parse all output files.

    Args:
        full_text: The complete book text.
        output_dir: Directory to write BookNLP output files into.
        book_id: Identifier used for output filenames.
        model_size: BookNLP model size ("small" or "big").

    Returns:
        Parsed BookNLPOutput with all structured annotations.

    Raises:
        ImportError: If booknlp package is not installed.
    """
    from booknlp.booknlp import BookNLP

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write input text for BookNLP
    input_path = output_dir / "input.txt"
    input_path.write_text(full_text, encoding="utf-8")

    logger.info(
        "Running BookNLP (model={}) on {} chars, output_dir={}",
        model_size, len(full_text), output_dir,
    )

    model = BookNLP("en", {"pipeline": "entity,quote,coref", "model": model_size})

    # BookNLP is CPU-bound; run in a thread to avoid blocking the event loop
    await asyncio.to_thread(
        model.process,
        str(input_path),
        str(output_dir),
        book_id,
    )

    logger.info("BookNLP execution complete for {}", book_id)

    return parse_booknlp_output(output_dir, book_id)


def parse_booknlp_output(output_dir: Path, book_id: str) -> BookNLPOutput:
    """Parse all BookNLP output files from a completed run.

    Can be called independently to re-parse outputs without re-running
    BookNLP (supports pipeline resume).

    Args:
        output_dir: Directory containing BookNLP output files.
        book_id: The book ID used during BookNLP processing.

    Returns:
        Parsed BookNLPOutput.
    """
    output_dir = Path(output_dir)

    characters = _parse_book_json(output_dir / f"{book_id}.book")
    entities = _parse_entities_tsv(output_dir / f"{book_id}.entities")
    quotes = _parse_quotes_tsv(output_dir / f"{book_id}.quotes")
    tokens = _parse_tokens_tsv(output_dir / f"{book_id}.tokens")

    # Enrich character names from entity mentions when the .book JSON
    # lacks the 'names' field (common with BookNLP small model).
    # First pass: PROP mentions (proper nouns — highest confidence).
    # Second pass: NOM mentions (nominals — "the Ghost", "his nephew") for
    # characters that still have placeholder names after PROP pass.
    _enrich_character_names_from_entities(characters, entities)

    # Build coref_id → canonical name mapping from character profiles
    coref_id_to_name = _build_coref_name_map(characters)

    # Back-fill char offsets on entities and quotes from tokens
    token_char_map = {t.token_id: (t.start_char, t.end_char) for t in tokens}
    _fill_char_offsets_entities(entities, token_char_map)
    _fill_char_offsets_quotes(quotes, token_char_map)

    result = BookNLPOutput(
        book_id=book_id,
        characters=characters,
        entities=entities,
        quotes=quotes,
        tokens=tokens,
        coref_id_to_name=coref_id_to_name,
    )

    logger.info(
        "Parsed BookNLP output: {} characters, {} entities, {} quotes, {} tokens",
        result.character_count,
        result.entity_count,
        result.quote_count,
        len(tokens),
    )

    return result


# ---------------------------------------------------------------------------
# Individual file parsers
# ---------------------------------------------------------------------------

def _parse_book_json(path: Path) -> list[CharacterProfile]:
    """Parse BookNLP's .book JSON file into CharacterProfile objects."""
    if not path.exists():
        logger.warning("BookNLP .book file not found: {}", path)
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    characters: list[CharacterProfile] = []

    for char_data in data.get("characters", []):
        # names is a dict of {name: count}
        names = char_data.get("names", {})
        if isinstance(names, list):
            # Handle alternative format where names is a list of strings
            names = {n: 1 for n in names}

        # Canonical name: highest mention count
        canonical = max(names, key=names.get) if names else f"CHARACTER_{char_data.get('id', '?')}"

        characters.append(CharacterProfile(
            coref_id=char_data.get("id", -1),
            canonical_name=canonical,
            aliases=names,
            agent_actions=char_data.get("agent", []),
            patient_actions=char_data.get("patient", []),
            modifiers=char_data.get("mod", []),
            possessions=char_data.get("poss", []),
            gender=char_data.get("g", "unknown"),
        ))

    logger.debug("Parsed {} characters from {}", len(characters), path.name)
    return characters


def _parse_entities_tsv(path: Path) -> list[EntityMention]:
    """Parse BookNLP's .entities TSV file."""
    if not path.exists():
        logger.warning("BookNLP .entities file not found: {}", path)
        return []

    rows = read_tsv(path)
    entities: list[EntityMention] = []

    for row in rows:
        try:
            entities.append(EntityMention(
                coref_id=safe_int(row.get("COREF", "-1")),
                start_token=safe_int(row.get("start_token", "0")),
                end_token=safe_int(row.get("end_token", "0")),
                prop=row.get("prop", ""),
                cat=row.get("cat", ""),
                text=row.get("text", ""),
            ))
        except (ValueError, KeyError) as exc:
            logger.debug("Skipping malformed entity row: {} ({})", row, exc)

    logger.debug("Parsed {} entity mentions from {}", len(entities), path.name)
    return entities


def _parse_quotes_tsv(path: Path) -> list[QuoteAttribution]:
    """Parse BookNLP's .quotes TSV file."""
    if not path.exists():
        logger.warning("BookNLP .quotes file not found: {}", path)
        return []

    rows = read_tsv(path)
    quotes: list[QuoteAttribution] = []

    for row in rows:
        try:
            speaker_raw = row.get("char_id", row.get("speaker", ""))
            speaker_id = safe_int(speaker_raw) if speaker_raw not in ("", "-1") else None

            quotes.append(QuoteAttribution(
                text=row.get("quote", row.get("text", "")),
                speaker_coref_id=speaker_id,
                start_token=safe_int(row.get("quote_start", row.get("start_token", "0"))),
                end_token=safe_int(row.get("quote_end", row.get("end_token", "0"))),
            ))
        except (ValueError, KeyError) as exc:
            logger.debug("Skipping malformed quote row: {} ({})", row, exc)

    logger.debug("Parsed {} quotes from {}", len(quotes), path.name)
    return quotes


def _parse_tokens_tsv(path: Path) -> list[TokenAnnotation]:
    """Parse BookNLP's .tokens TSV file.

    The .tokens file can be large (one row per token in the book).
    We parse it to build a token_id → char_offset mapping needed
    by entities and quotes.
    """
    if not path.exists():
        logger.warning("BookNLP .tokens file not found: {}", path)
        return []

    rows = read_tsv(path)
    tokens: list[TokenAnnotation] = []

    for row in rows:
        try:
            coref_raw = row.get("COREF", row.get("coref", ""))
            coref_id = safe_int(coref_raw) if coref_raw not in ("", "-1", "-") else None

            tokens.append(TokenAnnotation(
                token_id=safe_int(row.get("token_ID_within_document", row.get("token_id", "0"))),
                sentence_id=safe_int(row.get("sentence_ID", row.get("sentence_id", "0"))),
                text=row.get("word", row.get("text", "")),
                lemma=row.get("lemma", ""),
                pos=row.get("POS_tag", row.get("pos", "")),
                dep=row.get("dependency_relation", row.get("dep", "")),
                coref_id=coref_id,
                start_char=safe_int(row.get("byte_onset", row.get("start_char", "0"))),
                end_char=safe_int(row.get("byte_offset", row.get("end_char", "0"))),
            ))
        except (ValueError, KeyError) as exc:
            logger.debug("Skipping malformed token row: {} ({})", row, exc)

    logger.debug("Parsed {} tokens from {}", len(tokens), path.name)
    return tokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_coref_name_map(characters: list[CharacterProfile]) -> dict[int, str]:
    """Build a mapping from coref cluster ID to canonical character name."""
    return {c.coref_id: c.canonical_name for c in characters}


def _enrich_character_names_from_entities(
    characters: list[CharacterProfile],
    entities: list[EntityMention],
) -> None:
    """Fill in character names from entity mentions when .book JSON lacks them.

    BookNLP's small model often omits the 'names' dict from character profiles.
    Two-pass approach:
      1. PROP mentions (proper nouns) — highest quality: "Scrooge", "Bob Cratchit"
      2. NOM mentions (nominals) — fallback: "the Ghost", "his nephew", "the boy"
         Only used for characters still unnamed after pass 1.
         Filters out generic pronouns and very short mentions.
    """
    from collections import Counter, defaultdict

    # Pass 1: PROP mentions
    prop_names: dict[int, Counter] = defaultdict(Counter)
    for e in entities:
        if e.prop == "PROP" and e.text:
            prop_names[e.coref_id][e.text] += 1

    enriched_prop = 0
    for ch in characters:
        if ch.canonical_name.startswith("CHARACTER_") and ch.coref_id in prop_names:
            names = prop_names[ch.coref_id]
            if names:
                ch.canonical_name = names.most_common(1)[0][0]
                ch.aliases = dict(names)
                enriched_prop += 1

    # Pass 2: NOM mentions for remaining CHARACTER_N placeholders
    nom_names: dict[int, Counter] = defaultdict(Counter)
    # Skip generic words that aren't useful as character identifiers
    skip_noms = {
        "he", "she", "him", "her", "his", "it", "its", "they", "them",
        "their", "i", "me", "my", "we", "us", "our", "you", "your",
        "myself", "himself", "herself", "themselves", "yourself",
        "sir", "ma'am", "one",
    }
    for e in entities:
        if e.prop == "NOM" and e.text and e.text.lower() not in skip_noms:
            # Only keep nominals that look like descriptive references (2+ chars)
            if len(e.text) > 2:
                nom_names[e.coref_id][e.text] += 1

    enriched_nom = 0
    for ch in characters:
        if ch.canonical_name.startswith("CHARACTER_") and ch.coref_id in nom_names:
            names = nom_names[ch.coref_id]
            if names:
                # Pick the most frequent nominal as the display name
                best_name = names.most_common(1)[0][0]
                # Title-case it for readability: "the ghost" → "The Ghost"
                ch.canonical_name = best_name.title() if best_name[0].islower() else best_name
                ch.aliases = dict(names)
                enriched_nom += 1

    if enriched_prop or enriched_nom:
        logger.info(
            "Enriched character names: {} from PROP mentions, {} from NOM mentions",
            enriched_prop, enriched_nom,
        )


def _fill_char_offsets_entities(
    entities: list[EntityMention],
    token_char_map: dict[int, tuple[int, int]],
) -> None:
    """Fill start_char/end_char on entities from the token offset map."""
    for entity in entities:
        start = token_char_map.get(entity.start_token)
        end = token_char_map.get(entity.end_token)
        if start is not None:
            entity.start_char = start[0]
        if end is not None:
            entity.end_char = end[1]


def _fill_char_offsets_quotes(
    quotes: list[QuoteAttribution],
    token_char_map: dict[int, tuple[int, int]],
) -> None:
    """Fill start_char/end_char on quotes from the token offset map."""
    for quote in quotes:
        start = token_char_map.get(quote.start_token)
        end = token_char_map.get(quote.end_token)
        if start is not None:
            quote.start_char = start[0]
        if end is not None:
            quote.end_char = end[1]


def create_stub_output(book_id: str) -> BookNLPOutput:
    """Create an empty BookNLPOutput stub when BookNLP is not installed.

    This allows the pipeline to proceed with degraded quality (no NLP
    annotations) for testing or when BookNLP can't be installed.
    """
    logger.warning("Creating stub BookNLP output for {} (no annotations)", book_id)
    return BookNLPOutput(
        book_id=book_id,
        characters=[],
        entities=[],
        quotes=[],
        tokens=[],
        coref_id_to_name={},
    )
