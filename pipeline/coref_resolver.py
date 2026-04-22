"""
Coreference Resolution for BookRAG

Reads BookNLP annotation outputs (.tokens, .entities, .book) and produces
resolved text with parenthetical insertions like:

    "he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"

Insertion triggers:
  - Distance rule: nearest prior same-cluster mention is N+ sentences away
  - Ambiguity rule: multiple characters active in a sliding sentence window
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

from loguru import logger

from models.config import DEFAULT_DISTANCE_THRESHOLD
from pipeline.booknlp_runner import EntityMention

# ---------------------------------------------------------------------------
# Data classes — inputs
# ---------------------------------------------------------------------------

@dataclass
class Token:
    token_id: int
    sentence_id: int
    token_offset_begin: int
    token_offset_end: int
    word: str
    pos: str
    coref_id: int  # -1 if none


@dataclass
class CharacterProfile:
    coref_id: int
    name: str
    aliases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Data classes — config & outputs
# ---------------------------------------------------------------------------

@dataclass
class CorefConfig:
    distance_threshold: int = DEFAULT_DISTANCE_THRESHOLD
    ambiguity_window: int = 2
    annotate_ambiguous: bool = True


@dataclass
class ResolutionEvent:
    token_id: int
    original_text: str
    inserted_annotation: str
    rule_triggered: str  # "distance" | "ambiguity" | "both"
    sentence_id: int
    chapter: int


@dataclass
class CorefCluster:
    canonical_name: str
    mentions: list[dict] = field(default_factory=list)
    resolution_count: int = 0


@dataclass
class CorefResult:
    resolved_chapters: list[str]
    resolved_full_text: str
    clusters: dict[int, CorefCluster]
    resolution_log: list[ResolutionEvent]


# ---------------------------------------------------------------------------
# Alias selection
# ---------------------------------------------------------------------------

def _build_shortest_alias_map(
    characters: list[CharacterProfile],
) -> dict[int, str]:
    """Pick the shortest alias per character that is unique across the book.

    If a short alias (e.g. "Bob") collides with another character's alias,
    fall back to longer forms until one is unique, ultimately using the full
    canonical name.
    """
    # Collect every alias (including canonical name) per coref_id
    all_aliases: dict[int, list[str]] = {}
    for ch in characters:
        names = list(dict.fromkeys([ch.name] + ch.aliases))  # dedupe, keep order
        all_aliases[ch.coref_id] = names

    # Build a global frequency map: lowercase alias → set of coref_ids that own it
    alias_owners: dict[str, set[int]] = defaultdict(set)
    for cid, names in all_aliases.items():
        for n in names:
            alias_owners[n.lower()].add(cid)

    best: dict[int, str] = {}
    for cid, names in all_aliases.items():
        # Sort candidates shortest-first
        candidates = sorted(names, key=len)
        chosen = candidates[-1]  # default to longest (canonical name)
        for cand in candidates:
            if len(alias_owners[cand.lower()]) == 1:
                chosen = cand
                break
        best[cid] = chosen

    return best


# ---------------------------------------------------------------------------
# Mention index helpers
# ---------------------------------------------------------------------------

def _build_mention_index(
    entities: list[EntityMention],
) -> dict[int, EntityMention]:
    """Map start_token → EntityMention for fast lookup."""
    idx: dict[int, EntityMention] = {}
    for em in entities:
        idx[em.start_token] = em
    return idx



def _build_mention_end_index(
    entities: list[EntityMention],
) -> dict[int, EntityMention]:
    """Map the last token_id of each mention → EntityMention.

    Used to fire bracket annotations after the final token of a mention,
    so every token emits via tok.word (no em.text duplication).

    BookNLP uses two conventions:
    - Single-token: start_token == end_token (e.g., start=9, end=9 means token 9)
    - Multi-token: end_token is exclusive (e.g., start=3, end=5 means tokens 3,4)
    We handle both: last_tok = max(start_token, end_token - 1).
    """
    idx: dict[int, EntityMention] = {}
    for em in entities:
        last_tok = max(em.start_token, em.end_token - 1)
        idx[last_tok] = em
    return idx



# ---------------------------------------------------------------------------
# Chapter / boundary helpers
# ---------------------------------------------------------------------------

def _assign_token_chapters(
    tokens: list[Token],
    chapter_boundaries: list[tuple[int, int]],
) -> dict[int, int]:
    """Map token_id → chapter index (0-based).

    chapter_boundaries is a list of (start_token_id, end_token_id) pairs.
    """
    tok_to_chap: dict[int, int] = {}
    for chap_idx, (cb_start, cb_end) in enumerate(chapter_boundaries):
        for tok in tokens:
            if cb_start <= tok.token_id < cb_end:
                tok_to_chap[tok.token_id] = chap_idx
    # Fast path: if boundaries cover every token sequentially, the above is
    # fine.  For tokens not in any boundary, assign -1.
    return tok_to_chap


def _assign_token_chapters_fast(
    tokens: list[Token],
    chapter_boundaries: list[tuple[int, int]],
) -> dict[int, int]:
    """O(n) assignment using sorted boundaries."""
    tok_to_chap: dict[int, int] = {}
    if not chapter_boundaries:
        # Single chapter spanning all tokens
        for tok in tokens:
            tok_to_chap[tok.token_id] = 0
        return tok_to_chap

    # Sort boundaries by start
    sorted_bounds = sorted(enumerate(chapter_boundaries), key=lambda x: x[1][0])
    bi = 0
    for tok in tokens:
        while bi < len(sorted_bounds) - 1 and tok.token_id >= sorted_bounds[bi + 1][1][0]:
            bi += 1
        chap_idx, (cb_start, cb_end) = sorted_bounds[bi]
        if cb_start <= tok.token_id < cb_end:
            tok_to_chap[tok.token_id] = chap_idx
        else:
            tok_to_chap[tok.token_id] = -1
    return tok_to_chap


# ---------------------------------------------------------------------------
# Core resolution engine
# ---------------------------------------------------------------------------

def resolve_coreferences(
    tokens: list[Token],
    entities: list[EntityMention],
    characters: list[CharacterProfile],
    chapter_texts: list[str],
    chapter_boundaries: list[tuple[int, int]],
    config: CorefConfig | None = None,
    source_text: str | None = None,
) -> CorefResult:
    """Produce resolved text with parenthetical coreference annotations.

    Parameters
    ----------
    tokens : list[Token]
        Every token from the .tokens file, in order.
    entities : list[EntityMention]
        Entity mentions from the .entities file.
    characters : list[CharacterProfile]
        Character (and entity) profiles from the .book file.
    chapter_texts : list[str]
        Original chapter text strings (used only for logging / fallback).
    chapter_boundaries : list[tuple[int, int]]
        (start_token_id, end_token_id) per chapter.
    config : CorefConfig, optional
        Resolution configuration.
    source_text : str, optional
        Original full text that token offsets refer to.  When provided,
        whitespace between tokens is preserved exactly (including
        paragraph breaks).  Without it, a single space is used.

    Returns
    -------
    CorefResult
    """
    if config is None:
        config = CorefConfig()

    alias_map = _build_shortest_alias_map(characters)
    char_coref_ids = {ch.coref_id for ch in characters}
    mention_idx = _build_mention_index(entities)
    mention_end_idx = _build_mention_end_index(entities)
    tok_to_chap = _assign_token_chapters_fast(tokens, chapter_boundaries)

    num_chapters = len(chapter_boundaries) if chapter_boundaries else 1

    # Tracking state
    last_mention_sentence: dict[int, int] = {}  # coref_id → last sentence_id seen
    clusters: dict[int, CorefCluster] = {}
    resolution_log: list[ResolutionEvent] = []

    # Initialise clusters from characters
    for ch in characters:
        clusters[ch.coref_id] = CorefCluster(canonical_name=ch.name)

    # Pre-map token_id → Token for quick access (must come before sentence_clusters)
    token_map: dict[int, Token] = {t.token_id: t for t in tokens}

    # Build sentence → set of coref_ids present (for ambiguity detection)
    sentence_clusters: dict[int, set[int]] = defaultdict(set)
    for em in entities:
        if em.coref_id < 0:
            continue
        tok = token_map.get(em.start_token)
        if tok:
            sentence_clusters[tok.sentence_id].add(em.coref_id)

    def _active_clusters_in_window(sentence_id: int) -> set[int]:
        """Return coref_ids of characters active in the ambiguity window
        (current sentence + previous `ambiguity_window` sentences)."""
        active: set[int] = set()
        for sid in range(sentence_id - config.ambiguity_window, sentence_id + 1):
            active |= sentence_clusters.get(sid, set())
        return active

    def _should_annotate(em: EntityMention, sentence_id: int) -> str | None:
        """Determine if a mention should be annotated.

        Returns the rule name ("distance", "ambiguity", "both") or None.
        """
        # Never annotate proper nouns — they're already clear
        if em.prop == "PROP":
            return None

        cid = em.coref_id
        if cid < 0:
            return None

        # Bug 3 fix: skip all-caps multi-word mentions (headings like STAVE ONE)
        if em.text == em.text.upper() and " " in em.text.strip():
            return None

        # Must have a known canonical name
        if cid not in alias_map and cid not in clusters:
            return None

        # Bug 2 fix: skip if the resolved name is a placeholder or a pronoun
        canonical = alias_map.get(cid)
        if canonical is None:
            cl = clusters.get(cid)
            canonical = cl.canonical_name if cl else ""
        if (
            not canonical
            or canonical.startswith("CHARACTER_")
            or canonical.lower() in ("he", "she", "it", "they", "his", "her", "him")
        ):
            return None

        distance_triggered = False
        ambiguity_triggered = False

        # Distance rule
        last_sid = last_mention_sentence.get(cid)
        if last_sid is None:
            # First mention — treat as needing annotation (reader hasn't
            # seen who this pronoun refers to yet)
            distance_triggered = True
        elif sentence_id - last_sid >= config.distance_threshold:
            distance_triggered = True

        # Ambiguity rule
        if config.annotate_ambiguous:
            active = _active_clusters_in_window(sentence_id)
            # Filter to only person-like entities (PER) or keep all if
            # both are in scope — we count distinct coref_ids that are
            # character profiles.
            active_chars = {c for c in active if c in char_coref_ids}
            if len(active_chars) >= 2 and cid in active_chars:
                ambiguity_triggered = True

        if distance_triggered and ambiguity_triggered:
            return "both"
        if distance_triggered:
            return "distance"
        if ambiguity_triggered:
            return "ambiguity"
        return None

    # -----------------------------------------------------------------------
    # Walk tokens and build resolved text per chapter
    # -----------------------------------------------------------------------

    chapter_buffers: dict[int, list[str]] = defaultdict(list)
    prev_token_end: dict[int, int] = {}  # chapter → last char offset written

    # Sort tokens by token_id to ensure order
    sorted_tokens = sorted(tokens, key=lambda t: t.token_id)

    # Track which mention is "active" as we walk tokens, so we can
    # record the mention in the cluster at the start and annotate at the end.
    active_mention: EntityMention | None = None
    active_mention_sentence: int = 0

    for tok in sorted_tokens:
        chap = tok_to_chap.get(tok.token_id, 0)

        # --- Whitespace / gap before this token ---
        if chap in prev_token_end:
            gap_start = prev_token_end[chap]
            gap_end = tok.token_offset_begin
            if gap_end > gap_start:
                if source_text is not None and gap_end <= len(source_text):
                    chapter_buffers[chap].append(source_text[gap_start:gap_end])
                else:
                    chapter_buffers[chap].append(" ")
            elif gap_end < gap_start:
                chapter_buffers[chap].append(" ")

        # --- Emit this token's word (every token emits exactly once) ---
        chapter_buffers[chap].append(tok.word)
        prev_token_end[chap] = tok.token_offset_end

        # --- Check if this token STARTS a mention ---
        em_start = mention_idx.get(tok.token_id)
        if em_start is not None:
            active_mention = em_start
            active_mention_sentence = tok.sentence_id

            # Record mention in cluster
            if em_start.coref_id >= 0:
                if em_start.coref_id not in clusters:
                    clusters[em_start.coref_id] = CorefCluster(
                        canonical_name=alias_map.get(em_start.coref_id, em_start.text)
                    )
                clusters[em_start.coref_id].mentions.append({
                    "token_id": tok.token_id,
                    "text": em_start.text,
                    "sentence_id": active_mention_sentence,
                    "prop": em_start.prop,
                    "cat": em_start.cat,
                    "chapter": chap,
                })

        # --- Check if this token ENDS a mention → append [Name] ---
        em_end = mention_end_idx.get(tok.token_id)
        if em_end is not None and em_end.coref_id >= 0:
            # Use the sentence_id from when this mention started
            sid = active_mention_sentence if active_mention is em_end else tok.sentence_id

            rule = _should_annotate(em_end, sid)
            if rule is not None:
                canonical = alias_map.get(em_end.coref_id)
                if canonical is None:
                    canonical = clusters[em_end.coref_id].canonical_name

                # Don't annotate if mention text already matches the label
                if em_end.text.lower().strip() != canonical.lower().strip():
                    chapter_buffers[chap].append(f" [{canonical}]")

                    clusters[em_end.coref_id].resolution_count += 1
                    resolution_log.append(ResolutionEvent(
                        token_id=em_end.start_token,
                        original_text=em_end.text,
                        inserted_annotation=canonical,
                        rule_triggered=rule,
                        sentence_id=sid,
                        chapter=chap,
                    ))

            # Update last-seen sentence for this cluster
            last_mention_sentence[em_end.coref_id] = sid

            # Clear active mention
            if active_mention is em_end:
                active_mention = None

    # -----------------------------------------------------------------------
    # Assemble chapter strings
    # -----------------------------------------------------------------------

    resolved_chapters: list[str] = []
    for ci in range(num_chapters):
        text = "".join(chapter_buffers.get(ci, []))
        resolved_chapters.append(text)

    resolved_full = "\n\n".join(resolved_chapters)

    result = CorefResult(
        resolved_chapters=resolved_chapters,
        resolved_full_text=resolved_full,
        clusters=clusters,
        resolution_log=resolution_log,
    )

    # Logging summary
    total_insertions = len(resolution_log)
    rule_counts = defaultdict(int)
    for ev in resolution_log:
        rule_counts[ev.rule_triggered] += 1

    logger.info(f"Coreference resolution complete: {total_insertions} insertions")
    logger.info(f"  Rule breakdown: {dict(rule_counts)}")
    logger.info(f"  Clusters: {len(clusters)}")
    for cid, cl in clusters.items():
        logger.debug(
            f"  Cluster {cid} ({cl.canonical_name}): "
            f"{len(cl.mentions)} mentions, {cl.resolution_count} resolved"
        )
    for ci in range(num_chapters):
        chap_count = sum(1 for ev in resolution_log if ev.chapter == ci)
        logger.info(f"  Chapter {ci + 1}: {chap_count} insertions")

    return result


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_coref_outputs(
    result: CorefResult,
    book_id: str,
    base_dir: str | Path = "data/processed",
) -> None:
    """Write resolution artifacts to disk.

    Output structure:
        {base_dir}/{book_id}/coref/clusters.json
        {base_dir}/{book_id}/coref/resolution_log.json
        {base_dir}/{book_id}/resolved/chapters/chapter_01.txt ...
        {base_dir}/{book_id}/resolved/full_text_resolved.txt
    """
    base = Path(base_dir) / book_id

    coref_dir = base / "coref"
    coref_dir.mkdir(parents=True, exist_ok=True)

    resolved_dir = base / "resolved"
    chapters_dir = resolved_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    # clusters.json
    clusters_out = {}
    for cid, cl in result.clusters.items():
        clusters_out[str(cid)] = {
            "canonical_name": cl.canonical_name,
            "mention_count": len(cl.mentions),
            "resolution_count": cl.resolution_count,
            "mentions": cl.mentions,
        }
    (coref_dir / "clusters.json").write_text(
        json.dumps(clusters_out, indent=2, ensure_ascii=False)
    )
    logger.info(f"Saved clusters → {coref_dir / 'clusters.json'}")

    # resolution_log.json
    log_out = [asdict(ev) for ev in result.resolution_log]
    (coref_dir / "resolution_log.json").write_text(
        json.dumps(log_out, indent=2, ensure_ascii=False)
    )
    logger.info(f"Saved resolution log → {coref_dir / 'resolution_log.json'}")

    # Per-chapter resolved text
    for ci, chapter_text in enumerate(result.resolved_chapters):
        fname = f"chapter_{ci + 1:02d}.txt"
        (chapters_dir / fname).write_text(chapter_text, encoding="utf-8")
    logger.info(f"Saved {len(result.resolved_chapters)} chapter files → {chapters_dir}")

    # Full resolved text
    full_path = resolved_dir / "full_text_resolved.txt"
    full_path.write_text(result.resolved_full_text, encoding="utf-8")
    logger.info(f"Saved full resolved text → {full_path}")


# ---------------------------------------------------------------------------
# Demo / __main__
# ---------------------------------------------------------------------------

def _build_demo_data() -> tuple[
    list[Token],
    list[EntityMention],
    list[CharacterProfile],
    list[str],
    list[tuple[int, int]],
]:
    """Build a small *A Christmas Carol* excerpt for demonstration."""

    # Original text (conceptual):
    #   Sentence 0: "Scrooge sat in his counting-house."
    #   Sentence 1: "The door was open."
    #   Sentence 2: "Bob Cratchit worked nearby."
    #   Sentence 3: "He muttered to his clerk about the cold."
    #
    # In sentence 3, "He" and "his" refer to Scrooge (coref 1),
    # "clerk" refers to Bob Cratchit (coref 2).
    # Ambiguity rule fires because both Scrooge(1) and Bob(2) are active.

    tokens = [
        # Sentence 0
        Token(0, 0, 0, 7, "Scrooge", "NNP", 1),
        Token(1, 0, 8, 11, "sat", "VBD", -1),
        Token(2, 0, 12, 14, "in", "IN", -1),
        Token(3, 0, 15, 18, "his", "PRP$", 1),
        Token(4, 0, 19, 33, "counting-house", "NN", -1),
        Token(5, 0, 33, 34, ".", ".", -1),
        # Sentence 1
        Token(6, 1, 35, 38, "The", "DT", -1),
        Token(7, 1, 39, 43, "door", "NN", -1),
        Token(8, 1, 44, 47, "was", "VBD", -1),
        Token(9, 1, 48, 52, "open", "JJ", -1),
        Token(10, 1, 52, 53, ".", ".", -1),
        # Sentence 2
        Token(11, 2, 54, 57, "Bob", "NNP", 2),
        Token(12, 2, 58, 65, "Cratchit", "NNP", 2),
        Token(13, 2, 66, 72, "worked", "VBD", -1),
        Token(14, 2, 73, 79, "nearby", "RB", -1),
        Token(15, 2, 79, 80, ".", ".", -1),
        # Sentence 3
        Token(16, 3, 81, 83, "He", "PRP", 1),
        Token(17, 3, 84, 92, "muttered", "VBD", -1),
        Token(18, 3, 93, 95, "to", "TO", -1),
        Token(19, 3, 96, 99, "his", "PRP$", 1),
        Token(20, 3, 100, 105, "clerk", "NN", 2),
        Token(21, 3, 106, 111, "about", "IN", -1),
        Token(22, 3, 112, 115, "the", "DT", -1),
        Token(23, 3, 116, 120, "cold", "NN", -1),
        Token(24, 3, 120, 121, ".", ".", -1),
    ]

    entities = [
        EntityMention(1, 0, 1, "PROP", "PER", "Scrooge"),
        EntityMention(1, 3, 4, "PRON", "PER", "his"),
        EntityMention(2, 11, 13, "PROP", "PER", "Bob Cratchit"),
        EntityMention(1, 16, 17, "PRON", "PER", "He"),
        EntityMention(1, 19, 20, "PRON", "PER", "his"),
        EntityMention(2, 20, 21, "NOM", "PER", "clerk"),
    ]

    characters = [
        CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge", "Mr. Scrooge", "Ebenezer"]),
        CharacterProfile(2, "Bob Cratchit", ["Bob", "Cratchit", "Bob Cratchit"]),
    ]

    chapter_texts = [
        "Scrooge sat in his counting-house. The door was open. "
        "Bob Cratchit worked nearby. He muttered to his clerk about the cold."
    ]

    chapter_boundaries = [(0, 25)]

    return tokens, entities, characters, chapter_texts, chapter_boundaries


def main() -> None:
    tokens, entities, characters, chapter_texts, chapter_boundaries = _build_demo_data()

    config = CorefConfig(distance_threshold=DEFAULT_DISTANCE_THRESHOLD, ambiguity_window=2, annotate_ambiguous=True)

    result = resolve_coreferences(
        tokens=tokens,
        entities=entities,
        characters=characters,
        chapter_texts=chapter_texts,
        chapter_boundaries=chapter_boundaries,
        config=config,
    )

    logger.info("\n" + "=" * 70)
    logger.info("RESOLVED TEXT")
    logger.info("=" * 70)
    logger.info(result.resolved_full_text)
    logger.info("=" * 70)

    logger.info(f"\nTotal insertions: {len(result.resolution_log)}")
    for ev in result.resolution_log:
        logger.info(
            f"  token {ev.token_id}: \"{ev.original_text}\" → "
            f"[{ev.inserted_annotation}]  (rule: {ev.rule_triggered})"
        )

    logger.info("\nCluster summary:")
    for cid, cl in result.clusters.items():
        logger.info(
            f"  [{cid}] {cl.canonical_name}: "
            f"{len(cl.mentions)} mentions, {cl.resolution_count} annotated"
        )

    # Save to disk
    save_coref_outputs(result, book_id="christmas_carol_demo")
    logger.info("\nOutputs saved to data/processed/christmas_carol_demo/")


if __name__ == "__main__":
    main()
