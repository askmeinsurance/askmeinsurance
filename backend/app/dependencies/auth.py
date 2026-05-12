import logging

from fastapi import Depends, Request
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

logger = logging.getLogger("askmeinsurance.auth")


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserContext:
    request_id = getattr(request.state, "request_id", "unknown")
    token = extract_bearer_token(credentials)
    token_preview = token[:8] + "..." if len(token) > 8 else "***"

    try:
        claims = await auth_service.verify_access_token(token)
        user_context = await auth_service.build_user_context(claims)
        logger.info(
            "[%s] Auth success token_prefix=%s user_id=%s email=%s",
            request_id,
            token_preview,
            user_context.user_id,
            user_context.email,
        )
        return user_context
    except Exception as exc:  # noqa: BLE001
        # Keep auth failures opaque to avoid leaking verification internals.
        logger.warning(
            "[%s] Auth failure token_prefix=%s error=%s",
            request_id,
            token_preview,
            str(exc),
        )
        raise auth_http_error("Invalid or expired token") from exc


async def require_super_user(
    user: UserContext = Depends(require_auth),
) -> UserContext:
    if not user.is_super_user:
        raise super_user_http_error("Super user privileges required")
    return user
