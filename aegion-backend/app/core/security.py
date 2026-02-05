"""
Aegion Security Module.

Doctrine: "Separate auth from authority."
This module handles:
1. Firebase Token Validation (Authentication = Identity)
2. AuthorityContext (Authorization = Power)
3. Token Revocation List (Enterprise Hardening)

Authentication answers: "Who is this?"
AuthorityContext answers: "What can they do?"
"""

from typing import Optional, Set
from pydantic import BaseModel
from enum import Enum
from fastapi import Header
import time
import threading

from .logging import logger


# ========== Token Security Constants ==========

# Maximum allowed token lifetime (1 hour). Reject any JWT with exp > this.
MAX_TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
DEFAULT_ACCESS_TOKEN_EXPIRY = 900  # 15 minutes


# ========== Token Revocation List ==========

class TokenRevocationList:
    """
    Pure in-memory singleton token revocation list.

    State is held in a single process-local dictionary for now:
    {
        "revoked_jtis": {"<jti>": <revoked_at_epoch_seconds>},
        "revoked_users": {"<user_id>": <revoked_at_epoch_seconds>},
    }

    Revoked tokens are stored in thread-safe dictionaries.
    Tokens auto-expire from the revocation list after MAX_TOKEN_EXPIRY_SECONDS
    (no need to track revoked tokens beyond their natural expiry).

    Supports:
    - Individual token revocation by JTI (JWT ID)
    - User-wide revocation (revoke all tokens for a user_id)
    - Check if a token is revoked
    """

    _instance: Optional["TokenRevocationList"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        """Return a process-wide singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._lock = threading.Lock()
                    instance._state = {
                        "revoked_jtis": {},
                        "revoked_users": {},
                    }
                    cls._instance = instance
        return cls._instance

    @classmethod
    def get_instance(cls) -> "TokenRevocationList":
        """Get the singleton revocation list instance."""
        return cls()

    def __init__(self):
        # Keep compatibility aliases for existing tests/callers.
        self._revoked_jtis = self._state["revoked_jtis"]
        self._revoked_users = self._state["revoked_users"]

    def revoke_token(self, jti: str) -> None:
        """Revoke a specific token by its JWT ID."""
        with self._lock:
            self._revoked_jtis[jti] = time.time()
            logger.info("Token revoked", extra={"jti": jti})

    def revoke_user_tokens(self, user_id: str) -> None:
        """Revoke ALL tokens for a user (e.g., on password change, compromise)."""
        with self._lock:
            self._revoked_users[user_id] = time.time()
            logger.info("All tokens revoked for user", extra={"user_id": user_id})

    def is_revoked(self, jti: str, user_id: Optional[str] = None,
                   issued_at: Optional[float] = None) -> bool:
        """
        Check if a token is revoked.

        A token is revoked if:
        1. Its JTI is in the revocation list, OR
        2. The user's tokens were revoked AFTER the token was issued.
        """
        with self._lock:
            # Check individual token revocation
            if jti in self._revoked_jtis:
                return True

            # Check user-wide revocation
            if user_id and user_id in self._revoked_users:
                revoked_at = self._revoked_users[user_id]
                # If token was issued before revocation, it's revoked
                if issued_at is None or issued_at <= revoked_at:
                    return True

            return False

    def cleanup_expired(self) -> int:
        """Remove entries older than MAX_TOKEN_EXPIRY_SECONDS. Returns count removed."""
        cutoff = time.time() - MAX_TOKEN_EXPIRY_SECONDS
        removed = 0
        with self._lock:
            expired_jtis = [j for j, t in self._revoked_jtis.items() if t < cutoff]
            for jti in expired_jtis:
                del self._revoked_jtis[jti]
                removed += 1

            expired_users = [u for u, t in self._revoked_users.items() if t < cutoff]
            for uid in expired_users:
                del self._revoked_users[uid]
                removed += 1

        return removed

    def clear(self) -> None:
        """Clear all revoked state (primarily for deterministic tests)."""
        with self._lock:
            self._revoked_jtis.clear()
            self._revoked_users.clear()

    @property
    def size(self) -> int:
        """Current number of revoked entries."""
        with self._lock:
            return len(self._revoked_jtis) + len(self._revoked_users)


def get_revocation_list() -> TokenRevocationList:
    """Get the singleton token revocation list."""
    return TokenRevocationList.get_instance()


class Role(str, Enum):
    ADMIN = "admin"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class AuthorityContext(BaseModel):
    """
    Encapsulates what the current user CAN DO.
    This is computed after authentication, based on role + project context.
    """
    user_id: str
    role: Role
    email: Optional[str] = None
    display_name: Optional[str] = None
    
    # Explicit capability flags (not derived from role alone)
    can_propose_t1: bool = True
    can_propose_t2: bool = False
    can_approve_t1: bool = False
    can_approve_t2: bool = False
    can_write_memory: bool = False  # Only Chronos service can write memory
    
    # Scope limits
    allowed_modules: Set[str] = set()  # Empty = all allowed
    
    @classmethod
    def from_role(cls, user_id: str, role: Role, email: str = None, display_name: str = None) -> "AuthorityContext":
        """Factory method to create AuthorityContext from a role."""
        context = None
        if role == Role.ADMIN:
            context = cls(
                user_id=user_id,
                role=role,
                can_propose_t1=True,
                can_propose_t2=True,
                can_approve_t1=True,
                can_approve_t2=True,
            )
        elif role == Role.ARCHITECT:
            context = cls(
                user_id=user_id,
                role=role,
                can_propose_t1=True,
                can_propose_t2=True,
                can_approve_t1=True,
                can_approve_t2=False,  # Only Admin can approve T2
            )
        else:  # DEVELOPER, VIEWER
            context = cls(
                user_id=user_id,
                role=role,
                can_propose_t1=True,
                can_propose_t2=False,
                can_approve_t1=False,
                can_approve_t2=False,
            )
        
        context.email = email
        context.display_name = display_name or email  # Fallback to email if no name
        return context


async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Validates Firebase ID token.
    Returns decoded claims if valid, None otherwise.
    
    Phase 1: Real authentication using firebase_admin.
    """
    import os
    
    # Allow mock tokens ONLY in debug mode if explicitly set
    # Using 'false' as default to ensure production safety
    if os.getenv("AEGION_DEBUG", "false").lower() == "true":
        if token and token.startswith("mock-"):
            uid = token.replace("mock-", "")
            return {
                "uid": uid, 
                "email": f"{uid}@aegion.io",
                "name": uid.capitalize()
            }

    try:
        from firebase_admin import auth
        decoded = auth.verify_id_token(token, check_revoked=True)
        return decoded
    except auth.RevokedIdTokenError:
        raise ValueError("Token revoked")
    except auth.ExpiredIdTokenError:
        raise ValueError("Token expired")
    except Exception as e:
        # If firebase not initialized or token invalid
        return None


# FastAPI Dependency
async def get_current_user(
    authorization: str = Header(None),
    x_workspace_id: str = Header(None)
) -> AuthorityContext:
    """
    FastAPI dependency to get current authenticated user.
    
    Enforces valid authentication and resolves role from workspace context.
    """
    from fastapi import HTTPException
    from ..adapters.firestore.workspace_repository import FirestoreWorkspaceRepository
    
    # 1. Enforce Authentication (Who are you?)
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication credentials"
        )
    
    # Extract token from "Bearer <token>"
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    
    # Verify token
    try:
        claims = await verify_firebase_token(token)
        if not claims:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
            
        jti = claims.get("jti") or token  # fallback if no jti
        user_id = claims["uid"]
        
        # Check local revocation list
        revocation_list = get_revocation_list()
        if revocation_list.is_revoked(jti, user_id=user_id):
            raise HTTPException(
                status_code=401,
                detail="Token has been revoked"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
    
    # 2. Resolve Authorization (What can you do?)
    # Default to VIEWER if no workspace context or not a member
    role = Role.VIEWER
    
    if x_workspace_id:
        repo = FirestoreWorkspaceRepository()
        member = await repo.get_member(x_workspace_id, user_id)
        
        if member:
            # Map WorkspaceRole to AuthorityContext Role
            # Assuming simple mapping for now; can be expanded
            repo_role = member.role.value if hasattr(member.role, 'value') else member.role
            
            if repo_role == 'owner' or repo_role == 'admin':
                role = Role.ADMIN
            elif repo_role == 'editor' or repo_role == 'member':
                role = Role.DEVELOPER
            else:
                role = Role.VIEWER
    
    # Create context
    return AuthorityContext.from_role(
        user_id=user_id, 
        role=role,
        email=claims.get("email"),
        display_name=claims.get("name")
    )

