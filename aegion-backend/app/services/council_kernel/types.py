"""
Core types for the AEGION Council Kernel (ACK).

Enhanced shared type system used across engine, router, cascade, cache,
peer review, debate, persona, rubric, and evidence modules.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Council classification
# ──────────────────────────────────────────────────────────────────────────────

class CouncilType(str, Enum):
    CHILD = "child"                 # Developer assistance (T0/T1)
    DISTILLATION = "distillation"   # Session artifact processing
    PARENT = "parent"               # Architectural decisions (T2/T3)
    SENTINEL = "sentinel"           # Continuous security/risk monitoring


class CouncilProfile(str, Enum):
    """Determines how many models and rounds we use — drives cost."""
    TRIVIAL = "trivial"    # 1 model, 1 round   — cache hit or ultra-simple
    SIMPLE = "simple"      # 2 models, 1 round
    MODERATE = "moderate"  # 3 models, 2 rounds
    COMPLEX = "complex"    # 4 models, 3 rounds
    CRITICAL = "critical"  # 5+ models, 3 rounds + persona prompts + frontier models


# ──────────────────────────────────────────────────────────────────────────────
# Data transfer objects
# ──────────────────────────────────────────────────────────────────────────────

class ModelResponse(BaseModel):
    """Single model's response within a council round."""
    model: str
    provider: str
    response: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    # Enhanced metadata
    tier: int = 2                                     # Model quality tier (1=budget, 4=frontier)
    cascade_level: Optional[int] = None               # If from cascade, which tier was used
    was_compressed: bool = False                       # Whether prompt was compressed pre-call
    context_window: int = 0                            # Max tokens the model supports


class CouncilResult(BaseModel):
    """Aggregated result returned to callers after a full council run."""
    council_type: CouncilType
    profile: CouncilProfile
    query: str
    synthesis: str
    individual_responses: List[ModelResponse] = Field(default_factory=list)
    consensus_score: float = Field(ge=0.0, le=1.0)
    dissenting_views: List[str] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_latency_ms: int = 0
    cache_hit: bool = False
    models_used: List[str] = Field(default_factory=list)
    providers_used: List[str] = Field(default_factory=list)
    rounds_completed: int = 1
    # Enhanced metadata
    evidence_used: bool = False                            # Whether workspace evidence was gathered
    prompt_compressed: bool = False                        # Whether prompt compression was applied
    tokens_saved_by_compression: int = 0                   # Tokens saved via LLMLingua
    estimated_savings_vs_frontier: float = 0.0             # Cost savings compared to using frontier models
    rubric_scores: Optional[Dict[str, Any]] = None         # If rubric scoring was applied
    debate_history: Optional[List[Dict[str, Any]]] = None  # If debate engine was used
    persona_perspectives: Optional[List[Dict[str, Any]]] = None  # If persona engine was used


class CostSummary(BaseModel):
    """Aggregated cost telemetry for a workspace."""
    workspace_id: str
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    cost_by_provider: Dict[str, float] = Field(default_factory=dict)
    cost_by_purpose: Dict[str, float] = Field(default_factory=dict)
    estimated_savings_usd: float = 0.0  # How much was saved by cascade + cache vs always-frontier


# ──────────────────────────────────────────────────────────────────────────────
# Engine health (circuit breaker aggregation)
# ──────────────────────────────────────────────────────────────────────────────

class EngineHealth(str, Enum):
    """
    Aggregate health status for the entire council engine.

    Derived from individual provider circuit breaker states:
        OPERATIONAL  — all providers healthy (all circuits CLOSED, no recent failures)
        DEGRADED     — some providers failing or in HALF_OPEN
        CRITICAL     — majority of providers OPEN
        UNAVAILABLE  — all providers OPEN, no requests can be served
    """
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


class EngineStatus(BaseModel):
    """
    Full engine health report returned by GET /health/engine.

    Includes provider-level health + aggregate statistics for monitoring
    dashboards and the Cognitive Sidebar OS system state strip.
    """
    health: EngineHealth
    active_providers: int = 0       # Providers not in OPEN state
    total_providers: int = 0        # Total known providers
    provider_health: Dict[str, Any] = Field(default_factory=dict)
    cache_entries: int = 0          # In-process cache size
    uptime_s: float = 0.0           # Engine uptime
    total_consultations: int = 0    # Total consult() calls since startup
    total_errors: int = 0           # Total errors since startup


# ──────────────────────────────────────────────────────────────────────────────
# Argument Mining — Stab & Gurevych, 2017
# ──────────────────────────────────────────────────────────────────────────────

class ArgumentNode(BaseModel):
    """
    Structured debate output node — Argument Mining.

    Reference: Stab & Gurevych, 2017 — "Parsing Argumentation Structures
               in Persuasive Essays"

    Each node represents one agent's contribution in a debate round,
    decomposed into claim + evidence + relational links to other arguments.
    """
    id: str                                     # Unique node ID (e.g., "arg-001")
    agent: str                                  # Model/provider that produced this
    claim: str                                  # The main claim or position
    evidence: List[str] = Field(default_factory=list)    # Supporting evidence
    rebuts: List[str] = Field(default_factory=list)      # IDs of arguments this rebuts
    supports: List[str] = Field(default_factory=list)    # IDs of arguments this supports
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    round: int = 1                              # Debate round number

