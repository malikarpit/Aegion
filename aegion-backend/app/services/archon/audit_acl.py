"""
Aegion Archon - Audit Access Control Service.

Phase 4: Execution & Resilience
Manages fine-grained permissions for audit log access.
"""

from typing import List, Optional, Dict
import uuid

from ...contracts.audit_permission import (
    AuditPermission,
    AuditGrant,
    AuditQuery
)
from ...core.logging import logger
from ...core.time import TimeAuthority


class AuditACLService:
    """
    Service for managing audit log access control.
    
    Responsibilities:
    - Grant/revoke audit permissions
    - Check access rights
    - Enforce scope restrictions
    """
    
    def __init__(self):
        self._grants: Dict[str, AuditGrant] = {}
        self._user_grants: Dict[str, List[str]] = {}  # user_id -> grant_ids
    
    async def grant(
        self,
        user_id: str,
        permissions: List[AuditPermission],
        scope: str,
        granted_by: str,
        reason: str,
        expires_at: Optional[str] = None
    ) -> AuditGrant:
        """Grant audit permissions to a user."""
        grant_id = f"grant-{uuid.uuid4().hex[:12]}"
        
        grant = AuditGrant(
            grant_id=grant_id,
            user_id=user_id,
            permissions=permissions,
            scope=scope,
            granted_by=granted_by,
            granted_at=TimeAuthority.now(),
            expires_at=expires_at,
            reason=reason
        )
        
        self._grants[grant_id] = grant
        
        if user_id not in self._user_grants:
            self._user_grants[user_id] = []
        self._user_grants[user_id].append(grant_id)
        
        logger.audit(
            action="AUDIT_GRANT_CREATED",
            actor=granted_by,
            target=user_id,
            justification=reason,
            metadata={
                "grant_id": grant_id,
                "permissions": [p.value for p in permissions],
                "scope": scope
            }
        )
        
        return grant
    
    async def revoke(self, grant_id: str, revoked_by: str) -> bool:
        """Revoke an audit grant."""
        grant = self._grants.get(grant_id)
        if not grant:
            return False
        
        del self._grants[grant_id]
        
        if grant.user_id in self._user_grants:
            self._user_grants[grant.user_id] = [
                g for g in self._user_grants[grant.user_id]
                if g != grant_id
            ]
        
        logger.audit(
            action="AUDIT_GRANT_REVOKED",
            actor=revoked_by,
            target=grant.user_id,
            justification=f"Revoked grant {grant_id}"
        )
        
        return True
    
    async def check_permission(
        self,
        user_id: str,
        permission: AuditPermission,
        scope: Optional[str] = None
    ) -> bool:
        """Check if a user has a specific audit permission."""
        grant_ids = self._user_grants.get(user_id, [])
        
        for grant_id in grant_ids:
            grant = self._grants.get(grant_id)
            if not grant:
                continue
            
            # Check expiration
            if grant.expires_at and grant.expires_at < TimeAuthority.now():
                continue
            
            # Check permission
            if permission not in grant.permissions:
                continue
            
            # Check scope
            if scope and grant.scope != "*" and grant.scope != scope:
                continue
            
            return True
        
        return False
    
    async def get_user_grants(self, user_id: str) -> List[AuditGrant]:
        """Get all active grants for a user."""
        grant_ids = self._user_grants.get(user_id, [])
        grants = []
        now = TimeAuthority.now()
        
        for grant_id in grant_ids:
            grant = self._grants.get(grant_id)
            if grant and (not grant.expires_at or grant.expires_at > now):
                grants.append(grant)
        
        return grants
    
    async def can_query(
        self,
        user_id: str,
        query: AuditQuery
    ) -> tuple[bool, str]:
        """
        Check if a user can execute an audit query.
        Returns (allowed, reason).
        """
        # Check for read_all (admin)
        if await self.check_permission(user_id, AuditPermission.READ_ALL):
            return True, "Admin access"
        
        # Check for read_team with matching workspace
        if query.workspace_id:
            if await self.check_permission(
                user_id,
                AuditPermission.READ_TEAM,
                query.workspace_id
            ):
                return True, "Team workspace access"
        
        # Check for read_own with matching actor
        if query.actor == user_id:
            if await self.check_permission(user_id, AuditPermission.READ_OWN):
                return True, "Own logs access"
        
        return False, "Insufficient permissions"


# Singleton
_audit_acl: Optional[AuditACLService] = None


def get_audit_acl() -> AuditACLService:
    """Get singleton audit ACL service."""
    global _audit_acl
    if _audit_acl is None:
        _audit_acl = AuditACLService()
    return _audit_acl
