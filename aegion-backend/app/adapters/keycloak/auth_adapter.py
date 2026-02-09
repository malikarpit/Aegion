"""
Aegion Keycloak Authentication Adapter.

Phase 5: Enterprise SSO via Keycloak.
Supports OIDC/OAuth2 authentication and RBAC integration.
"""

from typing import Dict, Any, Optional, List
from datetime import timezone, datetime, timedelta
from dataclasses import dataclass
import base64
import hashlib

from ...core.logging import logger


@dataclass
class KeycloakConfig:
    """Keycloak configuration."""
    server_url: str = "http://localhost:8080"
    realm: str = "aegion"
    client_id: str = "aegion-backend"
    client_secret: str = ""
    admin_client_id: str = "admin-cli"
    admin_username: str = "admin"
    admin_password: str = ""


@dataclass
class KeycloakUser:
    """Keycloak user representation."""
    user_id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: List[str] = None
    realm_roles: List[str] = None
    attributes: Dict[str, Any] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.realm_roles is None:
            self.realm_roles = []
        if self.attributes is None:
            self.attributes = {}


@dataclass
class TokenInfo:
    """Token information."""
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_in: int
    refresh_expires_in: Optional[int]
    scope: str
    user_id: Optional[str] = None


class KeycloakAuthAdapter:
    """
    Keycloak authentication adapter.
    
    Provides enterprise SSO capabilities via Keycloak.
    
    Doctrine: "Identity is the foundation of trust."
    """
    
    def __init__(self, config: Optional[KeycloakConfig] = None):
        self.config = config or KeycloakConfig()
        self._http_client = None
        self._admin_token: Optional[str] = None
        self._admin_token_expires: Optional[datetime] = None
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        try:
            import httpx
            self._http_client = httpx.AsyncClient(timeout=30.0)
            logger.info(f"Keycloak adapter initialized for {self.config.server_url}")
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx")
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    # ========== Token Operations ==========
    
    async def authenticate(self, username: str, password: str) -> Optional[TokenInfo]:
        """Authenticate user with username/password."""
        token_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/token"
        
        try:
            response = await self._http_client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "username": username,
                    "password": password,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return TokenInfo(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token"),
                    token_type=data["token_type"],
                    expires_in=data["expires_in"],
                    refresh_expires_in=data.get("refresh_expires_in"),
                    scope=data.get("scope", ""),
                    user_id=self._extract_user_id(data["access_token"])
                )
            else:
                logger.warning(f"Authentication failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[TokenInfo]:
        """Refresh access token."""
        token_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/token"
        
        try:
            response = await self._http_client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": refresh_token,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return TokenInfo(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token"),
                    token_type=data["token_type"],
                    expires_in=data["expires_in"],
                    refresh_expires_in=data.get("refresh_expires_in"),
                    scope=data.get("scope", "")
                )
            return None
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and decode access token."""
        introspect_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/token/introspect"
        
        try:
            response = await self._http_client.post(
                introspect_url,
                data={
                    "token": token,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("active"):
                    return data
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None
    
    async def logout(self, refresh_token: str) -> bool:
        """Logout and invalidate tokens."""
        logout_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/logout"
        
        try:
            response = await self._http_client.post(
                logout_url,
                data={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": refresh_token,
                }
            )
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    # ========== User Operations ==========
    
    async def get_user_info(self, token: str) -> Optional[KeycloakUser]:
        """Get user info from token."""
        userinfo_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/userinfo"
        
        try:
            response = await self._http_client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return KeycloakUser(
                    user_id=data.get("sub"),
                    username=data.get("preferred_username"),
                    email=data.get("email", ""),
                    first_name=data.get("given_name"),
                    last_name=data.get("family_name"),
                    roles=data.get("realm_access", {}).get("roles", []),
                    attributes=data
                )
            return None
        except Exception as e:
            logger.error(f"Get user info error: {e}")
            return None
    
    async def get_user_roles(self, token: str) -> List[str]:
        """Extract roles from token."""
        token_data = await self.validate_token(token)
        if not token_data:
            return []
        
        roles = []
        
        # Realm roles
        realm_access = token_data.get("realm_access", {})
        roles.extend(realm_access.get("roles", []))
        
        # Client roles
        resource_access = token_data.get("resource_access", {})
        client_roles = resource_access.get(self.config.client_id, {})
        roles.extend(client_roles.get("roles", []))
        
        return roles
    
    async def has_role(self, token: str, role: str) -> bool:
        """Check if user has specific role."""
        roles = await self.get_user_roles(token)
        return role in roles
    
    async def has_any_role(self, token: str, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        user_roles = await self.get_user_roles(token)
        return any(role in user_roles for role in roles)
    
    # ========== Admin Operations ==========
    
    async def _get_admin_token(self) -> Optional[str]:
        """Get admin access token."""
        if self._admin_token and self._admin_token_expires and datetime.now(timezone.utc) < self._admin_token_expires:
            return self._admin_token
        
        token_url = f"{self.config.server_url}/realms/master/protocol/openid-connect/token"
        
        try:
            response = await self._http_client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": self.config.admin_client_id,
                    "username": self.config.admin_username,
                    "password": self.config.admin_password,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self._admin_token = data["access_token"]
                self._admin_token_expires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"] - 30)
                return self._admin_token
            return None
        except Exception as e:
            logger.error(f"Admin token error: {e}")
            return None
    
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        roles: Optional[List[str]] = None
    ) -> Optional[str]:
        """Create a new user (admin operation)."""
        admin_token = await self._get_admin_token()
        if not admin_token:
            return None
        
        users_url = f"{self.config.server_url}/admin/realms/{self.config.realm}/users"
        
        user_data = {
            "username": username,
            "email": email,
            "enabled": True,
            "emailVerified": True,
            "firstName": first_name,
            "lastName": last_name,
            "credentials": [{
                "type": "password",
                "value": password,
                "temporary": False
            }]
        }
        
        try:
            response = await self._http_client.post(
                users_url,
                json=user_data,
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            
            if response.status_code == 201:
                location = response.headers.get("Location", "")
                user_id = location.split("/")[-1] if location else None
                
                # Assign roles if specified
                if user_id and roles:
                    await self._assign_roles(user_id, roles, admin_token)
                
                return user_id
            else:
                logger.warning(f"Create user failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Create user error: {e}")
            return None
    
    async def _assign_roles(self, user_id: str, roles: List[str], admin_token: str) -> None:
        """Assign roles to a user."""
        # Get available realm roles
        roles_url = f"{self.config.server_url}/admin/realms/{self.config.realm}/roles"
        
        try:
            response = await self._http_client.get(
                roles_url,
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            
            if response.status_code == 200:
                available_roles = response.json()
                roles_to_assign = [r for r in available_roles if r["name"] in roles]
                
                if roles_to_assign:
                    assign_url = f"{self.config.server_url}/admin/realms/{self.config.realm}/users/{user_id}/role-mappings/realm"
                    await self._http_client.post(
                        assign_url,
                        json=roles_to_assign,
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
        except Exception as e:
            logger.error(f"Assign roles error: {e}")
    
    # ========== Helpers ==========
    
    def _extract_user_id(self, token: str) -> Optional[str]:
        """Extract user ID from JWT token."""
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                payload = parts[1]
                # Add padding if needed
                padding = 4 - len(payload) % 4
                if padding != 4:
                    payload += "=" * padding
                import json
                decoded = base64.urlsafe_b64decode(payload)
                data = json.loads(decoded)
                return data.get("sub")
        except Exception:
            pass
        return None


# Factory function
def create_keycloak_adapter(config: Optional[KeycloakConfig] = None) -> KeycloakAuthAdapter:
    """Create Keycloak adapter instance."""
    return KeycloakAuthAdapter(config)
