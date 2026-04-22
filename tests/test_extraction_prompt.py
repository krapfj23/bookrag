"""
Comprehensive tests for prompts/extraction_prompt.txt

Validates the extraction prompt template against CLAUDE.md,
bookrag_pipeline_plan.md, and bookrag_deep_research_context.md specs:
- All required placeholders present
- Cognee default prompt patterns adopted (from deep research context)
- Episodic vs semantic content distinction
- Chapter metadata requirement
- BookNLP annotation sections
- ExtractionResult schema alignment
- Parenthetical coref instruction
- No-hallucination instructions
- snake_case relationship convention
- No separate date nodes
- Human-readable IDs
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def prompt_text() -> str:
    """Load the extraction prompt template."""
    path = Path(__file__).parent.parent / "prompts" / "extraction_prompt.txt"
    return path.read_text()


# ===================================================================
# Required placeholders — per CLAUDE.md spec
# ===================================================================

class TestRequiredPlaceholders:
    """
    Per spec: {{ chapter_numbers }}, {{ ontology_classes }}, {{ ontology_relations }},
    {{ booknlp_entities }}, {{ booknlp_quotes }}
    """

    def test_chapter_numbers_placeholder(self, prompt_text):
        assert "{{ chapter_numbers }}" in prompt_text

    def test_ontology_classes_placeholder(self, prompt_text):
        assert "{{ ontology_classes }}" in prompt_text

    def test_ontology_relations_placeholder(self, prompt_text):
        assert "{{ ontology_relations }}" in prompt_text

    def test_booknlp_entities_placeholder(self, prompt_text):
        assert "{{ booknlp_entities }}" in prompt_text

    def test_booknlp_quotes_placeholder(self, prompt_text):
        assert "{{ booknlp_quotes }}" in prompt_text

    def test_text_placeholder(self, prompt_text):
        """The prompt needs a {{ text }} placeholder for the actual book text."""
        assert "{{ text }}" in prompt_text

    def test_all_placeholders_use_jinja2_syntax(self, prompt_text):
        """All placeholders should use {{ }} (Jinja2), not {single_braces}."""
        import re
        # Find all {{ placeholder }} patterns
        jinja_placeholders = re.findall(r"\{\{[^}]+\}\}", prompt_text)
        assert len(jinja_placeholders) >= 6  # 6 placeholders total
        # No single-brace placeholders that look like template vars
        # (exclude JSON schema examples which legitimately use braces)
        lines = prompt_text.split("\n")
        for line in lines:
            if line.strip().startswith('"') or line.strip().startswith("{") or line.strip().startswith("}"):
                continue  # skip JSON schema lines
            # Should not have {word} without {{ }}
            single_brace = re.findall(r"(?<!\{)\{([a-z_]+)\}(?!\})", line)
            assert not single_brace, f"Single-brace placeholder found: {single_brace} in: {line}"


# ===================================================================
# Cognee default prompt patterns — from bookrag_deep_research_context.md
# ===================================================================

class TestCogneePromptPatterns:
    """
    Per deep research context Section 1: 'Patterns to Adopt from Cognee's Prompt'.
    """

    def test_elementary_types_instruction(self, prompt_text):
        """Cognee: 'use basic or elementary types for node labels'."""
        # Should instruct to use ontology entity classes, not invent new ones
        assert "entity classes" in prompt_text.lower() or "ontology" in prompt_text.lower()

    def test_human_readable_ids(self, prompt_text):
        """Cognee: 'Node IDs should be names or human-readable identifiers'."""
        # Should reference canonical names as IDs
        assert "canonical name" in prompt_text.lower()

    def test_no_separate_date_nodes(self, prompt_text):
        """Cognee: 'Do not create separate nodes for dates or numerical values'."""
        assert "date" in prompt_text.lower() and "propert" in prompt_text.lower()

    def test_snake_case_relationships(self, prompt_text):
        """Cognee: 'Use snake_case for relationship names'."""
        assert "snake_case" in prompt_text

    def test_coreference_consistency(self, prompt_text):
        """Cognee: 'Maintain Entity Consistency' in coreference resolution."""
        # Our prompt should reference the parenthetical annotations
        assert "canonical name" in prompt_text.lower()
        assert "[" in prompt_text  # references bracket notation


# ===================================================================
# Episodic vs semantic distinction — per CLAUDE.md spec
# ===================================================================

class TestEpisodicVsSemantic:
    """
    Per spec: 'Distinguish episodic content (plot events, character actions)
    from semantic content (themes, relationships, world-building)'.
    """

    def test_episodic_section_exists(self, prompt_text):
        assert "episodic" in prompt_text.lower()

    def test_semantic_section_exists(self, prompt_text):
        assert "semantic" in prompt_text.lower()

    def test_plot_events_in_episodic(self, prompt_text):
        lower = prompt_text.lower()
        # Episodic section should mention plot events or character actions
        assert "plot event" in lower or "character action" in lower

    def test_themes_in_semantic(self, prompt_text):
        lower = prompt_text.lower()
        assert "theme" in lower

    def test_relationships_in_semantic(self, prompt_text):
        lower = prompt_text.lower()
        assert "relationship" in lower


# ===================================================================
# Chapter metadata tracking — per CLAUDE.md
# ===================================================================

class TestChapterMetadataTracking:
    """Per spec: 'chapter metadata tracking' must be in prompt."""

    def test_chapter_requirement(self, prompt_text):
        lower = prompt_text.lower()
        # Must instruct to include chapter numbers on entities/events
        assert "chapter" in lower

    def test_chapter_number_on_entities(self, prompt_text):
        # Should say entities must include chapter number
        assert "chapter number" in prompt_text.lower() or "first_chapter" in prompt_text

    def test_chapter_boundaries(self, prompt_text):
        # Should mention respecting chapter boundaries
        assert "chapter boundar" in prompt_text.lower() or "chapter_numbers" in prompt_text


# ===================================================================
# BookNLP annotations as "cheat sheet" — per CLAUDE.md
# ===================================================================

class TestBookNLPAnnotations:
    """Per spec: 'BookNLP annotations as a "cheat sheet" section'."""

    def test_cheat_sheet_section(self, prompt_text):
        assert "cheat sheet" in prompt_text.lower() or "Cheat Sheet" in prompt_text

    def test_known_entities_section(self, prompt_text):
        assert "Known Entities" in prompt_text or "known entities" in prompt_text.lower()

    def test_attributed_quotes_section(self, prompt_text):
        assert "Attributed Quotes" in prompt_text or "quotes" in prompt_text.lower()

    def test_ground_truth_instruction(self, prompt_text):
        """BookNLP annotations should be treated as ground truth for names."""
        assert "ground truth" in prompt_text.lower() or "canonical" in prompt_text.lower()


# ===================================================================
# Ontology constraints — per CLAUDE.md
# ===================================================================

class TestOntologyConstraints:
    """Per spec: 'ontology constraints' should be surfaced in the prompt."""

    def test_ontology_constraints_section(self, prompt_text):
        assert "ontology" in prompt_text.lower()

    def test_must_use_ontology_types(self, prompt_text):
        """Should instruct LLM to use only discovered ontology types."""
        lower = prompt_text.lower()
        assert "must use" in lower or "only" in lower


# ===================================================================
# Parenthetical coref instruction — per CLAUDE.md
# ===================================================================

class TestParentheticalCoref:
    """
    Per CLAUDE.md: text has parenthetical insertion like 'he [Scrooge]'.
    Prompt must instruct LLM to use canonical names from brackets.
    """

    def test_bracket_notation_explained(self, prompt_text):
        assert "[Scrooge]" in prompt_text or "[" in prompt_text

    def test_canonical_name_from_brackets(self, prompt_text):
        lower = prompt_text.lower()
        assert "bracket" in lower or "canonical name" in lower

    def test_no_pronouns_as_ids(self, prompt_text):
        lower = prompt_text.lower()
        assert "pronoun" in lower


# ===================================================================
# No-hallucination instructions — per spec
# ===================================================================

class TestNoHallucination:
    """
    Per spec: 'don't invent events not in the text',
    'do NOT use your prior knowledge'.
    """

    def test_no_invention(self, prompt_text):
        lower = prompt_text.lower()
        assert "invent" in lower or "not present" in lower

    def test_no_prior_knowledge(self, prompt_text):
        lower = prompt_text.lower()
        assert "prior knowledge" in lower

    def test_only_from_text(self, prompt_text):
        lower = prompt_text.lower()
        assert "only from" in lower or "from the provided text" in lower or "from the text" in lower


# ===================================================================
# JSON output schema matches ExtractionResult — per spec
# ===================================================================

class TestOutputSchemaAlignment:
    """
    Per spec: 'Instruct the LLM to output valid JSON matching the ExtractionResult schema'.
    """

    def test_json_instruction(self, prompt_text):
        lower = prompt_text.lower()
        assert "json" in lower

    def test_characters_in_schema(self, prompt_text):
        assert '"characters"' in prompt_text

    def test_locations_in_schema(self, prompt_text):
        assert '"locations"' in prompt_text

    def test_events_in_schema(self, prompt_text):
        assert '"events"' in prompt_text

    def test_relationships_in_schema(self, prompt_text):
        assert '"relationships"' in prompt_text

    def test_themes_in_schema(self, prompt_text):
        assert '"themes"' in prompt_text

    def test_factions_in_schema(self, prompt_text):
        assert '"factions"' in prompt_text

    def test_schema_has_name_field(self, prompt_text):
        assert '"name"' in prompt_text

    def test_schema_has_first_chapter(self, prompt_text):
        assert '"first_chapter"' in prompt_text

    def test_schema_has_chapter_for_events(self, prompt_text):
        assert '"chapter"' in prompt_text

    def test_schema_has_participant_names(self, prompt_text):
        assert '"participant_names"' in prompt_text

    def test_schema_has_source_name(self, prompt_text):
        assert '"source_name"' in prompt_text

    def test_schema_has_target_name(self, prompt_text):
        assert '"target_name"' in prompt_text

    def test_schema_has_relation_type(self, prompt_text):
        assert '"relation_type"' in prompt_text

    def test_schema_has_member_names(self, prompt_text):
        assert '"member_names"' in prompt_text

    def test_schema_has_related_character_names(self, prompt_text):
        assert '"related_character_names"' in prompt_text

    def test_schema_has_location_name(self, prompt_text):
        assert '"location_name"' in prompt_text

    def test_schema_has_aliases(self, prompt_text):
        assert '"aliases"' in prompt_text

    def test_schema_has_description(self, prompt_text):
        assert '"description"' in prompt_text


# ===================================================================
# No duplicate entities instruction
# ===================================================================

class TestNoDuplicateEntities:
    def test_no_duplicates_instruction(self, prompt_text):
        lower = prompt_text.lower()
        assert "duplicate" in lower

    def test_single_canonical_name(self, prompt_text):
        lower = prompt_text.lower()
        assert "canonical" in lower


# ===================================================================
# Name consistency instruction
# ===================================================================

class TestNameConsistency:
    def test_names_must_match(self, prompt_text):
        """Name fields in events/relationships must match character/location names."""
        lower = prompt_text.lower()
        assert "must" in lower and "match" in lower


# ===================================================================
# Structural completeness
# ===================================================================

class TestStructuralCompleteness:
    def test_prompt_is_not_empty(self, prompt_text):
        assert len(prompt_text) > 500

    def test_has_multiple_sections(self, prompt_text):
        """Should have clear section headers."""
        assert prompt_text.count("##") >= 5

    def test_has_extraction_rules(self, prompt_text):
        assert "Extraction Rules" in prompt_text or "extraction rules" in prompt_text.lower()

    def test_has_output_format(self, prompt_text):
        assert "Output Format" in prompt_text or "output format" in prompt_text.lower()


class TestLastKnownChapterInPrompt:
    """Prompt must instruct the LLM to populate last_known_chapter."""

    def test_field_appears_in_json_schema(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text()
        assert "last_known_chapter" in prompt, "prompt must document last_known_chapter"

    def test_prompt_explains_semantics(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text().lower()
        assert "latest chapter" in prompt or "last chapter" in prompt


class TestForwardLeakPrevention:
    """Prompt must explicitly instruct the LLM against forward-looking summarization."""

    def test_chapter_bounds_section_exists(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text()
        assert "## Chapter Bounds" in prompt

    def test_ignore_training_knowledge_instruction(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text().lower()
        assert (
            "ignore that knowledge" in prompt
            or "do not foreshadow" in prompt
            or "do not use your prior knowledge" in prompt
        )

    def test_future_tense_prohibition(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text().lower()
        assert "future tense" in prompt or "foreshadow" in prompt

    def test_worked_example_present(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text()
        assert "worked example" in prompt.lower() or "example" in prompt.lower()
        assert "three spirits" in prompt.lower() or "later" in prompt.lower()

    def test_self_check_section(self):
        prompt = Path("prompts/extraction_prompt.txt").read_text()
        assert "Self-Check" in prompt or "self-check" in prompt.lower()

    def test_chapter_numbers_placeholder_used_in_bounds_section(self):
        """The {{ chapter_numbers }} variable must be referenced inside the bounds
        guidance so the LLM sees the actual batch range, not a generic constant."""
        prompt = Path("prompts/extraction_prompt.txt").read_text()
        idx = prompt.find("## Chapter Bounds")
        assert idx >= 0
        tail = prompt[idx:]
        next_section = tail.find("\n## ", 5)
        section = tail if next_section < 0 else tail[:next_section]
        assert "{{ chapter_numbers }}" in section
