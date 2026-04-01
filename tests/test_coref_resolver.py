"""Comprehensive tests for pipeline/coref_resolver.py.

Covers every feature of the coreference text resolver:

- Data classes: Token, EntityMention, CharacterProfile, CorefConfig, CorefResult,
  CorefCluster, ResolutionEvent
- Alias selection: shortest unambiguous alias, collisions, no aliases, single char
- Mention indexing: _build_mention_index, _build_mention_span_set
- Chapter assignment: _assign_token_chapters_fast, empty boundaries, multi-chapter
- Distance rule: annotate when antecedent 3+ sentences away (configurable)
- Ambiguity rule: annotate when 2+ characters in ambiguity window
- Both rules firing simultaneously
- PROP (proper nouns) NEVER annotated
- NOM (common nouns) annotated when coref_id present
- PRON (pronouns) annotated as candidates
- Non-person entities: LOC, FAC, GPE also resolved
- Self-match guard: don't insert [Scrooge] after "Scrooge"
- First-mention distance: first pronoun with no prior mention triggers distance
- Config: custom thresholds, annotate_ambiguous=False disables ambiguity
- Multi-word mentions: "Bob Cratchit" emitted as single span
- Empty chapters: no crash
- Characters with no aliases: fall back to canonical name
- Token reconstruction: whitespace/gap handling
- Cluster tracking: mention_count, resolution_count
- Resolution log: every insertion recorded with correct rule
- Persistence: save_coref_outputs file structure matches plan docs
- CorefResult fields: resolved_chapters, resolved_full_text, clusters, resolution_log

Alignment with plan docs:
- CLAUDE.md: Parenthetical insertion "he [Scrooge] muttered to his [Scrooge] clerk
  [Bob Cratchit]", distance + ambiguity rules, thresholds tunable in config,
  BookNLP does NOT produce resolved text, all intermediate outputs saved,
  loguru logging, output structure coref/clusters.json + resolution_log.json +
  resolved/chapters/*.txt + resolved/full_text_resolved.txt
- bookrag_pipeline_plan.md: Step 3 Coreference Resolution, coref config in
  config.yaml (distance_threshold=3, annotate_ambiguous=true), output paths
- bookrag_deep_research_context.md: Section 6 Parenthetical Insertion Details,
  format "he [Scrooge] muttered...", reversible, Claude parses it well
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.coref_resolver import (
    Token,
    EntityMention,
    CharacterProfile,
    CorefConfig,
    CorefCluster,
    CorefResult,
    ResolutionEvent,
    resolve_coreferences,
    save_coref_outputs,
    _build_shortest_alias_map,
    _build_mention_index,
    _build_mention_span_set,
    _assign_token_chapters_fast,
)


# ============================================================================
# Fixtures — reusable test data
# ============================================================================

@pytest.fixture
def christmas_carol_data():
    """A Christmas Carol excerpt: 4 sentences, 2 characters, multi-word mention.

    Sentence 0: "Scrooge sat in his counting-house."
    Sentence 1: "The door was open."
    Sentence 2: "Bob Cratchit worked nearby."
    Sentence 3: "He muttered to his clerk about the cold."
    """
    tokens = [
        Token(0, 0, 0, 7, "Scrooge", "NNP", 1),
        Token(1, 0, 8, 11, "sat", "VBD", -1),
        Token(2, 0, 12, 14, "in", "IN", -1),
        Token(3, 0, 15, 18, "his", "PRP$", 1),
        Token(4, 0, 19, 33, "counting-house", "NN", -1),
        Token(5, 0, 33, 34, ".", ".", -1),
        Token(6, 1, 35, 38, "The", "DT", -1),
        Token(7, 1, 39, 43, "door", "NN", -1),
        Token(8, 1, 44, 47, "was", "VBD", -1),
        Token(9, 1, 48, 52, "open", "JJ", -1),
        Token(10, 1, 52, 53, ".", ".", -1),
        Token(11, 2, 54, 57, "Bob", "NNP", 2),
        Token(12, 2, 58, 65, "Cratchit", "NNP", 2),
        Token(13, 2, 66, 72, "worked", "VBD", -1),
        Token(14, 2, 73, 79, "nearby", "RB", -1),
        Token(15, 2, 79, 80, ".", ".", -1),
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


@pytest.fixture
def default_config():
    return CorefConfig(distance_threshold=3, ambiguity_window=2, annotate_ambiguous=True)


# ============================================================================
# Data class tests
# ============================================================================

class TestDataClasses:
    """Verify all data classes have correct fields and defaults."""

    def test_token_fields(self):
        t = Token(0, 1, 10, 15, "hello", "NN", -1)
        assert t.token_id == 0
        assert t.sentence_id == 1
        assert t.token_offset_begin == 10
        assert t.token_offset_end == 15
        assert t.word == "hello"
        assert t.pos == "NN"
        assert t.coref_id == -1

    def test_entity_mention_fields(self):
        em = EntityMention(5, 10, 12, "PRON", "PER", "he")
        assert em.coref_id == 5
        assert em.start_token == 10
        assert em.end_token == 12
        assert em.prop == "PRON"
        assert em.cat == "PER"
        assert em.text == "he"

    def test_character_profile_defaults(self):
        cp = CharacterProfile(1, "Test Name")
        assert cp.coref_id == 1
        assert cp.name == "Test Name"
        assert cp.aliases == []

    def test_character_profile_with_aliases(self):
        cp = CharacterProfile(1, "Test Name", ["Alias1", "Alias2"])
        assert len(cp.aliases) == 2

    def test_coref_config_defaults(self):
        cfg = CorefConfig()
        assert cfg.distance_threshold == 3
        assert cfg.ambiguity_window == 2
        assert cfg.annotate_ambiguous is True

    def test_coref_config_custom(self):
        cfg = CorefConfig(distance_threshold=5, ambiguity_window=4, annotate_ambiguous=False)
        assert cfg.distance_threshold == 5
        assert cfg.ambiguity_window == 4
        assert cfg.annotate_ambiguous is False

    def test_resolution_event_fields(self):
        ev = ResolutionEvent(
            token_id=10, original_text="he",
            inserted_annotation="Scrooge", rule_triggered="distance",
            sentence_id=5, chapter=0,
        )
        assert ev.rule_triggered == "distance"

    def test_coref_cluster_defaults(self):
        cl = CorefCluster(canonical_name="Test")
        assert cl.mentions == []
        assert cl.resolution_count == 0

    def test_coref_result_fields(self):
        r = CorefResult(
            resolved_chapters=["ch1"],
            resolved_full_text="ch1",
            clusters={},
            resolution_log=[],
        )
        assert isinstance(r.resolved_chapters, list)
        assert isinstance(r.clusters, dict)
        assert isinstance(r.resolution_log, list)


# ============================================================================
# Alias selection tests — _build_shortest_alias_map
# ============================================================================

class TestShortestAliasMap:
    """Tests for shortest unambiguous alias selection.

    Per CLAUDE.md: "Use the shortest unambiguous alias from CharacterProfile
    (prefer 'Scrooge' over 'Ebenezer Scrooge' if unambiguous in context)"
    """

    def test_picks_shortest_unique(self):
        characters = [
            CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge", "Mr. Scrooge", "Ebenezer"]),
            CharacterProfile(2, "Bob Cratchit", ["Bob", "Cratchit"]),
        ]
        alias_map = _build_shortest_alias_map(characters)
        # "Bob" (3 chars) is shorter than "Cratchit" (8) and unique
        assert alias_map[2] == "Bob"
        # "Scrooge" (7) is shorter than "Ebenezer" (8) and "Mr. Scrooge" (11)
        # and shorter than "Ebenezer Scrooge" (16)
        assert alias_map[1] == "Scrooge"

    def test_collision_falls_back_to_longer(self):
        """When two characters share a short alias, use a longer unique one."""
        characters = [
            CharacterProfile(1, "Bob Smith", ["Bob", "Smith"]),
            CharacterProfile(2, "Bob Jones", ["Bob", "Jones"]),
        ]
        alias_map = _build_shortest_alias_map(characters)
        # "Bob" collides — both own it
        # Character 1 should fall back to "Smith" (unique)
        # Character 2 should fall back to "Jones" (unique)
        assert alias_map[1] != "Bob"
        assert alias_map[2] != "Bob"
        assert alias_map[1] in ("Smith", "Bob Smith")
        assert alias_map[2] in ("Jones", "Bob Jones")

    def test_no_aliases_uses_canonical_name(self):
        """Character with empty aliases list falls back to canonical name."""
        characters = [
            CharacterProfile(1, "The Ghost", []),
        ]
        alias_map = _build_shortest_alias_map(characters)
        assert alias_map[1] == "The Ghost"

    def test_single_character(self):
        characters = [
            CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge"]),
        ]
        alias_map = _build_shortest_alias_map(characters)
        assert alias_map[1] == "Scrooge"

    def test_canonical_name_included_in_candidates(self):
        """Canonical name itself should be a candidate if it's the shortest unique."""
        characters = [
            CharacterProfile(1, "Ed", ["Edward", "Eddie"]),
            CharacterProfile(2, "Edward Smith", ["Edward", "Smith"]),
        ]
        alias_map = _build_shortest_alias_map(characters)
        # "Ed" is unique to character 1 (shortest)
        assert alias_map[1] == "Ed"
        # "Edward" collides, so char 2 uses "Smith"
        assert alias_map[2] == "Smith"

    def test_case_insensitive_collision(self):
        """Collision detection should be case-insensitive."""
        characters = [
            CharacterProfile(1, "Bob Smith", ["bob", "Smith"]),
            CharacterProfile(2, "Bob Jones", ["Bob", "Jones"]),
        ]
        alias_map = _build_shortest_alias_map(characters)
        # "bob" and "Bob" collide (case-insensitive)
        assert alias_map[1].lower() != "bob" or alias_map[2].lower() != "bob"

    def test_many_characters_all_unique(self):
        """Every character has a unique short alias."""
        characters = [
            CharacterProfile(i, f"Character {i}", [f"C{i}"])
            for i in range(10)
        ]
        alias_map = _build_shortest_alias_map(characters)
        for i in range(10):
            assert alias_map[i] == f"C{i}"

    def test_duplicate_aliases_within_character_deduped(self):
        """If canonical name is also in aliases list, don't double-count."""
        characters = [
            CharacterProfile(1, "Scrooge", ["Scrooge", "Scrooge"]),
        ]
        alias_map = _build_shortest_alias_map(characters)
        assert alias_map[1] == "Scrooge"


