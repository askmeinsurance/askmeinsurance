import asyncio
import json
from uuid import UUID, uuid4

import httpx

from app.dependencies.auth import require_auth
from app.main import create_app
from app.schemas.common import UserContext
from app.services.form_service import FormService


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


def test_sse_emits_chunk_text_and_canonical_form_payload() -> None:
    async def _run() -> None:
        FormService.clear_store()
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

            assert "form_requested" in by_type
            form_data = by_type["form_requested"]
            assert UUID(form_data["form_id"])
            assert form_data["conversation_id"] == str(conversation_id)
            assert form_data["title"] == "Insurance Planning Intake"
            assert form_data["description"]
            assert form_data["submit_label"] == "Submit Details"
            assert isinstance(form_data["pages"], list)
            assert form_data["pages"]
            first_page = form_data["pages"][0]
            assert first_page["id"] == "profile"
            assert isinstance(first_page["fields"], list)
            assert {"id", "label", "type", "required"}.issubset(first_page["fields"][0].keys())

        app.dependency_overrides.clear()

    asyncio.run(_run())


def test_emitted_form_id_can_be_submitted_via_forms_submit() -> None:
    async def _run() -> None:
        FormService.clear_store()
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_auth

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Help me choose coverage", "conversation_id": str(uuid4())},
            )
            assert response.status_code == 200

            events = _parse_sse_events(response.text)
            form_events = [event for event in events if event["event"] == "form_requested"]
            assert form_events
            form_id = form_events[0]["data"]["form_id"]

            submit_response = await client.post(
                f"/api/v1/forms/{form_id}/submit",
                json={"fields": {"full_name": "Alex Tan", "smoker": False}},
            )
            assert submit_response.status_code == 200
            payload = submit_response.json()
            assert payload["id"] == form_id
            assert payload["status"] == "submitted"
            assert payload["fields"]["full_name"] == "Alex Tan"
            assert payload["fields"]["smoker"] is False

        app.dependency_overrides.clear()

    asyncio.run(_run())
