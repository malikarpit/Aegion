"""
Aegion Firebase Auth Adapter.

Implements AuthenticationPort using Firebase Admin SDK.
Phase 1-4 implementation.
"""

from typing import Optional, Dict, Any
from firebase_admin import auth, credentials, initialize_app
import firebase_admin

from ...ports.auth import (
    AuthenticationPort,
    AuthorizationPort,
    AuthenticatedUser,
    AuthProvider,
)
from ...core.security import AuthorityContext, Role
from ...core.logging import logger


class FirebaseAuthAdapter(AuthenticationPort):
    """
    Firebase Admin SDK implementation of AuthenticationPort.
    """
    
    _initialized = False
    
    def __init__(self):
        self._ensure_initialized()
    
    @classmethod
    def _ensure_initialized(cls):
        """Initialize Firebase Admin SDK once."""
        if not cls._initialized:
            try:
                # Check if already initialized
                firebase_admin.get_app()
            except ValueError:
                # Initialize with default credentials
                initialize_app()
            cls._initialized = True
    
    async def verify_token(self, token: str) -> Optional[AuthenticatedUser]:
        """
        Verify Firebase ID token.
        Returns AuthenticatedUser if valid, None if invalid.
        """
        try:
            decoded_token = auth.verify_id_token(token)
            
            user = AuthenticatedUser(
                user_id=decoded_token["uid"],
                email=decoded_token.get("email", ""),
                email_verified=decoded_token.get("email_verified", False),
                provider=AuthProvider.FIREBASE,
                raw_claims=decoded_token
            )
            
            logger.info(
                f"Token verified for user {user.user_id}",
                user_id=user.user_id
            )
            
            return user
            
        except auth.InvalidIdTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except auth.ExpiredIdTokenError as e:
            logger.warning(f"Expired token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke refresh tokens for the user."""
        try:
            decoded_token = auth.verify_id_token(token)
            auth.revoke_refresh_tokens(decoded_token["uid"])
            
            logger.audit(
                action="TOKEN_REVOKED",
                actor="system",
                target=decoded_token["uid"],
                justification="Token revocation requested"
            )
            
            return True
        except Exception as e:
            logger.error(f"Token revocation failed: {e}")
            return False
    
    async def get_user_by_id(self, user_id: str) -> Optional[AuthenticatedUser]:
        """Get user info from Firebase."""
        try:
            user_record = auth.get_user(user_id)
            
            return AuthenticatedUser(
                user_id=user_record.uid,
                email=user_record.email or "",
                email_verified=user_record.email_verified,
                provider=AuthProvider.FIREBASE,
                raw_claims={}
            )
        except auth.UserNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None
    
    async def create_custom_token(
        self, user_id: str, claims: Dict[str, Any] = None
    ) -> str:
        """Create custom token for service-to-service auth."""
        try:
            token = auth.create_custom_token(user_id, claims or {})
            return token.decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to create custom token: {e}")
            raise


class FirebaseAuthorizationAdapter(AuthorizationPort):
    """
    Authorization adapter that builds AuthorityContext.
    
    Doctrine: Authentication ≠ Authorization
    - Firebase handles "who is this?"
    - AuthorityContext handles "what can they do?"
    """
    
    # Role mapping (would be stored in DB in production)
    _user_roles: Dict[str, Dict[str, str]] = {}
    
    async def get_user_roles(self, user_id: str, workspace_id: str) -> list[str]:
        """Get roles for user in workspace."""
        key = f"{user_id}:{workspace_id}"
        if key in self._user_roles:
            return [self._user_roles[key]]
        
        # Default to developer role
        return ["developer"]
    
    async def check_permission(
        self, user_id: str, workspace_id: str, permission: str
    ) -> bool:
        """Check specific permission."""
        context = await self.get_authority_context(user_id, workspace_id)
        
        permission_map = {
            "propose_t1": context.can_propose_t1,
            "propose_t2": context.can_propose_t2,
            "approve_t1": context.can_approve_t1,
            "approve_t2": context.can_approve_t2,
            "write_memory": context.can_write_memory,
        }
        
        return permission_map.get(permission, False)
    
    async def get_authority_context(
        self, user_id: str, workspace_id: str
    ) -> AuthorityContext:
        """Build AuthorityContext from user's roles."""
        roles = await self.get_user_roles(user_id, workspace_id)
        
        # Map first role to our Role enum
        role_mapping = {
            "admin": Role.ADMIN,
            "architect": Role.ARCHITECT,
            "developer": Role.DEVELOPER,
            "viewer": Role.VIEWER,
        }
        
        role = role_mapping.get(roles[0] if roles else "viewer", Role.VIEWER)
        
        return AuthorityContext.from_role(user_id, role)
    
    def set_user_role(self, user_id: str, workspace_id: str, role: str):
        """Set user role (for testing/admin)."""
        key = f"{user_id}:{workspace_id}"
        self._user_roles[key] = role
