"""
Aegion API v1 - Decision Endpoints.

Implements Doctrine S-2: "To 'change' a decision, create a new decision that supersedes it."
Decisions are immutable. Changes are managed via supersession chains.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Optional, List
from pydantic import BaseModel

from ...services.archon import get_archon, GovernanceError
from ...services.chronos.artifacts import ChronosSupersession, DecisionLineage
from ...contracts.decision_intent import DecisionIntent
from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger

router = APIRouter(prefix="/decisions", tags=["decisions"])

class SupersedeDecisionRequest(BaseModel):
    new_proposal_id: str
    justification: str

class SupersedeResponse(BaseModel):
    original_decision_id: str
    new_decision_id: str
    chain_position: int
    superseded_at: str


class DecisionSummary(BaseModel):
    decision_id: str
    title: str
    tier: str
    status: str
    approved_at: str


@router.get("/", response_model=list)
async def list_decisions(
    limit: int = 10,
    user: AuthorityContext = Depends(get_current_user),
    x_workspace_id: Optional[str] = Header(None) # Optional header if not in middleware
):
    """
    List recent decisions for dashboard.
    """
    from ...services.noesis.graph_service import GraphService
    # Todo: dependency injection
    from .analytics import _graph_service
    
    workspace_id = x_workspace_id or "default"
    
    nodes = await _graph_service.list_decisions(workspace_id, limit)
    
    results = []
    for node in nodes:
        results.append({
            "decision_id": node.node_id,
            "title": node.properties.get("title", f"Decision {node.node_id}"), # Title usually on proposal, might need proposal lookup or duplicate title
            "tier": node.properties.get("tier", "T1"), # Tier usually on proposal/metadata
            "status": node.properties.get("verdict", "approved"),
            "approved_at": node.properties.get("decided_at", node.created_at.isoformat())
        })
        
    return results

@router.post("/{decision_id}/supersede", response_model=SupersedeResponse)
async def supersede_decision(
    decision_id: str,
    request: SupersedeDecisionRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Supersede an existing decision with a new proposal.
    
    This is the ONLY way to "edit" a decision in Aegion.
    """
    archon = get_archon()
    from ...services.chronos.artifacts import ChronosSupersession
    chronos = ChronosSupersession()
    
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
        
    # Verify new_proposal_id exists and is APPROVED
    from .analytics import _graph_service
    proposal_node = await _graph_service.get_proposal(request.new_proposal_id)
    if not proposal_node:
        raise HTTPException(status_code=404, detail=f"Proposal {request.new_proposal_id} not found")
    if proposal_node.properties.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Proposal must be APPROVED before superseding a decision")
    
    # Verify original decision exists and is NOT already superseded
    original_node = await _graph_service.graph.get_node(decision_id)
    if not original_node:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    if original_node.properties.get("status") == "superseded":
        superseded_by = original_node.properties.get("superseded_by", "unknown")
        raise HTTPException(
            status_code=400,
            detail=f"Decision {decision_id} is already superseded by {superseded_by}. Cannot re-supersede."
        )
    
    # Build DecisionIntent from the approved proposal
    from ...contracts.decision_intent import DecisionIntent, DecisionTier, ImpactLevel, ReversibilityLevel, ReasoningPhase
    from datetime import datetime, timezone
    
    props = proposal_node.properties
    new_decision_intent = DecisionIntent(
        intent_id=f"dec-{request.new_proposal_id}",
        session_id=props.get("session_id", "unknown"),
        title=props.get("title", "Superseding Decision"),
        description=request.justification,
        impact_level=ImpactLevel(props.get("impact_level", "local")),
        reversibility=ReversibilityLevel(props.get("reversibility", "easy")),
        calculated_tier=DecisionTier(props.get("tier", "T1")),
        origin=props.get("origin", "human"),
        proposed_by=user.user_id,
        proposed_at=datetime.now(timezone.utc),
        reasoning=ReasoningPhase(
            problem_framing=props.get("problem_framing", "Update decision"),
            assumptions=props.get("assumptions", []),
            constraints=props.get("constraints", []),
            boundaries=props.get("boundaries", [])
        )
    )
    
    # Execute supersession
    new_decision, lineage = await chronos.supersede_decision(
        original_id=decision_id,
        new_decision=new_decision_intent,
        actor_id=user.user_id,
        reason=request.justification
    )
    
    return SupersedeResponse(
        original_decision_id=decision_id,
        new_decision_id=new_decision.intent_id,
        chain_position=lineage.chain_position,
        superseded_at=lineage.created_at
    )

@router.get("/graph", response_model=dict)
async def get_decision_graph(
    x_workspace_id: str = Header("default"),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get the full ADR graph for visualization.
    """
    from .analytics import _graph_service
    return await _graph_service.get_adr_graph(x_workspace_id)

@router.get("/{decision_id}/lineage", response_model=List[DecisionLineage])
async def get_decision_lineage(
    decision_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get the full history of a decision chain."""
    chronos = ChronosSupersession()
    return await chronos.get_lineage_chain(decision_id)
