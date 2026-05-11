import asyncio
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import httpx

from app.dependencies.auth import require_auth
from app.main import create_app
from app.schemas.common import UserContext
from app.services.conversation_service import conversation_service


async def _fake_auth() -> UserContext:
    return UserContext(user_id="test-user")


def _parse_sse_events(body: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current_event: str | None = None
    current_data: str | None = None
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: ") :]
        elif line.startswith("data: "):
            current_data = line[len("data: ") :]
        elif line == "" and current_event and current_data:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None
    return events


def test_existing_conversation_touch_and_messages_endpoint() -> None:
    async def _run() -> None:
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_auth

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            created = await client.post("/api/v1/conversations", json={"title": "Manual title"})
            assert created.status_code == 201
            conversation = created.json()
            conversation_id = conversation["id"]
            old_updated_at = datetime.fromisoformat(conversation["updated_at"])

            # Backdate timestamp to prove touch on stream.
            model = await conversation_service.get_conversation(UUID(conversation_id))
            assert model is not None
            model.updated_at = model.updated_at - timedelta(minutes=5)

            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "hello there", "conversation_id": conversation_id},
            )
            assert response.status_code == 200
            assert _parse_sse_events(response.text)

            refreshed = await client.get(f"/api/v1/conversations/{conversation_id}")
            assert refreshed.status_code == 200
            touched_updated_at = datetime.fromisoformat(refreshed.json()["updated_at"])
            assert touched_updated_at > old_updated_at

            messages = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
            assert messages.status_code == 200
            payload = messages.json()
            assert len(payload) >= 2
            assert payload[0]["role"] == "user"
            assert payload[1]["role"] == "bot"

            missing = await client.get(f"/api/v1/conversations/{uuid4()}/messages")
            assert missing.status_code == 404
            assert missing.json()["error"]["message"] == "Conversation not found"

        app.dependency_overrides.clear()

    asyncio.run(_run())