# ============================================================================
# Mention index tests
# ============================================================================

class TestMentionIndex:
    """Tests for _build_mention_index and _build_mention_span_set."""

    def test_mention_index_maps_start_token(self):
        entities = [
            EntityMention(1, 5, 6, "PRON", "PER", "he"),
            EntityMention(2, 10, 13, "PROP", "PER", "Bob Cratchit"),
        ]
        idx = _build_mention_index(entities)
        assert 5 in idx
        assert 10 in idx
        assert idx[5].text == "he"
        assert idx[10].text == "Bob Cratchit"

    def test_mention_index_no_continuation_tokens(self):
        entities = [EntityMention(2, 10, 13, "PROP", "PER", "Bob Cratchit")]
        idx = _build_mention_index(entities)
        assert 11 not in idx
        assert 12 not in idx

    def test_span_set_single_token_mention(self):
        """Single-token mention produces no continuation tokens."""
        entities = [EntityMention(1, 5, 6, "PRON", "PER", "he")]
        spans = _build_mention_span_set(entities)
        assert len(spans) == 0

    def test_span_set_multi_token_mention(self):
        """Multi-token mention: tokens after start are in the continuation set."""
        entities = [EntityMention(2, 10, 13, "PROP", "PER", "Bob Cratchit")]
        spans = _build_mention_span_set(entities)
        assert 11 in spans
        assert 12 in spans
        assert 10 not in spans  # start token not in continuation
        assert 13 not in spans  # end is exclusive

    def test_span_set_multiple_mentions(self):
        entities = [
            EntityMention(1, 0, 1, "PRON", "PER", "he"),
            EntityMention(2, 5, 8, "PROP", "PER", "Bob the Builder"),
        ]
        spans = _build_mention_span_set(entities)
        assert 6 in spans
        assert 7 in spans
        assert len(spans) == 2

    def test_empty_entities(self):
        assert _build_mention_index([]) == {}
        assert _build_mention_span_set([]) == set()


