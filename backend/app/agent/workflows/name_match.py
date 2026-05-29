import operator
from typing import Annotated, Literal

import anyio
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.agent.prompts.prompts import NAME_MATCH_ONE_POLICY_SYSTEM, NAME_MATCH_SYSTEM
from app.agent.schemas.tools import PolicyMatchResponse
from app.agent.services.llm_service import ainvoke_structured_with_fallback, resolve_timeout_seconds
from app.agent.tools.product_registry import get_product_names
from app.agent.utils.prompt_format import format_json_for_prompt


# ---------------------------------------------------------------------------
# State models
# ---------------------------------------------------------------------------


class NameMatchStateInput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    retrieval_query: str = ""
    conversation_history: Annotated[list[BaseMessage], add_messages] = []


class NameMatchStateOutput(BaseModel):
    lst_policy_matched: Annotated[list[PolicyMatchResponse], operator.add]


class OnePolicyMatchOutput(BaseModel):
    policy_id: str | None
    confidence: Literal["low", "medium", "high"]
    reason: str


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


async def name_match_workflow(state: NameMatchStateInput, config: RunnableConfig | None = None) -> NameMatchStateOutput:
    catalog = get_product_names()
    user_message = f"""User query:
{format_json_for_prompt(state.messages)}

Retrieval query:
{format_json_for_prompt(state.retrieval_query)}

Catalog:
{format_json_for_prompt(catalog)}
"""
    timeout = resolve_timeout_seconds("name_match_workflow", 10)

    with anyio.fail_after(timeout):
        output: NameMatchStateOutput = await ainvoke_structured_with_fallback(
            agent_name="name_match_workflow",
            schema_model=NameMatchStateOutput,
            timeout_seconds=timeout,
            config=config,
            messages=[SystemMessage(content=NAME_MATCH_SYSTEM), HumanMessage(content=user_message)],
        )

    return output


async def name_match_one_policy_workflow(
    state: NameMatchStateInput, config: RunnableConfig | None = None
) -> OnePolicyMatchOutput:
    catalog = get_product_names()
    user_message = f"""User query:
{format_json_for_prompt(state.messages)}

Retrieval query:
{format_json_for_prompt(state.retrieval_query)}

Catalog:
{format_json_for_prompt(catalog)}
"""
    timeout = resolve_timeout_seconds("name_match_one_policy_workflow", 10)

    with anyio.fail_after(timeout):
        output: OnePolicyMatchOutput = await ainvoke_structured_with_fallback(
            agent_name="name_match_one_policy_workflow",
            schema_model=OnePolicyMatchOutput,
            timeout_seconds=timeout,
            config=config,
            messages=[SystemMessage(content=NAME_MATCH_ONE_POLICY_SYSTEM), HumanMessage(content=user_message)],
        )

    return output
