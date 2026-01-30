"""
Aegion Contracts - Audit Access Control.

Phase 4: Execution & Resilience
Fine-grained permissions for audit log access.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class AuditPermission(str, Enum):
    """Audit access permission levels."""
    READ_OWN = "read_own"       # View own session logs
    READ_TEAM = "read_team"    # View team workspace logs
    READ_ALL = "read_all"      # Admin - all logs
    EXPORT = "export"          # Download audit exports
    PURGE = "purge"            # Delete old logs (admin only)


class AuditGrant(BaseModel):
    """
    A grant giving a user audit permissions.
    """
    grant_id: str
    user_id: str
    permissions: List[AuditPermission]
    scope: str = "*"  # workspace_id or "*" for all
    granted_by: str
    granted_at: str
    expires_at: Optional[str] = None
    reason: str


class AuditQuery(BaseModel):
    """
    Query parameters for audit log search.
    """
    actor: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None
    workspace_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = Field(default=100, le=1000)
