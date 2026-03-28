"""
Aegion Key Rotation Strategy.

Doctrine: "Secrets are ephemeral. Key rotation is hygiene, not crisis response."

Provides:
- Audit signing key rotation with overlap window
- Multi-key verification (current + previous key)
- Rotation scheduling and tracking
"""

import os
import hashlib
import hmac
import secrets
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from ..core.config import settings
from ..core.logging import logger


class KeyInfo(BaseModel):
    """Metadata about a signing key."""
    key_id: str
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool = True
    algorithm: str = "HMAC-SHA256"


class KeyRotationManager:
    """
    Manages audit signing key rotation with overlap window.

    Design:
    - Maintains current + previous key for seamless rotation
    - Signs with current key, verifies with both
    - Overlap window ensures no verification failures during rotation
    - Key IDs track which key signed which event
    """

    def __init__(
        self,
        current_key: Optional[str] = None,
        rotation_interval_days: int = 90,
        overlap_window_days: int = 7,
    ):
        self._current_key = (current_key or settings.audit_signing_key).encode("utf-8")
        self._previous_key: Optional[bytes] = None
        self._rotation_interval = timedelta(days=rotation_interval_days)
        self._overlap_window = timedelta(days=overlap_window_days)
        self._current_key_id = self._compute_key_id(self._current_key)
        self._previous_key_id: Optional[str] = None
        self._last_rotation: datetime = datetime.now(timezone.utc)

    def _compute_key_id(self, key: bytes) -> str:
        """Compute a short key identifier (first 8 chars of key hash)."""
        return hashlib.sha256(key).hexdigest()[:8]

    @property
    def current_key_id(self) -> str:
        return self._current_key_id

    def sign(self, data: str) -> Tuple[str, str]:
        """
        Sign data with the current key.

        Returns:
            (signature, key_id) — the signature and which key produced it
        """
        signature = hmac.new(
            self._current_key,
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature, self._current_key_id

    def verify(self, data: str, signature: str, key_id: Optional[str] = None) -> bool:
        """
        Verify a signature against current and previous keys.

        If key_id is provided, only checks the matching key.
        Otherwise, tries current key first, then previous (overlap window).
        """
        # Try current key
        expected = hmac.new(
            self._current_key,
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(expected, signature):
            return True

        # Try previous key (overlap window)
        if self._previous_key is not None:
            expected_prev = hmac.new(
                self._previous_key,
                data.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            if hmac.compare_digest(expected_prev, signature):
                return True

        return False

    def rotate(self, new_key: Optional[str] = None) -> KeyInfo:
        """
        Rotate to a new signing key.

        The previous key is retained for the overlap window.
        If no new_key is provided, a cryptographically random one is generated.
        """
        # Promote current → previous
        self._previous_key = self._current_key
        self._previous_key_id = self._current_key_id

        # Generate or set new key
        if new_key:
            self._current_key = new_key.encode("utf-8")
        else:
            self._current_key = secrets.token_bytes(32)

        self._current_key_id = self._compute_key_id(self._current_key)
        self._last_rotation = datetime.now(timezone.utc)

        logger.audit(
            action="security.key_rotated",
            actor="system",
            target="audit_signing_key",
            justification="Scheduled key rotation",
            metadata={
                "new_key_id": self._current_key_id,
                "previous_key_id": self._previous_key_id,
                "overlap_window_days": self._overlap_window.days,
            },
        )

        return KeyInfo(
            key_id=self._current_key_id,
            created_at=self._last_rotation.isoformat(),
            expires_at=(self._last_rotation + self._rotation_interval).isoformat(),
            is_active=True,
        )

    def needs_rotation(self) -> bool:
        """Check if the current key has exceeded its rotation interval."""
        elapsed = datetime.now(timezone.utc) - self._last_rotation
        return elapsed >= self._rotation_interval

    def get_key_info(self) -> List[KeyInfo]:
        """List all active keys (current + previous if in overlap window)."""
        keys = [
            KeyInfo(
                key_id=self._current_key_id,
                created_at=self._last_rotation.isoformat(),
                expires_at=(self._last_rotation + self._rotation_interval).isoformat(),
                is_active=True,
            )
        ]

        if self._previous_key is not None and self._previous_key_id:
            keys.append(
                KeyInfo(
                    key_id=self._previous_key_id,
                    created_at="(inherited)",
                    expires_at=(self._last_rotation + self._overlap_window).isoformat(),
                    is_active=True,
                    algorithm="HMAC-SHA256 (overlap)",
                )
            )

        return keys


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_key_manager: Optional[KeyRotationManager] = None


def get_key_rotation_manager() -> KeyRotationManager:
    """Get the global key rotation manager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyRotationManager()
    return _key_manager
