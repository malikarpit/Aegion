"""
Aegion API v1 - Council Endpoints.

AI Council orchestration endpoints.
Replaces mock diffs with dynamic `difflib` generation.
All invocations now route through CouncilService (single governed path).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import difflib
import uuid

from ...services.archon import get_archon, GovernanceError
from ...services.council.council_service import CouncilService
from ...contracts.decision_intent import (
    DecisionIntent, ImpactLevel, ReversibilityLevel, DecisionTier, ReasoningPhase
)
from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/council", tags=["council"])


# ========== Request/Response Models ==========

class InvokeCouncilRequest(BaseModel):
    session_id: str
    prompt: str
    context: dict = {}
    require_parent: bool = False
    file_path: Optional[str] = None  # Optional: diff against actual file content


class CouncilResponse(BaseModel):
    consensus: bool
    recommendation: str
    diff: Optional[str] = None
    child_confidence: float
    sentinel_blocking: bool


# ========== Helpers ==========

def get_council_service(request: Request) -> CouncilService:
    """Dependency to get CouncilService from app state."""
    return request.app.state.council_service


def _build_decision_intent(request: InvokeCouncilRequest, user: AuthorityContext) -> DecisionIntent:
    """Map API request to the governed DecisionIntent contract."""
    return DecisionIntent(
        intent_id=f"intent-{uuid.uuid4().hex[:8]}",
        session_id=request.session_id,
        title=request.prompt[:120],
        description=request.prompt,
        impact_level=ImpactLevel.LOCAL,
        reversibility=ReversibilityLevel.EASY,
        calculated_tier=DecisionTier.T1 if request.require_parent else DecisionTier.T0,
        reasoning=ReasoningPhase(
            problem_framing=request.prompt,
            assumptions=list(request.context.get("assumptions", [])),
            constraints=list(request.context.get("constraints", [])),
        ),
        affected_modules=list(request.context.get("affected_modules", [])),
        origin="human",
        proposed_by=user.user_id,
        proposed_at=datetime.now(timezone.utc),
        status="pending",
        metadata=request.context,
    )


def _generate_diff(recommendation: str, file_path: Optional[str]) -> Optional[str]:
    """Extract code block and generate unified diff against actual file."""
    if "```" not in recommendation:
        return None
    try:
        code_block = recommendation.split("```")[1]
        if code_block.startswith("python"):
            code_block = code_block[6:]
        code_block = code_block.strip()

        original_content = ""
        if file_path:
            import os
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    original_content = f.read()

        diff_lines = difflib.unified_diff(
            original_content.splitlines(),
            code_block.splitlines(),
            fromfile=f'a/{file_path or "generated.py"}',
            tofile=f'b/{file_path or "generated.py"}',
            lineterm=''
        )
        diff = "\n".join(diff_lines)
        if not diff:
            diff = (
                f"--- /dev/null\n+++ b/src/generated.py\n"
                f"@@ -0,0 +1,{len(code_block.splitlines())} @@\n"
                + "\n".join(f"+{line}" for line in code_block.splitlines())
            )
        return diff
    except Exception as e:
        logger.warning(f"Failed to generate diff: {e}")
        return None


# ========== Endpoints ==========

@router.post("/invoke", response_model=CouncilResponse)
async def invoke_council(
    request: InvokeCouncilRequest,
    user: AuthorityContext = Depends(get_current_user),
    service: CouncilService = Depends(get_council_service),
):
    """
    Invoke the AI Council for a governed debate.

    Routes through CouncilService for governance, sentinel checks, and consensus.
    Deterministic fail-safe: if the service is degraded or times out, sentinel blocks.
    """
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    logger.info("Council invoked", session_id=request.session_id, user_id=user.user_id)

    proposal = _build_decision_intent(request, user)

    # Deterministic fail-safe: timeout or degraded → sentinel blocks
    sentinel_blocking = False
    consensus = False
    recommendation = ""
    child_confidence = 0.0

    try:
        session = await service.convene_session(
            proposal=proposal,
            workspace_id=getattr(user, 'workspace_id', 'default'),
        )

        consensus = session.consensus_reached if hasattr(session, 'consensus_reached') else bool(session.verdict == "supported" if hasattr(session, 'verdict') else False)
        recommendation = session.summary if hasattr(session, 'summary') else str(session)
        child_confidence = session.confidence if hasattr(session, 'confidence') else 0.5
        sentinel_blocking = session.sentinel_blocked if hasattr(session, 'sentinel_blocked') else False

    except Exception as e:
        logger.error(f"Council session failed (fail-safe: sentinel blocks): {e}")
        sentinel_blocking = True
        recommendation = f"Council session failed: {e}. Sentinel engaged (fail-safe)."

    diff = _generate_diff(recommendation, request.file_path)

    return CouncilResponse(
        consensus=consensus,
        recommendation=recommendation,
        diff=diff,
        child_confidence=child_confidence,
        sentinel_blocking=sentinel_blocking,
    )


@router.post("/stream")
async def stream_council_response(
    request: InvokeCouncilRequest,
    user: AuthorityContext = Depends(get_current_user),
    service: CouncilService = Depends(get_council_service),
):
    """
    Phase 97: Stream the AI Council debate as Server-Sent Events.

    SSE Event types:
      - debate.started   — Session created, debate beginning
      - debate.round     — New debate round starting (for multi-round T2/T3)
      - debate.opinion   — Individual council member opinion received
      - debate.consensus — Consensus calculated
      - debate.complete  — Full session result with synthesis
      - debate.error     — Error during debate
    """
    import json as _json

    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    proposal = _build_decision_intent(request, user)
    workspace_id = getattr(user, 'workspace_id', 'default')

    async def sse_generate():
        try:
            # Emit debate start
            yield _sse_event("debate.started", {
                "proposal_id": proposal.intent_id,
                "tier": proposal.calculated_tier.value,
                "title": proposal.title[:120],
                "num_rounds": service.ROUNDS_BY_TIER.get(
                    proposal.calculated_tier, 1
                ),
            })

            # Run the full debate
            session = await service.convene_session(
                proposal=proposal,
                workspace_id=workspace_id,
            )

            # Emit each opinion individually so the UI can render them progressively
            for i, opinion in enumerate(session.opinions):
                yield _sse_event("debate.opinion", {
                    "index": i,
                    "member_id": opinion.member_id,
                    "vote": opinion.vote.value if hasattr(opinion.vote, 'value') else str(opinion.vote),
                    "confidence": opinion.confidence,
                    "analysis": opinion.analysis[:500],
                    "stage": opinion.metadata.get("stage", "child_debate"),
                })

            # Emit consensus
            yield _sse_event("debate.consensus", {
                "consensus": session.consensus.value if session.consensus else "none",
                "confidence": session.consensus_confidence,
                "dissent_count": session.dissent_count,
            })

            # Emit complete result
            yield _sse_event("debate.complete", {
                "session_id": session.session_id,
                "status": session.status,
                "synthesis": session.synthesis or "",
                "total_tokens": session.total_tokens,
            })

        except GovernanceError as e:
            yield _sse_event("debate.error", {
                "error": str(e),
                "type": "governance",
                "sentinel_blocked": True,
            })
        except Exception as e:
            logger.error(f"Council SSE stream failed: {e}")
            yield _sse_event("debate.error", {
                "error": str(e),
                "type": "internal",
                "sentinel_blocked": False,
            })

    return StreamingResponse(
        sse_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def _sse_event(event_type: str, data: dict) -> str:
    """Format a dict as a standard SSE event string."""
    import json as _json
    return f"event: {event_type}\ndata: {_json.dumps(data)}\n\n"


@router.get("/policy")
async def get_governance_policy(
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get the currently active governance policy.
    """
    from ...services.archon.registry import PolicyRegistry
    policy = PolicyRegistry.get_active()
    return policy


