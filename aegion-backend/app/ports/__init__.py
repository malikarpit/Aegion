# Aegion Ports (Hexagonal Architecture Interfaces)
#
# These are abstract interfaces that define HOW the application
# communicates with external systems. Concrete implementations
# (adapters) live in app/adapters/.
#
# Migration Path:
# - Phase 1-2: Firestore, Firebase, LangGraph
# - Phase 3-4: Postgres, Pub/Sub, Custom AI
# - Phase 5+: Neo4j, Kafka, Keycloak

from .database import (
    RepositoryPort,
    SessionRepositoryPort,
    DecisionRepositoryPort,
    UserRepositoryPort,
    EvidenceRepositoryPort,
    AuditLogRepositoryPort,
)

from .auth import (
    AuthProvider,
    AuthenticatedUser,
    AuthenticationPort,
    DeviceFlowPort,
    AuthorizationPort,
)

from .ai_orchestrator import (
    AgentRole,
    AgentCapability,
    FORBIDDEN_CAPABILITIES,
    AIProposal,
    CouncilDebateResult,
    AIOrchestrationPort,
    AgentRegistryPort,
)

from .events import (
    EventCategory,
    Event,
    EventHandler,
    EventBusPort,
    TransactionalOutboxPort,
    EventTypes,
)

from .storage import (
    StorageTier,
    StoredObject,
    StoragePort,
    ContentAddressedStore,
    ArtifactArchiver,
    compute_content_hash,
)

__all__ = [
    # Database
    "RepositoryPort",
    "SessionRepositoryPort",
    "DecisionRepositoryPort",
    "UserRepositoryPort",
    "EvidenceRepositoryPort",
    "AuditLogRepositoryPort",
    # Auth
    "AuthProvider",
    "AuthenticatedUser",
    "AuthenticationPort",
    "DeviceFlowPort",
    "AuthorizationPort",
    # AI
    "AgentRole",
    "AgentCapability",
    "FORBIDDEN_CAPABILITIES",
    "AIProposal",
    "CouncilDebateResult",
    "AIOrchestrationPort",
    "AgentRegistryPort",
    # Events
    "EventCategory",
    "Event",
    "EventHandler",
    "EventBusPort",
    "TransactionalOutboxPort",
    "EventTypes",
    # Storage
    "StorageTier",
    "StoredObject",
    "StoragePort",
    "ContentAddressedStore",
    "ArtifactArchiver",
    "compute_content_hash",
]
