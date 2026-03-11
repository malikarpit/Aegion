"""
Aegion API v1 - Sentinel & Noesis Endpoints.

Phase 4: Advanced Epistemics
Risk analysis, drift detection, cognitive safety API.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ...services.sentinel import RiskEngine, DriftDetector
from ...services.noesis import GraphService, CognitiveSafetyService
from ...services.graph_provider import get_shared_graph_service
from ...contracts.risk import (
    RiskScore, RiskLevel, RiskHeatmap,
    DriftReport, CognitiveLoadAssessment, UncertaintyVisualization
)


# Shared graph service — all modules use the same graph instance
_risk_engine = RiskEngine()
_drift_detector = DriftDetector()
_graph_service = get_shared_graph_service()
_cognitive_service = CognitiveSafetyService()


# ========== Request/Response Models ==========

class RiskScoreRequest(BaseModel):
    """Request for risk score calculation."""
    workspace_id: str
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    lookback_hours: int = 24


class HeatmapRequest(BaseModel):
    """Request for risk heatmap generation."""
    workspace_id: str
    modules: List[Dict[str, Any]]


class DriftRequest(BaseModel):
    """Request for drift detection."""
    workspace_id: str
    current_period: List[Dict[str, Any]]
    baseline_period: List[Dict[str, Any]]
    observation_hours: int = 24


class CognitiveLoadRequest(BaseModel):
    """Request for cognitive load assessment."""
    user_id: str
    session_id: Optional[str] = None
    recent_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    hours_active: float = 0.0


class UncertaintyRequest(BaseModel):
    """Request for uncertainty visualization."""
    decision_id: str
    evidence_data: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_level: float = 0.95


class ImpactAnalysisRequest(BaseModel):
    """Request for impact analysis."""
    source_id: str
    max_depth: int = 5


class RecordDecisionRequest(BaseModel):
    """Request to record a decision in the knowledge graph."""
    decision_id: str
    proposal_id: str
    approver_id: str
    evidence_ids: List[str]
    workspace_id: str
    metadata: Optional[Dict[str, Any]] = None


# ========== Sentinel Router ==========

sentinel_router = APIRouter(prefix="/sentinel", tags=["sentinel"])


@sentinel_router.post("/risk-score", response_model=RiskScore)
async def calculate_risk_score(request: RiskScoreRequest):
    """Calculate risk score for a workspace."""
    score = await _risk_engine.calculate_risk_score(
        workspace_id=request.workspace_id,
        decisions=request.decisions,
        evidence=request.evidence,
        lookback_hours=request.lookback_hours
    )
    return score


@sentinel_router.post("/heatmap", response_model=RiskHeatmap)
async def generate_risk_heatmap(request: HeatmapRequest):
    """Generate risk heatmap by module."""
    heatmap = await _risk_engine.generate_heatmap(
        workspace_id=request.workspace_id,
        modules=request.modules
    )
    return heatmap


@sentinel_router.post("/drift", response_model=DriftReport)
async def detect_drift(request: DriftRequest):
    """Detect pattern drift between periods."""
    report = await _drift_detector.detect_drift(
        workspace_id=request.workspace_id,
        current_period=request.current_period,
        baseline_period=request.baseline_period,
        observation_hours=request.observation_hours
    )
    return report


@sentinel_router.get("/drift/{workspace_id}/status")
async def get_drift_status(workspace_id: str):
    """Get quick drift status for a workspace."""
    report = await _drift_detector.detect_drift(
        workspace_id=workspace_id,
        current_period=[],
        baseline_period=[],
        observation_hours=24
    )
    
    status = "nominal"
    if report.requires_attention:
        status = "degraded" if report.critical_signals > 0 else "warning"
        
    return {
        "workspace_id": workspace_id,
        "status": status,
        "last_check": report.generated_at.isoformat(),
        "signals_count": report.total_signals
    }


@sentinel_router.get("/alerts")
async def get_sentinel_alerts(workspace_id: str = "default"):
    """
    Get active sentinel alerts for dashboard.

    Queries drift detector and risk engine in real-time and converts
    threshold breaches into alert objects.
    """
    alerts = []

    # ---- Drift-based alerts ----
    try:
        drift_report: DriftReport = await _drift_detector.detect_drift(
            workspace_id=workspace_id,
            current_period=[],
            baseline_period=[],
            observation_hours=24,
        )
        for signal in drift_report.signals:
            # DriftSignal uses severity (RiskLevel enum)
            # RiskLevel strings: critical, high, medium, low, minimal
            is_critical = signal.severity in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            
            if is_critical:
                alerts.append({
                    "alert_id": f"drift-{signal.drift_type}",
                    "type": signal.drift_type,
                    "severity": "critical" if signal.severity == RiskLevel.CRITICAL else "warning",
                    "message": signal.description,
                    "source": "drift_detector",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False
                })
    except Exception:
        pass  # Degrade gracefully

    # ---- Risk-based alerts ----
    try:
        risk_score: RiskScore = await _risk_engine.calculate_risk_score(
            workspace_id=workspace_id,
            lookback_hours=24,
        )
        if risk_score.overall_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            alerts.append({
                "alert_id": f"risk-{workspace_id}",
                "type": "high_risk_score",
                "severity": "critical" if risk_score.overall_level == RiskLevel.CRITICAL else "warning",
                "message": f"Workspace risk score {risk_score.overall_score:.1f}/100 ({risk_score.overall_level.value})",
                "source": "risk_engine",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "acknowledged": False
            })
    except Exception:
        pass  # Degrade gracefully

    return {"count": len(alerts), "alerts": alerts}


# ========== Noesis Router ==========

noesis_router = APIRouter(prefix="/noesis", tags=["noesis"])


@noesis_router.post("/cognitive-load", response_model=CognitiveLoadAssessment)
async def assess_cognitive_load(request: CognitiveLoadRequest):
    """Assess cognitive load for a user."""
    assessment = await _cognitive_service.assess_cognitive_load(
        user_id=request.user_id,
        session_id=request.session_id,
        recent_decisions=request.recent_decisions,
        hours_active=request.hours_active
    )
    return assessment


@noesis_router.get("/cognitive-load/{user_id}/should-break")
async def should_suggest_break(user_id: str):
    """Quick check if user should take a break."""
    should_break, reason = await _cognitive_service.should_suggest_break(user_id)
    return {
        "user_id": user_id,
        "should_break": should_break,
        "reason": reason
    }


@noesis_router.post("/cognitive-load/{user_id}/break")
async def record_user_break(user_id: str):
    """Record that user took a break."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=str(e))

    await _cognitive_service.record_break(user_id)
    return {"status": "break_recorded", "user_id": user_id}


