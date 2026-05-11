# InsureBot SG — Architecture Document

## Project Overview

A multi-agent AI chatbot with generative UI capabilities for Singapore insurance advisory. The system answers policy questions, compares products, identifies coverage gaps, and renders interactive visualizations — replicating a face-to-face agent interaction through an intelligent canvas interface.

**Target demo:** A user asks "I'm 30, married with one kid, earning $8K/month — what life insurance should I consider?" and receives a structured, visual breakdown with premium projections, coverage comparisons, and a recommendation rationale grounded in retrieved policy documents.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────────┐  ┌────────────────────────────────────┐   │
│  │  Chat Panel   │  │         Canvas Panel                │   │
│  │               │  │  ┌──────────┐ ┌────────────────┐  │   │
│  │  User msgs    │  │  │ Charts   │ │ Comparison     │  │   │
│  │  Bot msgs     │  │  │ (Recharts│ │ Tables         │  │   │
│  │  Typing ind.  │  │  │  / D3)   │ │                │  │   │
│  │               │  │  ├──────────┤ ├────────────────┤  │   │
│  │               │  │  │ Decision │ │ Policy Cards   │  │   │
│  │               │  │  │ Trees    │ │ w/ highlights  │  │   │
│  │               │  │  │ (Mermaid)│ │                │  │   │
│  │               │  │  └──────────┘ └────────────────┘  │   │
│  └──────────────┘  └────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ WebSocket / SSE
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  LangGraph Orchestrator                  │ │
│  │                                                          │ │
│  │   ┌──────────┐   ┌───────────┐   ┌──────────────────┐ │ │
│  │   │  Router   │──▶│ Retrieval │──▶│    Analysis      │ │ │
│  │   │  Agent    │   │ Agent     │   │    Agent         │ │ │
│  │   └──────────┘   └───────────┘   └────────┬─────────┘ │ │
│  │        │                                    │           │ │
│  │        │              ┌─────────────────────▼─────────┐ │ │
│  │        │              │    Visualization Agent         │ │ │
│  │        │              │    (structured JSON output)    │ │ │
│  │        │              └───────────────────────────────┘ │ │
│  │        ▼                                                │ │
│  │   ┌──────────┐                                          │ │
│  │   │Guardrails│  (input validation, topic boundaries,   │ │
│  │   │  Layer   │   hallucination check vs source docs)   │ │
│  │   └──────────┘                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  LangFuse /  │  │   Redis      │  │  Ragas / Deep-   │  │
│  │  LangSmith   │  │   Cache      │  │  Eval Pipeline   │  │
│  │  (tracing)   │  │              │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Qdrant   │ │ Claude   │ │ Embedding│
        │ Vector   │ │ API      │ │ Model    │
        │ Store    │ │ (Sonnet) │ │ (BGE-M3 │
        │          │ │          │ │  / Cohere)│
        └──────────┘ └──────────┘ └──────────┘
```

---

## Multi-Agent Design (LangGraph)

### Agent Graph — State Machine

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   Router    │
                    │   Agent     │
                    │ (resolve +  │
                    │  classify)  │
                    └──────┬──────┘
                           │
          ┌────────┬───────┼───────┬──────────┐
          ▼        ▼       ▼       ▼          ▼
    ┌──────────┐ ┌────────────┐ ┌────────┐ ┌─────┐
    │ Single   │ │ Multi-     │ │General │ │ Off │
    │ Policy   │ │ Policy     │ │FAQ /   │ │Topic│
    │ Flow     │ │ Flow       │ │Process │ │     │
    │          │ │            │ │        │ │     │
    │inquiry   │ │compare_    │ │general_│ │off_ │
    │deep_dive │ │specific    │ │faq     │ │topic│
    │follow_up │ │find_similar│ │claims_ │ └──┬──┘
    │          │ │find_by_    │ │process │    │
    │          │ │criteria    │ │regulat-│    │
    │          │ │follow_up   │ │ion     │    │
    └────┬─────┘ └─────┬──────┘ │clarif- │    │
         │              │        │ication │    │
         ▼              ▼        └───┬────┘    │
    ┌──────────┐ ┌──────────┐       │         │
    │Retrieval │ │Retrieval │       │         │
    │Agent     │ │Agent     │       │         │
    │(single)  │ │(multi-q) │       │         │
    └────┬─────┘ └────┬─────┘       │         │
         │             │             │         │
         ▼             ▼             │         │
    ┌─────────────────────────┐     │         │
    │      Guardrails         │     │         │
    │  (confidence + faith.)  │     │         │
    └────┬──────────┬─────────┘     │         │
         │          │               │         │
    proceed     low_confidence      │      blocked
         │          │               │         │
         ▼          ▼               ▼         ▼
    ┌──────────┐ ┌──────────────────────────────┐
    │Analysis  │ │                              │
    │Agent     │ │                              │
    └────┬─────┘ │     Visualization Agent      │
         │       │  Decides: chart | table |    │
         └──────▶│  card | diagram | text-only  │
                 │  | caveat | polite refusal   │
                 └──────────────┬───────────────┘
                                ▼
                         ┌─────────────┐
                         │    END      │
                         │  (response  │
                         │   + UI JSON)│
                         └─────────────┘
```

### Agent Specifications

#### 1. Router Agent
- **Input:** User message + conversation history
- **Method:** Two-step process — context resolution first, then few-shot classification via LLM (not a fine-tuned model — keep it simple, show you understand the tradeoff)
- **Output:** Resolved query + intent label + extracted entities (age, income, family status, policy type)
- **Resume signal:** Mention that in production you'd use a fine-tuned classifier for latency/cost, but LLM routing is acceptable for the demo

**Context Resolution:** Before classifying intent, the Router resolves conversational references ("this", "that policy", "what about age 40?") using conversation history. This turns ambiguous follow-ups into standalone queries that downstream agents can process without needing conversation context.

```python
async def router_agent(state: InsureBotState) -> InsureBotState:
    # Step 1: Resolve references using conversation history
    resolved = await resolve_context(
        message=state["user_message"],
        history=state["conversation_history"],
    )
    # "are there other similar policies like this?"
    # → "Find term life policies similar to AIA Term Life Plus from other providers"

    # Step 2: Classify intent on the resolved message
    intent = await classify_intent(resolved.full_query)

    state["resolved_query"] = resolved.full_query
    state["intent"] = intent
    state["extracted_entities"] = resolved.entities
    return state
```

**Intent Categories:**

| Intent | Example Queries | Retrieval Strategy | Downstream Behavior |
|--------|----------------|-------------------|---------------------|
| `policy_inquiry` | "Tell me about AIA Shield Plan" | Vector + structured store for the named policy | Single policy explanation + policy card |
| `policy_deep_dive` | "What's the co-insurance structure?" | Vector search filtered to current policy context | Detailed explanation, possibly with benefit table |
| `compare_specific` | "Compare AIA vs Prudential term life" | Vector + structured store for each named policy | Side-by-side comparison table + charts |
| `find_similar` | "Are there other policies like this?" | Vector search by policy type, exclude current provider; structured store for discovered policies | Discover candidates, then comparison flow |
| `find_by_criteria` | "What's the cheapest term life for a 30-year-old?" | Structured store query (sort by premium); vector for context | Ranked results with key figures |
| `claims_process` | "How do I make a claim?" | Vector search in process/FAQ documents | Text explanation, possibly decision tree diagram |
| `regulation_question` | "What does MAS say about rider limits?" | Vector search filtered to regulatory documents | Text explanation with source citations |
| `general_faq` | "What's the difference between term and whole life?" | Vector search (broad) | Educational explanation + comparison |
| `follow_up` | "What about age 40?", "Can you explain that chart?" | Re-run previous flow with modified parameters, or meta-question about prior output | Depends on what's being followed up |
| `clarification` | "What do you mean by co-insurance?" | May not need retrieval — LLM can explain from context | Text explanation, possibly with simple diagram |
| `off_topic` | "What's the weather today?" | No retrieval | Polite refusal, redirect to insurance topics |

**Design Principle:** These categories are intentionally broad. The Router is an LLM call with few-shot examples, so "anything cheaper?" maps to `find_by_criteria`, "what else is out there?" maps to `find_similar`, and "what about the premium for age 40?" maps to `follow_up` — even though none are predefined phrases. The goal is to cover clusters of user behavior, not enumerate every possible question.

**The `follow_up` Intent:** This is the most complex category. It requires the Router to inspect conversation history and determine whether the user is modifying a parameter ("what about age 40?" → re-run with age=40), asking about a prior output ("can you explain that chart?"), or continuing a thread ("tell me more about the second option"). The resolved query captures the full intent so downstream agents don't need to interpret context themselves.

#### 2. Retrieval Agent
- **Hybrid search:** Semantic (dense vector via Qdrant) + keyword (BM25 via rank_bm25 library)
- **Reciprocal Rank Fusion (RRF):** Merge and re-rank results from both retrievers
- **Query transformation:** For complex questions, decompose into sub-queries before retrieval (e.g., "Compare term vs whole life for a 30-year-old" → two separate retrievals)
- **Metadata filtering:** Filter by insurer, policy type, year of document to narrow search
- **Resume signal:** Hybrid search + RRF is a strong talking point. Most tutorial RAG only does naive semantic search.

#### 3. Analysis Agent
- **Input:** Retrieved document chunks + user context (age, income, family)
- **Structured output:** Uses Claude's tool-use / structured output to produce typed JSON:
  ```json
  {
    "summary": "...",
    "recommendations": [...],
    "premium_estimates": [...],
    "coverage_details": {...},
    "caveats": [...],
    "sources": [{"doc_id": "...", "chunk": "...", "relevance": 0.92}]
  }
  ```
- **Chain-of-thought:** Explicit reasoning step before final output (improves faithfulness, is visible in traces)
- **Resume signal:** Structured output + source attribution shows production RAG patterns

#### 4. Visualization Agent
- **Input:** Analysis Agent output
- **Decision logic:** Rule-based + LLM hybrid — certain analysis types always trigger certain viz (comparisons → table + radar chart), but the LLM can override for edge cases
- **Output:** UI component spec as JSON:
  ```json
  {
    "components": [
      {
        "type": "comparison_table",
        "props": {
          "policies": [...],
          "highlight_columns": ["premium", "coverage"]
        }
      },
      {
        "type": "line_chart",
        "props": {
          "title": "Premium Projection Over 20 Years",
          "series": [...]
        }
      },
      {
        "type": "decision_tree",
        "props": {
          "mermaid": "graph TD; A[Need coverage?] -->|Yes| B[...]"
        }
      }
    ]
  }
  ```
- **Resume signal:** Generative UI is rare in portfolios. This alone makes the project memorable.

---

## Data Models (Pydantic)

Pydantic models define the data contracts between every component — Router, Retrieval, Analysis, Visualization, and the FastAPI endpoints. This gives runtime validation at every state transition, ensures the LLM can't return malformed data, and provides a single source of truth shared by the backend, the LLM structured output, and the API layer.

### Intent & Router Models

