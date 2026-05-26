import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """Coerce arbitrary runtime values into JSON-serializable structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseMessage):
        data: dict = {"content": value.content, "type": value.type}
        if isinstance(value, AIMessage) and value.tool_calls:
            data["tool_calls"] = to_jsonable(value.tool_calls)
        return data
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): to_jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return str(value)


def format_json_for_prompt(value: Any) -> str:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


_STEP_KEEP = {"step_id", "target", "status", "output", "error"}
_INPUT_DROP = {"messages"}  # user query is already in the prompt separately
_OUTER_KEEP = {"status", "results", "failed_step", "failed_reason"}


def _slim_step(step: dict) -> dict:
    """Keep only inference-relevant fields from a single StepResult dict."""
    slimmed = {k: v for k, v in step.items() if k in _STEP_KEEP}
    if "input" in step and isinstance(step["input"], dict):
        slimmed["input"] = {k: v for k, v in step["input"].items() if k not in _INPUT_DROP}
    return slimmed


def _slim_execution_result(turn: dict) -> dict:
    """Strip executor bookkeeping fields that carry no value for LLM reasoning."""
    if not isinstance(turn, dict):
        return turn
    slimmed = {k: v for k, v in turn.items() if k in _OUTER_KEEP}
    if "results" in slimmed and isinstance(slimmed["results"], list):
        slimmed["results"] = [
            _slim_step(s) if isinstance(s, dict) else s
            for s in slimmed["results"]
        ]
    return slimmed


def format_execution_results_for_prompt(execution_results: list[Any]) -> str:
    if not execution_results:
        return "[]"

    sections: list[str] = []
    for idx, turn_result in enumerate(execution_results, start=1):
        sections.append(f"===== EXECUTION TURN {idx} =====")
        sections.append(format_json_for_prompt(_slim_execution_result(turn_result)))
    return "\n".join(sections)
