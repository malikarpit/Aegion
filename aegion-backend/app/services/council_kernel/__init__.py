"""AEGION Council Kernel (ACK) — Multi-model AI council orchestration.

Phases 8-18, 46-51, 76-77: Core Intelligence Layer

Modules:
  - engine.py          : CouncilEngine orchestrator (Phase 8)
  - model_router.py    : 9-provider LLM abstraction with 50+ models (Phase 9)
  - cascade.py         : FrugalGPT 8-tier cost cascade (Phase 10)
  - cache.py           : pgvector semantic cache (Phase 11)
  - compressor.py      : LLMLingua-2 prompt compression (Phase 12)
  - peer_review.py     : 3-stage adversarial review (Phase 13)
  - debate.py          : Anti-sycophancy structured debate (Phase 14)
  - rubric.py          : Weighted rubric scoring (Phase 15)
  - persona.py         : 6 AEGION expert personas (Phase 16)
  - evidence.py        : Workspace evidence manager (Phase 17)
  - constitution.py    : Constitutional AI governance (Phase 46)
  - reflector.py       : Cognitive debate pathology detection (Phase 47)
  - red_team.py        : Adversarial output validation (Phase 48)
  - temporal_memory.py : Historical decision context (Phase 49)
  - orchestrator.py    : Cross-council sub-council spawning (Phase 50)
  - analytics.py       : Council-specific analytics engine (Phase 51)
  - prompt_gateway.py  : Cheap query pre-processor & intent clarifier (Phase 76)
  - adaptive_council.py: Right-size model count from complexity (Phase 77)
  - circuit_breaker.py : Per-provider resilience state machine
  - types.py           : Shared type system

Providers: OpenAI, Anthropic, DeepSeek, Google Gemini, xAI/Grok,
           Mistral, Cohere, Ollama, Custom (any HTTP API)
"""

from .engine import CouncilEngine, get_council_engine
from .model_router import ModelRouter, MODEL_CATALOG, ModelSpec, ModelCapability
from .cascade import LLMCascade
from .circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    ProviderHealth,
    get_circuit_breaker_registry,
)
from .types import (
    CouncilType, CouncilProfile, ModelResponse, CouncilResult,
    EngineHealth, EngineStatus,
)
from .prompt_gateway import PromptGateway, prompt_gateway
from .adaptive_council import AdaptiveCouncil, adaptive_council

__all__ = [
    "CouncilEngine",
    "get_council_engine",
    "ModelRouter",
    "MODEL_CATALOG",
    "ModelSpec",
    "ModelCapability",
    "LLMCascade",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
    "ProviderHealth",
    "get_circuit_breaker_registry",
    "CouncilType",
    "CouncilProfile",
    "ModelResponse",
    "CouncilResult",
    "EngineHealth",
    "EngineStatus",
    "PromptGateway",
    "prompt_gateway",
    "AdaptiveCouncil",
    "adaptive_council",
]
