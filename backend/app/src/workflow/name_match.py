import anyio
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.src.agent_state.agent_state import NameMatchStateInput, NameMatchStateOutput
from app.src.prompts.prompts import NAME_MATCH_SYSTEM
from app.src.services.llm_service import get_llm, resolve_timeout_seconds
from app.src.tools.product_registry import get_product_names


async def name_match_workflow(state: NameMatchStateInput, config: RunnableConfig | None = None) -> NameMatchStateOutput:
    catalog = get_product_names()
    user_message = f"""User query: {state.messages}

Retrieval query: {state.retrieval_query}

Catalog: {catalog}
"""
    llm = get_llm("name_match_workflow").with_structured_output(NameMatchStateOutput)
    timeout = resolve_timeout_seconds("name_match_workflow", 10)

    with anyio.fail_after(timeout):
        output: NameMatchStateOutput = await llm.ainvoke(
            [SystemMessage(content=NAME_MATCH_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        )

    return output
