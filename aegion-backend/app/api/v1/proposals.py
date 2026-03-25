"""
Aegion API v1 - Proposal Endpoints.

Proposal and decision management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, model_validator
import uuid

from ...services.archon import get_archon, GovernanceError
from ...contracts.decision_intent import (
    DecisionTier, ImpactLevel, ReversibilityLevel, ReasoningPhase
)
from ...contracts.uncertainty_level import UncertaintyDeclaration
from ...contracts.evidence import (
    Evidence, EvidenceClassification, EvidenceSource, EvidenceType
)
from ...models.decision import VisibilityLabel
from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...adapters.inprocess.event_bus import get_event_bus
from ...ports.events import Event, EventCategory, EventTypes
from datetime import datetime, timezone


router = APIRouter(prefix="/proposals", tags=["proposals"])


# ========== Request/Response Models ==========

class CreateProposalRequest(BaseModel):
    session_id: str
    title: str
    description: str
    impact_level: ImpactLevel
    reversibility: ReversibilityLevel
    affected_modules: List[str] = []
    affected_files: List[str] = []
    reasoning: ReasoningPhase
    uncertainty: Optional[UncertaintyDeclaration] = None
    metadata: Optional[dict] = None  # Origin info, e.g. {"origin": "ai_child"}

    @model_validator(mode='after')
    def validate_uncertainty_for_high_tiers(self):
        """Enforce uncertainty declaration for T2+ impact proposals."""
        from ...contracts.decision_intent import classify_decision_tier
        tier = classify_decision_tier(self.impact_level, self.reversibility)
        if tier in (DecisionTier.T2, DecisionTier.T3) and self.uncertainty is None:
            raise ValueError(
                f"Uncertainty declaration is required for {tier.value} proposals "
                f"(impact={self.impact_level}, reversibility={self.reversibility})"
            )
        return self


class ProposalResponse(BaseModel):
    proposal_id: str
    tier: DecisionTier
    status: str
    title: str
    quorum_required: int = 1
    approvals_count: int = 0
    tier_reasons: List[str] = []
    uncertainty: Optional[UncertaintyDeclaration] = None
    visibility_label: str


class ApproveProposalRequest(BaseModel):
    evidence_ids: List[str]
    justification: str


# ========== Endpoints ==========

@router.get("/session/{session_id}")
async def list_proposals_by_session(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    List all proposals created during a session.
    Used by the distillation pipeline to gather real proposal data.
    """
    from .analytics import _graph_service

    # Proposals store session_id in the workspace_id field (legacy naming)
    nodes = await _graph_service.list_proposals(
        workspace_id=session_id,
        limit=100
    )

    results = []
    for node in nodes:
        results.append({
            "proposal_id": node.node_id,
            "title": node.properties.get("title", ""),
            "tier": node.properties.get("tier", "T1"),
            "status": node.properties.get("status", "pending"),
            "created_by": node.properties.get("created_by", ""),
            "created_at": node.properties.get("created_at", ""),
            "description": node.properties.get("description", ""),
        })

    return {"session_id": session_id, "count": len(results), "proposals": results}


