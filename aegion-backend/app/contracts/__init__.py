# Aegion Data Contracts
#
# These are the core data models shared across all layers.
# Contracts define WHAT flows through the system.
# Ports define HOW the system communicates.

from .decision_intent import (
    ImpactLevel,
    ReversibilityLevel,
    DecisionTier,
    ReasoningPhase,
    DecisionIntent,
    calculate_tier,
)

from .uncertainty_level import (
    UncertaintyLevel,
    UncertaintySource,
    UncertaintyDeclaration,
    CognitiveLoad,
)

from .audit_event import (
    AuditCategory,
    AuditSeverity,
    AuditAction,
    AuditEvent,
    AuditEventBuilder,
)

from .evidence import (
    EvidenceClassification,
    EvidenceType,
    EvidenceSource,
    Evidence,
    EvidenceChain,
    EvidenceGate,
    validate_evidence_for_proposal,
)

# Phase 3: Causality & Execution
from .dependency_node import (
    NodeType,
    EdgeType,
    SourceType,
    DependencyNode,
    DependencyEdge,
    StalenessReport,
    DependencyQuery,
)

from .snapshot import (
    SnapshotType,
    SnapshotStatus,
    FileSnapshot,
    EnvironmentSnapshot,
    EvidenceSnapshot,
    SnapshotManifest,
    SnapshotCaptureRequest,
    compute_snapshot_id,
    compute_manifest_hash,
)

__all__ = [
    # Decision Intent
    "ImpactLevel",
    "ReversibilityLevel",
    "DecisionTier",
    "ReasoningPhase",
    "DecisionIntent",
    "calculate_tier",
    # Uncertainty
    "UncertaintyLevel",
    "UncertaintySource",
    "UncertaintyDeclaration",
    "CognitiveLoad",
    # Audit
    "AuditCategory",
    "AuditSeverity",
    "AuditAction",
    "AuditEvent",
    "AuditEventBuilder",
    # Evidence
    "EvidenceClassification",
    "EvidenceType",
    "EvidenceSource",
    "Evidence",
    "EvidenceChain",
    "EvidenceGate",
    "validate_evidence_for_proposal",
    # Phase 3: Dependency Graph
    "NodeType",
    "EdgeType",
    "SourceType",
    "DependencyNode",
    "DependencyEdge",
    "StalenessReport",
    "DependencyQuery",
    # Phase 3: Snapshots
    "SnapshotType",
    "SnapshotStatus",
    "FileSnapshot",
    "EnvironmentSnapshot",
    "EvidenceSnapshot",
    "SnapshotManifest",
    "SnapshotCaptureRequest",
    "compute_snapshot_id",
    "compute_manifest_hash",
]

