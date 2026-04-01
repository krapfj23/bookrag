# BookRAG Research Context — Deep Technical Reference

This document captures the research findings, technical analysis, and architectural reasoning from the planning phase. It serves as background context that informed the architecture decisions in the plan document.

---

## 1. Cognee Internals

### How cognee.cognify() Works Under the Hood

The default `cognify()` runs a 5-task pipeline sequentially via `run_pipeline()`:

1. **classify_documents** — Detects file type (PDF, text, HTML). Lightweight, no LLM calls.
2. **extract_chunks_from_documents** — Splits text into chunks by token count using `TextChunker`. Configurable `max_chunk_size`.
3. **extract_graph_from_data** — The core LLM step. Sends batches of chunks (default `batch_size=50`) to the LLM with a system prompt. Extracts entities and relationships as structured triplets. Uses `KnowledgeGraph` Pydantic model. This is where ontology hooks in via `ontology_file_path`.
4. **summarize_text** — LLM generates summaries per chunk. Stored alongside raw chunks.
5. **add_data_points** — Persists nodes/edges to graph DB, embeddings to vector DB.

### Cognee's Default Extraction Prompt

Located in `generate_graph_prompt.txt`, rendered via `render_prompt()`. The full prompt:

```
You are a top-tier algorithm designed for extracting information in 
structured formats to build a knowledge graph.
- **Nodes** represent entities and concepts. They're akin to Wikipedia nodes.
- **Edges** represent relationships between concepts. They're akin to Wikipedia links.
- The aim is to achieve simplicity and clarity in the knowledge graph, 
  making it accessible for a vast audience.

YOU ARE ONLY EXTRACTING DATA FOR COGNITIVE LAYER `{{ layer }}`

## 1. Labeling Nodes
- **Consistency**: Ensure you use basic or elementary types for node labels.
  - For example, when you identify an entity representing a person, 
    always label it as **"Person"**. 
    Avoid using more specific terms like "mathematician" or "scientist".
  - Include event, entity, time, or action nodes to the category.
  - Classify the memory type as episodic or semantic.
- **Node IDs**: Never utilize integers as node IDs. 
  Node IDs should be names or human-readable identifiers found in the text.

## 2. Handling Numerical Data and Dates
- Numerical data, like age or other related information, 
  should be incorporated as attributes or properties of the respective nodes.
- **No Separate Nodes for Dates/Numbers**: 
  Do not create separate nodes for dates or numerical values. 
  Always attach them as attributes or properties of nodes.
- **Property Format**: Properties must be in a key-value format.
- **Quotation Marks**: Never use escaped single or double quotes within property values.
- **Naming Convention**: Use snake_case for relationship names, e.g., `acted_in`.

## 3. Coreference Resolution
- **Maintain Entity Consistency**: 
  When extracting entities, it's vital to ensure consistency. 
  If an entity, such as "John Doe", is mentioned multiple times 
  in the text but is referred to by different names or pronouns (e.g., "Joe", "he"), 
  always use the most complete identifier for that entity throughout the knowledge graph. 
  In this example, use "John Doe" as the entity ID. 
  Remember, the knowledge graph should be coherent and easily understandable, 
  so maintaining consistency in entity references is crucial.

## 4. Strict Compliance
Adhere to the rules strictly. Non-compliance will result in termination.
```

### Patterns to Adopt from Cognee's Prompt

- Elementary/consistent node labels ("Person" not "mathematician")
- Human-readable node IDs (names, not integers)
- Dates and numbers as properties, not separate nodes
- Snake_case for relationship names
- Built-in coreference instruction

### Where Our Prompt Must Go Further

- Chapter/position metadata on every entity and relationship
- BookNLP structured annotations as a "cheat sheet" context block
- Ontology constraints surfaced directly in the prompt text
- Episodic vs semantic distinction adapted for literary content (plot events vs themes)
- Our coref is pre-resolved via parenthetical insertion, so the LLM gets `"he [Scrooge]"` instead of just `"he"`

### Cognee's LLMGateway API

```python
from cognee.infrastructure.llm.LLMGateway import LLMGateway

result = await LLMGateway.acreate_structured_output(
    text_input="...",           # The text to extract from
    system_prompt="...",        # System prompt (our custom prompt)
    response_model=MyModel      # Pydantic model for structured output
)
```

