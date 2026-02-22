"""
Aegion Notification Service.

Doctrine: "Silent decisions are dangerous decisions."

Provides:
- Webhook integration for Slack/Teams
- Async notification dispatch
- Governance event formatting (blocks/cards)
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
try:
    from ...core.logging import logger
except (ImportError, ValueError):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("NotificationService")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not found. Notifications will be logged only.")

class NotificationService:
    """
    Dispatches governance alerts to external chat platforms.
    """
    
    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.teams_webhook = os.getenv("TEAMS_WEBHOOK_URL")
        self.enabled = bool(self.slack_webhook or self.teams_webhook)
        
        if not self.enabled:
            logger.info("NotificationService disabled (no webhooks configured).")

    async def notify_decision_approved(self, proposal_id: str, title: str, approver: str, tier: str):
        """Send alert for approved decision."""
        if not self.enabled:
            self._log_simulation(f"Decision Approved: {title} ({proposal_id}) by {approver}")
            return

        payload = {
            "text": f"✅ Decision Approved: {title}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Decision Approved"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Proposal:*\n{title}"},
                        {"type": "mrkdwn", "text": f"*ID:*\n`{proposal_id}`"},
                        {"type": "mrkdwn", "text": f"*Approver:*\n{approver}"},
                        {"type": "mrkdwn", "text": f"*Tier:*\n{tier}"}
                    ]
                }
            ]
        }
        await self._dispatch(payload)

    async def notify_freeze_activated(self, reason: str, actor: str):
        """Send alert for system freeze."""
        if not self.enabled:
            self._log_simulation(f"❄️ SYSTEM FREEZE ACTIVATED by {actor}: {reason}")
            return

        payload = {
            "text": f"❄️ SYSTEM FREEZE ACTIVATED",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "❄️ EMERGENCY FREEZE ACTIVATED"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"The governance system has been frozen by *{actor}*.\n\n*Reason:*\n{reason}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ All new proposals and approvals are blocked until explicitly thawed."
                    }
                }
            ]
        }
        await self._dispatch(payload)

    async def notify_freeze_deactivated(self, reason: str, actor: str):
        """Send alert for system thaw."""
        if not self.enabled:
            self._log_simulation(f"☀️ SYSTEM THAWED by {actor}: {reason}")
            return

        payload = {
            "text": f"☀️ SYSTEM THAWED",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "☀️ SYSTEM THAWED"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"The system has been thawed by *{actor}*.\n\n*Reason:*\n{reason}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "✅ Operations may resume normal function."
                    }
                }
            ]
        }
        await self._dispatch(payload)

    async def _dispatch(self, payload: Dict[str, Any]):
        """Post payload to configured webhooks."""
        if not HTTPX_AVAILABLE:
            self._log_simulation(f"Skipping webhook dispatch (httpx missing): {payload.get('text')}")
            return
            
        async with httpx.AsyncClient() as client:
            if self.slack_webhook:
                try:
                    await client.post(self.slack_webhook, json=payload, timeout=5.0)
                except Exception as e:
                    logger.error(f"Failed to push to Slack: {e}")

            # Teams payload format is different, would need adapter. 
            # For MVP, assuming Slack format or simplified text for others.
            if self.teams_webhook:
                 # Simplified text-only for Teams compatibility (unless using Adaptive Cards)
                 simple_payload = {"text": payload.get("text", "Notification")}
                 try:
                    await client.post(self.teams_webhook, json=simple_payload, timeout=5.0)
                 except Exception as e:
                    logger.error(f"Failed to push to Teams: {e}")

    def _log_simulation(self, message: str):
        """Log notification when webhooks are missing."""
        logger.info(f"[CHAT-OPS-SIMULATION] {message}")


# Singleton
_service = None

def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
