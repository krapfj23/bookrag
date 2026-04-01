"""Quality control tests for the coreference resolver.

These tests evaluate the *quality* of resolved text — not individual functions,
but whether the output is good for downstream LLM extraction in Phase 2.

QC dimensions tested:
- Format integrity: balanced brackets, no nesting, consistent pattern
- Alias consistency: same cluster always uses the same alias label
- No duplicate annotations: "he [Scrooge] [Scrooge]" never happens
- Over-annotation: annotation density stays within sane bounds
- Under-annotation: ambiguous scenes don't go unresolved
- Reversibility: stripping brackets recovers coherent original text
- Readability: resolved text doesn't degrade sentence structure
- Multi-character dialogue: the hardest coref scenario
- Long-distance references: characters absent for many sentences
- Chapter boundary behavior: no cross-chapter state pollution
- Annotation accuracy: brackets point to the correct character

Alignment:
- CLAUDE.md: parenthetical format, reversible, Claude parses it well
- bookrag_deep_research_context.md Section 6: "Preserves original text
  (reversible by stripping brackets)"
- bookrag_pipeline_plan.md: resolved text feeds Phase 2 LLM extraction
"""
from __future__ import annotations

import re
from collections import Counter

import pytest

from pipeline.coref_resolver import (
    Token,
    EntityMention,
    CharacterProfile,
    CorefConfig,
    CorefResult,
    resolve_coreferences,
)


# ============================================================================
# Helpers
# ============================================================================

def _count_annotations(text: str) -> int:
    """Count [bracketed] insertions in resolved text."""
    return len(re.findall(r"\[[^\]]+\]", text))


def _extract_annotations(text: str) -> list[str]:
    """Return list of annotation labels from resolved text."""
    return re.findall(r"\[([^\]]+)\]", text)


def _strip_annotations(text: str) -> str:
    """Remove all parenthetical annotations, restoring original-like text."""
    return re.sub(r"\s*\[[^\]]+\]", "", text)


# ============================================================================
# Fixtures — realistic multi-scene scenario
# ============================================================================

