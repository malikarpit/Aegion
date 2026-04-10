"""
Aegion Auth API — Phase 4: Firebase Auth Hardening.

Provides explicit token revocation endpoints so the backend can immediately
invalidate tokens on logout, without waiting for natural Firebase token expiry.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from ...core.security import get_current_user, get_revocation_list, AuthorityContext

router = APIRouter(prefix="/auth", tags=["auth"])


class LogoutResponse(BaseModel):
    message: str
    revoked: bool


@router.post("/logout", response_model=LogoutResponse, status_code=200)
async def logout(
    current_user: AuthorityContext = Depends(get_current_user),
):
    """
    Logout the current user by revoking their active token.

    Phase 4 behaviour:
    - Revoke the current session's user_id from the in-memory revocation list
      so all tokens issued before this moment for this user are immediately invalid.
    - Phase 7 will back this list with a durable store (Redis/PostgreSQL).
    """
    revocation_list = get_revocation_list()
    revocation_list.revoke_user(current_user.user_id)

    return LogoutResponse(
        message="Logged out successfully. All active tokens revoked.",
        revoked=True,
    )


@router.post("/revoke-token", response_model=LogoutResponse, status_code=200)
async def revoke_specific_token(
    jti: str,
    current_user: AuthorityContext = Depends(get_current_user),
):
    """
    Revoke a specific token by its JWT ID (jti claim).
    Requires admin role. Used for security incident response.
    """
    from ...core.security import Role
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can revoke specific tokens"
        )

    revocation_list = get_revocation_list()
    revocation_list.revoke_token(jti)

    return LogoutResponse(
        message=f"Token {jti} has been revoked.",
        revoked=True,
    )
