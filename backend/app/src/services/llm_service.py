import os
from pathlib import Path
from typing import Any, Union

import yaml
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

_CONFIG_PATH = Path(__file__).parent.parent / "agent_config.yaml"


def _get_all_agent_configs() -> dict[str, dict[str, Any]]:
    with open(_CONFIG_PATH) as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        raise ValueError("agent_config.yaml must be a mapping of agent names to config blocks.")
    return loaded


def get_agent_config(agent_name: str) -> dict[str, Any]:
    configs = _get_all_agent_configs()
    agent_config = configs.get(agent_name)
    if not isinstance(agent_config, dict) or not agent_config:
        raise ValueError(f"Agent Name: {agent_name} not found in config.")
    return agent_config


def _parse_max_output_tokens(agent_name: str, raw_value: Any) -> int | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value <= 0:
        raise ValueError(
            f"Agent {agent_name} has invalid max_output_tokens={raw_value!r}. "
            "Expected a positive integer."
        )
    return raw_value


def resolve_timeout_seconds(
    agent_name: str,
    default_timeout_seconds: float,
) -> float:
    agent_config = get_agent_config(agent_name)
    timeout_value = agent_config.get("timeout_seconds")

    if timeout_value is None:
        env_timeout = os.getenv("LLM_TIMEOUT_SECONDS")
        if env_timeout is not None and env_timeout.strip() != "":
            try:
                parsed_env = float(env_timeout)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid LLM_TIMEOUT_SECONDS={env_timeout!r}. Expected a positive number."
                ) from exc
            if parsed_env <= 0:
                raise ValueError(
                    f"Invalid LLM_TIMEOUT_SECONDS={env_timeout!r}. Expected a positive number."
                )
            return parsed_env
        return float(default_timeout_seconds)

    if isinstance(timeout_value, bool) or not isinstance(timeout_value, (int, float)):
        raise ValueError(
            f"Agent {agent_name} has invalid timeout_seconds={timeout_value!r}. "
            "Expected a positive number."
        )
    parsed_timeout = float(timeout_value)
    if parsed_timeout <= 0:
        raise ValueError(
            f"Agent {agent_name} has invalid timeout_seconds={timeout_value!r}. "
            "Expected a positive number."
        )
    return parsed_timeout


def get_llm(agent_name: str) -> Union[ChatOpenAI, ChatGoogleGenerativeAI]:
    """Return a LangChain LLM object for the given agent name from agent_config.yaml."""
    PROVIDERS = ["google", "openai", "openrouter"]

    agent_config = get_agent_config(agent_name)

    model = agent_config.get("model")
    if not model:
        raise ValueError(f"Agent {agent_name} has no model configured.")

    provider, model_name = model.split("|", 1)
    provider = provider.lower().strip()
    model_name = model_name.lower().strip()

    if provider not in PROVIDERS:
        raise ValueError(f"LLM provider '{provider}' not valid.")

    max_output_tokens = _parse_max_output_tokens(agent_name, agent_config.get("max_output_tokens"))

    s = get_settings()

    if provider == "openai":
        kwargs: dict[str, Any] = {
            "model": model_name,
            "api_key": s.openai_api_key,
            "temperature": agent_config.get("temperature", 0),
        }
        if max_output_tokens is not None:
            kwargs["max_tokens"] = max_output_tokens
        return ChatOpenAI(**kwargs)

    if provider == "google":
        thinking_budget = agent_config.get("thinking_budget", 0)
        kwargs: dict[str, Any] = {
            "model": model_name,
            "google_api_key": s.gemini_api_key,
            "thinking_budget": thinking_budget,
            "include_thoughts": True if thinking_budget else None,
            "temperature": agent_config.get("temperature", 0),
        }
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    if provider == "openrouter":
        thinking_budget = agent_config.get("thinking_budget", 0)
        kwargs = {
            "model": model_name,
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": s.openrouter_api_key,
            "temperature": agent_config.get("temperature", 0),
        }
        if thinking_budget == 0:
            kwargs["reasoning"] = {"effort": "none"}
        if max_output_tokens is not None:
            kwargs["max_tokens"] = max_output_tokens
        return ChatOpenAI(**kwargs)
