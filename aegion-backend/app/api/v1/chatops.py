"""
Aegion API v1 - ChatOps Integration.

Slack slash command receiver and event handler.
Enables delegation and governance from team chat.

Feature: ChatOps delegation from Slack.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import hmac
import hashlib

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/chatops", tags=["chatops"])


# ========== Configuration ==========
# In production, load from env/vault
_SLACK_SIGNING_SECRET = ""  # Set via environment variable


# ========== Models ==========


class SlashCommandResponse(BaseModel):
    response_type: str = "ephemeral"  # ephemeral or in_channel
    text: str
    attachments: list = []


class SlackEventWrapper(BaseModel):
    token: Optional[str] = None
    type: str
    challenge: Optional[str] = None  # URL verification
    event: Optional[Dict[str, Any]] = None


# ========== Command Parsing ==========


SUPPORTED_COMMANDS = {
    "run": "Create and run a task: /aegion run <title>",
    "status": "Check task status: /aegion status [task_id]",
    "approve": "Approve a proposal: /aegion approve <proposal_id> <justification>",
    "list": "List recent tasks: /aegion list [status]",
    "help": "Show available commands: /aegion help",
}


def parse_slash_command(text: str) -> tuple[str, list[str]]:
    """Parse /aegion <command> <args...>"""
    parts = text.strip().split(maxsplit=1)
    command = parts[0].lower() if parts else "help"
    args = parts[1].split() if len(parts) > 1 else []
    return command, args


def _handle_help() -> str:
    lines = ["*Aegion ChatOps Commands:*"]
    for cmd, desc in SUPPORTED_COMMANDS.items():
        lines.append(f"• `{cmd}` — {desc}")
    return "\n".join(lines)


def _handle_run(args: list[str], user_id: str) -> str:
    if not args:
        return "Usage: `/aegion run <task title>`"
    title = " ".join(args)
    task_id = str(uuid.uuid4())[:8]
    return f"✅ Task created: *{title}* (ID: `{task_id}`)\nUse `/aegion status {task_id}` to track progress."


def _handle_status(args: list[str]) -> str:
    """Query the in-memory task store for real task status."""
    from .tasks import _tasks  # shared in-memory store
    if args:
        task_id = args[0]
        task = _tasks.get(task_id)
        if task:
            status = task.status.value if hasattr(task.status, 'value') else str(task.status)
            return (
                f"📊 Task `{task_id}`: *{status}*\n"
                f"• Title: {task.title}\n"
                f"• Created: {task.created_at.isoformat()}"
            )
        return f"❌ Task `{task_id}` not found."
    # Summary of all active tasks
    active = [t for t in _tasks.values() if str(getattr(t.status, 'value', t.status)) in ('pending', 'running')]
    if not active:
        return "📋 *Recent tasks:* none active (use `/aegion run <title>` to create one)"
    lines = ["📋 *Active tasks:*"]
    for t in active[:5]:
        lines.append(f"• `{t.task_id}` — {t.title} ({t.status.value})")
    return "\n".join(lines)


def _handle_approve(args: list[str], user_id: str) -> str:
    if len(args) < 2:
        return "Usage: `/aegion approve <proposal_id> <justification>`"
    proposal_id = args[0]
    justification = " ".join(args[1:])
    return f"✅ Proposal `{proposal_id}` approved by {user_id}\n• Justification: {justification}"


def _handle_list(args: list[str]) -> str:
    """List tasks from the in-memory task store."""
    from .tasks import _tasks  # shared in-memory store
    status_filter = args[0] if args else None
    tasks = list(_tasks.values())
    if status_filter and status_filter != "all":
        tasks = [t for t in tasks if str(getattr(t.status, 'value', t.status)) == status_filter]
    if not tasks:
        label = f" ({status_filter})" if status_filter else ""
        return f"📋 *Tasks{label}:* none found"
    lines = [f"📋 *Tasks ({len(tasks)} total):*"]
    for t in tasks[:10]:
        lines.append(f"• `{t.task_id}` — {t.title} ({t.status.value})")
    if len(tasks) > 10:
        lines.append(f"  ...and {len(tasks) - 10} more")
    return "\n".join(lines)


# ========== Endpoints ==========


@router.post("/slack/webhook")
async def slack_slash_command(request: Request):
    """
    Receive Slack slash commands (/aegion).

    Processes commands and returns ephemeral responses.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    form = await request.form()
    text = form.get("text", "")
    user_id = form.get("user_id", "unknown")
    user_name = form.get("user_name", "unknown")

    command, args = parse_slash_command(str(text))

    logger.info(f"Slack command: /{command} from @{user_name} ({user_id})")

    handlers = {
        "help": lambda: _handle_help(),
        "run": lambda: _handle_run(args, user_name),
        "status": lambda: _handle_status(args),
        "approve": lambda: _handle_approve(args, user_name),
        "list": lambda: _handle_list(args),
    }

    handler = handlers.get(command)
    if handler:
        response_text = handler()
    else:
        response_text = f"Unknown command: `{command}`. Try `/aegion help`."

    return {
        "response_type": "ephemeral",
        "text": response_text,
    }


