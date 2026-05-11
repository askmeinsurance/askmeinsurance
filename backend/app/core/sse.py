import json
from typing import Any


def format_sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"
