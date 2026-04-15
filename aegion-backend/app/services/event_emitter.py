"""
Aegion Event Emitter — WebSocket Event Broadcasting (W5.1).

Centralized helper for emitting typed events to WebSocket-connected
clients. Any service can call emit_ws_event() to broadcast changes
to all connected clients in a workspace.

Event Types:
  - council.completed      — Council session finished
  - proposal.updated       — Proposal status changed
  - governance.changed     — Governance rule/mode changed
  - presence.changed       — User presence updated
  - incident.updated       — War room incident status changed
  - decision.recorded      — New decision recorded
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone

from ..core.logging import logger


# ──────────────────────────────────────────────────────────────────────────
# Event Types
# ──────────────────────────────────────────────────────────────────────────

class EventType:
    COUNCIL_COMPLETED = "council.completed"
    PROPOSAL_UPDATED = "proposal.updated"
    GOVERNANCE_CHANGED = "governance.changed"
    PRESENCE_CHANGED = "presence.changed"
    INCIDENT_UPDATED = "incident.updated"
    DECISION_RECORDED = "decision.recorded"
    REJECTION_RECORDED = "rejection.recorded"
    SKILL_INVOKED = "skill.invoked"
    TASK_UPDATED = "task.updated"


# ──────────────────────────────────────────────────────────────────────────
# Emit Function
# ──────────────────────────────────────────────────────────────────────────

async def emit_ws_event(
    event_type: str,
    workspace_id: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
) -> bool:
    """
    Broadcast a typed event to all WebSocket clients in a workspace.

    Args:
        event_type: One of EventType constants (e.g., 'council.completed')
        workspace_id: Target workspace
        payload: Event-specific data
        session_id: Optional session scope (broadcast to session clients only)

    Returns:
        True if broadcast succeeded, False otherwise.
    """
    try:
        from ..api.v1.websocket import get_connection_manager

        manager = get_connection_manager()
        if manager is None:
            logger.debug(f"WebSocket manager unavailable, event {event_type} not broadcast")
            return False

        message = {
            "type": event_type,
            "workspace_id": workspace_id,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if session_id:
            await manager.broadcast_to_session(session_id, message)
        else:
            await manager.broadcast_to_workspace(workspace_id, message)

        logger.debug(
            f"Event broadcast: {event_type} → {workspace_id}"
            + (f"/{session_id}" if session_id else ""),
        )
        return True

    except ImportError:
        logger.debug("WebSocket module not available for event broadcasting")
        return False
    except Exception as exc:
        logger.warning(f"Event broadcast failed ({event_type}): {exc}")
        return False


async def emit_council_completed(
    workspace_id: str, query: str, synthesis: str,
    consensus_score: float, cost_usd: float,
) -> bool:
    """Convenience: emit council completion event."""
    return await emit_ws_event(
        EventType.COUNCIL_COMPLETED, workspace_id,
        {
            "query": query[:200],
            "synthesis_preview": synthesis[:500] if synthesis else "",
            "consensus_score": consensus_score,
            "cost_usd": cost_usd,
        },
    )


async def emit_proposal_updated(
    workspace_id: str, proposal_id: str, status: str, updated_by: str,
) -> bool:
    """Convenience: emit proposal status change."""
    return await emit_ws_event(
        EventType.PROPOSAL_UPDATED, workspace_id,
        {"proposal_id": proposal_id, "status": status, "updated_by": updated_by},
    )


async def emit_incident_updated(
    workspace_id: str, incident_id: str, status: str, changed_by: str,
) -> bool:
    """Convenience: emit war room incident update."""
    return await emit_ws_event(
        EventType.INCIDENT_UPDATED, workspace_id,
        {"incident_id": incident_id, "status": status, "changed_by": changed_by},
    )
