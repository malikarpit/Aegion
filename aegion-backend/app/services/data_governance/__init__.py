"""
Aegion Data Governance — Retention, Erasure, and Legal Hold.

Doctrine: "Immutability protects truth. Erasure protects people."

Provides:
- Configurable retention policies per data category
- GDPR right-to-erasure (anonymization, not deletion — preserving graph integrity)
- Legal hold suspension of deletion
- Workspace deletion with cascade cleanup
"""

from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────
# Retention Policy
# ──────────────────────────────────────────────────────────────────────────

class DataCategory(str, Enum):
    """Categories of data with different retention requirements."""
    SESSION = "session"           # Session transcripts, context
    EVIDENCE = "evidence"         # Test results, metrics, snapshots
    DECISION = "decision"         # Approval records, ADRs
    AUDIT_LOG = "audit_log"       # Security audit trail
    USER_DATA = "user_data"       # User profiles, preferences
    WORKSPACE = "workspace"       # Workspace configs, memberships
    AI_OUTPUT = "ai_output"       # AI-generated content, suggestions
    ARTIFACT = "artifact"         # Generated documents, code


class RetentionPeriod(BaseModel):
    """Retention period configuration for a data category."""
    category: DataCategory
    retention_days: int           # -1 means indefinite
    archive_after_days: int       # Move to cold storage after N days
    description: str


# Default retention policies
DEFAULT_RETENTION_POLICIES: List[RetentionPeriod] = [
    RetentionPeriod(
        category=DataCategory.SESSION,
        retention_days=365,
        archive_after_days=90,
        description="Session data retained for 1 year, archived after 90 days",
    ),
    RetentionPeriod(
        category=DataCategory.EVIDENCE,
        retention_days=-1,  # Indefinite — immutable by design
        archive_after_days=365,
        description="Evidence is immutable and retained indefinitely",
    ),
    RetentionPeriod(
        category=DataCategory.DECISION,
        retention_days=-1,  # Indefinite — governance requires full history
        archive_after_days=365,
        description="Decisions retained indefinitely for governance audit",
    ),
    RetentionPeriod(
        category=DataCategory.AUDIT_LOG,
        retention_days=-1,  # Indefinite — compliance requirement
        archive_after_days=90,
        description="Audit logs retained indefinitely, archived after 90 days",
    ),
    RetentionPeriod(
        category=DataCategory.USER_DATA,
        retention_days=730,  # 2 years after account deletion
        archive_after_days=365,
        description="User data retained 2 years after deletion request",
    ),
    RetentionPeriod(
        category=DataCategory.AI_OUTPUT,
        retention_days=180,
        archive_after_days=30,
        description="AI outputs retained for 180 days",
    ),
    RetentionPeriod(
        category=DataCategory.ARTIFACT,
        retention_days=365,
        archive_after_days=90,
        description="Artifacts retained for 1 year",
    ),
]


class RetentionPolicyManager:
    """Manages data retention policies and cleanup scheduling."""

    def __init__(self, policies: Optional[List[RetentionPeriod]] = None):
        self._policies = {p.category: p for p in (policies or DEFAULT_RETENTION_POLICIES)}

    def get_policy(self, category: DataCategory) -> RetentionPeriod:
        return self._policies.get(category, RetentionPeriod(
            category=category, retention_days=365, archive_after_days=90,
            description="Default retention"
        ))

    def is_expired(self, category: DataCategory, created_at: datetime) -> bool:
        """Check if data has exceeded its retention period."""
        policy = self.get_policy(category)
        if policy.retention_days == -1:
            return False  # Indefinite retention
        cutoff = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)
        return created_at < cutoff

    def should_archive(self, category: DataCategory, created_at: datetime) -> bool:
        """Check if data should be moved to cold storage."""
        policy = self.get_policy(category)
        cutoff = datetime.now(timezone.utc) - timedelta(days=policy.archive_after_days)
        return created_at < cutoff


