from pathlib import Path
from typing import Any, Union

import yaml
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

_CONFIG_PATH = Path(__file__).parent.parent / "agent_config.yaml"


def get_llm(agent_name: str) -> Union[ChatOpenAI, ChatGoogleGenerativeAI]:
    """Return a LangChain LLM object for the given agent name from agent_config.yaml."""
    PROVIDERS = ["google", "openai", "openrouter"]

    with open(_CONFIG_PATH) as f:
        agent_config = yaml.safe_load(f).get(agent_name)

    if not agent_config:
        raise ValueError(f"Agent Name: {agent_name} not found in config.")

    model = agent_config.get("model")
    if not model:
        raise ValueError(f"Agent {agent_name} has no model configured.")

    provider, model_name = model.split("|", 1)
    provider = provider.lower().strip()
    model_name = model_name.lower().strip()

    if provider not in PROVIDERS:
        raise ValueError(f"LLM provider '{provider}' not valid.")

    s = get_settings()

    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            api_key=s.openai_api_key,
            temperature=agent_config.get("temperature", 0),
        )

    if provider == "google":
        thinking_budget = agent_config.get("thinking_budget", 0)
        kwargs: dict[str, Any] = {
            "model": model_name,
            "google_api_key": s.gemini_api_key,
            "thinking_budget": thinking_budget,
            "include_thoughts": True if thinking_budget else None,
            "temperature": agent_config.get("temperature", 0),
        }
        return ChatGoogleGenerativeAI(**kwargs)

    if provider == "openrouter":
        return ChatOpenAI(
            model=model_name,
            api_key=s.openrouter_api_key,
            temperature=agent_config.get("temperature", 0),
        )