# ========== Escalation Endpoint (Phase 3) ==========

class EscalateRequest(BaseModel):
    proposal_id: str
    proposal_title: str
    proposal_tier: str
    child_reasoning: str
    child_confidence: float
    affected_modules: List[str] = []
    context: dict = {}


@router.post("/escalate")
async def escalate_to_parent(
    request: EscalateRequest,
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Escalate a proposal to the Parent AI Council.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from ...services.council.escalation import get_escalation_service
    
    service = get_escalation_service()
    
    result = await service.escalate_to_parent(
        proposal_id=request.proposal_id,
        proposal_title=request.proposal_title,
        proposal_tier=request.proposal_tier,
        child_reasoning=request.child_reasoning,
        child_confidence=request.child_confidence,
        affected_modules=request.affected_modules,
        context=request.context
    )
    
    logger.info(
        "Proposal escalated",
        proposal_id=request.proposal_id,
        verdict=result.verdict,
        requires_human=result.requires_human
    )
    
    return result




@router.get("/sessions/{session_id}")
async def get_council_session(
    session_id: str,
    service: CouncilService = Depends(get_council_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get full details of a council session (for audit/provenance).
    """
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/sessions/{session_id}/transcript")
async def get_session_transcript(
    session_id: str,
    service: CouncilService = Depends(get_council_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get human-readable transcript of a session.
    """
    transcript = await service.get_transcript(session_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Session not found")
    return transcript

@router.get("/proposals/{proposal_id}/sessions")
async def get_proposal_sessions(
    proposal_id: str,
    service: CouncilService = Depends(get_council_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get all council sessions associated with a proposal.
    """
    return await service.get_sessions_for_proposal(proposal_id)

@router.get("/proposals/{proposal_id}/governance-status")
async def get_proposal_governance_status(
    proposal_id: str,
    service: CouncilService = Depends(get_council_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Check if a proposal has passed Council Governance (Safety Gate).
    Returns {"passed": true/false}.
    """
    passed = await service.verify_governance(proposal_id)
    return {"passed": passed, "proposal_id": proposal_id}


# ══════════════════════════════════════════════════════════════════════════════
# Phase 18: ACK (Aegion Council Kernel) endpoints
# ══════════════════════════════════════════════════════════════════════════════

class ACKConsultRequest(BaseModel):
    query: str
    council_type: str = "child"   # child | parent | sentinel | distillation
    context: dict = {}
    gather_evidence: bool = False
    compress_prompt: bool = False


class ACKDebateRequest(BaseModel):
    proposition: str
    context: dict = {}


class ACKPeerReviewRequest(BaseModel):
    query: str
    context: dict = {}


class ACKPersonaRequest(BaseModel):
    proposition: str
    persona_keys: List[str] = ["security_auditor", "cost_analyst", "devils_advocate"]


def _ack_engine(request: Request = None):
    """Get the ACK engine — prefer app.state (properly initialized at startup)."""
    if request and hasattr(request.app.state, 'council_engine') and request.app.state.council_engine:
        return request.app.state.council_engine
    from ...services.council_kernel.engine import get_council_engine
    return get_council_engine()


def _ack_supabase():
    from ...db.supabase_client import get_supabase_client
    return get_supabase_client()


@router.post("/consult", summary="ACK — Full multi-model council consultation")
async def ack_consult(
    req: ACKConsultRequest,
    request: Request = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Route a query through the ACK pipeline.

    - child:        FrugalGPT cascade + semantic cache (cheapest)
    - parent:       Debate + Persona + Peer Review
    - sentinel:     Rubric-scored safety check
    - distillation: Single-model session summarisation
    """
    from ...services.council_kernel.types import CouncilType

    workspace_id = getattr(user, "workspace_id", "global")

    try:
        council_type = CouncilType(req.council_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid council_type: {req.council_type}")

    context = dict(req.context)
    query = req.query

    if req.gather_evidence:
        from ...services.council_kernel.evidence import get_evidence_manager
        ev = get_evidence_manager()
        evidence = await ev.gather_evidence(workspace_id, query)
        context["evidence"] = ev.format_for_prompt(evidence)

    if req.compress_prompt:
        from ...services.council_kernel.compressor import get_compressor
        compressed = await get_compressor().compress(query)
        query = compressed["text"]

    engine = _ack_engine(request)
    result = await engine.consult(workspace_id, query, council_type, context)

    # Persist result for audit trail (best-effort)
    try:
        from ...adapters.postgres.council_store import get_council_result_store
        store = get_council_result_store()
        await store.save_result(workspace_id, result.model_dump())
    except Exception as exc:
        logger.debug(f"Council result persistence skipped: {exc}")

    return result.model_dump()


@router.post("/debate", summary="ACK — Anti-sycophancy structured debate")
async def ack_debate(
    req: ACKDebateRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Multi-round debate with anti-groupthink enforcement and Fresh Eyes Validation."""
    engine = _ack_engine()
    if not engine.model_router.providers:
        raise HTTPException(status_code=503, detail="No LLM providers configured")

    from ...services.council_kernel.debate import DebateEngine
    from ...services.council_kernel.model_router import _MODEL_MAP

    debate_engine = DebateEngine(engine.model_router)
    model_slots = [(p, _MODEL_MAP.get(p, "default")) for p in list(engine.model_router.providers.keys())[:4]]
    return await debate_engine.debate(req.proposition, model_slots, req.context)


@router.post("/peer-review", summary="ACK — Adversarial peer review")
async def ack_peer_review(
    req: ACKPeerReviewRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """3-stage peer review pipeline for hallucination reduction."""
    engine = _ack_engine()
    if not engine.model_router.providers:
        raise HTTPException(status_code=503, detail="No LLM providers configured")

    from ...services.council_kernel.peer_review import PeerReviewEngine
    from ...services.council_kernel.model_router import _MODEL_MAP

    pr_engine = PeerReviewEngine(engine.model_router)
    model_slots = [(p, _MODEL_MAP.get(p, "default")) for p in list(engine.model_router.providers.keys())[:4]]

    if len(model_slots) < 2:
        raise HTTPException(status_code=400, detail="Peer review requires at least 2 providers")

    result = await pr_engine.run(req.query, model_slots, req.context)
    return result.model_dump()


@router.post("/persona", summary="ACK — Persona-driven expert debate")
async def ack_persona(
    req: ACKPersonaRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Assign expert personas (security, cost, devil's advocate...) to available models."""
    engine = _ack_engine()
    if not engine.model_router.providers:
        raise HTTPException(status_code=503, detail="No LLM providers configured")

    from ...services.council_kernel.persona import get_persona_engine, PERSONAS
    from ...services.council_kernel.model_router import _MODEL_MAP

    invalid = [k for k in req.persona_keys if k not in PERSONAS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown personas: {invalid}")

    pe = get_persona_engine()
    model_slots = [(p, _MODEL_MAP.get(p, "default")) for p in list(engine.model_router.providers.keys())]
    return await pe.debate_with_personas(req.proposition, req.persona_keys, model_slots, engine.model_router)


@router.get("/cost/summary", summary="ACK — Workspace LLM cost summary")
async def ack_cost_summary(user: AuthorityContext = Depends(get_current_user)):
    """Return total LLM cost, token usage, and cache hit rate for the workspace."""
    workspace_id = getattr(user, "workspace_id", "global")
    try:
        result = (
            _ack_supabase()
            .table("cost_tracking")
            .select("cost_usd,cache_hit,tokens_in,tokens_out,purpose")
            .eq("workspace_id", workspace_id)
            .execute()
        )
        rows = result.data or []
        total_cost = sum(r["cost_usd"] for r in rows)
        cache_hits = sum(1 for r in rows if r["cache_hit"])
        by_purpose: dict = {}
        for r in rows:
            by_purpose[r["purpose"]] = by_purpose.get(r["purpose"], 0) + r["cost_usd"]

        return {
            "workspace_id": workspace_id,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": sum(r["tokens_in"] + r["tokens_out"] for r in rows),
            "total_requests": len(rows),
            "cache_hits": cache_hits,
            "cache_hit_rate": round(cache_hits / max(len(rows), 1), 3),
            "cost_by_purpose": {k: round(v, 6) for k, v in by_purpose.items()},
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/cache", summary="ACK — Invalidate semantic cache")
async def ack_invalidate_cache(
    pattern: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """Invalidate semantic cache entries for the workspace, optionally by query text pattern."""
    from ...services.council_kernel.cache import get_semantic_cache
    workspace_id = getattr(user, "workspace_id", "global")
    count = await get_semantic_cache().invalidate(workspace_id, pattern)
    return {"invalidated": count, "pattern": pattern}


# ══════════════════════════════════════════════════════════════════════════════
# W2.3: Decision Lineage Tracking
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/lineage/{decision_id}", summary="W2.3 — Decision lineage chain")
async def get_decision_lineage(
    decision_id: str,
    depth: int = 10,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Retrieve the lineage chain for a decision (W2.3).

    Walks parent→child relationships to build a provenance trail.
    Returns the chain in chronological order (root → current).
    """
    workspace_id = getattr(user, "workspace_id", "global")
    chain = []

    try:
        from ...db.supabase_client import get_supabase_client
        client = get_supabase_client()

        current_id = decision_id
        visited = set()

        for _ in range(depth):
            if current_id in visited:
                break  # Prevent cycles
            visited.add(current_id)

            result = client.table("decisions").select("*").eq(
                "id", current_id
            ).execute()

            if not result.data:
                break

            record = result.data[0]
            chain.append({
                "decision_id": record.get("id", current_id),
                "title": record.get("title", ""),
                "status": record.get("status", ""),
                "tier": record.get("tier", "T0"),
                "created_at": record.get("created_at", ""),
                "parent_id": record.get("parent_decision_id"),
                "workspace_id": record.get("workspace_id", workspace_id),
            })

            parent = record.get("parent_decision_id")
            if not parent:
                break
            current_id = parent

    except Exception as exc:
        logger.debug(f"Decision lineage query failed (non-fatal): {exc}")
        # Fall back to returning just the requested ID
        chain = [{"decision_id": decision_id, "error": str(exc)}]

    # Reverse so root is first
    chain.reverse()

    return {
        "decision_id": decision_id,
        "lineage_depth": len(chain),
        "chain": chain,
    }


@router.get("/decisions/recent", summary="W2.3 — Recent decisions with lineage")
async def get_recent_decisions(
    limit: int = 20,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    List recent decisions for the workspace with parent lineage references (W2.3).
    """
    workspace_id = getattr(user, "workspace_id", "global")
    try:
        from ...db.supabase_client import get_supabase_client
        result = (
            get_supabase_client()
            .table("decisions")
            .select("id,title,status,tier,created_at,parent_decision_id,workspace_id")
            .eq("workspace_id", workspace_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"workspace_id": workspace_id, "decisions": result.data or []}
    except Exception as exc:
        logger.debug(f"Recent decisions query failed: {exc}")
        return {"workspace_id": workspace_id, "decisions": [], "error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════════
# W1.6 / F6: Temporal Changes Query
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/temporal/changes", summary="W1.6 — Decisions changed since timestamp")
async def get_temporal_changes(
    since: str,
    limit: int = 50,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Query what decisions changed since a given timestamp (blueprint 1.6).

    Args:
        since: ISO timestamp (e.g. '2026-04-01T00:00:00Z').
        limit: Maximum results (default 50).
    """
    workspace_id = getattr(user, "workspace_id", "global")
    try:
        from ...services.council_kernel.temporal_memory import query_changes_since
        changes = await query_changes_since(workspace_id, since, limit)
        return {
            "workspace_id": workspace_id,
            "since": since,
            "count": len(changes),
            "changes": changes,
        }
    except Exception as exc:
        logger.debug(f"Temporal changes query failed: {exc}")
        return {
            "workspace_id": workspace_id,
            "since": since,
            "count": 0,
            "changes": [],
            "error": str(exc),
        }

