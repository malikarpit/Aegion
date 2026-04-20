"""
Aegion Merkle Audit Tree — Cryptographic Inclusion Proofs.

Doctrine: "Every audit trail is provable. Every event has a proof."

Builds a Merkle tree over audit event hashes so that:
- Any single event can be proven to exist in the log (inclusion proof)
- The entire log integrity is captured in a single root hash
- Root hashes can be anchored externally (blockchain, signed receipt, etc.)

Integrates with the existing AuditChain (linear hash chain) to provide
a complementary tree-based verification layer.
"""

import hashlib
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...contracts.audit_event import AuditEvent
from ...core.logging import logger


# ────────────────────────────────────────────────
# Data Structures
# ────────────────────────────────────────────────


@dataclass(frozen=True)
class MerkleProofStep:
    """One step in a Merkle inclusion proof."""
    hash: str
    position: str  # "left" or "right" — where the sibling is


@dataclass(frozen=True)
class MerkleInclusionProof:
    """
    Complete inclusion proof for a single audit event.

    To verify: start with leaf_hash, walk the path hashing
    with each sibling, and compare final result to root_hash.
    """
    event_id: str
    leaf_hash: str
    root_hash: str
    tree_size: int
    path: List[MerkleProofStep]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "leaf_hash": self.leaf_hash,
            "root_hash": self.root_hash,
            "tree_size": self.tree_size,
            "path": [{"hash": s.hash, "position": s.position} for s in self.path],
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MerkleAnchor:
    """Record of a root hash anchoring event."""
    root_hash: str
    tree_size: int
    anchored_at: datetime
    anchor_type: str  # "local" | "external" | "signed_receipt"
    anchor_ref: Optional[str] = None  # e.g. transaction hash, receipt ID
    metadata: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────
# Merkle Tree
# ────────────────────────────────────────────────


