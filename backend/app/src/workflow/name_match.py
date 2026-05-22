import asyncio
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.src.agent_state.agent_state import NameMatchStateInput, NameMatchStateOutput
from app.src.prompts.prompts import NAME_MATCH_SYSTEM
from app.src.services.llm_service import get_llm
from app.src.tools.product_registry import get_product_names

_NODE_TIMEOUT = os.getenv("LLM_TIMEOUT_SECONDS")


async def name_match_workflow(state: NameMatchStateInput, config: RunnableConfig | None = None) -> NameMatchStateOutput:
    catalog = get_product_names()
    user_message = f"""User query: {state.messages}

Retrieval query: {state.retrieval_query}

Catalog: {catalog}
"""
    llm = get_llm("name_match_workflow").with_structured_output(NameMatchStateOutput)

    output: NameMatchStateOutput = await asyncio.wait_for(
        llm.ainvoke(
            [SystemMessage(content=NAME_MATCH_SYSTEM), HumanMessage(content=user_message)],
            config=config,
        ),
        timeout=float(_NODE_TIMEOUT) if _NODE_TIMEOUT else 10,
    )

    return output
