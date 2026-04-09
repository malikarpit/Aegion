"""
Aegion API v1 - Agent Identity Endpoints.

REST endpoints for agent lifecycle: registration, verification,
identity claims, and deregistration.

Feature: Agent identity claim/verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ...services.agent_identity import (
    get_agent_identity_service,
    AgentRecord,
    IdentityClaim,
)
from ...core.security import get_current_user, AuthorityContext


router = APIRouter(prefix="/agents", tags=["agents"])


# ========== Request/Response Models ==========

class RegisterAgentRequest(BaseModel):
    display_name: str
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)


class RegisterAgentResponse(BaseModel):
    agent_id: str
    display_name: str
    owner_user_id: str
    api_key: str  # Shown only once
    capabilities: List[str]
    created_at: str
    message: str = "Store the api_key securely — it will not be shown again."


class AgentDetailResponse(BaseModel):
    agent_id: str
    display_name: str
    description: str
    owner_user_id: str
    capabilities: List[str]
    verified: bool
    status: str
    created_at: str
    last_seen_at: Optional[str] = None


class VerificationChallengeResponse(BaseModel):
    agent_id: str
    nonce: str
    message: str = "Sign this nonce with HMAC(api_key_hash, nonce) and POST to /verify/complete"


class CompleteVerificationRequest(BaseModel):
    signed_nonce: str


class VerificationResult(BaseModel):
    agent_id: str
    verified: bool
    message: str


class CreateClaimRequest(BaseModel):
    target_agent_id: str
    claim_type: str = Field(..., description="delegate_read | delegate_write | trust | attest")
    scope: str = "*"
    expires_at: Optional[str] = None


class ClaimResponse(BaseModel):
    claim_id: str
    source_agent_id: str
    target_agent_id: str
    claim_type: str
    scope: str
    verified: bool
    created_at: str
    expires_at: Optional[str] = None


class ClaimVerifyResponse(BaseModel):
    claim_id: str
    valid: bool
    message: str


# ========== Endpoints ==========


@router.post("", response_model=RegisterAgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    request: RegisterAgentRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Register a new agent identity bound to the current user."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_agent_identity_service()
    agent, raw_key = svc.register_agent(
        owner_user_id=user.user_id,
        display_name=request.display_name,
        capabilities=request.capabilities,
        description=request.description,
    )

    return RegisterAgentResponse(
        agent_id=agent.agent_id,
        display_name=agent.display_name,
        owner_user_id=agent.owner_user_id,
        api_key=raw_key,
        capabilities=agent.capabilities,
        created_at=agent.created_at,
    )


@router.get("", response_model=List[AgentDetailResponse])
async def list_agents(
    user: AuthorityContext = Depends(get_current_user),
):
    """List agents owned by the current user."""
    svc = get_agent_identity_service()
    agents = svc.list_agents(owner_user_id=user.user_id)
    return [
        AgentDetailResponse(
            agent_id=a.agent_id,
            display_name=a.display_name,
            description=a.description,
            owner_user_id=a.owner_user_id,
            capabilities=a.capabilities,
            verified=a.verified,
            status=a.status,
            created_at=a.created_at,
            last_seen_at=a.last_seen_at,
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(
    agent_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get details of a specific agent."""
    svc = get_agent_identity_service()
    agent = svc.get_agent(agent_id)
    if not agent or agent.status == "deregistered":
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentDetailResponse(
        agent_id=agent.agent_id,
        display_name=agent.display_name,
        description=agent.description,
        owner_user_id=agent.owner_user_id,
        capabilities=agent.capabilities,
        verified=agent.verified,
        status=agent.status,
        created_at=agent.created_at,
        last_seen_at=agent.last_seen_at,
    )


@router.post("/{agent_id}/verify", response_model=VerificationChallengeResponse)
async def start_verification(
    agent_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Start ownership verification — returns a nonce challenge."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_agent_identity_service()
    if not svc.verify_ownership(agent_id, user.user_id):
        raise HTTPException(status_code=403, detail="You do not own this agent")

    nonce = svc.create_verification_challenge(agent_id)
    if not nonce:
        raise HTTPException(status_code=404, detail="Agent not found")

    return VerificationChallengeResponse(agent_id=agent_id, nonce=nonce)


@router.post("/{agent_id}/verify/complete", response_model=VerificationResult)
async def complete_verification(
    agent_id: str,
    request: CompleteVerificationRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Complete ownership verification with signed nonce."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_agent_identity_service()
    if not svc.verify_ownership(agent_id, user.user_id):
        raise HTTPException(status_code=403, detail="You do not own this agent")

    success = svc.complete_verification(agent_id, request.signed_nonce)
    return VerificationResult(
        agent_id=agent_id,
        verified=success,
        message="Agent verified successfully" if success else "Verification failed — invalid signed nonce",
    )


@router.post("/{agent_id}/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    agent_id: str,
    request: CreateClaimRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create an identity claim from this agent to another."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_agent_identity_service()
    if not svc.verify_ownership(agent_id, user.user_id):
        raise HTTPException(status_code=403, detail="You do not own the source agent")

    claim = svc.create_claim(
        source_agent_id=agent_id,
        target_agent_id=request.target_agent_id,
        claim_type=request.claim_type,
        scope=request.scope,
        expires_at=request.expires_at,
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Source or target agent not found")

    return ClaimResponse(
        claim_id=claim.claim_id,
        source_agent_id=claim.source_agent_id,
        target_agent_id=claim.target_agent_id,
        claim_type=claim.claim_type,
        scope=claim.scope,
        verified=claim.verified,
        created_at=claim.created_at,
        expires_at=claim.expires_at,
    )


@router.get("/{agent_id}/claims", response_model=List[ClaimResponse])
async def list_claims(
    agent_id: str,
    direction: str = "both",
    user: AuthorityContext = Depends(get_current_user),
):
    """List identity claims involving this agent."""
    svc = get_agent_identity_service()
    claims = svc.list_claims(agent_id, direction=direction)
    return [
        ClaimResponse(
            claim_id=c.claim_id,
            source_agent_id=c.source_agent_id,
            target_agent_id=c.target_agent_id,
            claim_type=c.claim_type,
            scope=c.scope,
            verified=c.verified,
            created_at=c.created_at,
            expires_at=c.expires_at,
        )
        for c in claims
    ]


@router.post("/{agent_id}/claims/{claim_id}/verify", response_model=ClaimVerifyResponse)
async def verify_claim(
    agent_id: str,
    claim_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Verify the cryptographic proof of an identity claim."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_agent_identity_service()
    valid, message = svc.verify_claim(claim_id)
    return ClaimVerifyResponse(claim_id=claim_id, valid=valid, message=message)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_agent(
    agent_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Deregister an agent (soft delete, revokes all claims)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_agent_identity_service()
    if not svc.deregister_agent(agent_id, user.user_id):
        raise HTTPException(status_code=403, detail="Not authorized or agent not found")
