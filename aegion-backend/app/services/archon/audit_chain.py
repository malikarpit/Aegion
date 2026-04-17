"""
Aegion Audit Chain — Tamper-Resistant Log Integrity (P2-018).

Doctrine: "Every trace is chained. Every chain is signed."

Provides:
- SHA-256 hash chaining between consecutive audit events
- HMAC-SHA256 signing using a server-side secret
- Chain verification to detect gaps or tampering
"""

import hashlib
import hmac
from typing import List, Optional, Tuple

from ...contracts.audit_event import AuditEvent
from ...core.config import settings
from ...core.logging import logger


class AuditChain:
    """
    Append-only audit chain with hash linking and HMAC signing.

    Each event stores:
    - prev_hash: SHA-256 of the *previous* event's event_hash (genesis = None)
    - event_hash: SHA-256 of this event's canonical content + prev_hash
    - signature: HMAC-SHA256(event_hash, signing_key)
    """

    def __init__(self, signing_key: Optional[str] = None):
        self._signing_key = (signing_key or settings.audit_signing_key).encode("utf-8")
        self._last_hash: Optional[str] = None
        # Merkle tree overlay
        from .merkle_audit import MerkleAuditTree
        self._merkle_tree = MerkleAuditTree()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, event: AuditEvent) -> AuditEvent:
        """
        Seal an event into the chain.

        Returns a new AuditEvent with prev_hash, event_hash, and signature set.
        The original event is not mutated (frozen model).
        """
        # 1. Link to previous
        prev_hash = self._last_hash

        # 2. Build a temporary event with prev_hash set so canonical_bytes includes it
        linked = event.model_copy(update={"prev_hash": prev_hash})

        # 3. Compute content hash
        event_hash = hashlib.sha256(linked.canonical_bytes()).hexdigest()

        # 4. Sign
        signature = hmac.new(
            self._signing_key,
            event_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # 5. Produce sealed event
        sealed = linked.model_copy(update={
            "event_hash": event_hash,
            "signature": signature,
        })

        # 6. Advance chain head
        self._last_hash = event_hash

        # 7. Add to Merkle tree
        self._merkle_tree.add_leaf(event.event_id, event_hash)

        logger.debug(
            "Audit event sealed into chain",
            event_id=event.event_id,
            event_hash=event_hash[:12],
            prev_hash=(prev_hash or "genesis")[:12],
        )

        # ── Persist to Supabase audit_log (best-effort) ──
        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("audit_log").insert({
                "workspace_id": getattr(sealed, 'workspace_id', None),
                "event_type": sealed.action.value if hasattr(sealed.action, 'value') else str(sealed.action),
                "actor_id": sealed.actor_id,
                "target_type": getattr(sealed, 'target_type', None),
                "target_id": getattr(sealed, 'target_id', None),
                "event_hash": event_hash,
                "prev_hash": prev_hash,
                "signature": signature,
                "metadata": {
                    "event_id": sealed.event_id,
                    "justification": getattr(sealed, 'justification', None),
                    "evidence_ids": getattr(sealed, 'evidence_ids', []),
                },
            }).execute()
        except Exception as exc:
            logger.warning(f"Audit log persist failed (non-fatal): {exc}")

        return sealed

    def verify_single(self, event: AuditEvent) -> bool:
        """
        Verify that an event's hash and signature are self-consistent.

        Does NOT check chain ordering — use verify_chain() for that.
        """
        if not event.event_hash:
            return False

        # Recompute hash from canonical content
        expected_hash = hashlib.sha256(event.canonical_bytes()).hexdigest()
        if expected_hash != event.event_hash:
            return False

        # Verify HMAC signature
        if event.signature:
            expected_sig = hmac.new(
                self._signing_key,
                event.event_hash.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_sig, event.signature):
                return False

        return True

    def verify_chain(self, events: List[AuditEvent]) -> Tuple[bool, List[str]]:
        """
        Walk a list of events and verify hash-chain integrity.

        Returns:
            (all_valid, broken_links)
            - all_valid: True if every link is intact
            - broken_links: list of event_ids where integrity broke
        """
        broken: List[str] = []
        prev_hash: Optional[str] = None

        for event in events:
            # 1. Self-consistency
            if not self.verify_single(event):
                broken.append(f"{event.event_id}:hash_mismatch")
                prev_hash = event.event_hash
                continue

            # 2. Chain link
            if event.prev_hash != prev_hash:
                broken.append(f"{event.event_id}:chain_break")

            prev_hash = event.event_hash

        return (len(broken) == 0, broken)

    def reset(self, last_hash: Optional[str] = None) -> None:
        """Reset or restore chain head (e.g. after loading from persistence)."""
        self._last_hash = last_hash

    # ------------------------------------------------------------------
    # Merkle Tree Integration
    # ------------------------------------------------------------------

    def get_merkle_proof(self, event: AuditEvent):
        """
        Get a Merkle inclusion proof for a sealed event.

        Returns a MerkleInclusionProof that can be independently verified.
        """
        if not event.event_hash:
            raise ValueError(f"Event {event.event_id} has no event_hash")
        return self._merkle_tree.get_inclusion_proof(
            event.event_id, event.event_hash
        )

    def anchor_merkle_root(
        self,
        anchor_type: str = "local",
        anchor_ref: Optional[str] = None,
    ):
        """Anchor the current Merkle root hash."""
        return self._merkle_tree.anchor_root(
            anchor_type=anchor_type,
            anchor_ref=anchor_ref,
        )

    @property
    def merkle_root(self) -> Optional[str]:
        """Current Merkle root hash."""
        return self._merkle_tree.root_hash

    @property
    def merkle_tree(self):
        """Access the underlying MerkleAuditTree."""
        return self._merkle_tree


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_chain: Optional[AuditChain] = None


def get_audit_chain() -> AuditChain:
    """Get the global AuditChain instance."""
    global _chain
    if _chain is None:
        _chain = AuditChain()
    return _chain
