import operator
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.src.agents.general_agent import get_general_agent_subgraph
from app.src.workflow.simple_workflow import get_simple_workflow_subgraph


class MainAgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add]
    execution_results: Annotated[list, operator.add] = Field(default_factory=list)


async def get_main_agent_graph():
    """Build and compile the main agent graph."""
    builder = StateGraph(MainAgentState)

    # general_agent = await get_general_agent_subgraph()
    # builder.add_node("general_agent", general_agent)
    # builder.add_edge(START, "general_agent")
    # builder.add_edge("general_agent", END)

    simple_workflow = get_simple_workflow_subgraph()
    builder.add_node("simple_workflow", simple_workflow)
    builder.add_edge(START, "simple_workflow")
    builder.add_edge("simple_workflow", END)

    return builder.compile()
