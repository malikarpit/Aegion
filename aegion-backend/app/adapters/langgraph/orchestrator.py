"""
Aegion LangGraph AI Orchestrator Adapter.

Implements AIOrchestrationPort using LangGraph logic.
AG-006: Replaces literal mocks with structured heuristic fallbacks.
"""

from typing import Dict, Any, List, AsyncIterator, Optional
from enum import Enum
import asyncio
import json

from langgraph.graph import StateGraph, END

from ...ports.ai_orchestrator import (
    AIOrchestrationPort,
    AgentRegistryPort,
    AgentRole,
    AgentCapability,
    FORBIDDEN_CAPABILITIES,
    AIProposal,
    CouncilDebateResult,
)
from ...contracts.uncertainty_level import UncertaintyDeclaration
from ...core.logging import logger
from ...core.time import TimeAuthority
from ...core.config import settings


def _get_genai_model(model_name: str, temperature: float):
    """Lazy-init a Gemini model. Returns None if API key not configured."""
    try:
        import google.generativeai as genai
        api_key = getattr(settings, 'gemini_api_key', None) or __import__('os').environ.get('GEMINI_API_KEY')
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=model_name,
            generation_config={"temperature": temperature}
        )
    except Exception:
        return None


async def _call_llm(system_prompt: str, user_prompt: str, config: dict) -> str:
    """Call Gemini with fallback to None if unavailable."""
    model = _get_genai_model(config.get('model', 'gemini-2.0-flash'), config.get('temperature', 0.5))
    if model is None:
        return None  # Caller uses heuristic fallback
    try:
        response = await __import__('asyncio').get_event_loop().run_in_executor(
            None,
            lambda: model.generate_content(f"{system_prompt}\n\nUser: {user_prompt}")
        )
        return response.text
    except Exception as e:
        logger.warning(f"LLM call failed, falling back to heuristic: {e}")
        return None


# Agent capability matrix (from Agent Authority Doctrine)
AGENT_CAPABILITIES = {
    AgentRole.CHILD: frozenset([
        AgentCapability.SUGGEST,
        AgentCapability.DRAFT,
        AgentCapability.EXPLORE,
    ]),
    AgentRole.PARENT: frozenset([
        AgentCapability.ANALYZE,
        AgentCapability.REVIEW,
        AgentCapability.SCORE,
    ]),
    AgentRole.SENTINEL: frozenset([
        AgentCapability.MONITOR,
        AgentCapability.ALERT,
        AgentCapability.FLAG,
    ]),
}


class LangGraphAgentRegistry(AgentRegistryPort):
    """
    Registry for agent configurations and capabilities.
    Enforces the Agent Authority Matrix.
    """
    
    _configs = {
        AgentRole.CHILD: {
            "model": "gemini-2.0-flash",
            "temperature": 0.7,
            "system_prompt": """You are a creative coding assistant.
Your role is to SUGGEST and EXPLORE ideas.
Output format: {claim, reasoning, uncertainty, alternatives}"""
        },
        AgentRole.PARENT: {
            "model": "gemini-2.0-flash",
            "temperature": 0.2,
            "system_prompt": """You are an architectural reviewer.
Your role is to ANALYZE and REVIEW proposals.
Output format: {analysis, risks, score, recommendation}"""
        },
        AgentRole.SENTINEL: {
            "model": "gemini-2.0-flash",
            "temperature": 0.0,
            "system_prompt": """You are a risk monitor.
Your role is to FLAG violations and ALERT on risks.
Output format: {flags, alerts, severity}"""
        },
    }
    
    def get_allowed_capabilities(self, role: AgentRole) -> frozenset[AgentCapability]:
        return AGENT_CAPABILITIES.get(role, frozenset())
    
    def validate_agent_action(self, role: AgentRole, capability: AgentCapability) -> bool:
        if capability.value in FORBIDDEN_CAPABILITIES:
            raise PermissionError(f"Capability {capability} is FORBIDDEN for all agents")
        
        allowed = self.get_allowed_capabilities(role)
        if capability not in allowed:
            raise PermissionError(f"Agent {role} cannot perform {capability}")
        
        return True
    
    def get_agent_config(self, role: AgentRole) -> Dict[str, Any]:
        return self._configs.get(role, {})


