"""
Aegion API v1 - Session Endpoints.

Session management endpoints for the VS Code extension.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Optional, Dict, Any
from pydantic import BaseModel

from ...services.archon import get_archon, GovernanceError
from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
# Import Domain Model and Port
from ...domain.session import Session
from ...ports.database import SessionRepositoryPort


router = APIRouter(prefix="/sessions", tags=["sessions"])


# ========== Request/Response Models ==========

class StartSessionRequest(BaseModel):
    workspace_id: str
    context_hash: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str
    initial_context: Optional[Dict[str, Any]] = None


class CloseSessionRequest(BaseModel):
    distill: bool = True  # Whether to create artifact


class SessionStatusResponse(BaseModel):
    session_id: str
    owner_id: str
    status: str
    decision_count: int
    evidence_count: int
    exploration_stage: str




class ActiveSessionsResponse(BaseModel):
    count: int
    sessions: list


# ========== Dependency ==========

def get_session_repo(request: Request) -> SessionRepositoryPort:
    """Dependency to retrieve the injected session repository."""
    if not hasattr(request.app.state, "session_repo") or not request.app.state.session_repo:
        # Fallback or error? For safety, error.
        raise HTTPException(status_code=500, detail="Session repository not initialized")
    return request.app.state.session_repo


# ========== Endpoints ==========

from ...core.time import TimeAuthority

@router.get("/active", response_model=ActiveSessionsResponse)
async def get_active_sessions(
    user: AuthorityContext = Depends(get_current_user),
    repo: SessionRepositoryPort = Depends(get_session_repo)
):
    """
    Get count and list of active sessions for dashboard.
    """
    active_session = await repo.get_active_by_user(user.user_id)
    
    sessions = []
    if active_session:
        # Pydantic model supports dot access
        sessions.append({
            "session_id": active_session.session_id,
            "workspace_id": active_session.workspace_id,
            "owner_id": active_session.owner_id,
            "started_at": active_session.created_at
        })
        
    return ActiveSessionsResponse(
        count=len(sessions),
        sessions=sessions
    )

@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    user: AuthorityContext = Depends(get_current_user),
    repo: SessionRepositoryPort = Depends(get_session_repo)
):
    """
    Start a new session.
    
    Rules:
    - User can have only one active session
    - Previous active session is auto-closed
    """
    archon = get_archon()
    
    # Guard freeze mode
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # Check for existing active session and close it
    active_session = await repo.get_active_by_user(user.user_id)
    if active_session:
        await repo.close_session(active_session.session_id)
        logger.info(f"Auto-closed previous session {active_session.session_id} for user {user.user_id}")
    
    import uuid
    session_id = str(uuid.uuid4())
    
    new_session = Session(
        session_id=session_id,
        owner_id=user.user_id,
        workspace_id=request.workspace_id,
        status="active",
        context_hash=request.context_hash
    )
    
    await repo.create(new_session)

    # Register owner as participant via SessionOwnership
    try:
        from ...services.collaboration.session_ownership import SessionOwnership
        ownership = SessionOwnership()
        await ownership.register_participant(
            session_id=session_id,
            user_id=user.user_id,
            role="owner"
        )
    except Exception as e:
        logger.warning(f"Failed to register session ownership: {e}")
    
    # Hydrate session with governance context from knowledge graph
    from ...services.context_hydration import ContextHydrationService
    from ...services.graph_provider import get_shared_graph_service
    
    hydration = ContextHydrationService(graph_service=get_shared_graph_service())
    initial_context = await hydration.hydrate_session_context(
        workspace_id=request.workspace_id,
        limit=10
    )
    
    logger.audit(
        action="SESSION_STARTED",
        actor=user.user_id,
        target=session_id,
        justification="New session started",
        metadata={
            "workspace_id": request.workspace_id,
            "context_summary": initial_context.get("context_summary", ""),
        }
    )
    
    return StartSessionResponse(
        session_id=session_id,
        status="active",
        created_at=new_session.created_at.isoformat() if hasattr(new_session.created_at, 'isoformat') else str(new_session.created_at),
        initial_context=initial_context
    )


@router.get("/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user),
    repo: SessionRepositoryPort = Depends(get_session_repo)
):
    """Get session status."""
    session = await repo.get_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    from ...services.graph_provider import get_shared_graph_service
    graph_service = get_shared_graph_service()
    
    return SessionStatusResponse(
        session_id=session.session_id,
        owner_id=session.owner_id,
        status=session.status,
        decision_count=len(await graph_service.search_nodes(f"session:{session_id} type:decision", limit=100)),
        evidence_count=len(await graph_service.search_nodes(f"session:{session_id} type:evidence", limit=100)),
        exploration_stage=session.metadata.get("stage", "exploration")
    )


@router.post("/{session_id}/close")
async def close_session(
    session_id: str,
    request: CloseSessionRequest,
    user: AuthorityContext = Depends(get_current_user),
    repo: SessionRepositoryPort = Depends(get_session_repo)
):
    """
    Close a session.
    
    Optionally distills into an artifact.
    IRREVERSIBLE.
    """
    from ...core.security import Role
    archon = get_archon()
    
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    session = await repo.get_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.owner_id != user.user_id and user.role != Role.ADMIN:
         raise HTTPException(status_code=403, detail="Not authorized to close this session")

    # Close session
    await repo.close_session(session_id)
    
    distilled = False
    artifact_id = None
    if request.distill:
        try:
            from ...services.chronos.artifacts import ChronosArtifacts
            from ...adapters.local_artifact_log import LocalArtifactLog
            from ...contracts.decision_intent import (
                DecisionIntent, DecisionTier, ImpactLevel,
                ReversibilityLevel, ReasoningPhase,
            )
            from ...services.graph_provider import get_shared_graph_service
            _graph_svc = get_shared_graph_service()
            
            artifact_log = LocalArtifactLog()
            chronos = ChronosArtifacts(storage_port=artifact_log)
            
            # ---------- Fetch real proposals for this session ----------
            # BUG FIX: use session.workspace_id, NOT session_id
            proposal_nodes = await _graph_svc.list_proposals(
                workspace_id=session.workspace_id,
                limit=200
            )
            
            # ---------- Fetch real decisions for this workspace ----------
            decision_nodes = await _graph_svc.list_decisions(
                workspace_id=session.workspace_id,
                limit=200
            )
            
            # Convert graph nodes → DecisionIntent objects for distillation
            decisions = []
            for d in decision_nodes:
                props = d.properties
                decisions.append(DecisionIntent(
                    intent_id=d.node_id,
                    session_id=session_id,
                    title=props.get("title", f"Decision {d.node_id}"),
                    description=props.get("description", ""),
                    impact_level=ImpactLevel.LOCAL,
                    reversibility=ReversibilityLevel.EASY,
                    calculated_tier=DecisionTier.T1,
                    origin=props.get("origin", "human"),
                    proposed_by=props.get("approver_id", user.user_id),
                    reasoning=ReasoningPhase(
                        problem_framing=props.get("description", ""),
                        assumptions=[],
                        constraints=[],
                        boundaries=[],
                    ),
                ))
            
            # Build reasoning phases from proposals
            reasoning_phases = []
            for p in proposal_nodes:
                props = p.properties
                reasoning_phases.append({
                    "proposal_id": p.node_id,
                    "title": props.get("title", ""),
                    "tier": props.get("tier", "T1"),
                    "status": props.get("status", "pending"),
                    "created_by": props.get("created_by", ""),
                    "created_at": props.get("created_at", ""),
                })
            
            # ---------- Distill ----------
            session_end = TimeAuthority.now()
            artifact = await chronos.distill_session(
                session_id=session_id,
                owner_id=session.owner_id,
                workspace_id=session.workspace_id,
                session_start=session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else str(session.created_at),
                session_end=session_end,
                decisions=decisions,
                evidence_list=[],  # Evidence collected separately via snapshots
                reasoning_phases=reasoning_phases,
                metrics={
                    "proposal_count": len(proposal_nodes),
                    "decision_count": len(decision_nodes),
                },
            )
            artifact_id = artifact.artifact_id

            # Mark as distilled in repo
            await repo.distill_session(session_id)
            distilled = True
            
            # ---------- Create trace proposal linking artifact → session ----------
            await _graph_svc.record_proposal(
                proposal_id=f"trace-{artifact_id[:12]}",
                creator_id="chronos",
                title=f"Session Distillation: {session_id[:8]}",
                description=f"Immutable artifact {artifact_id} created from session {session_id}",
                tier="T1",
                status="distilled",
                workspace_id=session.workspace_id,
                metadata={
                    "artifact_id": artifact_id,
                    "source_session_id": session_id,
                    "decision_count": len(decisions),
                    "proposal_count": len(proposal_nodes),
                    "distilled_at": session_end,
                },
            )
            
        except Exception as e:
            logger.error(f"Failed to distill session {session_id}: {e}")
            # Don't fail the close operation, just log error
    
    logger.audit(
        action="SESSION_CLOSED",
        actor=user.user_id,
        target=session_id,
        justification="Session closed by user",
        metadata={
            "distill": request.distill,
            "artifact_id": artifact_id,
        }
    )
    
    return {
        "status": "closed",
        "distilled": distilled,
        "artifact_id": artifact_id,
    }
