"""
Aegion API Key Management.

Secure API key generation, rotation, and validation.
"""

import secrets
import hashlib
import hmac
from typing import Optional, Dict, List, Tuple
from datetime import timezone, datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum

from ..core.time import TimeAuthority
from ..core.logging import logger


class APIKeyScope(str, Enum):
    """API key permission scopes."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SERVICE = "service"


class APIKey(BaseModel):
    """API key record."""
    key_id: str = Field(..., description="Public key identifier")
    key_hash: str = Field(..., description="Hashed secret key")
    name: str = Field(..., description="Human-readable name")
    scopes: List[APIKeyScope] = Field(default_factory=list)
    created_at: str = Field(default_factory=TimeAuthority.now)
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    is_active: bool = True
    created_by: str = Field(..., description="User who created the key")
    
    # Rotation tracking
    rotation_count: int = 0
    previous_key_hash: Optional[str] = None
    rotation_grace_period_until: Optional[str] = None


class APIKeyService:
    """
    API key management service.
    
    Security features:
    - Keys are hashed before storage (SHA-256)
    - Key rotation with grace period
    - Scope-based permissions
    - Automatic expiration
    """
    
    def __init__(self):
        self._keys: Dict[str, APIKey] = {}
        self._key_prefix = "aeg"
        self._rotation_grace_hours = 24
    
    def generate_key(
        self,
        name: str,
        created_by: str,
        scopes: List[APIKeyScope],
        expires_in_days: Optional[int] = None
    ) -> Tuple[str, APIKey]:
        """
        Generate a new API key.
        
        Returns:
            (raw_key, api_key_record)
            
        The raw_key is returned only once and should be shown to the user.
        """
        # Generate secure random key
        key_id = f"{self._key_prefix}_{secrets.token_urlsafe(8)}"
        key_secret = secrets.token_urlsafe(32)
        raw_key = f"{key_id}.{key_secret}"
        
        # Hash the secret
        key_hash = self._hash_key(key_secret)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            ).isoformat() + "Z"
        
        # Create record
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            scopes=scopes,
            created_by=created_by,
            expires_at=expires_at,
        )
        
        self._keys[key_id] = api_key
        
        logger.info(f"API key created: {key_id} for {created_by}")
        
        return raw_key, api_key
    
    def validate_key(
        self, 
        raw_key: str,
        required_scopes: Optional[List[APIKeyScope]] = None
    ) -> Tuple[bool, Optional[APIKey], Optional[str]]:
        """
        Validate an API key.
        
        Returns:
            (is_valid, api_key_record, error_message)
        """
        try:
            key_id, key_secret = raw_key.split(".", 1)
        except ValueError:
            return False, None, "Invalid key format"
        
        api_key = self._keys.get(key_id)
        if not api_key:
            return False, None, "Key not found"
        
        if not api_key.is_active:
            return False, None, "Key is inactive"
        
        # Check expiration
        if api_key.expires_at:
            expires = datetime.fromisoformat(api_key.expires_at.rstrip("Z"))
            if datetime.now(timezone.utc) > expires:
                return False, None, "Key has expired"
        
        # Verify hash
        key_hash = self._hash_key(key_secret)
        hash_valid = hmac.compare_digest(key_hash, api_key.key_hash)
        
        # Check if in rotation grace period
        if not hash_valid and api_key.previous_key_hash:
            if api_key.rotation_grace_period_until:
                grace_end = datetime.fromisoformat(
                    api_key.rotation_grace_period_until.rstrip("Z")
                )
                if datetime.now(timezone.utc) < grace_end:
                    hash_valid = hmac.compare_digest(
                        key_hash, api_key.previous_key_hash
                    )
        
        if not hash_valid:
            return False, None, "Invalid key"
        
        # Check scopes
        if required_scopes:
            if APIKeyScope.ADMIN in api_key.scopes:
                pass  # Admin has all scopes
            else:
                for scope in required_scopes:
                    if scope not in api_key.scopes:
                        return False, api_key, f"Missing scope: {scope}"
        
        # Update last used
        api_key.last_used_at = TimeAuthority.now()
        
        return True, api_key, None
    
    def rotate_key(self, key_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Rotate an API key.
        
        Returns:
            (new_raw_key, error_message)
        """
        api_key = self._keys.get(key_id)
        if not api_key:
            return None, "Key not found"
        
        # Store old hash for grace period
        api_key.previous_key_hash = api_key.key_hash
        api_key.rotation_grace_period_until = (
            datetime.now(timezone.utc) + timedelta(hours=self._rotation_grace_hours)
        ).isoformat() + "Z"
        
        # Generate new secret
        key_secret = secrets.token_urlsafe(32)
        new_raw_key = f"{key_id}.{key_secret}"
        api_key.key_hash = self._hash_key(key_secret)
        api_key.rotation_count += 1
        
        logger.info(f"API key rotated: {key_id} (rotation #{api_key.rotation_count})")
        
        return new_raw_key, None
    
    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        api_key = self._keys.get(key_id)
        if api_key:
            api_key.is_active = False
            logger.info(f"API key revoked: {key_id}")
            return True
        return False
    
    def list_keys(self, created_by: Optional[str] = None) -> List[APIKey]:
        """List API keys (without hashes)."""
        keys = list(self._keys.values())
        if created_by:
            keys = [k for k in keys if k.created_by == created_by]
        
        # Remove sensitive data
        return [
            APIKey(
                key_id=k.key_id,
                key_hash="[REDACTED]",
                name=k.name,
                scopes=k.scopes,
                created_at=k.created_at,
                expires_at=k.expires_at,
                last_used_at=k.last_used_at,
                is_active=k.is_active,
                created_by=k.created_by,
                rotation_count=k.rotation_count,
            )
            for k in keys
        ]
    
    def _hash_key(self, key_secret: str) -> str:
        """Hash a key secret using SHA-256."""
        return hashlib.sha256(key_secret.encode()).hexdigest()


# Singleton
_api_key_service: Optional[APIKeyService] = None


def get_api_key_service() -> APIKeyService:
    """Get API key service singleton."""
    global _api_key_service
    if _api_key_service is None:
        _api_key_service = APIKeyService()
    return _api_key_service
