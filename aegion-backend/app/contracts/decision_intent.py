"""
Aegion Data Contracts - Decision Intent.

Doctrine: "Truth is governed, not generated."
DecisionIntent captures the structured reasoning BEFORE code changes.

This is part of the Reasoning Phase Doctrine:
- Problem Framing
- Assumptions
- Constraints
- Boundaries
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ImpactLevel(str, Enum):
    """How much does this decision affect the system?"""
    TRIVIAL = "trivial"      # No architectural impact
    LOCAL = "local"          # Affects single module
    CROSS_MODULE = "cross_module"  # Affects multiple modules
    SYSTEM_WIDE = "system_wide"    # Affects entire system
    EXTERNAL = "external"    # Affects external integrations


class ReversibilityLevel(str, Enum):
    """How easy is it to undo this decision?"""
    TRIVIAL = "trivial"      # Undo with single command
    EASY = "easy"            # Undo within same session
    MODERATE = "moderate"    # Requires rollback plan
    DIFFICULT = "difficult"  # Requires significant effort
    IRREVERSIBLE = "irreversible"  # Cannot be undone


class DecisionTier(str, Enum):
    """Governance tier based on impact and reversibility."""
    T0 = "T0"  # Auto-approved: trivial, reversible
    T1 = "T1"  # User-approved: local, moderate
    T2 = "T2"  # Architect-approved: cross-module, significant
    T3 = "T3"  # Team-approved: system-wide, strategic


class ReasoningPhase(BaseModel):
    """
    Structured reasoning captured before any code.
    From Moltbook Doctrine: "Thinking before coding."
    """
    problem_framing: str = Field(
        ..., description="What are we trying to solve?"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="What do we believe to be true?"
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="What cannot change?"
    )
    boundaries: List[str] = Field(
        default_factory=list,
        description="What is out of scope?"
    )
    alternatives_considered: List[str] = Field(
        default_factory=list,
        description="What other approaches were considered?"
    )
    
    # Optional depth
    risk_assessment: Optional[str] = None
    success_criteria: Optional[List[str]] = None


class DecisionIntent(BaseModel):
    """
    Complete intent declaration for a proposed decision.
    Required before any code changes can be promoted.
    """
    # Identity
    intent_id: str = Field(..., description="Unique identifier")
    session_id: str = Field(..., description="Parent session")
    
    # Classification
    title: str = Field(..., description="Short summary of intent")
    description: str = Field(..., description="Detailed explanation")
    
    # Impact analysis
    impact_level: ImpactLevel
    reversibility: ReversibilityLevel
    calculated_tier: DecisionTier
    
    # Affected scope
    affected_modules: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    affected_invariants: List[str] = Field(default_factory=list)
    
    # Reasoning
    reasoning: ReasoningPhase
    
    # Provenance
    origin: str = Field(
        ..., 
        description="Who/what proposed this: 'human' | 'ai_child' | 'ai_parent'"
    )
    proposed_by: str = Field(..., description="User ID of proposer")
    proposed_at: datetime
    
    # Status
    status: str = Field(
        default="draft",
        description="draft | pending | approved | rejected | superseded"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_id": "intent-123",
                "session_id": "session-456",
                "title": "Add user authentication middleware",
                "description": "Implement JWT validation for all API endpoints",
                "impact_level": "cross_module",
                "reversibility": "moderate",
                "calculated_tier": "T2",
                "affected_modules": ["api", "auth", "middleware"],
                "reasoning": {
                    "problem_framing": "API endpoints are currently unprotected",
                    "assumptions": ["JWT tokens are provided by Firebase"],
                    "constraints": ["Must not break existing endpoints"],
                    "boundaries": ["OAuth flows are out of scope"]
                },
                "origin": "human",
                "proposed_by": "user-789",
                "proposed_at": "2026-02-09T10:00:00Z"
            }
        }
    )


def calculate_tier(impact: ImpactLevel, reversibility: ReversibilityLevel) -> DecisionTier:
    """
    Deterministic tier calculation based on impact and reversibility.
    This is the Archon rule engine.
    """
    # Matrix: higher impact or lower reversibility = higher tier
    if impact == ImpactLevel.TRIVIAL and reversibility in [ReversibilityLevel.TRIVIAL, ReversibilityLevel.EASY]:
        return DecisionTier.T0
    
    if impact in [ImpactLevel.TRIVIAL, ImpactLevel.LOCAL]:
        if reversibility in [ReversibilityLevel.TRIVIAL, ReversibilityLevel.EASY, ReversibilityLevel.MODERATE]:
            return DecisionTier.T1
    
    if impact in [ImpactLevel.LOCAL, ImpactLevel.CROSS_MODULE]:
        if reversibility not in [ReversibilityLevel.IRREVERSIBLE]:
            return DecisionTier.T2
    
    # System-wide, external, or irreversible = T3
    return DecisionTier.T3


# Alias for semantic clarity in validation contexts
classify_decision_tier = calculate_tier