```python
from pydantic import BaseModel, Field
from enum import Enum


class Intent(str, Enum):
    POLICY_INQUIRY = "policy_inquiry"
    POLICY_DEEP_DIVE = "policy_deep_dive"
    COMPARE_SPECIFIC = "compare_specific"
    FIND_SIMILAR = "find_similar"
    FIND_BY_CRITERIA = "find_by_criteria"
    CLAIMS_PROCESS = "claims_process"
    REGULATION_QUESTION = "regulation_question"
    GENERAL_FAQ = "general_faq"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    OFF_TOPIC = "off_topic"


class ExtractedEntities(BaseModel):
    policy_name: str | None = None
    policy_type: str | None = None
    provider: str | None = None
    age: int | None = Field(None, ge=0, le=120)
    income: float | None = Field(None, ge=0)
    family_status: str | None = None
    comparison_mode: str | None = None  # "find_similar", "compare_specific", etc.


class RouterOutput(BaseModel):
    resolved_query: str
    intent: Intent
    entities: ExtractedEntities
```

### Conversation Context

Persists across turns. Updated after each response so the Router can resolve references like "the AIA one" or "what about age 40?"

```python
class ConversationContext(BaseModel):
    discussed_policies: list[str] = []           # ["AIA Term Life Plus", "PRUTerm Vantage"]
    current_focus_policy: str | None = None      # most recently discussed
    user_profile: ExtractedEntities = ExtractedEntities()  # accumulated across turns
    prior_intent: Intent | None = None
```

### Retrieval Models

```python
class ChunkMetadata(BaseModel):
    doc_id: str
    doc_title: str
    page_numbers: list[int]
    section_title: str
    bbox: dict | None = None          # for PDF highlight overlay
    paragraph_index: int
    source_url: str | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: ChunkMetadata
    relevance_score: float = Field(ge=0, le=1)
```

### Analysis Models

```python
class SourceRef(BaseModel):
    chunk_id: str
    doc_title: str
    page_number: int
    section_title: str | None = None
    bbox: dict | None = None
    relevant_excerpt: str


class Claim(BaseModel):
    claim_id: str
    text: str
    source_refs: list[SourceRef]
    confidence: float = Field(ge=0, le=1)
    ungrounded: bool = False


class PolicyData(BaseModel):
    name: str
    provider: str
    policy_type: str
    annual_premium: float | None = None
    coverage_amount: float | None = None
    policy_term: str | None = None
    key_features: list[str] = []
    key_differences: list[str] = []    # populated in comparison flows


class AnalysisOutput(BaseModel):
    response_type: str                 # "single_policy", "comparison", "faq", etc.
    claims: list[Claim]
    policies: list[PolicyData] = []
    projection_data: dict | None = None
    coverage_breakdown: dict | None = None
```

### Visualization Models

```python
class ComponentType(str, Enum):
    COMPARISON_TABLE = "comparison_table"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    RADAR_CHART = "radar_chart"
    POLICY_CARD = "policy_card"
    DECISION_TREE = "decision_tree"
    TEXT_EXPLANATION = "text_explanation"
    SOURCE_CITATIONS = "source_citations"


class ComponentSpec(BaseModel):
    type: ComponentType
    props: dict  # component-specific, validated by frontend registry
```

### Full Agent State

```python
class InsureBotState(BaseModel):
    # Input
    user_message: str
    conversation_history: list[dict] = []
    conversation_context: ConversationContext = ConversationContext()

    # Router Agent writes
    resolved_query: str | None = None
    intent: Intent | None = None
    extracted_entities: ExtractedEntities | None = None

    # Retrieval Agent writes
    retrieved_chunks: list[RetrievedChunk] = []
    structured_data: dict | None = None
    retrieval_scores: list[float] = []

    # Guardrails writes
    flags: list[str] = []

    # Analysis Agent writes
    analysis: AnalysisOutput | None = None

    # Visualization Agent writes
    ui_components: list[ComponentSpec] = []
```

### LLM Structured Output Integration

Pydantic models integrate directly with Claude's tool-use to force validated structured output from LLM calls:

```python
from anthropic import Anthropic

client = Anthropic()

# Pass Pydantic schema as tool definition
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[...],
    tools=[{
        "name": "produce_analysis",
        "description": "Produce structured analysis of insurance policies",
        "input_schema": AnalysisOutput.model_json_schema(),
    }]
)

# Parse + validate in one step — rejects malformed LLM output
analysis = AnalysisOutput.model_validate(tool_use_block.input)
```

This means: if the LLM omits `source_refs` on a claim, Pydantic rejects it. If `confidence` is outside 0-1, validation fails. If `intent` isn't in the enum, it's caught immediately. The guardrails are partially built into the data model itself — bad data cannot propagate through the agent pipeline.

### Resume Signal

Using Pydantic throughout signals you understand data contracts between system components — not just types for IDE autocomplete, but runtime validation that prevents bad data from flowing through a multi-agent pipeline. Combined with Claude's structured output, it means the LLM is constrained to produce valid, typed data at every step. FastAPI also uses Pydantic for request/response models, so the same model definitions serve the LLM output layer, the agent state, and the API layer — one source of truth.

---

## RAG Pipeline Detail

### Three-Store Architecture

Insurance PDFs contain fundamentally different types of content that require different storage, retrieval, and presentation strategies. The system uses three parallel stores:

```
PDF Document
    │
    ├──▶ Text Extraction (PyMuPDF)
    │        │
    │        ▼
    │    Chunking + Embedding + Metadata Enrichment
    │        │
    │        ▼
    │    Store 1: Qdrant (vector store)
    │    → "What does this policy cover?"
    │    → Semantic search over unstructured text
    │
    ├──▶ Table Extraction (pdfplumber / vision fallback)
    │        │
    │        ▼
    │    Store 2: SQLite (structured store)
    │    → "What's the premium for a 30-year-old?"
    │    → Direct SQL queries on numerical data
    │
    └──▶ Original PDF archived
             │
             ▼
         Store 3: Filesystem (PDF archive)
         → Source Viewer renders pages with bbox highlights
         → User-verifiable citations
```

**Why three stores:**
- **Qdrant** for natural language questions about policy features, exclusions, processes
- **SQLite** for numerical queries — premiums, coverage amounts, benefit limits — where you need exact figures, not LLM-generated approximations
- **Filesystem** for source attribution — the original PDFs are needed to render the Source Viewer with bounding box highlights

**Why SQLite over JSON files:** Queryability (`ORDER BY annual_premium`), joins across tables, indexing for fast lookups, and portability (single `.db` file, no infrastructure). For a portfolio project with 20-30 policies, JSON would work, but SQLite is the correct production pattern.

### SQLite Schema

```sql
-- Premium schedules (extracted from premium tables in PDFs)
CREATE TABLE premiums (
    id INTEGER PRIMARY KEY,
    doc_id TEXT,
    policy_name TEXT,
    provider TEXT,
    policy_type TEXT,
    age INTEGER,
    annual_premium REAL,
    annual_premium_with_rider REAL,
    payment_frequency TEXT,
    currency TEXT DEFAULT 'SGD',
    page_number INTEGER,          -- for source attribution back to PDF
    UNIQUE(doc_id, age)
);

-- Benefit limits (extracted from benefit schedule tables)
CREATE TABLE benefits (
    id INTEGER PRIMARY KEY,
    doc_id TEXT,
    policy_name TEXT,
    provider TEXT,
    benefit_category TEXT,        -- "hospitalization", "surgical", "outpatient"
    benefit_description TEXT,
    limit_amount REAL,
    limit_period TEXT,            -- "per_policy_year", "lifetime", "per_event"
    co_insurance_rate REAL,
    deductible REAL,
    page_number INTEGER
);

-- Policy metadata (one row per policy document)
CREATE TABLE policies (
    doc_id TEXT PRIMARY KEY,
    policy_name TEXT,
    provider TEXT,
    policy_type TEXT,             -- "term_life", "whole_life", "health", "critical_illness"
    product_line TEXT,            -- "HealthShield", "PRUTerm" — groups variants
    ward_class TEXT,
    min_entry_age INTEGER,
    max_entry_age INTEGER,
    coverage_term TEXT,
    pdf_filename TEXT,
    ingested_at TIMESTAMP
);
```

### Vector Store Metadata Design

The metadata attached to each chunk determines what can be filtered at query time. Good metadata lets the Retrieval Agent narrow the search space before vector search runs, rather than relying entirely on semantic similarity.

#### Document-Level Metadata (same for all chunks from one PDF)

```python
doc_id: str              # "aia-healthshield-gold-max-2024"
doc_title: str           # "AIA HealthShield Gold Max"
provider: str            # "AIA"
policy_type: str         # "term_life" | "whole_life" | "health" | "critical_illness" | "endowment"
product_line: str        # "HealthShield" — groups variants under one product family
doc_category: str        # "product_brochure" | "benefit_schedule" | "policy_contract" | "regulatory_notice" | "faq"
doc_year: int            # 2024 — critical for filtering out outdated documents
doc_language: str        # "en" | "zh" — some Singapore insurers publish bilingual docs
```

**Why each field matters:**

| Field | Enables | Without it |
|-------|---------|------------|
| `provider` | "Find similar from other providers" → filter `provider != "AIA"` | Vector search returns other AIA products instead of competitors |
| `policy_type` | "Compare term life options" → filter to `term_life` only | Retrieves critical illness chunks that are semantically similar but irrelevant |
| `product_line` | "Difference between Gold and Basic plans?" → filter to `HealthShield` | Mixes results from unrelated product lines |
| `doc_category` | Prioritize brochures for general queries, regulatory docs for compliance | All doc types weighted equally regardless of query intent |
| `doc_year` | Filter to recent documents, avoid outdated policy info | Returns superseded policy terms from 2020 |
| `doc_language` | Filter to user's preferred language | Retrieves Chinese-language chunks for English queries |

#### Chunk-Level Metadata (specific to each chunk)

```python
chunk_id: str            # "aia-healthshield-gold-max-2024-chunk-042"
parent_chunk_id: str     # for parent-child retrieval — search small, return big
page_numbers: list[int]  # [12, 13] if chunk spans pages
section_title: str       # "Benefit Schedule" | "Premium Table" | "Exclusions"
section_type: str        # "benefits" | "premiums" | "exclusions" | "eligibility" | "claims" | "riders" | "definitions" | "general"
content_type: str        # "prose" | "table_text" | "list" | "header"
bbox: dict | None        # {x0, y0, x1, y1} for PDF highlighting
paragraph_index: int     # position within page
chunk_index: int         # position within document — for ordering results
```

**`section_type` is the second most valuable filter after `policy_type`.** When a user asks "what's excluded?", filtering to `section_type = "exclusions"` prevents returning a benefits section that happens to mention an exclusion in passing.

| section_type | What it covers |
|---|---|
| `benefits` | Coverage amounts, what's included |
| `premiums` | Premium tables, payment terms |
| `exclusions` | What's not covered, waiting periods |
| `eligibility` | Age limits, underwriting requirements |
| `claims` | How to file, required documents |
| `riders` | Optional add-ons, their costs |
| `definitions` | Glossary, technical terms |
| `general` | Overview, product summary |

