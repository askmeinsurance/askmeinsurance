import httpx
import pytest

from app.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_auth_verification_accepts_valid_token_when_service_verifies(monkeypatch) -> None:
    async def _verify_ok(self, token: str) -> dict[str, object]:
        assert token == "valid-token"
        return {
            "sub": "user-123",
            "email": "user@example.com",
            "role": "super_user",
            "is_super_user": True,
        }

    monkeypatch.setattr("app.services.auth_service.AuthService.verify_access_token", _verify_ok)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_auth_verification_rejects_invalid_token_when_service_fails(monkeypatch) -> None:
    async def _verify_fail(self, _token: str) -> dict[str, object]:
        raise ValueError("bad token")

    monkeypatch.setattr("app.services.auth_service.AuthService.verify_access_token", _verify_fail)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json() == {
        "error": {
            "code": "HTTP_401",
            "message": "Invalid or expired token",
            "detail": "Invalid or expired token",
        }
    }


@pytest.mark.anyio
async def test_auth_verification_rejects_missing_bearer_header() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/conversations")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json() == {
        "error": {
            "code": "HTTP_401",
            "message": "Missing authorization credentials",
            "detail": "Missing authorization credentials",
        }
    }
