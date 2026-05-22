import asyncio
import operator
import os
from typing import Annotated, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.src.agent_state.agent_state import (
    ExpandedQueries,
    NameMatchStateInput,
    SimpleQueryClassification,
)
from app.src.prompts.prompts import (
    SIMPLE_WORKFLOW_CLASSIFY_SYSTEM,
    SIMPLE_WORKFLOW_EXPAND_SYSTEM,
    SIMPLE_WORKFLOW_SYNTHESIS_SYSTEM,
)
from app.src.services.llm_service import get_llm
from app.src.tools.product_summary import query_product_summary
from app.src.tools.textbook import query_textbook
from app.src.workflow.name_match import name_match_workflow

_NODE_TIMEOUT = os.getenv("LLM_TIMEOUT_SECONDS")


def _timeout() -> float:
    return float(_NODE_TIMEOUT) if _NODE_TIMEOUT else 30


class SimpleWorkflowGraphState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], add_messages] = []
    classification: SimpleQueryClassification | None = None
    policy_ids: Annotated[list[str], operator.add] = []
    expanded: ExpandedQueries | None = None
    product_chunks: Annotated[list[dict], operator.add] = []
    concept_chunks: Annotated[list[dict], operator.add] = []


async def _classify_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    llm = get_llm("simple_workflow").with_structured_output(SimpleQueryClassification)
    user_message = f"Conversation history:\n{state.conversation_history}\n\nMost recent question:\n{state.messages}"
    result = await asyncio.wait_for(
        llm.ainvoke(
            [SystemMessage(content=SIMPLE_WORKFLOW_CLASSIFY_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        ),
        timeout=_timeout(),
    )
    return {"classification": result}


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


async def _expand_queries_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    llm = get_llm("simple_workflow").with_structured_output(ExpandedQueries)
    classification = state.classification
    user_message = (
        f"Conversation history:\n{state.conversation_history}\n\n"
        f"User question:\n{state.messages}\n\n"
        f"Question type: {classification.question_type if classification else 'unknown'}\n"
        f"Product mentioned: {classification.product_name_mentioned if classification else 'none'}"
    )
    result = await asyncio.wait_for(
        llm.ainvoke(
            [SystemMessage(content=SIMPLE_WORKFLOW_EXPAND_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        ),
        timeout=_timeout(),
    )
    return {"expanded": result}


async def _retrieve_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    expanded = state.expanded
    product_queries = expanded.product_queries if expanded else []
    concept_queries = expanded.concept_queries if expanded else []

    async def _retrieve_product() -> list[dict]:
        if not state.policy_ids or not product_queries:
            return []
        query_pairs = [[q, pid] for pid in state.policy_ids for q in product_queries]
        return await asyncio.to_thread(
            lambda: query_product_summary.invoke({"queries": query_pairs}, config=config)
        )

    async def _retrieve_concept() -> list[dict]:
        if not concept_queries:
            return []
        return await asyncio.to_thread(
            lambda: query_textbook.invoke({"queries": [[q] for q in concept_queries]}, config=config)
        )

    product_chunks, concept_chunks = await asyncio.gather(_retrieve_product(), _retrieve_concept())
    return {"product_chunks": product_chunks, "concept_chunks": concept_chunks}


async def _synthesise_node(state: SimpleWorkflowGraphState, config: RunnableConfig) -> dict:
    llm = get_llm("simple_workflow")
    expanded = state.expanded
    user_message = (
        f"Conversation history:\n{state.conversation_history}\n\n"
        f"User question:\n{state.messages}\n\n"
        f"Expanded product queries: {expanded.product_queries if expanded else []}\n"
        f"Expanded concept queries: {expanded.concept_queries if expanded else []}\n\n"
        f"Product evidence:\n{state.product_chunks}\n\n"
        f"Concept evidence:\n{state.concept_chunks}"
    )
    response = await asyncio.wait_for(
        llm.ainvoke(
            [SystemMessage(content=SIMPLE_WORKFLOW_SYNTHESIS_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        ),
        timeout=_timeout(),
    )
    return {"messages": [AIMessage(content=response.content)]}


def _route_after_classify(state: SimpleWorkflowGraphState) -> str:
    if state.classification and state.classification.question_type in ("specific_product", "both"):
        return "name_match"
    return "expand_queries"


def get_simple_workflow_subgraph():
    builder = StateGraph(SimpleWorkflowGraphState)

    builder.add_node("classify", _classify_node)
    builder.add_node("name_match", _name_match_node)
    builder.add_node("expand_queries", _expand_queries_node)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("synthesise", _synthesise_node)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"name_match": "name_match", "expand_queries": "expand_queries"},
    )
    builder.add_edge("name_match", "expand_queries")
    builder.add_edge("expand_queries", "retrieve")
    builder.add_edge("retrieve", "synthesise")
    builder.add_edge("synthesise", END)

    return builder.compile()
