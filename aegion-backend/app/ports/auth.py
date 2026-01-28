"""
Aegion Authentication Port (Abstract Interface).

This is the hexagonal architecture PORT for all authentication operations.
Implementations (adapters) include:
- FirebaseAuthAdapter (Phase 1-4)
- KeycloakAdapter (Phase 5+)
- Auth0Adapter (Enterprise alternative)

Doctrine: AuthorityContext is separate from Authentication.
Authentication = "Who is this?"
Authority = "What can they do?"
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel


class AuthProvider(str, Enum):
    """Supported authentication providers."""
    FIREBASE = "firebase"
    KEYCLOAK = "keycloak"
    AUTH0 = "auth0"


class AuthenticatedUser(BaseModel):
    """Result of successful authentication."""
    user_id: str
    email: str
    email_verified: bool
    provider: AuthProvider
    raw_claims: Dict[str, Any] = {}


class AuthenticationPort(ABC):
    """
    Abstract interface for authentication providers.
    Application layer uses this interface; never imports concrete adapters.
    """
    
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[AuthenticatedUser]:
        """
        Verify an authentication token.
        Returns AuthenticatedUser if valid, None if invalid.
        """
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token (e.g., on logout or security event)."""
        pass
    
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[AuthenticatedUser]:
        """Get user info by ID from auth provider."""
        pass
    
    @abstractmethod
    async def create_custom_token(self, user_id: str, claims: Dict[str, Any] = None) -> str:
        """Create a custom token for the user (for service-to-service auth)."""
        pass


class DeviceFlowPort(ABC):
    """
    Device authorization flow for VS Code extension.
    Used when browser-based auth is needed from a non-browser environment.
    """
    
    @abstractmethod
    async def initiate_device_flow(self) -> Dict[str, str]:
        """
        Start device authorization flow.
        Returns: {device_code, user_code, verification_uri, expires_in}
        """
        pass
    
    @abstractmethod
    async def poll_for_token(self, device_code: str) -> Optional[str]:
        """
        Poll for token completion.
        Returns token if user completed auth, None if still pending.
        Raises exception if expired or denied.
        """
        pass


class AuthorizationPort(ABC):
    """
    Authorization (what can they do) - separate from authentication.
    This maps to AuthorityContext in security.py.
    """
    
    @abstractmethod
    async def get_user_roles(self, user_id: str, workspace_id: str) -> list[str]:
        """Get roles for user in a workspace."""
        pass
    
    @abstractmethod
    async def check_permission(
        self, user_id: str, workspace_id: str, permission: str
    ) -> bool:
        """Check if user has a specific permission."""
        pass
    
    @abstractmethod
    async def get_authority_context(
        self, user_id: str, workspace_id: str
    ) -> "AuthorityContext":
        """Build full AuthorityContext for a user in a workspace."""
        pass


# Forward reference
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..core.security import AuthorityContext
