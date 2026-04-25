"""
Tests for Governance Hardening — Section 1.8.

Covers:
    Merkle Audit Tree:
        - Leaf addition and tree size
        - Root hash computation
        - Inclusion proof generation and verification
        - Proof verification with wrong data (negative test)
        - Tree integrity verification
        - State export/import roundtrip
        - Hash pair determinism
        - Power-of-two and non-power-of-two leaf counts
        - Singleton pattern

References:
    - Merkle, R. "A Digital Signature Based on a Conventional Encryption Function" (1987)
    - Certificate Transparency (RFC 6962) — Merkle audit proofs
"""

import hashlib
import pytest

from app.services.archon.merkle_audit import (
    MerkleAuditTree,
    MerkleInclusionProof,
    MerkleProofStep,
    MerkleAnchor,
    get_merkle_tree,
)


# ══════════════════════════════════════════════════════════════════════════════
# MERKLE TREE — BASICS
# ══════════════════════════════════════════════════════════════════════════════

class TestMerkleBasics:
    """Basic tree operations."""

    def test_empty_tree(self):
        tree = MerkleAuditTree()
        assert tree.size == 0
        assert tree.root_hash is None

    def test_single_leaf(self):
        tree = MerkleAuditTree()
        idx = tree.add_leaf("event-1", "abc123")
        assert idx == 0
        assert tree.size == 1
        assert tree.root_hash is not None

    def test_two_leaves(self):
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")
        tree.add_leaf("e2", "hash2")
        assert tree.size == 2
        # Root should be hash of hash1 + hash2
        expected_root = hashlib.sha256(("hash1" + "hash2").encode()).hexdigest()
        assert tree.root_hash == expected_root

    def test_four_leaves(self):
        """Power-of-two leaf count — balanced tree."""
        tree = MerkleAuditTree()
        for i in range(4):
            tree.add_leaf(f"e{i}", f"hash{i}")
        assert tree.size == 4
        assert tree.root_hash is not None

    def test_three_leaves(self):
        """Non-power-of-two — odd leaf gets duplicated."""
        tree = MerkleAuditTree()
        for i in range(3):
            tree.add_leaf(f"e{i}", f"hash{i}")
        assert tree.size == 3
        assert tree.root_hash is not None

    def test_root_changes_on_new_leaf(self):
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")
        root1 = tree.root_hash

        tree.add_leaf("e2", "hash2")
        root2 = tree.root_hash

        assert root1 != root2


# ══════════════════════════════════════════════════════════════════════════════
# INCLUSION PROOFS
# ══════════════════════════════════════════════════════════════════════════════