class MerkleAuditTree:
    """
    Append-only Merkle tree over audit event hashes.

    Usage:
        tree = MerkleAuditTree()
        tree.add_leaf(event.event_hash)  # for each sealed event
        proof = tree.get_inclusion_proof(event_id, event.event_hash)
        assert MerkleAuditTree.verify_proof(proof)
    """

    def __init__(self):
        self._leaves: List[str] = []           # Leaf hashes (event hashes)
        self._leaf_ids: List[str] = []         # Corresponding event IDs
        self._tree: List[List[str]] = [[]]     # tree[0] = leaves, tree[k] = level k
        self._root: Optional[str] = None
        self._anchors: List[MerkleAnchor] = []
        self._dirty = True                     # Tree needs rebuild

    # ── Public API ───────────────────────────────

    def add_leaf(self, event_id: str, event_hash: str) -> int:
        """
        Append an event hash as a new leaf.

        Returns the leaf index (0-based).
        """
        self._leaves.append(event_hash)
        self._leaf_ids.append(event_id)
        self._dirty = True
        return len(self._leaves) - 1

    def add_event(self, event: AuditEvent) -> int:
        """Convenience: add an AuditEvent (must be sealed with event_hash)."""
        if not event.event_hash:
            raise ValueError(f"Event {event.event_id} has no event_hash — seal it first")
        return self.add_leaf(event.event_id, event.event_hash)

    @property
    def root_hash(self) -> Optional[str]:
        """Get the current Merkle root hash."""
        if self._dirty:
            self._rebuild()
        return self._root

    @property
    def size(self) -> int:
        return len(self._leaves)

    def get_inclusion_proof(
        self, event_id: str, leaf_hash: str
    ) -> MerkleInclusionProof:
        """
        Generate an inclusion proof for a leaf.

        The proof is a list of sibling hashes that, when hashed together
        with the leaf, reproduces the root.
        """
        if self._dirty:
            self._rebuild()

        try:
            index = self._leaves.index(leaf_hash)
        except ValueError:
            raise ValueError(f"Leaf hash not found in tree: {leaf_hash[:16]}...")

        path: List[MerkleProofStep] = []

        for level in range(len(self._tree) - 1):
            layer = self._tree[level]
            is_right = index % 2 == 1
            sibling_index = index - 1 if is_right else index + 1

            if sibling_index < len(layer):
                sibling_hash = layer[sibling_index]
                position = "left" if is_right else "right"
                path.append(MerkleProofStep(hash=sibling_hash, position=position))
            else:
                # Odd-length level: last node was duplicated during tree build.
                # Mirror that by using the node itself as its right sibling.
                sibling_hash = layer[index]
                path.append(MerkleProofStep(hash=sibling_hash, position="right"))

            index //= 2

        return MerkleInclusionProof(
            event_id=event_id,
            leaf_hash=leaf_hash,
            root_hash=self._root or "",
            tree_size=len(self._leaves),
            path=path,
        )

    @staticmethod
    def verify_proof(proof: MerkleInclusionProof) -> bool:
        """
        Verify a Merkle inclusion proof.

        Walks the proof path, hashing at each step, and checks
        the final hash matches the root.
        """
        current = proof.leaf_hash

        for step in proof.path:
            if step.position == "left":
                # Sibling is on the left
                current = MerkleAuditTree._hash_pair(step.hash, current)
            else:
                # Sibling is on the right
                current = MerkleAuditTree._hash_pair(current, step.hash)

        return current == proof.root_hash

    def anchor_root(
        self,
        anchor_type: str = "local",
        anchor_ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MerkleAnchor:
        """
        Record the current root hash as an anchor point.

        This produces a receipt that can be stored externally
        (e.g., signed, published to a blockchain, etc.)
        """
        if self._dirty:
            self._rebuild()

        anchor = MerkleAnchor(
            root_hash=self._root or "",
            tree_size=len(self._leaves),
            anchored_at=datetime.now(timezone.utc),
            anchor_type=anchor_type,
            anchor_ref=anchor_ref,
            metadata=metadata or {},
        )
        self._anchors.append(anchor)

        logger.audit(
            action="MERKLE_ROOT_ANCHORED",
            actor="merkle_audit_tree",
            target=anchor.root_hash[:16],
            justification=(
                f"Root anchored at size {anchor.tree_size}, "
                f"type={anchor_type}"
            ),
        )

        # ── Persist anchor to Supabase audit_log ──
        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("audit_log").insert({
                "event_type": "MERKLE_ROOT_ANCHORED",
                "actor_id": "merkle_audit_tree",
                "event_hash": anchor.root_hash,
                "metadata": {
                    "tree_size": anchor.tree_size,
                    "anchor_type": anchor_type,
                    "anchor_ref": anchor_ref,
                },
            }).execute()
        except Exception as exc:
            logger.warning(f"Merkle anchor persist failed (non-fatal): {exc}")

        return anchor

    def verify_tree_integrity(self) -> Tuple[bool, List[str]]:
        """
        Full integrity check — rebuild from leaves and compare.

        Returns (is_valid, errors).
        """
        if not self._leaves:
            return True, []

        errors = []
        self._rebuild()

        # Verify root exists
        if not self._root:
            errors.append("Tree has leaves but no root hash")

        # Verify against last anchor
        if self._anchors:
            last = self._anchors[-1]
            if last.tree_size == len(self._leaves):
                if last.root_hash != self._root:
                    errors.append(
                        f"Root hash mismatch with anchor: "
                        f"expected {last.root_hash[:16]}, "
                        f"got {(self._root or '')[:16]}"
                    )

        # Verify every leaf can produce a valid inclusion proof
        sample_size = min(len(self._leaves), 10)  # Spot check
        import random
        indices = random.sample(range(len(self._leaves)), sample_size)
        for i in indices:
            proof = self.get_inclusion_proof(self._leaf_ids[i], self._leaves[i])
            if not self.verify_proof(proof):
                errors.append(f"Inclusion proof failed for leaf {i}")

        return len(errors) == 0, errors

    def get_anchors(self) -> List[Dict[str, Any]]:
        """Return all recorded anchors."""
        return [
            {
                "root_hash": a.root_hash,
                "tree_size": a.tree_size,
                "anchored_at": a.anchored_at.isoformat(),
                "anchor_type": a.anchor_type,
                "anchor_ref": a.anchor_ref,
            }
            for a in self._anchors
        ]

    def export_state(self) -> Dict[str, Any]:
        """Export tree state for persistence."""
        return {
            "leaves": list(self._leaves),
            "leaf_ids": list(self._leaf_ids),
            "root": self.root_hash,
            "size": len(self._leaves),
            "anchors": self.get_anchors(),
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        """Restore tree from persisted state."""
        self._leaves = list(state.get("leaves", []))
        self._leaf_ids = list(state.get("leaf_ids", []))
        self._dirty = True
        # Anchors
        for a in state.get("anchors", []):
            self._anchors.append(MerkleAnchor(
                root_hash=a["root_hash"],
                tree_size=a["tree_size"],
                anchored_at=datetime.fromisoformat(a["anchored_at"]),
                anchor_type=a["anchor_type"],
                anchor_ref=a.get("anchor_ref"),
            ))
        if self._leaves:
            self._rebuild()

    # ── Internal ─────────────────────────────────

    def _rebuild(self) -> None:
        """Rebuild the tree from leaves."""
        if not self._leaves:
            self._tree = [[]]
            self._root = None
            self._dirty = False
            return

        # Level 0 = leaves
        self._tree = [list(self._leaves)]

        # Build each level
        current = self._tree[0]
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else left  # Duplicate odd node
                next_level.append(self._hash_pair(left, right))
            self._tree.append(next_level)
            current = next_level

        self._root = current[0] if current else None
        self._dirty = False

    @staticmethod
    def _hash_pair(left: str, right: str) -> str:
        """Hash two children together to produce parent node."""
        combined = (left + right).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()


# ────────────────────────────────────────────────
# Singleton
# ────────────────────────────────────────────────

_merkle_tree: Optional[MerkleAuditTree] = None


def get_merkle_tree() -> MerkleAuditTree:
    """Get the global MerkleAuditTree instance."""
    global _merkle_tree
    if _merkle_tree is None:
        _merkle_tree = MerkleAuditTree()
    return _merkle_tree
