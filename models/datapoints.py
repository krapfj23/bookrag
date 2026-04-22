"""
Custom Cognee DataPoint models for the BookRAG knowledge graph.

DataPoints define the graph schema stored in Kuzu (graph) and LanceDB (vectors).
metadata["index_fields"] controls which fields get embedded in the vector DB.
Relationships between entities are expressed via typed fields referencing other DataPoints.

Also contains LLM extraction models (Pydantic BaseModel, NOT DataPoints) and a
converter from extraction output to DataPoints.
"""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from cognee.infrastructure.engine import DataPoint


# ===========================================================================
# RelationshipType — canonical narrative relationship enum
# ===========================================================================


class RelationshipType(str, Enum):
    """Canonical narrative relationship categories.

    Kept small (10 entries) so the LLM reliably picks a best fit in
    structured output. MENTOR/SUBORDINATE encode direction in (source,
    target); FAMILY/ROMANTIC/ENEMY/RIVAL are symmetric. Phase A Stage 1 / Item 11.
    """

    FAMILY       = "family"
    ROMANTIC     = "romantic"
    FRIEND       = "friend"
    ALLY         = "ally"
    MENTOR       = "mentor"
    SUBORDINATE  = "subordinate"
    RIVAL        = "rival"
    ENEMY        = "enemy"
    ACQUAINTANCE = "acquaintance"
    UNKNOWN      = "unknown"


# ===========================================================================
# Provenance — evidence for every extraction claim
# ===========================================================================


