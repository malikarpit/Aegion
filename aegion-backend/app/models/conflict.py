
from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"

class Conflict(BaseModel):
    conflict_id: str = Field(..., description="Unique conflict ID")
    workspace_id: str = Field(..., description="Workspace ID")
    rule_id: str = Field(..., description="ID of the violated rule")
    severity: ConflictSeverity = Field(..., description="Severity of the conflict")
    status: ConflictStatus = Field(default=ConflictStatus.OPEN)
    
    # Location
    file_path: Optional[str] = Field(None, description="Path to file with conflict")
    line_number: Optional[int] = Field(None, description="Line number of conflict")
    
    # Details
    message: str = Field(..., description="Human readable conflict message")
    context: Optional[dict] = Field(default_factory=dict, description="Additional context (e.g. diff)")
    
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
