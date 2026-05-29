import asyncio
import operator
from types import SimpleNamespace
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.agent.agents.main_agent import get_main_agent_graph


class _SubgraphState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]


def _build_leaf_subgraph(response: str):
    async def _node(_: _SubgraphState) -> dict:
        return {"messages": [AIMessage(content=response)]}

    builder = StateGraph(_SubgraphState)
    builder.add_node("node", _node)
    builder.add_edge(START, "node")
    builder.add_edge("node", END)
    return builder.compile()


class _DummyRouterLLM:
    def __init__(self, route: str):
        self._route = route
        self.last_prompt = ""

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, *_args, **_kwargs):
        messages = _args[0] if _args else []
        if messages:
            self.last_prompt = messages[-1].content
        return SimpleNamespace(route=self._route, reasoning="test")


def _build_main_state_input():
    return {
        "messages": [HumanMessage(content="route this")],
        "conversation_history": [],
        "execution_results": [],
        "route": "",
        "route_reasoning": "",
    }


def test_main_agent_routes_to_simple(monkeypatch):
    monkeypatch.setattr("app.agent.agents.main_agent.FORCE_ROUTE", None)
    monkeypatch.setattr(
        "app.agent.agents.main_agent.get_simple_workflow_v2_subgraph",
        lambda: _build_leaf_subgraph("from simple"),
    )

    async def _general():
        return _build_leaf_subgraph("from react")

    monkeypatch.setattr("app.agent.agents.main_agent.get_general_agent_subgraph", _general)

    async def _fake_classify(**_kwargs):
        return SimpleNamespace(route="simple_workflow", reasoning="test")

    monkeypatch.setattr("app.agent.agents.main_agent.ainvoke_structured_with_fallback", _fake_classify)

    graph = asyncio.run(get_main_agent_graph())
    result = asyncio.run(graph.ainvoke(_build_main_state_input()))
    assert result["messages"][-1].content == "from simple"


def test_main_agent_routes_to_react(monkeypatch):
    monkeypatch.setattr("app.agent.agents.main_agent.FORCE_ROUTE", None)
    monkeypatch.setattr(
        "app.agent.agents.main_agent.get_simple_workflow_v2_subgraph",
        lambda: _build_leaf_subgraph("from simple"),
    )

    async def _general():
        return _build_leaf_subgraph("from react")

    monkeypatch.setattr("app.agent.agents.main_agent.get_general_agent_subgraph", _general)

    async def _fake_classify(**_kwargs):
        return SimpleNamespace(route="general_agent", reasoning="test")

    monkeypatch.setattr("app.agent.agents.main_agent.ainvoke_structured_with_fallback", _fake_classify)

    graph = asyncio.run(get_main_agent_graph())
    result = asyncio.run(graph.ainvoke(_build_main_state_input()))
    assert result["messages"][-1].content == "from react"


def test_main_agent_router_fallbacks_to_simple(monkeypatch):
    monkeypatch.setattr("app.agent.agents.main_agent.FORCE_ROUTE", None)
    monkeypatch.setattr(
        "app.agent.agents.main_agent.get_simple_workflow_v2_subgraph",
        lambda: _build_leaf_subgraph("from simple"),
    )

    async def _general():
        return _build_leaf_subgraph("from react")

    monkeypatch.setattr("app.agent.agents.main_agent.get_general_agent_subgraph", _general)

    async def _fake_classify(**_kwargs):
        return SimpleNamespace(route="unknown_route", reasoning="test")

    monkeypatch.setattr("app.agent.agents.main_agent.ainvoke_structured_with_fallback", _fake_classify)

    graph = asyncio.run(get_main_agent_graph())
    result = asyncio.run(graph.ainvoke(_build_main_state_input()))
    assert result["messages"][-1].content == "from simple"


def test_main_agent_router_prompt_uses_json(monkeypatch):
    monkeypatch.setattr("app.agent.agents.main_agent.FORCE_ROUTE", None)
    monkeypatch.setattr(
        "app.agent.agents.main_agent.get_simple_workflow_v2_subgraph",
        lambda: _build_leaf_subgraph("from simple"),
    )

    async def _general():
        return _build_leaf_subgraph("from react")

    monkeypatch.setattr("app.agent.agents.main_agent.get_general_agent_subgraph", _general)

    captured = {}

    async def _fake_classify(*, messages, **_kwargs):
        captured["last_prompt"] = messages[-1].content
        return SimpleNamespace(route="simple_workflow", reasoning="test")

    monkeypatch.setattr("app.agent.agents.main_agent.ainvoke_structured_with_fallback", _fake_classify)

    graph = asyncio.run(get_main_agent_graph())
    _ = asyncio.run(
        graph.ainvoke(
            {
                "messages": [HumanMessage(content="latest question")],
                "conversation_history": [HumanMessage(content="older question")],
                "execution_results": [],
                "route": "",
                "route_reasoning": "",
            }
        )
    )
    assert '"content": "latest question"' in captured["last_prompt"]
    assert '"content": "older question"' in captured["last_prompt"]
