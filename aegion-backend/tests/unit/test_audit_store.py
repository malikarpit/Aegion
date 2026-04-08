"""
Audit Store Tests.

Validates:
- Append-only audit chain
- Hash chain integrity
- Tamper detection
- Filtering by category and workspace
- SIEM export (JSON and CEF)
- Alert fatigue controls
"""

import json

import pytest
from app.services.archon.audit_store import (
    AuditStore,
    AuditCategory,
    AuditEntry,
)


class TestAppendOnly:
    def test_append_creates_entry(self):
        store = AuditStore()
        entry = store.append(
            AuditCategory.GOVERNANCE, "decision_signed",
            "admin-1", "ws-1", {"proposal_id": "p1"}
        )
        assert entry.sequence == 0
        assert entry.event_type == "decision_signed"

    def test_sequential_numbering(self):
        store = AuditStore()
        e1 = store.append(AuditCategory.SECURITY, "login", "u1", "ws-1")
        e2 = store.append(AuditCategory.SECURITY, "logout", "u1", "ws-1")
        assert e1.sequence == 0
        assert e2.sequence == 1

    def test_first_entry_has_genesis_prev(self):
        store = AuditStore()
        entry = store.append(AuditCategory.SYSTEM, "startup", "system", "global")
        assert entry.prev_hash == AuditStore.GENESIS_HASH


class TestChainIntegrity:
    def test_valid_chain(self):
        store = AuditStore()
        for i in range(10):
            store.append(AuditCategory.GOVERNANCE, f"event_{i}", "u1", "ws-1")
        valid, broken_at = store.verify_chain()
        assert valid is True
        assert broken_at is None

    def test_empty_chain_is_valid(self):
        store = AuditStore()
        assert store.verify_chain() == (True, None)

    def test_chain_links_correctly(self):
        store = AuditStore()
        e1 = store.append(AuditCategory.SECURITY, "a", "u1", "ws-1")
        e2 = store.append(AuditCategory.SECURITY, "b", "u1", "ws-1")
        assert e2.prev_hash == e1.entry_hash


class TestTamperDetection:
    def test_detect_tampered_entry(self):
        store = AuditStore()
        store.append(AuditCategory.GOVERNANCE, "event1", "u1", "ws-1")
        store.append(AuditCategory.GOVERNANCE, "event2", "u1", "ws-1")

        # Tamper with the first entry
        store._entries[0].detail["tampered"] = True

        valid, broken_at = store.verify_chain()
        assert valid is False
        assert broken_at == 0

    def test_detect_broken_chain_link(self):
        store = AuditStore()
        store.append(AuditCategory.SECURITY, "a", "u1", "ws-1")
        store.append(AuditCategory.SECURITY, "b", "u1", "ws-1")
        store.append(AuditCategory.SECURITY, "c", "u1", "ws-1")

        # Break chain link
        store._entries[2].prev_hash = "0" * 64

        valid, broken_at = store.verify_chain()
        assert valid is False
        assert broken_at == 2


class TestFiltering:
    def setup_method(self):
        self.store = AuditStore()
        self.store.append(AuditCategory.GOVERNANCE, "decision", "u1", "ws-1")
        self.store.append(AuditCategory.SECURITY, "login", "u1", "ws-1")
        self.store.append(AuditCategory.GOVERNANCE, "proposal", "u2", "ws-2")

    def test_filter_by_category(self):
        entries = self.store.get_entries(category=AuditCategory.GOVERNANCE)
        assert len(entries) == 2

    def test_filter_by_workspace(self):
        entries = self.store.get_entries(workspace_id="ws-1")
        assert len(entries) == 2

    def test_filter_combined(self):
        entries = self.store.get_entries(
            category=AuditCategory.GOVERNANCE, workspace_id="ws-2"
        )
        assert len(entries) == 1


class TestSIEMExport:
    def setup_method(self):
        self.store = AuditStore()
        self.store.append(AuditCategory.SECURITY, "sandbox_escape", "u1", "ws-1")
        self.store.append(AuditCategory.GOVERNANCE, "decision_signed", "u2", "ws-1")

    def test_json_export(self):
        output = self.store.export_json()
        data = json.loads(output)
        assert len(data) == 2
        assert data[0]["event_type"] == "sandbox_escape"

    def test_cef_export(self):
        lines = self.store.export_cef()
        assert len(lines) == 2
        assert "CEF:0|Aegion" in lines[0]
        assert "sandbox_escape" in lines[0]

    def test_cef_severity_mapping(self):
        lines = self.store.export_cef()
        # sandbox_escape should be severity 10 (P0)
        assert "|10|" in lines[0]


class TestAlertFatigue:
    def test_first_alert_fires(self):
        store = AuditStore()
        assert store.should_alert("sandbox_escape") is True

    def test_duplicate_suppressed(self):
        store = AuditStore()
        store.should_alert("sandbox_escape")
        assert store.should_alert("sandbox_escape") is False

    def test_different_events_not_suppressed(self):
        store = AuditStore()
        store.should_alert("sandbox_escape")
        assert store.should_alert("token_replay") is True


class TestStats:
    def test_stats(self):
        store = AuditStore()
        store.append(AuditCategory.GOVERNANCE, "a", "u1", "ws-1")
        store.append(AuditCategory.SECURITY, "b", "u1", "ws-1")
        stats = store.stats
        assert stats["total_entries"] == 2
        assert stats["chain_valid"] is True
        assert stats["categories"]["governance"] == 1
