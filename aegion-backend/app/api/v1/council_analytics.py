"""
Aegion API v1 - Council Analytics (Elevated).

Real analytics backed by Noesis CognitiveAnalytics engine:
  - Council debate analysis with real rubric scoring
  - Decision quality trends over time
  - Governance health score (composite metric)
  - Model performance ranking
  - Cognitive drift detection
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger

router = APIRouter(prefix="/council/analytics", tags=["council-analytics"])


class CouncilOpinion(BaseModel):
    agent_id: str
    verdict: str  # approve/reject
    confidence: float
    justification: str


class AnalyzeContextRequest(BaseModel):
    session_id: str
    proposal_id: Optional[str] = None
    opinions: List[CouncilOpinion]


class AgentDisagreement(BaseModel):
    agent_a_id: str
    agent_b_id: str
    disagreement_score: float  # 0.0 to 1.0
    topic: str


class AnalyticsResponse(BaseModel):
    heatmap: Dict[str, float]  # agent_id -> divergence_score
    disagreements: List[AgentDisagreement]
    justification_quality: Dict[str, float]  # agent_id -> quality_score
    consensus_strength: float


@router.post("/analyze", response_model=AnalyticsResponse)
async def analyze_council_debate(
    request: AnalyzeContextRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Analyze council opinions for disagreement patterns and quality.
    Uses real rubric scoring instead of naive heuristics.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # 1. Compute consensus strength
    approvals = [o for o in request.opinions if o.verdict == "approve"]
    rejects = [o for o in request.opinions if o.verdict == "reject"]

    total = len(request.opinions)
    if total == 0:
        return AnalyticsResponse(
            heatmap={},
            disagreements=[],
            justification_quality={},
            consensus_strength=0.0
        )

    majority_count = max(len(approvals), len(rejects))
    consensus_strength = majority_count / total

    # 2. Heatmap — divergence from consensus, weighted by confidence
    majority_verdict = "approve" if len(approvals) > len(rejects) else "reject"

    heatmap = {}
    justification_quality = {}

    for opinion in request.opinions:
        # Divergence: 0.0 if aligned, scaled by confidence if opposed
        divergence = 0.0
        if opinion.verdict != majority_verdict:
            divergence = opinion.confidence

        heatmap[opinion.agent_id] = divergence

        # Real rubric-backed quality scoring
        quality = await _score_justification(opinion.justification)
        justification_quality[opinion.agent_id] = quality

    # 3. Pairwise Disagreements with semantic topic detection
    disagreements = []
    for i in range(len(request.opinions)):
        for j in range(i + 1, len(request.opinions)):
            op_a = request.opinions[i]
            op_b = request.opinions[j]

            if op_a.verdict != op_b.verdict:
                score = (op_a.confidence + op_b.confidence) / 2
                topic = _detect_disagreement_topic(
                    op_a.justification, op_b.justification
                )
                disagreements.append(AgentDisagreement(
                    agent_a_id=op_a.agent_id,
                    agent_b_id=op_b.agent_id,
                    disagreement_score=score,
                    topic=topic,
                ))

    return AnalyticsResponse(
        heatmap=heatmap,
        disagreements=disagreements,
        justification_quality=justification_quality,
        consensus_strength=consensus_strength,
    )


@router.get("/health")
async def governance_health(
    workspace_id: str = Query(...),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Composite governance health score for a workspace.

    Returns A-F grade with component breakdown.
    """
    from ...services.noesis.analytics import get_cognitive_analytics
    analytics = get_cognitive_analytics()
    return await analytics.governance_health(workspace_id)


