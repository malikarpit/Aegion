"""
Aegion Data Models - War Room Incidents.

Tracking operational incidents and alerts for the War Room cockpit.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    """Severity level of an incident."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentStatus(str, Enum):
    """Status of an incident."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


class Incident(BaseModel):
    """An operational incident or alert."""

    # Identity
    incident_id: str = Field(..., description="Unique incident ID")
    title: str = Field(..., description="Brief summary of the incident")
    description: str = Field(default="", description="Detailed description")
    workspace_id: str = Field(default="default", description="Workspace this incident belongs to")

    # Classification
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    service: str = Field(..., description="Affected service or component")

    # Metadata
    created_by: str = Field(..., description="User or system that created the incident")
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # Context
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context (e.g. error logs, metrics)")
