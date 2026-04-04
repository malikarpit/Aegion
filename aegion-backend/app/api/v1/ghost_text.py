"""
Aegion API v1 - Ghost Text Endpoints.

Wired to the ACK cascade-backed GhostTextEngine (services/ghost_text.py)
which uses FrugalGPT for cost-effective inline completions.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from ...services.ghost_text import get_ghost_text
from ...core.security import AuthorityContext, get_current_user

router = APIRouter(prefix="/ghost-text", tags=["ghost-text"])


class CompletionRequest(BaseModel):
    file_path: str
    file_content: str
    cursor_position: Dict[str, int]  # {"line": int, "character": int}
    language_id: str
    workspace_id: str


class GhostTextSuggestion(BaseModel):
    text: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    model: Optional[str] = None
    cost_usd: float = 0.0
    latency_ms: int = 0


@router.post("/complete", response_model=GhostTextSuggestion)
async def generate_ghost_text(
    request: CompletionRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Generate an inline completion suggestion.

    Splits the file content at the cursor position into prefix/suffix,
    then calls the ACK cascade-backed ghost text engine.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Split file content at cursor position into prefix and suffix
    lines = request.file_content.split("\n")
    cursor_line = request.cursor_position.get("line", 0)
    cursor_char = request.cursor_position.get("character", 0)

    prefix_lines = lines[:cursor_line]
    if cursor_line < len(lines):
        prefix_lines.append(lines[cursor_line][:cursor_char])
    prefix = "\n".join(prefix_lines)

    suffix_lines = []
    if cursor_line < len(lines):
        suffix_lines.append(lines[cursor_line][cursor_char:])
    if cursor_line + 1 < len(lines):
        suffix_lines.extend(lines[cursor_line + 1:])
    suffix = "\n".join(suffix_lines)

    # Call the ACK cascade-backed ghost text engine
    ghost = get_ghost_text()
    result = await ghost.complete(
        workspace_id=request.workspace_id,
        prefix=prefix,
        suffix=suffix,
        language=request.language_id,
        file_path=request.file_path,
    )

    return GhostTextSuggestion(
        text=result.get("completion", ""),
        confidence=result.get("confidence", 0.0),
        reasoning=f"Model: {result.get('model', 'unknown')}",
        model=result.get("model"),
        cost_usd=result.get("cost_usd", 0.0),
        latency_ms=result.get("latency_ms", 0),
    )