@router.get("/trends")
async def decision_trends(
    workspace_id: str = Query(...),
    days: int = Query(30, ge=7, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Decision quality trends over time (weekly buckets).
    """
    from ...services.noesis.analytics import get_cognitive_analytics
    analytics = get_cognitive_analytics()
    return await analytics.decision_quality_trends(workspace_id, days=days)


@router.get("/drift")
async def cognitive_drift(
    workspace_id: str = Query(...),
    days: int = Query(60, ge=14, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Detect cognitive drift — are decision patterns changing?
    """
    from ...services.noesis.analytics import get_cognitive_analytics
    analytics = get_cognitive_analytics()
    return await analytics.cognitive_drift_report(workspace_id, days=days)


@router.get("/consensus")
async def consensus_evolution(
    workspace_id: str = Query(...),
    days: int = Query(30, ge=7, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Track how consensus scores evolve across decisions.
    """
    from ...services.noesis.analytics import get_cognitive_analytics
    analytics = get_cognitive_analytics()
    return await analytics.consensus_evolution(workspace_id, days=days)


@router.get("/models")
async def model_ranking(
    workspace_id: str = Query(...),
    days: int = Query(30, ge=7, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Rank models by quality and cost-effectiveness.
    """
    from ...services.noesis.analytics import get_cognitive_analytics
    analytics = get_cognitive_analytics()
    return await analytics.model_performance_ranking(workspace_id, days=days)


# ──────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────

async def _score_justification(justification: str) -> float:
    """
    Score justification quality using the rubric engine.

    Falls back to heuristic scoring if rubric engine is unavailable.
    """
    try:
        from ...services.council_kernel.rubric import get_rubric_engine
        engine = get_rubric_engine()
        result = await engine.score(
            justification,
            rubric_name="general",
            context="Council agent justification for a governance decision",
        )
        return result["weighted_total"]
    except Exception:
        # Heuristic fallback
        score = 0.20
        text = justification.lower()
        if len(text) > 50:
            score += 0.25
        if "because" in text or "therefore" in text:
            score += 0.15
        if "risk" in text or "evidence" in text:
            score += 0.10
        if "policy" in text or "constraint" in text:
            score += 0.10
        if any(text.strip().startswith(p) for p in ("1.", "- ", "* ")):
            score += 0.10
        return min(1.0, score)


def _detect_disagreement_topic(justification_a: str, justification_b: str) -> str:
    """
    Detect what the disagreement is about using keyword analysis.
    """
    a_lower = justification_a.lower()
    b_lower = justification_b.lower()
    combined = a_lower + " " + b_lower

    topic_signals = {
        "Security Concern": ["security", "vulnerability", "cve", "injection", "xss"],
        "Performance Risk": ["performance", "latency", "throughput", "slow", "scalab"],
        "Cost Concern": ["cost", "budget", "expensive", "cheaper", "price"],
        "Architecture Dispute": ["architecture", "pattern", "design", "microservice", "monolith"],
        "Governance Policy": ["policy", "tier", "governance", "compliance", "regulation"],
        "Technical Feasibility": ["feasib", "complex", "impossible", "difficult", "technical debt"],
        "Data/Privacy": ["data", "privacy", "pii", "gdpr", "encrypt"],
    }

    for topic, keywords in topic_signals.items():
        if any(kw in combined for kw in keywords):
            return topic

    return "Verdict Mismatch"


# ──────────────────────────────────────────────────────────────────────────────
# Council Config API — Per-workspace ACK advanced feature toggles
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/config/{workspace_id}")
async def get_council_config(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Get the ACK advanced pipeline config for a workspace.

    Returns all feature toggles and budget caps.
    Used by the settings page to populate toggle controls.
    """
    try:
        from ...services.model_registry import get_model_registry
        registry = get_model_registry()
        config = registry.get_council_config(workspace_id)
        return {
            "workspace_id": workspace_id,
            "config": config.model_dump(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/config/{workspace_id}")
async def update_council_config(
    workspace_id: str,
    updates: Dict[str, Any],
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Partially update the ACK advanced pipeline config for a workspace.

    Send only the fields you want to change:
        {"mcts_enabled": true, "mcts_max_budget_usd": 0.25}

    Returns the full updated config.
    """
    try:
        from ...services.model_registry import get_model_registry, WorkspaceCouncilConfig
        registry = get_model_registry()

        # Validate the update keys
        valid_fields = set(WorkspaceCouncilConfig.model_fields.keys())
        invalid_keys = set(updates.keys()) - valid_fields
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid config fields: {invalid_keys}. Valid: {valid_fields}",
            )

        config = registry.update_council_config(workspace_id, updates)
        logger.info(f"Council config updated for {workspace_id}: {list(updates.keys())}")
        return {
            "workspace_id": workspace_id,
            "config": config.model_dump(),
            "updated_fields": list(updates.keys()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/config/{workspace_id}/reset")
async def reset_council_config(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Reset the ACK config to defaults for a workspace.

    All features go back to OFF (except constitution_enforcement).
    """
    try:
        from ...services.model_registry import get_model_registry, WorkspaceCouncilConfig
        registry = get_model_registry()
        config = registry.set_council_config(workspace_id, WorkspaceCouncilConfig())
        return {
            "workspace_id": workspace_id,
            "config": config.model_dump(),
            "message": "Config reset to defaults",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Phase 51: Council Analytics API
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/hallucination-rate/{workspace_id}")
async def get_hallucination_rate(
    workspace_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """Track the hallucination rate over the specified period."""
    try:
        from ...services.council_kernel.analytics import get_council_analytics
        return await get_council_analytics().hallucination_rate(workspace_id, days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/dissent-score/{workspace_id}")
async def get_dissent_score(
    workspace_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """Track whether the council preserves minority opinions."""
    try:
        from ...services.council_kernel.analytics import get_council_analytics
        return await get_council_analytics().dissent_preservation_score(workspace_id, days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/decision-regret/{workspace_id}")
async def get_decision_regret(
    workspace_id: str,
    days: int = Query(default=60, ge=1, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """Track decisions later reversed and correlate with original consensus."""
    try:
        from ...services.council_kernel.analytics import get_council_analytics
        return await get_council_analytics().decision_regret_analysis(workspace_id, days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/model-accuracy/{workspace_id}")
async def get_model_accuracy(
    workspace_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """Rank models by quality per task type (security, architecture, cost, etc.)."""
    try:
        from ...services.council_kernel.analytics import get_council_analytics
        return await get_council_analytics().model_accuracy_by_task(workspace_id, days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cost-efficiency/{workspace_id}")
async def get_cost_efficiency(
    workspace_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: AuthorityContext = Depends(get_current_user),
):
    """Track cascade savings, cache hit rate, and cost per query."""
    try:
        from ...services.council_kernel.analytics import get_council_analytics
        return await get_council_analytics().cost_efficiency(workspace_id, days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