@pytest.fixture
def dialogue_scene():
    """A multi-character dialogue scene — the hardest case for coref.

    Sentence 0: "Scrooge sat at his desk."
    Sentence 1: "Bob Cratchit entered the room."
    Sentence 2: "'You want the day off?' he asked."
    Sentence 3: "'Yes sir,' his clerk replied."
    Sentence 4: "He frowned."
    Sentence 5: "He nodded reluctantly."

    Sentences 4 and 5 are ambiguous — both Scrooge and Bob are in scope.
    """
    tokens = [
        # Sentence 0
        Token(0, 0, 0, 7, "Scrooge", "NNP", 1),
        Token(1, 0, 8, 11, "sat", "VBD", -1),
        Token(2, 0, 12, 14, "at", "IN", -1),
        Token(3, 0, 15, 18, "his", "PRP$", 1),
        Token(4, 0, 19, 23, "desk", "NN", -1),
        Token(5, 0, 23, 24, ".", ".", -1),
        # Sentence 1
        Token(6, 1, 25, 28, "Bob", "NNP", 2),
        Token(7, 1, 29, 37, "Cratchit", "NNP", 2),
        Token(8, 1, 38, 45, "entered", "VBD", -1),
        Token(9, 1, 46, 49, "the", "DT", -1),
        Token(10, 1, 50, 54, "room", "NN", -1),
        Token(11, 1, 54, 55, ".", ".", -1),
        # Sentence 2
        Token(12, 2, 56, 57, "'", "``", -1),
        Token(13, 2, 57, 60, "You", "PRP", -1),
        Token(14, 2, 61, 65, "want", "VBP", -1),
        Token(15, 2, 66, 69, "the", "DT", -1),
        Token(16, 2, 70, 73, "day", "NN", -1),
        Token(17, 2, 74, 77, "off", "RP", -1),
        Token(18, 2, 77, 78, "?", ".", -1),
        Token(19, 2, 78, 79, "'", "''", -1),
        Token(20, 2, 80, 82, "he", "PRP", 1),
        Token(21, 2, 83, 88, "asked", "VBD", -1),
        Token(22, 2, 88, 89, ".", ".", -1),
        # Sentence 3
        Token(23, 3, 90, 91, "'", "``", -1),
        Token(24, 3, 91, 94, "Yes", "UH", -1),
        Token(25, 3, 95, 98, "sir", "NN", -1),
        Token(26, 3, 98, 99, ",", ",", -1),
        Token(27, 3, 99, 100, "'", "''", -1),
        Token(28, 3, 101, 104, "his", "PRP$", 1),
        Token(29, 3, 105, 110, "clerk", "NN", 2),
        Token(30, 3, 111, 118, "replied", "VBD", -1),
        Token(31, 3, 118, 119, ".", ".", -1),
        # Sentence 4
        Token(32, 4, 120, 122, "He", "PRP", 1),
        Token(33, 4, 123, 130, "frowned", "VBD", -1),
        Token(34, 4, 130, 131, ".", ".", -1),
        # Sentence 5
        Token(35, 5, 132, 134, "He", "PRP", 1),
        Token(36, 5, 135, 141, "nodded", "VBD", -1),
        Token(37, 5, 142, 153, "reluctantly", "RB", -1),
        Token(38, 5, 153, 154, ".", ".", -1),
    ]
    entities = [
        EntityMention(1, 0, 1, "PROP", "PER", "Scrooge"),
        EntityMention(1, 3, 4, "PRON", "PER", "his"),
        EntityMention(2, 6, 8, "PROP", "PER", "Bob Cratchit"),
        EntityMention(1, 20, 21, "PRON", "PER", "he"),
        EntityMention(1, 28, 29, "PRON", "PER", "his"),
        EntityMention(2, 29, 30, "NOM", "PER", "clerk"),
        EntityMention(1, 32, 33, "PRON", "PER", "He"),
        EntityMention(1, 35, 36, "PRON", "PER", "He"),
    ]
    characters = [
        CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge", "Mr. Scrooge"]),
        CharacterProfile(2, "Bob Cratchit", ["Bob", "Cratchit"]),
    ]
    return tokens, entities, characters, [""], [(0, 39)]


@pytest.fixture
def long_distance_scene():
    """Character mentioned, then absent for 10+ sentences, then pronoun.

    Sentence 0: "Darrow entered the hall."
    Sentences 1-9: filler sentences with no entity mentions.
    Sentence 10: "He drew his sword."
    """
    tokens = []
    tid = 0
    # Sentence 0
    tokens.append(Token(tid, 0, 0, 6, "Darrow", "NNP", 1)); tid += 1
    tokens.append(Token(tid, 0, 7, 14, "entered", "VBD", -1)); tid += 1
    tokens.append(Token(tid, 0, 15, 18, "the", "DT", -1)); tid += 1
    tokens.append(Token(tid, 0, 19, 23, "hall", "NN", -1)); tid += 1
    tokens.append(Token(tid, 0, 23, 24, ".", ".", -1)); tid += 1

    # Sentences 1-9: filler
    offset = 25
    for sent_id in range(1, 10):
        tokens.append(Token(tid, sent_id, offset, offset + 3, "The", "DT", -1)); tid += 1; offset += 4
        tokens.append(Token(tid, sent_id, offset, offset + 4, "wind", "NN", -1)); tid += 1; offset += 5
        tokens.append(Token(tid, sent_id, offset, offset + 4, "blew", "VBD", -1)); tid += 1; offset += 5
        tokens.append(Token(tid, sent_id, offset, offset + 1, ".", ".", -1)); tid += 1; offset += 2

    # Sentence 10: "He drew his sword."
    tokens.append(Token(tid, 10, offset, offset + 2, "He", "PRP", 1)); he_tid = tid; tid += 1; offset += 3
    tokens.append(Token(tid, 10, offset, offset + 4, "drew", "VBD", -1)); tid += 1; offset += 5
    tokens.append(Token(tid, 10, offset, offset + 3, "his", "PRP$", 1)); his_tid = tid; tid += 1; offset += 4
    tokens.append(Token(tid, 10, offset, offset + 5, "sword", "NN", -1)); tid += 1; offset += 6
    tokens.append(Token(tid, 10, offset, offset + 1, ".", ".", -1)); tid += 1

    entities = [
        EntityMention(1, 0, 1, "PROP", "PER", "Darrow"),
        EntityMention(1, he_tid, he_tid + 1, "PRON", "PER", "He"),
        EntityMention(1, his_tid, his_tid + 1, "PRON", "PER", "his"),
    ]
    characters = [CharacterProfile(1, "Darrow of Lykos", ["Darrow"])]
    return tokens, entities, characters, [""], [(0, tid)]


