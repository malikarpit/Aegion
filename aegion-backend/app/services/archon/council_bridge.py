"""
Archon ↔ ACK Bridge — Phase 19: Tier-aware council routing.

Connects the existing ArchonGates governance system with the new
Council Kernel (ACK) for AI-powered proposal evaluation.

This sits between Archon (who decides authority) and ACK (who provides intelligence).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...core.logging import logger
from ..archon import get_archon
from ..archon.gates import GovernanceError


# Tier → Council routing map
_TIER_COUNCIL_POLICY = {
    0: {"authority": "auto", "requires_human": False, "council": None,
        "description": "Trivial (formatting, comments) — auto-approved"},
    1: {"authority": "auto", "requires_human": False, "council": "child",
        "description": "Low-impact (bug fixes, small features) — auto + child cascade"},
    2: {"authority": "council", "requires_human": True, "council": "parent",
        "description": "Moderate (new APIs, schema) — full council review + human approve"},
    3: {"authority": "human", "requires_human": True, "council": "parent",
        "description": "High (architecture, security, breaking) — T3 always needs human"},
}


async def evaluate_proposal_through_council(
    proposal_id: str,
    workspace_id: str,
    tier: int,
    title: str,
    description: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Route a proposal through ACK based on its governance tier.

    T0: Auto-approve (no LLM call)
    T1: FrugalGPT cascade (cheapest model, quick review)
    T2: Full parent council (debate + persona + peer review)
    T3: Full parent council + MUST have human sign-off

    Returns dict with: status, method, council_result (if applicable)
    """
    policy = _TIER_COUNCIL_POLICY.get(tier, _TIER_COUNCIL_POLICY[1])

    # T0 — auto-approve, no council needed
    if policy["authority"] == "auto" and policy["council"] is None:
        logger.info(f"Proposal {proposal_id} auto-approved (T0)")
        await _record_decision(workspace_id, proposal_id, tier, "approved", "auto", None)
        return {"status": "approved", "method": "auto", "tier": tier}

    # T1 — auto-approve + quick child council review for audit
    if policy["authority"] == "auto" and policy["council"] == "child":
        council_result = await _run_council(workspace_id, title, description, "child")
        logger.info(f"Proposal {proposal_id} auto-approved (T1) with council review")
        await _record_decision(workspace_id, proposal_id, tier, "approved", "auto+child", council_result)
        return {"status": "approved", "method": "auto_with_review", "tier": tier,
                "council_result": council_result}

    # T2/T3 — full parent council review
    council_result = await _run_council(workspace_id, title, description, "parent")

    if policy["requires_human"]:
        logger.info(f"Proposal {proposal_id} pending human review (T{tier})")
        await _store_pending_review(workspace_id, proposal_id, council_result)
        return {
            "status": "pending_human_review",
            "method": "council_review",
            "tier": tier,
            "council_result": council_result,
            "message": f"T{tier} requires human approval. Council recommendation attached.",
        }

    return {"status": "pending_review", "tier": tier, "council_result": council_result}


async def _run_council(
    workspace_id: str,
    title: str,
    description: str,
    council_type_str: str,
) -> Dict[str, Any]:
    """Run ACK council and return serializable result."""
    try:
        from ..council_kernel.engine import get_council_engine
        from ..council_kernel.types import CouncilType

        engine = get_council_engine()
        ct = CouncilType(council_type_str)
        result = await engine.consult(
            workspace_id=workspace_id,
            query=f"Review this proposal:\nTitle: {title}\nDescription: {description}",
            council_type=ct,
            context={"proposal_title": title},
        )
        return result.model_dump()
    except Exception as exc:
        logger.warning(f"Council review failed (non-fatal): {exc}")
        return {"error": str(exc), "synthesis": "Council unavailable — proceed with manual review."}


async def _record_decision(
    workspace_id: str,
    proposal_id: str,
    tier: int,
    outcome: str,
    method: str,
    council_result: Optional[Dict],
) -> None:
    """Record decision to Supabase (best-effort)."""
    try:
        from ...db.supabase_client import get_supabase_client
        get_supabase_client().table("decisions").insert({
            "workspace_id": workspace_id,
            "proposal_id": proposal_id,
            "tier": tier,
            "outcome": outcome,
            "decided_by": f"archon_{method}",
            "rationale": f"Auto-approved: T{tier} via {method}",
            "council_result": council_result,
        }).execute()
    except Exception as exc:
        logger.warning(f"Decision recording failed (non-fatal): {exc}")


async def _store_pending_review(
    workspace_id: str,
    proposal_id: str,
    council_result: Dict,
) -> None:
    """Store council result on proposal for human review."""
    try:
        from ...db.supabase_client import get_supabase_client
        get_supabase_client().table("proposals").update({
            "council_result": council_result,
            "status": "pending_review",
        }).eq("id", proposal_id).execute()
    except Exception as exc:
        logger.warning(f"Pending review storage failed (non-fatal): {exc}")