**`parent_chunk_id`** enables parent-child retrieval: search against small chunks (precise matching) but return the parent chunk (full context). Without this, you retrieve a sentence about premiums but lose the surrounding context about which age band it applies to.

**`content_type`** distinguishes prose from table-derived text. When the Retrieval Agent sees `content_type = "table_text"`, it knows to also query the SQLite structured store for the same data in queryable form.

**`chunk_index`** lets you reassemble multiple chunks from the same document in reading order for the Analysis Agent. Without it, chunks arrive in relevance-score order, which breaks references like "the above benefit" or "as stated in Section 3."

#### Derived / Enriched Metadata (computed during ingestion)

```python
mentions_ages: list[int]      # [25, 30, 35, 40] — extracted from premium tables
mentions_amounts: list[float] # [500000, 1000000] — coverage amounts found in text
rider_names: list[str]        # ["AIA Vitality", "Early CI Rider"]
has_table: bool               # chunk contains or was derived from a table
key_terms: list[str]          # ["co-insurance", "deductible", "waiting period"]
```

**`mentions_ages`** — when a user says they're 30, boost chunks that specifically mention age 30. Semantic search doesn't understand that "age 30" in a query should match a premium table row for age 30.

**`mentions_amounts`** — "policies with at least $500K coverage" can filter on this directly.

**`rider_names`** — riders are a major part of insurance conversations. Filtering to "chunks that mention Early CI Rider" is much more precise than hoping vector search picks them up.

**`has_table`** — signals the Retrieval Agent to also query SQLite for the same data in structured form.

### Qdrant Collection Setup

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance,
    PayloadSchemaType,
)

client = QdrantClient(host="localhost", port=6333)

# Create collection with BGE-M3 dimensions
client.create_collection(
    collection_name="policy_chunks",
    vectors_config=VectorParams(
        size=1024,           # BGE-M3 dimension
        distance=Distance.COSINE,
    ),
)

# Payload indexes — make filtered queries fast instead of scanning all payloads
# Index every field you'll filter on frequently
for field, schema in [
    ("provider", PayloadSchemaType.KEYWORD),
    ("policy_type", PayloadSchemaType.KEYWORD),
    ("product_line", PayloadSchemaType.KEYWORD),
    ("section_type", PayloadSchemaType.KEYWORD),
    ("doc_category", PayloadSchemaType.KEYWORD),
    ("doc_year", PayloadSchemaType.INTEGER),
    ("content_type", PayloadSchemaType.KEYWORD),
]:
    client.create_payload_index(
        collection_name="policy_chunks",
        field_name=field,
        field_schema=schema,
    )
```

**Why payload indexes matter:** Without them, Qdrant scans every payload on filtered queries. With indexes, it narrows the candidate set first, then runs vector search only on matching documents. For 20-30 policies this is fast either way, but it's the correct production pattern and shows you understand how vector databases work under the hood.

### How Retrieval Agent Uses Metadata Filters

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

# "Compare term life options for a 30-year-old"
# → Filter to policy type BEFORE vector search
results = qdrant.search(
    collection_name="policy_chunks",
    query_vector=embed("term life insurance benefits features"),
    query_filter=Filter(
        must=[
            FieldCondition(key="policy_type", match=MatchValue(value="term_life")),
            FieldCondition(key="doc_year", range=Range(gte=2023)),
        ]
    ),
    limit=20,
)

# "What's excluded from AIA HealthShield?"
# → Filter to provider + product line + section type
results = qdrant.search(
    collection_name="policy_chunks",
    query_vector=embed("exclusions not covered waiting period"),
    query_filter=Filter(
        must=[
            FieldCondition(key="provider", match=MatchValue(value="AIA")),
            FieldCondition(key="product_line", match=MatchValue(value="HealthShield")),
            FieldCondition(key="section_type", match=MatchValue(value="exclusions")),
        ]
    ),
    limit=10,
)

# "Are there other similar policies like this?" (currently viewing AIA Term Life Plus)
# → Filter to same type, EXCLUDE current provider
results = qdrant.search(
    collection_name="policy_chunks",
    query_vector=embed("term life insurance policy features"),
    query_filter=Filter(
        must=[
            FieldCondition(key="policy_type", match=MatchValue(value="term_life")),
            FieldCondition(key="section_type", match=MatchValue(value="general")),
        ],
        must_not=[
            FieldCondition(key="provider", match=MatchValue(value="AIA")),
        ]
    ),
    limit=20,
)
```

The combination of metadata filtering + semantic search is what makes retrieval accurate. Semantic search alone returns "kind of relevant" chunks from all over the corpus. Metadata filtering narrows to the right document, section, and time period — then semantic search ranks within that subset.

### Document Ingestion Pipeline

The pipeline processes a raw PDF through eight steps into chunks, structured tables, metadata, and embeddings across all three stores.

```
Raw PDF
  │
  ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: Document Registration                                     │
│   Hash PDF for dedup → generate doc_id → register in SQLite       │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 2: Page-Level Extraction                                     │
│   PyMuPDF: text blocks with bounding boxes                        │
│   pdfplumber: tables as structured rows                           │
│   Vision LLM fallback: for scanned / image-heavy pages            │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 3: Document Structure Detection                              │
│   Font-size heuristic for headers (covers ~80% of cases)          │
│   Pattern matching for section_type classification                │
│   LLM fallback for ambiguous headers ("Table 3A", "Appendix B")  │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 4: Section-Aware Chunking                                    │
│   Respect section boundaries (never split mid-section)            │
│   Create parent chunks (full section) + child chunks (paragraphs) │
│   Link via parent_chunk_id                                        │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 5: Table Processing                                          │
│   Classify table type (premium_schedule, benefit_limit, etc.)     │
│   Parse into structured rows → insert into SQLite                 │
│   Also create text representation chunk → Qdrant (dual storage)   │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 6: Metadata Enrichment                                       │
│   Document-level: provider, policy_type, product_line, doc_year   │
│   Chunk-level: section_type, content_type, bbox, chunk_index      │
│   Derived: mentions_ages, mentions_amounts, rider_names, key_terms│
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 7: Embedding                                                 │
│   BGE-M3 encodes each child chunk                                 │
│   Batch upload to Qdrant with full metadata payload               │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 8: Validation                                                │
│   Verify chunk count, check for empty chunks (<20 chars)          │
│   Confirm SQLite rows match tables found in PDF                   │
│   Log ingestion stats to manifest file                            │
└──────────────────────────────────────────────────────────────────┘
```

### Pipeline Implementation

```python
# rag/ingest.py
import hashlib
from pathlib import Path
from pydantic import BaseModel

from rag.chunker import chunk_document
from rag.table_extractor import extract_tables
from rag.metadata_enricher import enrich_metadata
from rag.structured_store import StructuredStore
from rag.embedder import Embedder
from rag.qdrant_setup import get_qdrant_client


class IngestionResult(BaseModel):
    doc_id: str
    text_chunks_count: int
    tables_extracted: int
    sqlite_rows_inserted: int
    qdrant_points_uploaded: int
    errors: list[str] = []


class DocumentIngestionPipeline:
    def __init__(self):
        self.qdrant = get_qdrant_client()
        self.sqlite = StructuredStore("data/structured/insurebot.db")
        self.embedder = Embedder()  # BGE-M3

    async def ingest_pdf(
        self, pdf_path: Path, metadata_override: dict = None
    ) -> IngestionResult:
        errors = []

        # ── Step 1: Document registration + dedup ──────────────────
        doc_id = self._generate_doc_id(pdf_path)
        if self._already_ingested(doc_id):
            return IngestionResult(
                doc_id=doc_id, text_chunks_count=0, tables_extracted=0,
                sqlite_rows_inserted=0, qdrant_points_uploaded=0,
                errors=["Already ingested, skipping"],
            )

        doc_metadata = await self._detect_document_metadata(
            pdf_path, metadata_override
        )
        self.sqlite.register_policy(doc_id, doc_metadata)

        # ── Step 2: Page-level extraction ──────────────────────────
        pages = self._extract_pages(pdf_path)

        # ── Step 3: Structure detection + section assignment ───────
        structured_pages = await self._detect_structure(pages, pdf_path)

        # ── Step 4: Chunking (section-aware, parent-child) ────────
        chunks = chunk_document(structured_pages, doc_id, doc_metadata)

        # ── Step 5: Table processing → SQLite + text chunks ───────
        tables = extract_tables(pdf_path)
        sqlite_rows = 0
        for table in tables:
            rows = self.sqlite.insert_table(doc_id, table)
            sqlite_rows += rows
            # Dual storage: text representation of table for vector search
            table_chunk = table.to_text_chunk(doc_id, doc_metadata)
            chunks.append(table_chunk)

        # ── Step 6: Metadata enrichment ────────────────────────────
        enriched_chunks = enrich_metadata(chunks)

        # ── Step 7: Embedding + upload to Qdrant ──────────────────
        embeddings = self.embedder.encode_batch(
            [c.text for c in enriched_chunks]
        )
        self._upload_to_qdrant(enriched_chunks, embeddings)

        # ── Step 8: Validation ─────────────────────────────────────
        validation_errors = self._validate(doc_id, enriched_chunks, tables)
        errors.extend(validation_errors)

        return IngestionResult(
            doc_id=doc_id,
            text_chunks_count=len(enriched_chunks),
            tables_extracted=len(tables),
            sqlite_rows_inserted=sqlite_rows,
            qdrant_points_uploaded=len(enriched_chunks),
            errors=errors,
        )

    # ── Step 1 helpers ─────────────────────────────────────────────

    def _generate_doc_id(self, pdf_path: Path) -> str:
        """Hash-based doc_id for dedup — re-running ingestion skips
        already-processed documents."""
        content_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:12]
        stem = pdf_path.stem.lower().replace(" ", "-")
        return f"{stem}-{content_hash}"

    def _already_ingested(self, doc_id: str) -> bool:
        return self.sqlite.policy_exists(doc_id)

    # ── Step 2: Page extraction ────────────────────────────────────

    def _extract_pages(self, pdf_path: Path) -> list[PageContent]:
        """PyMuPDF extraction with bbox for every text block."""
        import fitz

        doc = fitz.open(str(pdf_path))
        pages = []
        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            text_blocks = []
            for block in blocks:
                if block["type"] == 0:  # text block
                    text = " ".join(
                        span["text"]
                        for line in block["lines"]
                        for span in line["spans"]
                    )
                    if text.strip():
                        text_blocks.append(TextBlock(
                            text=text.strip(),
                            bbox={
                                "x0": block["bbox"][0],
                                "y0": block["bbox"][1],
                                "x1": block["bbox"][2],
                                "y1": block["bbox"][3],
                            },
                            page_number=page_num + 1,
                            font_sizes=[
                                span["size"]
                                for line in block["lines"]
                                for span in line["spans"]
                            ],
                        ))
                elif block["type"] == 1:  # image block
                    text_blocks.append(TextBlock(
                        text="[IMAGE]",
                        bbox={
                            "x0": block["bbox"][0],
                            "y0": block["bbox"][1],
                            "x1": block["bbox"][2],
                            "y1": block["bbox"][3],
                        },
                        page_number=page_num + 1,
                        is_image=True,
                    ))
            pages.append(PageContent(
                page_number=page_num + 1, blocks=text_blocks
            ))
        return pages

    # ── Step 3: Structure detection ────────────────────────────────

    async def _detect_structure(
        self, pages: list[PageContent], pdf_path: Path
    ) -> list[StructuredPage]:
        """Detect headers, sections, and assign section_type.
        Font-size heuristic first (~80% of cases), LLM fallback for ambiguous."""
        structured = []
        current_section = "general"
        current_section_title = ""

        for page in pages:
            structured_blocks = []
            for block in page.blocks:
                # Image blocks → vision fallback
                if block.is_image:
                    extracted = await self._vision_extract(
                        pdf_path, page.page_number
                    )
                    if extracted:
                        structured_blocks.extend(extracted)
                    continue

                # Header detection: larger font = likely a section header
                avg_font = (
                    sum(block.font_sizes) / len(block.font_sizes)
                    if block.font_sizes else 12
                )
                is_header = avg_font > 14 or block.text.isupper()

                if is_header:
                    current_section_title = block.text
                    current_section = self._classify_section(block.text)

                structured_blocks.append(StructuredBlock(
                    text=block.text,
                    bbox=block.bbox,
                    page_number=block.page_number,
                    section_title=current_section_title,
                    section_type=current_section,
                    is_header=is_header,
                    content_type="header" if is_header else "prose",
                ))

            structured.append(StructuredPage(
                page_number=page.page_number, blocks=structured_blocks
            ))
        return structured

    def _classify_section(self, header_text: str) -> str:
        """Map header text to section_type via pattern matching.
        Covers most insurance document headers. LLM fallback for edge cases."""
        header_lower = header_text.lower().strip()

        SECTION_PATTERNS = {
            "benefits": [
                "benefit", "schedule of benefit", "coverage",
                "what is covered", "plan benefits", "table of benefits",
            ],
            "premiums": [
                "premium", "pricing", "cost", "rate table",
                "premium schedule",
            ],
            "exclusions": [
                "exclusion", "not covered", "limitation",
                "waiting period", "what is not covered",
            ],
            "eligibility": [
                "eligibility", "entry age", "who can apply",
                "underwriting",
            ],
            "claims": [
                "claim", "how to claim", "claims procedure",
                "making a claim",
            ],
            "riders": [
                "rider", "optional benefit", "add-on",
                "supplementary",
            ],
            "definitions": [
                "definition", "glossary", "meaning of terms",
            ],
        }

        for section_type, patterns in SECTION_PATTERNS.items():
            if any(p in header_lower for p in patterns):
                return section_type

        return "general"

    async def _vision_extract(
        self, pdf_path: Path, page_number: int
    ) -> list[StructuredBlock] | None:
        """Multimodal fallback: render page as image, send to Claude
        for text extraction. Used for scanned pages or image-heavy
        marketing brochures."""
        import fitz
        import base64
        from anthropic import Anthropic

        doc = fitz.open(str(pdf_path))
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=200)
        image_bytes = pix.tobytes("png")

        client = Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(image_bytes).decode(),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract all text from this insurance document page. "
                            "Return as JSON array: "
                            '[{"text": "...", "section_type": "..."}]. '
                            "section_type must be one of: benefits, premiums, "
                            "exclusions, eligibility, claims, riders, "
                            "definitions, general."
                        ),
                    },
                ],
            }],
        )
        # Parse response into StructuredBlocks
        # (bbox not available from vision extraction)
        ...

    # ── Step 8: Validation ─────────────────────────────────────────

    def _validate(
        self, doc_id: str, chunks: list, tables: list
    ) -> list[str]:
        """Post-ingestion validation catches silent failures."""
        errors = []

        if len(chunks) == 0:
            errors.append(f"{doc_id}: No text chunks extracted")

        empty_chunks = [c for c in chunks if len(c.text.strip()) < 20]
        if empty_chunks:
            errors.append(
                f"{doc_id}: {len(empty_chunks)} chunks with <20 chars"
            )

        # Verify SQLite has rows for each table found
        for table in tables:
            count = self.sqlite.count_rows(doc_id, table.table_type)
            if count == 0:
                errors.append(
                    f"{doc_id}: Table '{table.table_type}' found "
                    f"but 0 SQLite rows inserted"
                )

        return errors
```

