"""
Aegion AI Council Service.

Manages AI-to-AI collaboration and multi-agent decision support.

Doctrine: "AI proposes, humans dispose."
The Council provides advisory capabilities, never makes autonomous decisions.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
import uuid
import asyncio

from ...core.logging import logger
from ...contracts.decision_intent import DecisionIntent, DecisionTier
from ...domain.council import (
    CouncilRole, CouncilVote, CouncilStageResult, 
    ChildDebateResult, ParentVerdict, SentinelAssessment,
    UncertaintyLevel, CouncilHealth, HealthStatus,
    CouncilMember, CouncilOpinion, CouncilSession
)
from ...ports.council import CouncilRepository
from .llm_gateway import LLMGateway


class GovernanceError(Exception):
    """Raised when a proposal violates governance contracts."""
    pass

class CouncilService:
    """
    Manages AI council sessions for proposal evaluation.
    
    The council provides:
    1. Multi-perspective analysis of proposals
    2. Risk identification and mitigation suggestions
    3. Advisory opinions (never binding decisions)
    
    Doctrine compliance:
    - All opinions are logged and auditable
    - Council never approves directly - only advises
    - Human approval is always required for T1+
    """
    

    def __init__(self, llm_port=None, repository: Optional[CouncilRepository] = None):
        """
        Initialize Council Service.
        
        Args:
            llm_port: Optional LLM port for AI invocations
            repository: Optional Persistence adapter
        """

        self.llm_port = llm_port
        self.gateway = LLMGateway(llm_port) if llm_port else None
        self.repository = repository
        self._members: Dict[str, CouncilMember] = {}
        # We only use _sessions as a fallback in-memory cache if no repo provided
        self._memory_sessions: Dict[str, CouncilSession] = {}
        self._freeze_mode = False
        
        # Default members (can be configured)
        self._register_default_members()

    async def check_health(self) -> CouncilHealth:
        """
        Check operational health of the Council.
        Probes LLM connectivity.
        """
        status = HealthStatus.HEALTHY
        details = {"llm_connectivity": True}
        
        if not self.llm_port:
            # If explicit mock mode (no port), consider it degraded for production use
            # but healthy for dev/test if intended.
            # Strategy: If initialized without LLM, it's DEGRADED by definition of "AI Council".
            status = HealthStatus.DEGRADED
            details["llm_connectivity"] = False
            details["reason"] = "No LLM port configured"
        else:
            try:
                # Simple probe - ask for a 1-token response or check status
                # We'll use a lightweight call if possible, or just assume if gateway exists
                # For now, let's try a ping if the port supports it, otherwise a simple completion
                if hasattr(self.llm_port, 'ping'):
                    await self.llm_port.ping()
                else:
                    # Fallback probe
                    await self.llm_port.complete(prompt="ping", model="gpt-4-turbo", max_tokens=1)
            except Exception as e:
                status = HealthStatus.DEGRADED
                details["llm_connectivity"] = False
                details["error"] = str(e)
        
        return CouncilHealth(
            status=status,
            details=details
        )
    
    def _register_default_members(self):
        """Register default AI council members."""
        defaults = [
            CouncilMember(
                member_id="ai-proposer",
                role=CouncilRole.PROPOSER,
                model="gpt-4-turbo",  # OpenAI: Strong generative capabilities
                specialization="solution_design"
            ),
            CouncilMember(
                member_id="ai-critic",
                role=CouncilRole.CRITIC,
                model="claude-3-opus",  # Anthropic: Strong reasoning and critique
                specialization="risk_analysis"
            ),
            CouncilMember(
                member_id="ai-auditor",
                role=CouncilRole.AUDITOR,
                model="gemini-1.5-pro",  # Google: Large context for compliance checking
                specialization="governance_compliance"
            ),
        ]
        for member in defaults:
            self._members[member.member_id] = member
    
    def register_member(self, member: CouncilMember) -> None:
        """Register a new council member."""
        self._members[member.member_id] = member
        logger.info(f"Registered council member: {member.member_id} ({member.role})")
    
    async def convene_session(
        self,
        proposal: DecisionIntent,
        workspace_id: str,
        member_ids: Optional[List[str]] = None
    ) -> CouncilSession:
        """
        Convene a council session to evaluate a proposal.
        
        Args:
            proposal: The proposal to evaluate
            workspace_id: Workspace context
            member_ids: Specific members to include (default: all)
        
        Returns:
            CouncilSession with collected opinions
        """
        if self._freeze_mode:
            raise GovernanceError("Cannot convene council during freeze mode.")
            
        # Health Check & Degradation Policy
        health = await self.check_health()
        
        if health.status == HealthStatus.FAILED:
            raise GovernanceError(f"Council System FAILED: {health.details}")
            
        if health.status == HealthStatus.DEGRADED:
            # Policy: High stakes proposals require fully healthy council
            if proposal.calculated_tier in (DecisionTier.T2, DecisionTier.T3):
                raise GovernanceError(
                    f"Cannot evaluate {proposal.calculated_tier.value} proposal in DEGRADED mode. "
                    f"Details: {health.details}"
                )
            # T0/T1 allowed but logged
            logger.warning(f"Convening session for {proposal.title} in DEGRADED mode.")

        start_time = datetime.now(timezone.utc).timestamp()

        # Select members
        if member_ids:
            members = [
                self._members[mid] for mid in member_ids 
                if mid in self._members
            ]
        else:
            members = list(self._members.values())
        
        # Create session
        session = CouncilSession(
            proposal_id=proposal.intent_id,
            workspace_id=workspace_id,
            member_ids=[m.member_id for m in members],
            status="active"
        )
        if self.repository:
            await self.repository.save_session(session)
        else:
            self._memory_sessions[session.session_id] = session
        
        logger.audit(
            action="COUNCIL_INVOKED",
            actor="council",
            target=proposal.intent_id,
            justification=f"Council convened with {len(members)} members",
            metadata={
                "session_id": session.session_id,
                "tier": proposal.calculated_tier.value,
                "health": health.status.value,
                "members": [m.member_id for m in members]
            }
        )
        
        # Collect opinions from each member in parallel
        cors = [
            self._get_member_opinion(member, proposal, workspace_id)
            for member in members
        ]
        
        # Gather results (parallel execution)
        results = await asyncio.gather(*cors, return_exceptions=True)
        
        opinions = []
        total_tokens = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Council member {members[i].member_id} failed: {str(result)}"
                )
                # Create fallback error opinion
                opinions.append(CouncilOpinion(
                    member_id=members[i].member_id,
                    proposal_id=proposal.intent_id,
                    vote=CouncilVote.ABSTAIN,
                    confidence=0.0,
                    analysis=f"System Error: {str(result)}",
                    tokens_consumed=0
                ))
            else:
                opinions.append(result)
                total_tokens += result.tokens_consumed
        
        # Update session
        session = CouncilSession(
            session_id=session.session_id,
            proposal_id=session.proposal_id,
            workspace_id=session.workspace_id,
            member_ids=session.member_ids,
            opinions=opinions,
            status="completed",
            started_at=session.started_at,
            completed_at=datetime.now(timezone.utc),
            total_tokens=total_tokens
        )
        
        # Calculate consensus
        session = self._calculate_consensus(session)
        
        # Sentinel Enforcement Gate: Post-processing check
        # If any Sentinel opinion is blocking=True, we must override consensus or reject
        for opinion in session.opinions:
            if opinion.metadata.get("blocking") is True and opinion.metadata.get("stage") == "sentinel_assessment":
                logger.error(
                    f"SENTINEL BLOCK: {opinion.member_id} flagged critical risk in session {session.session_id}",
                    metadata=opinion.metadata
                )
                session = CouncilSession(
                    **session.model_dump(exclude={'status', 'consensus', 'synthesis'}),
                    status="rejected",
                    consensus=CouncilVote.OPPOSE,
                    synthesis=f"**SENTINEL BLOCK APPLIED**: {opinion.analysis}"
                )
                
                # Persist rejection
                if self.repository:
                    await self.repository.save_session(session)
                else:
                    self._memory_sessions[session.session_id] = session
                
                # We raise an error to stop the proposal flow immediately
                # The session is saved as rejected for audit trail
                raise GovernanceError(f"Sentinel blocked proposal: {opinion.analysis[:100]}...")

        if self.repository:
            await self.repository.save_session(session)
        else:
            self._memory_sessions[session.session_id] = session
        
        logger.audit(
            action="COUNCIL_COMPLETED",
            actor="council",
            target=proposal.intent_id,
            justification=f"Council reached {session.consensus} consensus",
            metadata={
                "session_id": session.session_id,
                "consensus": session.consensus.value if session.consensus else "none",
                "confidence": session.consensus_confidence,
                "total_tokens": total_tokens
            }
        )
        
        # Update metrics
        from .metrics import get_metrics_service
        metrics = get_metrics_service()
        
        elapsed = datetime.now(timezone.utc).timestamp() - start_time
        metrics.council_duration.observe(elapsed)
        metrics.council_sessions.labels(result=session.consensus.value if session.consensus else "none").inc()

        return session
    
    async def _get_member_opinion(
        self,
        member: CouncilMember,
        proposal: DecisionIntent,
        workspace_id: str
    ) -> CouncilOpinion:
        """Get opinion from a council member."""
        # If no LLM port, create mock opinion based on role
        if not self.llm_port:
            return self._create_mock_opinion(member, proposal)
            
        # Determine schema and prompts
        if member.role == CouncilRole.SYNTHESIZER:
            schema = ParentVerdict
        elif member.role == CouncilRole.SENTINEL:
            schema = SentinelAssessment
        else:
            schema = ChildDebateResult
            
        prompt = self._create_prompt(member, proposal, schema)
        
        # Determine timeout based on role/stage
        if member.role == CouncilRole.SYNTHESIZER:
            timeout = 45.0  # Complex synthesis
        elif member.role == CouncilRole.SENTINEL:
            timeout = 20.0  # Quick safety check
        else:
            timeout = 30.0  # Standard debate

        # Invoke LLM with strict validation and timeout
        try:
            result = await asyncio.wait_for(
                self.gateway.complete_with_schema(
                    prompt=prompt,
                    model=member.model,
                    schema=schema
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Council member {member.member_id} timed out after {timeout}s")
            # Return a valid fallback schema based on type
            if schema == ChildDebateResult:
                result = ChildDebateResult(
                    stage_name="child_debate",
                    claim="Analysis timed out.",
                    reasoning_summary=f"The model failed to respond within {timeout} seconds.",
                    confidence_score=0.0,
                    uncertainty_level=UncertaintyLevel.CRITICAL,
                    blocking=False,
                    agent_role=member.role.value,
                    vote=CouncilVote.ABSTAIN,
                    citations=[],
                    result_id=str(uuid.uuid4())
                )
            elif schema == ParentVerdict:
                result = ParentVerdict(
                    stage_name="parent_verdict",
                    recommended_action=CouncilVote.ABSTAIN,
                    child_consensus="None (Timeout)",
                    claim="Synthesis timed out.",
                    reasoning_summary=f"The model failed to respond within {timeout} seconds.",
                    confidence_score=0.0,
                    uncertainty_level=UncertaintyLevel.CRITICAL,
                    blocking=False,
                    result_id=str(uuid.uuid4())
                )
            elif schema == SentinelAssessment:
                result = SentinelAssessment(
                    stage_name="sentinel_assessment",
                    risk_category="Timeout",
                    claim="Safety check timed out.",
                    reasoning_summary=f"The model failed to respond within {timeout} seconds. Treating as high uncertainty.",
                    confidence_score=0.0,
                    uncertainty_level=UncertaintyLevel.CRITICAL,
                    blocking=True, # Fail safe: block if sentinel times out
                    result_id=str(uuid.uuid4())
                )
            else:
                raise ValueError("Unknown schema type for timeout fallback")
        
        # Map to CouncilOpinion (Legacy Adapter)
        if isinstance(result, ChildDebateResult):
            return CouncilOpinion(
                member_id=member.member_id,
                proposal_id=proposal.intent_id,
                vote=result.vote,
                confidence=result.confidence_score,
                analysis=f"**Claim:** {result.claim}\n\n**Reasoning:** {result.reasoning_summary}",
                concerns=[], # Extracted from analysis if needed, or structured later
                suggestions=[],
                metadata={
                    "stage": "child_debate",
                    "uncertainty": result.uncertainty_level.value,
                    "blocking": result.blocking,
                    "citations": result.citations,
                    "result_id": result.result_id
                }
            )
        elif isinstance(result, ParentVerdict):
             return CouncilOpinion(
                member_id=member.member_id,
                proposal_id=proposal.intent_id,
                vote=result.recommended_action,
                confidence=result.confidence_score,
                analysis=f"**Verdict:** {result.recommended_action}\n\n**Consensus Summary:** {result.child_consensus}\n\n**Reasoning:** {result.reasoning_summary}",
                metadata={
                    "stage": "parent_verdict",
                    "uncertainty": result.uncertainty_level.value,
                    "blocking": result.blocking,
                    "result_id": result.result_id
                }
            )
        elif isinstance(result, SentinelAssessment):
             # Sentinel blocks map to OPPOSE if blocking
             vote = CouncilVote.OPPOSE if result.blocking else CouncilVote.SUPPORT
             return CouncilOpinion(
                member_id=member.member_id,
                proposal_id=proposal.intent_id,
                vote=vote,
                confidence=result.confidence_score,
                analysis=f"**Risk Category:** {result.risk_category}\n\n**Assessment:** {result.claim}\n\n**Reasoning:** {result.reasoning_summary}",
                metadata={
                    "stage": "sentinel_assessment",
                    "uncertainty": result.uncertainty_level.value,
                    "blocking": result.blocking,
                    "risk_category": result.risk_category,
                    "result_id": result.result_id
                }
            )
        else:
            raise ValueError(f"Unknown result type: {type(result)}")

    def _create_prompt(
        self,
        member: CouncilMember,
        proposal: DecisionIntent,
        schema: Any
    ) -> str:
        """Create prompt for council member based on role."""
        role_instructions = {
            CouncilRole.PROPOSER: "Evaluate if this proposal addresses the problem effectively. Construct a strong claim.",
            CouncilRole.CRITIC: "Identify potential risks, gaps, and concerns with this proposal.",
            CouncilRole.ADVOCATE: "Highlight the strengths and benefits of this proposal.",
            CouncilRole.SYNTHESIZER: "Synthesize the child opinions (provided in context) into a final verdict.",
            CouncilRole.AUDITOR: "Check for governance compliance and proper documentation.",
            CouncilRole.SENTINEL: "Perform a safety check. Identify any critical risks (auth, data loss)."
        }
        
        base_prompt = f"""
