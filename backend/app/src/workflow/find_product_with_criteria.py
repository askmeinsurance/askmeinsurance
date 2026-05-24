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
from app.src.services.llm_service import ainvoke_structured_with_fallback, resolve_timeout_seconds
from app.src.tools.product_registry import find_policy_id_with_criteria
from app.src.utils.prompt_format import format_json_for_prompt


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
            SystemMessage(content=FIND_PPRODUCT_WITH_CRITERIA_SYSTEM_1),
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
            SystemMessage(content=FIND_PPRODUCT_WITH_CRITERIA_SYSTEM_2),
            HumanMessage(
                content=(
                    f"{user_message}\nproduct_catalog:\n"
                    f"{format_json_for_prompt(tool_output)}"
                )
            ),
        ],
    )
    return output