### Batch Ingestion Script

```python
# rag/ingest_all.py
import asyncio
from pathlib import Path

async def ingest_all():
    pipeline = DocumentIngestionPipeline()
    pdf_dir = Path("data/raw")
    results = []

    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        print(f"Ingesting: {pdf_path.name}")
        result = await pipeline.ingest_pdf(pdf_path)
        results.append(result)
        print(
            f"  → {result.text_chunks_count} chunks, "
            f"{result.tables_extracted} tables, "
            f"{result.sqlite_rows_inserted} SQLite rows"
        )
        if result.errors:
            for err in result.errors:
                print(f"  ⚠ {err}")

    # Summary
    total_chunks = sum(r.text_chunks_count for r in results)
    total_tables = sum(r.tables_extracted for r in results)
    total_errors = sum(len(r.errors) for r in results)
    print(
        f"\nDone: {len(results)} documents, {total_chunks} chunks, "
        f"{total_tables} tables, {total_errors} errors"
    )

if __name__ == "__main__":
    asyncio.run(ingest_all())
```

### Key Design Decisions

**Dedup by content hash:** Re-running ingestion skips already-processed documents. This matters because you'll iterate on chunking strategy and want to selectively re-ingest. To force re-ingestion, delete the doc_id from SQLite's policies table.

**Font-size heuristic for section detection:** Insurance PDFs use larger fonts for section headers. This avoids an LLM call for ~80% of cases. The LLM fallback handles ambiguous headers like "Table 3A" that don't match keyword patterns.

**Vision fallback for image-heavy pages:** Some insurance brochures embed benefit tables as images, not text. Rendering the page as PNG and sending to Claude's vision handles this without OCR tooling like Tesseract. The tradeoff: no bounding box data from vision-extracted text (since the LLM returns text without coordinates).

**Table-to-text dual storage:** Every extracted table goes to SQLite (for exact numerical queries) and as a text chunk to Qdrant (for conversational queries). "What's the premium for age 30?" hits SQLite. "Tell me about the pricing" hits Qdrant. The Retrieval Agent prefers the SQL path when it detects numerical intent via the Router's extracted entities.

**Validation step:** Catches silent failures — empty chunks, missing table rows, pages where extraction returned nothing. In practice, you discover these when debugging "why is my retrieval bad for this policy?" Having validation from day one saves hours of debugging later.

### Chunking Strategy
- **Parent-child chunking:** Store small chunks for retrieval precision, but retrieve the parent chunk for context completeness. This is a strong interview talking point.
- **Section-aware splitting:** Use document structure (headers, section breaks) rather than naive character splitting. The `section_type` metadata is assigned during this step.
- **Metadata enrichment:** Each chunk gets document-level, chunk-level, and derived metadata as specified above.

### Embedding Model Choice
- **Primary:** BGE-M3 (multilingual, supports dense + sparse in one model — aligns with hybrid search story)
- **Alternative:** Cohere embed-v3 (if you want to show you can evaluate embedding models)
- **Resume signal:** Justify your choice with a sentence in the README about why you picked it (multilingual for potential Mandarin/Malay support, dimensionality tradeoff, etc.)

### Retrieval Flow
1. User query → Router resolves context, classifies intent, extracts entities
2. Retrieval Agent builds metadata filters from entities (provider, policy_type, section_type, doc_year)
3. Dense retrieval via Qdrant with metadata filters (top-20)
4. Sparse retrieval via BM25 index (top-20)
5. Reciprocal Rank Fusion → merged top-10
6. Re-ranking pass (Cohere reranker or cross-encoder) → final top-5
7. Parent chunk expansion via `parent_chunk_id` → fuller context
8. If `has_table` or numerical intent → also query SQLite structured store
9. All results + metadata written to state for Analysis Agent

### Resume Signal

The three-store architecture (vector for text, SQLite for numbers, filesystem for source PDFs) combined with rich metadata filtering shows you understand that production RAG is not just "embed and search." Metadata-filtered vector search, parent-child retrieval, and dual-store routing for numerical data are the patterns that separate production systems from tutorial demos.

---

## Generative UI — Frontend Architecture

The frontend uses **Vercel AI SDK's `streamUI`** (`ai/rsc`) so that React components stream progressively from the server as the Visualization Agent produces output — no polling, no custom SSE parser, no client-side JSON→component mapping.

### Architecture Overview

```
User Message
     │
     ▼
Next.js Server Action  ──▶  FastAPI (LangGraph agents)
  (streamUI)                 Router → Retrieval → Analysis
     │                               │
     │                               ▼
     │                    Visualization Agent
     │                    (AnalysisOutput JSON)
     │                               │
     │◀──────── structured JSON ─────┘
     │
     ▼
streamUI resolves tool calls → streams React components to client
     │
     ▼
Chat Panel (token-by-token text)  +  Canvas Panel (streamed components)
```

The Next.js server action acts as a BFF (Backend for Frontend): it calls the FastAPI LangGraph pipeline, receives the `AnalysisOutput` + `ui_components` JSON, then feeds that into `streamUI` which decides which React component to stream back to the client.

### Server Action — `streamUI` Definition

