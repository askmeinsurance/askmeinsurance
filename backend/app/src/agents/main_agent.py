import operator
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.src.agents.general_agent import get_general_agent_subgraph


class MainAgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add]


async def get_main_agent_graph():
    """Build and compile the main agent graph.

    For now all messages route directly to general_agent.
    Routing to fplanner_agent will be added when that agent is implemented.
    """
    general_agent = await get_general_agent_subgraph()

    builder = StateGraph(MainAgentState)
    builder.add_node("general_agent", general_agent)
    builder.add_edge(START, "general_agent")
    builder.add_edge("general_agent", END)

    return builder.compile()
