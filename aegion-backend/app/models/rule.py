"""
Aegion Data Models - Rule.

Governance rules scoped by org/repo for enforcing policies.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class RulePriority(str, Enum):
    """Priority level for a rule."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleScope(str, Enum):
    """Scope level for a rule."""
    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    SESSION = "session"


class Rule(BaseModel):
    """A governance rule definition."""

    # Identity
    rule_id: str = Field(..., description="Unique rule ID")
    name: str = Field(..., description="Human-readable rule name")

    # Definition
    description: str = Field("", description="What this rule does")
    condition: str = Field(..., description="Condition expression (e.g., 'file.extension == .py')")
    action: str = Field(..., description="Action to take (e.g., 'require_review', 'block', 'warn')")

    # Scope
    scope: RuleScope = Field(default=RuleScope.REPOSITORY)
    scope_id: str = Field("", description="Org/repo/session ID")

    # Configuration
    priority: RulePriority = Field(default=RulePriority.MEDIUM)
    enabled: bool = Field(default=True)
    tags: List[str] = Field(default_factory=list)

    # Metadata
    created_by: str = Field(...)
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Optional config
    config: Dict[str, Any] = Field(default_factory=dict)
