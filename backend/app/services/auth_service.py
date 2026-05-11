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

        # Placeholder coherent claims shape until real verifier is wired.
        return {
            "sub": "placeholder-user-id",
            "email": "user@example.com",
            "role": "user",
            "is_super_user": False,
        }

    async def build_user_context(self, claims: dict[str, Any]) -> UserContext:
        """Map verified claims to our internal user context."""
        return UserContext(
            user_id=str(claims.get("sub", "")),
            email=claims.get("email"),
            role=claims.get("role"),
            is_super_user=bool(claims.get("is_super_user", False)),
        )
