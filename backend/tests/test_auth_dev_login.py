import httpx
import pytest

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _reset_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_dev_login_success_in_local_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEV_SUPERUSER_EMAIL", "dev@example.com")
    monkeypatch.setenv("DEV_SUPERUSER_PASSWORD", "super-secret")
    monkeypatch.setenv("DEV_JWT_SIGNING_SECRET", "dev-jwt-secret")
    _reset_settings_cache()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/dev-login",
            json={"email": "dev@example.com", "password": "super-secret"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("access_token"), str)
    assert payload["access_token"]
    assert payload.get("token_type") == "bearer"


@pytest.mark.anyio
async def test_dev_login_fails_without_dev_token_config(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEV_SUPERUSER_EMAIL", "dev@example.com")
    monkeypatch.delenv("DEV_SUPERUSER_PASSWORD", raising=False)
    monkeypatch.delenv("DEV_JWT_SIGNING_SECRET", raising=False)
    _reset_settings_cache()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/dev-login",
            json={"email": "dev@example.com", "password": "wrong"},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_dev_login_is_blocked_outside_dev_like_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEV_SUPERUSER_EMAIL", "dev@example.com")
    monkeypatch.setenv("DEV_SUPERUSER_PASSWORD", "super-secret")
    monkeypatch.setenv("DEV_JWT_SIGNING_SECRET", "dev-jwt-secret")
    _reset_settings_cache()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/dev-login",
            json={"email": "dev@example.com", "password": "super-secret"},
        )

    assert response.status_code == 404


@pytest.fixture(autouse=True)
def _cleanup_settings_cache() -> None:
    yield
    _reset_settings_cache()
