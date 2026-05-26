import asyncio
import operator
from typing import Annotated, List

import anyio

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.src.agent_state.agent_state import (
    ExpandedQueries,
    NameMatchStateInput,
    SimpleQueryClassification,
)
from app.src.prompts.prompts import (
    SIMPLE_WORKFLOW_CLASSIFY_SYSTEM,
    SIMPLE_WORKFLOW_EXPAND_SYSTEM,
    SIMPLE_WORKFLOW_SYNTHESIS_SYSTEM,
    GENERAL_AGENT_SYNTHESIS_SYSTEM,
)
from app.src.services.llm_service import ainvoke_structured_with_fallback, get_llm, resolve_timeout_seconds
from app.src.tools.product_summary import query_product_summary
from app.src.tools.textbook import TextbookOutput, query_textbook
from app.src.utils.prompt_format import format_json_for_prompt
from app.src.workflow.name_match import name_match_workflow

def _timeout() -> float:
    return resolve_timeout_seconds("simple_workflow", 30)


class SimpleWorkflowGraphState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add] = []
    classification: SimpleQueryClassification | None = None
    policy_ids: Annotated[list[str], operator.add] = []
    expanded: ExpandedQueries | None = None
    product_chunks: Annotated[list[dict], operator.add] = []
    concept_chunks: TextbookOutput = Field(default_factory=lambda: {"queries": [], "results": []})


async def _classify_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    user_message = (
        f"Conversation history:\n{format_json_for_prompt(state.conversation_history)}\n\n"
        f"Most recent question:\n{format_json_for_prompt(state.messages)}"
    )
    with anyio.fail_after(_timeout()):
        result = await ainvoke_structured_with_fallback(
            agent_name="simple_workflow",
            schema_model=SimpleQueryClassification,
            timeout_seconds=_timeout(),
            config=config,
            messages=[
                SystemMessage(content=SIMPLE_WORKFLOW_CLASSIFY_SYSTEM),
                HumanMessage(content=user_message),
            ],
        )
    return {"classification": result}


async def _expand_queries_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    classification = state.classification
    user_message = (
        f"Conversation history:\n{format_json_for_prompt(state.conversation_history)}\n\n"
        f"User question:\n{format_json_for_prompt(state.messages)}\n\n"
        f"Question type: {format_json_for_prompt(classification.question_type if classification else 'unknown')}\n"
        f"Product mentioned: {format_json_for_prompt(classification.product_name_mentioned if classification else 'none')}"
    )
    with anyio.fail_after(_timeout()):
        result = await ainvoke_structured_with_fallback(
            agent_name="simple_workflow",
            schema_model=ExpandedQueries,
            timeout_seconds=_timeout(),
            config=config,
            messages=[
                SystemMessage(content=SIMPLE_WORKFLOW_EXPAND_SYSTEM),
                HumanMessage(content=user_message),
            ],
        )
    return {"expanded": result}


async def _name_match_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    product_name = state.classification.product_name_mentioned if state.classification else None
    if not product_name:
        return {"policy_ids": []}
    result = await name_match_workflow(
        NameMatchStateInput(
            messages=state.messages,
            retrieval_query=product_name,
            conversation_history=state.conversation_history,
        ),
        config=config,
    )
    policy_ids: List[str] = [
        match.selected_policy_ids[0]
        for match in result.lst_policy_matched
        if match.selected_policy_ids
    ]
    return {"policy_ids": policy_ids}


async def _retrieve_product_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    product_queries = state.expanded.product_queries if state.expanded else []
    if not state.policy_ids or not product_queries:
        return {"product_chunks": []}
    query_pairs = [[q, pid] for pid in state.policy_ids for q in product_queries]
    chunks = await asyncio.to_thread(
        lambda: query_product_summary.invoke({"queries": query_pairs}, config=config)
    )
    return {"product_chunks": chunks}


async def _retrieve_concept_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    concept_queries = state.expanded.concept_queries if state.expanded else []
    if not concept_queries:
        return {"concept_chunks": {"queries": [], "results": []}}
    chunks = await asyncio.to_thread(
        lambda: query_textbook.invoke({"queries": [[q] for q in concept_queries]}, config=config)
    )
    return {"concept_chunks": chunks}


async def _synthesise_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    llm = get_llm("simple_workflow")
    expanded = state.expanded
    user_message = (
        f"Question type: {state.classification.question_type if state.classification else 'unknown'}\n\n"
        f"Conversation history:\n{format_json_for_prompt(state.conversation_history)}\n\n"
        f"User question:\n{format_json_for_prompt(state.messages)}\n\n"
        f"Expanded product queries:\n{format_json_for_prompt(expanded.product_queries if expanded else [])}\n"
        f"Expanded concept queries:\n{format_json_for_prompt(expanded.concept_queries if expanded else [])}\n\n"
        f"Product evidence:\n{format_json_for_prompt(state.product_chunks)}\n\n"
        f"Concept evidence:\n{format_json_for_prompt(state.concept_chunks)}"
    )
    with anyio.fail_after(_timeout()):
        response = await llm.ainvoke(
            [SystemMessage(content=SIMPLE_WORKFLOW_SYNTHESIS_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        )
    return {"messages": [AIMessage(content=response.content)]}


def _route_after_expand(state: SimpleWorkflowGraphState) -> list[str]:
    qt = state.classification.question_type if state.classification else "concept"
    if qt in ("specific_product", "lookup"):
        return ["name_match"]
    if qt == "concept":
        return ["retrieve_concept"]
    return ["name_match", "retrieve_concept"]  # "both" — parallel fan-out


def get_simple_workflow_subgraph():
    builder = StateGraph(SimpleWorkflowGraphState)

    builder.add_node("classify", _classify_node)
    builder.add_node("expand_queries", _expand_queries_node)
    builder.add_node("name_match", _name_match_node)
    builder.add_node("retrieve_product", _retrieve_product_node)
    builder.add_node("retrieve_concept", _retrieve_concept_node)
    builder.add_node("synthesise", _synthesise_node)

    builder.add_edge(START, "classify")
    builder.add_edge("classify", "expand_queries")
    builder.add_conditional_edges("expand_queries", _route_after_expand)
    builder.add_edge("name_match", "retrieve_product")
    builder.add_edge("retrieve_product", "synthesise")
    builder.add_edge("retrieve_concept", "synthesise")
    builder.add_edge("synthesise", END)

    return builder.compile()
