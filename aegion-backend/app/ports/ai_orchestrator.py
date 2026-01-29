"""
Aegion AI Orchestrator Port (Abstract Interface).

This is the hexagonal architecture PORT for AI agent orchestration.
Implementations (adapters) include:
- LangGraphOrchestrator (Phase 1-3)
- CustomPipelineOrchestrator (Phase 4+)

Doctrine: AI agents never have authority.
AI generates proposals; Archon decides.

Agent Types (from Agent Authority Doctrine):
- Child: Suggest, Draft, Explore
- Parent: Analyze, Review, Score
- Sentinel: Monitor, Alert, Flag
- Archon: Enforce, Persist, Reject (NOT an AI agent)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncIterator
from enum import Enum
from pydantic import BaseModel


class AgentRole(str, Enum):
    """AI agent roles with explicit capability boundaries."""
    CHILD = "child"      # Creative, exploratory
    PARENT = "parent"    # Architectural review
    SENTINEL = "sentinel"  # Risk monitoring


class AgentCapability(str, Enum):
    """Explicit agent capabilities (from Agent Authority Matrix)."""
    SUGGEST = "suggest"
    DRAFT = "draft"
    EXPLORE = "explore"
    ANALYZE = "analyze"
    REVIEW = "review"
    SCORE = "score"
    MONITOR = "monitor"
    ALERT = "alert"
    FLAG = "flag"


# Forbidden capabilities - no AI agent may have these
FORBIDDEN_CAPABILITIES = frozenset([
    "approve", "persist", "execute", "override_archon", "modify_memory"
])


class AIProposal(BaseModel):
    """Output from AI agents - always a proposal, never a decision."""
    agent_role: AgentRole
    claim: str
    reasoning_summary: str
    alternatives_rejected: List[str] = []
    uncertainty_level: str  # LOW, MEDIUM, HIGH
    confidence_score: float  # 0.0 - 1.0
    evidence_references: List[str] = []
    blocking: bool = False  # If True, AI recommends NOT proceeding
    metadata: Dict[str, Any] = {}


class CouncilDebateResult(BaseModel):
    """Result of multi-agent council debate."""
    child_proposals: List[AIProposal]
    parent_analysis: Optional[AIProposal]
    sentinel_flags: List[AIProposal]
    consensus_reached: bool
    recommended_action: str  # "proceed", "abstain", "block"
    debate_transcript: List[Dict[str, Any]]  # For audit


class AIOrchestrationPort(ABC):
    """
    Abstract interface for AI orchestration.
    Implements the Governed Debate Pipeline.
    """
    
    @abstractmethod
    async def invoke_child_council(
        self, 
        prompt: str, 
        context: Dict[str, Any],
        session_id: str
    ) -> AsyncIterator[str]:
        """
        Invoke Child AI Council for creative exploration.
        Streams response tokens.
        """
        pass
    
    @abstractmethod
    async def invoke_parent_review(
        self, 
        proposal: AIProposal,
        architectural_context: Dict[str, Any]
    ) -> AIProposal:
        """
        Invoke Parent AI Council for architectural review.
        Returns analysis with risk scoring.
        """
        pass
    
    @abstractmethod
    async def invoke_sentinel_check(
        self,
        proposal: AIProposal,
        invariants: List[str],
        constraints: List[str]
    ) -> AIProposal:
        """
        Invoke Sentinel for risk/invariant checking.
        Returns flags and alerts.
        """
        pass
    
    @abstractmethod
    async def run_council_debate(
        self,
        prompt: str,
        context: Dict[str, Any],
        session_id: str,
        require_parent: bool = False
    ) -> CouncilDebateResult:
        """
        Run full council debate (Child → Parent → Sentinel).
        This is the main entry point for governed AI reasoning.
        """
        pass
    
    @abstractmethod
    async def classify_evidence(
        self,
        execution_result: Dict[str, Any],
        proposal: AIProposal
    ) -> str:
        """
        Classify execution result as evidence.
        Returns: "supporting", "contradictory", "inconclusive"
        """
        pass


class AgentRegistryPort(ABC):
    """
    Registry for agent capabilities and configurations.
    Enforces the Agent Authority Matrix.
    """
    
    @abstractmethod
    def get_allowed_capabilities(self, role: AgentRole) -> frozenset[AgentCapability]:
        """Get allowed capabilities for an agent role."""
        pass
    
    @abstractmethod
    def validate_agent_action(
        self, role: AgentRole, capability: AgentCapability
    ) -> bool:
        """Check if agent can perform an action. Raises if forbidden."""
        pass
    
    @abstractmethod
    def get_agent_config(self, role: AgentRole) -> Dict[str, Any]:
        """Get configuration for an agent (model, temperature, etc.)."""
        pass