class TestInclusionProofs:
    """Merkle inclusion proof generation and verification."""

    def test_proof_single_leaf(self):
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")
        proof = tree.get_inclusion_proof("e1", "hash1")
        assert proof.leaf_hash == "hash1"
        assert proof.root_hash == tree.root_hash
        assert MerkleAuditTree.verify_proof(proof) is True

    def test_proof_two_leaves(self):
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")
        tree.add_leaf("e2", "hash2")

        proof1 = tree.get_inclusion_proof("e1", "hash1")
        proof2 = tree.get_inclusion_proof("e2", "hash2")

        assert MerkleAuditTree.verify_proof(proof1) is True
        assert MerkleAuditTree.verify_proof(proof2) is True

    def test_proof_eight_leaves(self):
        """All 8 leaves should produce valid proofs."""
        tree = MerkleAuditTree()
        hashes = [f"h{i}" for i in range(8)]
        for i, h in enumerate(hashes):
            tree.add_leaf(f"e{i}", h)

        for i, h in enumerate(hashes):
            proof = tree.get_inclusion_proof(f"e{i}", h)
            assert MerkleAuditTree.verify_proof(proof), f"Proof failed for leaf {i}"

    def test_invalid_proof_tampered_leaf(self):
        """Tampered leaf should fail verification."""
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")
        tree.add_leaf("e2", "hash2")

        proof = tree.get_inclusion_proof("e1", "hash1")
        # Tamper with the leaf hash
        tampered = MerkleInclusionProof(
            event_id=proof.event_id,
            leaf_hash="TAMPERED",
            root_hash=proof.root_hash,
            tree_size=proof.tree_size,
            path=proof.path,
        )
        assert MerkleAuditTree.verify_proof(tampered) is False

    def test_invalid_proof_tampered_root(self):
        """Tampered root should fail verification."""
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")

        proof = tree.get_inclusion_proof("e1", "hash1")
        tampered = MerkleInclusionProof(
            event_id=proof.event_id,
            leaf_hash=proof.leaf_hash,
            root_hash="FAKEROOTHASH",
            tree_size=proof.tree_size,
            path=proof.path,
        )
        assert MerkleAuditTree.verify_proof(tampered) is False

    def test_proof_not_found(self):
        """Non-existent leaf hash should raise ValueError."""
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "hash1")
        with pytest.raises(ValueError, match="Leaf hash not found"):
            tree.get_inclusion_proof("e99", "nonexistent")

    def test_proof_serialization(self):
        """Proof should serialize to dict cleanly."""
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "h1")
        tree.add_leaf("e2", "h2")
        proof = tree.get_inclusion_proof("e1", "h1")
        d = proof.to_dict()
        assert d["event_id"] == "e1"
        assert d["leaf_hash"] == "h1"
        assert "path" in d
        assert isinstance(d["path"], list)


# ══════════════════════════════════════════════════════════════════════════════
# TREE INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════

class TestTreeIntegrity:
    """Full tree integrity verification."""

    def test_empty_tree_valid(self):
        tree = MerkleAuditTree()
        is_valid, errors = tree.verify_tree_integrity()
        assert is_valid is True
        assert len(errors) == 0

    def test_valid_tree(self):
        tree = MerkleAuditTree()
        for i in range(5):
            tree.add_leaf(f"e{i}", f"h{i}")
        is_valid, errors = tree.verify_tree_integrity()
        assert is_valid is True
        assert len(errors) == 0


# ══════════════════════════════════════════════════════════════════════════════
# STATE EXPORT/IMPORT
# ══════════════════════════════════════════════════════════════════════════════

class TestStateRoundtrip:
    """Export/import state persistence."""

    def test_roundtrip(self):
        tree = MerkleAuditTree()
        for i in range(6):
            tree.add_leaf(f"e{i}", f"h{i}")
        original_root = tree.root_hash

        state = tree.export_state()

        tree2 = MerkleAuditTree()
        tree2.import_state(state)

        assert tree2.size == 6
        assert tree2.root_hash == original_root

    def test_export_has_required_fields(self):
        tree = MerkleAuditTree()
        tree.add_leaf("e1", "h1")
        state = tree.export_state()
        assert "leaves" in state
        assert "leaf_ids" in state
        assert "root" in state
        assert "size" in state


# ══════════════════════════════════════════════════════════════════════════════
# HASH PAIR
# ══════════════════════════════════════════════════════════════════════════════

class TestHashPair:
    """Low-level hash pair computation."""

    def test_deterministic(self):
        h1 = MerkleAuditTree._hash_pair("a", "b")
        h2 = MerkleAuditTree._hash_pair("a", "b")
        assert h1 == h2

    def test_order_matters(self):
        """hash(a,b) != hash(b,a) — order is significant."""
        h1 = MerkleAuditTree._hash_pair("a", "b")
        h2 = MerkleAuditTree._hash_pair("b", "a")
        assert h1 != h2

    def test_uses_sha256(self):
        expected = hashlib.sha256(("ab").encode()).hexdigest()
        result = MerkleAuditTree._hash_pair("a", "b")
        assert result == expected


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleton:
    def test_singleton(self):
        import app.services.archon.merkle_audit as ma
        ma._merkle_tree = None
        t1 = get_merkle_tree()
        t2 = get_merkle_tree()
        assert t1 is t2
        ma._merkle_tree = None