# ============================================================================
# Chapter assignment tests
# ============================================================================

class TestChapterAssignment:
    """Tests for _assign_token_chapters_fast."""

    def test_single_chapter(self):
        tokens = [Token(i, 0, i * 5, i * 5 + 4, "w", "NN", -1) for i in range(5)]
        boundaries = [(0, 5)]
        mapping = _assign_token_chapters_fast(tokens, boundaries)
        assert all(v == 0 for v in mapping.values())

    def test_two_chapters(self):
        tokens = [Token(i, 0, i * 5, i * 5 + 4, "w", "NN", -1) for i in range(10)]
        boundaries = [(0, 5), (5, 10)]
        mapping = _assign_token_chapters_fast(tokens, boundaries)
        for i in range(5):
            assert mapping[i] == 0
        for i in range(5, 10):
            assert mapping[i] == 1

    def test_empty_boundaries_single_chapter(self):
        """No boundaries → all tokens assigned to chapter 0."""
        tokens = [Token(i, 0, i, i + 1, "w", "NN", -1) for i in range(3)]
        mapping = _assign_token_chapters_fast(tokens, [])
        assert all(v == 0 for v in mapping.values())

    def test_token_outside_boundaries(self):
        """Token not covered by any boundary gets -1."""
        tokens = [Token(99, 0, 99, 100, "w", "NN", -1)]
        boundaries = [(0, 10)]
        mapping = _assign_token_chapters_fast(tokens, boundaries)
        assert mapping[99] == -1

    def test_many_chapters(self):
        """Stress test: 10 chapters."""
        tokens = [Token(i, 0, i, i + 1, "w", "NN", -1) for i in range(100)]
        boundaries = [(i * 10, (i + 1) * 10) for i in range(10)]
        mapping = _assign_token_chapters_fast(tokens, boundaries)
        for i in range(100):
            assert mapping[i] == i // 10


# ============================================================================
# Distance rule tests
# ============================================================================

