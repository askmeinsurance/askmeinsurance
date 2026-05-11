from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import (
    bearer_scheme,
    extract_bearer_token,
    get_auth_service,
    auth_http_error,
    super_user_http_error,
)
from app.schemas.common import UserContext
from app.services.auth_service import AuthService


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserContext:
    token = extract_bearer_token(credentials)

    try:
        claims = await auth_service.verify_access_token(token)
        return await auth_service.build_user_context(claims)
    except Exception as exc:  # noqa: BLE001
        # Keep auth failures opaque to avoid leaking verification internals.
        raise auth_http_error("Invalid or expired token") from exc


async def require_super_user(
    user: UserContext = Depends(require_auth),
) -> UserContext:
    if not user.is_super_user:
        raise super_user_http_error("Super user privileges required")
    return user
