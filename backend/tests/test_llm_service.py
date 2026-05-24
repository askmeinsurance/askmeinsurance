from types import SimpleNamespace
import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.src.agent_state.agent_state import NameMatchStateOutput
from app.src.services import llm_service


def _base_agent(model: str = "openai|gpt-4o-mini") -> dict:
    return {
        "model": model,
        "temperature": 0,
        "thinking_budget": 0,
        "timeout_seconds": 30,
    }


def test_get_llm_openai_sets_max_tokens(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openai|gpt-4o-mini"), "max_output_tokens": 321},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="openai", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatOpenAI", _chat_openai)

    llm_service.get_llm("agent")
    assert captured["max_tokens"] == 321
    assert captured["model"] == "gpt-4o-mini"
    assert captured["temperature"] == 0


def test_get_llm_openrouter_sets_max_tokens(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openrouter|google/gemini-2.5-flash-lite"), "max_output_tokens": 512},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="openrouter", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatOpenAI", _chat_openai)

    llm_service.get_llm("agent")
    assert captured["max_tokens"] == 512
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["extra_body"] == {"reasoning": {"effort": "none"}}
    assert captured["temperature"] == 0


def test_get_llm_google_sets_max_output_tokens(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("google|gemini-2.5-flash-lite"), "max_output_tokens": 777},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_google(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="google", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatGoogleGenerativeAI", _chat_google)

    llm_service.get_llm("agent")
    assert captured["max_output_tokens"] == 777
    assert captured["model"] == "gemini-2.5-flash-lite"
    assert captured["temperature"] == 0


def test_get_llm_openrouter_thinking_budget_positive_does_not_force_none(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openrouter|google/gemini-2.5-flash-lite"), "thinking_budget": 100},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="openrouter", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatOpenAI", _chat_openai)

    llm_service.get_llm("agent")
    assert "extra_body" not in captured


def test_get_llm_respects_temperature_for_openai(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openai|gpt-4o-mini"), "temperature": 0.7},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="openai", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatOpenAI", _chat_openai)
    llm_service.get_llm("agent")
    assert captured["temperature"] == 0.7


def test_get_llm_respects_temperature_for_google(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("google|gemini-2.5-flash-lite"), "temperature": 0.4},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_google(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="google", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatGoogleGenerativeAI", _chat_google)
    llm_service.get_llm("agent")
    assert captured["temperature"] == 0.4


def test_get_llm_respects_temperature_for_openrouter(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openrouter|google/gemini-2.5-flash-lite"), "temperature": 0.2},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )
    captured = {}

    def _chat_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(provider="openrouter", kwargs=kwargs)

    monkeypatch.setattr(llm_service, "ChatOpenAI", _chat_openai)
    llm_service.get_llm("agent")
    assert captured["temperature"] == 0.2


@pytest.mark.parametrize("value", [0, -1, 3.14, "100", True, False])
def test_get_llm_invalid_max_output_tokens_raise(monkeypatch, value):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openai|gpt-4o-mini"), "max_output_tokens": value},
    )
    monkeypatch.setattr(
        llm_service,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="k", gemini_api_key="g", openrouter_api_key="r"),
    )

    with pytest.raises(ValueError, match="invalid max_output_tokens"):
        llm_service.get_llm("agent")


def test_resolve_timeout_uses_agent_config_first(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent(), "timeout_seconds": 12},
    )
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "77")
    assert llm_service.resolve_timeout_seconds("agent", 30) == 12.0


def test_resolve_timeout_falls_back_to_env_when_missing(monkeypatch):
    config = _base_agent()
    config.pop("timeout_seconds")
    monkeypatch.setattr(llm_service, "get_agent_config", lambda _name: config)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    assert llm_service.resolve_timeout_seconds("agent", 30) == 45.0


def test_resolve_timeout_falls_back_to_default_when_missing(monkeypatch):
    config = _base_agent()
    config.pop("timeout_seconds")
    monkeypatch.setattr(llm_service, "get_agent_config", lambda _name: config)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    assert llm_service.resolve_timeout_seconds("agent", 30) == 30.0


@pytest.mark.parametrize("value", [0, -3, "a", True, False])
def test_resolve_timeout_invalid_agent_config_raises(monkeypatch, value):
    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent(), "timeout_seconds": value},
    )
    with pytest.raises(ValueError, match="invalid timeout_seconds"):
        llm_service.resolve_timeout_seconds("agent", 30)


@pytest.mark.parametrize("value", ["0", "-1", "bad"])
def test_resolve_timeout_invalid_env_raises(monkeypatch, value):
    config = _base_agent()
    config.pop("timeout_seconds")
    monkeypatch.setattr(llm_service, "get_agent_config", lambda _name: config)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="Invalid LLM_TIMEOUT_SECONDS"):
        llm_service.resolve_timeout_seconds("agent", 30)


def test_ainvoke_structured_with_fallback_wraps_single_object_for_single_list_field(monkeypatch):
    class _DummyLLM:
        async def ainvoke(self, _messages, config=None):
            _ = config
            return AIMessage(
                content=(
                    '{"mode":"specific_match","selected_policy_ids":["P123"],'
                    '"applied_filters":{"provider":"AIA","category":"term"},'
                    '"confidence":"high","reason":"exact"}'
                )
            )

    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openrouter|google/gemini-2.5-flash-lite"), "structured_mode": "fallback"},
    )
    monkeypatch.setattr(llm_service, "get_llm", lambda _name: _DummyLLM())

    result = asyncio.run(
        llm_service.ainvoke_structured_with_fallback(
            agent_name="name_match_workflow",
            messages=[HumanMessage(content="test")],
            schema_model=NameMatchStateOutput,
        )
    )

    assert result.lst_policy_matched[0].selected_policy_ids == ["P123"]


def test_ainvoke_structured_with_fallback_accepts_no_match_shape(monkeypatch):
    class _DummyLLM:
        async def ainvoke(self, _messages, config=None):
            _ = config
            return AIMessage(
                content='{"mode":"no_match","selected_policy_ids":null,"applied_filters":{"provider":"AIA"},"confidence":"high","reason":"none"}'
            )

    monkeypatch.setattr(
        llm_service,
        "get_agent_config",
        lambda _name: {**_base_agent("openrouter|google/gemini-2.5-flash-lite"), "structured_mode": "fallback"},
    )
    monkeypatch.setattr(llm_service, "get_llm", lambda _name: _DummyLLM())

    result = asyncio.run(
        llm_service.ainvoke_structured_with_fallback(
            agent_name="name_match_workflow",
            messages=[HumanMessage(content="test")],
            schema_model=NameMatchStateOutput,
        )
    )

    assert result.lst_policy_matched[0].mode == "no_match"
    assert result.lst_policy_matched[0].applied_filters.provider == "AIA"
