"""
Aegion Risk & Cognitive Safety Contracts.

Phase 4: Advanced Epistemics
Data contracts for Sentinel analysis and cognitive safety.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ========== Risk Contracts ==========

class RiskLevel(str, Enum):
    """Risk severity levels."""
    CRITICAL = "critical"   # Immediate action required
    HIGH = "high"           # Needs attention soon
    MEDIUM = "medium"       # Should be monitored
    LOW = "low"             # Acceptable risk
    MINIMAL = "minimal"     # Negligible risk


class RiskCategory(str, Enum):
    """Categories of risk."""
    STALENESS = "staleness"           # Stale evidence/decisions
    VELOCITY = "velocity"             # Decision rate too high
    AUTHORITY = "authority"           # Authority violations
    EVIDENCE_GAP = "evidence_gap"     # Missing evidence
    COGNITIVE_LOAD = "cognitive_load" # Decision fatigue
    PATTERN_DRIFT = "pattern_drift"   # Unusual patterns


class RiskScore(BaseModel):
    """Computed risk score for a workspace or entity."""
    entity_id: str = Field(..., description="Workspace or user ID")
    entity_type: str = Field(..., description="workspace|user|module")
    
    # Overall score
    overall_score: float = Field(..., ge=0.0, le=100.0)
    overall_level: RiskLevel
    
    # Component scores
    component_scores: Dict[RiskCategory, float] = Field(default_factory=dict)
    
    # Factors
    contributing_factors: List[str] = Field(default_factory=list)
    
    # Timing
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime = Field(default_factory=datetime.utcnow)
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class RiskHeatmapCell(BaseModel):
    """A cell in the risk heatmap."""
    module_id: str
    module_name: str
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_level: RiskLevel
    stale_evidence_count: int = 0
    pending_decisions_count: int = 0
    recent_changes_count: int = 0

    model_config = ConfigDict(frozen=True)


class RiskHeatmap(BaseModel):
    """Risk heatmap for a workspace."""
    workspace_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    cells: List[RiskHeatmapCell] = Field(default_factory=list)
    
    # Aggregates
    max_risk_score: float = 0.0
    avg_risk_score: float = 0.0
    critical_modules: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


# ========== Drift Detection Contracts ==========

class DriftType(str, Enum):
    """Types of pattern drift."""
    VELOCITY_INCREASE = "velocity_increase"   # Decisions getting faster
    VELOCITY_DECREASE = "velocity_decrease"   # Decisions slowing down
    EVIDENCE_DECLINE = "evidence_decline"     # Less evidence per decision
    TIER_ESCALATION = "tier_escalation"       # More high-tier decisions
    REVIEW_BYPASS = "review_bypass"           # Fewer reviews happening


class DriftSignal(BaseModel):
    """A detected drift signal."""
    signal_id: str = Field(..., description="Unique signal identifier")
    drift_type: DriftType
    severity: RiskLevel
    
    # Measurement
    baseline_value: float
    current_value: float
    deviation_percent: float
    
    # Context
    workspace_id: str
    module_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Timing
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    observation_window_hours: int = 24
    
    # Details
    description: str
    recommendation: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class DriftReport(BaseModel):
    """Consolidated drift report."""
    workspace_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    signals: List[DriftSignal] = Field(default_factory=list)
    
    # Summary
    total_signals: int = 0
    critical_signals: int = 0
    high_signals: int = 0
    
    # Status
    requires_attention: bool = False
    attention_reason: Optional[str] = None

    model_config = ConfigDict(frozen=True)


# ========== Cognitive Safety Contracts ==========

class CognitiveLoadLevel(str, Enum):
    """Cognitive load levels."""
    OPTIMAL = "optimal"         # Good for decision-making
    ELEVATED = "elevated"       # Approaching limits
    HIGH = "high"               # Should take a break
    OVERLOADED = "overloaded"   # Break required


class CognitiveLoadFactors(BaseModel):
    """Factors contributing to cognitive load."""
    decisions_per_hour: float = 0.0
    avg_decision_complexity: float = 0.0
    hours_since_break: float = 0.0
    error_rate_recent: float = 0.0
    context_switches: int = 0
    high_tier_decisions: int = 0

    model_config = ConfigDict(frozen=True)


class CognitiveLoadAssessment(BaseModel):
    """Assessment of user's cognitive load."""
    user_id: str
    session_id: Optional[str] = None
    
    # Assessment
    load_level: CognitiveLoadLevel
    load_score: float = Field(ge=0.0, le=100.0)
    
    # Factors
    factors: CognitiveLoadFactors
    
    # Recommendations
    should_break: bool = False
    break_reason: Optional[str] = None
    recommended_break_minutes: int = 0
    
    # Timing
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(frozen=True)


class UncertaintyVisualization(BaseModel):
    """Structured data for uncertainty UI display."""
    decision_id: str
    
    # Uncertainty breakdown
    overall_uncertainty: float = Field(ge=0.0, le=1.0)
    uncertainty_components: Dict[str, float] = Field(default_factory=dict)
    
    # Confidence intervals
    confidence_lower: float = 0.0
    confidence_upper: float = 1.0
    confidence_level: float = 0.95
    
    # Evidence quality
    evidence_strength: float = Field(ge=0.0, le=1.0)
    evidence_count: int = 0
    contradictory_evidence_count: int = 0
    
    # Visualization hints
    display_type: str = "gauge"  # gauge, bar, confidence_interval
    color_code: str = "green"    # green, yellow, orange, red
    
    # Explanation
    uncertainty_explanation: Optional[str] = None

    model_config = ConfigDict(frozen=True)