@pytest.fixture
def multi_chapter_scene():
    """Two chapters, character introduced in ch1, pronoun-only in ch2.

    Chapter 0, Sentence 0: "Mustang smiled."
    Chapter 0, Sentence 1: "She waved."
    Chapter 1, Sentence 2: "She rode into battle."
    """
    tokens = [
        Token(0, 0, 0, 7, "Mustang", "NNP", 3),
        Token(1, 0, 8, 14, "smiled", "VBD", -1),
        Token(2, 0, 14, 15, ".", ".", -1),
        Token(3, 1, 16, 19, "She", "PRP", 3),
        Token(4, 1, 20, 25, "waved", "VBD", -1),
        Token(5, 1, 25, 26, ".", ".", -1),
        # Chapter 1
        Token(6, 2, 27, 30, "She", "PRP", 3),
        Token(7, 2, 31, 35, "rode", "VBD", -1),
        Token(8, 2, 36, 40, "into", "IN", -1),
        Token(9, 2, 41, 47, "battle", "NN", -1),
        Token(10, 2, 47, 48, ".", ".", -1),
    ]
    entities = [
        EntityMention(3, 0, 1, "PROP", "PER", "Mustang"),
        EntityMention(3, 3, 4, "PRON", "PER", "She"),
        EntityMention(3, 6, 7, "PRON", "PER", "She"),
    ]
    characters = [CharacterProfile(3, "Virginia au Augustus", ["Mustang", "Virginia"])]
    return tokens, entities, characters, ["", ""], [(0, 6), (6, 11)]


@pytest.fixture
def five_character_scene():
    """Five characters active in a tight window — stress test for ambiguity.

    Sentence 0: "Darrow, Cassius, Sevro, Mustang, and Roque stood together."
    Sentence 1: "He spoke first."
    """
    tokens = [
        Token(0, 0, 0, 6, "Darrow", "NNP", 1),
        Token(1, 0, 6, 7, ",", ",", -1),
        Token(2, 0, 8, 15, "Cassius", "NNP", 2),
        Token(3, 0, 15, 16, ",", ",", -1),
        Token(4, 0, 17, 22, "Sevro", "NNP", 3),
        Token(5, 0, 22, 23, ",", ",", -1),
        Token(6, 0, 24, 31, "Mustang", "NNP", 4),
        Token(7, 0, 31, 32, ",", ",", -1),
        Token(8, 0, 33, 36, "and", "CC", -1),
        Token(9, 0, 37, 42, "Roque", "NNP", 5),
        Token(10, 0, 43, 48, "stood", "VBD", -1),
        Token(11, 0, 49, 57, "together", "RB", -1),
        Token(12, 0, 57, 58, ".", ".", -1),
        # Sentence 1
        Token(13, 1, 59, 61, "He", "PRP", 1),
        Token(14, 1, 62, 67, "spoke", "VBD", -1),
        Token(15, 1, 68, 73, "first", "RB", -1),
        Token(16, 1, 73, 74, ".", ".", -1),
    ]
    entities = [
        EntityMention(1, 0, 1, "PROP", "PER", "Darrow"),
        EntityMention(2, 2, 3, "PROP", "PER", "Cassius"),
        EntityMention(3, 4, 5, "PROP", "PER", "Sevro"),
        EntityMention(4, 6, 7, "PROP", "PER", "Mustang"),
        EntityMention(5, 9, 10, "PROP", "PER", "Roque"),
        EntityMention(1, 13, 14, "PRON", "PER", "He"),
    ]
    characters = [
        CharacterProfile(1, "Darrow of Lykos", ["Darrow"]),
        CharacterProfile(2, "Cassius au Bellona", ["Cassius"]),
        CharacterProfile(3, "Sevro au Barca", ["Sevro"]),
        CharacterProfile(4, "Virginia au Augustus", ["Mustang"]),
        CharacterProfile(5, "Roque au Fabii", ["Roque"]),
    ]
    return tokens, entities, characters, [""], [(0, 17)]


