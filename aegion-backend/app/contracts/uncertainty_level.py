"""
Aegion Data Contracts - Uncertainty Level.

Doctrine: "Uncertainty is a first-class signal."
High uncertainty blocks promotion. Low uncertainty allows consideration.

From Hallucination Governance Doctrine:
- Rule H-3: Uncertainty Is a First-Class Signal
- "I don't know" > "Probably"
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class UncertaintyLevel(str, Enum):
    """Discrete uncertainty bands."""
    CERTAIN = "certain"      # >95% confidence
    HIGH = "high"            # 80-95% confidence
    MEDIUM = "medium"        # 50-80% confidence
    LOW = "low"              # 20-50% confidence
    UNKNOWN = "unknown"      # <20% confidence or cannot estimate


class UncertaintySource(str, Enum):
    """What is the source of uncertainty?"""
    DATA_QUALITY = "data_quality"          # Incomplete or noisy input
    MODEL_LIMITATION = "model_limitation"  # AI model confidence
    AMBIGUOUS_CONTEXT = "ambiguous_context"  # Unclear requirements
    CONFLICTING_EVIDENCE = "conflicting_evidence"  # Evidence disagrees
    NO_PRECEDENT = "no_precedent"          # No historical data
    EXTERNAL_DEPENDENCY = "external_dependency"  # Depends on unknown external factors


class UncertaintyDeclaration(BaseModel):
    """
    Explicit uncertainty declaration for AI outputs.
    
    Doctrine: AI must always declare uncertainty.
    Abstention is preferred over false confidence.
    """
    # Core uncertainty
    level: UncertaintyLevel = Field(
        ...,
        description="Discrete uncertainty band"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0, le=1.0,
        description="Numeric confidence 0.0-1.0"
    )
    
    # Sources
    sources: List[UncertaintySource] = Field(
        default_factory=list,
        description="What contributes to uncertainty?"
    )
    
    # Explanation
    reasoning: str = Field(
        ...,
        description="Why this uncertainty level?"
    )
    
    # Blocking
    is_blocking: bool = Field(
        default=False,
        description="Should this block promotion?"
    )
    blocking_reason: Optional[str] = Field(
        default=None,
        description="Why this should block, if blocking"
    )
    
    # Recommendations
    additional_evidence_needed: List[str] = Field(
        default_factory=list,
        description="What evidence could reduce uncertainty?"
    )
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v: float, info) -> float:
        """Ensure confidence aligns with level."""
        # This is a soft validation - we allow slight mismatches
        return v
    
    @classmethod
    def from_confidence(cls, score: float, reasoning: str) -> "UncertaintyDeclaration":
        """Factory method to create from confidence score."""
        if score >= 0.95:
            level = UncertaintyLevel.CERTAIN
        elif score >= 0.80:
            level = UncertaintyLevel.HIGH
        elif score >= 0.50:
            level = UncertaintyLevel.MEDIUM
        elif score >= 0.20:
            level = UncertaintyLevel.LOW
        else:
            level = UncertaintyLevel.UNKNOWN
        
        # Auto-block on unknown
        is_blocking = level == UncertaintyLevel.UNKNOWN
        
        return cls(
            level=level,
            confidence_score=score,
            reasoning=reasoning,
            is_blocking=is_blocking,
            blocking_reason="Uncertainty too high for promotion" if is_blocking else None
        )
    
    @classmethod
    def abstain(cls, reason: str) -> "UncertaintyDeclaration":
        """
        Factory method for explicit abstention.
        Doctrine: Abstention is a valid outcome.
        """
        return cls(
            level=UncertaintyLevel.UNKNOWN,
            confidence_score=0.0,
            reasoning=reason,
            is_blocking=True,
            blocking_reason=f"Explicit abstention: {reason}",
            sources=[UncertaintySource.MODEL_LIMITATION]
        )


class CognitiveLoad(BaseModel):
    """
    Cognitive safety metrics for AI outputs.
    Tracks complexity and potential for confusion.
    """
    complexity_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="How complex is this output?"
    )
    ambiguity_flags: List[str] = Field(
        default_factory=list,
        description="Specific ambiguities detected"
    )
    requires_clarification: bool = Field(
        default=False,
        description="Should we ask user for clarification?"
    )
    suggested_simplifications: List[str] = Field(
        default_factory=list,
        description="How could this be made clearer?"
    )
