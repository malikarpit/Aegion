"""
Tests for ChatOps Service — Phase R2: Integrations.

Covers:
    Configuration:
        - Configure webhook
        - Get config
        - Remove config
        - List configs

    Notification:
        - No config → not delivered
        - Below min level → filtered
        - Not in event filter → filtered
        - Builds Slack payload
        - Notification log recorded

    Convenience Methods:
        - notify_proposal_created
        - notify_sentinel_alert (critical)
        - notify_incident_opened
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.chatops_service import (
    ChatOpsService,
    NotificationLevel,
    get_chatops_service,
)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class TestChatOpsConfig:
    """Webhook configuration."""

    def test_configure_webhook(self):
        svc = ChatOpsService()
        config = svc.configure_webhook("ws1", "https://hooks.slack.com/test")
        assert config["workspace_id"] == "ws1"
        assert config["webhook_url"] == "https://hooks.slack.com/test"
        assert config["enabled"] is True

    def test_get_config(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://hooks.slack.com/test")
        assert svc.get_config("ws1") is not None
        assert svc.get_config("nonexistent") is None

    def test_remove_config(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://hooks.slack.com/test")
        svc.remove_config("ws1")
        assert svc.get_config("ws1") is None

    def test_list_configs(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://a")
        svc.configure_webhook("ws2", "https://b")
        assert len(svc.list_configs()) == 2

    def test_custom_events(self):
        svc = ChatOpsService()
        config = svc.configure_webhook(
            "ws1", "https://hooks.slack.com/test",
            events=["proposal.created"],
        )
        assert config["events"] == ["proposal.created"]


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION FILTERING
# ══════════════════════════════════════════════════════════════════════════════

class TestChatOpsNotification:
    """Notification sending and filtering."""

    @pytest.mark.asyncio
    async def test_no_config_not_delivered(self):
        svc = ChatOpsService()
        result = await svc.send_notification(
            "ws1", "test.event", "Title", "Message"
        )
        assert result["delivered"] is False
        assert "No webhook" in result["reason"]

    @pytest.mark.asyncio
    async def test_below_min_level_filtered(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://a", min_level="critical")
        result = await svc.send_notification(
            "ws1", "test.event", "Title", "Message",
            level=NotificationLevel.INFO,
        )
        assert result["delivered"] is False
        assert "min level" in result["reason"]

    @pytest.mark.asyncio
    async def test_not_in_event_filter_filtered(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://a", events=["proposal.created"])
        result = await svc.send_notification(
            "ws1", "other.event", "Title", "Message"
        )
        assert result["delivered"] is False
        assert "not in filter" in result["reason"]

    @pytest.mark.asyncio
    async def test_notification_delivered(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://hooks.slack.com/test")

        # Mock httpx to avoid real HTTP
        with patch.object(svc, "_deliver_webhook", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.return_value = {"delivered": True, "status_code": 200}
            result = await svc.send_notification(
                "ws1", "proposal.created", "New Proposal", "Details"
            )
            assert result["delivered"] is True
            mock_deliver.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_log_recorded(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://hooks.slack.com/test")

        with patch.object(svc, "_deliver_webhook", new_callable=AsyncMock) as mock:
            mock.return_value = {"delivered": True}
            await svc.send_notification("ws1", "proposal.created", "T", "M")

        log = svc.get_notification_log()
        assert len(log) == 1
        assert log[0]["event_type"] == "proposal.created"


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE METHODS
# ══════════════════════════════════════════════════════════════════════════════

class TestChatOpsConvenience:
    """Convenience notification methods."""

    @pytest.mark.asyncio
    async def test_notify_proposal_created(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://a")
        with patch.object(svc, "_deliver_webhook", new_callable=AsyncMock) as mock:
            mock.return_value = {"delivered": True}
            result = await svc.notify_proposal_created(
                "ws1", "p-123", "Add caching", "alice", "tier_1"
            )
            assert result["delivered"] is True

    @pytest.mark.asyncio
    async def test_notify_sentinel_alert_critical(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://a")
        with patch.object(svc, "_deliver_webhook", new_callable=AsyncMock) as mock:
            mock.return_value = {"delivered": True}
            result = await svc.notify_sentinel_alert(
                "ws1", "high_error_rate", "Error rate > 10%", "critical"
            )
            assert result["delivered"] is True

    @pytest.mark.asyncio
    async def test_notify_incident_opened(self):
        svc = ChatOpsService()
        svc.configure_webhook("ws1", "https://a")
        with patch.object(svc, "_deliver_webhook", new_callable=AsyncMock) as mock:
            mock.return_value = {"delivered": True}
            result = await svc.notify_incident_opened(
                "ws1", "inc-456", "DB Outage", "critical"
            )
            assert result["delivered"] is True


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

class TestChatOpsSingleton:
    def test_singleton(self):
        import app.services.chatops_service as mod
        mod._chatops_service = None
        s1 = get_chatops_service()
        s2 = get_chatops_service()
        assert s1 is s2
        mod._chatops_service = None