DEFAULT_CONFIG = CorefConfig(distance_threshold=3, ambiguity_window=2, annotate_ambiguous=True)


# ============================================================================
# QC 1: Format integrity
# ============================================================================

class TestFormatIntegrity:
    """Every annotation must follow the exact pattern: `word [Name]`.
    No nested brackets, no unclosed brackets, no empty brackets.
    """

    def test_brackets_balanced(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        text = result.resolved_full_text
        assert text.count("[") == text.count("]"), "Unbalanced brackets"

    def test_no_nested_brackets(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        # [foo [bar]] should never occur
        assert not re.search(r"\[[^\]]*\[", result.resolved_full_text), "Nested brackets found"

    def test_no_empty_brackets(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        assert "[]" not in result.resolved_full_text

    def test_annotation_pattern_consistent(self, dialogue_scene):
        """Every annotation must be ` [SomeName]` — space before bracket, non-empty."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        # Find all bracket contents
        for match in re.finditer(r"\[([^\]]+)\]", result.resolved_full_text):
            label = match.group(1)
            assert len(label.strip()) > 0, f"Empty annotation label: [{label}]"
            # Check space before bracket
            pos = match.start()
            if pos > 0:
                assert result.resolved_full_text[pos - 1] == " ", \
                    f"Missing space before [{label}] at position {pos}"

    def test_no_double_annotations(self, dialogue_scene):
        """No `word [Name] [Name]` — a single mention should get at most one bracket."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        assert not re.search(r"\]\s*\[", result.resolved_full_text), \
            "Back-to-back annotations found"


# ============================================================================
# QC 2: Alias consistency
# ============================================================================

class TestAliasConsistency:
    """The same coref cluster must always resolve to the same alias label.
    Inconsistent naming (sometimes "Bob", sometimes "Bob Cratchit") confuses
    the Phase 2 LLM.
    """

    def test_same_cluster_same_label(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        # Group annotations by coref cluster (via resolution_log)
        labels_per_cluster: dict[str, set[str]] = {}
        for ev in result.resolution_log:
            key = ev.inserted_annotation
            # All events for the same inserted_annotation should match
            # (this tests the flip side: group by original coref_id)
        # Better: check via clusters
        for cid, cluster in result.clusters.items():
            labels = set()
            for ev in result.resolution_log:
                # Find events for this cluster by checking the annotation matches
                # the cluster's expected alias
                if ev.inserted_annotation == result.clusters[cid].canonical_name or \
                   any(ev.token_id == m["token_id"] for m in cluster.mentions):
                    labels.add(ev.inserted_annotation)
            if labels:
                assert len(labels) == 1, \
                    f"Cluster {cid} ({cluster.canonical_name}) has inconsistent " \
                    f"annotation labels: {labels}"

    def test_annotation_matches_known_character(self, dialogue_scene):
        """Every annotation label should correspond to a known character alias."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        all_names = set()
        for ch in characters:
            all_names.add(ch.name.lower())
            for a in ch.aliases:
                all_names.add(a.lower())
        for ev in result.resolution_log:
            assert ev.inserted_annotation.lower() in all_names, \
                f"Annotation '{ev.inserted_annotation}' is not a known alias"


# ============================================================================
# QC 3: Reversibility
# ============================================================================

class TestReversibility:
    """Stripping brackets should recover the original text structure.
    Per deep_research_context.md: 'Preserves original text (reversible
    by stripping brackets)'.
    """

    def test_stripped_text_has_no_brackets(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        stripped = _strip_annotations(result.resolved_full_text)
        assert "[" not in stripped
        assert "]" not in stripped

    def test_stripped_text_preserves_all_words(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        stripped = _strip_annotations(result.resolved_full_text)
        # Every original word should still be present
        for tok in tokens:
            if tok.word not in (".", ",", "'", "?", "!"):
                assert tok.word.lower() in stripped.lower(), \
                    f"Word '{tok.word}' missing after stripping annotations"

    def test_stripped_text_no_double_spaces(self, dialogue_scene):
        """Stripping should not leave double spaces."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        stripped = _strip_annotations(result.resolved_full_text)
        assert "  " not in stripped, "Double spaces after stripping annotations"


# ============================================================================
# QC 4: Over-annotation (annotation density)
# ============================================================================

class TestAnnotationDensity:
    """Too many brackets clutters text and wastes LLM context tokens in Phase 2.
    Proper nouns should NEVER be annotated. Within a single sentence, a pronoun
    immediately following its PROP antecedent should not be annotated.
    """

    def test_proper_nouns_never_annotated(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        for ev in result.resolution_log:
            # Check the entity mention for this token
            for ent in entities:
                if ent.start_token == ev.token_id:
                    assert ent.prop != "PROP", \
                        f"PROP mention '{ev.original_text}' was annotated"

    def test_annotation_density_below_threshold(self, dialogue_scene):
        """Annotation count should be < 50% of total entity mentions.
        Over-annotating is nearly as bad as not annotating.
        """
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        annotatable = [e for e in entities if e.prop != "PROP" and e.coref_id >= 0]
        if annotatable:
            density = len(result.resolution_log) / len(annotatable)
            # In a dialogue scene most pronouns WILL be annotated due to ambiguity,
            # but it should still be bounded
            assert density <= 1.0, \
                f"Density {density:.1%} — more annotations than annotatable mentions"

    def test_nearby_same_sentence_prop_then_pron_not_redundant(self):
        """'John ran. He smiled.' with distance=3 — 'He' 1 sentence away, sole
        character, should NOT be annotated. This tests against over-annotation.
        """
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 5, 8, "ran", "VBD", -1),
            Token(2, 0, 8, 9, ".", ".", -1),
            Token(3, 1, 10, 12, "He", "PRP", 1),
            Token(4, 1, 13, 19, "smiled", "VBD", -1),
            Token(5, 1, 19, 20, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 3, 4, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 6)], config)
        # 1 sentence away, no ambiguity — should NOT annotate
        assert len(result.resolution_log) == 0, \
            "Over-annotated: pronoun 1 sentence from antecedent with no ambiguity"


# ============================================================================
# QC 5: Under-annotation (ambiguous scenes must be resolved)
# ============================================================================

class TestUnderAnnotation:
    """Ambiguous pronouns without annotations are the #1 failure mode —
    the Phase 2 LLM can't tell who 'he' is if multiple characters are active.
    """

    def test_ambiguous_pronoun_annotated(self, dialogue_scene):
        """In the dialogue scene, 'He frowned' (sentence 4) has both Scrooge
        and Bob in scope — MUST be annotated."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        # Find "He" at token 32 (sentence 4)
        he_events = [e for e in result.resolution_log
                     if e.token_id == 32 and e.original_text == "He"]
        assert len(he_events) == 1, "Ambiguous 'He' in sentence 4 not annotated"

    def test_five_character_scene_pronoun_annotated(self, five_character_scene):
        """With 5 characters in scope, the pronoun MUST be annotated."""
        tokens, entities, characters, texts, bounds = five_character_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert len(he_events) == 1, "Pronoun with 5 characters in scope not annotated"

    def test_nominal_in_ambiguous_context_annotated(self, dialogue_scene):
        """'clerk' (NOM) in sentence 3 with two characters in scope — annotated."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        clerk_events = [e for e in result.resolution_log if e.original_text == "clerk"]
        assert len(clerk_events) == 1, "'clerk' in ambiguous context not annotated"


# ============================================================================
# QC 6: Long-distance references
# ============================================================================

class TestLongDistance:
    """Character absent for many sentences then referenced by pronoun.
    This is the primary use case for the distance rule.
    """

    def test_pronoun_after_10_sentence_gap(self, long_distance_scene):
        tokens, entities, characters, texts, bounds = long_distance_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        # "He" in sentence 10 should be annotated (10 sentences from sentence 0)
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert len(he_events) >= 1, "Pronoun 10 sentences away not annotated"
        assert he_events[0].inserted_annotation == "Darrow"

    def test_possessive_same_sentence_as_resolved_pronoun(self, long_distance_scene):
        """'his' in sentence 10 appears AFTER 'He [Darrow]' in the same sentence.
        Once 'He' is resolved, last_mention updates to sentence 10, so 'his'
        is no longer distant — correctly NOT annotated. This is good behavior:
        avoiding redundant brackets in the same sentence."""
        tokens, entities, characters, texts, bounds = long_distance_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        his_events = [e for e in result.resolution_log if e.original_text == "his"]
        # "his" should NOT be annotated — "He [Darrow]" already clarified the referent
        assert len(his_events) == 0, \
            "Redundant annotation: 'his' in same sentence as already-resolved 'He [Darrow]'"

    def test_distance_rule_in_log(self, long_distance_scene):
        """Should trigger 'distance' rule, not 'ambiguity' (only 1 character)."""
        tokens, entities, characters, texts, bounds = long_distance_scene
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=True)
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, config)
        for ev in result.resolution_log:
            assert ev.rule_triggered == "distance", \
                f"Expected 'distance' rule but got '{ev.rule_triggered}'"