- Backend-agnostic: works with Instructor (default) or BAML
- Configurable via `STRUCTURED_OUTPUT_FRAMEWORK` env var
- Automatic retries, backoff, and runtime type validation
- Supports Anthropic via LLM_PROVIDER="anthropic" config

### Cognee Custom Pipelines

```python
from cognee.modules.pipelines.tasks.task import Task
from cognee.modules.pipelines import run_pipeline
from cognee.tasks.storage import add_data_points

tasks = [
    Task(my_custom_extraction_task),
    Task(add_data_points, task_config={"batch_size": 30}),
]

async for status in run_pipeline(tasks=tasks, data=input_data, datasets=["my_dataset"]):
    print(status)
```

### Cognee DataPoints

```python
from cognee.infrastructure.engine import DataPoint

class Character(DataPoint):
    name: str
    aliases: list[str] = []
    first_chapter: int
    metadata: dict = {"index_fields": ["name"]}
```

- `metadata["index_fields"]` controls which fields get embedded in the vector DB
- Relationships are expressed via typed fields referencing other DataPoints
- `add_data_points` recursively unpacks nested DataPoints, deduplicates, and stores

### Cognee Ontology Support

- Parses OWL files via RDFLib (supports RDF/XML, Turtle, N-Triples, JSON-LD)
- Hooks into the cognify() step during extraction
- Canonicalizes entity names to ontology URIs
- Performs BFS traversal to inject rdfs:subClassOf hierarchies
- Tags nodes as `ontology_valid = True/False`
- Usage: `await cognee.cognify(ontology_file_path="book_ontology.owl")`

### Cognee Search Types

- `GRAPH_COMPLETION` — Graph traversal + LLM completion
- `RAG_COMPLETION` — Vector search + LLM completion
- `CHUNKS` — Raw vector similarity (no LLM)
- `SUMMARIES` — Pre-generated hierarchical summaries
- `GRAPH_SUMMARY` — Graph relationships in human-readable format
- `CYPHER` — Direct Cypher queries (Neo4j only)

---

## 2. BookNLP Internals

### Output Files

For a book processed as `{book_id}`, BookNLP produces:

| File | Format | Contents |
|------|--------|----------|
| `{book_id}.tokens` | TSV | Every token annotated: POS, dependency, coref ID, event triggers |
| `{book_id}.entities` | TSV | Entity mentions with coref cluster IDs, type (PER, LOC, FAC, GPE, VEH, ORG), proper/common/pronoun classification |
| `{book_id}.quotes` | TSV | Quotation text + attributed speaker (linked via coref ID) |
| `{book_id}.supersense` | TSV | Semantic categories from WordNet (41 lexical categories) |
| `{book_id}.book` | JSON | Full character profiles: aliases, referential gender, agent/patient actions, possessions, modifiers |
| `{book_id}.book.html` | HTML | Annotated text with entities, coref, and speaker attribution visualized |

### Key .entities Columns

- `COREF` — Unique identifier for the entity cluster
- `start_token` / `end_token` — Token span
- `prop` — PROP (proper noun), NOM (nominal), PRON (pronoun)
- `cat` — Entity type: PER, LOC, FAC, GPE, VEH, ORG
- `text` — Raw text of the mention

### BookNLP's Coref Approach

- First performs character name clustering ("Tom", "Tom Sawyer", "Mr. Sawyer" → TOM_SAWYER)
- Then allows pronouns to corefer with named or common entities
- Disallows common entities from co-referring to named entities (prevents over-merging)
- ~70% accuracy on literary text
- Trained on LitBank + PreCo

### BookNLP Models

- **big model**: More accurate, requires GPU or multi-core
- **small model**: Faster, appropriate for personal computers/Apple Silicon

### Important: BookNLP Does NOT Produce Resolved Text

BookNLP outputs annotation layers (coref cluster IDs on token spans). It does NOT produce text where "he" has been replaced with "Scrooge." We must build a custom text resolution step that reads `.entities` and `.tokens`, maps cluster IDs to canonical names from `.book` JSON, applies parenthetical insertion rules, and outputs annotated chapter files.

---

## 3. BookCoref (ACL 2025)

### Paper Summary