```typescript
// app/actions/chat.ts
"use server";

import { streamUI } from "ai/rsc";
import { anthropic } from "@ai-sdk/anthropic";
import { z } from "zod";
import {
  ComparisonTable,
  PremiumLineChart,
  CoverageRadarChart,
  PremiumBarChart,
  PolicyCard,
  DecisionTreeDiagram,
  CoverageGapHighlight,
  SourceCitations,
} from "@/components/canvas";

export async function submitMessage(userMessage: string) {
  // 1. Call FastAPI LangGraph pipeline
  const agentResponse = await fetch(
    `${process.env.API_URL}/api/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMessage }),
    }
  ).then((r) => r.json());

  // 2. Stream React components using Vercel AI SDK streamUI
  //    The Visualization Agent JSON becomes the tool call arguments
  const result = await streamUI({
    model: anthropic("claude-sonnet-4-20250514"),
    // System prompt instructs the model to call tools based on the
    // structured output from the FastAPI agent pipeline
    system: `You are a UI renderer. The user has received this analysis:
${JSON.stringify(agentResponse.analysis)}.
Call the appropriate visualization tools to render the response.
Always call source_citations last.`,
    prompt: userMessage,
    text: ({ content }) => <p className="text-sm">{content}</p>,
    tools: {
      comparison_table: {
        description: "Render a side-by-side policy comparison table",
        parameters: z.object({
          policies: z.array(
            z.object({
              name: z.string(),
              provider: z.string(),
              annual_premium: z.number().nullable(),
              coverage_amount: z.number().nullable(),
              policy_term: z.string().nullable(),
              key_features: z.array(z.string()),
              key_differences: z.array(z.string()),
            })
          ),
          highlight_columns: z.array(z.string()),
        }),
        generate: async ({ policies, highlight_columns }) => (
          <ComparisonTable
            policies={policies}
            highlightColumns={highlight_columns}
          />
        ),
      },
      line_chart: {
        description: "Render a line chart for premium projections over time",
        parameters: z.object({
          title: z.string(),
          xAxis: z.string(),
          series: z.array(
            z.object({
              name: z.string(),
              data: z.array(
                z.object({ age: z.number(), cumulative: z.number() })
              ),
            })
          ),
        }),
        generate: async ({ title, xAxis, series }) => (
          <PremiumLineChart title={title} xAxis={xAxis} series={series} />
        ),
      },
      radar_chart: {
        description: "Render a radar chart for multi-dimensional coverage comparison",
        parameters: z.object({
          title: z.string(),
          categories: z.array(z.string()),
          series: z.array(
            z.object({ name: z.string(), data: z.array(z.number()) })
          ),
        }),
        generate: async ({ title, categories, series }) => (
          <CoverageRadarChart
            title={title}
            categories={categories}
            series={series}
          />
        ),
      },
      bar_chart: {
        description: "Render a bar chart for premium breakdown by category",
        parameters: z.object({
          title: z.string(),
          categories: z.array(z.string()),
          series: z.array(
            z.object({ name: z.string(), data: z.array(z.number()) })
          ),
        }),
        generate: async ({ title, categories, series }) => (
          <PremiumBarChart
            title={title}
            categories={categories}
            series={series}
          />
        ),
      },
      policy_card: {
        description: "Render a summary card for a single policy",
        parameters: z.object({
          name: z.string(),
          key_figures: z.array(
            z.object({ label: z.string(), value: z.string() })
          ),
          actions: z.array(z.string()),
        }),
        generate: async ({ name, key_figures, actions }) => (
          <PolicyCard name={name} keyFigures={key_figures} actions={actions} />
        ),
      },
      decision_tree: {
        description: "Render a decision tree diagram via Mermaid",
        parameters: z.object({ mermaid: z.string() }),
        generate: async ({ mermaid }) => (
          <DecisionTreeDiagram mermaid={mermaid} />
        ),
      },
      coverage_gap: {
        description: "Render a visual highlight of coverage gaps",
        parameters: z.object({
          gaps: z.array(
            z.object({ label: z.string(); severity: z.enum(["low", "medium", "high"]) })
          ),
        }),
        generate: async ({ gaps }) => <CoverageGapHighlight gaps={gaps} />,
      },
      source_citations: {
        description: "Render collapsible source references for all claims",
        parameters: z.object({
          citations: z.array(
            z.object({
              chunk_id: z.string(),
              doc_title: z.string(),
              page_number: z.number(),
              section_title: z.string().nullable(),
              relevant_excerpt: z.string(),
              bbox: z
                .object({
                  x0: z.number(),
                  y0: z.number(),
                  x1: z.number(),
                  y1: z.number(),
                })
                .nullable(),
            })
          ),
        }),
        generate: async ({ citations }) => (
          <SourceCitations citations={citations} />
        ),
      },
    },
  });

  return result.value;
}
```

### Client — `useUIState` + Server Action

```typescript
// app/page.tsx
"use client";

import { useState } from "react";
import { useUIState, useActions } from "ai/rsc";
import type { AI } from "./ai";

export default function ChatPage() {
  const [messages, setMessages] = useUIState<typeof AI>();
  const { submitMessage } = useActions<typeof AI>();
  const [input, setInput] = useState("");

  async function handleSubmit() {
    // Optimistically add user message
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", display: input },
    ]);

    // Server action streams React nodes back — no JSON parsing on client
    const response = await submitMessage(input);
    setMessages((prev) => [
      ...prev,
      { id: Date.now() + 1, role: "assistant", display: response },
    ]);
    setInput("");
  }

  return (
    <div className="flex h-screen">
      {/* Chat Panel */}
      <div className="w-1/2 flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((m) => (
            <div key={m.id}>{m.display}</div>
          ))}
        </div>
        <div className="p-4 border-t flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            className="flex-1 border rounded px-3 py-2"
          />
          <button onClick={handleSubmit}>Send</button>
        </div>
      </div>

      {/* Canvas Panel — components stream into here via useUIState */}
      <div className="w-1/2 border-l p-4 overflow-y-auto">
        {/* Canvas components are part of the streamed message display */}
      </div>
    </div>
  );
}
```

### AI Provider Setup

```typescript
// app/ai.ts
import { createAI } from "ai/rsc";
import { submitMessage } from "./actions/chat";

export const AI = createAI({
  actions: { submitMessage },
  initialUIState: [] as { id: number; role: string; display: React.ReactNode }[],
  initialAIState: [] as { role: string; content: string }[],
});
```

```typescript
// app/layout.tsx
import { AI } from "./ai";

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <AI>{children}</AI>
      </body>
    </html>
  );
}
```

### Visualization Components

| Component | Library | Use Case |
|-----------|---------|----------|
| `ComparisonTable` | Custom React | Side-by-side policy comparison |
| `PremiumLineChart` | Recharts | Premium projections over time |
| `CoverageRadarChart` | Recharts | Coverage area comparison |
| `PremiumBarChart` | Recharts | Premium breakdown by category |
| `DecisionTreeDiagram` | Mermaid.js | "Which policy type suits you?" |
| `CoverageGapHighlight` | Custom SVG | Visual highlight of coverage holes |
| `PolicyCard` | Custom React | Summary card for a single policy |
| `SourceCitations` | Custom React | Collapsible source references with PDF highlight |

### Streaming UX

- **Text:** Streams token-by-token into Chat Panel via `streamUI`'s `text` callback
- **Components:** Stream progressively as the Visualization Agent resolves tool calls — comparison table appears first, charts follow, citations last
- **Loading state:** Suspense boundaries + skeleton components shown while each tool's `generate` function resolves
- **No client-side JSON parsing:** The `streamUI` protocol handles serialization; the client receives React nodes, not raw JSON

### Why Vercel AI SDK `streamUI` over Custom SSE

| Concern | Custom SSE + JSON | Vercel `streamUI` |
|---------|-------------------|-------------------|
| Component protocol | Manual JSON spec + client registry | Tool call schema enforced by Zod |
| Streaming granularity | Full JSON blob at end | Component-by-component as tools resolve |
| Type safety | Runtime duck-typing | Zod schemas validated at server action boundary |
| Loading states | Manual skeleton logic | Suspense-native per component |
| Error handling | Custom error events | Server action error propagation |

**Resume signal:** Using `streamUI` with tool-defined React components is rare in portfolios. It demonstrates understanding of React Server Components, the Vercel AI SDK's RSC streaming protocol, and how to bridge a Python LangGraph backend to a Next.js generative UI layer.

---

## Production Patterns (Resume Signals)

### 1. Evaluation Pipeline (Ragas / DeepEval)

```python
# eval/evaluate_rag.py
from ragas import evaluate
from ragas.metrics import (
    faithfulness,        # Is the answer grounded in retrieved docs?
    answer_relevancy,    # Does the answer address the question?
    context_precision,   # Are the retrieved docs relevant?
    context_recall,      # Did we retrieve all relevant docs?
)

# Golden dataset: 50-100 curated Q&A pairs with ground truth
results = evaluate(
    dataset=golden_dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
)
# Output: scores per metric, exportable to dashboard
```

**What to show in README/portfolio:**
- Faithfulness: 0.89, Context Precision: 0.84 (example scores)
- "Improved faithfulness from 0.71 to 0.89 by switching to parent-child chunking"
- A screenshot of eval results or a simple chart

### 2. Guardrails

```python
# guardrails/validator.py
class InsuranceBotGuardrails:
    def validate_input(self, user_msg: str) -> ValidationResult:
        # Topic boundary: reject off-topic (crypto advice, medical diagnosis)
        # PII detection: flag if user shares NRIC, bank details
        # Prompt injection detection: basic pattern matching + LLM check

    def validate_output(self, response: str, sources: list) -> ValidationResult:
        # Hallucination check: verify claims against source chunks
        # Regulatory compliance: flag if response gives specific financial advice
        #   without disclaimer
        # Confidence threshold: if retrieval scores are low, add uncertainty
        #   language
```

### 3. Observability (LangFuse)

Instrument every agent call with traces:
- **Trace per conversation turn:** Shows the full agent graph execution
- **Span per agent:** Router → Retrieval → Analysis → Visualization, each with latency + token count
- **Retrieval quality logging:** Log query, retrieved chunks, relevance scores
- **Screenshot for portfolio:** A LangFuse trace showing the multi-agent flow is visually impressive in a README

### 4. Semantic Cache (Redis)

```python
# cache/semantic_cache.py
class SemanticCache:
    def __init__(self, redis_client, embedding_model, threshold=0.92):
        self.redis = redis_client
        self.embedder = embedding_model
        self.threshold = threshold

    async def get(self, query: str):
        query_embedding = self.embedder.encode(query)
        # Search Redis for cached query embeddings within threshold
        # If match found, return cached response (skip LLM entirely)

    async def set(self, query: str, response: dict):
        # Store query embedding + response with TTL
```

**Resume signal:** Shows cost-awareness and latency optimization — production concerns, not just demo concerns.

---

## Source Attribution & Document Highlighting

Every claim the system makes must be traceable to a specific location in a source document — not just "this chunk was retrieved," but "page 12, paragraph 3 of AIA Shield Plan brochure." This is the Perplexity-style UX applied to a domain-specific corpus.

### Ingestion-Time: Preserve Location Metadata

Location data must be captured during chunking. Reconstructing it later is fragile and unreliable.

```python
# rag/chunker.py
@dataclass
class ChunkMetadata:
    doc_id: str              # "aia-shield-plan-2024"
    doc_title: str           # "AIA HealthShield Gold Max"
    page_numbers: list[int]  # [12, 13] if chunk spans pages
    section_title: str       # "Benefit Schedule"
    bbox: dict | None        # {"x0": 72, "y0": 200, "x1": 540, "y1": 340}
    paragraph_index: int     # position within page
    source_url: str | None   # link to original PDF if public

# PyMuPDF (fitz) extraction — gives bounding boxes per text block
import fitz

def extract_chunks_with_location(pdf_path: str) -> list[Chunk]:
    doc = fitz.open(pdf_path)
    chunks = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for block_idx, block in enumerate(blocks):
            if block["type"] == 0:  # text block
                text = " ".join(
                    span["text"]
                    for line in block["lines"]
                    for span in line["spans"]
                )
                chunks.append(Chunk(
                    text=text,
                    metadata=ChunkMetadata(
                        doc_id=derive_doc_id(pdf_path),
                        doc_title=extract_title(doc),
                        page_numbers=[page_num + 1],
                        section_title=detect_section(text, page),
                        bbox={
                            "x0": block["bbox"][0],
                            "y0": block["bbox"][1],
                            "x1": block["bbox"][2],
                            "y1": block["bbox"][3],
                        },
                        paragraph_index=block_idx,
                        source_url=None,
                    ),
                ))
    return chunks
