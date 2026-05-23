import asyncio

from langchain_core.messages import HumanMessage, SystemMessage

from app.src.agent_state.agent_state import (
    FindProductWithCriteriaStateInput,
    FindProductWithCriteriaStateOutput,
)
from app.src.prompts.prompts import (
    FIND_PPRODUCT_WITH_CRITERIA_SYSTEM_1,
    FIND_PPRODUCT_WITH_CRITERIA_SYSTEM_2,
)
from app.src.schema.tool_schema import FindPolicyIdWithCriteriaInput, FindPolicyIdWithCriteriaOutput
from app.src.services.llm_service import get_llm, resolve_timeout_seconds
from app.src.tools.product_registry import find_policy_id_with_criteria


async def find_product_with_criteria_workflow(
    state: FindProductWithCriteriaStateInput,
) -> FindProductWithCriteriaStateOutput:
    timeout = resolve_timeout_seconds("find_product_with_criteria_workflow", 60)
    llm_tool_param = (
        get_llm("find_product_with_criteria_workflow")
        .bind_tools([find_policy_id_with_criteria])
        .with_structured_output(FindPolicyIdWithCriteriaInput)
    )

    llm_eval = get_llm("find_product_with_criteria_workflow").with_structured_output(
        FindProductWithCriteriaStateOutput
    )

    user_message = f"query: {state.query}"

    tool_param: FindPolicyIdWithCriteriaInput = await asyncio.wait_for(
        asyncio.to_thread(
            llm_tool_param.invoke,
            [
                SystemMessage(content=FIND_PPRODUCT_WITH_CRITERIA_SYSTEM_1),
                HumanMessage(content=user_message),
            ],
        ),
        timeout=timeout,
    )

    tool_output: FindPolicyIdWithCriteriaOutput = await asyncio.to_thread(
        find_policy_id_with_criteria.invoke, tool_param.model_dump()
    )

    output: FindProductWithCriteriaStateOutput = await asyncio.wait_for(
        asyncio.to_thread(
            llm_eval.invoke,
            [
                SystemMessage(content=FIND_PPRODUCT_WITH_CRITERIA_SYSTEM_2),
                HumanMessage(
                    content=user_message + f"\nproduct_catalog:\n{tool_output.model_dump_json()}"
                ),
            ],
        ),
        timeout=timeout,
    )
    return output
