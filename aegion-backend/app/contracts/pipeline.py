"""
Aegion Contracts - Decision Pipeline.

Phase 3: The Cognitive Plane
Hypothesis → Evaluation → Decision flow models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class HypothesisStatus(str, Enum):
    """Status of a hypothesis in the pipeline."""
    PROPOSED = "proposed"
    TESTING = "testing"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"
    ABANDONED = "abandoned"


class EvaluationOutcome(str, Enum):
    """Outcome of an evaluation step."""
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


class Hypothesis(BaseModel):
    """
    A hypothesis to be tested in the decision pipeline.
    """
    hypothesis_id: str
    statement: str  # "If X, then Y because Z"
    created_by: str
    created_at: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    
    # Context
    proposal_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Evidence links
    supporting_evidence: List[str] = Field(default_factory=list)
    counter_evidence: List[str] = Field(default_factory=list)
    
    # Outcome
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    conclusion: Optional[str] = None


class EvaluationStep(BaseModel):
    """
    A single evaluation step in the pipeline.
    """
    step_id: str
    step_type: str  # "unit_test", "integration_test", "manual_review", "ai_review"
    description: str
    outcome: EvaluationOutcome = EvaluationOutcome.SKIPPED
    
    # Results
    evidence_collected: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    executed_at: Optional[str] = None
    executed_by: Optional[str] = None


class DecisionPipeline(BaseModel):
    """
    Full decision pipeline: Hypothesis → Evaluations → Decision.
    """
    pipeline_id: str
    title: str
    description: str
    
    # Workflow
    hypothesis: Hypothesis
    evaluation_steps: List[EvaluationStep] = Field(default_factory=list)
    
    # State
    current_step: int = 0
    started_at: str
    completed_at: Optional[str] = None
    
    # Outcome
    final_decision: Optional[str] = None  # proposal_id if approved
    outcome_summary: Optional[str] = None
    
    # Metadata
    created_by: str
    workspace_id: str


class PipelineTemplate(BaseModel):
    """
    Reusable pipeline template for common decision types.
    """
    template_id: str
    name: str
    description: str
    step_definitions: List[Dict[str, Any]]  # Step type + description templates
    applicable_tiers: List[str] = Field(default_factory=lambda: ["T1", "T2", "T3"])