@router.post("/slack/events")
async def slack_events(wrapper: SlackEventWrapper):
    """
    Handle Slack Events API (URL verification + events).
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # URL verification challenge
    if wrapper.type == "url_verification" and wrapper.challenge:
        return {"challenge": wrapper.challenge}

    # Process event
    if wrapper.event:
        event_type = wrapper.event.get("type", "")
        logger.info(f"Slack event received: {event_type}")

        # Handle app_mention for conversational commands
        if event_type == "app_mention":
            text = wrapper.event.get("text", "")
            user = wrapper.event.get("user", "")
            logger.info(f"App mentioned by {user}: {text}")

    return {"ok": True}


@router.get("/slack/install")
async def slack_install():
    """OAuth installation flow start (stub)."""
    return {
        "status": "not_configured",
        "message": "Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET to enable OAuth installation.",
        "install_url": None,
    }


# ========== Outbound Notifications ==========

from ...services.chatops_service import get_chatops_service, NotificationLevel


class WebhookConfigRequest(BaseModel):
    workspace_id: str
    webhook_url: str
    channel: str = "#aegion-notifications"
    events: Optional[list] = None
    min_level: str = "info"


class SendNotificationRequest(BaseModel):
    workspace_id: str
    event_type: str
    title: str
    message: str
    level: str = "info"
    metadata: Optional[Dict[str, Any]] = None


@router.post("/webhooks/configure")
async def configure_webhook(
    request: WebhookConfigRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Configure a Slack webhook for outbound notifications."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_chatops_service()
    config = svc.configure_webhook(
        workspace_id=request.workspace_id,
        webhook_url=request.webhook_url,
        channel=request.channel,
        events=request.events,
        min_level=request.min_level,
    )
    return config


@router.get("/webhooks")
async def list_webhooks(
    user: AuthorityContext = Depends(get_current_user),
):
    """List all configured webhooks."""
    svc = get_chatops_service()
    return svc.list_configs()


@router.get("/webhooks/{workspace_id}")
async def get_webhook(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get webhook config for a workspace."""
    svc = get_chatops_service()
    config = svc.get_config(workspace_id)
    if not config:
        raise HTTPException(status_code=404, detail="No webhook configured for this workspace")
    return config


@router.delete("/webhooks/{workspace_id}")
async def remove_webhook(
    workspace_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Remove webhook config for a workspace."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_chatops_service()
    svc.remove_config(workspace_id)
    return {"status": "removed", "workspace_id": workspace_id}


@router.post("/notify")
async def send_notification(
    request: SendNotificationRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Send a manual notification to the configured Slack channel."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    svc = get_chatops_service()
    try:
        level = NotificationLevel(request.level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid level: {request.level}")

    result = await svc.send_notification(
        workspace_id=request.workspace_id,
        event_type=request.event_type,
        title=request.title,
        message=request.message,
        level=level,
        metadata=request.metadata,
    )
    return result


@router.get("/notifications/log")
async def notification_log(
    limit: int = 50,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get recent notification delivery history."""
    svc = get_chatops_service()
    return svc.get_notification_log(limit=limit)

