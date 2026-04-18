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

# ──────────────────────────────────────────────────────
# Phase 89: WebSocket Ticket Exchange
# ──────────────────────────────────────────────────────

import secrets
import time
from typing import Dict, Tuple

_WS_TICKET_TTL = 30  # seconds
_ws_tickets: Dict[str, Tuple[str, float]] = {}  # ticket -> (user_id, expires_at)


def _cleanup_expired_tickets() -> None:
    """Remove expired tickets to prevent memory leak."""
    now = time.time()
    expired = [t for t, (_, exp) in _ws_tickets.items() if exp < now]
    for t in expired:
        del _ws_tickets[t]


class TicketResponse(BaseModel):
    ticket: str
    expires_in: int = _WS_TICKET_TTL


@router.post("/ws-ticket", response_model=TicketResponse, status_code=200)
async def issue_ws_ticket(
    current_user: AuthorityContext = Depends(get_current_user),
):
    """
    Issue a short-lived, one-time-use ticket for WebSocket authentication.

    Phase 89 Security Hardening:
    - Ticket expires after 30 seconds or first use, whichever comes first.
    - Replaces `?token=...` in WebSocket URLs which exposed bearer tokens
      in server access logs, browser history, and HTTP Referer headers.
    - Tickets are consumed on WebSocket handshake via `consume_ws_ticket()`.
    """
    _cleanup_expired_tickets()

    ticket = secrets.token_urlsafe(32)
    _ws_tickets[ticket] = (current_user.user_id, time.time() + _WS_TICKET_TTL)

    return TicketResponse(ticket=ticket)


def consume_ws_ticket(ticket: str) -> Optional[str]:
    """
    Consume a WebSocket ticket and return the user_id.
    Returns None if ticket is invalid, expired, or already used.
    One-time use: ticket is deleted after consumption.
    """
    _cleanup_expired_tickets()

    entry = _ws_tickets.pop(ticket, None)
    if entry is None:
        return None

    user_id, expires_at = entry
    if time.time() > expires_at:
        return None

    return user_id
