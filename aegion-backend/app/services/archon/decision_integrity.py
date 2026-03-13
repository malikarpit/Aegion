"""
Aegion Decision Integrity: Governance Hardening.

Cryptographic tamper-evidence for DECISION nodes:
- HMAC-SHA256 signing on record_decision()
- Signature verification on get_decision()
- DECISION_INTEGRITY_VIOLATION event on mismatch
- Uses KeyRotationManager for key lifecycle

Signing payload: hash(decision_id | proposal_id | timestamp | approver_id)
"""

import hashlib
import time
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum

from ...core.logging import logger


class DecisionIntegrityError(Exception):
    """Raised when decision signature verification fails."""
    pass


class IntegrityStatus(str, Enum):
    """Decision integrity verification status."""
    VALID = "valid"
    INVALID = "invalid"
    MISSING_SIGNATURE = "missing_signature"
    KEY_NOT_FOUND = "key_not_found"


class DecisionSigner:
    """
    Sign and verify decision nodes using HMAC-SHA256.

    Uses KeyRotationManager for key management (current + previous key).
    """

    def __init__(self, key_manager):
        """
        Args:
            key_manager: KeyRotationManager instance with sign()/verify() methods
        """
        self._key_manager = key_manager
        self._total_signed = 0
        self._total_verified = 0
        self._total_violations = 0

    @staticmethod
    def compute_signing_payload(
        decision_id: str,
        proposal_id: str,
        decided_at: str,
        approver_id: str,
    ) -> str:
        """
        Construct the canonical string to sign.

        Format: SHA-256(decision_id|proposal_id|decided_at|approver_id)
        """
        canonical = f"{decision_id}|{proposal_id}|{decided_at}|{approver_id}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sign_decision(
        self,
        decision_id: str,
        proposal_id: str,
        decided_at: str,
        approver_id: str,
    ) -> Dict[str, str]:
        """
        Sign a decision and return signature metadata.

        Returns dict with:
        - signature: HMAC-SHA256 hex digest
        - key_id: ID of the signing key
        - signed_at: ISO timestamp
        - payload_hash: canonical payload hash (for audit)
        """
        payload = self.compute_signing_payload(
            decision_id, proposal_id, decided_at, approver_id
        )

        signature, key_id = self._key_manager.sign(payload)

        self._total_signed += 1

        return {
            "signature": signature,
            "key_id": key_id,
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "payload_hash": payload,
        }

    def verify_decision(
        self,
        decision_id: str,
        proposal_id: str,
        decided_at: str,
        approver_id: str,
        signature: str,
        key_id: Optional[str] = None,
    ) -> Tuple[IntegrityStatus, Optional[str]]:
        """
        Verify a decision signature.

        Returns:
            (status, detail_message)
        """
        self._total_verified += 1

        if not signature:
            self._record_violation(decision_id, "missing_signature")
            return IntegrityStatus.MISSING_SIGNATURE, "No signature on decision"

        payload = self.compute_signing_payload(
            decision_id, proposal_id, decided_at, approver_id
        )

        is_valid = self._key_manager.verify(payload, signature, key_id=key_id)

        if is_valid:
            return IntegrityStatus.VALID, None

        # Integrity violation!
        self._record_violation(decision_id, "signature_mismatch")
        return (
            IntegrityStatus.INVALID,
            f"Decision {decision_id} signature verification failed — possible tampering",
        )

    def _record_violation(self, decision_id: str, violation_type: str) -> None:
        """Log and track integrity violations."""
        self._total_violations += 1
        logger.error(
            "DECISION_INTEGRITY_VIOLATION",
            extra={
                "decision_id": decision_id,
                "violation_type": violation_type,
                "violation_count": self._total_violations,
            },
        )

    @property
    def stats(self) -> Dict[str, int]:
        """Integrity check statistics."""
        return {
            "total_signed": self._total_signed,
            "total_verified": self._total_verified,
            "total_violations": self._total_violations,
        }


# ========== Re-signing Support (Key Compromise Recovery) ==========

class DecisionResigner:
    """
    Batch re-sign decisions after key compromise/rotation.

    Records re_signed_at and trust_chain_version on each decision.
    """

    def __init__(self, signer: DecisionSigner):
        self._signer = signer
        self._re_signed_count = 0

    def re_sign_decision(
        self,
        decision_id: str,
        proposal_id: str,
        decided_at: str,
        approver_id: str,
        current_trust_version: int = 1,
    ) -> Dict[str, Any]:
        """
        Re-sign a decision with the current key.

        Returns updated signature metadata with trust chain versioning.
        """
        sig_metadata = self._signer.sign_decision(
            decision_id, proposal_id, decided_at, approver_id
        )

        sig_metadata["re_signed_at"] = datetime.now(timezone.utc).isoformat()
        sig_metadata["trust_chain_version"] = current_trust_version + 1

        self._re_signed_count += 1

        logger.info(
            "Decision re-signed",
            extra={
                "decision_id": decision_id,
                "trust_chain_version": sig_metadata["trust_chain_version"],
                "key_id": sig_metadata["key_id"],
            },
        )

        return sig_metadata

    @property
    def re_signed_count(self) -> int:
        return self._re_signed_count


# ========== Singleton ==========

_decision_signer: Optional[DecisionSigner] = None


def get_decision_signer() -> DecisionSigner:
    """Get the singleton DecisionSigner using the global KeyRotationManager."""
    global _decision_signer
    if _decision_signer is None:
        from ..services.archon.key_rotation import get_key_rotation_manager
        _decision_signer = DecisionSigner(get_key_rotation_manager())
    return _decision_signer
