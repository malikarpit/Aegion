"""
Freeze Escalation Tests.

Validates:
- Freeze tier escalation and ordering
- De-escalation (normal and EMERGENCY)
- Auto-freeze on violation thresholds
- Multi-party unlock requests
- Operation guards per tier
- Freeze audit log
"""

import sys
from unittest.mock import MagicMock

# Mock imports
_mock_logger = MagicMock()
_mock_logging = MagicMock()
_mock_logging.logger = _mock_logger
for prefix in ["app.services.core", "app.core"]:
    sys.modules.setdefault(f"{prefix}", MagicMock())
    sys.modules.setdefault(f"{prefix}.logging", _mock_logging)
    config_mod = MagicMock()
    config_mod.settings = MagicMock()
    sys.modules.setdefault(f"{prefix}.config", config_mod)

import pytest

from app.services.archon.freeze_escalation import (
    FreezeEscalationManager,
    FreezeEscalationError,
    FreezeTier,
    FreezeReason,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tier Ordering
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTierOrdering:
    def test_tier_ordering(self):
        assert FreezeTier.NONE < FreezeTier.PARTIAL
        assert FreezeTier.PARTIAL < FreezeTier.FULL
        assert FreezeTier.FULL < FreezeTier.EMERGENCY

    def test_default_tier_is_none(self):
        mgr = FreezeEscalationManager()
        assert mgr.get_tier("ws-1") == FreezeTier.NONE


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Escalation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestEscalation:
    def test_escalate_to_partial(self):
        mgr = FreezeEscalationManager()
        result = mgr.escalate("ws-1", FreezeTier.PARTIAL, "admin", "test")
        assert result == FreezeTier.PARTIAL
        assert mgr.get_tier("ws-1") == FreezeTier.PARTIAL

    def test_escalate_to_emergency(self):
        mgr = FreezeEscalationManager()
        result = mgr.escalate("ws-1", FreezeTier.EMERGENCY, "admin", "breach")
        assert result == FreezeTier.EMERGENCY

    def test_cannot_escalate_below_current(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.FULL, "admin", "test")
        result = mgr.escalate("ws-1", FreezeTier.PARTIAL, "admin", "test")
        assert result == FreezeTier.FULL  # Stays at FULL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# De-escalation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDeEscalation:
    def test_de_escalate_from_full(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.FULL, "admin", "test")
        result = mgr.de_escalate("ws-1", FreezeTier.NONE, "admin", "resolved")
        assert result == FreezeTier.NONE

    def test_cannot_de_escalate_emergency_directly(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.EMERGENCY, "admin", "breach")
        with pytest.raises(FreezeEscalationError, match="multi-party"):
            mgr.de_escalate("ws-1", FreezeTier.NONE, "admin", "resolved")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Auto-freeze
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAutoFreeze:
    def test_no_freeze_below_threshold(self):
        mgr = FreezeEscalationManager()
        for _ in range(4):  # Below threshold of 5
            result = mgr.auto_freeze("ws-1", "rate_limit")
        assert result is None
        assert mgr.get_tier("ws-1") == FreezeTier.NONE

    def test_partial_freeze_at_threshold(self):
        mgr = FreezeEscalationManager()
        for i in range(5):
            result = mgr.auto_freeze("ws-1", "auth_failure")
        assert result == FreezeTier.PARTIAL

    def test_full_freeze_at_double_threshold(self):
        mgr = FreezeEscalationManager()
        for i in range(10):
            result = mgr.auto_freeze("ws-1", "auth_failure")
        assert result == FreezeTier.FULL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Multi-party Unlock
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMultiPartyUnlock:
    def setup_method(self):
        self.mgr = FreezeEscalationManager()
        self.mgr.escalate("ws-1", FreezeTier.EMERGENCY, "system", "breach")

    def test_request_unlock(self):
        req = self.mgr.request_unlock("ws-1", "admin-1")
        assert req.workspace_id == "ws-1"
        assert req.completed is False

    def test_approve_unlock(self):
        self.mgr.request_unlock("ws-1", "admin-1")
        req = self.mgr.approve_unlock("ws-1", "admin-2", "admin")
        assert not req.completed  # Need 2 approvals, have 1
        req = self.mgr.approve_unlock("ws-1", "architect-1", "architect")
        assert req.completed
        assert self.mgr.get_tier("ws-1") == FreezeTier.NONE

    def test_cannot_self_approve(self):
        self.mgr.request_unlock("ws-1", "admin-1")
        with pytest.raises(FreezeEscalationError, match="self-approve"):
            self.mgr.approve_unlock("ws-1", "admin-1", "admin")

    def test_cannot_double_approve(self):
        self.mgr.request_unlock("ws-1", "admin-1")
        self.mgr.approve_unlock("ws-1", "admin-2", "admin")
        with pytest.raises(FreezeEscalationError, match="Already approved"):
            self.mgr.approve_unlock("ws-1", "admin-2", "admin")

    def test_unlock_only_for_emergency(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-2", FreezeTier.FULL, "admin", "test")
        with pytest.raises(FreezeEscalationError, match="EMERGENCY"):
            mgr.request_unlock("ws-2", "admin-1")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Operation Guards
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestOperationGuards:
    def test_none_allows_all(self):
        mgr = FreezeEscalationManager()
        assert mgr.is_operation_allowed("ws-1", "read") is True
        assert mgr.is_operation_allowed("ws-1", "write") is True
        assert mgr.is_operation_allowed("ws-1", "propose") is True

    def test_partial_blocks_propose(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.PARTIAL, "admin", "test")
        assert mgr.is_operation_allowed("ws-1", "read") is True
        assert mgr.is_operation_allowed("ws-1", "write") is True
        assert mgr.is_operation_allowed("ws-1", "propose") is False

    def test_full_only_reads(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.FULL, "admin", "test")
        assert mgr.is_operation_allowed("ws-1", "read") is True
        assert mgr.is_operation_allowed("ws-1", "write") is False
        assert mgr.is_operation_allowed("ws-1", "propose") is False

    def test_emergency_blocks_all(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.EMERGENCY, "admin", "breach")
        assert mgr.is_operation_allowed("ws-1", "read") is False
        assert mgr.is_operation_allowed("ws-1", "write") is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Audit Log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAuditLog:
    def test_escalation_logged(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.PARTIAL, "admin-1", "test")
        log = mgr.get_freeze_log("ws-1")
        assert len(log) == 1
        assert log[0].previous_tier == FreezeTier.NONE
        assert log[0].new_tier == FreezeTier.PARTIAL

    def test_stats(self):
        mgr = FreezeEscalationManager()
        mgr.escalate("ws-1", FreezeTier.FULL, "admin", "test")
        mgr.escalate("ws-2", FreezeTier.EMERGENCY, "admin", "breach")
        stats = mgr.stats
        assert stats["frozen_workspaces"] == 2
        assert stats["emergency_count"] == 1
