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
    AbbreviationResolution,
    DecomposedIntent,
    IntentExtension,
    IntentsDecomposition,
    IntentSummary,
    NameMatchStateInput,
    RephrasedQuerySet,
)
from app.src.prompts.prompts import (
    SIMPLEV2_IDENTIFY_INTENT_SYSTEM,
    SIMPLEV2_INTENT_EXTENSION_SYSTEM,
    SIMPLEV2_INTENTS_DECOMPOSITION_SYSTEM,
    SIMPLEV2_QUERY_EXPANSION_SYSTEM,
    SIMPLEV2_RESOLVE_ABBREVIATION_SYSTEM,
    SIMPLEV2_SYNTHESIS_SYSTEM,
)
from app.src.services.llm_service import ainvoke_structured_with_fallback, get_llm, resolve_timeout_seconds
from app.src.tools.product_registry import get_product_names
from app.src.tools.product_summary import query_product_summary
from app.src.tools.textbook import TextbookOutput, query_textbook
from app.src.utils.prompt_format import format_json_for_prompt
from app.src.workflow.name_match import name_match_workflow


def _timeout() -> float:
    return resolve_timeout_seconds("simple_workflow", 30)


class SimpleWorkflowV2GraphState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add] = []
    abbreviation_context: str | None = None
    intent_summary: IntentSummary | None = None
    intent_extension: IntentExtension | None = None
    intents_decomposition: IntentsDecomposition | None = None
    policy_ids: Annotated[list[str], operator.add] = []
    product_chunks: Annotated[list[dict], operator.add] = []
    concept_chunks: TextbookOutput = Field(default_factory=lambda: {"queries": [], "results": []})


async def _resolve_abbreviation_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    human_messages = [m for m in state.messages if isinstance(m, HumanMessage)]
    if not human_messages:
        return {"abbreviation_context": None}

    latest_message = human_messages[-1].content
    product_names = get_product_names()
    product_name_list = [d["policy_name"] for d in product_names if "policy_name" in d]
    product_list_str = "\n".join(product_name_list)

    with anyio.fail_after(15):
        result = await ainvoke_structured_with_fallback(
            agent_name="simplev2_resolve_abbreviation",
            schema_model=AbbreviationResolution,
            timeout_seconds=15,
            config=config,
            messages=[
                SystemMessage(content=SIMPLEV2_RESOLVE_ABBREVIATION_SYSTEM),
                HumanMessage(content=f"User message: {latest_message}\n\nProduct names:\n{product_list_str}"),
            ],
        )
    return {"abbreviation_context": result.abbreviation_context}


async def _identify_intent_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    extra: list[BaseMessage] = []
    if state.abbreviation_context:
        extra = [SystemMessage(content=f"[Abbreviation context]\n{state.abbreviation_context}")]

    user_message = (
        f"Conversation history:\n{format_json_for_prompt(state.conversation_history)}\n\n"
        f"Latest user message:\n{format_json_for_prompt(state.messages)}"
    )
    with anyio.fail_after(_timeout()):
        result = await ainvoke_structured_with_fallback(
            agent_name="simplev2_identify_intent",
            schema_model=IntentSummary,
            timeout_seconds=_timeout(),
            config=config,
            messages=extra + [
                SystemMessage(content=SIMPLEV2_IDENTIFY_INTENT_SYSTEM),
                HumanMessage(content=user_message),
            ],
        )
    return {"intent_summary": result}


async def _intent_extension_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    intent_summary = state.intent_summary
    user_message = (
        f"Condensed intent:\n{intent_summary.condensed_intent if intent_summary else 'unknown'}\n\n"
        f"Original user message:\n{format_json_for_prompt(state.messages)}"
    )
    with anyio.fail_after(_timeout()):
        result = await ainvoke_structured_with_fallback(
            agent_name="simplev2_intent_extension",
            schema_model=IntentExtension,
            timeout_seconds=_timeout(),
            config=config,
            messages=[
                SystemMessage(content=SIMPLEV2_INTENT_EXTENSION_SYSTEM),
                HumanMessage(content=user_message),
            ],
        )
    return {"intent_extension": result}


async def _intents_decomposition_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    intent_summary = state.intent_summary
    intent_extension = state.intent_extension
    user_message = (
        f"Condensed intent:\n{intent_summary.condensed_intent if intent_summary else 'unknown'}\n\n"
        f"Extended queries:\n{format_json_for_prompt(intent_extension.extended_queries if intent_extension else [])}"
    )
    with anyio.fail_after(_timeout()):
        result = await ainvoke_structured_with_fallback(
            agent_name="simplev2_intents_decomposition",
            schema_model=IntentsDecomposition,
            timeout_seconds=_timeout(),
            config=config,
            messages=[
                SystemMessage(content=SIMPLEV2_INTENTS_DECOMPOSITION_SYSTEM),
                HumanMessage(content=user_message),
            ],
        )
    return {"intents_decomposition": result}


