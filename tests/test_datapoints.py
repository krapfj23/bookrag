"""
Comprehensive tests for models/datapoints.py

Tests every feature against CLAUDE.md DataPoint models spec and
bookrag_deep_research_context.md Cognee DataPoint patterns:
- All 6 DataPoint models: Character, Location, Faction, PlotEvent, Relationship, Theme
- metadata["index_fields"] on every DataPoint
- first_chapter field on every DataPoint (per CLAUDE.md requirement)
- All 6 Extraction models mirror DataPoint fields
- ExtractionResult structured output model
- ExtractionResult.to_datapoints() cross-reference resolution
- Deterministic UUIDs via uuid5
- Unresolved references handled gracefully
- Empty ExtractionResult
- DataPoint inheritance from cognee.infrastructure.engine.DataPoint
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel, ValidationError

from models.datapoints import (
    Character,
    CharacterExtraction,
    EventExtraction,
    ExtractionResult,
    Faction,
    FactionExtraction,
    Location,
    LocationExtraction,
    PlotEvent,
    Relationship,
    RelationshipExtraction,
    Theme,
    ThemeExtraction,
)


# ===================================================================
# DataPoint base class inheritance
# ===================================================================

class TestDataPointInheritance:
    """All DataPoints should inherit from cognee.infrastructure.engine.DataPoint."""

    def test_character_is_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(Character, DataPoint)

    def test_location_is_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(Location, DataPoint)

    def test_faction_is_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(Faction, DataPoint)

    def test_plot_event_is_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(PlotEvent, DataPoint)

    def test_relationship_is_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(Relationship, DataPoint)

    def test_theme_is_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(Theme, DataPoint)


# ===================================================================
# Extraction models are NOT DataPoints (per spec)
# ===================================================================

class TestExtractionModelsNotDataPoints:
    """Extraction models are Pydantic BaseModel, NOT DataPoints."""

    def test_character_extraction_is_basemodel_not_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(CharacterExtraction, BaseModel)
        assert not issubclass(CharacterExtraction, DataPoint)

    def test_location_extraction_is_basemodel_not_datapoint(self):
        from cognee.infrastructure.engine import DataPoint
        assert issubclass(LocationExtraction, BaseModel)
        assert not issubclass(LocationExtraction, DataPoint)

    def test_event_extraction_is_basemodel(self):
        assert issubclass(EventExtraction, BaseModel)

    def test_relationship_extraction_is_basemodel(self):
        assert issubclass(RelationshipExtraction, BaseModel)

    def test_theme_extraction_is_basemodel(self):
        assert issubclass(ThemeExtraction, BaseModel)

    def test_faction_extraction_is_basemodel(self):
        assert issubclass(FactionExtraction, BaseModel)

    def test_extraction_result_is_basemodel(self):
        assert issubclass(ExtractionResult, BaseModel)


# ===================================================================
# Character DataPoint — fields and metadata
# ===================================================================

class TestCharacterDataPoint:
    """Covers the Character DataPoint schema."""

    def test_required_fields(self):
        c = Character(name="Scrooge", first_chapter=1)
        assert c.name == "Scrooge"
        assert c.first_chapter == 1

    def test_optional_fields_defaults(self):
        c = Character(name="Scrooge", first_chapter=1)
        assert c.aliases == []
        assert c.description is None
        assert c.chapters_present == []

    def test_all_fields(self):
        c = Character(
            name="Scrooge",
            aliases=["Ebenezer", "Mr. Scrooge"],
            description="A cold miser",
            first_chapter=1,
            chapters_present=[1, 2, 3, 4, 5],
        )
        assert c.aliases == ["Ebenezer", "Mr. Scrooge"]
        assert c.chapters_present == [1, 2, 3, 4, 5]

    def test_index_fields(self):
        """Per spec: metadata["index_fields"] = ["name", "description"]."""
        c = Character(name="Scrooge", first_chapter=1)
        assert c.metadata["index_fields"] == ["name", "description"]

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            Character(first_chapter=1)

    def test_missing_first_chapter_raises(self):
        with pytest.raises(ValidationError):
            Character(name="Scrooge")


# ===================================================================
# Location DataPoint
# ===================================================================

class TestLocationDataPoint:
    """Covers the Location DataPoint schema."""

    def test_required_fields(self):
        loc = Location(name="London", first_chapter=1)
        assert loc.name == "London"
        assert loc.first_chapter == 1

    def test_optional_description(self):
        loc = Location(name="London", first_chapter=1)
        assert loc.description is None

    def test_index_fields(self):
        loc = Location(name="London", first_chapter=1)
        assert loc.metadata["index_fields"] == ["name", "description"]


# ===================================================================
# Faction DataPoint
# ===================================================================

class TestFactionDataPoint:
    """Covers the Faction DataPoint schema."""

    def test_required_fields(self):
        f = Faction(name="The Golds", first_chapter=1)
        assert f.name == "The Golds"

    def test_members_default_empty(self):
        f = Faction(name="The Golds", first_chapter=1)
        assert f.members == []

    def test_members_are_characters(self):
        c = Character(name="Darrow", first_chapter=1)
        f = Faction(name="Sons of Ares", first_chapter=5, members=[c])
        assert len(f.members) == 1
        assert f.members[0].name == "Darrow"

    def test_index_fields(self):
        f = Faction(name="The Golds", first_chapter=1)
        assert f.metadata["index_fields"] == ["name"]


# ===================================================================
# PlotEvent DataPoint
# ===================================================================

class TestPlotEventDataPoint:
    """Covers the PlotEvent DataPoint schema."""

    def test_required_fields(self):
        e = PlotEvent(description="Scrooge sees a ghost", chapter=1)
        assert e.description == "Scrooge sees a ghost"
        assert e.chapter == 1

    def test_participants_default_empty(self):
        e = PlotEvent(description="test", chapter=1)
        assert e.participants == []

    def test_location_default_none(self):
        e = PlotEvent(description="test", chapter=1)
        assert e.location is None

    def test_with_participants_and_location(self):
        c = Character(name="Scrooge", first_chapter=1)
        loc = Location(name="Counting-house", first_chapter=1)
        e = PlotEvent(
            description="Scrooge sees Marley's ghost",
            chapter=1,
            participants=[c],
            location=loc,
        )
        assert len(e.participants) == 1
        assert e.location.name == "Counting-house"

    def test_index_fields(self):
        e = PlotEvent(description="test", chapter=1)
        assert e.metadata["index_fields"] == ["description"]


# ===================================================================
# Relationship DataPoint
# ===================================================================

class TestRelationshipDataPoint:
    """Covers the Relationship DataPoint schema."""

    def test_required_fields(self):
        src = Character(name="Scrooge", first_chapter=1)
        tgt = Character(name="Bob Cratchit", first_chapter=1)
        r = Relationship(
            source=src,
            target=tgt,
            relation_type="employs",
            first_chapter=1,
        )
        assert r.source.name == "Scrooge"
        assert r.target.name == "Bob Cratchit"
        assert r.relation_type == "employs"

    def test_optional_description(self):
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        r = Relationship(source=src, target=tgt, relation_type="loves", first_chapter=1)
        assert r.description is None

    def test_index_fields(self):
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        r = Relationship(source=src, target=tgt, relation_type="loves", first_chapter=1)
        assert r.metadata["index_fields"] == ["relation_type", "description"]


# ===================================================================
# Theme DataPoint
# ===================================================================

class TestThemeDataPoint:
    """Covers the Theme DataPoint schema."""

    def test_required_fields(self):
        t = Theme(name="Redemption", first_chapter=1)
        assert t.name == "Redemption"

    def test_related_characters_default_empty(self):
        t = Theme(name="Redemption", first_chapter=1)
        assert t.related_characters == []

    def test_index_fields(self):
        t = Theme(name="Redemption", first_chapter=1)
        assert t.metadata["index_fields"] == ["name", "description"]


# ===================================================================
# first_chapter on every DataPoint — CLAUDE.md requirement
# ===================================================================

class TestFirstChapterOnAllDataPoints:
    """
    Per CLAUDE.md: 'Chapter metadata is a first-class field on every entity.'
    All DataPoints must have first_chapter (PlotEvent uses 'chapter').
    """

    def test_character_has_first_chapter(self):
        assert "first_chapter" in Character.model_fields

    def test_location_has_first_chapter(self):
        assert "first_chapter" in Location.model_fields

    def test_faction_has_first_chapter(self):
        assert "first_chapter" in Faction.model_fields

    def test_plot_event_has_chapter(self):
        assert "chapter" in PlotEvent.model_fields

    def test_relationship_has_first_chapter(self):
        assert "first_chapter" in Relationship.model_fields

    def test_theme_has_first_chapter(self):
        assert "first_chapter" in Theme.model_fields


# ===================================================================
# CharacterExtraction — LLM response model
# ===================================================================

class TestCharacterExtraction:
    """Covers CharacterExtraction (pre-persistence model) schema."""

    def test_fields_match_datapoint(self):
        """Extraction model should have same data fields as DataPoint (minus id/metadata)."""
        ce = CharacterExtraction(
            name="Scrooge",
            aliases=["Ebenezer"],
            description="A miser",
            first_chapter=1,
            chapters_present=[1, 2],
        )
        assert ce.name == "Scrooge"
        assert ce.aliases == ["Ebenezer"]

    def test_no_id_field(self):
        """Extraction models don't have DataPoint's id field as required."""
        ce = CharacterExtraction(name="Scrooge", first_chapter=1)
        assert not hasattr(ce, "id") or "id" not in CharacterExtraction.model_fields


# ===================================================================
# EventExtraction — uses _name string references
# ===================================================================

class TestEventExtraction:
    """Covers EventExtraction (pre-persistence model) schema."""

    def test_participant_names_are_strings(self):
        ee = EventExtraction(
            description="Ghost appears",
            chapter=1,
            participant_names=["Scrooge", "Marley"],
            location_name="Counting-house",
        )
        assert ee.participant_names == ["Scrooge", "Marley"]
        assert ee.location_name == "Counting-house"

    def test_location_name_optional(self):
        ee = EventExtraction(description="test", chapter=1)
        assert ee.location_name is None


# ===================================================================
# RelationshipExtraction — uses _name string references
# ===================================================================

class TestRelationshipExtraction:
    """Covers RelationshipExtraction (pre-persistence model) schema."""

    def test_uses_source_name_target_name(self):
        re = RelationshipExtraction(
            source_name="Scrooge",
            target_name="Bob Cratchit",
            relation_type="employs",
            first_chapter=1,
        )
        assert re.source_name == "Scrooge"
        assert re.target_name == "Bob Cratchit"
        assert re.relation_type == "employs"


# ===================================================================
# FactionExtraction — uses member_names
# ===================================================================

class TestFactionExtraction:
    """Covers FactionExtraction (pre-persistence model) schema."""

    def test_member_names_are_strings(self):
        fe = FactionExtraction(
            name="Cratchit Family",
            first_chapter=3,
            member_names=["Bob Cratchit", "Tiny Tim"],
        )
        assert fe.member_names == ["Bob Cratchit", "Tiny Tim"]


# ===================================================================
# ExtractionResult — top-level model
# ===================================================================

class TestExtractionResult:
    """Covers the ExtractionResult aggregate model and round-trip."""

    def test_all_fields_default_empty(self):
        er = ExtractionResult()
        assert er.characters == []
        assert er.locations == []
        assert er.events == []
        assert er.relationships == []
        assert er.themes == []
        assert er.factions == []

    def test_from_json(self):
        """Should deserialize from JSON (as Claude would return)."""
        data = {
            "characters": [{"name": "Scrooge", "first_chapter": 1}],
            "locations": [{"name": "London", "first_chapter": 1}],
            "events": [{"description": "Ghost appears", "chapter": 1}],
            "relationships": [
                {"source_name": "Scrooge", "target_name": "Bob", "relation_type": "employs", "first_chapter": 1}
            ],
            "themes": [{"name": "Redemption", "first_chapter": 1}],
            "factions": [{"name": "Ghosts", "first_chapter": 2}],
        }
        er = ExtractionResult.model_validate(data)
        assert len(er.characters) == 1
        assert len(er.locations) == 1
        assert len(er.events) == 1
        assert len(er.relationships) == 1
        assert len(er.themes) == 1
        assert len(er.factions) == 1


# ===================================================================
# ExtractionResult.to_datapoints() — conversion + resolution
# ===================================================================

class TestToDatapoints:
    """Covers ExtractionResult.to_datapoints cross-reference resolution."""

    @pytest.fixture
    def full_extraction(self) -> ExtractionResult:
        return ExtractionResult(
            characters=[
                CharacterExtraction(
                    name="Scrooge",
                    aliases=["Ebenezer"],
                    description="A cold miser",
                    first_chapter=1,
                    chapters_present=[1, 2, 3, 4, 5],
                ),
                CharacterExtraction(
                    name="Bob Cratchit",
                    aliases=["Bob"],
                    description="Scrooge's clerk",
                    first_chapter=1,
                    chapters_present=[1, 3, 5],
                ),
                CharacterExtraction(
                    name="Tiny Tim",
                    first_chapter=3,
                    chapters_present=[3, 5],
                ),
            ],
            locations=[
                LocationExtraction(name="London", description="The city", first_chapter=1),
                LocationExtraction(name="Counting-house", first_chapter=1),
            ],
            factions=[
                FactionExtraction(
                    name="Cratchit Family",
                    first_chapter=3,
                    member_names=["Bob Cratchit", "Tiny Tim"],
                ),
            ],
            events=[
                EventExtraction(
                    description="Scrooge is visited by Marley's ghost",
                    chapter=1,
                    participant_names=["Scrooge"],
                    location_name="Counting-house",
                ),
            ],
            relationships=[
                RelationshipExtraction(
                    source_name="Scrooge",
                    target_name="Bob Cratchit",
                    relation_type="employs",
                    description="Scrooge employs Bob as his clerk",
                    first_chapter=1,
                ),
            ],
            themes=[
                ThemeExtraction(
                    name="Redemption",
                    description="Scrooge's transformation",
                    first_chapter=1,
                    related_character_names=["Scrooge"],
                ),
            ],
        )

    def test_returns_list_of_datapoints(self, full_extraction):
        from cognee.infrastructure.engine import DataPoint
        dps = full_extraction.to_datapoints()
        assert isinstance(dps, list)
        assert all(isinstance(dp, DataPoint) for dp in dps)

    def test_correct_total_count(self, full_extraction):
        dps = full_extraction.to_datapoints()
        # 3 characters + 2 locations + 1 faction + 1 event + 1 relationship + 1 theme = 9
        assert len(dps) == 9

    def test_characters_converted(self, full_extraction):
        dps = full_extraction.to_datapoints()
        chars = [dp for dp in dps if isinstance(dp, Character)]
        assert len(chars) == 3
        names = {c.name for c in chars}
        assert names == {"Scrooge", "Bob Cratchit", "Tiny Tim"}

    def test_character_fields_preserved(self, full_extraction):
        dps = full_extraction.to_datapoints()
        scrooge = next(dp for dp in dps if isinstance(dp, Character) and dp.name == "Scrooge")
        assert scrooge.aliases == ["Ebenezer"]
        assert scrooge.description == "A cold miser"
        assert scrooge.first_chapter == 1
        assert scrooge.chapters_present == [1, 2, 3, 4, 5]

    def test_locations_converted(self, full_extraction):
        dps = full_extraction.to_datapoints()
        locs = [dp for dp in dps if isinstance(dp, Location)]
        assert len(locs) == 2

    def test_faction_members_resolved(self, full_extraction):
        dps = full_extraction.to_datapoints()
        factions = [dp for dp in dps if isinstance(dp, Faction)]
        assert len(factions) == 1
        f = factions[0]
        assert f.name == "Cratchit Family"
        member_names = {m.name for m in f.members}
        assert member_names == {"Bob Cratchit", "Tiny Tim"}

    def test_event_participants_resolved(self, full_extraction):
        dps = full_extraction.to_datapoints()
        events = [dp for dp in dps if isinstance(dp, PlotEvent)]
        assert len(events) == 1
        e = events[0]
        assert len(e.participants) == 1
        assert e.participants[0].name == "Scrooge"

    def test_event_location_resolved(self, full_extraction):
        dps = full_extraction.to_datapoints()
        events = [dp for dp in dps if isinstance(dp, PlotEvent)]
        e = events[0]
        assert e.location is not None
        assert e.location.name == "Counting-house"

    def test_relationship_source_target_resolved(self, full_extraction):
        dps = full_extraction.to_datapoints()
        rels = [dp for dp in dps if isinstance(dp, Relationship)]
        assert len(rels) == 1
        r = rels[0]
        assert r.source.name == "Scrooge"
        assert r.target.name == "Bob Cratchit"
        assert r.relation_type == "employs"

    def test_theme_related_characters_resolved(self, full_extraction):
        dps = full_extraction.to_datapoints()
        themes = [dp for dp in dps if isinstance(dp, Theme)]
        assert len(themes) == 1
        t = themes[0]
        assert len(t.related_characters) == 1
        assert t.related_characters[0].name == "Scrooge"

    def test_deterministic_uuids(self, full_extraction):
        """Same input should produce same UUIDs (uuid5 is deterministic)."""
        dps1 = full_extraction.to_datapoints()
        dps2 = full_extraction.to_datapoints()

        ids1 = sorted(str(dp.id) for dp in dps1)
        ids2 = sorted(str(dp.id) for dp in dps2)
        assert ids1 == ids2

    def test_character_uuid_formula(self, full_extraction):
        dps = full_extraction.to_datapoints()
        scrooge = next(dp for dp in dps if isinstance(dp, Character) and dp.name == "Scrooge")
        expected_id = uuid.uuid5(uuid.NAMESPACE_DNS, "character:Scrooge")
        assert scrooge.id == expected_id

    def test_unresolved_relationship_skipped(self):
        """Relationships with unknown source/target should be silently skipped."""
        er = ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
            relationships=[
                RelationshipExtraction(
                    source_name="Scrooge",
                    target_name="NonExistentCharacter",
                    relation_type="loves",
                    first_chapter=1,
                )
            ],
        )
        dps = er.to_datapoints()
        rels = [dp for dp in dps if isinstance(dp, Relationship)]
        assert len(rels) == 0  # skipped because target not found

    def test_unresolved_faction_member_skipped(self):
        """Faction members not in characters list should be silently skipped."""
        er = ExtractionResult(
            characters=[CharacterExtraction(name="Scrooge", first_chapter=1)],
            factions=[
                FactionExtraction(
                    name="Team",
                    first_chapter=1,
                    member_names=["Scrooge", "Ghost"],  # Ghost not in characters
                )
            ],
        )
        dps = er.to_datapoints()
        factions = [dp for dp in dps if isinstance(dp, Faction)]
        assert len(factions[0].members) == 1  # only Scrooge

    def test_unresolved_event_location_is_none(self):
        er = ExtractionResult(
            characters=[],
            events=[
                EventExtraction(
                    description="Something happened",
                    chapter=1,
                    location_name="NonExistentPlace",
                )
            ],
        )
        dps = er.to_datapoints()
        events = [dp for dp in dps if isinstance(dp, PlotEvent)]
        assert events[0].location is None

    def test_empty_extraction_result(self):
        er = ExtractionResult()
        dps = er.to_datapoints()
        assert dps == []

    def test_event_with_no_location_name(self):
        er = ExtractionResult(
            events=[EventExtraction(description="test", chapter=1, location_name=None)],
        )
        dps = er.to_datapoints()
        events = [dp for dp in dps if isinstance(dp, PlotEvent)]
        assert events[0].location is None


# ===================================================================
# Schema alignment with CLAUDE.md spec
# ===================================================================

class TestMetadataIsolation:
    """
    metadata uses Field(default_factory=...) so each instance gets its own dict.
    Mutating one instance's metadata must not affect another.
    """

    def test_character_metadata_isolation(self):
        c1 = Character(name="A", first_chapter=1)
        c2 = Character(name="B", first_chapter=2)
        c1.metadata["extra"] = True
        assert "extra" not in c2.metadata

    def test_location_metadata_isolation(self):
        l1 = Location(name="A", first_chapter=1)
        l2 = Location(name="B", first_chapter=2)
        l1.metadata["extra"] = True
        assert "extra" not in l2.metadata

    def test_faction_metadata_isolation(self):
        f1 = Faction(name="A", first_chapter=1)
        f2 = Faction(name="B", first_chapter=2)
        f1.metadata["extra"] = True
        assert "extra" not in f2.metadata

    def test_plot_event_metadata_isolation(self):
        e1 = PlotEvent(description="a", chapter=1)
        e2 = PlotEvent(description="b", chapter=2)
        e1.metadata["extra"] = True
        assert "extra" not in e2.metadata

    def test_relationship_metadata_isolation(self):
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        r1 = Relationship(source=src, target=tgt, relation_type="x", first_chapter=1)
        r2 = Relationship(source=src, target=tgt, relation_type="y", first_chapter=2)
        r1.metadata["extra"] = True
        assert "extra" not in r2.metadata

    def test_theme_metadata_isolation(self):
        t1 = Theme(name="A", first_chapter=1)
        t2 = Theme(name="B", first_chapter=2)
        t1.metadata["extra"] = True
        assert "extra" not in t2.metadata


class TestSchemaAlignmentWithSpec:
    """
    Verify field-by-field alignment with CLAUDE.md DataPoint Models (Draft) section.
    """

    def test_character_fields_match_spec(self):
        fields = set(Character.model_fields.keys())
        expected = {"name", "aliases", "description", "first_chapter", "chapters_present", "metadata", "id"}
        assert expected.issubset(fields)

    def test_location_fields_match_spec(self):
        fields = set(Location.model_fields.keys())
        expected = {"name", "description", "first_chapter", "metadata", "id"}
        assert expected.issubset(fields)

    def test_faction_fields_match_spec(self):
        fields = set(Faction.model_fields.keys())
        expected = {"name", "description", "first_chapter", "members", "metadata", "id"}
        assert expected.issubset(fields)

    def test_plot_event_fields_match_spec(self):
        fields = set(PlotEvent.model_fields.keys())
        expected = {"description", "chapter", "participants", "location", "metadata", "id"}
        assert expected.issubset(fields)

    def test_relationship_fields_match_spec(self):
        fields = set(Relationship.model_fields.keys())
        expected = {"source", "target", "relation_type", "description", "first_chapter", "metadata", "id"}
        assert expected.issubset(fields)

    def test_theme_fields_match_spec(self):
        fields = set(Theme.model_fields.keys())
        expected = {"name", "description", "first_chapter", "related_characters", "metadata", "id"}
        assert expected.issubset(fields)


class TestLastKnownChapter:
    """Every temporally-scoped DataPoint carries last_known_chapter."""

    def test_character_has_last_known_chapter(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1, last_known_chapter=3)
        assert c.last_known_chapter == 3

    def test_last_known_chapter_defaults_to_first_chapter(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1)
        assert c.last_known_chapter == 1

    def test_location_faction_theme_relationship_all_have_it(self):
        from models.datapoints import Location, Faction, Theme, Relationship, Character
        assert Location(name="L", first_chapter=2).last_known_chapter == 2
        assert Faction(name="F", first_chapter=2).last_known_chapter == 2
        assert Theme(name="T", first_chapter=2).last_known_chapter == 2
        a = Character(name="A", first_chapter=1)
        b = Character(name="B", first_chapter=1)
        r = Relationship(source=a, target=b, relation_type="x", first_chapter=2)
        assert r.last_known_chapter == 2


class TestSourceChunkOrdinal:
    """Test source_chunk_ordinal field on DataPoints and propagation through to_datapoints."""

    def test_character_accepts_source_chunk_ordinal(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1, source_chunk_ordinal=7)
        assert c.source_chunk_ordinal == 7

    def test_character_source_chunk_ordinal_defaults_to_none(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1)
        assert c.source_chunk_ordinal is None

    def test_plotevent_accepts_source_chunk_ordinal(self):
        from models.datapoints import PlotEvent
        e = PlotEvent(description="x", chapter=1, source_chunk_ordinal=3)
        assert e.source_chunk_ordinal == 3

    def test_extraction_result_to_datapoints_stamps_ordinal(self):
        from models.datapoints import ExtractionResult, CharacterExtraction
        r = ExtractionResult(characters=[CharacterExtraction(name="A", first_chapter=1)])
        dps = r.to_datapoints(source_chunk_ordinal=12)
        assert all(getattr(dp, "source_chunk_ordinal", None) == 12 for dp in dps)


class TestExtractionLastKnownChapter:
    """LLM extraction models accept last_known_chapter and default to first_chapter."""

    def test_character_extraction_accepts_field(self):
        from models.datapoints import CharacterExtraction
        c = CharacterExtraction(name="Scrooge", first_chapter=1, last_known_chapter=3)
        assert c.last_known_chapter == 3

    def test_extraction_default_equals_first_chapter(self):
        from models.datapoints import (
            CharacterExtraction, LocationExtraction, FactionExtraction,
            ThemeExtraction, RelationshipExtraction,
        )
        assert CharacterExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert LocationExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert FactionExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert ThemeExtraction(name="X", first_chapter=2).last_known_chapter == 2
        assert RelationshipExtraction(
            source_name="a", target_name="b", relation_type="x", first_chapter=2
        ).last_known_chapter == 2


class TestToDatapointsPreservesLastKnownChapter:
    """Asserts to_datapoints() copies last_known_chapter onto every persisted DataPoint."""

    def test_character_last_known_chapter_copied(self):
        from models.datapoints import ExtractionResult, CharacterExtraction
        result = ExtractionResult(characters=[
            CharacterExtraction(name="Scrooge", first_chapter=1, last_known_chapter=4)
        ])
        dps = result.to_datapoints()
        char = next(d for d in dps if d.__class__.__name__ == "Character")
        assert char.last_known_chapter == 4

    def test_all_types_preserve_last_known_chapter(self):
        from models.datapoints import (
            ExtractionResult, CharacterExtraction, LocationExtraction,
            FactionExtraction, ThemeExtraction, RelationshipExtraction,
        )
        result = ExtractionResult(
            characters=[
                CharacterExtraction(name="A", first_chapter=1, last_known_chapter=5),
                CharacterExtraction(name="B", first_chapter=1, last_known_chapter=5),
            ],
            locations=[LocationExtraction(name="L", first_chapter=2, last_known_chapter=6)],
            factions=[FactionExtraction(name="F", first_chapter=3, last_known_chapter=7)],
            themes=[ThemeExtraction(name="T", first_chapter=4, last_known_chapter=8)],
            relationships=[RelationshipExtraction(
                source_name="A", target_name="B", relation_type="loves",
                first_chapter=2, last_known_chapter=9,
            )],
        )
        dps = {d.__class__.__name__: d for d in result.to_datapoints() if d.__class__.__name__ != "Character"}
        assert dps["Location"].last_known_chapter == 6
        assert dps["Faction"].last_known_chapter == 7
        assert dps["Theme"].last_known_chapter == 8
        assert dps["Relationship"].last_known_chapter == 9


# ===========================================================================
# Item 11 (Phase A Stage 1): RelationshipType enum + signed valence
# ===========================================================================


class TestRelationshipTypeEnum:
    """Covers RelationshipType enum values and lowercase invariant."""

    def test_enum_has_ten_canonical_types(self):
        from models.datapoints import RelationshipType
        assert set(v.value for v in RelationshipType) == {
            "family", "romantic", "friend", "ally", "mentor",
            "subordinate", "rival", "enemy", "acquaintance", "unknown",
        }

    def test_enum_values_are_lowercase(self):
        from models.datapoints import RelationshipType
        assert all(v.value == v.value.lower() for v in RelationshipType)


class TestRelationshipValence:
    """Covers signed valence range and confidence defaults on Relationship DataPoint."""

    def test_valence_default_zero(self):
        from models.datapoints import Relationship, Character
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        r = Relationship(source=src, target=tgt, relation_type="ally", first_chapter=1)
        assert r.valence == 0.0
        assert r.confidence == 1.0

    def test_valence_rejects_out_of_bounds_high(self):
        import pytest
        from models.datapoints import Relationship, Character
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        with pytest.raises(ValueError):
            Relationship(
                source=src, target=tgt, relation_type="ally",
                first_chapter=1, valence=1.5,
            )

    def test_valence_rejects_out_of_bounds_low(self):
        import pytest
        from models.datapoints import Relationship, Character
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        with pytest.raises(ValueError):
            Relationship(
                source=src, target=tgt, relation_type="ally",
                first_chapter=1, valence=-1.1,
            )

    def test_valence_accepts_anchors(self):
        from models.datapoints import Relationship, Character
        src = Character(name="A", first_chapter=1)
        tgt = Character(name="B", first_chapter=1)
        for v in (-1.0, -0.5, 0.0, 0.5, 1.0):
            r = Relationship(
                source=src, target=tgt, relation_type="ally",
                first_chapter=1, valence=v,
            )
            assert r.valence == v


class TestRelationshipExtractionValence:
    """Asserts RelationshipExtraction propagates valence/confidence into DataPoints."""

    def test_extraction_defaults(self):
        from models.datapoints import RelationshipExtraction
        r = RelationshipExtraction(
            source_name="A", target_name="B", relation_type="ally", first_chapter=1,
        )
        assert r.valence == 0.0
        assert r.confidence == 1.0

    def test_to_datapoints_propagates_valence(self):
        from models.datapoints import (
            CharacterExtraction, RelationshipExtraction, ExtractionResult,
            Relationship,
        )
        ex = ExtractionResult(
            characters=[
                CharacterExtraction(name="A", first_chapter=1),
                CharacterExtraction(name="B", first_chapter=1),
            ],
            relationships=[RelationshipExtraction(
                source_name="A", target_name="B", relation_type="enemy",
                first_chapter=1, valence=-0.8, confidence=0.9,
            )],
        )
        dps = ex.to_datapoints()
        rel = next(d for d in dps if isinstance(d, Relationship))
        assert rel.valence == -0.8
        assert rel.confidence == 0.9


# ===========================================================================
# Item 8 (Phase A Stage 1): BookNLP cluster_id on Character
# ===========================================================================


class TestCharacterCorefId:
    """Asserts Character carries the BookNLP coref cluster id through extraction."""

    def test_character_has_booknlp_coref_id_field(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1, booknlp_coref_id=42)
        assert c.booknlp_coref_id == 42

    def test_character_coref_id_defaults_to_none(self):
        from models.datapoints import Character
        c = Character(name="Scrooge", first_chapter=1)
        assert c.booknlp_coref_id is None

    def test_extraction_propagates_coref_id(self):
        from models.datapoints import (
            CharacterExtraction, ExtractionResult, Character,
        )
        ex = ExtractionResult(
            characters=[CharacterExtraction(
                name="Scrooge", first_chapter=1, booknlp_coref_id=42,
            )],
        )
        dps = ex.to_datapoints()
        char = next(d for d in dps if isinstance(d, Character))
        assert char.booknlp_coref_id == 42


# ===========================================================================
# Item 12 (Phase A Stage 1): ExtractionResult version metadata
# ===========================================================================


class TestExtractionResultMetadata:
    """Covers ExtractionResult provenance fields (extractor_version, prompt_hash, etc.)."""

    def test_metadata_defaults_empty(self):
        from models.datapoints import ExtractionResult
        er = ExtractionResult()
        assert er.extractor_version == ""
        assert er.prompt_hash == ""
        assert er.model_id == ""
        assert er.schema_version == "v1"
        assert er.cache_key == ""
        assert er.created_at is None

    def test_metadata_roundtrip(self):
        from datetime import datetime, timezone
        from models.datapoints import ExtractionResult
        now = datetime.now(timezone.utc)
        er = ExtractionResult(
            extractor_version="phase-a@2026-04-22",
            prompt_hash="deadbeef",
            model_id="openai/gpt-4o-mini",
            schema_version="v2",
            cache_key="abc123",
            created_at=now,
        )
        assert er.extractor_version == "phase-a@2026-04-22"
        assert er.created_at == now

    def test_metadata_json_roundtrip(self):
        from datetime import datetime, timezone
        from models.datapoints import ExtractionResult
        now = datetime.now(timezone.utc)
        er = ExtractionResult(
            extractor_version="phase-a@2026-04-22",
            prompt_hash="deadbeef",
            model_id="openai/gpt-4o-mini",
            schema_version="v1",
            cache_key="abc123",
            created_at=now,
        )
        restored = ExtractionResult.model_validate_json(er.model_dump_json())
        assert restored.extractor_version == er.extractor_version
        assert restored.created_at == er.created_at


# ===========================================================================
# Item 9 (Phase A Stage 2): PlotEvent.realis
# ===========================================================================


class TestPlotEventRealis:
    """Covers PlotEvent.realis enum (actual/generic/other) and extraction propagation."""

    def test_realis_defaults_to_actual(self):
        from models.datapoints import PlotEvent
        ev = PlotEvent(description="Scrooge slammed the door.", chapter=1)
        assert ev.realis == "actual"

    def test_realis_accepts_three_values(self):
        from models.datapoints import PlotEvent
        for v in ("actual", "generic", "other"):
            ev = PlotEvent(description="x", chapter=1, realis=v)
            assert ev.realis == v

    def test_realis_rejects_other_values(self):
        import pytest
        from models.datapoints import PlotEvent
        with pytest.raises(ValueError):
            PlotEvent(description="x", chapter=1, realis="hypothetical")

    def test_extraction_propagates_realis(self):
        from models.datapoints import (
            EventExtraction, ExtractionResult, PlotEvent,
        )
        ex = ExtractionResult(
            events=[EventExtraction(
                description="He dreamed of a palace.", chapter=1, realis="other",
            )],
        )
        dps = ex.to_datapoints()
        ev = next(d for d in dps if isinstance(d, PlotEvent))
        assert ev.realis == "other"


# ===========================================================================
# Slice 3 — Unicode + path edges
# ===========================================================================


class TestUnicodeAndPathEdges:
    """Slice 3: real books contain curly apostrophes, em dashes, cyrillic,
    zero-width joiners. Datapoints must preserve these bytes through
    construction and JSON round-trips."""

    def test_character_name_curly_apostrophe(self):
        """U+2019 RIGHT SINGLE QUOTATION MARK must survive model construction
        and JSON dump."""
        name = "D’Artagnan"  # curly apostrophe
        c = CharacterExtraction(name=name, description="", first_chapter=1)
        assert c.name == name
        dumped = c.model_dump_json()
        assert "’" in dumped or "\\u2019" in dumped

    def test_character_name_em_dash(self):
        """U+2014 EM DASH must survive on both name and description."""
        name = "Mr. X—the stranger"
        c = CharacterExtraction(name=name, description="A man—mysterious.", first_chapter=1)
        assert "—" in c.name
        assert "—" in c.description

    def test_location_name_cyrillic(self):
        """Non-ASCII (cyrillic) must pass through Location construction unchanged."""
        loc = LocationExtraction(name="Соня", first_chapter=1)  # Соня
        assert loc.name == "Соня"
        # Round-trip through JSON to confirm no mojibake
        restored = LocationExtraction.model_validate_json(loc.model_dump_json())
        assert restored.name == "Соня"

    def test_character_name_zero_width_joiner_preserved(self):
        """U+200D ZERO WIDTH JOINER must not be stripped — emoji sequences and
        some complex scripts rely on it."""
        name = "a‍z"  # two letters joined by ZWJ
        c = CharacterExtraction(name=name, description="", first_chapter=1)
        assert c.name == name
        assert "‍" in c.name
        # Round-trip preserves exact byte content
        restored = CharacterExtraction.model_validate_json(c.model_dump_json())
        assert restored.name == name

    def test_extraction_result_json_roundtrip_preserves_unicode(self):
        """Full ExtractionResult round-trip preserves curly apostrophe, em dash,
        cyrillic, and ZWJ on every field that contains them."""
        er = ExtractionResult(
            characters=[CharacterExtraction(
                name="D’Artagnan",
                description="A Gascon—young and bold.",
                first_chapter=1,
            )],
            locations=[LocationExtraction(
                name="Соня",
                first_chapter=1,
            )],
            themes=[ThemeExtraction(
                name="family a‍z",
                first_chapter=1,
            )],
        )
        restored = ExtractionResult.model_validate_json(er.model_dump_json())
        assert restored.characters[0].name == "D’Artagnan"
        assert "—" in restored.characters[0].description
        assert restored.locations[0].name == "Соня"
        assert "‍" in restored.themes[0].name

    def test_extraction_result_json_roundtrip_idempotent(self):
        """Dumping an ExtractionResult, loading it back, and dumping again
        must yield byte-identical JSON."""
        er = ExtractionResult(
            characters=[CharacterExtraction(
                name="D’Artagnan",
                description="A Gascon.",
                first_chapter=1,
            )],
        )
        first = er.model_dump_json()
        restored = ExtractionResult.model_validate_json(first)
        second = restored.model_dump_json()
        assert first == second, (
            "round-trip must be idempotent; dump→load→dump should produce "
            "byte-identical output"
        )
