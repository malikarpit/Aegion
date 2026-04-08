"""
Signed Decisions Tests.

Validates:
- Decision signing produces valid HMAC-SHA256 signatures
- Verification passes for correctly signed decisions
- Verification fails for tampered decisions
- Missing signature detection
- Re-signing with trust chain versioning
- Stats tracking
"""

import pytest
import sys
from unittest.mock import MagicMock

# Mock the import chain that key_rotation.py uses (..core.config, ..core.logging)
# key_rotation.py uses `from ..core.config import settings` which resolves
# to app.services.core.config (wrong — should be app.core.config).
# We mock both variants to prevent ImportError in standalone test execution.
_mock_settings = MagicMock()
_mock_settings.audit_signing_key = "test-default-key-for-unit-tests"
_mock_logger = MagicMock()

# Register mocks for both potential import paths
for prefix in ["app.services.core", "app.core"]:
    sys.modules.setdefault(f"{prefix}", MagicMock())
    config_mod = MagicMock()
    config_mod.settings = _mock_settings
    sys.modules.setdefault(f"{prefix}.config", config_mod)
    logging_mod = MagicMock()
    logging_mod.logger = _mock_logger
    sys.modules.setdefault(f"{prefix}.logging", logging_mod)

from app.services.archon.decision_integrity import (
    DecisionSigner,
    DecisionResigner,
    DecisionIntegrityError,
    IntegrityStatus,
)
from app.services.archon.key_rotation import KeyRotationManager


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _make_signer() -> DecisionSigner:
    km = KeyRotationManager(current_key="test-signing-key-2024")
    return DecisionSigner(km)


DECISION = {
    "decision_id": "dec-001",
    "proposal_id": "prop-100",
    "decided_at": "2026-02-13T14:00:00+00:00",
    "approver_id": "user-admin-1",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Signing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDecisionSigning:
    def test_sign_returns_required_fields(self):
        signer = _make_signer()
        result = signer.sign_decision(**DECISION)
        assert "signature" in result
        assert "key_id" in result
        assert "signed_at" in result
        assert "payload_hash" in result

    def test_signature_is_hex(self):
        signer = _make_signer()
        result = signer.sign_decision(**DECISION)
        int(result["signature"], 16)  # Should not raise

    def test_deterministic_signing(self):
        """Same inputs produce same signature."""
        signer = _make_signer()
        r1 = signer.sign_decision(**DECISION)
        r2 = signer.sign_decision(**DECISION)
        assert r1["signature"] == r2["signature"]

    def test_different_inputs_different_sig(self):
        signer = _make_signer()
        r1 = signer.sign_decision(**DECISION)
        r2 = signer.sign_decision(
            decision_id="dec-002",
            proposal_id="prop-200",
            decided_at="2026-02-13T15:00:00+00:00",
            approver_id="user-admin-2",
        )
        assert r1["signature"] != r2["signature"]

    def test_sign_increments_counter(self):
        signer = _make_signer()
        signer.sign_decision(**DECISION)
        signer.sign_decision(**DECISION)
        assert signer.stats["total_signed"] == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Verification
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDecisionVerification:
    def test_valid_signature_passes(self):
        signer = _make_signer()
        sig_meta = signer.sign_decision(**DECISION)

        status, msg = signer.verify_decision(
            **DECISION,
            signature=sig_meta["signature"],
            key_id=sig_meta["key_id"],
        )
        assert status == IntegrityStatus.VALID
        assert msg is None

    def test_tampered_decision_fails(self):
        """Changing decision fields after signing should fail verification."""
        signer = _make_signer()
        sig_meta = signer.sign_decision(**DECISION)

        status, msg = signer.verify_decision(
            decision_id=DECISION["decision_id"],
            proposal_id="TAMPERED-PROPOSAL",  # Changed!
            decided_at=DECISION["decided_at"],
            approver_id=DECISION["approver_id"],
            signature=sig_meta["signature"],
        )
        assert status == IntegrityStatus.INVALID
        assert "tampering" in msg.lower() or "failed" in msg.lower()

    def test_wrong_signature_fails(self):
        signer = _make_signer()
        status, msg = signer.verify_decision(
            **DECISION,
            signature="deadbeef" * 8,
        )
        assert status == IntegrityStatus.INVALID

    def test_missing_signature(self):
        signer = _make_signer()
        status, msg = signer.verify_decision(
            **DECISION,
            signature="",
        )
        assert status == IntegrityStatus.MISSING_SIGNATURE

    def test_verify_increments_counter(self):
        signer = _make_signer()
        sig = signer.sign_decision(**DECISION)
        signer.verify_decision(**DECISION, signature=sig["signature"])
        signer.verify_decision(**DECISION, signature="bad")
        assert signer.stats["total_verified"] == 2

    def test_violation_counter(self):
        signer = _make_signer()
        signer.verify_decision(**DECISION, signature="")
        signer.verify_decision(**DECISION, signature="bad")
        assert signer.stats["total_violations"] == 2

    def test_cross_key_verification_after_rotation(self):
        """Signatures made with old key should verify during overlap window."""
        km = KeyRotationManager(current_key="old-key-abc")
        signer = DecisionSigner(km)

        sig_meta = signer.sign_decision(**DECISION)
        old_sig = sig_meta["signature"]

        # Rotate key
        km.rotate("new-key-xyz")

        # Old signature should still verify (overlap window)
        status, _ = signer.verify_decision(
            **DECISION,
            signature=old_sig,
        )
        assert status == IntegrityStatus.VALID


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Re-signing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDecisionResigning:
    def test_re_sign_produces_new_signature(self):
        km = KeyRotationManager(current_key="key-v1")
        signer = DecisionSigner(km)
        resigner = DecisionResigner(signer)

        # Sign with v1
        original = signer.sign_decision(**DECISION)

        # Rotate key
        km.rotate("key-v2")

        # Re-sign
        re_signed = resigner.re_sign_decision(**DECISION, current_trust_version=1)

        assert re_signed["signature"] != original["signature"]
        assert re_signed["trust_chain_version"] == 2
        assert "re_signed_at" in re_signed

    def test_re_signed_count(self):
        signer = _make_signer()
        resigner = DecisionResigner(signer)
        resigner.re_sign_decision(**DECISION)
        resigner.re_sign_decision(**DECISION)
        assert resigner.re_signed_count == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Payload Canonical Form
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPayloadCanonicalization:
    def test_payload_is_deterministic(self):
        p1 = DecisionSigner.compute_signing_payload("d1", "p1", "2024-01-01", "u1")
        p2 = DecisionSigner.compute_signing_payload("d1", "p1", "2024-01-01", "u1")
        assert p1 == p2

    def test_payload_is_sha256_hex(self):
        p = DecisionSigner.compute_signing_payload("d1", "p1", "t1", "u1")
        assert len(p) == 64  # SHA-256 = 64 hex chars

    def test_different_fields_different_payload(self):
        p1 = DecisionSigner.compute_signing_payload("d1", "p1", "t1", "u1")
        p2 = DecisionSigner.compute_signing_payload("d2", "p1", "t1", "u1")
        assert p1 != p2
