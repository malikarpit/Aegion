"""
Aegion API v1 - AI Commands.

Transform, explain, and debug code operations.

Feature: Code transformation/explanation/debugging commands.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/ai", tags=["ai-commands"])


# ========== Models ==========


class TransformRequest(BaseModel):
    """Transform code with instructions."""
    code: str
    instruction: str  # e.g. "Convert to TypeScript", "Add error handling"
    language: str = "python"
    model_profile: str = "quality"  # fast, quality, code


class ExplainRequest(BaseModel):
    """Explain a code selection."""
    code: str
    language: str = "python"
    detail_level: str = "standard"  # brief, standard, detailed
    audience: str = "developer"  # developer, beginner, reviewer


class DebugRequest(BaseModel):
    """Analyze code for bugs."""
    code: str
    language: str = "python"
    error_message: Optional[str] = None
    context: Optional[str] = None  # Surrounding code or context


class AICommandResponse(BaseModel):
    command_id: str
    command_type: str  # transform, explain, debug
    input_preview: str
    output: str
    model_used: str
    token_usage: dict
    duration_ms: int
    created_at: str


# ========== Endpoints ==========


@router.post("/transform", response_model=AICommandResponse)
async def transform_code(
    request: TransformRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Transform code according to an instruction."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    start = datetime.now(timezone.utc)
    command_id = str(uuid.uuid4())

    # Mock transformation (in production, calls AI orchestrator)
    transformed = (
        f"// Transformed: {request.instruction}\n"
        f"// Language: {request.language}\n"
        f"// Original ({len(request.code)} chars)\n\n"
        f"/* [AI would transform the code here using {request.model_profile} model] */\n"
        f"{request.code}"
    )

    elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    logger.info(f"AI transform: {command_id} instruction='{request.instruction[:50]}'")

    return AICommandResponse(
        command_id=command_id,
        command_type="transform",
        input_preview=request.code[:100],
        output=transformed,
        model_used=request.model_profile,
        token_usage={"prompt": len(request.code) // 4, "completion": len(transformed) // 4, "total": (len(request.code) + len(transformed)) // 4},
        duration_ms=elapsed,
        created_at=start.isoformat(),
    )


@router.post("/explain", response_model=AICommandResponse)
async def explain_code(
    request: ExplainRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Explain a code selection."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    start = datetime.now(timezone.utc)
    command_id = str(uuid.uuid4())

    # Mock explanation
    explanation = (
        f"## Code Explanation ({request.detail_level})\n\n"
        f"**Language:** {request.language}\n"
        f"**Audience:** {request.audience}\n\n"
        f"This code ({len(request.code)} characters) "
        f"[AI explanation would appear here based on {request.detail_level} detail level]\n\n"
        f"### Key Points\n"
        f"- The code contains {request.code.count(chr(10)) + 1} lines\n"
        f"- [Additional analysis points from AI]\n"
    )

    elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    logger.info(f"AI explain: {command_id} detail={request.detail_level}")

    return AICommandResponse(
        command_id=command_id,
        command_type="explain",
        input_preview=request.code[:100],
        output=explanation,
        model_used="quality",
        token_usage={"prompt": len(request.code) // 4, "completion": len(explanation) // 4, "total": (len(request.code) + len(explanation)) // 4},
        duration_ms=elapsed,
        created_at=start.isoformat(),
    )


@router.post("/debug", response_model=AICommandResponse)
async def debug_code(
    request: DebugRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Analyze code for bugs and propose fixes."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    start = datetime.now(timezone.utc)
    command_id = str(uuid.uuid4())

    # Mock debug analysis
    debug_report = (
        f"## Debug Analysis\n\n"
        f"**Language:** {request.language}\n"
    )
    if request.error_message:
        debug_report += f"**Error:** `{request.error_message}`\n\n"

    debug_report += (
        f"### Findings\n"
        f"- Code length: {len(request.code)} characters, {request.code.count(chr(10)) + 1} lines\n"
        f"- [AI would analyze for: null checks, off-by-one errors, type mismatches, race conditions]\n\n"
        f"### Suggested Fix\n"
        f"```\n[AI proposed fix would appear here]\n```\n"
    )

    elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    logger.info(f"AI debug: {command_id}")

    return AICommandResponse(
        command_id=command_id,
        command_type="debug",
        input_preview=request.code[:100],
        output=debug_report,
        model_used="code",
        token_usage={"prompt": len(request.code) // 4, "completion": len(debug_report) // 4, "total": (len(request.code) + len(debug_report)) // 4},
        duration_ms=elapsed,
        created_at=start.isoformat(),
    )
