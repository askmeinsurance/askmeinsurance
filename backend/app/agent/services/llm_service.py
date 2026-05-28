import os
import json
import logging
from pathlib import Path
from typing import Annotated, Any, Union, get_args, get_origin

import yaml
from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import get_settings

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
logger = logging.getLogger("askmeinsurance.llm")


def _get_all_agent_configs() -> dict[str, dict[str, Any]]:
    with open(_CONFIG_PATH) as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        raise ValueError("config.yaml must be a mapping of agent names to config blocks.")
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
    """Return a LangChain LLM object for the given agent name from config.yaml."""
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
            "use_responses_api": False,
            "temperature": agent_config.get("temperature", 0),
        }
        if thinking_budget == 0:
            # Chat Completions rejects unknown top-level params like `reasoning`.
            # Pass OpenRouter-specific controls via `extra_body` instead.
            kwargs["extra_body"] = {"reasoning": {"effort": "none"}}
        if max_output_tokens is not None:
            kwargs["max_tokens"] = max_output_tokens
        return ChatOpenAI(**kwargs)


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks)
    return str(content)


def _strip_markdown_json_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return text


def _unwrap_annotated(annotation: Any) -> Any:
    current = annotation
    while get_origin(current) is Annotated:
        args = get_args(current)
        if not args:
            break
        current = args[0]
    return current


def _normalize_single_field_payload(parsed: Any, schema_model: type[BaseModel]) -> Any:
    if not isinstance(parsed, dict):
        return parsed

    fields = schema_model.model_fields
    if len(fields) != 1:
        return parsed

    field_name, field_info = next(iter(fields.items()))
    if field_name in parsed:
        return parsed

    annotation = _unwrap_annotated(field_info.annotation)
    if get_origin(annotation) is list:
        return {field_name: [parsed]}
    return {field_name: parsed}


def invoke_structured_with_fallback(
    *,
    agent_name: str,
    messages: list[BaseMessage],
    schema_model: type[BaseModel],
    timeout_seconds: float | None = None,
    config: dict[str, Any] | None = None,
) -> BaseModel:
    """Invoke a structured model with fallback JSON parsing for providers
    that return plain text instead of OpenAI parsed/refusal fields."""
    agent_config = get_agent_config(agent_name)
    structured_mode = str(agent_config.get("structured_mode", "auto")).strip().lower()
    model = agent_config.get("model", "unknown")
    provider = model.split("|", 1)[0].strip().lower() if "|" in model else ""

    llm = get_llm(agent_name)
    invoke_config = dict(config or {})
    if timeout_seconds:
        invoke_config["timeout"] = timeout_seconds
    if structured_mode == "auto" and provider == "openrouter":
        structured_mode = "fallback"

    if structured_mode in {"native", "auto"}:
        try:
            return llm.with_structured_output(schema_model).invoke(messages, config=invoke_config)
        except ValueError as exc:
            err_text = str(exc)
            if (
                structured_mode == "native"
                or "does not have a 'parsed' field nor a 'refusal' field" not in err_text
            ):
                raise
            logger.warning(
                "Structured output parser fallback engaged: agent=%s model=%s reason=%s",
                agent_name,
                model,
                "missing_parsed_or_refusal",
            )

    raw = llm.invoke(messages, config=invoke_config)
    if isinstance(raw, AIMessage):
        raw_text = _extract_text_content(raw.content)
    else:
        raw_text = _extract_text_content(raw)
    sanitized = _strip_markdown_json_fences(raw_text)
    candidate = _extract_first_json_object(sanitized)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        excerpt = raw_text[:300]
        raise ValueError(
            f"Fallback JSON parse failed for agent={agent_name}, model={model}. "
            f"Raw excerpt={excerpt!r}"
        ) from exc

    normalized_payload = _normalize_single_field_payload(parsed, schema_model)
    try:
        result = schema_model.model_validate(normalized_payload)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Fallback schema validation failed for agent={agent_name}, "
            f"model={model}, schema={schema_model.__name__}"
        ) from exc

    logger.info(
        "Structured output succeeded via json fallback: agent=%s model=%s schema=%s",
        agent_name,
        model,
        schema_model.__name__,
    )
    return result


async def ainvoke_structured_with_fallback(
    *,
    agent_name: str,
    messages: list[BaseMessage],
    schema_model: type[BaseModel],
    timeout_seconds: float | None = None,
    config: dict[str, Any] | None = None,
) -> BaseModel:
    """Async variant of invoke_structured_with_fallback."""
    agent_config = get_agent_config(agent_name)
    structured_mode = str(agent_config.get("structured_mode", "auto")).strip().lower()
    model = agent_config.get("model", "unknown")
    provider = model.split("|", 1)[0].strip().lower() if "|" in model else ""

    llm = get_llm(agent_name)
    invoke_config = dict(config or {})
    if timeout_seconds:
        invoke_config["timeout"] = timeout_seconds
    if structured_mode == "auto" and provider == "openrouter":
        structured_mode = "fallback"

    if structured_mode in {"native", "auto"}:
        try:
            return await llm.with_structured_output(schema_model).ainvoke(messages, config=invoke_config)
        except ValueError as exc:
            err_text = str(exc)
            if (
                structured_mode == "native"
                or "does not have a 'parsed' field nor a 'refusal' field" not in err_text
            ):
                raise
            logger.warning(
                "Structured output parser fallback engaged: agent=%s model=%s reason=%s",
                agent_name,
                model,
                "missing_parsed_or_refusal",
            )

    raw = await llm.ainvoke(messages, config=invoke_config)
    if isinstance(raw, AIMessage):
        raw_text = _extract_text_content(raw.content)
    else:
        raw_text = _extract_text_content(raw)
    sanitized = _strip_markdown_json_fences(raw_text)
    candidate = _extract_first_json_object(sanitized)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        excerpt = raw_text[:300]
        raise ValueError(
            f"Fallback JSON parse failed for agent={agent_name}, model={model}. "
            f"Raw excerpt={excerpt!r}"
        ) from exc

    normalized_payload = _normalize_single_field_payload(parsed, schema_model)
    try:
        result = schema_model.model_validate(normalized_payload)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Fallback schema validation failed for agent={agent_name}, "
            f"model={model}, schema={schema_model.__name__}"
        ) from exc

    logger.info(
        "Structured output succeeded via json fallback: agent=%s model=%s schema=%s",
        agent_name,
        model,
        schema_model.__name__,
    )
    return result