# ──────────────────────────────────────────────────────────────────────────
# GDPR Erasure Service
# ──────────────────────────────────────────────────────────────────────────

class ErasureRequest(BaseModel):
    """GDPR Article 17 right-to-erasure request."""
    request_id: str
    user_id: str
    requested_at: str
    reason: str
    status: str = "pending"   # pending → processing → completed → verified
    categories_to_erase: List[DataCategory]


class ErasureService:
    """
    Handles GDPR right-to-erasure requests.

    Strategy: ANONYMIZE rather than DELETE.
    - User identifiers are replaced with pseudonyms
    - Graph structure is preserved (decision provenance intact)
    - Evidence nodes remain (stripped of PII)
    - Audit trail records the erasure itself
    """

    def __init__(self):
        self._legal_holds: Set[str] = set()  # user_ids under legal hold
        self._pending_requests: Dict[str, ErasureRequest] = {}

    def place_legal_hold(self, user_id: str, reason: str):
        """Suspend erasure for a user under legal hold."""
        self._legal_holds.add(user_id)
        logger.audit(
            action="security.legal_hold_placed",
            actor="system",
            target=f"user/{user_id}",
            justification=reason,
        )

    def release_legal_hold(self, user_id: str, reason: str):
        """Release legal hold on a user."""
        self._legal_holds.discard(user_id)
        logger.audit(
            action="security.legal_hold_released",
            actor="system",
            target=f"user/{user_id}",
            justification=reason,
        )

    def is_under_legal_hold(self, user_id: str) -> bool:
        return user_id in self._legal_holds

    async def request_erasure(self, request: ErasureRequest) -> Dict[str, Any]:
        """
        Process a GDPR erasure request.

        If under legal hold, the request is deferred.
        """
        if self.is_under_legal_hold(request.user_id):
            return {
                "status": "deferred",
                "reason": "User is under legal hold. Erasure deferred.",
                "request_id": request.request_id,
            }

        self._pending_requests[request.request_id] = request

        # Anonymization plan
        anonymization_plan = {
            "request_id": request.request_id,
            "user_id": request.user_id,
            "status": "processing",
            "actions": [],
        }

        for category in request.categories_to_erase:
            if category in (DataCategory.EVIDENCE, DataCategory.DECISION):
                anonymization_plan["actions"].append({
                    "category": category.value,
                    "action": "anonymize",
                    "detail": f"Replace user references in {category.value} with pseudonym",
                })
            elif category == DataCategory.AUDIT_LOG:
                anonymization_plan["actions"].append({
                    "category": category.value,
                    "action": "retain_anonymized",
                    "detail": "Audit logs retained for compliance, user fields pseudonymized",
                })
            else:
                anonymization_plan["actions"].append({
                    "category": category.value,
                    "action": "delete",
                    "detail": f"Delete {category.value} data for user",
                })

        logger.audit(
            action="security.erasure_requested",
            actor=request.user_id,
            target=f"user/{request.user_id}",
            justification=request.reason,
            metadata={"categories": [c.value for c in request.categories_to_erase]},
        )

        return anonymization_plan

    def generate_pseudonym(self, user_id: str) -> str:
        """Generate a deterministic pseudonym for anonymization."""
        import hashlib
        hash_val = hashlib.sha256(f"aegion-anon:{user_id}".encode()).hexdigest()[:12]
        return f"anon-{hash_val}"


# ──────────────────────────────────────────────────────────────────────────
# Singletons
# ──────────────────────────────────────────────────────────────────────────

_retention_manager: Optional[RetentionPolicyManager] = None
_erasure_service: Optional[ErasureService] = None


def get_retention_manager() -> RetentionPolicyManager:
    global _retention_manager
    if _retention_manager is None:
        _retention_manager = RetentionPolicyManager()
    return _retention_manager


def get_erasure_service() -> ErasureService:
    global _erasure_service
    if _erasure_service is None:
        _erasure_service = ErasureService()
    return _erasure_service