```

**Why PyMuPDF:** It provides bounding box coordinates per text block, enabling pixel-level highlighting on the original PDF page. pdfplumber is the alternative when table-aware extraction is needed.

### Retrieval-Time: Carry Metadata Through the Agent Pipeline

Every retrieved chunk retains its full metadata through Router → Retrieval → Analysis → Visualization. The Analysis Agent's structured output references chunk IDs for every claim:

```json
{
  "claims": [
    {
      "claim_id": "c1",
      "text": "AIA HealthShield Gold Max covers up to $1M per policy year",
      "source_refs": [
        {
          "chunk_id": "chunk_a3f2",
          "doc_title": "AIA HealthShield Gold Max Brochure",
          "page_number": 12,
          "section_title": "Benefit Schedule",
          "bbox": {"x0": 72, "y0": 200, "x1": 540, "y1": 340},
          "relevant_excerpt": "The maximum policy year benefit is $1,000,000..."
        }
      ],
      "confidence": 0.95
    },
    {
      "claim_id": "c2",
      "text": "The annual premium for a 30-year-old is approximately $315",
      "source_refs": [
        {
          "chunk_id": "chunk_a3f2",
          "doc_title": "AIA HealthShield Gold Max Brochure",
          "page_number": 12,
          "section_title": "Benefit Schedule"
        },
        {
          "chunk_id": "chunk_b7c1",
          "doc_title": "AIA HealthShield Gold Max Brochure",
          "page_number": 18,
          "section_title": "Premium Table"
        }
      ],
      "confidence": 0.88
    }
  ]
}
```

**Critical prompt instruction for the Analysis Agent:** "For every factual claim you make, you MUST include the chunk_id(s) that support it. If you cannot attribute a claim to a specific chunk, mark it as `ungrounded: true`."

### Frontend: Inline Citations + Source Viewer

The UX has two parts — inline citation markers in the Chat Panel, and a Source Viewer component in the Canvas Panel.

#### Chat Panel — Inline Citations

```
AIA HealthShield Gold Max covers up to $1M per policy year [1].
The annual premium for a 30-year-old is approximately $315 [1][2].

The plan includes coverage for Class A ward stays [3], with
co-insurance rates varying by claim tier [3].
```

Each `[n]` is a clickable badge. Tapping it opens the Source Viewer in the Canvas Panel.

#### Canvas Panel — Source Viewer (Two Modes)

**Mode 1: Quick Preview (lightweight, default)**
```
┌─────────────────────────────────────────────────┐
│ [1] AIA HealthShield Gold Max Brochure          │
│     Page 12 — "Benefit Schedule"                │
│ ┌─────────────────────────────────────────────┐ │
│ │ "The maximum policy year benefit is         │ │
│ │  $1,000,000 for HealthShield Gold Max       │ │
│ │  plan holders..."                           │ │
│ └─────────────────────────────────────────────┘ │
│              [View in Document →]                │
└─────────────────────────────────────────────────┘
```

**Mode 2: Full Document View (impressive in demo)**
- PDF rendered via `react-pdf` in the Canvas Panel
- Auto-scrolled to the exact page referenced
- Bounding box highlighted with a semi-transparent colored overlay
- Multiple citations on the same page get different highlight colors

```typescript
// components/canvas/SourceViewer.tsx
interface SourceReference {
  chunkId: string;
  docTitle: string;
  pageNumber: number;
  bbox?: { x0: number; y0: number; x1: number; y1: number };
  relevantExcerpt: string;
}

interface SourceViewerProps {
  references: SourceReference[];
  activeCitationIndex: number | null;
  mode: "preview" | "document";
}

// PDF highlight overlay — positioned using bbox from PyMuPDF
function HighlightOverlay({ bbox, pageWidth, pageHeight, renderWidth }) {
  const scale = renderWidth / pageWidth;
  return (
    <div
      style={{
        position: "absolute",
        left: bbox.x0 * scale,
        top: bbox.y0 * scale,
        width: (bbox.x1 - bbox.x0) * scale,
        height: (bbox.y1 - bbox.y0) * scale,
        backgroundColor: "rgba(59, 130, 246, 0.2)",
        border: "2px solid rgba(59, 130, 246, 0.6)",
        borderRadius: 4,
        pointerEvents: "none",
      }}
    />
  );
}
```

### Connection to Hallucination Prevention

Source attribution and faithfulness checking reinforce each other:

1. **At generation time:** Any claim the Analysis Agent produces without a `source_ref` is automatically flagged as `ungrounded`
2. **At validation time:** The faithfulness checker (see Guardrails section) cross-references claim text against the linked source excerpts
3. **At display time:** Ungrounded claims are either removed, shown with a visual caveat ("⚠ Based on general knowledge, not a specific document"), or trigger a regeneration with stricter constraints
4. **At user interaction time:** The user can click any citation to verify the claim themselves — building trust and completing the responsible-AI story

### Resume Signal

The portfolio narrative: "Every claim is grounded, attributed, and user-verifiable — with pixel-level highlighting on the original source document." This demonstrates retrieval traceability, structured output design, and responsible AI in a single feature. A screenshot showing the citation flow (chat → highlight → PDF) is one of the most visually compelling things you can put in a README.

---

## Structured Data Extraction & Numerical Visualization

Insurance documents contain two fundamentally different types of content: unstructured text (policy descriptions, terms, exclusions) and structured numerical data (premium tables, benefit schedules, payout limits). These require different extraction, storage, retrieval, and presentation strategies.

### Dual-Store Ingestion Pattern

During document ingestion, text and tables follow parallel pipelines into separate stores:

```
PDF Document
    │
    ├──▶ Text Extraction (PyMuPDF)
    │        │
    │        ▼
    │    Chunking + Embedding
    │        │
    │        ▼
    │    Qdrant (vector store)         →  "What does this policy cover?"
    │
    └──▶ Table Extraction (pdfplumber)
             │
             ▼
         Structured JSON / SQLite      →  "What's the premium for age 30?"
```

**pdfplumber for tables:** It's significantly better than PyMuPDF at detecting table boundaries and cell positions. For messier PDFs where table detection fails, fall back to a multimodal LLM — send the page image to Claude and ask it to extract the table as JSON.

```python
# rag/table_extractor.py
import pdfplumber

def extract_structured_tables(pdf_path: str) -> list[PolicyTable]:
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            for table in page.extract_tables():
                classified = classify_table(table)  # LLM or heuristic
                if classified:
                    tables.append(PolicyTable(
                        doc_id=derive_doc_id(pdf_path),
                        page_number=page_num + 1,
                        table_type=classified.type,  # "premium_schedule", "benefit_limit", etc.
                        data=classified.structured_data,
                    ))
    return tables

# A premium table becomes queryable structured data:
{
    "doc_id": "aia-shield-gold-max-2024",
    "table_type": "premium_schedule",
    "policy_name": "AIA HealthShield Gold Max",
    "data": [
        {"age": 25, "annual_premium": 263, "with_rider": 387},
        {"age": 30, "annual_premium": 315, "with_rider": 456},
        {"age": 35, "annual_premium": 402, "with_rider": 578},
        {"age": 40, "annual_premium": 531, "with_rider": 743},
    ]
}

# Multimodal fallback for messy tables
async def extract_table_via_vision(page_image: bytes) -> dict:
    response = await claude.invoke(
        system="Extract the table from this image as structured JSON. "
               "Identify column headers, row labels, and all numerical values.",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "data": page_image}},
                {"type": "text", "text": "Extract this table as JSON."}
            ]
        }]
    )
    return parse_json(response)
```

### Retrieval Agent — Dual-Store Routing

The Retrieval Agent must decide which store to query based on the Router Agent's intent and extracted entities:

```python
# agents/retrieval.py
async def retrieval_agent(state: InsureBotState) -> InsureBotState:
    entities = state["extracted_entities"]
    intent = state["intent"]

    # Numerical queries → structured store
    if needs_numerical_data(entities, intent):
        structured_results = query_structured_store(
            policy_name=entities.get("policy_name"),
            table_type=infer_table_type(intent),  # "premium_schedule", "benefit_limit"
            filters={"age": entities.get("age")},
        )
        state["structured_data"] = structured_results

    # Text queries → vector store (existing hybrid search pipeline)
    if needs_text_context(intent):
        text_chunks = await hybrid_search(
            query=state["user_message"],
            filters=build_metadata_filters(entities),
        )
        state["retrieved_chunks"] = text_chunks

    # Comparison queries → both stores
    if intent == "policy_comparison":
        # Retrieve text for each policy being compared
        # Retrieve numerical data for side-by-side figures
        pass

    return state

def needs_numerical_data(entities: dict, intent: str) -> bool:
    """Heuristic: if the user mentions age, income, premium, cost,
    or the intent involves comparison, we need structured data."""
    numerical_signals = {"age", "income", "premium", "cost", "price", "payout"}
    return bool(numerical_signals & set(entities.keys())) or intent == "policy_comparison"
```

### Visualization Agent — Data Shape to Component Mapping

The Visualization Agent uses deterministic rules for common patterns and LLM fallback for edge cases. The core principle: **numerical data should always be visualized, not just described in words.**

```python
# agents/visualization.py
def decide_components(analysis: AnalysisResult) -> list[ComponentSpec]:
    components = []

    # Multiple policies with premiums → comparison table + bar chart
    if len(analysis.policies) > 1 and has_premium_data(analysis):
        components.append(ComponentSpec(
            type="comparison_table",
            props=build_comparison_table(analysis.policies)
        ))
        components.append(ComponentSpec(
            type="bar_chart",
            props={
                "title": "Annual Premium Comparison",
                "categories": [p.name for p in analysis.policies],
                "series": [
                    {"name": "Base Premium", "data": [p.base_premium for p in analysis.policies]},
                    {"name": "With Rider", "data": [p.rider_premium for p in analysis.policies]},
                ]
            }
        ))

    # Time-series data → line chart (premium projections, cash value growth)
    if analysis.projection_data:
        components.append(ComponentSpec(
            type="line_chart",
            props={
                "title": "Cumulative Premium: Term Life vs Whole Life (Age 30-50)",
                "xAxis": "Age",
                "series": [
                    {
                        "name": "AIA Term Life",
                        "data": [
                            {"age": 30, "cumulative": 1200},
                            {"age": 35, "cumulative": 6000},
                            {"age": 40, "cumulative": 12500},
                            {"age": 50, "cumulative": 34000},
                        ]
                    },
                    {
                        "name": "Prudential PRULife Vantage",
                        "data": [
                            {"age": 30, "cumulative": 3600},
                            {"age": 35, "cumulative": 18000},
                            {"age": 40, "cumulative": 36000},
                            {"age": 50, "cumulative": 72000},
                        ]
                    }
                ]
            }
        ))

    # Coverage areas with amounts → radar chart
    if analysis.coverage_breakdown:
        components.append(ComponentSpec(
            type="radar_chart",
            props={
                "title": "Coverage Area Comparison",
                "categories": ["Hospitalization", "Outpatient", "Surgical",
                               "Critical Illness", "Death Benefit"],
                "series": [
                    {"name": p.name, "data": p.coverage_amounts}
                    for p in analysis.policies
                ]
            }
        ))

    # Single policy → summary card with key figures
    if len(analysis.policies) == 1:
        p = analysis.policies[0]
        components.append(ComponentSpec(
            type="policy_card",
            props={
                "name": p.name,
                "key_figures": [
                    {"label": "Annual Premium (age 30)", "value": "$315"},
                    {"label": "Policy Year Limit", "value": "$1,000,000"},
                    {"label": "Lifetime Limit", "value": "$2,000,000"},
                    {"label": "Ward Class", "value": "A"},
                    {"label": "Co-insurance (below $5K)", "value": "10%"},
                    {"label": "Co-insurance (above $5K)", "value": "5%"},
                ],
                "actions": ["View Premium Table", "Compare Plans"]
            }
        ))

    # Always include source citations
    components.append(ComponentSpec(
        type="source_citations",
        props=build_citations(analysis.sources)
    ))

    return components
