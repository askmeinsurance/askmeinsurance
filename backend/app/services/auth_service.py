import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwt

from app.core.config import Settings
from app.schemas.common import UserContext

logger = logging.getLogger("askmeinsurance.auth.service")

_JWKS_CACHE_TTL_SECONDS = 300


class AuthService:
    """Auth service boundary for token verification and claim parsing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks_keys: list[dict[str, Any]] = []
        self._jwks_cached_at: float = 0.0

    def _resolve_jwks_url(self) -> str:
        if not self.settings.supabase_url:
            raise ValueError("SUPABASE_URL is required for JWKS verification")
        return f"{self.settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    async def _fetch_jwks_keys(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        if (
            not force_refresh
            and self._jwks_keys
            and (now - self._jwks_cached_at) < _JWKS_CACHE_TTL_SECONDS
        ):
            return self._jwks_keys

        jwks_url = self._resolve_jwks_url()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            payload = response.json()

        keys = payload.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError("JWKS response does not contain any keys")

        normalized_keys = [key for key in keys if isinstance(key, dict)]
        if not normalized_keys:
            raise ValueError("JWKS response contains invalid keys")

        self._jwks_keys = normalized_keys
        self._jwks_cached_at = now
        return self._jwks_keys

    async def _find_jwk_for_kid(self, kid: str | None) -> dict[str, Any]:
        keys = await self._fetch_jwks_keys()
        if kid:
            for key in keys:
                if str(key.get("kid", "")) == kid:
                    return key

        # Handle rotations: refresh once and retry before failing.
        keys = await self._fetch_jwks_keys(force_refresh=True)
        if kid:
            for key in keys:
                if str(key.get("kid", "")) == kid:
                    return key

        raise ValueError(f"No JWKS key found for kid={kid or '<missing>'}")

    async def _verify_supabase_jwt(self, token: str) -> dict[str, Any]:
        options = {"verify_aud": bool(self.settings.jwt_audience)}
        header = jwt.get_unverified_header(token)
        algorithm = str(header.get("alg", "")).upper()

        if algorithm in {"RS256", "ES256"}:
            # Backward-compatible override for environments that still provide PEM key directly.
            if self.settings.jwt_public_key:
                return jwt.decode(
                    token,
                    self.settings.jwt_public_key,
                    algorithms=[algorithm],
                    audience=self.settings.jwt_audience,
                    issuer=self.settings.jwt_issuer,
                    options=options,
                )

            kid = str(header.get("kid")) if header.get("kid") is not None else None
            jwk_key = await self._find_jwk_for_kid(kid)
            return jwt.decode(
                token,
                jwk_key,
                algorithms=[algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options=options,
            )

        if algorithm == "HS256":
            secret = self.settings.supabase_jwt_secret
            if not secret:
                logger.info("HS256 token received but SUPABASE_JWT_SECRET is not configured")
                raise ValueError("SUPABASE_JWT_SECRET is not configured for HS256 token verification")
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options=options,
            )

        logger.info("Unsupported JWT algorithm: %s", algorithm or "<missing>")
        raise ValueError(f"Unsupported JWT algorithm: {algorithm or '<missing>'}")

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        if not token or not token.strip():
            raise ValueError("Missing bearer token")

        if not self.settings.auth_enabled:
            logger.warning("AUTH_ENABLED=false bypass accepted (development mode)")
            return {
                "sub": "dev-auth-disabled-user-id",
                "email": "dev-auth-disabled@example.com",
                "role": "user",
                "is_super_user": False,
            }

        try:
            claims = await self._verify_supabase_jwt(token.strip())
            logger.info(
                "Bearer token accepted via Supabase JWT verification sub=%s role=%s exp=%s",
                claims.get("sub"),
                claims.get("role"),
                claims.get("exp"),
            )
            return claims
        except (JWTError, ValueError) as exc:
            logger.info("Supabase JWT verification failed: %s", str(exc))
            raise ValueError("Invalid bearer token") from exc

    async def build_user_context(self, claims: dict[str, Any]) -> UserContext:
        return UserContext(
            user_id=str(claims.get("sub", "")),
            email=claims.get("email"),
            role=claims.get("role"),
            is_super_user=bool(claims.get("is_super_user", False)),
        )
