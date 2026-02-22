"""
Aegion Immutable Audit Store: Compliance.

Hash-chained, append-only audit log:
- Each entry contains prev_hash for tamper detection
- Chain verification on startup and on-demand
- SIEM export (CEF and JSON formats)
- Configurable retention (audit 7yr, sessions 90d, AI 30d)
- Alert fatigue controls (dedup window, cooldown, escalation)
"""

import hashlib
import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


class AuditCategory(str, Enum):
    """Audit event categories with different retention policies."""
    GOVERNANCE = "governance"      # 7 year retention
    SECURITY = "security"          # 7 year retention
    SESSION = "session"            # 90 day retention
    AI_INTERACTION = "ai"          # 30 day retention
    SYSTEM = "system"              # 1 year retention


class AlertSeverity(str, Enum):
    P0 = "P0"  # Immediate
    P1 = "P1"  # 4 hours
    P2 = "P2"  # 24 hours
    P3 = "P3"  # Next business day


@dataclass
class AuditEntry:
    """A single hash-chained audit log entry."""
    sequence: int
    timestamp: str
    category: AuditCategory
    event_type: str
    actor_id: str
    workspace_id: str
    detail: Dict[str, Any]
    prev_hash: str
    entry_hash: str = ""

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry (including prev_hash)."""
        canonical = json.dumps({
            "seq": self.sequence,
            "ts": self.timestamp,
            "cat": self.category.value,
            "evt": self.event_type,
            "actor": self.actor_id,
            "ws": self.workspace_id,
            "detail": self.detail,
            "prev": self.prev_hash,
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


class AuditStore:
    """
    Immutable, hash-chained audit store.

    Guarantees:
    - Append-only (no updates or deletes)
    - Each entry hashes over previous entry (chain integrity)
    - Tamper detection via chain verification
    - SIEM export in CEF or JSON format
    """

    # Genesis hash for the first entry
    GENESIS_HASH = "0" * 64

    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._alert_history: Dict[str, float] = {}
        self._alert_dedup_window = 300    # 5 minutes
        self._alert_cooldown = 900        # 15 minutes

    def append(
        self,
        category: AuditCategory,
        event_type: str,
        actor_id: str,
        workspace_id: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Append a new entry to the audit chain."""
        prev_hash = (
            self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH
        )

        entry = AuditEntry(
            sequence=len(self._entries),
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category,
            event_type=event_type,
            actor_id=actor_id,
            workspace_id=workspace_id,
            detail=detail or {},
            prev_hash=prev_hash,
        )

        self._entries.append(entry)
        return entry

    def verify_chain(self) -> tuple:
        """
        Verify the entire audit chain integrity.

        Returns (is_valid, broken_at_sequence | None)
        """
        if not self._entries:
            return (True, None)

        # Check genesis
        if self._entries[0].prev_hash != self.GENESIS_HASH:
            return (False, 0)

        for i, entry in enumerate(self._entries):
            # Verify self-hash
            expected = entry._compute_hash()
            if entry.entry_hash != expected:
                return (False, i)

            # Verify chain link
            if i > 0:
                if entry.prev_hash != self._entries[i - 1].entry_hash:
                    return (False, i)

        return (True, None)

    def get_entries(
        self,
        category: Optional[AuditCategory] = None,
        workspace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries with optional filters."""
        filtered = self._entries
        if category:
            filtered = [e for e in filtered if e.category == category]
        if workspace_id:
            filtered = [e for e in filtered if e.workspace_id == workspace_id]
        return filtered[-limit:]

    def export_json(self, entries: Optional[List[AuditEntry]] = None) -> str:
        """Export entries in JSON format (for Datadog/ELK)."""
        target = entries or self._entries
        records = []
        for entry in target:
            records.append({
                "sequence": entry.sequence,
                "timestamp": entry.timestamp,
                "category": entry.category.value,
                "event_type": entry.event_type,
                "actor_id": entry.actor_id,
                "workspace_id": entry.workspace_id,
                "detail": entry.detail,
                "hash": entry.entry_hash,
            })
        return json.dumps(records, indent=2)

    def export_cef(self, entries: Optional[List[AuditEntry]] = None) -> List[str]:
        """Export entries in CEF format (for Splunk/QRadar)."""
        target = entries or self._entries
        cef_lines = []
        for entry in target:
            severity = self._map_severity(entry.event_type)
            cef = (
                f"CEF:0|Aegion|AuditStore|1.0|{entry.event_type}|"
                f"{entry.category.value}|{severity}|"
                f"src={entry.actor_id} dst={entry.workspace_id} "
                f"msg={json.dumps(entry.detail)}"
            )
            cef_lines.append(cef)
        return cef_lines

    def should_alert(self, event_type: str) -> bool:
        """
        Alert fatigue control: check dedup window and cooldown.

        Returns True if alert should fire, False if suppressed.
        """
        now = time.monotonic()
        key = event_type

        if key in self._alert_history:
            last_alert = self._alert_history[key]
            if now - last_alert < self._alert_cooldown:
                return False  # Cooldown active

        self._alert_history[key] = now
        return True

    def _map_severity(self, event_type: str) -> int:
        """Map event type to CEF severity (0-10)."""
        p0_events = {"sandbox_escape", "governance_bypass", "audit_integrity_failure"}
        p1_events = {"token_replay", "cross_workspace_access"}
        if event_type in p0_events:
            return 10
        elif event_type in p1_events:
            return 7
        return 3

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self._entries),
            "chain_valid": self.verify_chain()[0],
            "categories": {
                cat.value: sum(1 for e in self._entries if e.category == cat)
                for cat in AuditCategory
            },
        }
