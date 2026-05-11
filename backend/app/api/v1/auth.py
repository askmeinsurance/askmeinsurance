import hmac
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import get_auth_service
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class DevLoginRequest(BaseModel):
    email: str
    password: str


class DevLoginResponse(BaseModel):
    token_type: str
    access_token: str
    expires_at: str
    user: dict[str, Any]


@router.post("/dev-login", response_model=DevLoginResponse)
async def dev_login(
    payload: DevLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> DevLoginResponse:
    if not auth_service.is_dev_auth_login_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    expected_email = auth_service.settings.dev_superuser_email or ""
    expected_password = auth_service.settings.dev_superuser_password or ""
    provided_email = payload.email.strip()
    provided_password = payload.password

    email_match = hmac.compare_digest(provided_email, expected_email)
    password_match = hmac.compare_digest(provided_password, expected_password)
    if not (email_match and password_match and expected_email and expected_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token, expires_at, claims = auth_service.create_dev_access_token()
    user = await auth_service.build_user_context(claims)
    return DevLoginResponse(
        token_type="bearer",
        access_token=token,
        expires_at=expires_at.astimezone(UTC).isoformat(),
        user=user.model_dump(),
    )
