import asyncio
import json
from uuid import uuid4

import httpx

from app.dependencies.auth import require_auth
from app.main import create_app
from app.schemas.common import UserContext


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    current_event: str | None = None
    current_data: dict[str, object] | None = None

    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: ") :]
        elif line.startswith("data: "):
            current_data = json.loads(line[len("data: ") :])
        elif line == "" and current_event is not None and current_data is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None

    if current_event is not None and current_data is not None:
        events.append({"event": current_event, "data": current_data})

    return events


async def _fake_auth() -> UserContext:
    return UserContext(user_id="test-user")


def test_sse_emits_chunk_text_without_form_requested_event() -> None:
    async def _run() -> None:
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_auth

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            conversation_id = uuid4()
            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Need life coverage", "conversation_id": str(conversation_id)},
            )

            assert response.status_code == 200
            events = _parse_sse_events(response.text)
            by_type = {event["event"]: event["data"] for event in events}

            assert "chunk" in by_type
            assert isinstance(by_type["chunk"]["text"], str)
            assert by_type["chunk"]["text"]
            assert "form_requested" not in by_type

        app.dependency_overrides.clear()

    asyncio.run(_run())