class TestDistanceRule:
    """Test the distance rule: annotate when antecedent is 3+ sentences away.

    Per CLAUDE.md & plan: "Annotate pronouns when antecedent is 3+ sentences away"
    Per config.yaml spec: distance_threshold: 3
    """

    def test_distance_triggers_at_threshold(self, christmas_carol_data, default_config):
        """Sentence 0 has 'Scrooge', sentence 3 has 'He' — distance = 3, triggers."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert len(he_events) == 1
        assert he_events[0].rule_triggered in ("distance", "both")

    def test_distance_does_not_trigger_below_threshold(self):
        """Mention 1 sentence away should NOT trigger distance rule."""
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 5, 8, "ran", "VBD", -1),
            Token(2, 0, 8, 9, ".", ".", -1),
            Token(3, 1, 10, 12, "He", "PRP", 1),
            Token(4, 1, 13, 18, "smiled", "VBD", -1),
            Token(5, 1, 18, 19, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 3, 4, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 6)], config)
        # Only 1 sentence apart — distance rule should NOT fire
        # No ambiguity rule (disabled). So no annotation.
        assert len(result.resolution_log) == 0

    def test_distance_exactly_at_minus_one(self):
        """Distance = threshold - 1 should NOT trigger."""
        # Sentences 0, 1, 2 — distance from 0 to 2 is 2, threshold is 3
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 4, 5, ".", ".", -1),
            Token(2, 1, 6, 9, "The", "DT", -1),
            Token(3, 1, 10, 14, "door", "NN", -1),
            Token(4, 1, 14, 15, ".", ".", -1),
            Token(5, 2, 16, 18, "He", "PRP", 1),
            Token(6, 2, 19, 22, "ran", "VBD", -1),
            Token(7, 2, 22, 23, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 5, 6, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 8)], config)
        assert len(result.resolution_log) == 0

    def test_custom_distance_threshold(self):
        """Custom threshold of 1 should annotate even 1 sentence apart."""
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 4, 5, ".", ".", -1),
            Token(2, 1, 6, 8, "He", "PRP", 1),
            Token(3, 1, 9, 12, "ran", "VBD", -1),
            Token(4, 1, 12, 13, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 2, 3, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 5)], config)
        assert len(result.resolution_log) == 1
        assert result.resolution_log[0].rule_triggered == "distance"

    def test_first_mention_pronoun_triggers_distance(self):
        """First pronoun with no prior mention should trigger distance.

        A pronoun appearing before any other mention in its cluster has
        no antecedent at all — readers have never seen who it refers to.
        """
        tokens = [
            Token(0, 0, 0, 2, "He", "PRP", 1),
            Token(1, 0, 3, 6, "ran", "VBD", -1),
            Token(2, 0, 6, 7, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 3)], config)
        assert len(result.resolution_log) == 1
        assert result.resolution_log[0].rule_triggered == "distance"
        assert "[John]" in result.resolved_full_text


# ============================================================================
# Ambiguity rule tests
# ============================================================================

class TestAmbiguityRule:
    """Test the ambiguity rule: annotate when 2+ characters in scope.

    Per CLAUDE.md: "Annotate when multiple characters are in scope"
    Per plan: ambiguity_window configurable in config.yaml
    """

    def test_ambiguity_triggers_with_two_characters(self, christmas_carol_data, default_config):
        """Sentence 3 has both Scrooge and Bob in the ambiguity window."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        # "clerk" (NOM, coref 2) should be annotated due to ambiguity
        clerk_events = [e for e in result.resolution_log if e.original_text == "clerk"]
        assert len(clerk_events) == 1
        assert clerk_events[0].rule_triggered in ("ambiguity", "both")

    def test_no_ambiguity_single_character(self):
        """Only one character in scope — ambiguity rule should NOT fire."""
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 5, 8, "ran", "VBD", -1),
            Token(2, 0, 8, 9, ".", ".", -1),
            Token(3, 1, 10, 12, "He", "PRP", 1),
            Token(4, 1, 13, 18, "smiled", "VBD", -1),
            Token(5, 1, 18, 19, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 3, 4, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=99, annotate_ambiguous=True)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 6)], config)
        # Distance won't fire (threshold too high), ambiguity won't fire (only 1 char)
        assert len(result.resolution_log) == 0

    def test_ambiguity_disabled(self, christmas_carol_data):
        """annotate_ambiguous=False disables the ambiguity rule entirely."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        config = CorefConfig(distance_threshold=99, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, config)
        # With distance_threshold=99, only first-mention distance should trigger
        # The ambiguity-only annotations like "clerk" should NOT appear
        for ev in result.resolution_log:
            assert ev.rule_triggered != "ambiguity"

    def test_ambiguity_window_size(self):
        """Ambiguity window=0 means only current sentence matters."""
        # Sentence 0: John ran.
        # Sentence 1: Jane smiled.
        # Sentence 2: He left.
        # With window=0, only sentence 2 is checked. Only John (via "He") in sentence 2,
        # but Jane is in sentence 1 which is outside window=0.
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 5, 8, "ran", "VBD", -1),
            Token(2, 0, 8, 9, ".", ".", -1),
            Token(3, 1, 10, 14, "Jane", "NNP", 2),
            Token(4, 1, 15, 21, "smiled", "VBD", -1),
            Token(5, 1, 21, 22, ".", ".", -1),
            Token(6, 2, 23, 25, "He", "PRP", 1),
            Token(7, 2, 26, 30, "left", "VBD", -1),
            Token(8, 2, 30, 31, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(2, 3, 4, "PROP", "PER", "Jane"),
            EntityMention(1, 6, 7, "PRON", "PER", "He"),
        ]
        characters = [
            CharacterProfile(1, "John Smith", ["John"]),
            CharacterProfile(2, "Jane Doe", ["Jane"]),
        ]
        config = CorefConfig(distance_threshold=99, ambiguity_window=0, annotate_ambiguous=True)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 9)], config)
        # With window=0, only sentence 2 is checked — only coref 1 (He).
        # So only 1 character in window — no ambiguity.
        assert len(result.resolution_log) == 0

    def test_ambiguity_window_includes_prior_sentences(self):
        """With window=2, sentences 0-2 should all be in scope for sentence 2."""
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 5, 8, "ran", "VBD", -1),
            Token(2, 0, 8, 9, ".", ".", -1),
            Token(3, 1, 10, 14, "Jane", "NNP", 2),
            Token(4, 1, 15, 21, "smiled", "VBD", -1),
            Token(5, 1, 21, 22, ".", ".", -1),
            Token(6, 2, 23, 25, "He", "PRP", 1),
            Token(7, 2, 26, 30, "left", "VBD", -1),
            Token(8, 2, 30, 31, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(2, 3, 4, "PROP", "PER", "Jane"),
            EntityMention(1, 6, 7, "PRON", "PER", "He"),
        ]
        characters = [
            CharacterProfile(1, "John Smith", ["John"]),
            CharacterProfile(2, "Jane Doe", ["Jane"]),
        ]
        config = CorefConfig(distance_threshold=99, ambiguity_window=2, annotate_ambiguous=True)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 9)], config)
        # Window=2: sentence 2 checks sentences 0,1,2 — both John and Jane in scope
        assert len(result.resolution_log) == 1
        assert result.resolution_log[0].rule_triggered == "ambiguity"


# ============================================================================
# Both rules tests
# ============================================================================

class TestBothRules:
    """Test when both distance and ambiguity fire simultaneously."""

    def test_both_rules_reported(self, christmas_carol_data, default_config):
        """'He' in sentence 3 is 3 sentences from sentence 0 (distance) AND
        both characters are in scope (ambiguity) — rule should be 'both'."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert len(he_events) == 1
        assert he_events[0].rule_triggered == "both"


# ============================================================================
# PROP / NOM / PRON annotation rules
# ============================================================================

class TestMentionTypAnnotation:
    """Test what gets annotated based on prop type.

    Per spec:
    - PROP (proper nouns) → NEVER annotated
    - PRON (pronouns) → always candidates
    - NOM (common nouns) → annotated if coref_id present
    """

    def test_proper_nouns_never_annotated(self, christmas_carol_data, default_config):
        """'Scrooge' (PROP) and 'Bob Cratchit' (PROP) should never get brackets."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        for ev in result.resolution_log:
            assert ev.original_text not in ("Scrooge", "Bob Cratchit")

    def test_pronouns_annotated(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        pron_events = [e for e in result.resolution_log if e.original_text in ("He", "his")]
        assert len(pron_events) >= 1

    def test_nominals_annotated(self, christmas_carol_data, default_config):
        """'clerk' (NOM) with coref_id should be annotated."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        nom_events = [e for e in result.resolution_log if e.original_text == "clerk"]
        assert len(nom_events) == 1


# ============================================================================
# Non-person entity resolution
# ============================================================================

