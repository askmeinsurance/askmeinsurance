import hmac
from typing import Any

from app.core.config import Settings
from app.schemas.common import UserContext


class AuthService:
    """Auth service boundary for token verification and claim parsing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify JWT and return claims.

        TODO:
        - Validate signature with JWKS/public key.
        - Enforce issuer/audience checks.
        - Enforce expiry and not-before checks.
        """
        if not token or not token.strip():
            raise ValueError("Missing bearer token")

        # Development bypass: when AUTH_ENABLED=false, accept any non-empty bearer token.
        if not self.settings.auth_enabled:
            return {
                "sub": "dev-auth-disabled-user-id",
                "email": "dev-auth-disabled@example.com",
                "role": "super_user",
                "is_super_user": True,
            }

        expected_token = self.settings.auth_dev_bearer_token
        if not expected_token:
            raise ValueError("AUTH_DEV_BEARER_TOKEN is not configured")

        # Temporary development-only behavior:
        # accept only a single bearer token from environment configuration.
        if not hmac.compare_digest(token.strip(), expected_token.strip()):
            raise ValueError("Invalid bearer token")

        return {
            "sub": "dev-super-user-id",
            "email": "dev-super-user@example.com",
            "role": "super_user",
            "is_super_user": True,
        }

    async def build_user_context(self, claims: dict[str, Any]) -> UserContext:
        """Map verified claims to our internal user context."""
        return UserContext(
            user_id=str(claims.get("sub", "")),
            email=claims.get("email"),
            role=claims.get("role"),
            is_super_user=bool(claims.get("is_super_user", False)),
        )
