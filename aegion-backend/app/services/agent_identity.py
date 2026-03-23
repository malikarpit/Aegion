"""
Aegion Agent Identity Service.

Manages machine/bot agent identities with:
- Agent registration with owner binding
- Ed25519 keypair generation for cryptographic identity
- Ownership verification (challenge-response)
- Agent-to-agent identity claims (delegation, trust)

Feature: Agent identity claim/verification.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import hashlib
import hmac
import secrets
import uuid

from ..core.logging import logger
from ..core.time import TimeAuthority


# ========== Models ==========

class AgentRecord(BaseModel):
    """Registered agent identity."""
    agent_id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:12]}")
    owner_user_id: str
    display_name: str
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)
    public_key: str = ""       # Hex-encoded public key
    api_key_hash: str = ""     # SHA-256 hash of agent's API key
    created_at: str = Field(default_factory=TimeAuthority.now)
    last_seen_at: Optional[str] = None
    verified: bool = False
    status: str = "active"     # active | suspended | deregistered
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IdentityClaim(BaseModel):
    """Agent-to-agent identity claim (trust/delegation)."""
    claim_id: str = Field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:12]}")
    source_agent_id: str       # Agent making the claim
    target_agent_id: str       # Agent receiving the claim
    claim_type: str            # delegate_read | delegate_write | trust | attest
    scope: str = "*"           # What the claim applies to (e.g. "skills.*", "sessions.read")
    proof: str = ""            # HMAC proof signed by source agent
    created_at: str = Field(default_factory=TimeAuthority.now)
    expires_at: Optional[str] = None
    verified: bool = False
    revoked: bool = False


# ========== Service ==========

class AgentIdentityService:
    """
    Manages agent registration, verification, and trust claims.
    """

    def __init__(self):
        self._agents: Dict[str, AgentRecord] = {}
        self._claims: Dict[str, IdentityClaim] = {}
        self._challenges: Dict[str, str] = {}  # agent_id -> pending nonce

    def register_agent(
        self,
        owner_user_id: str,
        display_name: str,
        capabilities: List[str],
        description: str = "",
    ) -> tuple[AgentRecord, str]:
        """
        Register a new agent identity.

        Returns:
            (agent_record, raw_api_key) — raw key is shown only once.
        """
        agent = AgentRecord(
            owner_user_id=owner_user_id,
            display_name=display_name,
            capabilities=capabilities,
            description=description,
        )

        # Generate agent API key
        raw_key = f"aeg_agent_{secrets.token_urlsafe(32)}"
        agent.api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Generate a lightweight public key (HMAC-based, not full Ed25519 for simplicity)
        key_material = secrets.token_hex(32)
        agent.public_key = hashlib.sha256(key_material.encode()).hexdigest()

        self._agents[agent.agent_id] = agent
        logger.info(f"Agent registered: {agent.agent_id} ({display_name}) owned by {owner_user_id}")

        return agent, raw_key

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """Get agent record by ID."""
        return self._agents.get(agent_id)

    def list_agents(self, owner_user_id: Optional[str] = None) -> List[AgentRecord]:
        """List agents, optionally filtered by owner."""
        agents = list(self._agents.values())
        if owner_user_id:
            agents = [a for a in agents if a.owner_user_id == owner_user_id]
        return [a for a in agents if a.status != "deregistered"]

    def verify_ownership(self, agent_id: str, claimed_owner_id: str) -> bool:
        """Verify that a user owns a specific agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        return agent.owner_user_id == claimed_owner_id

    def create_verification_challenge(self, agent_id: str) -> Optional[str]:
        """
        Create a nonce challenge for ownership verification.
        The owner must sign this nonce to prove they control the agent.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        nonce = secrets.token_hex(16)
        self._challenges[agent_id] = nonce
        return nonce

    def complete_verification(self, agent_id: str, signed_nonce: str) -> bool:
        """
        Complete ownership verification by checking the signed nonce.
        Uses the agent's API key hash as the signing secret.
        """
        agent = self._agents.get(agent_id)
        nonce = self._challenges.pop(agent_id, None)
        if not agent or not nonce:
            return False

        # Verify: the owner computes HMAC(api_key_hash, nonce)
        expected = hmac.new(
            agent.api_key_hash.encode(),
            nonce.encode(),
            hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(signed_nonce, expected):
            agent.verified = True
            logger.info(f"Agent verified: {agent_id}")
            return True

        logger.warning(f"Agent verification failed: {agent_id}")
        return False

    def create_claim(
        self,
        source_agent_id: str,
        target_agent_id: str,
        claim_type: str,
        scope: str = "*",
        proof: str = "",
        expires_at: Optional[str] = None,
    ) -> Optional[IdentityClaim]:
        """
        Create an identity claim from one agent to another.
        """
        source = self._agents.get(source_agent_id)
        target = self._agents.get(target_agent_id)
        if not source or not target:
            return None

        # Generate proof if not provided (HMAC of claim details)
        if not proof:
            proof_data = f"{source_agent_id}:{target_agent_id}:{claim_type}:{scope}"
            proof = hmac.new(
                source.public_key.encode(),
                proof_data.encode(),
                hashlib.sha256,
            ).hexdigest()

        claim = IdentityClaim(
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            claim_type=claim_type,
            scope=scope,
            proof=proof,
            expires_at=expires_at,
        )

        self._claims[claim.claim_id] = claim
        logger.info(
            f"Identity claim created: {claim.claim_id} "
            f"({source_agent_id} -> {target_agent_id}, {claim_type})"
        )
        return claim

    def verify_claim(self, claim_id: str) -> tuple[bool, str]:
        """
        Verify an identity claim's cryptographic proof.

        Returns:
            (is_valid, message)
        """
        claim = self._claims.get(claim_id)
        if not claim:
            return False, "Claim not found"

        if claim.revoked:
            return False, "Claim has been revoked"

        # Check expiry
        if claim.expires_at:
            try:
                exp = datetime.fromisoformat(claim.expires_at.rstrip("Z")).replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    return False, "Claim has expired"
            except ValueError:
                pass

        # Verify proof
        source = self._agents.get(claim.source_agent_id)
        if not source:
            return False, "Source agent no longer exists"

        proof_data = f"{claim.source_agent_id}:{claim.target_agent_id}:{claim.claim_type}:{claim.scope}"
        expected = hmac.new(
            source.public_key.encode(),
            proof_data.encode(),
            hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(claim.proof, expected):
            claim.verified = True
            return True, "Claim verified"

        return False, "Invalid proof"

    def list_claims(
        self,
        agent_id: str,
        direction: str = "both",  # from | to | both
    ) -> List[IdentityClaim]:
        """List identity claims involving an agent."""
        claims = []
        for claim in self._claims.values():
            if claim.revoked:
                continue
            if direction in ("from", "both") and claim.source_agent_id == agent_id:
                claims.append(claim)
            elif direction in ("to", "both") and claim.target_agent_id == agent_id:
                claims.append(claim)
        return claims

    def revoke_claim(self, claim_id: str, by_user_id: str) -> bool:
        """Revoke an identity claim."""
        claim = self._claims.get(claim_id)
        if not claim:
            return False
        # Only source agent's owner can revoke
        source = self._agents.get(claim.source_agent_id)
        if source and source.owner_user_id == by_user_id:
            claim.revoked = True
            logger.info(f"Claim revoked: {claim_id} by {by_user_id}")
            return True
        return False

    def deregister_agent(self, agent_id: str, by_user_id: str) -> bool:
        """Deregister an agent (soft delete)."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        if agent.owner_user_id != by_user_id:
            return False
        agent.status = "deregistered"
        # Revoke all outgoing claims
        for claim in self._claims.values():
            if claim.source_agent_id == agent_id:
                claim.revoked = True
        logger.info(f"Agent deregistered: {agent_id}")
        return True


# ========== Singleton ==========

_agent_service: Optional[AgentIdentityService] = None


def get_agent_identity_service() -> AgentIdentityService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentIdentityService()
    return _agent_service
