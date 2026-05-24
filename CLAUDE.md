# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

```
backend/    FastAPI + LangGraph agent system
frontend/   React 19 + TypeScript + Vite chat UI  (has its own CLAUDE.md)
evals/      Offline evaluation scripts
ref/        Reference implementations (read-only reference)
```

## Commands

### Backend
All backend commands run from the `backend/` directory using `uv`:
```bash
uv run uvicorn app.main:app --reload   # Dev server (http://localhost:8000)
uv run pytest                           # All tests
uv run pytest tests/test_<name>.py     # Single test file
uv run pytest -k "test_function_name"  # Single test by name
```

### Frontend
From `frontend/`:
```bash
npm run dev       # Dev server (http://localhost:5173)
npm run build     # Type-check + production build
npm run lint      # ESLint
```

## Backend Architecture

### Request Flow
```
POST /api/v1/chat/stream
  → ChatService
    → LangGraphService.stream_response()
      → get_compiled_graph()            (singleton in app/src/graph.py)
        → MainAgent (LangGraph graph)
          → router node (classifies route)
          → simple_workflow subgraph  OR  general_agent subgraph
```

### Agent Routing (`app/src/agents/main_agent.py`)
The main agent is a LangGraph `StateGraph` with state type `MainAgentState`. A **router node** calls an LLM to classify the user query and sets `state.route` to either `"simple_workflow"` or `"general_agent"`. A conditional edge then dispatches to the appropriate subgraph.

### Simple Workflow (`app/src/workflow/simple_workflow.py`)
A LangGraph subgraph for straightforward insurance Q&A. Steps:
1. **classify** — classifies as `specific_product`, `concept`, or `both`
2. **expand_queries** — generates product and concept sub-queries
3. **name_match** ← parallel fan-out when applicable → **retrieve_concept**
4. **retrieve_product** (follows name_match)
5. **synthesise** — waits for both retrieval branches, generates final answer

The `_route_after_expand` function implements the parallel fan-out: `"both"` returns `["name_match", "retrieve_concept"]` to run them concurrently.

### General Agent (`app/src/agents/general_agent.py`)
A ReAct planner-executor loop (max 5 iterations). Classifies the question, then iteratively plans tool calls (`textbook_retriever`, `product_registry`, `name_match`, `find_product_with_criteria`), executes them via `execute_parallel_plan`, and synthesises when the planner marks `finish=True`.

### LLM Configuration (`app/src/agent_config.yaml`)
Each named agent gets its own model config block. `get_llm(agent_name)` in `llm_service.py` reads this file and returns a LangChain LLM instance. Model format: `provider|model-name` where provider is `openrouter`, `google`, or `openai`.

To change which model an agent uses, edit `agent_config.yaml` — no Python changes needed.

### Shared State Types (`app/src/agent_state/agent_state.py`)
- `SimpleQueryClassification` — `question_type`, `product_name_mentioned`
- `ExpandedQueries` — `product_queries`, `concept_queries`
- `NameMatchStateInput` / `NameMatchStateOutput`

### Tools (`app/src/tools/`)
- `textbook.py` — `query_textbook`: searches Qdrant collection `insurance_text_book2`
- `product_summary.py` — `query_product_summary`: searches Qdrant product summary collection
- `product_registry.py` — `get_product_names()`: returns flat list of product names from `static_data/`

### Services (`app/services/`)
- `LangGraphService` — wraps graph invocation, integrates Langfuse tracing via `CallbackHandler`, streams `ChatEvent`s
- `ChatService` — resolves/creates conversations, loads history, calls `LangGraphService`
- `ConversationService` / `MessageService` — Supabase-backed conversation and message persistence

### Observability
Langfuse is initialized in `app/core/langfuse.py` at startup. `LangGraphService` passes a `CallbackHandler` into `graph.astream_events(config={"callbacks": [handler]})`, giving Langfuse visibility into all LangGraph node executions. Configure via `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` env vars.

### Auth
JWT verification (RS256) using `SUPABASE_JWT_SECRET`. Set `AUTH_ENABLED=false` in `.env` to disable during local development.

## Environment Setup

Copy `backend/sample.env` to `backend/.env` and fill in:
- `OPENROUTER_API_KEY` (primary LLM provider)
- `QDRANT_URL` + `QDRANT_API_KEY` (vector search)
- `SUPABASE_*` keys (conversation persistence)
- `LANGFUSE_*` keys (optional, for tracing)
- `AUTH_ENABLED=false` for local dev without Supabase auth

Copy `frontend/sample.env` to `frontend/.env` similarly.

## Key Design Patterns

- **Agent config over code**: model selection and timeouts live in `agent_config.yaml`, not in Python. Add a new agent entry there before calling `get_llm("new_agent")`.
- **Subgraphs as nodes**: both `simple_workflow` and `general_agent` are compiled LangGraph subgraphs added as nodes in the main graph via `builder.add_node("simple_workflow", compiled_subgraph)`.
- **Pydantic state**: all LangGraph state types are Pydantic `BaseModel`s with `Annotated` reducers (`add_messages`, `operator.add`).
- **Structured output with fallback**: `invoke_structured_with_fallback()` in `llm_service.py` handles providers that return plain text instead of structured JSON — strips markdown fences and parses manually.
- **Parallel retrieval**: `asyncio.to_thread` wraps sync Qdrant calls; `anyio.fail_after` enforces per-node timeouts.