- **Title**: BOOKCOREF: Coreference Resolution at Book Scale
- **Authors**: Martinelli, Bonomo, Huguet Cabot, Navigli (Sapienza University of Rome)
- **Venue**: ACL 2025 main conference
- **Code**: https://github.com/sapienzanlp/bookcoref
- **Data**: https://huggingface.co/datasets/sapienzanlp/bookcoref
- **Key contribution**: First book-scale coreference benchmark (avg 200k+ tokens per document)

### BookCoref Pipeline (4 stages)

1. **Character Linking** — Link all explicit character name mentions
2. **LLM Filtering** — Filter out inconsistent assignments via LLM
3. **Cluster Expansion (small windows)** — CR model (Maverick) on 1500-token windows
4. **Cluster Expansion (grouped windows)** — Merge clusters across grouped windows

### Why Not Using BookCoref for MVP

- Requires LLM calls during NLP phase (added cost)
- Maverick XL needs significant compute
- Designed for benchmark-quality annotations (overkill for MVP)
- Clean upgrade path: both systems output compatible cluster formats

---

## 4. The Three Approaches (Decision Context)

### Approach A — Standard cognee.add()
Feed resolved text into cognee.add(). Cognee handles chunking and extraction. Simplest. Limitation: no chapter metadata, no structured annotations context.

### Approach B — Custom DataPoints Only
BookNLP output → DataPoints directly. Cognee = storage only. Cheapest. Limitation: no themes, emotional arcs, or implicit relationships.

### Approach C — Hybrid Custom Pipeline (CHOSEN)
Custom pipeline: LLM receives resolved text + BookNLP annotations + ontology. Outputs custom DataPoints with chapter metadata. Best quality. Chosen because Jeffrey wants themes and emotional arcs in the query experience, and quality > cost.

---

## 5. The Six Gaps (All Resolved)

1. **Double Extraction**: BookNLP informs ontology → Claude re-extracts with that constraint + BookNLP annotations as context
2. **Chapter Metadata**: Chunk-level tagging; entities inherit chapter from source chunks
3. **BookCoref Integration**: BookNLP coref for MVP; swappable interface for future upgrade
4. **Evaluation**: Automated known-answer test suite
5. **Text Cleaning**: Moderate (strip HTML + junk, keep epigraphs/section breaks)
6. **What Goes Into Cognee**: Resolved text + BookNLP annotations + ontology + chapter number, via custom extraction task using Cognee LLMGateway

---

## 6. Parenthetical Insertion Details

### Format
`"he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"`

### Rules
- Annotate when antecedent is 3+ sentences away
- Annotate when multiple characters are in scope (ambiguity)
- Both rules applied simultaneously (tunable thresholds)

### Why Parenthetical
- Preserves original text (reversible by stripping brackets)
- Claude parses it well
- Avoids unnatural full-replacement artifacts

---

## 7. Ontology Discovery (Pass 1)

1. Entity types from BookNLP character profiles + entities
2. BERTopic on full text → latent themes
3. TF-IDF → domain-specific terminology and relationship types
4. Generate OWL file via RDFLib
5. Optional CLI review before Pass 2

---

## 8. Cognee's extract_content_graph Function

The actual extraction function in Cognee source:

```python
async def extract_content_graph(content: str, response_model: Type[BaseModel]):
    llm_client = get_llm_client()
    system_prompt = render_prompt("generate_graph_prompt.txt", {})
    content_graph = await llm_client.acreate_structured_output(
        content, system_prompt, response_model
    )
    return content_graph
```

Our custom task will follow this same pattern but with:
- Our custom prompt template (extending Cognee's patterns)
- Our custom Pydantic response model (BookRAG DataPoints)
- Additional context (BookNLP annotations) injected into the text_input or system_prompt

---

## 9. Cognee's KnowledgeGraph Default Schema

From Cognee's blog/source, the default extraction schema:

```python
class Node(BaseModel):
    id: str
    name: str
    type: str
    description: str
    properties: Optional[Dict[str, Any]] = None

class Edge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_name: str
    properties: Optional[Dict[str, Any]] = None

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(..., default_factory=list)
    edges: List[Edge] = Field(..., default_factory=list)
```

Our DataPoints replace this generic schema with domain-specific literary types (Character, Location, PlotEvent, Theme, Relationship, Faction) while maintaining the same node/edge conceptual model.
