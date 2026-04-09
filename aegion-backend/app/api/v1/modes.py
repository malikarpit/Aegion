"""
Aegion API v1 - Session Modes.

Plan / Edit / Ask mode switching for agent routing.

Feature: Modes split controls which agents run,
which tools are available, and what governance tier applies.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from enum import Enum

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/sessions", tags=["modes"])


# ========== Mode Definitions ==========


class SessionMode(str, Enum):
    """Agent operational modes."""
    PLAN = "plan"      # Explore, research, design — no file edits
    EDIT = "edit"      # Code changes, file writes — full tool access
    ASK = "ask"        # Quick questions — lightweight, no governance


# Mode → agent/tool constraints
MODE_CONFIG = {
    SessionMode.PLAN: {
        "agents": ["child", "parent"],
        "tools": ["read_file", "search", "analyze", "graph_query"],
        "governance_tier": "T1",
        "description": "Research and planning mode. Read-only, no file modifications.",
        "auto_checkpoint": False,
    },
    SessionMode.EDIT: {
        "agents": ["child", "parent", "sentinel"],
        "tools": ["read_file", "write_file", "execute", "search", "analyze", "terminal"],
        "governance_tier": "T2",
        "description": "Edit and build mode. Full tool access with governance gates.",
        "auto_checkpoint": True,
    },
    SessionMode.ASK: {
        "agents": ["child"],
        "tools": ["search", "analyze"],
        "governance_tier": "T0",
        "description": "Quick question mode. Lightweight, no governance overhead.",
        "auto_checkpoint": False,
    },
}


# ========== In-Memory Store ==========
# Session ID → current mode
_session_modes: dict[str, SessionMode] = {}


# ========== Request/Response Models ==========


class SetModeRequest(BaseModel):
    mode: str  # plan, edit, ask


class ModeResponse(BaseModel):
    session_id: str
    mode: str
    agents: list
    tools: list
    governance_tier: str
    description: str
    auto_checkpoint: bool


class ModeListResponse(BaseModel):
    modes: list


# ========== Helpers ==========


def _build_mode_response(session_id: str, mode: SessionMode) -> ModeResponse:
    config = MODE_CONFIG[mode]
    return ModeResponse(
        session_id=session_id,
        mode=mode.value,
        agents=config["agents"],
        tools=config["tools"],
        governance_tier=config["governance_tier"],
        description=config["description"],
        auto_checkpoint=config["auto_checkpoint"],
    )


# ========== Endpoints ==========


@router.get("/{session_id}/mode", response_model=ModeResponse)
async def get_session_mode(
    session_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get the current mode for a session."""
    mode = _session_modes.get(session_id, SessionMode.ASK)
    return _build_mode_response(session_id, mode)


@router.put("/{session_id}/mode", response_model=ModeResponse)
async def set_session_mode(
    session_id: str,
    request: SetModeRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Switch session mode (plan / edit / ask)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        mode = SessionMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{request.mode}'. Must be: plan, edit, ask",
        )

    previous = _session_modes.get(session_id, SessionMode.ASK)
    _session_modes[session_id] = mode

    logger.info(f"Session {session_id} mode switched: {previous.value} → {mode.value}")

    return _build_mode_response(session_id, mode)


@router.get("/modes/available", response_model=ModeListResponse)
async def list_available_modes(
    user: AuthorityContext = Depends(get_current_user),
):
    """List all available session modes with their configurations."""
    modes = []
    for mode, config in MODE_CONFIG.items():
        modes.append({
            "mode": mode.value,
            **config,
        })
    return ModeListResponse(modes=modes)
