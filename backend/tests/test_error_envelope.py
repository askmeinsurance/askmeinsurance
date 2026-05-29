from uuid import uuid4

import httpx
import pytest

from app.dependencies.auth import require_auth
from app.main import create_app
from app.schemas.common import UserContext


async def _fake_user() -> UserContext:
    return UserContext(user_id="test-user")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_check_is_public() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.anyio
async def test_http_exception_is_normalized(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user

    async def _missing_conversation(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.conversations.conversation_service.get_conversation",
        _missing_conversation,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/v1/conversations/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "HTTP_404",
            "message": "Conversation not found",
            "detail": "Conversation not found",
        }
    }


@pytest.mark.anyio
async def test_request_validation_error_is_normalized() -> None:
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/forms", params={"conversation_id": "not-a-uuid"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "HTTP_422"
    assert body["error"]["message"] == "Request validation failed"
    assert isinstance(body["error"]["detail"], list)
    assert body["error"]["detail"]