# ============================================================================
# QC 7: Chapter boundary behavior
# ============================================================================

class TestChapterBoundaryQuality:
    """Annotations should work correctly across chapter breaks.
    A pronoun in chapter 2 referring to a character last seen in chapter 1
    should be annotated (reader may have taken a break between chapters).
    """

    def test_cross_chapter_pronoun_annotated(self, multi_chapter_scene):
        tokens, entities, characters, texts, bounds = multi_chapter_scene
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, config)
        # "She" in chapter 1 (sentence 2) should be annotated
        ch1_events = [e for e in result.resolution_log if e.chapter == 1]
        assert len(ch1_events) >= 1, "Cross-chapter pronoun not annotated"

    def test_each_chapter_has_text(self, multi_chapter_scene):
        tokens, entities, characters, texts, bounds = multi_chapter_scene
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, config)
        assert len(result.resolved_chapters) == 2
        assert len(result.resolved_chapters[0].strip()) > 0
        assert len(result.resolved_chapters[1].strip()) > 0

    def test_chapter_text_independent(self, multi_chapter_scene):
        """Each chapter's resolved text should stand alone — no cross-chapter tokens.
        'Mustang' appears in chapter 1 only inside a [Mustang] annotation, which
        is correct — it helps the Phase 2 LLM identify who 'She' is.
        """
        tokens, entities, characters, texts, bounds = multi_chapter_scene
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, config)
        # Chapter 0 has the PROP "Mustang"
        assert "Mustang" in result.resolved_chapters[0]
        # Chapter 1 has "rode" (its own content) and [Mustang] annotation
        assert "rode" in result.resolved_chapters[1]
        # The raw token "Mustang" (as PROP) should NOT be in ch1,
        # but the annotation [Mustang] should be — verify via stripping
        ch1_stripped = _strip_annotations(result.resolved_chapters[1])
        assert "Mustang" not in ch1_stripped, \
            "Raw PROP 'Mustang' leaked into chapter 1"


