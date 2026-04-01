"""
Ontology discovery from BookNLP output + full text.

Extracts entity types, runs BERTopic for latent themes, TF-IDF for domain terms,
and generates an OWL ontology file using RDFLib.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
from sklearn.feature_extraction.text import TfidfVectorizer

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class OntologyResult:
    """Return value of discover_ontology()."""

    discovered_entities: dict[str, list[dict]]  # type -> [{name, count, ...}]
    discovered_themes: list[dict]                # [{topic_id, label, keywords}]
    discovered_relations: list[dict]             # [{name, source, evidence}]
    owl_path: Path = field(default_factory=lambda: Path())


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "min_entity_frequency": 2,
    "num_topics": 20,
    "num_tfidf_terms": 100,
}

# Namespace for our book ontology
BOOK = Namespace("http://bookrag.local/ontology#")

# Base entity classes that always exist in the ontology
BASE_ENTITY_CLASSES = ["Character", "Location", "Faction", "Organization", "Object"]

# Map BookNLP entity categories to our ontology classes
BOOKNLP_CAT_MAP = {
    "PER": "Character",
    "LOC": "Location",
    "FAC": "Location",   # facilities are a subtype of location
    "GPE": "Location",   # geo-political entities map to location
    "VEH": "Object",
    "ORG": "Organization",
}


# ---------------------------------------------------------------------------
# Step 1 — Extract entities from BookNLP
# ---------------------------------------------------------------------------

def _extract_entities_from_booknlp(booknlp_output: dict) -> dict[str, list[dict]]:
    """
    Parse the BookNLP .book JSON (character profiles) and .entities TSV data
    to discover entity types with frequency counts.

    booknlp_output should contain:
      - "book_json": parsed .book JSON (list of character dicts)
      - "entities_tsv": list of dicts from .entities TSV rows
    """
    entity_counts: dict[str, Counter] = {cls: Counter() for cls in BASE_ENTITY_CLASSES}

    # --- Character profiles from .book JSON ---
    book_json = booknlp_output.get("book_json", {})
    characters = book_json.get("characters", [])
    for char in characters:
        # Use the most frequent proper name as the canonical name
        names = char.get("names", {})
        if names:
            # names is {name_text: count, ...} or a list depending on BookNLP version
            if isinstance(names, dict):
                canonical = max(names, key=names.get)
                count = names[canonical]
            elif isinstance(names, list) and names:
                if isinstance(names[0], dict):
                    # Pick the name with highest count
                    best = max(names, key=lambda n: n.get("c", 1))
                    canonical = best.get("n", "UNKNOWN")
                    count = best.get("c", 1)
                else:
                    canonical = str(names[0])
                    count = 1
            else:
                continue
            entity_counts["Character"][canonical] += count

        # Agent actions are useful later for relationship extraction
        # but we just track character existence here

    # --- Entity mentions from .entities TSV ---
    entities_rows = booknlp_output.get("entities_tsv", [])
    for row in entities_rows:
        cat = row.get("cat", "")
        text = row.get("text", "").strip()
        prop = row.get("prop", "")
        if not text or not cat:
            continue
        # Skip pronouns — they add noise ("he", "she" as Character instances)
        if prop == "PRON":
            continue
        target_class = BOOKNLP_CAT_MAP.get(cat)
        if target_class:
            entity_counts[target_class][text] += 1

    # Convert to output format
    result: dict[str, list[dict]] = {}
    for cls, counter in entity_counts.items():
        items = [{"name": name, "count": count} for name, count in counter.most_common()]
        if items:
            result[cls] = items

    logger.info("Extracted entities: {}", {k: len(v) for k, v in result.items()})
    return result


# ---------------------------------------------------------------------------
# Step 2 — BERTopic theme discovery
# ---------------------------------------------------------------------------

def _discover_themes_bertopic(full_text: str, num_topics: int) -> list[dict]:
    """
    Run BERTopic on the full text split into paragraphs to discover latent themes.
    Returns a list of topic dicts: {topic_id, label, keywords}.
    """
    try:
        from bertopic import BERTopic
    except ImportError:
        logger.warning("bertopic not installed — skipping theme discovery")
        return []

    # Split text into paragraph-level documents for BERTopic
    paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 50]

    if len(paragraphs) < 10:
        logger.warning(
            "Only {} paragraphs found — too few for BERTopic, skipping themes",
            len(paragraphs),
        )
        return []

    logger.info("Running BERTopic on {} paragraphs (requesting {} topics)...", len(paragraphs), num_topics)

    try:
        topic_model = BERTopic(nr_topics=num_topics, verbose=False)
        topics, _probs = topic_model.fit_transform(paragraphs)
    except Exception as exc:
        logger.warning("BERTopic failed (small corpus?): {}", exc)
        return []

    # Extract topic info
    topic_info = topic_model.get_topic_info()
    discovered_themes: list[dict] = []

    for _, row in topic_info.iterrows():
        topic_id = row["Topic"]
        if topic_id == -1:
            continue  # outlier topic
        topic_words = topic_model.get_topic(topic_id)
        if not topic_words:
            continue
        keywords = [w for w, _ in topic_words[:10]]
        # Create a readable label from top 3 keywords
        label = "_".join(keywords[:3])
        discovered_themes.append({
            "topic_id": int(topic_id),
            "label": label,
            "keywords": keywords,
        })

    logger.info("BERTopic discovered {} themes", len(discovered_themes))
    return discovered_themes


# ---------------------------------------------------------------------------
# Step 3 — TF-IDF for domain terms and relation candidates
# ---------------------------------------------------------------------------

def _extract_tfidf_terms(full_text: str, num_terms: int) -> list[str]:
    """
    Run TF-IDF on the full text to find domain-specific terminology.
    Returns the top N terms by TF-IDF score.
    """
    # Split into chunks for TF-IDF (paragraphs work well)
    chunks = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 30]
    if not chunks:
        logger.warning("No text chunks for TF-IDF")
        return []

    vectorizer = TfidfVectorizer(
        max_features=num_terms * 3,  # overshoot then filter
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(chunks)
    except ValueError as exc:
        logger.warning("TF-IDF failed: {}", exc)
        return []

    feature_names = vectorizer.get_feature_names_out()
    # Sum TF-IDF scores across all chunks
    scores = tfidf_matrix.sum(axis=0).A1
    ranked_indices = scores.argsort()[::-1]

    top_terms = [str(feature_names[i]) for i in ranked_indices[:num_terms]]
    logger.info("TF-IDF extracted {} domain terms", len(top_terms))
    return top_terms


# ---------------------------------------------------------------------------
# Step 4 — Infer relationship types
# ---------------------------------------------------------------------------

# Verbs that commonly indicate relationships in literature
_RELATION_VERBS = {
    "loves", "hates", "fights", "kills", "betrays", "employs", "serves",
    "marries", "befriends", "commands", "follows", "teaches", "mentors",
    "protects", "rescues", "captures", "imprisons", "banishes", "helps",
    "trusts", "fears", "opposes", "allies_with", "rules", "obeys",
    "attacks", "defends", "leads", "joins", "leaves", "visits",
}


def _infer_relations(
    booknlp_output: dict, tfidf_terms: list[str]
) -> list[dict]:
    """
    Infer candidate relationship types from:
    1. Character agent_actions in the BookNLP .book JSON
    2. TF-IDF terms that look like verbs/relations
    """
    relations: list[dict] = []
    seen: set[str] = set()

    # --- From BookNLP character actions ---
    book_json = booknlp_output.get("book_json", {})
    characters = book_json.get("characters", [])
    action_counter: Counter = Counter()

    for char in characters:
        agent_actions = char.get("agent", [])
        if isinstance(agent_actions, list):
            for action in agent_actions:
                if isinstance(action, dict):
                    verb = action.get("w", "")
                    freq = action.get("c", 1)
                else:
                    verb = str(action)
                    freq = 1
                verb = verb.lower().strip()
                if verb and len(verb) > 2:
                    action_counter[verb] += freq

    for verb, count in action_counter.most_common(50):
        rel_name = verb.replace(" ", "_")
        if rel_name not in seen:
            seen.add(rel_name)
            relations.append({
                "name": rel_name,
                "source": "booknlp_agent_actions",
                "evidence": f"appears {count} times as character action",
            })

    # --- From TF-IDF terms that look like relations ---
    for term in tfidf_terms:
        term_lower = term.lower().strip()
        # Check if it matches known relation patterns or is a single verb-like word
        if term_lower in _RELATION_VERBS:
            if term_lower not in seen:
                seen.add(term_lower)
                relations.append({
                    "name": term_lower,
                    "source": "tfidf_relation_verb",
                    "evidence": "high TF-IDF score, matches relation vocabulary",
                })
        # Also check two-word terms that look relational (e.g., "works for")
        elif " " in term_lower:
            parts = term_lower.split()
            if len(parts) == 2 and parts[0] in _RELATION_VERBS:
                rel = "_".join(parts)
                if rel not in seen:
                    seen.add(rel)
                    relations.append({
                        "name": rel,
                        "source": "tfidf_bigram",
                        "evidence": f"TF-IDF bigram: '{term}'",
                    })

    logger.info("Inferred {} candidate relationship types", len(relations))
    return relations


# ---------------------------------------------------------------------------
# Step 5 — Build OWL ontology with RDFLib
# ---------------------------------------------------------------------------

def _build_owl(
    entities: dict[str, list[dict]],
    themes: list[dict],
    relations: list[dict],
    owl_path: Path,
    min_entity_frequency: int,
) -> None:
    """Build an OWL ontology file from the discovered entities, themes, and relations."""
    g = Graph()
    g.bind("book", BOOK)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Declare the ontology
    ontology_uri = URIRef(str(BOOK).rstrip("#"))
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.label, Literal("Book Ontology")))

    # --- Root class: BookEntity ---
    book_entity = BOOK.BookEntity
    g.add((book_entity, RDF.type, OWL.Class))
    g.add((book_entity, RDFS.label, Literal("BookEntity")))

    # --- Base entity classes as subclasses of BookEntity ---
    # Include both the fixed base classes AND any custom types from the entities dict
    # (custom types can be added during ontology review)
    all_entity_classes = set(BASE_ENTITY_CLASSES) | set(entities.keys())
    for cls_name in sorted(all_entity_classes):
        cls_uri = BOOK[cls_name]
        g.add((cls_uri, RDF.type, OWL.Class))
        g.add((cls_uri, RDFS.subClassOf, book_entity))
        g.add((cls_uri, RDFS.label, Literal(cls_name)))

    # --- Add discovered entity instances as OWL NamedIndividuals ---
    for cls_name, items in entities.items():
        cls_uri = BOOK[cls_name]
        for item in items:
            if item["count"] < min_entity_frequency:
                continue
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", item["name"])
            individual = BOOK[safe_name]
            g.add((individual, RDF.type, OWL.NamedIndividual))
            g.add((individual, RDF.type, cls_uri))
            g.add((individual, RDFS.label, Literal(item["name"])))

    # --- Theme classes from BERTopic ---
    theme_root = BOOK.Theme
    g.add((theme_root, RDF.type, OWL.Class))
    g.add((theme_root, RDFS.subClassOf, book_entity))
    g.add((theme_root, RDFS.label, Literal("Theme")))

    for theme in themes:
        safe_label = re.sub(r"[^a-zA-Z0-9_]", "_", theme["label"])
        theme_uri = BOOK[f"Theme_{safe_label}"]
        g.add((theme_uri, RDF.type, OWL.Class))
        g.add((theme_uri, RDFS.subClassOf, theme_root))
        g.add((theme_uri, RDFS.label, Literal(theme["label"])))
        g.add((theme_uri, RDFS.comment, Literal(", ".join(theme["keywords"]))))

    # --- Relationship types as OWL ObjectProperties ---
    for rel in relations:
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", rel["name"])
        prop_uri = BOOK[safe_name]
        g.add((prop_uri, RDF.type, OWL.ObjectProperty))
        g.add((prop_uri, RDFS.label, Literal(rel["name"])))
        g.add((prop_uri, RDFS.comment, Literal(rel.get("evidence", ""))))
        # Domain and range default to BookEntity (characters can relate to anything)
        g.add((prop_uri, RDFS.domain, book_entity))
        g.add((prop_uri, RDFS.range, book_entity))

    # --- PlotEvent as a class (always present) ---
    plot_event = BOOK.PlotEvent
    g.add((plot_event, RDF.type, OWL.Class))
    g.add((plot_event, RDFS.subClassOf, book_entity))
    g.add((plot_event, RDFS.label, Literal("PlotEvent")))

    # --- Relationship DataPoint class ---
    relationship_cls = BOOK.Relationship
    g.add((relationship_cls, RDF.type, OWL.Class))
    g.add((relationship_cls, RDFS.subClassOf, book_entity))
    g.add((relationship_cls, RDFS.label, Literal("Relationship")))

    # Serialize
    owl_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(owl_path), format="xml")
    logger.info("OWL ontology written to {}", owl_path)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def discover_ontology(
    booknlp_output: dict,
    full_text: str,
    book_id: str,
    config: dict | None = None,
) -> OntologyResult:
    """
    Discover an ontology from BookNLP structured output and the full book text.

    Args:
        booknlp_output: Dict with keys "book_json" (parsed .book JSON) and
                        "entities_tsv" (list of entity row dicts from .entities).
        full_text: The full (optionally coref-resolved) book text.
        book_id: Identifier for this book (e.g. "christmas_carol").
        config: Optional overrides for min_entity_frequency, num_topics, num_tfidf_terms.

    Returns:
        OntologyResult with discovered entities, themes, relations, and path to OWL file.
    """
    cfg = {**_DEFAULT_CONFIG, **(config or {})}
    min_freq = cfg["min_entity_frequency"]
    num_topics = cfg["num_topics"]
    num_tfidf = cfg["num_tfidf_terms"]

    output_dir = Path(f"data/processed/{book_id}/ontology")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Ontology Discovery for '{}' ===", book_id)

    # Step 1: Extract entities from BookNLP
    logger.info("Step 1: Extracting entities from BookNLP output...")
    entities = _extract_entities_from_booknlp(booknlp_output)

    # Step 2: Discover themes via BERTopic
    logger.info("Step 2: Running BERTopic for theme discovery...")
    themes = _discover_themes_bertopic(full_text, num_topics)

    # Step 3: TF-IDF for domain terms
    logger.info("Step 3: Running TF-IDF for domain terminology...")
    tfidf_terms = _extract_tfidf_terms(full_text, num_tfidf)

    # Step 4: Infer relationship types
    logger.info("Step 4: Inferring relationship types...")
    relations = _infer_relations(booknlp_output, tfidf_terms)

    # Save discovered entities JSON
    discovery_output = {
        "book_id": book_id,
        "entities": entities,
        "themes": themes,
        "relations": relations,
        "tfidf_top_terms": tfidf_terms[:30],  # save a sample for review
        "config": cfg,
    }
    entities_path = output_dir / "discovered_entities.json"
    entities_path.write_text(json.dumps(discovery_output, indent=2, ensure_ascii=False))
    logger.info("Saved discovery output to {}", entities_path)

    # Step 5: Build OWL
    logger.info("Step 5: Building OWL ontology...")
    owl_path = output_dir / "book_ontology.owl"
    _build_owl(entities, themes, relations, owl_path, min_freq)

    result = OntologyResult(
        discovered_entities=entities,
        discovered_themes=themes,
        discovered_relations=relations,
        owl_path=owl_path,
    )

    logger.info("=== Ontology Discovery complete ===")
    return result