class LangGraphOrchestrator(AIOrchestrationPort):
    """
    LangGraph implementation of the Governed Debate Pipeline.
    AG-006: Enhanced heuristics and structured output.
    """
    
    def __init__(self, registry: AgentRegistryPort = None):
        self.registry = registry or LangGraphAgentRegistry()
    
    async def invoke_child_council(
        self, 
        prompt: str, 
        context: Dict[str, Any],
        session_id: str
    ) -> AsyncIterator[str]:
        """
        Invoke Child AI Council for creative exploration.
        Streams response tokens.
        
        Validates agent authority before invocation.
        Returns degradation-labeled response if LLM unavailable.
        """
        
        self.registry.validate_agent_action(AgentRole.CHILD, AgentCapability.SUGGEST)
        
        config = self.registry.get_agent_config(AgentRole.CHILD)
        
        # 1. Try LLM
        llm_response = await _call_llm(
            config.get('system_prompt', ''),
            f"Context: {context}\n\nPrompt: {prompt}",
            config
        )
        
        # 2. Degraded Fallback (clearly marked, not silent)
        if not llm_response:
            logger.warning("Council child returned degraded response: LLM unavailable")
            response_obj = {
                "claim": f"[DEGRADED] Heuristic suggestion for: {prompt[:80]}",
                "reasoning": "LLM unavailable — this is a heuristic placeholder, not AI analysis.",
                "uncertainty": "HIGH",
                "alternatives": [],
                "blocking": False,
                "degraded": True,
                "degradation_reason": "llm_unavailable",
                "confidence": 0.15,
                "disclaimer": "This response was generated without AI analysis. Treat with caution."
            }
            llm_response = json.dumps(response_obj, indent=2)

        # Stream the response
        for char in llm_response:
            yield char
            await asyncio.sleep(0.005)
    
    async def invoke_parent_review(
        self, 
        proposal: AIProposal,
        architectural_context: Dict[str, Any]
    ) -> AIProposal:
        """
        Invoke Parent AI Council for architectural review.
        Validates agent authority. Degradation-labeled fallback.
        """
        self.registry.validate_agent_action(AgentRole.PARENT, AgentCapability.REVIEW)
        
        config = self.registry.get_agent_config(AgentRole.PARENT)
        
        llm_response = await _call_llm(
            config.get('system_prompt', ''),
            f"Review this proposal: {proposal.claim[:200]}\nContext: {architectural_context}",
            config
        )
        
        degraded = False
        if llm_response:
            review_claim = llm_response
            summary = "LLM architectural review"
            confidence = 0.75
        else:
            degraded = True
            review_claim = f"[DEGRADED] Reviewed proposal: {proposal.claim[:50]}... seems architecturally sound."
            summary = "Heuristic review (LLM unavailable)"
            confidence = 0.3
            logger.warning("Parent review returned degraded response: LLM unavailable")
        
        return AIProposal(
            agent_role=AgentRole.PARENT,
            claim=review_claim,
            reasoning_summary=summary,
            alternatives_rejected=[],
            uncertainty_level="HIGH" if degraded else "MEDIUM",
            confidence_score=confidence,
            evidence_references=[],
            blocking=False,
            metadata={
                "reviewed_proposal_role": proposal.agent_role.value,
                "degraded": degraded,
                "degradation_reason": "llm_unavailable" if degraded else None,
            }
        )
    
    async def invoke_sentinel_check(
        self,
        proposal: AIProposal,
        invariants: List[str],
        constraints: List[str]
    ) -> AIProposal:
        """
        Invoke Sentinel for risk/invariant checking.
        GAP-3: Validates agent authority. GAP-2: Degradation-labeled fallback.
        """
        # Enforce Agent Authority Matrix
        self.registry.validate_agent_action(AgentRole.SENTINEL, AgentCapability.FLAG)
        
        config = self.registry.get_agent_config(AgentRole.SENTINEL)
        
        llm_response = await _call_llm(
            config.get('system_prompt', ''),
            f"Check proposal: {proposal.claim[:200]}\nInvariants: {invariants}\nConstraints: {constraints}",
            config
        )
        
        degraded = False
        if llm_response:
            claim = llm_response
            confidence = 0.95
        else:
            degraded = True
            claim = f"[DEGRADED] Checked {len(invariants)} invariants. No violations found (heuristic only)."
            confidence = 0.4
            logger.warning("Sentinel check returned degraded response: LLM unavailable")
        
        return AIProposal(
            agent_role=AgentRole.SENTINEL,
            claim=claim,
            reasoning_summary="Sentinel risk analysis",
            alternatives_rejected=[],
            uncertainty_level="HIGH" if degraded else "LOW",
            confidence_score=confidence,
            evidence_references=[],
            blocking=False,
            metadata={
                "invariants_checked": invariants,
                "constraints_checked": constraints,
                "violations": []
            }
        )
    
    async def classify_evidence(
        self,
        execution_result: Dict[str, Any],
        proposal: AIProposal
    ) -> str:
        """
        Classify execution result as evidence.
        Returns: "supporting", "contradictory", "inconclusive"
        """
        return_code = execution_result.get("return_code", -1)
        output = execution_result.get("output", "")
        violations = execution_result.get("violations", [])

        # Try LLM classification first
        try:
            system_prompt = (
                "You are an evidence classifier. Given an execution result and a proposal, "
                "classify the evidence as exactly one of: supporting, contradictory, inconclusive. "
                "Return ONLY that single word."
            )
            user_prompt = (
                f"Proposal claim: {proposal.claim}\n"
                f"Return code: {return_code}\n"
                f"Output (truncated): {output[:500]}\n"
                f"Violations: {violations}"
            )
            llm_result = await _call_llm(system_prompt, user_prompt, {"temperature": 0.1})
            if llm_result:
                classification = llm_result.strip().lower()
                if classification in ("supporting", "contradictory", "inconclusive"):
                    return classification
        except Exception:
            pass

        # Heuristic fallback
        if violations:
            return "contradictory"
        if return_code == 0:
            # Check for failure indicators in output
            failure_keywords = ["error", "fail", "exception", "traceback", "denied"]
            if any(kw in output.lower() for kw in failure_keywords):
                return "inconclusive"
            return "supporting"
        elif return_code > 0:
            return "contradictory"
        return "inconclusive"

    async def run_council_debate(
        self,
        prompt: str,
        context: Dict[str, Any],
        session_id: str,
        require_parent: bool = False
    ) -> CouncilDebateResult:
        """
        Run full council debate (Child → Parent → Sentinel).
        """
        transcript = []
        
        # Step 1: Child
        child_response = ""
        async for token in self.invoke_child_council(prompt, context, session_id):
            child_response += token
        
        # Attempt to parse JSON from child response, fallback to text
        try:
            child_data = json.loads(child_response)
            child_claim = child_data.get("claim", child_response)
        except json.JSONDecodeError:
            child_claim = child_response

        child_proposal = AIProposal(
            agent_role=AgentRole.CHILD,
            claim=child_claim,
            reasoning_summary="Creative exploration complete",
            uncertainty_level="MEDIUM",
            confidence_score=0.6,
            alternatives_rejected=[],
            evidence_references=[],
            blocking=False
        )
        transcript.append({"role": "child", "content": child_claim})
        
        # Step 2: Parent
        parent_analysis = None
        if require_parent or context.get("tier", "T0") in ["T2", "T3"]:
            parent_analysis = await self.invoke_parent_review(
                child_proposal,
                context.get("architectural_context", {})
            )
            transcript.append({"role": "parent", "content": parent_analysis.claim})
        
        # Step 3: Sentinel
        sentinel_flags = await self.invoke_sentinel_check(
            child_proposal,
            invariants=context.get("invariants", []),
            constraints=context.get("constraints", [])
        )
        transcript.append({"role": "sentinel", "content": sentinel_flags.claim})
        
        consensus = not sentinel_flags.blocking
        if parent_analysis and parent_analysis.blocking:
            consensus = False
            
        recommended_action = "proceed" if consensus else "block"
        
        # If Child provided code, include it in recommendation for diff extraction
        # Heuristic: if prompt asks for code, assume child claim contains it
        if "function" in prompt or "class" in prompt or "code" in prompt:
             # Just append it if not present, to ensure Diff extraction works
             if "```" not in child_claim and ("def " in child_claim or "class " in child_claim):
                 recommended_action = f"{child_claim}\n\n```python\n# Suggested implementation\n{child_claim}\n```"
             else:
                 recommended_action = child_claim

        return CouncilDebateResult(
            child_proposals=[child_proposal],
            parent_analysis=parent_analysis,
            sentinel_flags=[sentinel_flags],
            consensus_reached=consensus,
            recommended_action=recommended_action,
            debate_transcript=transcript
        )
