import asyncio
from typing import Annotated

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.agent.prompts.prompts import (
    FIND_PRODUCT_WITH_CRITERIA_SYSTEM_1,
    FIND_PRODUCT_WITH_CRITERIA_SYSTEM_2,
)
from app.agent.schemas.tools import FindPolicyIdWithCriteriaInput, FindPolicyIdWithCriteriaOutput
from app.agent.services.llm_service import ainvoke_structured_with_fallback, resolve_timeout_seconds
from app.agent.tools.product_registry import find_policy_id_with_criteria
from app.agent.utils.prompt_format import format_json_for_prompt


# ---------------------------------------------------------------------------
# State models
# ---------------------------------------------------------------------------


class FindProductWithCriteriaStateInput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str


class PolicyMatch(BaseModel):
    policy_id: str
    reasoning: str


class FindProductWithCriteriaStateOutput(BaseModel):
    matching_product: list[PolicyMatch]


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


async def find_product_with_criteria_workflow(
    state: FindProductWithCriteriaStateInput,
) -> FindProductWithCriteriaStateOutput:
    timeout = resolve_timeout_seconds("find_product_with_criteria_workflow", 60)

    user_message = f"query:\n{format_json_for_prompt(state.query)}"

    tool_param: FindPolicyIdWithCriteriaInput = await ainvoke_structured_with_fallback(
        agent_name="find_product_with_criteria_workflow",
        schema_model=FindPolicyIdWithCriteriaInput,
        timeout_seconds=timeout,
        messages=[
            SystemMessage(content=FIND_PRODUCT_WITH_CRITERIA_SYSTEM_1),
            HumanMessage(content=user_message),
        ],
    )

    tool_output: FindPolicyIdWithCriteriaOutput = await asyncio.to_thread(
        find_policy_id_with_criteria.invoke, tool_param.model_dump()
    )

    output: FindProductWithCriteriaStateOutput = await ainvoke_structured_with_fallback(
        agent_name="find_product_with_criteria_workflow",
        schema_model=FindProductWithCriteriaStateOutput,
        timeout_seconds=timeout,
        messages=[
            SystemMessage(content=FIND_PRODUCT_WITH_CRITERIA_SYSTEM_2),
            HumanMessage(
                content=(
                    f"{user_message}\nproduct_catalog:\n"
                    f"{format_json_for_prompt(tool_output)}"
                )
            ),
        ],
    )
    return output