You are acting as a {member.role.value} in an AI Council evaluating a development proposal.

{role_instructions.get(member.role, "Provide your analysis.")}

PROPOSAL:
Title: {proposal.title}
Description: {proposal.description}
Tier: {proposal.calculated_tier.value}
Impact: {proposal.impact_level.value}
Reversibility: {proposal.reversibility.value}
Affected Modules: {', '.join(proposal.affected_modules)}

REASONING PROVIDED:
Problem: {proposal.reasoning.problem_framing}
Assumptions: {', '.join(proposal.reasoning.assumptions)}
Constraints: {', '.join(proposal.reasoning.constraints)}

Ensure your response is valid JSON matching the following schema structure:
"""
        
        # Schema specific instructions
        if schema == ChildDebateResult:
            base_prompt += """
{
  "claim": "Your main assertion",
  "reasoning_summary": "Summary of your logic",
  "confidence_score": 0.0 to 1.0,
  "uncertainty_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "blocking": boolean (true if this should block the proposal),
  "agent_role": "role_name",
  "vote": "support" | "oppose" | "abstain" | "defer",
  "citations": ["list", "of", "files"]
}
"""
        elif schema == ParentVerdict:
            base_prompt += """
{
  "recommended_action": "support" | "oppose" | "abstain" | "defer",
  "child_consensus": "Summary of children agreement",
  "claim": "Final verdict statement",
  "reasoning_summary": "Logic for verdict",
  "confidence_score": 0.0 to 1.0,
  "uncertainty_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "blocking": boolean
}
"""
        elif schema == SentinelAssessment:
            base_prompt += """
{
  "risk_category": "category",
  "claim": "Safety assessment",
  "reasoning_summary": "Why it is safe/unsafe",
  "confidence_score": 0.0 to 1.0,
  "uncertainty_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "blocking": boolean (MUST be true if high risk/uncertainty)
}
"""
        
        return base_prompt

    def _create_mock_opinion(
        self,
        member: CouncilMember,
        proposal: DecisionIntent
    ) -> CouncilOpinion:
        """
        Create heuristic fallback opinion.
        """
         # Role-based mock responses
        role_responses = {
            CouncilRole.PROPOSER: {
                "vote": CouncilVote.SUPPORT,
                "analysis": f"[DEGRADED] Proposal '{proposal.title}' — heuristic review only (LLM unavailable).",
                "concerns": ["This opinion was generated without AI analysis"],
                "suggestions": ["Consider adding rollback strategy"],
                "confidence": 0.3
            },
            CouncilRole.CRITIC: {
                "vote": CouncilVote.ABSTAIN,
                "analysis": f"[DEGRADED] Proposal requires more evidence — heuristic review only.",
                "concerns": ["Limited evidence provided", "Affected scope unclear", "This opinion was generated without AI analysis"],
                "suggestions": ["Add more test coverage", "Document rollback plan"],
                "confidence": 0.2
            },
            CouncilRole.AUDITOR: {
                "vote": CouncilVote.ABSTAIN,
                "analysis": f"[DEGRADED] Cannot verify compliance without AI analysis (LLM unavailable).",
                "concerns": ["This opinion was generated without AI analysis"],
                "suggestions": [],
                "confidence": 0.25
            },
            CouncilRole.ADVOCATE: {
                "vote": CouncilVote.ABSTAIN,
                "analysis": f"[DEGRADED] Unable to fully assess benefits without AI analysis.",
                "concerns": ["This opinion was generated without AI analysis"],
                "suggestions": [],
                "confidence": 0.25
            },
            CouncilRole.SYNTHESIZER: {
                "vote": CouncilVote.ABSTAIN,
                "analysis": f"[DEGRADED] Cannot synthesize perspectives without AI analysis.",
                "concerns": ["This opinion was generated without AI analysis"],
                "suggestions": ["Ensure cross-team visibility"],
                "confidence": 0.2
            },
        }
        
        return CouncilOpinion(
            member_id=member.member_id,
            proposal_id=proposal.intent_id,
            vote=CouncilVote.ABSTAIN,
            confidence=0.0,
            analysis="Mock",
            concerns=[],
            suggestions=[],
            tokens_consumed=0,
            metadata={"stage": "mock"}
        )
    
    def _calculate_consensus(self, session: CouncilSession) -> CouncilSession:
        """Calculate consensus from council opinions."""
        if not session.opinions:
            return session
        
        # Weighted voting
        vote_weights = {
            CouncilVote.SUPPORT: 0.0,
            CouncilVote.OPPOSE: 0.0,
            CouncilVote.ABSTAIN: 0.0,
            CouncilVote.DEFER: 0.0
        }
        total_weight = 0.0
        
        for opinion in session.opinions:
            member = self._members.get(opinion.member_id)
            weight = (member.weight if member else 1.0) * opinion.confidence
            vote_weights[opinion.vote] += weight
            total_weight += weight
        
        # Determine consensus
        if total_weight == 0:
            consensus = CouncilVote.ABSTAIN
            confidence = 0.0
        else:
            max_vote = max(vote_weights.items(), key=lambda x: x[1])
            consensus = max_vote[0]
            confidence = max_vote[1] / total_weight
        
        # Create synthesis
        concerns = []
        suggestions = []
        dissenting_ids = []
        
        for opinion in session.opinions:
            concerns.extend(opinion.concerns)
            suggestions.extend(opinion.suggestions)
            if opinion.vote != consensus and opinion.vote != CouncilVote.ABSTAIN:
                dissenting_ids.append(opinion.member_id)
        
        synthesis = f"Council {consensus.value} with {confidence:.0%} confidence."
        if dissenting_ids:
            synthesis += f" Dissent from {len(dissenting_ids)} members."
            
        if concerns:
            synthesis += f" Concerns: {'; '.join(list(set(concerns))[:3])}."
        if suggestions:
            synthesis += f" Suggestions: {'; '.join(list(set(suggestions))[:3])}."
        
        # Update metrics
        from ..archon.metrics import get_metrics_service
        metrics = get_metrics_service()
        
        # Fix start_time reference
        if session.started_at.tzinfo is None:
             now = datetime.utcnow()
        else:
             now = datetime.now(timezone.utc)
             
        elapsed = (now - session.started_at).total_seconds()
        metrics.council_duration.observe(elapsed)
        metrics.council_sessions.labels(result=consensus.value).inc()
        
        return CouncilSession(
            session_id=session.session_id,
            proposal_id=session.proposal_id,
            workspace_id=session.workspace_id,
            member_ids=session.member_ids,
            opinions=session.opinions,
            consensus=consensus,
            consensus_confidence=confidence,
            synthesis=synthesis,
            dissent_count=len(dissenting_ids),
            dissenting_member_ids=dissenting_ids,
            status=session.status,
            started_at=session.started_at,
            completed_at=session.completed_at,
            total_tokens=session.total_tokens
        )
    
    async def get_session(self, session_id: str) -> Optional[CouncilSession]:
        """Get a council session by ID."""
        if self.repository:
            return await self.repository.get_session(session_id)
        return self._memory_sessions.get(session_id)
    
    async def get_sessions_for_proposal(
        self,
        proposal_id: str
    ) -> List[CouncilSession]:
        """Get all council sessions for a proposal."""
        if self.repository:
            return await self.repository.find_sessions_by_proposal(proposal_id)
            
        return [
            s for s in self._memory_sessions.values() 
            if s.proposal_id == proposal_id
        ]
        
    async def get_transcript(self, session_id: str) -> Dict[str, Any]:
        """
        Get full transcript of a council session.
        Useful for audit and governance review.
        """
        session = await self.get_session(session_id)
        if not session:
            return None
            
        return {
            "session_id": session.session_id,
            "proposal_id": session.proposal_id,
            "result": session.consensus,
            "transcript": [
                {
                    "member": op.member_id,
                    "role": self._members.get(op.member_id).role.value if op.member_id in self._members else "unknown",
                    "vote": op.vote,
                    "analysis": op.analysis,
                    "metadata": op.metadata
                }
                for op in session.opinions
            ],
            "synthesis": session.synthesis,
            "metadata": {
                "started_at": session.started_at.isoformat(),
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "health_status": "archived" # In future we could store health snapshot
            }
        }

    async def verify_governance(self, proposal_id: str) -> bool:
        """
        Check if a proposal has passed council review with SUPPORT.
        """
        sessions = await self.get_sessions_for_proposal(proposal_id)
        # Check for any completed session with SUPPORT consensus
        for session in sessions:
            if session.status == "completed" and session.consensus == CouncilVote.SUPPORT:
                return True
        return False

    async def assert_governance(self, proposal_id: str) -> None:
        """
        Assert that a proposal has passed governance. Raises GovernanceError if not.
        """
        if not await self.verify_governance(proposal_id):
            raise GovernanceError(f"Proposal {proposal_id} has not passed Council Governance.")

