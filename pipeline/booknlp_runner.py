"""BookNLP runner: executes BookNLP on a text file and parses all outputs
into structured Python dataclasses.

Handles .tokens, .entities, .quotes TSV files and the .book JSON file,
producing a unified BookNLPOutput for downstream pipeline consumption.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """A single token from the BookNLP .tokens file."""

    token_id: int
    sentence_id: int
    token_offset_begin: int
    token_offset_end: int
    word: str
    lemma: str
    pos: str
    dep_rel: str
    dep_head: int
    coref_id: int  # -1 if none
    supersense: str = ""
    event: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Token:
        """Parse a single row from the .tokens TSV."""
        return cls(
            token_id=_int(row, "token_ID_within_document", fallback_keys=["token_id"]),
            sentence_id=_int(row, "sentence_ID", fallback_keys=["sentence_id"]),
            token_offset_begin=_int(row, "token_offset_begin", fallback_keys=["byte_onset", "start_offset"]),
            token_offset_end=_int(row, "token_offset_end", fallback_keys=["byte_offset", "end_offset"]),
            word=_str(row, "word", fallback_keys=["token"]),
            lemma=_str(row, "lemma"),
            pos=_str(row, "POS_tag", fallback_keys=["pos", "fine_POS_tag"]),
            dep_rel=_str(row, "dependency_relation", fallback_keys=["dep_rel"]),
            dep_head=_int(row, "dependency_head_ID", fallback_keys=["dep_head"]),
            coref_id=_int(row, "coref_id", fallback_keys=["COREF", "coref"], default=-1),
            supersense=_str(row, "supersense_category", fallback_keys=["supersense"], default=""),
            event=_str(row, "event", fallback_keys=["event_category"], default=""),
        )


@dataclass
class EntityMention:
    """A named-entity mention from the BookNLP .entities file."""

    coref_id: int
    start_token: int
    end_token: int
    prop: str  # PROP, NOM, PRON
    cat: str   # PER, LOC, FAC, GPE, VEH, ORG
    text: str

    @classmethod
    def from_row(cls, row: dict[str, str]) -> EntityMention:
        """Parse a single row from the .entities TSV."""
        return cls(
            coref_id=_int(row, "COREF", fallback_keys=["coref_id", "coref"]),
            start_token=_int(row, "start_token", fallback_keys=["token_ID_start"]),
            end_token=_int(row, "end_token", fallback_keys=["token_ID_end"]),
            prop=_str(row, "prop", fallback_keys=["PROP"]),
            cat=_str(row, "cat", fallback_keys=["CAT", "ner", "NER"]),
            text=_str(row, "text", fallback_keys=["Text", "mention"]),
        )


@dataclass
class Quote:
    """A detected quote with attributed speaker."""

    quote_start: int
    quote_end: int
    quote_text: str
    speaker_coref_id: int
    speaker_name: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str], coref_to_name: dict[int, str] | None = None) -> Quote:
        """Parse a single row from the .quotes TSV."""
        coref_id = _int(row, "char_id", fallback_keys=["speaker_coref_id", "coref_id", "COREF"])
        speaker_name = ""
        if coref_to_name and coref_id in coref_to_name:
            speaker_name = coref_to_name[coref_id]

        return cls(
            quote_start=_int(row, "quote_start", fallback_keys=["start_token"]),
            quote_end=_int(row, "quote_end", fallback_keys=["end_token"]),
            quote_text=_str(row, "quote", fallback_keys=["quote_text", "text"]),
            speaker_coref_id=coref_id,
            speaker_name=speaker_name,
        )


@dataclass
class CharacterProfile:
    """A character profile extracted from the BookNLP .book JSON."""

    coref_id: int
    name: str
    aliases: list[str] = field(default_factory=list)
    gender: str = ""
    agent_actions: list[str] = field(default_factory=list)
    patient_actions: list[str] = field(default_factory=list)
    possessions: list[str] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class BookNLPOutput:
    """Complete structured output from a BookNLP run."""

    book_id: str
    tokens: list[Token] = field(default_factory=list)
    entities: list[EntityMention] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
    characters: list[CharacterProfile] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TSV / JSON helper parsers
# ---------------------------------------------------------------------------

def _int(row: dict[str, str], key: str, *, fallback_keys: list[str] | None = None, default: int = 0) -> int:
    """Safely extract an integer from a TSV row, trying fallback column names."""
    keys = [key] + (fallback_keys or [])
    for k in keys:
        if k in row:
            val = row[k].strip()
            if val == "" or val == "NA" or val == "-1":
                return default if val in ("", "NA") else -1
            try:
                return int(val)
            except ValueError:
                try:
                    return int(float(val))
                except ValueError:
                    continue
    return default


def _str(row: dict[str, str], key: str, *, fallback_keys: list[str] | None = None, default: str = "") -> str:
    """Safely extract a string from a TSV row, trying fallback column names."""
    keys = [key] + (fallback_keys or [])
    for k in keys:
        if k in row:
            return row[k].strip()
    return default


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a TSV file into a list of dicts (one per row)."""
    if not path.exists():
        logger.warning("TSV file not found: {}", path)
        return []

    rows: list[dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for line_num, row in enumerate(reader, start=2):
            try:
                rows.append(dict(row))
            except Exception as exc:
                logger.warning("Malformed row at line {} in {}: {}", line_num, path.name, exc)
    logger.info("Read {} rows from {}", len(rows), path.name)
    return rows


def _parse_tokens(path: Path) -> list[Token]:
    """Parse the .tokens TSV file."""
    rows = _read_tsv(path)
    tokens: list[Token] = []
    for i, row in enumerate(rows):
        try:
            tokens.append(Token.from_row(row))
        except Exception as exc:
            logger.warning("Failed to parse token row {}: {}", i, exc)
    return tokens


def _parse_entities(path: Path) -> list[EntityMention]:
    """Parse the .entities TSV file."""
    rows = _read_tsv(path)
    entities: list[EntityMention] = []
    for i, row in enumerate(rows):
        try:
            entities.append(EntityMention.from_row(row))
        except Exception as exc:
            logger.warning("Failed to parse entity row {}: {}", i, exc)
    return entities


def _parse_quotes(path: Path, coref_to_name: dict[int, str]) -> list[Quote]:
    """Parse the .quotes TSV file, resolving speaker names from coref map."""
    rows = _read_tsv(path)
    quotes: list[Quote] = []
    for i, row in enumerate(rows):
        try:
            quotes.append(Quote.from_row(row, coref_to_name))
        except Exception as exc:
            logger.warning("Failed to parse quote row {}: {}", i, exc)
    return quotes


def _parse_book_json(path: Path) -> tuple[list[CharacterProfile], dict[int, str]]:
    """Parse the .book JSON file for character profiles.

    Returns:
        Tuple of (character profiles list, coref_id -> canonical name mapping).
    """
    if not path.exists():
        logger.warning("Book JSON not found: {}", path)
        return [], {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    characters: list[CharacterProfile] = []
    coref_to_name: dict[int, str] = {}

    char_list = data if isinstance(data, list) else data.get("characters", [])

    for char_data in char_list:
        coref_id = char_data.get("id", char_data.get("coref_id", -1))

        # Extract canonical name and aliases from "names" or "mentions"
        names_data = char_data.get("names", char_data.get("mentions", {}))
        all_names: list[str] = []
        if isinstance(names_data, dict):
            # BookNLP format: {"proper": [...], "common": [...]}
            for category in ("proper", "common", "pronoun"):
                for entry in names_data.get(category, []):
                    name = entry if isinstance(entry, str) else entry.get("n", entry.get("name", ""))
                    if name:
                        all_names.append(name)
        elif isinstance(names_data, list):
            all_names = [str(n) for n in names_data]

        canonical_name = all_names[0] if all_names else f"CHARACTER_{coref_id}"
        aliases = all_names[1:] if len(all_names) > 1 else []

        gender = char_data.get("g", char_data.get("gender", ""))
        if isinstance(gender, dict):
            # BookNLP sometimes has {"male": 0.1, "female": 0.9}
            gender = max(gender, key=gender.get) if gender else ""

        # Extract actions and attributes
        agent_list = char_data.get("agent", [])
        patient_list = char_data.get("patient", [])
        poss_list = char_data.get("poss", char_data.get("possessions", []))
        mod_list = char_data.get("mod", char_data.get("modifiers", []))

        def _extract_words(items: list[Any]) -> list[str]:
            words: list[str] = []
            for item in items:
                if isinstance(item, str):
                    words.append(item)
                elif isinstance(item, dict):
                    w = item.get("w", item.get("word", item.get("text", "")))
                    if w:
                        words.append(w)
            return words

        mention_count = char_data.get("count", char_data.get("mention_count", 0))
        if mention_count == 0 and isinstance(names_data, dict):
            for category in names_data.values():
                if isinstance(category, list):
                    for entry in category:
                        if isinstance(entry, dict):
                            mention_count += entry.get("c", entry.get("count", 0))

        profile = CharacterProfile(
            coref_id=coref_id,
            name=canonical_name,
            aliases=aliases,
            gender=gender,
            agent_actions=_extract_words(agent_list),
            patient_actions=_extract_words(patient_list),
            possessions=_extract_words(poss_list),
            modifiers=_extract_words(mod_list),
            mention_count=mention_count,
        )
        characters.append(profile)
        coref_to_name[coref_id] = canonical_name

    logger.info("Parsed {} character profiles from {}", len(characters), path.name)
    return characters, coref_to_name


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_booknlp(
    full_text_path: Path,
    output_dir: Path,
    book_id: str,
    model_size: str = "small",
) -> BookNLPOutput:
    """Run BookNLP on a text file and parse all outputs into structured objects.

    Args:
        full_text_path: Path to the plain-text input file.
        output_dir: Directory where BookNLP will write its output files.
        book_id: Identifier for the book (used as BookNLP's ``book_id``).
        model_size: BookNLP model size — ``"small"`` or ``"big"``.

    Returns:
        A ``BookNLPOutput`` with all parsed data.
    """
    full_text_path = Path(full_text_path)
    output_dir = Path(output_dir)

    if not full_text_path.exists():
        raise FileNotFoundError(f"Input text file not found: {full_text_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Run BookNLP ---
    logger.info("Running BookNLP (model={}) on {} -> {}", model_size, full_text_path, output_dir)
    try:
        from booknlp.booknlp import BookNLP

        pipeline_config = "entity,quote,supersense,event,coref"
        model = BookNLP("en", {"pipeline": pipeline_config})
        model.pipeline(
            str(full_text_path),
            str(output_dir),
            book_id,
        )
        logger.info("BookNLP pipeline completed successfully")
    except ImportError:
        logger.error(
            "booknlp is not installed. Install it with: pip install booknlp"
        )
        raise
    except Exception as exc:
        logger.error("BookNLP pipeline failed: {}", exc)
        raise

    # --- Locate output files ---
    tokens_path = output_dir / f"{book_id}.tokens"
    entities_path = output_dir / f"{book_id}.entities"
    quotes_path = output_dir / f"{book_id}.quotes"
    book_path = output_dir / f"{book_id}.book"

    for p in [tokens_path, entities_path, quotes_path, book_path]:
        if not p.exists():
            logger.warning("Expected output file not found: {}", p)

    # --- Parse outputs ---
    characters, coref_to_name = _parse_book_json(book_path)
    tokens = _parse_tokens(tokens_path)
    entities = _parse_entities(entities_path)
    quotes = _parse_quotes(quotes_path, coref_to_name)

    result = BookNLPOutput(
        book_id=book_id,
        tokens=tokens,
        entities=entities,
        quotes=quotes,
        characters=characters,
    )

    # --- Log summary ---
    logger.info(
        "BookNLP output: {} tokens, {} entities, {} quotes, {} characters",
        len(tokens),
        len(entities),
        len(quotes),
        len(characters),
    )

    # --- Save parsed output as JSON ---
    parsed_output_dir = Path("data/processed") / book_id / "booknlp"
    parsed_output_dir.mkdir(parents=True, exist_ok=True)
    parsed_json_path = parsed_output_dir / "parsed_output.json"

    serializable = asdict(result)
    with open(parsed_json_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    logger.info("Saved parsed output to {}", parsed_json_path)

    return result


def parse_booknlp_outputs(output_dir: Path, book_id: str) -> BookNLPOutput:
    """Parse existing BookNLP output files without re-running the pipeline.

    Useful when BookNLP has already been run and you just need the parsed data.

    Args:
        output_dir: Directory containing BookNLP output files.
        book_id: Identifier for the book.

    Returns:
        A ``BookNLPOutput`` with all parsed data.
    """
    output_dir = Path(output_dir)
    logger.info("Parsing existing BookNLP outputs from {} (book_id={})", output_dir, book_id)

    tokens_path = output_dir / f"{book_id}.tokens"
    entities_path = output_dir / f"{book_id}.entities"
    quotes_path = output_dir / f"{book_id}.quotes"
    book_path = output_dir / f"{book_id}.book"

    characters, coref_to_name = _parse_book_json(book_path)
    tokens = _parse_tokens(tokens_path)
    entities = _parse_entities(entities_path)
    quotes = _parse_quotes(quotes_path, coref_to_name)

    result = BookNLPOutput(
        book_id=book_id,
        tokens=tokens,
        entities=entities,
        quotes=quotes,
        characters=characters,
    )

    logger.info(
        "Parsed: {} tokens, {} entities, {} quotes, {} characters",
        len(tokens),
        len(entities),
        len(quotes),
        len(characters),
    )
    return result


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    if len(sys.argv) < 2:
        logger.error("Usage: python -m pipeline.booknlp_runner <full_text.txt> [book_id] [output_dir]")
        logger.info("  Or to parse existing outputs: python -m pipeline.booknlp_runner --parse-only <output_dir> <book_id>")
        sys.exit(1)

    if sys.argv[1] == "--parse-only":
        if len(sys.argv) < 4:
            logger.error("Usage: python -m pipeline.booknlp_runner --parse-only <output_dir> <book_id>")
            sys.exit(1)
        out_dir = Path(sys.argv[2])
        bid = sys.argv[3]
        result = parse_booknlp_outputs(out_dir, bid)
    else:
        text_path = Path(sys.argv[1])
        bid = sys.argv[2] if len(sys.argv) > 2 else text_path.stem
        out_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/processed") / bid / "booknlp" / "raw"
        result = run_booknlp(text_path, out_dir, bid)

    logger.info("Done. {} tokens, {} characters, {} quotes", len(result.tokens), len(result.characters), len(result.quotes))
