"""
Aegion API v1 - Admin Dashboard.

Feature: Admin layer with env controls, usage analytics, and policy dashboards.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from ...core.security import AuthorityContext, Role, get_current_user
from ...core.logging import logger

router = APIRouter(prefix="/admin", tags=["admin"])


# ========== Models ==========

class UsageStats(BaseModel):
    total_users: int
    active_users_24h: int
    total_requests_24h: int
    total_tokens_24h: int
    cost_estimate_usd: float

class PolicyStats(BaseModel):
    proposals_created: int
    proposals_approved: int
    proposals_rejected: int
    approval_rate: float
    avg_time_to_approve_ms: float
    tier_distribution: Dict[str, int]

class EnvConfig(BaseModel):
    debug_mode: bool
    log_level: str
    feature_flags: Dict[str, bool]


# ========== Endpoints ==========

@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    user: AuthorityContext = Depends(get_current_user),
):
    """Get system-wide usage statistics from live metrics."""
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ...middleware.observability import get_metrics, MetricNames
    metrics = get_metrics()

    total_requests = int(metrics._counters.get(MetricNames.REQUEST_TOTAL, 0))
    total_tokens = int(metrics._counters.get(MetricNames.AI_TOKENS_USED, 0))
    active_sessions = int(metrics._gauges.get(MetricNames.ACTIVE_SESSIONS, 0))
    # Cost heuristic: $0.002 per 1K tokens (blended GPT-4/Claude rate)
    cost_estimate = round(total_tokens / 1000 * 0.002, 2)

    return UsageStats(
        total_users=active_sessions,
        active_users_24h=active_sessions,
        total_requests_24h=total_requests,
        total_tokens_24h=total_tokens,
        cost_estimate_usd=cost_estimate,
    )


@router.get("/policy-dashboard", response_model=PolicyStats)
async def get_policy_dashboard(
    user: AuthorityContext = Depends(get_current_user),
):
    """Get governance policy enforcement statistics from live metrics."""
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ...middleware.observability import get_metrics, MetricNames
    metrics = get_metrics()

    created = int(metrics._counters.get(MetricNames.PROPOSALS_CREATED, 0))
    approved = int(metrics._counters.get(MetricNames.PROPOSALS_APPROVED, 0))
    rejected = int(metrics._counters.get(MetricNames.PROPOSALS_REJECTED, 0))
    rate = round(approved / max(created, 1), 3)

    # Approval latency: average of the histogram (if recorded)
    latency_key = "governance_approval_latency_ms"
    latency_obs = metrics._histograms.get(latency_key, [])
    avg_latency = round(sum(latency_obs) / max(len(latency_obs), 1), 1)

    return PolicyStats(
        proposals_created=created,
        proposals_approved=approved,
        proposals_rejected=rejected,
        approval_rate=rate,
        avg_time_to_approve_ms=avg_latency,
        tier_distribution={"T0": 0, "T1": 0, "T2": 0, "T3": 0},
    )


@router.get("/env", response_model=EnvConfig)
async def get_env_config(
    user: AuthorityContext = Depends(get_current_user),
):
    """Get current environment configuration/flags from live settings."""
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ...core.config import settings as live_settings

    return EnvConfig(
        debug_mode=getattr(live_settings, 'debug_mode', False),
        log_level=getattr(live_settings, 'log_level', 'INFO'),
        feature_flags={
            "enable_gpt4": getattr(live_settings, 'enable_gpt4', False),
            "enable_claude": getattr(live_settings, 'enable_claude', False),
            "enable_auto_approve": getattr(live_settings, 'enable_auto_approve', False),
        }
    )


@router.post("/env", response_model=EnvConfig)
async def update_env_config(
    config: EnvConfig,
    user: AuthorityContext = Depends(get_current_user),
):
    """Update environment configuration (feature flags)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    logger.audit(
        action="ENV_CONFIG_UPDATE",
        actor=user.user_id,
        target="system_config",
        justification="Admin config update"
    )
    
    return config