```

### Visualization Decision Matrix

| Data Shape | Component | Why Not Words |
|-----------|-----------|---------------|
| 2+ policies with premiums | Comparison table + bar chart | Numbers side-by-side are instantly scannable; paragraphs require mental tracking |
| Premium over time / age bands | Line chart | Trends and crossover points are invisible in text |
| Coverage areas with dollar amounts | Radar chart | Relative strengths across categories are hard to compare verbally |
| Benefit breakdown by category | Stacked bar chart | Proportions and totals are immediately visible |
| Single policy overview | Policy card with key figures | Structured layout beats a paragraph of numbers |
| Payout scenarios (death, CI, disability) | Decision tree / flow diagram | Conditional logic is clearer as a visual flow |
| Premium vs claim history | Scatter or line chart | Correlation patterns only emerge visually |

### Resume Signal

The dual-store pattern (vector store for text, structured store for numbers) shows you understand that RAG isn't just "embed everything and search." Numerical data needs different retrieval and different presentation. Most portfolio chatbots treat tables as text chunks and then hallucinate the numbers. This system extracts them as structured data and renders them visually — a production-level distinction that interviewers will remember.

---

## Data Sources

| Source | Content | Format | URL |
|--------|---------|--------|-----|
| MAS | Insurance regulations, notices | PDF/HTML | mas.gov.sg |
| LIA Singapore | Industry guidelines | PDF | lia.org.sg |
| CPF Board | MediShield Life, CareShield | HTML | cpf.gov.sg |
| Major Insurers | Product brochures, benefit tables | PDF | (AIA, Prudential, Great Eastern, NTUC Income, etc.) |
| MOH | Healthcare cost benchmarks | PDF/HTML | moh.gov.sg |

---

## Project Structure

```
insurebot-sg/
├── README.md                    # Portfolio-quality writeup
├── docker-compose.yml           # One-command startup
├── pyproject.toml
│
├── backend/
│   ├── main.py                  # FastAPI app + SSE endpoints
│   ├── models.py                # Pydantic models (state, intents, claims, components)
│   ├── agents/
│   │   ├── graph.py             # LangGraph state machine
│   │   ├── router.py            # Router Agent
│   │   ├── retrieval.py         # Retrieval Agent (hybrid search)
│   │   ├── analysis.py          # Analysis Agent
│   │   └── visualization.py     # Visualization Agent
│   ├── rag/
│   │   ├── ingest.py            # Document ingestion pipeline (8-step)
│   │   ├── ingest_all.py        # Batch ingestion script for all PDFs
│   │   ├── chunker.py           # Section-aware + parent-child
│   │   ├── table_extractor.py   # pdfplumber table extraction + vision fallback
│   │   ├── metadata_enricher.py # Derive ages, amounts, key_terms from chunks
│   │   ├── structured_store.py  # SQLite store for numerical data
│   │   ├── qdrant_setup.py      # Collection creation + payload indexes
│   │   ├── embedder.py          # Embedding model wrapper (BGE-M3)
│   │   ├── retriever.py         # Hybrid retrieval + RRF + dual-store routing
│   │   └── reranker.py          # Cross-encoder reranking
│   ├── guardrails/
│   │   ├── input_validator.py
│   │   ├── output_validator.py
│   │   └── faithfulness_check.py
│   ├── cache/
│   │   └── semantic_cache.py
│   └── observability/
│       └── langfuse_config.py
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── CanvasPanel.tsx
│   │   │   ├── canvas/
│   │   │   │   ├── ComparisonTable.tsx
│   │   │   │   ├── PremiumLineChart.tsx
│   │   │   │   ├── PremiumBarChart.tsx
│   │   │   │   ├── CoverageRadarChart.tsx
│   │   │   │   ├── DecisionTree.tsx
│   │   │   │   ├── PolicyCard.tsx
│   │   │   │   ├── SourceCitation.tsx
│   │   │   │   ├── SourceViewer.tsx
│   │   │   │   └── HighlightOverlay.tsx
│   │   │   └── CanvasRenderer.tsx
│   │   └── hooks/
│   │       └── useSSE.ts
│   └── package.json
│
├── eval/
│   ├── golden_dataset.json      # Curated Q&A test set
│   ├── evaluate_rag.py          # Ragas evaluation script
│   └── results/                 # Eval output + charts
│
├── data/
│   ├── raw/                     # Store 3: Original PDFs (for Source Viewer rendering)
│   ├── processed/               # Chunked text exports (JSON, for re-ingestion)
│   └── structured/
│       └── insurebot.db         # Store 2: SQLite database (premiums, benefits, policies)
│
└── docs/
    ├── architecture.md          # This document
    └── screenshots/             # LangFuse traces, UI demos
```

---

## Deployment

- **Docker Compose** for local: FastAPI + React + Qdrant + Redis containers (SQLite is embedded, no container needed; PDFs mounted as a volume)
- **README must include:** One-command setup (`docker compose up`), a 30-second demo GIF, architecture diagram, eval metrics, and a link to a LangFuse trace screenshot
- Optional: Deploy frontend to Vercel, backend to Railway or Fly.io for a live demo link

---

## Development Sprints

8 sprints across 8 weeks. Work is split across three parallel tracks that can be developed by separate developers. Tracks converge at integration points where components must be connected.

### Team Structure

| Track | Focus | Key Skills |
|-------|-------|-----------|
| **Track A: Data & RAG** | Ingestion pipeline, vector store, structured store, retrieval | Python, PDF parsing, embeddings, Qdrant, SQLite |
| **Track B: Agents & Backend** | LangGraph orchestration, agent logic, FastAPI, guardrails | Python, LangGraph, Claude API, FastAPI |
| **Track C: Frontend & UI** | React app, chat panel, canvas panel, visualization components | React, TypeScript, Recharts, Mermaid, SSE |

### Shared Foundation (Sprint 0 — Day 1-2, all tracks)

Before parallel work begins, all developers align on shared contracts.

```
All tracks together:
  ├── Set up monorepo structure (insurebot-sg/)
  ├── Define and review models.py (Pydantic models are the API contract)
  │   All tracks code against these types — this is the single source of truth
  ├── Set up Docker Compose skeleton (Qdrant, Redis, FastAPI, React containers)
  ├── Agree on InsureBotState shape — every agent reads/writes to this
  └── Collect 10-20 sample insurance PDFs into data/raw/
```

**Why this matters:** The Pydantic models define the interface between every component. Track A writes `RetrievedChunk` objects, Track B reads them. Track B writes `ComponentSpec` objects, Track C renders them. If the models aren't agreed upfront, integration breaks.

---

### Sprint 1 (Week 1) — Vertical Slice

Goal: One question flows end-to-end, even if each piece is basic.

```
Track A: Data & RAG
  ├── qdrant_setup.py — create collection with payload indexes
  ├── ingest.py — basic pipeline (PyMuPDF text extraction only, no tables yet)
  ├── chunker.py — naive section-aware splitting (by page or header)
  ├── embedder.py — BGE-M3 wrapper, encode + batch upload to Qdrant
  ├── Ingest 5 sample PDFs as proof of concept
  └── Deliverable: Qdrant populated with chunks, searchable via Python client

Track B: Agents & Backend
  ├── main.py — FastAPI app with /chat POST endpoint
  ├── models.py — finalize all Pydantic models (shared with other tracks)
  ├── graph.py — minimal LangGraph graph: router → retrieval → analysis → END
  ├── router.py — hardcoded intent classification (no LLM yet, pattern matching)
  ├── retrieval.py — basic semantic search against Qdrant (no hybrid yet)
  ├── analysis.py — pass retrieved chunks to Claude, get text response
  └── Deliverable: POST /chat returns a text answer grounded in retrieved chunks

Track C: Frontend & UI
  ├── React project setup (Vite + TypeScript + Tailwind)
  ├── App.tsx — two-panel layout (ChatPanel left, CanvasPanel right)
  ├── ChatPanel.tsx — message input, display user/bot messages
  ├── useSSE.ts hook — connect to backend (start with simple fetch, SSE later)
  ├── CanvasPanel.tsx — empty placeholder panel
  └── Deliverable: User types question, sees text response in chat panel
```

**🔗 Integration point (end of Sprint 1):** Connect frontend → FastAPI → LangGraph → Qdrant. One question answered end-to-end.

---

### Sprint 2 (Week 2) — Core Quality

Goal: Retrieval quality improves significantly, router uses LLM, tables extracted.

```
Track A: Data & RAG
  ├── table_extractor.py — pdfplumber table extraction
  ├── structured_store.py — SQLite schema (premiums, benefits, policies tables)
  ├── Ingest tables from PDFs into SQLite
  ├── metadata_enricher.py — derive mentions_ages, mentions_amounts, key_terms
  ├── Re-ingest all PDFs with full metadata (document-level + chunk-level)
  ├── retriever.py — add BM25 index + Reciprocal Rank Fusion
  └── Deliverable: Hybrid search (semantic + BM25 + RRF) with rich metadata

Track B: Agents & Backend
  ├── router.py — LLM-based intent classification with few-shot examples
  ├── Context resolution — resolve "this", "that policy" from conversation history
  ├── ExtractedEntities population — age, provider, policy_type from user message
  ├── retrieval.py — build metadata filters from extracted entities
  ├── retrieval.py — dual-store routing (Qdrant for text, SQLite for numbers)
  ├── analysis.py — structured output via Claude tool-use (Claim model with source_refs)
  └── Deliverable: Router classifies intents, retrieval uses metadata filters,
      analysis outputs structured claims with source attribution

Track C: Frontend & UI
  ├── ChatPanel.tsx — inline citation badges [1][2][3] in bot messages
  ├── CanvasRenderer.tsx — component registry mapping type → React component
  ├── PolicyCard.tsx — single policy summary with key figures
  ├── SourceCitation.tsx — collapsible source reference card (Mode 1: quick preview)
  ├── useSSE.ts — upgrade to Server-Sent Events for streaming
  └── Deliverable: Chat shows citations, canvas renders policy cards and source previews
