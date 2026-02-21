"""
Audit Chain — tamper-evident audit trail.

Initial version: HMAC-based integrity checking.
Merkle tree verification will be added in a later phase.
"""

import hashlib
import hmac
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from ...core.logging import logger


class AuditChain:
    """HMAC-based audit trail for governance events."""

    def __init__(self, signing_key: str):
        self.signing_key = signing_key.encode()
        self._chain: List[Dict[str, Any]] = []

    def _compute_hmac(self, data: str) -> str:
        """Compute HMAC-SHA256 signature."""
        return hmac.new(self.signing_key, data.encode(), hashlib.sha256).hexdigest()

    def append_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Append a signed event to the audit chain."""
        entry = {
            "sequence": len(self._chain),
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
        }
        payload = json.dumps(entry, sort_keys=True)
        entry["signature"] = self._compute_hmac(payload)
        self._chain.append(entry)
        logger.info(f"Audit event #{entry['sequence']} recorded")
        return entry

    def verify_chain(self) -> bool:
        """Verify all entries in the chain."""
        for entry in self._chain:
            sig = entry.pop("signature")
            payload = json.dumps(entry, sort_keys=True)
            expected = self._compute_hmac(payload)
            entry["signature"] = sig
            if sig != expected:
                return False
        return True
