import json
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """Coerce arbitrary runtime values into JSON-serializable structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, BaseMessage):
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


def format_execution_results_for_prompt(execution_results: list[Any]) -> str:
    if not execution_results:
        return "[]"

    sections: list[str] = []
    for idx, turn_result in enumerate(execution_results, start=1):
        sections.append(f"===== EXECUTION TURN {idx} =====")
        sections.append(format_json_for_prompt(turn_result))
    return "\n".join(sections)