@noesis_router.post("/uncertainty", response_model=UncertaintyVisualization)
async def get_uncertainty_visualization(request: UncertaintyRequest):
    """Get uncertainty visualization data for a decision."""
    viz = await _cognitive_service.get_uncertainty_visualization(
        decision_id=request.decision_id,
        evidence_data=request.evidence_data,
        confidence_level=request.confidence_level
    )
    return viz


@noesis_router.post("/impact-analysis")
async def analyze_impact(request: ImpactAnalysisRequest):
    """Analyze impact of a source change."""
    impact = await _graph_service.analyze_impact(
        source_id=request.source_id,
        max_depth=request.max_depth
    )
    return impact


@noesis_router.post("/decisions/record")
async def record_decision(request: RecordDecisionRequest):
    """Record a decision in the knowledge graph."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=str(e))

    node = await _graph_service.record_decision(
        decision_id=request.decision_id,
        proposal_id=request.proposal_id,
        approver_id=request.approver_id,
        evidence_ids=request.evidence_ids,
        workspace_id=request.workspace_id,
        metadata=request.metadata
    )
    return {
        "status": "recorded",
        "node_id": node.node_id,
        "node_type": node.node_type.value
    }


@noesis_router.get("/decisions/{decision_id}/provenance")
async def get_decision_provenance(decision_id: str, depth: int = 3):
    """Get provenance chain for a decision."""
    subgraph = await _graph_service.get_decision_provenance(
        decision_id=decision_id,
        depth=depth
    )
    return {
        "decision_id": decision_id,
        "node_count": len(subgraph.nodes),
        "edge_count": len(subgraph.edges),
        "nodes": [
            {"id": n.node_id, "type": n.node_type.value}
            for n in subgraph.nodes
        ],
        "edges": [
            {"from": e.source_id, "to": e.target_id, "type": e.edge_type.value}
            for e in subgraph.edges
        ]
    }


@noesis_router.get("/workspace/{workspace_id}/topology")
async def get_workspace_topology(workspace_id: str):
    """Get topology summary for a workspace."""
    topology = await _graph_service.get_workspace_topology(workspace_id)
    return topology
