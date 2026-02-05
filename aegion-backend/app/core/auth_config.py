"""
Aegion Auth Configuration — Multi-Provider JWT/Auth Support.

Supports:
- Firebase (default, production)
- Generic JWT/OIDC (Auth0, Keycloak, custom)
- Mock tokens (development only)

Selection via AEGION_AUTH_ADAPTER environment variable.
"""

import os
import hashlib
import hmac
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel


class AuthProviderConfig(BaseModel):
    """Configuration for the active authentication provider."""

    # Provider type: "firebase" | "jwt" | "mock"
    provider: str = os.getenv("AEGION_AUTH_ADAPTER", "firebase")

    # JWT/OIDC settings (used when provider="jwt")
    jwt_issuer: Optional[str] = os.getenv("AEGION_JWT_ISSUER")
    jwt_audience: Optional[str] = os.getenv("AEGION_JWT_AUDIENCE", "aegion-api")
    jwt_algorithm: str = os.getenv("AEGION_JWT_ALGORITHM", "RS256")
    jwks_url: Optional[str] = os.getenv("AEGION_JWKS_URL")

    # Key management
    jwt_secret: Optional[str] = os.getenv("AEGION_JWT_SECRET")

    # TLS enforcement
    require_tls: bool = os.getenv("AEGION_REQUIRE_TLS", "true").lower() == "true"


# Singleton
_auth_config: Optional[AuthProviderConfig] = None


def get_auth_config() -> AuthProviderConfig:
    """Get the global auth configuration."""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthProviderConfig()
    return _auth_config


async def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a generic JWT token using JWKS or shared secret.

    Returns decoded claims if valid, None otherwise.
    """
    config = get_auth_config()

    try:
        import jwt as pyjwt

        # If JWKS URL is configured, fetch public keys
        if config.jwks_url:
            from jwt import PyJWKClient
            jwks_client = PyJWKClient(config.jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            decoded = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=[config.jwt_algorithm],
                audience=config.jwt_audience,
                issuer=config.jwt_issuer,
            )
        elif config.jwt_secret:
            # Shared secret for HS256
            decoded = pyjwt.decode(
                token,
                config.jwt_secret,
                algorithms=[config.jwt_algorithm],
                audience=config.jwt_audience,
                issuer=config.jwt_issuer,
            )
        else:
            return None

        # Map standard claims to Aegion format
        return {
            "uid": decoded.get("sub", decoded.get("uid")),
            "email": decoded.get("email"),
            "name": decoded.get("name", decoded.get("preferred_username")),
            "roles": decoded.get("roles", []),
            "workspace_id": decoded.get("workspace_id"),
        }

    except Exception:
        return None


async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Unified token verification — delegates to the configured provider.
    """
    config = get_auth_config()

    if config.provider == "firebase":
        from .security import verify_firebase_token
        return await verify_firebase_token(token)

    elif config.provider == "jwt":
        return await verify_jwt_token(token)

    elif config.provider == "mock":
        # Only in development
        if os.getenv("AEGION_DEBUG", "false").lower() == "true":
            if token and token.startswith("mock-"):
                uid = token.replace("mock-", "")
                return {
                    "uid": uid,
                    "email": f"{uid}@aegion.io",
                    "name": uid.capitalize(),
                }
        return None

    return None