class TestNonPersonEntities:
    """Test LOC, FAC, GPE resolution.

    Per spec: "Non-person entities: Also resolve LOC, FAC, GPE mentions if
    they have coref chains, using same format: 'the city [London]'"
    """

    def test_location_resolved(self):
        tokens = [
            Token(0, 0, 0, 3, "The", "DT", -1),
            Token(1, 0, 4, 8, "city", "NN", 10),
            Token(2, 0, 9, 12, "was", "VBD", -1),
            Token(3, 0, 13, 17, "cold", "JJ", -1),
            Token(4, 0, 17, 18, ".", ".", -1),
        ]
        entities = [
            EntityMention(10, 1, 2, "NOM", "LOC", "city"),
        ]
        characters = [
            CharacterProfile(10, "London", ["London"]),
        ]
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 5)], config)
        assert "[London]" in result.resolved_full_text

    def test_gpe_resolved(self):
        tokens = [
            Token(0, 0, 0, 2, "It", "PRP", 20),
            Token(1, 0, 3, 6, "was", "VBD", -1),
            Token(2, 0, 7, 12, "great", "JJ", -1),
            Token(3, 0, 12, 13, ".", ".", -1),
        ]
        entities = [
            EntityMention(20, 0, 1, "PRON", "GPE", "It"),
        ]
        characters = [
            CharacterProfile(20, "United Kingdom", ["UK", "Britain"]),
        ]
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 4)], config)
        assert "[UK]" in result.resolved_full_text


# ============================================================================
# Self-match guard
# ============================================================================

class TestSelfMatchGuard:
    """Don't insert [Scrooge] after the word 'Scrooge'.

    The resolver should skip annotation when the mention text already
    matches the chosen alias (case-insensitive).
    """

    def test_no_annotation_when_mention_matches_alias(self):
        """If a NOM mention text equals the alias, skip it."""
        tokens = [
            Token(0, 0, 0, 7, "Scrooge", "NN", 1),
            Token(1, 0, 8, 11, "ran", "VBD", -1),
            Token(2, 0, 11, 12, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "NOM", "PER", "Scrooge"),
        ]
        characters = [
            CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge"]),
        ]
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 3)], config)
        # "Scrooge" NOM matches alias "Scrooge" — should NOT annotate
        assert "[Scrooge]" not in result.resolved_full_text

    def test_annotation_when_mention_differs_from_alias(self):
        """'the old man' does not match 'Scrooge' — should annotate."""
        tokens = [
            Token(0, 0, 0, 3, "the", "DT", -1),
            Token(1, 0, 4, 7, "old", "JJ", -1),
            Token(2, 0, 8, 11, "man", "NN", 1),
            Token(3, 0, 12, 15, "ran", "VBD", -1),
            Token(4, 0, 15, 16, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 3, "NOM", "PER", "the old man"),
        ]
        characters = [
            CharacterProfile(1, "Ebenezer Scrooge", ["Scrooge"]),
        ]
        config = CorefConfig(distance_threshold=1, annotate_ambiguous=False)
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 5)], config)
        assert "the old man [Scrooge]" in result.resolved_full_text


# ============================================================================
# Multi-word mention handling
# ============================================================================

class TestMultiWordMentions:
    """Multi-word mentions like 'Bob Cratchit' should be emitted as a single
    span, with continuation tokens skipped."""

    def test_multi_word_emitted_once(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        # "Bob Cratchit" should appear exactly once, not "Bob Cratchit Cratchit"
        assert result.resolved_full_text.count("Bob Cratchit") == 1
        # No double "Cratchit"
        assert "Cratchit Cratchit" not in result.resolved_full_text


# ============================================================================
# Text reconstruction
# ============================================================================

class TestTextReconstruction:
    """Test that text is rebuilt correctly from tokens.

    Per spec: "Build resolved text by reconstructing from tokens + insertions
    (don't try to do string replacement on the original text)"
    """

    def test_basic_reconstruction(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        text = result.resolved_full_text
        # All original words present
        assert "Scrooge" in text
        assert "sat" in text
        assert "counting-house" in text
        assert "Bob Cratchit" in text
        assert "muttered" in text

    def test_parenthetical_format(self, christmas_carol_data, default_config):
        """Annotations should be in format: 'word [Name]' with space before bracket.

        Per deep_research_context.md Section 6: 'he [Scrooge] muttered...'
        """
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        text = result.resolved_full_text
        # Should contain annotations in the right format
        assert "He [Scrooge]" in text
        assert "clerk [Bob]" in text

    def test_reversible_by_stripping_brackets(self, christmas_carol_data, default_config):
        """Per deep_research_context.md: 'Preserves original text (reversible
        by stripping brackets)'.

        Stripping all [bracketed] insertions should leave coherent text.
        """
        import re
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        # Strip all parenthetical insertions
        stripped = re.sub(r"\s*\[[^\]]+\]", "", result.resolved_full_text)
        # Should still contain all original words
        assert "Scrooge" in stripped
        assert "muttered" in stripped
        assert "clerk" in stripped

    def test_punctuation_spacing(self):
        """Punctuation attached to previous word should not have extra space."""
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 4, 5, ",", ",", -1),
            Token(2, 0, 6, 9, "who", "WP", -1),
            Token(3, 0, 10, 13, "ran", "VBD", -1),
            Token(4, 0, 13, 14, ".", ".", -1),
        ]
        entities = [EntityMention(1, 0, 1, "PROP", "PER", "John")]
        characters = [CharacterProfile(1, "John", [])]
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 5)])
        # Comma should be attached to "John" without space
        assert "John," in result.resolved_full_text


# ============================================================================
# Cluster tracking
# ============================================================================