```

**🔗 Integration point (end of Sprint 2):** Structured claims with source_refs flow from Analysis Agent → frontend renders inline citations + source preview cards.

---

### Sprint 3 (Week 3) — Multi-Agent Orchestration

Goal: Full agent graph with conditional routing, comparison flows work.

```
Track A: Data & RAG
  ├── reranker.py — Cohere reranker or cross-encoder integration
  ├── retriever.py — parent chunk expansion via parent_chunk_id
  ├── Ingest remaining PDFs (target: 20-30 policies across major SG insurers)
  ├── table_extractor.py — vision LLM fallback for image-heavy pages
  ├── ingest_all.py — batch ingestion script with progress logging
  └── Deliverable: Full corpus ingested, retrieval pipeline complete with reranking

Track B: Agents & Backend
  ├── graph.py — full conditional edges (see Router intent table)
  │   ├── policy_inquiry → retrieval (single) → analysis → visualization → END
  │   ├── compare_specific → retrieval (multi-query) → analysis → visualization → END
  │   ├── find_similar → retrieval (discover) → analysis → visualization → END
  │   ├── find_by_criteria → retrieval (structured store) → analysis → visualization → END
  │   ├── general_faq → retrieval → visualization → END
  │   └── off_topic → END
  ├── visualization.py — decide_components() logic (rule-based + LLM hybrid)
  ├── ConversationContext — accumulate discussed_policies, current_focus across turns
  ├── follow_up intent handling — parameter modification, meta-questions
  └── Deliverable: All intent flows work, multi-turn conversations maintain context

Track C: Frontend & UI
  ├── ComparisonTable.tsx — side-by-side policy comparison with highlights
  ├── PremiumBarChart.tsx — bar chart via Recharts for premium comparison
  ├── PremiumLineChart.tsx — line chart for premium projections over time
  ├── CoverageRadarChart.tsx — radar chart for coverage area comparison
  ├── CanvasPanel.tsx — render multiple components with staggered animations
  └── Deliverable: Canvas renders charts and tables from backend ComponentSpec JSON
```

**🔗 Integration point (end of Sprint 3):** Visualization Agent outputs ComponentSpec JSON → CanvasRenderer resolves and renders charts, tables, cards. Multi-agent routing verified for all intent types.

---

### Sprint 4 (Week 4) — Source Attribution & Guardrails

Goal: Every claim is verifiable, hallucination guardrails active.

```
Track A: Data & RAG
  ├── Verify bbox data quality across all ingested documents
  ├── Build mapping: chunk_id → {pdf_path, page_number, bbox}
  ├── API endpoint: GET /source/{chunk_id} returns PDF page + bbox coordinates
  ├── Create golden_dataset.json — 50-100 curated Q&A pairs with ground truth
  │   (manually verify answers against source PDFs)
  └── Deliverable: Source lookup API works, golden dataset ready for evaluation

Track B: Agents & Backend
  ├── guardrails/input_validator.py — topic boundaries, PII detection
  ├── guardrails/output_validator.py — confidence thresholds, disclaimer injection
  ├── guardrails/faithfulness_check.py — claim-level verification against sources
  ├── graph.py — insert guardrails node between retrieval and analysis
  │   ├── proceed → analysis (confidence above threshold)
  │   ├── low_confidence → visualization with caveat message
  │   └── blocked → END with polite refusal
  ├── Ungrounded claim handling — flag, add caveat, or regenerate
  └── Deliverable: Guardrails intercept low-confidence and ungrounded responses

Track C: Frontend & UI
  ├── SourceViewer.tsx — Mode 2: full PDF rendering via react-pdf
  ├── HighlightOverlay.tsx — bbox overlay on PDF pages
  ├── Click citation [1] → canvas switches to SourceViewer, scrolls to page
  ├── DecisionTree.tsx — Mermaid.js rendering for "which policy suits you?" flows
  ├── Loading skeletons in canvas while agents are working
  └── Deliverable: Full source attribution UX — click citation → see highlighted PDF
```

**🔗 Integration point (end of Sprint 4):** Claim → source_ref → PDF page with highlight. Guardrails active in agent graph. This is the "responsible AI" milestone.

---

### Sprint 5 (Week 5) — Production Patterns

Goal: Observability, caching, evaluation pipeline.

```
Track A: Data & RAG
  ├── eval/evaluate_rag.py — Ragas evaluation script
  │   ├── Run against golden_dataset.json
  │   ├── Measure: faithfulness, answer_relevancy, context_precision, context_recall
  │   └── Generate eval results as charts for README
  ├── Iterate on chunking/retrieval based on eval results
  │   ├── Tune chunk sizes, overlap percentages
  │   ├── Adjust RRF weights between semantic and BM25
  │   └── Test metadata filter combinations
  └── Deliverable: Eval scores documented, retrieval optimized

Track B: Agents & Backend
  ├── cache/semantic_cache.py — Redis-based semantic cache
  │   ├── Embed query → search cache → if similar enough, return cached response
  │   └── Cache miss → run full pipeline → store result with TTL
  ├── observability/langfuse_config.py — instrument every agent node
  │   ├── Trace per conversation turn
  │   ├── Span per agent with latency + token count
  │   └── Log retrieval scores, faithfulness check results
  ├── SSE streaming refinement — stream text tokens, then batch-send UI components
  └── Deliverable: LangFuse traces visible, cache reduces latency on repeated queries

Track C: Frontend & UI
  ├── Streaming UX polish — token-by-token text, then canvas components fade in
  ├── Error states — display graceful messages for low_confidence, blocked, off_topic
  ├── Responsive layout — chat + canvas panels work on different screen sizes
  ├── Dark/light mode support
  └── Deliverable: Polished, production-quality frontend UX
```

---

### Sprint 6 (Week 6) — Edge Cases & Hardening

Goal: Handle all conversational flows, stress test.

```
Track A: Data & RAG
  ├── Handle edge case PDFs — bilingual documents, scanned pages, unusual layouts
  ├── Re-ingest any PDFs that had extraction issues
  ├── Expand golden dataset with edge case questions
  ├── Re-run evaluation, document improvement (e.g., "faithfulness: 0.71 → 0.89")
  └── Deliverable: Robust ingestion across all document types, eval improvement documented

Track B: Agents & Backend
  ├── Test all intent flows end-to-end with real conversation scenarios
  │   ├── General FAQ → deep dive → comparison (escalation path)
  │   ├── Follow-up: "what about age 40?" (parameter modification)
  │   ├── Follow-up: "can you explain that chart?" (meta-question)
  │   ├── Find similar: "any other options?" (discover + compare)
  │   └── Off-topic graceful handling
  ├── Conversation context persistence — verify ConversationContext accumulates correctly
  ├── Rate limiting on Claude API calls
  └── Deliverable: All conversational flows verified, edge cases handled

Track C: Frontend & UI
  ├── Mobile-responsive chat interface
  ├── Canvas component interaction — click bar chart segment → see policy detail
  ├── Smooth transitions between canvas states (source viewer ↔ charts ↔ cards)
  ├── Accessibility audit (keyboard navigation, screen reader support)
  └── Deliverable: Frontend handles all component types, responsive + accessible
```

---

### Sprint 7 (Week 7) — Deployment & Documentation

Goal: One-command startup, portfolio-quality README.

```
Track A: Data & RAG
  ├── Package ingested data for distribution (Qdrant snapshot + SQLite db + PDFs)
  ├── Seed script: docker compose up → auto-ingest if stores are empty
  └── Deliverable: Fresh clone → docker compose up → fully populated stores

Track B: Agents & Backend
  ├── docker-compose.yml — FastAPI + Qdrant + Redis containers
  ├── Environment variable configuration (.env.example)
  ├── Health check endpoints for all services
  ├── API documentation (FastAPI auto-generates OpenAPI spec)
  └── Deliverable: Backend runs in Docker with health checks

Track C: Frontend & UI
  ├── Production build configuration
  ├── Record 30-second demo GIF showing key flows
  │   ├── General question → policy card
  │   ├── Comparison → charts + table
  │   ├── Click citation → PDF source viewer with highlight
  ├── Screenshot LangFuse trace for README
  └── Deliverable: Demo assets ready
```

**🔗 Integration point (end of Sprint 7):** `docker compose up` starts everything. Fresh clone to working demo in under 5 minutes.

---

### Sprint 8 (Week 8) — README & Polish

Goal: Portfolio-ready. Someone can evaluate this in 60 seconds.

```
All tracks together:
  ├── README.md
  │   ├── One-line description + demo GIF at the top
  │   ├── Architecture diagram (simplified version of this doc)
  │   ├── Quick start: docker compose up
  │   ├── Key features with screenshots
  │   │   ├── Multi-agent orchestration (LangFuse trace screenshot)
  │   │   ├── Generative UI (canvas with charts screenshot)
  │   │   ├── Source attribution (PDF highlight screenshot)
  │   │   └── Evaluation metrics (faithfulness, precision scores)
  │   ├── Tech stack summary
  │   ├── Architecture decisions (condensed from this doc)
  │   └── What I'd do differently / next steps
  ├── Final end-to-end testing across all flows
  ├── Performance profiling — document average latency per query type
  ├── Clean up code — remove dead code, add docstrings, type hints everywhere
  └── Deliverable: Portfolio project ready for job applications
```

---

### Sprint Dependency Map

```
Sprint 0 ─── models.py + Docker + sample PDFs (all tracks)
    │
    ▼
Sprint 1 ─── Vertical slice (parallel tracks, integrate at end)
    │
    ▼
Sprint 2 ─── Core quality (parallel, integrate structured output → citations)
    │
    ▼
Sprint 3 ─── Full orchestration (parallel, integrate ComponentSpec → canvas)
    │
    ▼
Sprint 4 ─── Source attribution + guardrails (parallel, integrate PDF viewer)
    │
    ▼
Sprint 5 ─── Production patterns (parallel, mostly independent)
    │
    ▼
Sprint 6 ─── Hardening (parallel, mostly independent)
    │
    ▼
Sprint 7 ─── Deployment (converge for Docker + demo assets)
    │
    ▼
Sprint 8 ─── README + polish (all tracks together)
```

### Critical Path

The longest dependency chain runs through Track B (Agents & Backend), since both Track A and Track C deliver components that Track B orchestrates. If any track falls behind, prioritize:

1. **models.py** — everything depends on shared Pydantic models
2. **Basic ingestion + Qdrant** — agents can't work without data
3. **LangGraph graph with router** — frontend can't render without structured output
4. **ComponentSpec → CanvasRenderer** — this is the demo-defining feature

---

## Interview Talking Points

This section exists to remind you what each architectural decision signals:

| Decision | What It Signals |
|----------|----------------|
| LangGraph over simple chains | You understand stateful orchestration, not just LLM wrappers |
| Hybrid search + RRF | You know naive RAG is insufficient for production |
| Parent-child chunking | You've thought about retrieval precision vs context tradeoff |
| Structured output → Generative UI | You can bridge ML backend to user-facing product |
| Ragas evaluation | You measure system quality, not just vibes |
| LangFuse tracing | You build observable systems |
| Semantic cache | You think about cost and latency at scale |
| Guardrails | You care about responsible AI deployment |
| Singapore insurance domain | Deep domain expertise, not a generic chatbot demo |