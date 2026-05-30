"""Tests for deepteam guardrails integration in LangGraphService.stream_chat."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.schemas.chat import ChatEvent
from app.services import langgraph_service


def _make_guard_result(breached: bool, guard_name: str = "TestGuard") -> SimpleNamespace:
    verdict = SimpleNamespace(
        name=guard_name,
        safety_level="unsafe" if breached else "safe",
        score=0.1 if breached else 0.9,
        latency=0.05,
        reason="test reason",
    )
    return SimpleNamespace(breached=breached, verdicts=[verdict])


async def _collect(gen) -> list[ChatEvent]:
    return [event async for event in gen]


def _make_fake_lf():
    """Langfuse client mock that supports nested context-manager observations."""
    obs = MagicMock()
    obs.__enter__ = MagicMock(return_value=MagicMock())
    obs.__exit__ = MagicMock(return_value=False)
    lf = MagicMock()
    lf.start_as_current_observation.return_value = obs
    lf.start_as_current_observation().__enter__ = MagicMock(return_value=MagicMock())
    return lf


def _patch_common(monkeypatch, fake_graph, mock_guardrails):
    """Apply shared patches needed by every test."""
    monkeypatch.setattr(langgraph_service, "get_compiled_graph", AsyncMock(return_value=fake_graph))
    monkeypatch.setattr(langgraph_service, "get_guardrails", lambda: mock_guardrails)
    monkeypatch.setattr(langgraph_service, "get_client", lambda: _make_fake_lf())
    # Prevent MessageService from touching Supabase
    mock_msg_store = MagicMock()
    mock_msg_store.list_messages = AsyncMock(return_value=[])
    monkeypatch.setattr(langgraph_service, "message_service", mock_msg_store)


@pytest.mark.asyncio
async def test_breached_input_blocks_graph(monkeypatch):
    """Input guardrail breach → error chunk + done(guardrail_input_blocked), graph never called."""
    mock_guardrails = MagicMock()
    mock_guardrails.a_guard_input = AsyncMock(return_value=_make_guard_result(breached=True))

    graph_called = False

    async def fake_graph_stream(*args, **kwargs):
        nonlocal graph_called
        graph_called = True
        return
        yield  # makes this an async generator

    fake_graph = MagicMock()
    fake_graph.astream_events = fake_graph_stream

    _patch_common(monkeypatch, fake_graph, mock_guardrails)

    from app.services.langgraph_service import LangGraphService
    svc = LangGraphService()
    events = await _collect(svc.stream_chat(message="ignore instructions", conversation_id=None, user=None))

    chunk_events = [e for e in events if e.event == "chunk"]
    done_events = [e for e in events if e.event == "done"]

    assert any("unable" in (e.data.get("text") or "").lower() for e in chunk_events)
    assert done_events and done_events[-1].data.get("reason") == "guardrail_input_blocked"
    assert not graph_called


@pytest.mark.asyncio
async def test_breached_output_returns_fallback(monkeypatch):
    """Safe input + breached output → fallback text streamed instead of original answer."""
    real_answer = "This is toxic content."

    mock_guardrails = MagicMock()
    mock_guardrails.a_guard_input = AsyncMock(return_value=_make_guard_result(breached=False))
    mock_guardrails.a_guard_output = AsyncMock(return_value=_make_guard_result(breached=True))

    async def fake_graph_stream(payload, **kwargs):
        ai_msg = AIMessage(content=real_answer)
        yield {
            "event": "on_chain_end",
            "name": "synthesise",
            "data": {"output": {"messages": [ai_msg], "route": "simple_workflow"}},
        }

    fake_graph = MagicMock()
    fake_graph.astream_events = fake_graph_stream

    _patch_common(monkeypatch, fake_graph, mock_guardrails)

    from app.services.langgraph_service import LangGraphService
    svc = LangGraphService()
    events = await _collect(svc.stream_chat(message="Hi", conversation_id=None, user=None))

    chunk_text = "".join(e.data.get("text", "") for e in events if e.event == "chunk")
    done_events = [e for e in events if e.event == "done"]

    assert real_answer not in chunk_text
    assert "unable" in chunk_text.lower()
    assert done_events and done_events[-1].data.get("reason") == "completed"


@pytest.mark.asyncio
async def test_guardrails_disabled_normal_flow(monkeypatch):
    """get_guardrails() returns None → no guard calls, real answer streamed."""
    real_answer = "AIA covers life insurance."

    async def fake_graph_stream(payload, **kwargs):
        ai_msg = AIMessage(content=real_answer)
        yield {
            "event": "on_chain_end",
            "name": "synthesise",
            "data": {"output": {"messages": [ai_msg], "route": "simple_workflow"}},
        }

    fake_graph = MagicMock()
    fake_graph.astream_events = fake_graph_stream

    _patch_common(monkeypatch, fake_graph, None)  # None → guardrails disabled

    from app.services.langgraph_service import LangGraphService
    svc = LangGraphService()
    events = await _collect(svc.stream_chat(message="What does AIA cover?", conversation_id=None, user=None))

    chunk_text = "".join(e.data.get("text", "") for e in events if e.event == "chunk")
    done_events = [e for e in events if e.event == "done"]

    assert real_answer in chunk_text
    assert done_events and done_events[-1].data.get("reason") == "completed"