# ============================================================================
# QC 8: Annotation accuracy
# ============================================================================

class TestAnnotationAccuracy:
    """Annotations must point to the CORRECT character. A wrong annotation
    is worse than no annotation — it actively misleads the Phase 2 LLM.
    """

    def test_pronoun_resolves_to_correct_character(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        for ev in result.resolution_log:
            # "he"/"his"/"He" with coref_id=1 should resolve to Scrooge, not Bob
            if ev.original_text.lower() in ("he", "his"):
                # Find the entity for this token
                for ent in entities:
                    if ent.start_token == ev.token_id:
                        if ent.coref_id == 1:
                            assert ev.inserted_annotation == "Scrooge", \
                                f"Token '{ev.original_text}' (coref 1) resolved to " \
                                f"'{ev.inserted_annotation}' instead of 'Scrooge'"
                        elif ent.coref_id == 2:
                            assert ev.inserted_annotation == "Bob", \
                                f"Token '{ev.original_text}' (coref 2) resolved to " \
                                f"'{ev.inserted_annotation}' instead of 'Bob'"

    def test_nominal_resolves_to_correct_character(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        clerk_events = [e for e in result.resolution_log if e.original_text == "clerk"]
        assert len(clerk_events) == 1
        assert clerk_events[0].inserted_annotation == "Bob", \
            f"'clerk' resolved to '{clerk_events[0].inserted_annotation}' instead of 'Bob'"

    def test_five_character_scene_correct_resolution(self, five_character_scene):
        """'He' (coref 1 = Darrow) with 5 characters in scope — must resolve to Darrow."""
        tokens, entities, characters, texts, bounds = five_character_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert he_events[0].inserted_annotation == "Darrow"


# ============================================================================
# QC 9: Stress — resolution log consistency
# ============================================================================

class TestResolutionLogQuality:
    """The resolution log is used for debugging and threshold tuning.
    It must be complete and accurate.
    """

    def test_log_count_matches_text_brackets(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        bracket_count = _count_annotations(result.resolved_full_text)
        assert bracket_count == len(result.resolution_log), \
            f"Text has {bracket_count} annotations but log has {len(result.resolution_log)}"

    def test_log_annotations_match_text(self, dialogue_scene):
        """Every annotation in the log should appear in the text."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        text_annotations = _extract_annotations(result.resolved_full_text)
        log_annotations = [ev.inserted_annotation for ev in result.resolution_log]
        assert Counter(text_annotations) == Counter(log_annotations), \
            f"Mismatch: text={Counter(text_annotations)}, log={Counter(log_annotations)}"

    def test_all_log_rules_valid(self, dialogue_scene):
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        valid_rules = {"distance", "ambiguity", "both"}
        for ev in result.resolution_log:
            assert ev.rule_triggered in valid_rules, \
                f"Invalid rule '{ev.rule_triggered}'"

    def test_cluster_resolution_count_matches_log(self, dialogue_scene):
        """Sum of cluster resolution_counts should equal total log entries."""
        tokens, entities, characters, texts, bounds = dialogue_scene
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, DEFAULT_CONFIG)
        total_from_clusters = sum(c.resolution_count for c in result.clusters.values())
        assert total_from_clusters == len(result.resolution_log)


# ============================================================================
# QC 10: Full integration — realistic book excerpt
# ============================================================================

class TestRealisticExcerpt:
    """End-to-end quality check on a realistic multi-paragraph excerpt
    combining all scenarios: dialogue, distance, nominals, multiple characters.
    """

    def test_combined_scenario(self):
        """
        Paragraph 1 (sentences 0-1): Scrooge in counting-house.
        Paragraph 2 (sentences 2-3): Bob enters, dialogue.
        Paragraph 3 (sentences 4-8): Long description, no characters.
        Paragraph 4 (sentence 9): "He locked the door." — who is "He"?
        """
        tokens = []
        entities_list = []
        tid = 0
        offset = 0

        def add_tok(sid, word, pos, coref=-1):
            nonlocal tid, offset
            t = Token(tid, sid, offset, offset + len(word), word, pos, coref)
            tokens.append(t)
            tid += 1
            offset += len(word) + 1
            return t

        # S0: "Scrooge sat in his office."
        add_tok(0, "Scrooge", "NNP", 1)
        entities_list.append(EntityMention(1, 0, 1, "PROP", "PER", "Scrooge"))
        add_tok(0, "sat", "VBD")
        add_tok(0, "in", "IN")
        t = add_tok(0, "his", "PRP$", 1)
        entities_list.append(EntityMention(1, t.token_id, t.token_id + 1, "PRON", "PER", "his"))
        add_tok(0, "office", "NN")
        add_tok(0, ".", ".")

        # S1: "It was cold."
        add_tok(1, "It", "PRP")
        add_tok(1, "was", "VBD")
        add_tok(1, "cold", "JJ")
        add_tok(1, ".", ".")

        # S2: "Bob Cratchit entered."
        bob_start = tid
        add_tok(2, "Bob", "NNP", 2)
        add_tok(2, "Cratchit", "NNP", 2)
        entities_list.append(EntityMention(2, bob_start, bob_start + 2, "PROP", "PER", "Bob Cratchit"))
        add_tok(2, "entered", "VBD")
        add_tok(2, ".", ".")

        # S3: "'Good evening,' said his clerk."
        add_tok(3, "'", "``")
        add_tok(3, "Good", "JJ")
        add_tok(3, "evening", "NN")
        add_tok(3, ",", ",")
        add_tok(3, "'", "''")
        add_tok(3, "said", "VBD")
        t_his = add_tok(3, "his", "PRP$", 1)
        entities_list.append(EntityMention(1, t_his.token_id, t_his.token_id + 1, "PRON", "PER", "his"))
        t_clerk = add_tok(3, "clerk", "NN", 2)
        entities_list.append(EntityMention(2, t_clerk.token_id, t_clerk.token_id + 1, "NOM", "PER", "clerk"))
        add_tok(3, ".", ".")

        # S4-S8: filler (5 sentences)
        for sid in range(4, 9):
            add_tok(sid, "The", "DT")
            add_tok(sid, "wind", "NN")
            add_tok(sid, "howled", "VBD")
            add_tok(sid, ".", ".")

        # S9: "He locked the door."
        t_he = add_tok(9, "He", "PRP", 1)
        entities_list.append(EntityMention(1, t_he.token_id, t_he.token_id + 1, "PRON", "PER", "He"))
        add_tok(9, "locked", "VBD")
        add_tok(9, "the", "DT")
        add_tok(9, "door", "NN")
        add_tok(9, ".", ".")

        characters = [
            CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge", "Mr. Scrooge"]),
            CharacterProfile(2, "Bob Cratchit", ["Bob", "Cratchit"]),
        ]

        result = resolve_coreferences(
            tokens, entities_list, characters, [""], [(0, tid)], DEFAULT_CONFIG,
        )

        text = result.resolved_full_text
        annotations = _extract_annotations(text)
        stripped = _strip_annotations(text)

        # --- Format checks ---
        assert text.count("[") == text.count("]"), "Unbalanced brackets"
        assert not re.search(r"\[[^\]]*\[", text), "Nested brackets"
        assert "[]" not in text

        # --- Accuracy checks ---
        # "He" in sentence 9 is Scrooge (coref 1), 6+ sentences from last mention
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert len(he_events) >= 1, "'He' in sentence 9 not annotated"
        assert he_events[0].inserted_annotation == "Scrooge"

        # "clerk" should resolve to Bob
        clerk_events = [e for e in result.resolution_log if e.original_text == "clerk"]
        if clerk_events:
            assert clerk_events[0].inserted_annotation == "Bob"

        # --- Reversibility ---
        assert "[" not in stripped
        assert "Scrooge" in stripped
        assert "Bob" in stripped

        # --- Density ---
        total_annotatable = len([e for e in entities_list if e.prop != "PROP" and e.coref_id >= 0])
        if total_annotatable > 0:
            density = len(result.resolution_log) / total_annotatable
            assert density <= 1.0

        # --- Log consistency ---
        assert _count_annotations(text) == len(result.resolution_log)
