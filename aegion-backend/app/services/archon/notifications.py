"""
Aegion Notification Service.

Doctrine: "Silent decisions are dangerous decisions."

Provides:
- Official Slack SDK Integration (ChatOps)
- Async notification dispatch
- Governance event formatting (blocks/cards)
- Fallback to Webhooks for MS Teams
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

try:
    from slack_sdk.web.async_client import AsyncWebClient
    from slack_sdk.errors import SlackApiError
    SLACK_SDK_AVAILABLE = True
except ImportError:
    SLACK_SDK_AVAILABLE = False
    logger.warning("slack_sdk not found. Slack Notifications will not use the official SDK.")


class NotificationService:
    """
    Dispatches governance alerts to external chat platforms with rich UI blocks.
    """
    
    def __init__(self):
        # Slack SDK settings
        self.slack_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_channel = os.getenv("SLACK_CHANNEL", "#governance-alerts")
        
        # Webhook fallbacks
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.teams_webhook = os.getenv("TEAMS_WEBHOOK_URL")
        
        self.enabled = bool(self.slack_token or self.slack_webhook or self.teams_webhook)
        
        if self.slack_token and SLACK_SDK_AVAILABLE:
            self.slack_client = AsyncWebClient(token=self.slack_token)
        else:
            self.slack_client = None
            
        if not self.enabled:
            logger.info("NotificationService disabled (no configured tokens/webhooks).")

    async def notify_decision_approved(self, proposal_id: str, title: str, approver: str, tier: str):
        """Send alert for approved decision."""
        if not self.enabled:
            self._log_simulation(f"Decision Approved: {title} ({proposal_id}) by {approver}")
            return

        text = f"✅ Decision Approved: {title}"
        blocks = [
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
        
        await self._dispatch(text=text, blocks=blocks)

    async def notify_freeze_activated(self, reason: str, actor: str):
        """Send alert for system freeze."""
        if not self.enabled:
            self._log_simulation(f"❄️ EMERGENCY FREEZE ACTIVATED by {actor}: {reason}")
            return

        text = "❄️ EMERGENCY FREEZE ACTIVATED"
        blocks = [
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
        await self._dispatch(text=text, blocks=blocks)

    async def notify_freeze_deactivated(self, reason: str, actor: str):
        """Send alert for system thaw."""
        if not self.enabled:
            self._log_simulation(f"☀️ SYSTEM THAWED by {actor}: {reason}")
            return

        text = "☀️ SYSTEM THAWED"
        blocks = [
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
        await self._dispatch(text=text, blocks=blocks)

    async def _dispatch(self, text: str, blocks: list):
        """Post payload using Slack SDK or fallback to webhooks."""
        
        # 1. Try Official Slack SDK
        if self.slack_client:
            try:
                await self.slack_client.chat_postMessage(
                    channel=self.slack_channel,
                    text=text,
                    blocks=blocks
                )
                logger.info("Dispatched notification via Slack SDK")
            except Exception as e:
                logger.error(f"Failed to post via Slack SDK: {e}")
                
        # 2. Try legacy webhooks
        elif HTTPX_AVAILABLE and (self.slack_webhook or self.teams_webhook):
            payload = {"text": text, "blocks": blocks}
            async with httpx.AsyncClient() as client:
                if self.slack_webhook:
                    try:
                        await client.post(self.slack_webhook, json=payload, timeout=5.0)
                        logger.info("Dispatched notification via Slack Webhook")
                    except Exception as e:
                        logger.error(f"Failed to push to Slack Webhook: {e}")

                if self.teams_webhook:
                    simple_payload = {"text": text}
                    try:
                        await client.post(self.teams_webhook, json=simple_payload, timeout=5.0)
                        logger.info("Dispatched notification via Teams Webhook")
                    except Exception as e:
                        logger.error(f"Failed to push to Teams Webhook: {e}")
        else:
            self._log_simulation(f"Simulation Fallback (unable to dispatch): {text}")

    def _log_simulation(self, message: str):
        """Log notification when webhooks and tokens are missing."""
        logger.info(f"[CHAT-OPS-SIMULATION] {message}")


# Singleton
_service = None

def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