@router.post("/", response_model=ProposalResponse)
async def create_proposal(
    request: CreateProposalRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Create a new proposal and record it in the Knowledge Graph.
    """
    archon = get_archon()
    # Import GraphService (Noesis)
    from .analytics import _graph_service
    
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # Calculate tier with full reasoning
    tier_info = archon.explain_tier(
        request.impact_level,
        request.reversibility,
        request.affected_modules
    )
    tier = DecisionTier(tier_info["tier"])
    
    import uuid
    proposal_id = str(uuid.uuid4())
    status_str = "pending"
    
    # Derive visibility from proposal origin instead of hardcoding
    origin = (request.metadata or {}).get("origin", "human")
    if origin in ("ai_child", "ai_parent", "ai_council"):
        visibility = VisibilityLabel.AI_SUGGESTION.value
    elif (request.metadata or {}).get("governed"):
        visibility = VisibilityLabel.GOVERNED.value
    else:
        visibility = VisibilityLabel.HUMAN_AUTHORED.value
    
    # Persist to Knowledge Graph
    await _graph_service.record_proposal(
        proposal_id=proposal_id,
        creator_id=user.user_id,
        title=request.title,
        description=request.description,
        tier=tier.value,
        status=status_str,
        workspace_id=request.session_id,
        metadata={
            "impact_level": request.impact_level,
            "reversibility": request.reversibility,
            "uncertainty": request.uncertainty.model_dump() if request.uncertainty else None,
            "tier_reasons": tier_info["reasons"]
        }
    )
    
    logger.audit(
        action="DECISION_PROPOSED",
        actor=user.user_id,
        target=proposal_id,
        justification=f"Proposal created: {request.title}",
        metadata={"tier": tier.value, "session_id": request.session_id}
    )

    # Emit governance event for real-time subscribers
    await get_event_bus().publish(Event(
        event_id=proposal_id,
        category=EventCategory.DECISION,
        event_type=EventTypes.DECISION_PROPOSED,
        timestamp=datetime.now(timezone.utc),
        source="proposals.create",
        payload={"title": request.title, "tier": tier.value, "status": status_str},
        workspace_id=request.session_id,
        actor_id=user.user_id,
    ))
    
    return ProposalResponse(
        proposal_id=proposal_id,
        tier=tier,
        status=status_str,
        title=request.title,
        quorum_required=tier_info["quorum"],
        approvals_count=0,
        tier_reasons=tier_info["reasons"],
        uncertainty=request.uncertainty,
        visibility_label=visibility
    )


@router.post("/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    request: ApproveProposalRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Approve a proposal.
    Enforces governance gates including Segregation of Duties.
    """
    archon = get_archon()
    from .analytics import _graph_service
    
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # Fetch proposal
    proposal_node = await _graph_service.get_proposal(proposal_id)
    if not proposal_node:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    proposal_creator_id = proposal_node.properties.get("created_by")
    proposal_created_at_str = proposal_node.properties.get("created_at")
    from datetime import datetime, timezone
    proposal_created_at = datetime.fromisoformat(proposal_created_at_str) if proposal_created_at_str else datetime.now(timezone.utc)
    tier_str = proposal_node.properties.get("tier", "T1")
    tier = DecisionTier(tier_str)
    
    # Fetch real evidence linked to this proposal from knowledge graph
    evidence_nodes = await _graph_service.get_evidence_for_proposal(proposal_id)
    evidence_list = [
        Evidence(
            evidence_id=node.properties.get("evidence_id", node.node_id),
            proposal_id=proposal_id,
            evidence_type=EvidenceType(node.properties.get("evidence_type", "manual")),
            classification=EvidenceClassification(node.properties.get("classification", "unclassified")),
            source=EvidenceSource(node.properties.get("source", "human")),
            source_id=node.properties.get("source_id", node.properties.get("submitted_by", "unknown")),
            created_at=datetime.fromisoformat(node.properties.get("created_at", datetime.now(timezone.utc).isoformat())),
            collected_at=datetime.fromisoformat(node.properties.get("collected_at", datetime.now(timezone.utc).isoformat())),
            content_hash=node.properties.get("content_hash", ""),
            summary=node.properties.get("summary", node.properties.get("analysis_notes", "")),
            metrics=node.properties.get("metrics", {}),
            analysis_notes=node.properties.get("analysis_notes"),
        )
        for node in evidence_nodes
    ]
    
    try:
        # Retrieve stored uncertainty from proposal metadata
        stored_uncertainty = None
        uncertainty_data = proposal_node.properties.get("uncertainty")
        if uncertainty_data:
            try:
                stored_uncertainty = UncertaintyDeclaration.model_validate(uncertainty_data)
            except Exception as e:
                logger.warning(f"Malformed uncertainty data on proposal {proposal_id}: {e}", exc_info=False)

        audit_event = await archon.approve_proposal(
            proposal_id=proposal_id,
            proposal_status=proposal_node.properties.get("status", "pending"),
            approver=user,
            tier=tier,
            evidence_list=evidence_list,
            proposal_created_at=proposal_created_at,
            uncertainty=stored_uncertainty,
            proposal_creator_id=proposal_creator_id
        )
    except GovernanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    decision_id = f"dec-{proposal_id}"
    
    # Re-approval guard: reject if decision already exists for this proposal
    existing_decision = await _graph_service.get_node(decision_id)
    if existing_decision:
        raise HTTPException(
            status_code=409,
            detail=f"Decision '{decision_id}' already exists for proposal '{proposal_id}'. "
            "A proposal can only be approved once."
        )
    
    # Persist Decision — use ONLY graph-validated evidence (never trust client input)
    # Security: request.evidence_ids is client-provided and could contain
    # evidence IDs that were never linked to this proposal. We use the 
    # graph-fetched evidence_nodes (validated above) as the single source of truth.
    validated_evidence_ids = [
        n.properties.get("evidence_id", n.node_id) for n in evidence_nodes
    ]
    
    workspace_id = proposal_node.properties.get("workspace_id", "default")

    await _graph_service.record_decision(
        decision_id=decision_id,
        proposal_id=proposal_id,
        approver_id=user.user_id,
        evidence_ids=validated_evidence_ids,
        workspace_id=workspace_id,
        metadata={
            "tier": tier.value,
            "justification": request.justification,
            "client_evidence_ids": request.evidence_ids,  # Audit trail only
        }
    )
    
    # Update Proposal Status
    await _graph_service.update_proposal_status(proposal_id, "approved")

    # Emit governance event for real-time subscribers
    await get_event_bus().publish(Event(
        event_id=decision_id,
        category=EventCategory.DECISION,
        event_type=EventTypes.DECISION_APPROVED,
        timestamp=datetime.now(timezone.utc),
        source="proposals.approve",
        payload={"proposal_id": proposal_id, "decision_id": decision_id},
        workspace_id=workspace_id,
        actor_id=user.user_id,
    ))

    return {
        "status": "approved",
        "decision_id": decision_id
    }


@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    reason: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Reject a proposal."""
    archon = get_archon()
    from .analytics import _graph_service
    
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # Fetch proposal to get context
    proposal_node = await _graph_service.get_proposal(proposal_id)
    if not proposal_node:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    workspace_id = proposal_node.properties.get("workspace_id", "default")
    
    import uuid
    decision_id = f"dec-{uuid.uuid4().hex[:12]}"
    
    # Record rejection in graph
    await _graph_service.record_rejection(
        decision_id=decision_id,
        proposal_id=proposal_id,
        rejector_id=user.user_id,
        workspace_id=workspace_id,
        reason=reason
    )
    
    logger.audit(
        action="DECISION_REJECTED",
        actor=user.user_id,
        target=proposal_id,
        justification=reason,
        metadata={"decision_id": decision_id}
    )

    # Emit governance event for real-time subscribers
    await get_event_bus().publish(Event(
        event_id=decision_id,
        category=EventCategory.DECISION,
        event_type=EventTypes.DECISION_REJECTED,
        timestamp=datetime.now(timezone.utc),
        source="proposals.reject",
        payload={"proposal_id": proposal_id, "decision_id": decision_id, "reason": reason},
        workspace_id=workspace_id,
        actor_id=user.user_id,
    ))

    return {"status": "rejected", "decision_id": decision_id}


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get proposal details."""
    from .analytics import _graph_service
    
    node = await _graph_service.get_proposal(proposal_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    # Map graph node to response model
    tier_str = node.properties.get("tier", "T1")
    try:
        tier = DecisionTier(tier_str)
    except ValueError:
        tier = DecisionTier.T1
        
    return ProposalResponse(
        proposal_id=node.node_id,
        tier=tier,
        status=node.properties.get("status", "pending"),
        title=node.properties.get("title", "Untitled Proposal"),
        visibility_label=node.properties.get("origin", "human_authored")
    )


# ========== Multi-User Review Endpoints ==========

class SubmitReviewRequest(BaseModel):
    verdict: str  # "approve" | "request_changes" | "comment" | "reject"
    comments: str
    inline_comments: List[dict] = []


class ReviewResponse(BaseModel):
    review_id: str
    proposal_id: str
    reviewer_id: str
    verdict: str
    created_at: str


@router.post("/{proposal_id}/review", response_model=ReviewResponse)
async def submit_review(
    proposal_id: str,
    request: SubmitReviewRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Submit a review on a proposal.
    
    Reviews are immutable once submitted.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    import uuid
    from datetime import datetime, timezone
    
    review_id = f"rev-{uuid.uuid4().hex[:12]}"
    
    # Persist review to knowledge graph (immutable once created)
    from ...ports.knowledge_graph import GraphNodeType, GraphEdgeType
    await _graph_service.graph.add_node(
        node_type=GraphNodeType.REVIEW,
        node_id=review_id,
        properties={
            "proposal_id": proposal_id,
            "reviewer_id": user.user_id,
            "verdict": request.verdict,
            "comment": getattr(request, "comment", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    await _graph_service.graph.add_edge(
        source_id=review_id,
        target_id=proposal_id,
        edge_type=GraphEdgeType.REVIEWED_BY,
    )
    
    logger.audit(
        action="REVIEW_SUBMITTED",
        actor=user.user_id,
        target=proposal_id,
        justification=f"Review: {request.verdict}",
        metadata={"review_id": review_id}
    )
    
    return ReviewResponse(
        review_id=review_id,
        proposal_id=proposal_id,
        reviewer_id=user.user_id,
        verdict=request.verdict,
        created_at=datetime.now(timezone.utc).isoformat()
    )


class CastVoteRequest(BaseModel):
    approve: bool
    justification: Optional[str] = None


class VoteResponse(BaseModel):
    vote_id: str
    proposal_id: str
    voter_id: str
    approved: bool


@router.post("/{proposal_id}/vote", response_model=VoteResponse)
async def cast_vote(
    proposal_id: str,
    request: CastVoteRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Cast approval vote on a proposal.
    
    INVARIANT: Votes are immutable once cast.
    """
    import uuid
    
    # Authority gate: enforce tier-based approval rights
    archon = get_archon()
    
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
        
    # Fetch proposal tier from graph if available
    from .analytics import _graph_service
    node = await _graph_service.get_proposal(proposal_id)
    proposal_tier = DecisionTier.T1
    if node:
        tier_str = node.properties.get("tier", "T1")
        try:
            proposal_tier = DecisionTier(tier_str)
        except ValueError:
            logger.debug(f"Unknown proposal tier {tier_str!r}; defaulting to T0")
    
    # Check authority for non-trivial tiers
    if proposal_tier in (DecisionTier.T2, DecisionTier.T3) and not user.can_approve_t2:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient authority to vote on {proposal_tier.value} proposal"
        )
    
    vote_id = f"vote-{uuid.uuid4().hex[:12]}"
    
    # 1. Record Vote in Graph
    from ...ports.knowledge_graph import GraphEdgeType
    edge_type = GraphEdgeType.APPROVED_BY if request.approve else GraphEdgeType.REJECTED_BY
    
    # Check if already voted (idempotency/single vote per user)
    existing_edges = await _graph_service.get_edges(source_id=proposal_id, target_id=user.user_id)
    has_voted = any(e.edge_type in [GraphEdgeType.APPROVED_BY, GraphEdgeType.REJECTED_BY] for e in existing_edges)
    
    if has_voted:
        # For MVP, we reject duplicate votes. Alternatively we could update the vote.
        pass # Allow update? Or block? Doctrine says "Votes are immutable".
        # If strict immutability, we block.
        # But previous implementation allowed it? No, it was a stub.
        # Let's BLOCK duplicate voting for now to enforce immutability strictly.
        raise HTTPException(status_code=400, detail="User has already voted on this proposal")

    await _graph_service.graph.add_edge(
        source_id=proposal_id,
        target_id=user.user_id,
        edge_type=edge_type,
        properties={
            "justification": request.justification or "",
            "vote_id": vote_id,
            "voted_at": datetime.now(timezone.utc).isoformat()
        }
    )
    
    logger.audit(
        action="VOTE_CAST",
        actor=user.user_id,
        target=proposal_id,
        justification=request.justification or "No justification",
        metadata={"approved": request.approve}
    )
    
    # 2. Check Quorum & Enforce Decision (Policy-Driven)
    if request.approve:
        # Count approvals from graph
        approvals = await _graph_service.get_edges(source_id=proposal_id, edge_type=GraphEdgeType.APPROVED_BY)
        approver_ids = set(e.target_id for e in approvals if e.edge_type == GraphEdgeType.APPROVED_BY)
        
        # Policy-driven quorum from Archon
        required_votes = archon.get_quorum(proposal_tier)
        
        if len(approver_ids) >= required_votes:
            # Quorum met — formally approve via Archon gates
            proposal_creator_id = node.properties.get("created_by") if node else None
            proposal_created_at_str = node.properties.get("created_at") if node else None
            proposal_created_at = (
                datetime.fromisoformat(proposal_created_at_str)
                if proposal_created_at_str
                else datetime.now(timezone.utc)
            )
            
            # Fetch real evidence for quorum-triggered approval
            evidence_nodes = await _graph_service.get_evidence_for_proposal(proposal_id)
            evidence_list = [
                Evidence(
                    evidence_id=en.properties.get("evidence_id", en.node_id),
                    proposal_id=proposal_id,
                    evidence_type=EvidenceType(en.properties.get("evidence_type", "manual")),
                    classification=EvidenceClassification(en.properties.get("classification", "unclassified")),
                    source=EvidenceSource(en.properties.get("source", "human")),
                    source_id=en.properties.get("source_id", en.properties.get("submitted_by", "unknown")),
                    created_at=datetime.fromisoformat(en.properties.get("created_at", datetime.now(timezone.utc).isoformat())),
                    collected_at=datetime.fromisoformat(en.properties.get("collected_at", datetime.now(timezone.utc).isoformat())),
                    content_hash=en.properties.get("content_hash", ""),
                    summary=en.properties.get("summary", en.properties.get("analysis_notes", "")),
                    metrics=en.properties.get("metrics", {}),
                    analysis_notes=en.properties.get("analysis_notes"),
                )
                for en in evidence_nodes
            ]
            
            try:
                await archon.approve_proposal(
                    proposal_id=proposal_id,
                    proposal_status=node.properties.get("status", "pending") if node else "pending",
                    approver=user,
                    tier=proposal_tier,
                    evidence_list=evidence_list,
                    proposal_created_at=proposal_created_at,
                    proposal_creator_id=proposal_creator_id
                )
            except GovernanceError as e:
                # Quorum met but governance gate failed (e.g. self-approval on T2+)
                # Vote was already recorded — log but don't auto-approve
                logger.warning(f"Quorum met for {proposal_id} but governance blocked: {e}")
                return VoteResponse(
                    vote_id=vote_id,
                    proposal_id=proposal_id,
                    voter_id=user.user_id,
                    approved=request.approve
                )
            
            # Update proposal status
            await _graph_service.update_node_properties(proposal_id, {
                "status": "approved",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approved_by": user.user_id
            })
            
            # Create Decision Record
            decision_id = f"dec-{proposal_id}"
            evidence_edges = await _graph_service.get_edges(source_id=proposal_id, edge_type=GraphEdgeType.SUPPORTS)
            evidence_ids = [e.target_id for e in evidence_edges] if evidence_edges else []
            await _graph_service.record_decision(
                decision_id=decision_id,
                proposal_id=proposal_id,
                approver_id=user.user_id,
                evidence_ids=evidence_ids,
                workspace_id=node.properties.get("workspace_id", "default") if node else "default",
                metadata={"tier": proposal_tier.value, "auto_approved": True, "quorum": required_votes}
            )
            
            logger.info(f"Proposal {proposal_id} auto-approved: quorum {len(approver_ids)}/{required_votes} met.")

    return VoteResponse(
        vote_id=vote_id,
        proposal_id=proposal_id,
        voter_id=user.user_id,
        approved=request.approve
    )


class ActivityItem(BaseModel):
    type: str
    actor_id: str
    description: str
    created_at: str


@router.get("/{proposal_id}/activity", response_model=List[ActivityItem])
async def get_proposal_activity(
    proposal_id: str,
    user: AuthorityContext = Depends(get_current_user)
):
    """Get activity log for a proposal."""
    from .analytics import _graph_service
    from datetime import datetime, timezone
    
    # Query graph for nodes related to this proposal
    nodes = await _graph_service.search_nodes(proposal_id, limit=10)
    
    if not nodes:
        return [ActivityItem(
            type="created",
            actor_id="system",
            description="Proposal created",
            created_at=datetime.now(timezone.utc).isoformat()
        )]
    
    return [
        ActivityItem(
            type=n.properties.get("event_type", "update"),
            actor_id=n.properties.get("actor_id", "unknown"),
            description=n.properties.get("title", n.node_id),
            created_at=n.properties.get("created_at", datetime.now(timezone.utc).isoformat())
        )
        for n in nodes
    ]
