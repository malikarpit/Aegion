"""
ChatOps Service — Outbound Notifications.

Sends proactive notifications to configured Slack channels
when high-impact events occur (proposals, alerts, approvals).
"""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.logging import logger


class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ChatOpsService:
    """
    Manages outbound Slack notifications for workspace events.

    Supports:
    - Webhook-based notifications
    - Per-workspace channel configuration
    - Event filtering by level/type
    - Notification history
    """

    def __init__(self):
        self._webhook_configs: Dict[str, Dict[str, Any]] = {}  # workspace_id -> config
        self._notification_log: List[Dict[str, Any]] = []

    def configure_webhook(
        self,
        workspace_id: str,
        webhook_url: str,
        channel: str = "#aegion-notifications",
        events: Optional[List[str]] = None,
        min_level: str = "info",
    ) -> Dict[str, Any]:
        """Configure Slack webhook for a workspace."""
        config = {
            "workspace_id": workspace_id,
            "webhook_url": webhook_url,
            "channel": channel,
            "events": events or ["proposal.created", "alert.triggered", "approval.required", "incident.opened"],
            "min_level": min_level,
            "enabled": True,
            "configured_at": datetime.now(timezone.utc).isoformat(),
        }
        self._webhook_configs[workspace_id] = config
        logger.info(f"ChatOps webhook configured for workspace {workspace_id}")
        return config

    def get_config(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook config for a workspace."""
        return self._webhook_configs.get(workspace_id)

    def list_configs(self) -> List[Dict[str, Any]]:
        """List all webhook configurations."""
        return list(self._webhook_configs.values())

    def remove_config(self, workspace_id: str) -> None:
        """Remove webhook config for a workspace."""
        if workspace_id in self._webhook_configs:
            del self._webhook_configs[workspace_id]

    async def send_notification(
        self,
        workspace_id: str,
        event_type: str,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification to the configured Slack channel.

        Returns delivery status.
        """
        config = self._webhook_configs.get(workspace_id)
        if not config or not config.get("enabled"):
            return {"delivered": False, "reason": "No webhook configured or disabled"}

        # Check level filter
        level_order = {"info": 0, "warning": 1, "critical": 2}
        if level_order.get(level.value, 0) < level_order.get(config.get("min_level", "info"), 0):
            return {"delivered": False, "reason": f"Below min level ({config['min_level']})"}

        # Check event filter
        if config.get("events") and event_type not in config["events"]:
            return {"delivered": False, "reason": f"Event '{event_type}' not in filter"}

        # Build Slack message payload
        emoji_map = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.CRITICAL: "🚨",
        }
        color_map = {
            NotificationLevel.INFO: "#36a64f",
            NotificationLevel.WARNING: "#ff9900",
            NotificationLevel.CRITICAL: "#ff0000",
        }

        payload = {
            "channel": config.get("channel", "#aegion-notifications"),
            "username": "Aegion Bot",
            "icon_emoji": ":robot_face:",
            "attachments": [
                {
                    "color": color_map.get(level, "#36a64f"),
                    "title": f"{emoji_map.get(level, '')} {title}",
                    "text": message,
                    "fields": [
                        {"title": "Event", "value": event_type, "short": True},
                        {"title": "Level", "value": level.value.upper(), "short": True},
                    ],
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }
            ],
        }

        # Add metadata fields
        if metadata:
            for key, value in list(metadata.items())[:4]:
                payload["attachments"][0]["fields"].append(
                    {"title": key.replace("_", " ").title(), "value": str(value), "short": True}
                )

        # Deliver via webhook
        delivery_result = await self._deliver_webhook(config["webhook_url"], payload)

        # Log
        log_entry = {
            "workspace_id": workspace_id,
            "event_type": event_type,
            "title": title,
            "level": level.value,
            "delivered": delivery_result["delivered"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._notification_log.append(log_entry)

        return delivery_result

    async def _deliver_webhook(
        self, webhook_url: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deliver a payload to a Slack webhook URL."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload, timeout=10)

            if resp.status_code == 200:
                logger.info(f"ChatOps notification delivered to {webhook_url}")
                return {"delivered": True, "status_code": resp.status_code}
            else:
                logger.warning(f"ChatOps delivery failed: {resp.status_code} {resp.text}")
                return {"delivered": False, "status_code": resp.status_code, "error": resp.text}

        except Exception as e:
            logger.error(f"ChatOps webhook error: {e}")
            return {"delivered": False, "error": str(e)}

    def get_notification_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent notification history."""
        return self._notification_log[-limit:]

    # ─── Convenience Methods for Common Events ─────────────────────

    async def notify_proposal_created(
        self, workspace_id: str, proposal_id: str, title: str, author: str, tier: str
    ) -> Dict[str, Any]:
        """Notify when a new proposal is created."""
        return await self.send_notification(
            workspace_id=workspace_id,
            event_type="proposal.created",
            title=f"New Proposal: {title}",
            message=f"*{author}* created a {tier} proposal.",
            level=NotificationLevel.WARNING if tier.startswith("tier_3") else NotificationLevel.INFO,
            metadata={"proposal_id": proposal_id, "tier": tier, "author": author},
        )

    async def notify_approval_required(
        self, workspace_id: str, proposal_id: str, title: str, tier: str
    ) -> Dict[str, Any]:
        """Notify when a proposal requires approval."""
        return await self.send_notification(
            workspace_id=workspace_id,
            event_type="approval.required",
            title=f"Approval Required: {title}",
            message=f"A *{tier}* proposal needs review before it can be merged.",
            level=NotificationLevel.WARNING,
            metadata={"proposal_id": proposal_id, "tier": tier},
        )

    async def notify_sentinel_alert(
        self, workspace_id: str, alert_type: str, message: str, severity: str
    ) -> Dict[str, Any]:
        """Notify when Sentinel triggers an alert."""
        level = NotificationLevel.CRITICAL if severity == "critical" else NotificationLevel.WARNING
        return await self.send_notification(
            workspace_id=workspace_id,
            event_type="alert.triggered",
            title=f"Sentinel Alert: {alert_type}",
            message=message,
            level=level,
            metadata={"alert_type": alert_type, "severity": severity},
        )

    async def notify_incident_opened(
        self, workspace_id: str, incident_id: str, title: str, severity: str
    ) -> Dict[str, Any]:
        """Notify when a war room incident is opened."""
        return await self.send_notification(
            workspace_id=workspace_id,
            event_type="incident.opened",
            title=f"Incident: {title}",
            message=f"A *{severity}* incident has been opened in the War Room.",
            level=NotificationLevel.CRITICAL if severity in ("critical", "high") else NotificationLevel.WARNING,
            metadata={"incident_id": incident_id, "severity": severity},
        )


# ─── Singleton ──────────────────────────────────────────────────────

_chatops_service: Optional[ChatOpsService] = None


def get_chatops_service() -> ChatOpsService:
    """Get or create the ChatOps service singleton."""
    global _chatops_service
    if _chatops_service is None:
        _chatops_service = ChatOpsService()
    return _chatops_service
