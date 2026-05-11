import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import Settings
from app.schemas.common import UserContext


class AuthService:
    """Auth service boundary for token verification and claim parsing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _is_dev_env(self) -> bool:
        return self.settings.app_env in {"local", "dev"}

    def is_dev_auth_login_enabled(self) -> bool:
        return self._is_dev_env() and self.settings.dev_auth_enabled

    def _verify_supabase_jwt(self, token: str) -> dict[str, Any]:
        secret = self.settings.supabase_jwt_secret
        if not secret:
            raise ValueError("SUPABASE_JWT_SECRET is not configured")

        options = {"verify_aud": bool(self.settings.jwt_audience)}
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=self.settings.jwt_audience,
            issuer=self.settings.jwt_issuer,
            options=options,
        )

    def _verify_dev_jwt(self, token: str) -> dict[str, Any]:
        if not self.is_dev_auth_login_enabled():
            raise ValueError("Dev JWT verification is disabled")

        secret = self.settings.dev_jwt_signing_secret
        if not secret:
            raise ValueError("DEV_JWT_SIGNING_SECRET is not configured")

        claims = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
        if claims.get("token_use") != "dev_auth":
            raise ValueError("Invalid dev token")
        return claims

    def create_dev_access_token(self) -> tuple[str, datetime, dict[str, Any]]:
        secret = self.settings.dev_jwt_signing_secret
        email = self.settings.dev_superuser_email
        if not secret or not email:
            raise ValueError("Dev auth settings are incomplete")

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self.settings.dev_jwt_expires_minutes)
        claims: dict[str, Any] = {
            "sub": "dev-super-user-id",
            "email": email,
            "role": "super_user",
            "is_super_user": True,
            "token_use": "dev_auth",
            "iss": "askmeinsurance-dev",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(claims, secret, algorithm="HS256")
        return token, expires_at, claims

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

        # First-class verification path for Supabase JWTs.
        try:
            return self._verify_supabase_jwt(token.strip())
        except (JWTError, ValueError) as supabase_exc:
            # For local/dev environments we support dedicated dev JWTs.
            try:
                return self._verify_dev_jwt(token.strip())
            except (JWTError, ValueError):
                # Backward-compatible temporary dev bearer token fallback.
                expected_token = self.settings.auth_dev_bearer_token
                if expected_token and hmac.compare_digest(token.strip(), expected_token.strip()):
                    return {
                        "sub": "dev-super-user-id",
                        "email": self.settings.dev_superuser_email or "dev-super-user@example.com",
                        "role": "super_user",
                        "is_super_user": True,
                    }
                raise ValueError("Invalid bearer token") from supabase_exc


    async def build_user_context(self, claims: dict[str, Any]) -> UserContext:
        """Map verified claims to our internal user context."""
        return UserContext(
            user_id=str(claims.get("sub", "")),
            email=claims.get("email"),
            role=claims.get("role"),
            is_super_user=bool(claims.get("is_super_user", False)),
        )
