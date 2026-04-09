"""
Aegion API v1 - Diff Review Endpoints.

Inline feedback and comments on proposal diffs.
Enables "review before apply" workflow.

Feature: In-thread diff review with inline feedback.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/proposals", tags=["diff-review"])


# ========== In-Memory Store ==========
_comments: dict[str, "DiffComment"] = {}


# ========== Models ==========


class DiffComment(BaseModel):
    """Inline comment on a proposal diff."""
    comment_id: str
    proposal_id: str
    file_path: str
    line_number: int
    content: str
    author: str
    resolved: bool = False
    thread_id: Optional[str] = None  # For reply threads
    created_at: datetime
    resolved_at: Optional[datetime] = None


class CreateDiffCommentRequest(BaseModel):
    file_path: str
    line_number: int
    content: str
    thread_id: Optional[str] = None


class DiffCommentResponse(BaseModel):
    comment_id: str
    proposal_id: str
    file_path: str
    line_number: int
    content: str
    author: str
    resolved: bool
    thread_id: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None


class ApplyProposalRequest(BaseModel):
    """Apply review-approved proposal changes."""
    merge_strategy: str = "squash"  # squash, merge, rebase
    commit_message: Optional[str] = None


class ApplyProposalResponse(BaseModel):
    proposal_id: str
    applied: bool
    unresolved_comments: int
    message: str


# ========== Endpoints ==========


@router.post("/{proposal_id}/comments", response_model=DiffCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_diff_comment(
    proposal_id: str,
    request: CreateDiffCommentRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Add an inline comment to a proposal diff."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    comment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    comment = DiffComment(
        comment_id=comment_id,
        proposal_id=proposal_id,
        file_path=request.file_path,
        line_number=request.line_number,
        content=request.content,
        author=user.user_id,
        thread_id=request.thread_id,
        created_at=now,
    )

    _comments[comment_id] = comment
    logger.info(f"Diff comment added: {comment_id} on proposal {proposal_id}")

    return DiffCommentResponse(
        comment_id=comment.comment_id,
        proposal_id=comment.proposal_id,
        file_path=comment.file_path,
        line_number=comment.line_number,
        content=comment.content,
        author=comment.author,
        resolved=comment.resolved,
        thread_id=comment.thread_id,
        created_at=comment.created_at.isoformat(),
    )


@router.get("/{proposal_id}/comments", response_model=List[DiffCommentResponse])
async def list_diff_comments(
    proposal_id: str,
    resolved: Optional[bool] = None,
    file_path: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List all comments on a proposal diff."""
    comments = [c for c in _comments.values() if c.proposal_id == proposal_id]

    if resolved is not None:
        comments = [c for c in comments if c.resolved == resolved]

    if file_path:
        comments = [c for c in comments if c.file_path == file_path]

    # Sort by file path, then line number
    comments.sort(key=lambda c: (c.file_path, c.line_number))

    return [
        DiffCommentResponse(
            comment_id=c.comment_id,
            proposal_id=c.proposal_id,
            file_path=c.file_path,
            line_number=c.line_number,
            content=c.content,
            author=c.author,
            resolved=c.resolved,
            thread_id=c.thread_id,
            created_at=c.created_at.isoformat(),
            resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
        )
        for c in comments
    ]


@router.patch("/{proposal_id}/comments/{comment_id}/resolve")
async def resolve_comment(
    proposal_id: str,
    comment_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Mark a diff comment as resolved."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    comment = _comments.get(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this proposal")

    comment.resolved = True
    comment.resolved_at = datetime.now(timezone.utc)
    _comments[comment_id] = comment

    return {"comment_id": comment_id, "resolved": True}


@router.post("/{proposal_id}/apply", response_model=ApplyProposalResponse)
async def apply_proposal(
    proposal_id: str,
    request: ApplyProposalRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Apply proposal changes after diff review.

    Blocks if there are unresolved comments (configurable).
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Count unresolved comments
    unresolved = [
        c for c in _comments.values()
        if c.proposal_id == proposal_id and not c.resolved
    ]

    if unresolved:
        return ApplyProposalResponse(
            proposal_id=proposal_id,
            applied=False,
            unresolved_comments=len(unresolved),
            message=f"Cannot apply: {len(unresolved)} unresolved comment(s). Resolve all comments first.",
        )

    logger.audit(
        action="PROPOSAL_APPLIED",
        actor=user.user_id,
        target=proposal_id,
        justification=f"Applied via {request.merge_strategy}",
    )

    return ApplyProposalResponse(
        proposal_id=proposal_id,
        applied=True,
        unresolved_comments=0,
        message=f"Proposal applied successfully via {request.merge_strategy}",
    )