class Provenance(BaseModel):
    """Evidence for an extracted entity/event/relationship.

    Emitted by the LLM alongside each DataPoint so downstream validators
    can confirm the extraction is grounded in actual chunk text (not
    hallucinated). See pipeline.cognee_pipeline._validate_provenance for
    the consumer. Phase A Stage 1 / Item 2.
    """

    chunk_id: str = Field(..., description="<book_id>::chunk_<ordinal:04d>")
    quote: str = Field(..., description="Verbatim snippet from chunk text, <=200 chars")
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., ge=0)

    @field_validator("quote")
    @classmethod
    def _quote_bounded(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError(f"quote must be <=200 chars, got {len(v)}")
        return v


# ===========================================================================
# DataPoint models — stored in Kuzu + LanceDB
# ===========================================================================


class Character(DataPoint):
    name: str
    aliases: list[str] = []
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = None
    chapters_present: list[int] = []
    source_chunk_ordinal: int | None = None
    provenance: list[Provenance] = []
    metadata: dict = {"index_fields": ["name", "description"]}

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class Location(DataPoint):
    name: str
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = None
    source_chunk_ordinal: int | None = None
    provenance: list[Provenance] = []
    metadata: dict = {"index_fields": ["name", "description"]}

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class Faction(DataPoint):
    name: str
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = None
    members: list[Character] = []
    source_chunk_ordinal: int | None = None
    provenance: list[Provenance] = []
    metadata: dict = {"index_fields": ["name"]}

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class PlotEvent(DataPoint):
    description: str
    chapter: int
    participants: list[Character] = []
    location: Location | None = None
    source_chunk_ordinal: int | None = None
    provenance: list[Provenance] = []
    metadata: dict = {"index_fields": ["description"]}


class Relationship(DataPoint):
    source: Character
    target: Character
    relation_type: str  # backward compat: accepts free strings; new extractions use RelationshipType values
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = None
    source_chunk_ordinal: int | None = None
    provenance: list[Provenance] = []
    # Item 11 (Phase A Stage 1): signed valence + confidence.
    # valence anchored: -1 murderous hatred, 0 neutral, +1 devoted love.
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict = {"index_fields": ["relation_type", "description"]}

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class Theme(DataPoint):
    name: str
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = None
    related_characters: list[Character] = []
    source_chunk_ordinal: int | None = None
    provenance: list[Provenance] = []
    metadata: dict = {"index_fields": ["name", "description"]}

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


# ===========================================================================
# LLM Extraction models — Pydantic BaseModel (NOT DataPoints)
#
# These mirror the DataPoint fields but are plain Pydantic models suitable
# for use as a structured output response_model with Cognee's LLMGateway.
# ===========================================================================


class CharacterExtraction(BaseModel):
    """A character extracted by the LLM from a text chunk."""
    name: str
    aliases: list[str] = []
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = Field(
        default=None,
        description="Latest chapter (in this extraction batch) whose text contributed to this entity's description. Defaults to first_chapter when omitted.",
    )
    chapters_present: list[int] = []
    provenance: list[Provenance] = []

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class LocationExtraction(BaseModel):
    """A location extracted by the LLM."""
    name: str
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = Field(
        default=None,
        description="Latest chapter (in this extraction batch) whose text contributed to this entity's description. Defaults to first_chapter when omitted.",
    )
    provenance: list[Provenance] = []

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class FactionExtraction(BaseModel):
    """A faction or group extracted by the LLM."""
    name: str
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = Field(
        default=None,
        description="Latest chapter (in this extraction batch) whose text contributed to this entity's description. Defaults to first_chapter when omitted.",
    )
    member_names: list[str] = Field(
        default=[],
        description="Names of characters who belong to this faction",
    )
    provenance: list[Provenance] = []

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class EventExtraction(BaseModel):
    """A plot event extracted by the LLM."""
    description: str
    chapter: int
    participant_names: list[str] = Field(
        default=[],
        description="Names of characters involved in this event",
    )
    location_name: str | None = Field(
        default=None,
        description="Name of the location where the event occurs",
    )
    provenance: list[Provenance] = []


class RelationshipExtraction(BaseModel):
    """A relationship between two characters."""
    source_name: str
    target_name: str
    relation_type: str = Field(
        description=(
            "One of: family, romantic, friend, ally, mentor, subordinate, "
            "rival, enemy, acquaintance, unknown. See RelationshipType."
        ),
    )
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = Field(
        default=None,
        description="Latest chapter (in this extraction batch) whose text contributed to this entity's description. Defaults to first_chapter when omitted.",
    )
    provenance: list[Provenance] = []
    valence: float = Field(
        default=0.0, ge=-1.0, le=1.0,
        description="-1 murderous, 0 neutral, +1 devoted love",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class ThemeExtraction(BaseModel):
    """A theme identified by the LLM."""
    name: str
    description: str | None = None
    first_chapter: int
    last_known_chapter: int | None = Field(
        default=None,
        description="Latest chapter (in this extraction batch) whose text contributed to this entity's description. Defaults to first_chapter when omitted.",
    )
    related_character_names: list[str] = []
    provenance: list[Provenance] = []

    @model_validator(mode="after")
    def _default_last_known_chapter(self):
        if self.last_known_chapter is None:
            self.last_known_chapter = self.first_chapter
        return self


class ExtractionResult(BaseModel):
    """
    Top-level structured output returned by the LLM.

    This is what Claude returns via LLMGateway.acreate_structured_output.
    Use to_datapoints() to convert into actual DataPoints for Cognee storage.
    """

    characters: list[CharacterExtraction] = []
    locations: list[LocationExtraction] = []
    events: list[EventExtraction] = []
    relationships: list[RelationshipExtraction] = []
    themes: list[ThemeExtraction] = []
    factions: list[FactionExtraction] = []

    def to_datapoints(self, source_chunk_ordinal: int | None = None) -> list[DataPoint]:
        """
        Convert the flat LLM extraction output into interconnected DataPoints.

        Resolves cross-references by name: e.g. an EventExtraction with
        participant_names=["Scrooge"] gets linked to the Character DataPoint
        for Scrooge.
        """
        datapoints: list[DataPoint] = []

        # --- Build Characters first (everything else references them by name) ---
        char_map: dict[str, Character] = {}
        for c in self.characters:
            dp = Character(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"character:{c.name}"),
                name=c.name,
                aliases=c.aliases,
                description=c.description,
                first_chapter=c.first_chapter,
                last_known_chapter=c.last_known_chapter,
                chapters_present=c.chapters_present,
                source_chunk_ordinal=source_chunk_ordinal,
                provenance=list(c.provenance),
            )
            char_map[c.name] = dp
            datapoints.append(dp)

        # --- Locations ---
        loc_map: dict[str, Location] = {}
        for loc in self.locations:
            dp = Location(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"location:{loc.name}"),
                name=loc.name,
                description=loc.description,
                first_chapter=loc.first_chapter,
                last_known_chapter=loc.last_known_chapter,
                source_chunk_ordinal=source_chunk_ordinal,
                provenance=list(loc.provenance),
            )
            loc_map[loc.name] = dp
            datapoints.append(dp)

        # --- Factions ---
        for f in self.factions:
            members = [char_map[n] for n in f.member_names if n in char_map]
            dp = Faction(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"faction:{f.name}"),
                name=f.name,
                description=f.description,
                first_chapter=f.first_chapter,
                last_known_chapter=f.last_known_chapter,
                members=members,
                source_chunk_ordinal=source_chunk_ordinal,
                provenance=list(f.provenance),
            )
            datapoints.append(dp)

        # --- Plot Events ---
        for i, ev in enumerate(self.events):
            participants = [char_map[n] for n in ev.participant_names if n in char_map]
            location = loc_map.get(ev.location_name) if ev.location_name else None
            desc_slug = ev.description[:60] if ev.description else f"unnamed_{i}"
            dp = PlotEvent(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"event:{ev.chapter}:{desc_slug}"),
                description=ev.description,
                chapter=ev.chapter,
                participants=participants,
                location=location,
                source_chunk_ordinal=source_chunk_ordinal,
                provenance=list(ev.provenance),
            )
            datapoints.append(dp)

        # --- Relationships ---
        for rel in self.relationships:
            source = char_map.get(rel.source_name)
            target = char_map.get(rel.target_name)
            if not source or not target:
                continue  # skip unresolved references
            dp = Relationship(
                id=uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"rel:{rel.source_name}:{rel.relation_type}:{rel.target_name}",
                ),
                source=source,
                target=target,
                relation_type=rel.relation_type,
                description=rel.description,
                first_chapter=rel.first_chapter,
                last_known_chapter=rel.last_known_chapter,
                source_chunk_ordinal=source_chunk_ordinal,
                provenance=list(rel.provenance),
                valence=rel.valence,
                confidence=rel.confidence,
            )
            datapoints.append(dp)

        # --- Themes ---
        for th in self.themes:
            related = [char_map[n] for n in th.related_character_names if n in char_map]
            dp = Theme(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"theme:{th.name}"),
                name=th.name,
                description=th.description,
                first_chapter=th.first_chapter,
                last_known_chapter=th.last_known_chapter,
                related_characters=related,
                source_chunk_ordinal=source_chunk_ordinal,
                provenance=list(th.provenance),
            )
            datapoints.append(dp)

        return datapoints
