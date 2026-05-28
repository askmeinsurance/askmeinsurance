import logging
import operator
from typing import Annotated

logger = logging.getLogger("askmeinsurance.main_agent")

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.agent.agents.general_agent import get_general_agent_subgraph
from app.agent.prompts.prompts import MAIN_AGENT_ROUTER_SYSTEM
from app.agent.schemas.agent import MainAgentRouterClassification
from app.agent.services.llm_service import ainvoke_structured_with_fallback, resolve_timeout_seconds
from app.agent.utils.prompt_format import format_json_for_prompt

from app.agent.workflows.simple_workflow_v2 import get_simple_workflow_v2_subgraph


# ---------------------------------------------------------------------------
# Dev toggle — set to "simple_workflow" or "general_agent" to bypass routing,
# or None to use the LLM router normally.
# ---------------------------------------------------------------------------
FORCE_ROUTE: str | None = "simple_workflow"


class MainAgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add] = Field(default_factory=list)
    execution_results: Annotated[list, operator.add] = Field(default_factory=list)
    route: str = "simple_workflow"
    route_reasoning: str = ""
    # simple_workflow_v2 retrieval output — must be present here so LangGraph
    # merges the subgraph's final state back into this parent state.
    product_chunks: Annotated[list[dict], operator.add] = Field(default_factory=list)
    concept_chunks: dict = Field(default_factory=lambda: {"queries": [], "results": []})


async def get_main_agent_graph():
    """Build and compile the main agent graph."""
    builder = StateGraph(MainAgentState)

    async def router_node(state: MainAgentState) -> dict:
        if FORCE_ROUTE is not None:
            return {"route": FORCE_ROUTE, "route_reasoning": f"[FORCE_ROUTE={FORCE_ROUTE}]"}
        user_message_text = format_json_for_prompt(state.messages)
        history_text = format_json_for_prompt(state.conversation_history)
        classification: MainAgentRouterClassification = await ainvoke_structured_with_fallback(
            agent_name="main_agent",
            schema_model=MainAgentRouterClassification,
            timeout_seconds=resolve_timeout_seconds("simple_workflow", 30),
            messages=[
                SystemMessage(content=MAIN_AGENT_ROUTER_SYSTEM),
                HumanMessage(
                    content=f"Conversation history:\n{history_text}\n\nlatest_message:\n{user_message_text}"
                ),
            ],
        )
        return {
            "route": classification.route,
            "route_reasoning": classification.reasoning,
        }

    def router_edge(state: MainAgentState) -> str:
        if state.route == "general_agent":
            return "general_agent"
        if state.route == "simple_workflow":
            return "simple_workflow"
        logger.warning("Unknown route %r — defaulting to simple_workflow", state.route)
        return "simple_workflow"

    simple_workflow = get_simple_workflow_v2_subgraph()
    general_agent = await get_general_agent_subgraph()
    builder.add_node("router", router_node)
    builder.add_node("simple_workflow", simple_workflow)
    builder.add_node("general_agent", general_agent)
    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        router_edge,
        {
            "simple_workflow": "simple_workflow",
            "general_agent": "general_agent",
        },
    )
    builder.add_edge("simple_workflow", END)
    builder.add_edge("general_agent", END)

    return builder.compile()