async def _name_match_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    product_name = state.intent_summary.product_name_mentioned if state.intent_summary else None
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


async def _query_expansion_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    decomposed_intents = (
        state.intents_decomposition.decomposed_intents if state.intents_decomposition else []
    )
    if not decomposed_intents:
        return {"concept_chunks": {"queries": [], "results": []}, "product_chunks": []}

    # LLM rephrases each decomposed intent for its target RAG source
    user_message = (
        f"Decomposed intents:\n{format_json_for_prompt(decomposed_intents)}"
    )
    with anyio.fail_after(_timeout()):
        rephrased: RephrasedQuerySet = await ainvoke_structured_with_fallback(
            agent_name="simplev2_query_expansion",
            schema_model=RephrasedQuerySet,
            timeout_seconds=_timeout(),
            config=config,
            messages=[
                SystemMessage(content=SIMPLEV2_QUERY_EXPANSION_SYSTEM),
                HumanMessage(content=user_message),
            ],
        )

    # Call both RAG tools in parallel
    textbook_queries = rephrased.textbook_queries or []
    product_queries = rephrased.product_queries or []
    policy_ids = state.policy_ids

    async def _fetch_concept() -> TextbookOutput:
        if not textbook_queries:
            return {"queries": [], "results": []}
        return await asyncio.to_thread(
            lambda: query_textbook.invoke({"queries": [[q] for q in textbook_queries]}, config=config)
        )

    async def _fetch_product() -> list:
        if not policy_ids or not product_queries:
            return []
        query_pairs = [[q, pid] for pid in policy_ids for q in product_queries]
        return await asyncio.to_thread(
            lambda: query_product_summary.invoke({"queries": query_pairs}, config=config)
        )

    concept_chunks, product_chunks = await asyncio.gather(_fetch_concept(), _fetch_product())
    return {"concept_chunks": concept_chunks, "product_chunks": product_chunks}


async def _synthesise_node(state: SimpleWorkflowV2GraphState, config: RunnableConfig) -> dict:
    llm = get_llm("simple_workflow")
    intent_summary = state.intent_summary
    intents_decomposition = state.intents_decomposition

    user_message = (
        f"Conversation history:\n{format_json_for_prompt(state.conversation_history)}\n\n"
        f"User question:\n{format_json_for_prompt(state.messages)}\n\n"
        f"Condensed intent:\n{intent_summary.condensed_intent if intent_summary else 'unknown'}\n\n"
        f"Retrieval angles used:\n{format_json_for_prompt(intents_decomposition.decomposed_intents if intents_decomposition else [])}\n\n"
        f"Product evidence:\n{format_json_for_prompt(state.product_chunks)}\n\n"
        f"Concept evidence:\n{format_json_for_prompt(state.concept_chunks)}"
    )
    with anyio.fail_after(_timeout()):
        response = await llm.ainvoke(
            [SystemMessage(content=SIMPLEV2_SYNTHESIS_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        )
    return {"messages": [AIMessage(content=response.content)]}


def _route_after_decomposition(state: SimpleWorkflowV2GraphState) -> str:
    product_name = state.intent_summary.product_name_mentioned if state.intent_summary else None
    if product_name:
        return "name_match"
    return "query_expansion"


def get_simple_workflow_v2_subgraph():
    builder = StateGraph(SimpleWorkflowV2GraphState)

    builder.add_node("resolve_abbreviation", _resolve_abbreviation_node)
    builder.add_node("identify_intent", _identify_intent_node)
    builder.add_node("intent_extension", _intent_extension_node)
    builder.add_node("intents_decomposition", _intents_decomposition_node)
    builder.add_node("name_match", _name_match_node)
    builder.add_node("query_expansion", _query_expansion_node)
    builder.add_node("synthesise", _synthesise_node)

    builder.add_edge(START, "resolve_abbreviation")
    builder.add_edge("resolve_abbreviation", "identify_intent")
    builder.add_edge("identify_intent", "intent_extension")
    builder.add_edge("intent_extension", "intents_decomposition")
    builder.add_conditional_edges(
        "intents_decomposition",
        _route_after_decomposition,
        {
            "name_match": "name_match",
            "query_expansion": "query_expansion",
        },
    )
    builder.add_edge("name_match", "query_expansion")
    builder.add_edge("query_expansion", "synthesise")
    builder.add_edge("synthesise", END)

    return builder.compile()
