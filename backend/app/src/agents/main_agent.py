import operator
from typing import Annotated

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.src.agents.general_agent import get_general_agent_subgraph
from app.src.prompts.prompts import MAIN_AGENT_ROUTER_SYSTEM
from app.src.schema.agent_schema import MainAgentRouterClassification
from app.src.services.llm_service import get_llm, resolve_timeout_seconds
from app.src.utils.prompt_format import format_json_for_prompt
from app.src.workflow.simple_workflow import get_simple_workflow_subgraph


class MainAgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add] = Field(default_factory=list)
    execution_results: Annotated[list, operator.add] = Field(default_factory=list)
    route: str = "simple_workflow"
    route_reasoning: str = ""


async def get_main_agent_graph():
    """Build and compile the main agent graph."""
    builder = StateGraph(MainAgentState)

    async def router_node(state: MainAgentState) -> dict:
        user_message_text = format_json_for_prompt(state.messages)
        history_text = format_json_for_prompt(state.conversation_history)
        llm = get_llm("main_agent").with_structured_output(MainAgentRouterClassification)
        classification: MainAgentRouterClassification = await llm.ainvoke(
            [
                SystemMessage(content=MAIN_AGENT_ROUTER_SYSTEM),
                HumanMessage(
                    content=f"Conversation history:\n{history_text}\n\nlatest_message:\n{user_message_text}"
                ),
            ],
            config={
                "timeout": resolve_timeout_seconds("simple_workflow", 30),
            },
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
        return "simple_workflow"

    simple_workflow = get_simple_workflow_subgraph()
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
