from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, model_validator, ConfigDict
import uuid

class UncertaintyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class CouncilRole(str, Enum):
    """Roles AI agents can take in the council."""
    PROPOSER = "proposer"
    CRITIC = "critic"
    ADVOCATE = "advocate"
    SYNTHESIZER = "synthesizer"
    AUDITOR = "auditor"
    SENTINEL = "sentinel"

class CouncilVote(str, Enum):
    """Council voting options."""
    SUPPORT = "support"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"
    DEFER = "defer"

class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    SKIPPED = "SKIPPED"

class HealthStatus(str, Enum):
    """System health status."""
    HEALTHY = "HEALTHY"    # Fully operational
    DEGRADED = "DEGRADED"  # Partial failures (e.g. LLM timeouts)
    FAILED = "FAILED"      # Critical failures (e.g. Auth down)

class CouncilHealth(BaseModel):
    """
    Snapshot of the Council's operational health.
    """
    status: HealthStatus = Field(default=HealthStatus.HEALTHY)
    last_check: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)

class CouncilStageResult(BaseModel):
    """
    Base contract for any Council stage output.
    Ensures consistent metadata and status tracking.
    """
    model_config = ConfigDict(frozen=True)

    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stage_name: str
    status: StageStatus = Field(default=StageStatus.COMPLETED)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Core reasoning fields
    claim: str = Field(..., description="The core assertion or finding of this stage.")
    reasoning_summary: str = Field(..., description="Concise summary of the reasoning path.")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="0.0 to 1.0 confidence score.")
    uncertainty_level: UncertaintyLevel = Field(..., description="Categorical uncertainty.")
    
    # Operational fields
    blocking: bool = Field(False, description="If True, this result should block the proposal.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_blocking_policy(self) -> 'CouncilStageResult':
        """
        Enforce safety policy: High uncertainty must assume blocking unless explicitly justified.
        """
        if self.uncertainty_level in (UncertaintyLevel.HIGH, UncertaintyLevel.CRITICAL):
            # For Sentinel/Parent, high uncertainty usually implies blocking.
            # We enforce this strictly for SentinelAssessment, but as a general warning here.
            pass
        return self

class ChildDebateResult(CouncilStageResult):
    """
    Output from a specific Child Agent (e.g., Security Specialist, Perf Specialist).
    """
    agent_role: CouncilRole = Field(..., description="Role of the agent.")
    vote: CouncilVote = Field(..., description="Vote: SUPPORT/OPPOSE/ABSTAIN/DEFER")
    citations: List[str] = Field(default_factory=list, description="File paths or context IDs referenced.")

class ParentVerdict(CouncilStageResult):
    """
    Synthesis output from the Parent/Speaker.
    Aggregates child results into a final recommendation.
    """
    recommended_action: CouncilVote = Field(..., description="Proposed action: SUPPORT (Approve), OPPOSE (Reject/Changes), ABSTAIN")
    child_consensus: str = Field(..., description="Summary of child agent agreement/disagreement.")

class SentinelAssessment(CouncilStageResult):
    """
    Safety gate output from the Sentinel.
    Must be strictly blocking on high risk.
    """
    risk_category: str = Field(..., description="Primary risk category (e.g., 'data_loss', 'auth_bypass').")
    
    @model_validator(mode='after')
    def enforce_safety_gate(self) -> 'SentinelAssessment':
        """
        Policy: Critical/High uncertainty in Sentinel MUST block.
        """
        if self.uncertainty_level in (UncertaintyLevel.HIGH, UncertaintyLevel.CRITICAL):
            if not self.blocking:
                raise ValueError(f"Sentinel cannot return non-blocking result with {self.uncertainty_level} uncertainty.")
        
        # Policy: Low confidence (< 0.7) usually implies blocking or at least degraded mode
        if self.confidence_score < 0.7 and not self.blocking:
             # We might allow this but perform a warning logged elsewhere.
             # For strict Phase 3, let's enforce blocking on very low confidence.
             if self.confidence_score < 0.4:
                 raise ValueError("Sentinel confidence too low (< 0.4) to permit non-blocking result.")
                 
        return self

class CouncilMember(BaseModel):
    """An AI agent participating in the council."""
    member_id: str = Field(..., description="Unique member ID")
    role: CouncilRole
    model: str = Field(..., description="LLM model identifier")
    specialization: Optional[str] = Field(None, description="Domain expertise")
    weight: float = Field(default=1.0, ge=0.1, le=2.0, description="Vote weight")
    
    model_config = ConfigDict(frozen=True)

class CouncilOpinion(BaseModel):
    """Opinion from a council member on a proposal."""
    opinion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    member_id: str
    proposal_id: str
    
    # Vote
    vote: CouncilVote
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in opinion")
    
    # Reasoning
    analysis: str = Field(..., description="Analysis of the proposal")
    concerns: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    
    # Provenance
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tokens_consumed: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(frozen=True)

class CouncilSession(BaseModel):
    """A council session for evaluating a proposal."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str
    workspace_id: str
    
    # Members
    member_ids: List[str] = Field(default_factory=list)
    
    # Opinions
    opinions: List[CouncilOpinion] = Field(default_factory=list)
    
    # Aggregated result
    consensus: Optional[CouncilVote] = None
    consensus_confidence: float = 0.0
    synthesis: Optional[str] = None  # Synthesized summary of opinions
    
    # Status
    status: str = Field(default="pending")  # pending, active, completed, cancelled
    
    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # Metrics
    total_tokens: int = 0
    
    # Dissent Tracking
    dissent_count: int = 0
    dissenting_member_ids: List[str] = Field(default_factory=list)

