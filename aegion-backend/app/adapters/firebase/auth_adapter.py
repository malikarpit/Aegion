"""
Aegion Firebase Auth Adapter.

Implements AuthenticationPort using Firebase Admin SDK.
Initial stub — real verification to be added.
"""

from typing import Optional, Dict, Any
from ...ports.auth import (
    AuthenticationPort,
    AuthorizationPort,
    AuthenticatedUser,
    AuthProvider,
)
from ...core.logging import logger


class FirebaseAuthAdapter(AuthenticationPort):
    """Firebase Admin SDK implementation of AuthenticationPort."""

    async def verify_token(self, token: str) -> Optional[AuthenticatedUser]:
        """Verify Firebase ID token. TODO: Real Firebase Admin SDK."""
        # Stub: returns mock user for local development
        return AuthenticatedUser(
            user_id="dev_user",
            email="dev@aegion.io",
            email_verified=True,
            provider=AuthProvider.FIREBASE,
            raw_claims={}
        )

    async def revoke_token(self, token: str) -> bool:
        """Revoke refresh tokens. TODO: Implement."""
        return True

    async def get_user_by_id(self, user_id: str) -> Optional[AuthenticatedUser]:
        """Get user info. TODO: Implement."""
        return None
