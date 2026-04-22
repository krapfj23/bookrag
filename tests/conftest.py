"""
Shared fixtures for BookRAG tests.

Provides realistic BookNLP output fixtures modeled on A Christmas Carol
(the project's test book per CLAUDE.md).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock cognee before any test imports datapoints.py
# ---------------------------------------------------------------------------

def _install_cognee_mock():
    """Install a mock cognee package so models/datapoints.py can import DataPoint."""
    if "cognee" not in sys.modules:
        # Build a minimal cognee mock with DataPoint as a Pydantic BaseModel
        from pydantic import BaseModel, Field
        import uuid as _uuid

        class _DataPoint(BaseModel):
            id: _uuid.UUID = Field(default_factory=_uuid.uuid4)

            class Config:
                arbitrary_types_allowed = True

        cognee = types.ModuleType("cognee")
        cognee_infra = types.ModuleType("cognee.infrastructure")
        cognee_engine = types.ModuleType("cognee.infrastructure.engine")
        cognee_engine.DataPoint = _DataPoint

        # LLMGateway mock — cognee_pipeline.py imports this
        cognee_llm = types.ModuleType("cognee.infrastructure.llm")
        cognee_llm_gw = types.ModuleType("cognee.infrastructure.llm.LLMGateway")
        cognee_llm_gw.LLMGateway = MagicMock()
        cognee_llm.LLMGateway = cognee_llm_gw

        # Pipeline mocks
        cognee_modules = types.ModuleType("cognee.modules")
        cognee_pipelines = types.ModuleType("cognee.modules.pipelines")
        cognee_pipelines.run_pipeline = MagicMock()
        cognee_pipelines_tasks = types.ModuleType("cognee.modules.pipelines.tasks")
        cognee_pipelines_tasks_task = types.ModuleType("cognee.modules.pipelines.tasks.task")
        cognee_pipelines_tasks_task.Task = MagicMock()

        # Storage mock
        cognee_tasks = types.ModuleType("cognee.tasks")
        cognee_storage = types.ModuleType("cognee.tasks.storage")
        cognee_storage.add_data_points = AsyncMock(return_value=None)

        # Search mocks — used by validation/test_suite.py
        cognee_search = types.ModuleType("cognee.modules.search")
        cognee_search_types = types.ModuleType("cognee.modules.search.types")

        class _SearchType:
            GRAPH_COMPLETION = "GRAPH_COMPLETION"
            CHUNKS = "CHUNKS"
            SUMMARIES = "SUMMARIES"
            CYPHER = "CYPHER"
            RAG_COMPLETION = "RAG_COMPLETION"

        cognee_search_types.SearchType = _SearchType
        cognee_search.types = cognee_search_types

        cognee.search = AsyncMock(return_value=[])

        # cognee.config — mocked so configure_cognee exercises the real code path
        cognee_config = types.ModuleType("cognee.config")
        cognee_config.set_llm_config = MagicMock()
        cognee.config = cognee_config
        sys.modules["cognee.config"] = cognee_config

        sys.modules["cognee"] = cognee
        sys.modules["cognee.infrastructure"] = cognee_infra
        sys.modules["cognee.infrastructure.engine"] = cognee_engine
        sys.modules["cognee.infrastructure.llm"] = cognee_llm
        sys.modules["cognee.infrastructure.llm.LLMGateway"] = cognee_llm_gw
        sys.modules["cognee.modules"] = cognee_modules
        sys.modules["cognee.modules.pipelines"] = cognee_pipelines
        sys.modules["cognee.modules.pipelines.tasks"] = cognee_pipelines_tasks
        sys.modules["cognee.modules.pipelines.tasks.task"] = cognee_pipelines_tasks_task
        sys.modules["cognee.modules.search"] = cognee_search
        sys.modules["cognee.modules.search.types"] = cognee_search_types
        sys.modules["cognee.tasks"] = cognee_tasks
        sys.modules["cognee.tasks.storage"] = cognee_storage

        cognee.infrastructure = cognee_infra
        cognee_infra.engine = cognee_engine
        cognee_infra.llm = cognee_llm
        cognee.modules = cognee_modules
        cognee_modules.pipelines = cognee_pipelines
        cognee_pipelines.tasks = cognee_pipelines_tasks
        cognee_pipelines_tasks.task = cognee_pipelines_tasks_task
        cognee_modules.search = cognee_search
        cognee.tasks = cognee_tasks
        cognee_tasks.storage = cognee_storage


_install_cognee_mock()


# ---------------------------------------------------------------------------
# BookNLP fixtures — modeled on A Christmas Carol
# ---------------------------------------------------------------------------

@pytest.fixture
def christmas_carol_book_json() -> dict:
    """
    Realistic BookNLP .book JSON for A Christmas Carol.
    Contains character profiles with names (dict format) and agent actions.
    """
    return {
        "characters": [
            {
                "id": 0,
                "names": {"Scrooge": 150, "Ebenezer": 12, "Mr. Scrooge": 8},
                "agent": [
                    {"w": "said", "c": 30},
                    {"w": "muttered", "c": 5},
                    {"w": "exclaimed", "c": 8},
                    {"w": "walked", "c": 4},
                    {"w": "employs", "c": 2},
                ],
                "patient": [{"w": "visited", "c": 3}],
                "mod": ["old", "cold", "covetous"],
                "poss": ["counting-house", "chambers"],
                "g": "he/him/his",
            },
            {
                "id": 1,
                "names": {"Bob Cratchit": 40, "Cratchit": 25, "Bob": 18},
                "agent": [
                    {"w": "said", "c": 12},
                    {"w": "worked", "c": 3},
                    {"w": "serves", "c": 2},
                ],
                "patient": [],
                "mod": ["poor", "faithful"],
                "poss": ["desk", "candle"],
                "g": "he/him/his",
            },
            {
                "id": 2,
                "names": {"Jacob Marley": 20, "Marley": 35},
                "agent": [
                    {"w": "said", "c": 6},
                    {"w": "warned", "c": 3},
                    {"w": "haunts", "c": 1},
                ],
                "patient": [],
                "mod": ["dead"],
                "poss": ["ghost", "chains"],
                "g": "he/him/his",
            },
            {
                "id": 3,
                "names": {"Tiny Tim": 15, "Tim": 8},
                "agent": [{"w": "said", "c": 2}],
                "patient": [],
                "mod": ["little", "crippled"],
                "poss": ["crutch"],
                "g": "he/him/his",
            },
        ]
    }


@pytest.fixture
def christmas_carol_entities_tsv() -> list[dict]:
    """
    Realistic BookNLP .entities TSV rows for A Christmas Carol.
    Each row has: COREF, start_token, end_token, prop, cat, text.
    """
    return [
        {"COREF": 0, "start_token": 10, "end_token": 11, "prop": "PROP", "cat": "PER", "text": "Scrooge"},
        {"COREF": 0, "start_token": 50, "end_token": 51, "prop": "PRON", "cat": "PER", "text": "he"},
        {"COREF": 1, "start_token": 80, "end_token": 82, "prop": "PROP", "cat": "PER", "text": "Bob Cratchit"},
        {"COREF": 2, "start_token": 120, "end_token": 122, "prop": "PROP", "cat": "PER", "text": "Jacob Marley"},
        {"COREF": 100, "start_token": 200, "end_token": 201, "prop": "PROP", "cat": "LOC", "text": "London"},
        {"COREF": 100, "start_token": 300, "end_token": 301, "prop": "PROP", "cat": "LOC", "text": "London"},
        {"COREF": 100, "start_token": 400, "end_token": 401, "prop": "PROP", "cat": "LOC", "text": "London"},
        {"COREF": 101, "start_token": 210, "end_token": 213, "prop": "PROP", "cat": "FAC", "text": "Scrooge's counting-house"},
        {"COREF": 102, "start_token": 500, "end_token": 501, "prop": "PROP", "cat": "GPE", "text": "England"},
        {"COREF": 103, "start_token": 600, "end_token": 602, "prop": "PROP", "cat": "ORG", "text": "Royal Exchange"},
        {"COREF": 104, "start_token": 700, "end_token": 701, "prop": "PROP", "cat": "VEH", "text": "coach"},
        # Empty/edge cases
        {"COREF": 999, "start_token": 800, "end_token": 801, "prop": "PROP", "cat": "", "text": "unknown"},
        {"COREF": 998, "start_token": 900, "end_token": 901, "prop": "PROP", "cat": "PER", "text": ""},
    ]


@pytest.fixture
def booknlp_output(christmas_carol_book_json, christmas_carol_entities_tsv) -> dict:
    """Combined BookNLP output dict as expected by ontology_discovery."""
    return {
        "book_json": christmas_carol_book_json,
        "entities_tsv": christmas_carol_entities_tsv,
    }


@pytest.fixture
def christmas_carol_text() -> str:
    """
    Simplified A Christmas Carol text (enough paragraphs for TF-IDF).
    Uses parenthetical coref as per CLAUDE.md:
      "he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"
    """
    paragraphs = [
        "Marley was dead: to begin with. There is no doubt whatever about that. "
        "Old Marley was as dead as a door-nail.",

        "Scrooge knew he [Scrooge] was dead? Of course he [Scrooge] did. How could "
        "it be otherwise? Scrooge and he [Marley] were partners for I don't know how many years.",

        "Scrooge was his [Marley] sole executor, his [Marley] sole administrator, "
        "his [Marley] sole assign, his [Marley] sole residuary legatee, his [Marley] sole friend.",

        "Oh! But he [Scrooge] was a tight-fisted hand at the grindstone, Scrooge! "
        "a squeezing, wrenching, grasping, scraping, clutching, covetous old sinner!",

        "He [Scrooge] carried his [Scrooge] own low temperature always about with him [Scrooge]; "
        "he [Scrooge] iced his [Scrooge] office in the dog-days.",

        "Nobody ever stopped him [Scrooge] in the street to say, with gladsome looks, "
        "'My dear Scrooge, how are you?'",

        "Once upon a time — of all the good days in the year, on Christmas Eve — old Scrooge "
        "sat busy in his [Scrooge] counting-house.",

        "The door of Scrooge's counting-house was open that he [Scrooge] might keep his [Scrooge] "
        "eye upon his [Scrooge] clerk [Bob Cratchit], who in a dismal little cell beyond was copying letters.",

        "Scrooge had a very small fire, but the clerk's [Bob Cratchit] fire was so very much smaller "
        "that it looked like one coal.",

        "'A merry Christmas, uncle! God save you!' cried a cheerful voice. It was the voice of "
        "Scrooge's nephew [Fred], who came upon him [Scrooge] so quickly.",

        "Bob Cratchit went down a slide on Cornhill, at the end of a lane of boys, "
        "twenty times, in honour of its being Christmas Eve.",

        "The ghost of Jacob Marley appeared before Scrooge, draped in chains and cashboxes. "
        "'I wear the chain I forged in life,' said Marley's ghost.",

        "The Ghost of Christmas Past took Scrooge's hand and they flew together through the night sky "
        "to visit scenes from Scrooge's youth in the countryside.",

        "The Spirit of Christmas Present showed Scrooge the Cratchit family gathered around their "
        "meager Christmas dinner. Tiny Tim sat close to his [Tiny Tim] father [Bob Cratchit].",

        "London was cold and foggy. The city streets were full of people carrying Christmas "
        "packages and hurrying home to their families.",

        "Scrooge employs Bob Cratchit as his [Scrooge] clerk for a meager fifteen shillings a week. "
        "Bob Cratchit serves faithfully despite the low wages.",

        "The Ghost of Christmas Yet to Come pointed silently at a gravestone bearing the name "
        "Ebenezer Scrooge. Scrooge fell upon his [Scrooge] knees and wept.",

        "Scrooge awoke on Christmas morning a changed man. He [Scrooge] laughed and danced "
        "and sent the largest turkey to the Cratchit family.",

        "Scrooge raised Bob Cratchit's salary and became like a second father to Tiny Tim, "
        "who did NOT die. God bless us, every one!",

        "The counting-house in London was cold and dreary, but Scrooge's heart was now warm. "
        "He [Scrooge] loved Christmas from that day forward.",
    ]
    return "\n\n".join(paragraphs)


@pytest.fixture
def sample_ontology_result(tmp_path) -> "OntologyResult":
    """A pre-built OntologyResult for reviewer tests."""
    from pipeline.ontology_discovery import OntologyResult

    return OntologyResult(
        discovered_entities={
            "Character": [
                {"name": "Scrooge", "count": 150},
                {"name": "Bob Cratchit", "count": 40},
                {"name": "Marley", "count": 35},
            ],
            "Location": [
                {"name": "London", "count": 3},
                {"name": "counting-house", "count": 2},
            ],
        },
        discovered_themes=[
            {"topic_id": 0, "label": "christmas_ghost_spirit", "keywords": ["christmas", "ghost", "spirit"]},
            {"topic_id": 1, "label": "money_poor_wages", "keywords": ["money", "poor", "wages"]},
        ],
        discovered_relations=[
            {"name": "employs", "source": "booknlp_agent_actions", "evidence": "appears 2 times"},
            {"name": "serves", "source": "booknlp_agent_actions", "evidence": "appears 2 times"},
            {"name": "haunts", "source": "booknlp_agent_actions", "evidence": "appears 1 times"},
        ],
        owl_path=tmp_path / "ontology" / "book_ontology.owl",
    )
