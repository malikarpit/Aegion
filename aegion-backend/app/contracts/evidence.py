"""
Aegion Data Contracts - Evidence.

Doctrine: "Execution = Evidence, Not Authority."
All execution results are classified evidence, not decisions.

From Agent Authority Doctrine:
- ✅ Supporting: Evidence supports the proposal
- ❌ Contradictory: Evidence contradicts the proposal
- ⚪ Inconclusive: Evidence is ambiguous
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class EvidenceClassification(str, Enum):
    """How does this evidence relate to the proposal?"""
    SUPPORTING = "supporting"          # Confirms the proposal
    CONTRADICTORY = "contradictory"    # Refutes the proposal
    INCONCLUSIVE = "inconclusive"      # Neither confirms nor refutes
    UNCLASSIFIED = "unclassified"      # Not yet analyzed


class EvidenceType(str, Enum):
    """What kind of evidence is this?"""
    TEST_RESULT = "test_result"        # Unit/integration test output
    BUILD_LOG = "build_log"            # Build/compile output
    LINT_RESULT = "lint_result"        # Static analysis
    RUNTIME_LOG = "runtime_log"        # Runtime execution logs
    METRIC = "metric"                  # Performance/health metrics
    SNAPSHOT = "snapshot"              # State snapshot
    MANUAL_VERIFICATION = "manual"     # Human verification
    EXTERNAL_VALIDATION = "external"   # Third-party validation


class EvidenceSource(str, Enum):
    """Where did this evidence come from?"""
    AUTOMATED = "automated"      # From CI/CD or automated tests
    AI_EXECUTION = "ai_execution"  # AI ran the tests
    HUMAN = "human"              # Human performed verification
    SENTINEL = "sentinel"        # Sentinel monitoring


class Evidence(BaseModel):
    """
    Evidence attached to a proposal or decision.
    Immutable once created.
    """
    # Identity
    evidence_id: str = Field(..., description="Unique evidence ID")
    
    # Links
    proposal_id: str = Field(..., description="Proposal this evidence relates to")
    session_id: Optional[str] = Field(None, description="Session where evidence was generated")
    
    # Classification
    evidence_type: EvidenceType
    classification: EvidenceClassification = Field(
        default=EvidenceClassification.UNCLASSIFIED
    )
    
    # Source provenance  
    source: EvidenceSource
    source_id: str = Field(..., description="ID of source (test run ID, user ID, etc)")
    
    # Timing
    created_at: datetime
    collected_at: datetime = Field(..., description="When the evidence was actually produced")
    
    # Content (content-addressed)
    content_hash: str = Field(..., description="SHA-256 hash of evidence content")
    content_type: str = Field(default="application/json")
    storage_key: Optional[str] = Field(None, description="Key in blob storage")
    
    # Summary (for quick access without fetching full content)
    summary: str = Field(..., description="Human-readable summary")
    
    # Metrics (if applicable)
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted metrics (test count, coverage, etc)"
    )
    
    # Analysis
    analysis_notes: Optional[str] = Field(None, description="Why this classification?")
    confidence_in_classification: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="How confident is the classification?"
    )
    
    # Validity
    expires_at: Optional[datetime] = Field(None, description="When evidence becomes stale")
    is_stale: bool = Field(default=False, description="Has evidence expired?")
    
    # Phase 3: Snapshot Links (Verifiable Evidence)
    input_snapshot_ids: List[str] = Field(
        default_factory=list,
        description="IDs of input snapshots (captured source files)"
    )
    output_snapshot_ids: List[str] = Field(
        default_factory=list,
        description="IDs of output snapshots (captured results)"
    )
    environment_snapshot_id: Optional[str] = Field(
        None, description="ID of environment snapshot"
    )
    
    # Reproducibility
    is_reproducible: bool = Field(
        default=False,
        description="Can this evidence be reproduced from snapshots?"
    )
    manifest_hash: Optional[str] = Field(
        None, description="Hash of snapshot manifest for verification"
    )
    
    # EDG Integration
    dependency_node_id: Optional[str] = Field(
        None, description="ID of this evidence's node in the EDG"
    )
    
    model_config = ConfigDict(frozen=True)


class EvidenceChain(BaseModel):
    """
    A chain of evidence for a decision.
    Used for approval workflow.
    """
    proposal_id: str
    evidence_ids: List[str]
    
    # Aggregated classification
    supporting_count: int = 0
    contradictory_count: int = 0
    inconclusive_count: int = 0
    
    # Overall verdict
    overall_classification: EvidenceClassification = Field(
        default=EvidenceClassification.UNCLASSIFIED
    )
    
    # Requirements
    minimum_supporting_required: int = Field(
        default=1,
        description="Minimum supporting evidence needed"
    )
    
    @property
    def meets_requirements(self) -> bool:
        """Does this chain have enough supporting evidence?"""
        return (
            self.supporting_count >= self.minimum_supporting_required and
            self.contradictory_count == 0
        )
    
    @property
    def is_blocked(self) -> bool:
        """Is approval blocked by contradictory evidence?"""
        return self.contradictory_count > 0


class EvidenceGate(BaseModel):
    """
    Evidence gating configuration for tiers.
    
    From Security Enhancements:
    - Require proposal.evidenceIds.length > 0
    - Only accept evidence linked to that proposal
    - Evidence must be newer than proposal creation
    """
    tier: str
    
    # Requirements
    require_evidence: bool = Field(default=True)
    minimum_evidence_count: int = Field(default=1)
    require_supporting: bool = Field(default=True)
    block_on_contradictory: bool = Field(default=True)
    
    # Freshness
    evidence_max_age_hours: Optional[int] = Field(
        default=24,
        description="Evidence older than this is stale"
    )
    require_newer_than_proposal: bool = Field(default=True)
    
    # Types
    required_evidence_types: List[EvidenceType] = Field(
        default_factory=list,
        description="Specific evidence types required (empty = any)"
    )


def validate_evidence_for_proposal(
    evidence: Evidence,
    proposal_created_at: datetime,
    gate: EvidenceGate
) -> tuple[bool, Optional[str]]:
    """
    Validate evidence against gating rules.
    Returns (is_valid, error_message).
    """
    # Check proposal linkage
    # (Note: proposal_id is already set in Evidence, this validates timing)
    
    # Check freshness
    if gate.require_newer_than_proposal:
        if evidence.collected_at < proposal_created_at:
            return False, f"Evidence {evidence.evidence_id} predates proposal"
    
    # Check staleness
    if evidence.is_stale:
        return False, f"Evidence {evidence.evidence_id} is stale"
    
    # Check required types
    if gate.required_evidence_types:
        if evidence.evidence_type not in gate.required_evidence_types:
            return False, f"Evidence type {evidence.evidence_type} not in required types"
    
    # Check classification
    if gate.block_on_contradictory:
        if evidence.classification == EvidenceClassification.CONTRADICTORY:
            return False, f"Contradictory evidence {evidence.evidence_id} blocks approval"
    
    return True, None