class TestClusterTracking:
    """Test that clusters record mentions and resolution counts correctly."""

    def test_cluster_mention_count(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        # Scrooge cluster (coref 1): "Scrooge" PROP, "his" PRON, "He" PRON, "his" PRON = 4
        assert len(result.clusters[1].mentions) == 4
        # Bob cluster (coref 2): "Bob Cratchit" PROP, "clerk" NOM = 2
        assert len(result.clusters[2].mentions) == 2

    def test_cluster_resolution_count(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        # Scrooge: "He" and "his" (sentence 3) annotated = 2
        assert result.clusters[1].resolution_count == 2
        # Bob: "clerk" annotated = 1
        assert result.clusters[2].resolution_count == 1

    def test_cluster_canonical_name(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        assert result.clusters[1].canonical_name == "Ebenezer Scrooge"
        assert result.clusters[2].canonical_name == "Bob Cratchit"

    def test_cluster_mentions_have_chapter(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        for cl in result.clusters.values():
            for m in cl.mentions:
                assert "chapter" in m
                assert isinstance(m["chapter"], int)

    def test_cluster_mentions_have_prop_and_cat(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        for cl in result.clusters.values():
            for m in cl.mentions:
                assert m["prop"] in ("PROP", "NOM", "PRON")
                assert m["cat"] in ("PER", "LOC", "FAC", "GPE", "VEH", "ORG")

    def test_entity_without_character_profile_creates_cluster(self):
        """Entities with coref_id but no CharacterProfile should still create a cluster."""
        tokens = [
            Token(0, 0, 0, 2, "it", "PRP", 99),
            Token(1, 0, 3, 6, "was", "VBD", -1),
            Token(2, 0, 7, 11, "cold", "JJ", -1),
            Token(3, 0, 11, 12, ".", ".", -1),
        ]
        entities = [EntityMention(99, 0, 1, "PRON", "LOC", "it")]
        # No CharacterProfile for coref_id 99
        characters = []
        result = resolve_coreferences(tokens, entities, characters, [""], [(0, 4)])
        assert 99 in result.clusters


# ============================================================================
# Resolution log tests
# ============================================================================

class TestResolutionLog:
    """Test that the resolution log captures every insertion correctly."""

    def test_log_count_matches_brackets(self, christmas_carol_data, default_config):
        """Number of log entries should match number of [brackets] in text."""
        import re
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        bracket_count = len(re.findall(r"\[", result.resolved_full_text))
        assert bracket_count == len(result.resolution_log)

    def test_log_has_all_fields(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        for ev in result.resolution_log:
            assert isinstance(ev.token_id, int)
            assert isinstance(ev.original_text, str)
            assert isinstance(ev.inserted_annotation, str)
            assert ev.rule_triggered in ("distance", "ambiguity", "both")
            assert isinstance(ev.sentence_id, int)
            assert isinstance(ev.chapter, int)

    def test_log_rule_values(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        rules = {ev.rule_triggered for ev in result.resolution_log}
        # We expect at least "both" and "ambiguity" from the demo data
        assert "both" in rules or "ambiguity" in rules


# ============================================================================
# Multi-chapter tests
# ============================================================================

class TestMultiChapter:
    """Test resolution across multiple chapters."""

    def test_two_chapters_separate_text(self):
        """Each chapter should produce its own resolved text."""
        tokens = [
            # Chapter 0, sentence 0
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 5, 8, "ran", "VBD", -1),
            Token(2, 0, 8, 9, ".", ".", -1),
            # Chapter 1, sentence 5
            Token(3, 5, 10, 12, "He", "PRP", 1),
            Token(4, 5, 13, 18, "smiled", "VBD", -1),
            Token(5, 5, 18, 19, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 3, 4, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=False)
        result = resolve_coreferences(
            tokens, entities, characters,
            ["ch1", "ch2"],
            [(0, 3), (3, 6)],
            config,
        )
        assert len(result.resolved_chapters) == 2
        assert "John" in result.resolved_chapters[0]
        assert "He" in result.resolved_chapters[1]

    def test_resolution_log_has_chapter_numbers(self):
        tokens = [
            Token(0, 0, 0, 4, "John", "NNP", 1),
            Token(1, 0, 4, 5, ".", ".", -1),
            Token(2, 5, 6, 8, "He", "PRP", 1),
            Token(3, 5, 9, 12, "ran", "VBD", -1),
            Token(4, 5, 12, 13, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "John"),
            EntityMention(1, 2, 3, "PRON", "PER", "He"),
        ]
        characters = [CharacterProfile(1, "John Smith", ["John"])]
        config = CorefConfig(distance_threshold=3, annotate_ambiguous=False)
        result = resolve_coreferences(
            tokens, entities, characters, ["", ""], [(0, 2), (2, 5)], config,
        )
        for ev in result.resolution_log:
            assert ev.chapter in (0, 1)


# ============================================================================
# Empty / edge case tests
# ============================================================================

class TestEdgeCases:
    """Edge cases: empty inputs, no entities, no characters."""

    def test_empty_tokens(self):
        result = resolve_coreferences([], [], [], [""], [(0, 0)])
        assert result.resolved_full_text == ""
        assert len(result.resolution_log) == 0

    def test_no_entities(self):
        tokens = [
            Token(0, 0, 0, 5, "Hello", "UH", -1),
            Token(1, 0, 6, 11, "world", "NN", -1),
        ]
        result = resolve_coreferences(tokens, [], [], [""], [(0, 2)])
        assert "Hello" in result.resolved_full_text
        assert "[" not in result.resolved_full_text

    def test_no_characters(self):
        """Entities exist but no CharacterProfiles — clusters still created."""
        tokens = [
            Token(0, 0, 0, 2, "He", "PRP", 5),
            Token(1, 0, 3, 6, "ran", "VBD", -1),
        ]
        entities = [EntityMention(5, 0, 1, "PRON", "PER", "He")]
        result = resolve_coreferences(tokens, entities, [], [""], [(0, 2)])
        assert 5 in result.clusters

    def test_tokens_with_no_coref(self):
        """All tokens have coref_id=-1. No annotations should appear."""
        tokens = [
            Token(0, 0, 0, 3, "The", "DT", -1),
            Token(1, 0, 4, 7, "cat", "NN", -1),
            Token(2, 0, 8, 11, "sat", "VBD", -1),
        ]
        result = resolve_coreferences(tokens, [], [], [""], [(0, 3)])
        assert "[" not in result.resolved_full_text

    def test_single_token_input(self):
        tokens = [Token(0, 0, 0, 5, "Hello", "UH", -1)]
        result = resolve_coreferences(tokens, [], [], [""], [(0, 1)])
        assert result.resolved_full_text == "Hello"

    def test_default_config_when_none(self):
        """Passing config=None should use default CorefConfig."""
        tokens = [Token(0, 0, 0, 5, "Hello", "UH", -1)]
        result = resolve_coreferences(tokens, [], [], [""], [(0, 1)], config=None)
        assert result.resolved_full_text == "Hello"


# ============================================================================
# CorefResult structure
# ============================================================================

class TestCorefResult:
    """Verify CorefResult has all required fields per plan docs."""

    def test_resolved_chapters_is_list_of_strings(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        assert isinstance(result.resolved_chapters, list)
        for ch in result.resolved_chapters:
            assert isinstance(ch, str)

    def test_resolved_full_text_is_string(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        assert isinstance(result.resolved_full_text, str)
        assert len(result.resolved_full_text) > 0

    def test_clusters_keyed_by_coref_id(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        assert isinstance(result.clusters, dict)
        for key, val in result.clusters.items():
            assert isinstance(key, int)
            assert isinstance(val, CorefCluster)

    def test_full_text_joins_chapters(self, christmas_carol_data, default_config):
        """Full text should be chapters joined by double newlines."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        expected = "\n\n".join(result.resolved_chapters)
        assert result.resolved_full_text == expected


# ============================================================================
# Persistence / save_coref_outputs tests
# ============================================================================

class TestSaveCorefOutputs:
    """Test file output matches the plan's output structure.

    Per CLAUDE.md:
        coref/clusters.json
        coref/resolution_log.json
        resolved/chapters/chapter_01.txt
        resolved/full_text_resolved.txt

    Per bookrag_pipeline_plan.md: same structure under data/processed/{book_id}/
    """

    def _make_result(self, num_chapters: int = 2) -> CorefResult:
        chapters = [f"Chapter {i + 1} resolved text." for i in range(num_chapters)]
        return CorefResult(
            resolved_chapters=chapters,
            resolved_full_text="\n\n".join(chapters),
            clusters={
                1: CorefCluster(
                    canonical_name="Scrooge",
                    mentions=[{"token_id": 0, "text": "he", "sentence_id": 0,
                               "prop": "PRON", "cat": "PER", "chapter": 0}],
                    resolution_count=1,
                ),
            },
            resolution_log=[
                ResolutionEvent(
                    token_id=0, original_text="he",
                    inserted_annotation="Scrooge", rule_triggered="distance",
                    sentence_id=0, chapter=0,
                ),
            ],
        )

    def test_creates_correct_directories(self, tmp_path):
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        assert (tmp_path / "test_book" / "coref").is_dir()
        assert (tmp_path / "test_book" / "resolved").is_dir()
        assert (tmp_path / "test_book" / "resolved" / "chapters").is_dir()

    def test_clusters_json_exists(self, tmp_path):
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        path = tmp_path / "test_book" / "coref" / "clusters.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "1" in data
        assert data["1"]["canonical_name"] == "Scrooge"
        assert data["1"]["mention_count"] == 1
        assert data["1"]["resolution_count"] == 1

    def test_resolution_log_json_exists(self, tmp_path):
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        path = tmp_path / "test_book" / "coref" / "resolution_log.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["original_text"] == "he"
        assert data[0]["inserted_annotation"] == "Scrooge"
        assert data[0]["rule_triggered"] == "distance"

    def test_chapter_files_exist(self, tmp_path):
        result = self._make_result(num_chapters=3)
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        chapters_dir = tmp_path / "test_book" / "resolved" / "chapters"
        assert (chapters_dir / "chapter_01.txt").exists()
        assert (chapters_dir / "chapter_02.txt").exists()
        assert (chapters_dir / "chapter_03.txt").exists()

    def test_chapter_file_content(self, tmp_path):
        result = self._make_result(num_chapters=2)
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        ch1 = (tmp_path / "test_book" / "resolved" / "chapters" / "chapter_01.txt").read_text()
        assert ch1 == "Chapter 1 resolved text."

    def test_full_text_file_exists(self, tmp_path):
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        path = tmp_path / "test_book" / "resolved" / "full_text_resolved.txt"
        assert path.exists()
        content = path.read_text()
        assert content == result.resolved_full_text

    def test_chapter_filename_zero_padded(self, tmp_path):
        """Chapter files should be zero-padded: chapter_01.txt."""
        result = self._make_result(num_chapters=1)
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        assert (tmp_path / "test_book" / "resolved" / "chapters" / "chapter_01.txt").exists()
        # NOT chapter_1.txt
        assert not (tmp_path / "test_book" / "resolved" / "chapters" / "chapter_1.txt").exists()

    def test_clusters_json_valid_json(self, tmp_path):
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        path = tmp_path / "test_book" / "coref" / "clusters.json"
        # Should not raise
        json.loads(path.read_text())

    def test_resolution_log_json_valid_json(self, tmp_path):
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        path = tmp_path / "test_book" / "coref" / "resolution_log.json"
        json.loads(path.read_text())

    def test_idempotent_save(self, tmp_path):
        """Saving twice should not error (directories already exist)."""
        result = self._make_result()
        save_coref_outputs(result, "test_book", base_dir=tmp_path)
        save_coref_outputs(result, "test_book", base_dir=tmp_path)  # No error

    def test_empty_result_saves(self, tmp_path):
        """Empty result (no chapters, no clusters) should still save cleanly."""
        result = CorefResult(
            resolved_chapters=[],
            resolved_full_text="",
            clusters={},
            resolution_log=[],
        )
        save_coref_outputs(result, "empty_book", base_dir=tmp_path)
        assert (tmp_path / "empty_book" / "coref" / "clusters.json").exists()
        assert (tmp_path / "empty_book" / "resolved" / "full_text_resolved.txt").exists()


# ============================================================================
# Config alignment with models/config.py
# ============================================================================

class TestConfigAlignment:
    """Verify CorefConfig defaults match BookRAGConfig defaults from models/config.py.

    Per CLAUDE.md & plan: coref config thresholds in config.yaml:
      distance_threshold: 3
      annotate_ambiguous: true
    """

    def test_distance_threshold_default_matches_plan(self):
        cfg = CorefConfig()
        assert cfg.distance_threshold == 3

    def test_annotate_ambiguous_default_matches_plan(self):
        cfg = CorefConfig()
        assert cfg.annotate_ambiguous is True

    def test_ambiguity_window_default(self):
        """Per spec: 'current sentence and the previous 2 sentences' → window=2."""
        cfg = CorefConfig()
        assert cfg.ambiguity_window == 2


# ============================================================================
# Integration test — full demo scenario
# ============================================================================

class TestIntegration:
    """Full end-to-end integration test matching the expected output.

    Expected from CLAUDE.md: "he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"
    (Note: alias selection may choose "Bob" over "Bob Cratchit" since "Bob" is unique)
    """

    def test_christmas_carol_demo(self, christmas_carol_data, default_config):
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)

        text = result.resolved_full_text

        # The key assertion from the spec
        assert "He [Scrooge]" in text
        assert "his [Scrooge]" in text
        assert "clerk [Bob]" in text

        # Proper nouns not annotated
        assert "Scrooge [" not in text  # No annotation after "Scrooge" PROP
        assert "Bob Cratchit [" not in text  # No annotation after "Bob Cratchit" PROP

        # Correct number of annotations
        assert len(result.resolution_log) == 3

        # All original content preserved
        assert "sat" in text
        assert "counting-house" in text
        assert "door" in text
        assert "worked" in text
        assert "cold" in text

    def test_full_save_and_reload(self, christmas_carol_data, default_config, tmp_path):
        """Resolve, save, then verify saved files can be loaded and match."""
        tokens, entities, characters, texts, bounds = christmas_carol_data
        result = resolve_coreferences(tokens, entities, characters, texts, bounds, default_config)
        save_coref_outputs(result, "christmas_carol", base_dir=tmp_path)

        # Reload and verify
        clusters = json.loads(
            (tmp_path / "christmas_carol" / "coref" / "clusters.json").read_text()
        )
        assert "1" in clusters
        assert clusters["1"]["canonical_name"] == "Ebenezer Scrooge"
        assert "2" in clusters
        assert clusters["2"]["canonical_name"] == "Bob Cratchit"

        log = json.loads(
            (tmp_path / "christmas_carol" / "coref" / "resolution_log.json").read_text()
        )
        assert len(log) == 3
        rules = {entry["rule_triggered"] for entry in log}
        assert len(rules) >= 1

        full_text = (
            tmp_path / "christmas_carol" / "resolved" / "full_text_resolved.txt"
        ).read_text()
        assert "He [Scrooge]" in full_text

    def test_red_rising_style_scenario(self):
        """Simulate a Red Rising-like scenario with more characters and sentences.

        Per CLAUDE.md: Validation book is Red Rising (~45 chapters, ~100k words).
        This tests the resolver can handle more complex multi-character scenarios.
        """
        tokens = [
            # Sentence 0: "Darrow stood in the mine."
            Token(0, 0, 0, 6, "Darrow", "NNP", 1),
            Token(1, 0, 7, 12, "stood", "VBD", -1),
            Token(2, 0, 13, 15, "in", "IN", -1),
            Token(3, 0, 16, 19, "the", "DT", -1),
            Token(4, 0, 20, 24, "mine", "NN", -1),
            Token(5, 0, 24, 25, ".", ".", -1),
            # Sentence 1: "Cassius watched."
            Token(6, 1, 26, 33, "Cassius", "NNP", 2),
            Token(7, 1, 34, 41, "watched", "VBD", -1),
            Token(8, 1, 41, 42, ".", ".", -1),
            # Sentence 2: "Mustang waited."
            Token(9, 2, 43, 50, "Mustang", "NNP", 3),
            Token(10, 2, 51, 57, "waited", "VBD", -1),
            Token(11, 2, 57, 58, ".", ".", -1),
            # Sentence 3: "He grabbed his sword."
            Token(12, 3, 59, 61, "He", "PRP", 1),
            Token(13, 3, 62, 69, "grabbed", "VBD", -1),
            Token(14, 3, 70, 73, "his", "PRP$", 1),
            Token(15, 3, 74, 79, "sword", "NN", -1),
            Token(16, 3, 79, 80, ".", ".", -1),
        ]
        entities = [
            EntityMention(1, 0, 1, "PROP", "PER", "Darrow"),
            EntityMention(2, 6, 7, "PROP", "PER", "Cassius"),
            EntityMention(3, 9, 10, "PROP", "PER", "Mustang"),
            EntityMention(1, 12, 13, "PRON", "PER", "He"),
            EntityMention(1, 14, 15, "PRON", "PER", "his"),
        ]
        characters = [
            CharacterProfile(1, "Darrow of Lykos", ["Darrow", "The Reaper"]),
            CharacterProfile(2, "Cassius au Bellona", ["Cassius"]),
            CharacterProfile(3, "Virginia au Augustus", ["Mustang", "Virginia"]),
        ]
        config = CorefConfig(distance_threshold=3, ambiguity_window=2, annotate_ambiguous=True)
        result = resolve_coreferences(
            tokens, entities, characters, [""], [(0, 17)], config,
        )

        text = result.resolved_full_text

        # "He" and "his" in sentence 3 with 3 characters in scope
        assert "He [Darrow]" in text
        assert "his [Darrow]" in text

        # Proper nouns not annotated
        assert "Darrow [" not in text
        assert "Cassius [" not in text
        assert "Mustang [" not in text

        # Shortest alias picked
        he_events = [e for e in result.resolution_log if e.original_text == "He"]
        assert he_events[0].inserted_annotation == "Darrow"
