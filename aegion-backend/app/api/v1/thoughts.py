from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional

from ...services.thought_service import ThoughtService, get_thought_service
from ...models.thought import (
    ThoughtCommit,
    ThoughtLink,
    CreateThoughtRequest,
    UpdateThoughtRequest,
    SealThoughtRequest,
    LinkCommitRequest
)
from ...core.security import AuthorityContext, get_current_user
from ...core.errors import ResourceNotFoundError, ConflictError

router = APIRouter(tags=["Thoughts"])

@router.post("/thoughts", response_model=ThoughtCommit)
async def create_thought(
    req: CreateThoughtRequest,
    current_user: AuthorityContext = Depends(get_current_user),
    service: ThoughtService = Depends(get_thought_service)
):
    """Create a new draft thought artifact."""
    return await service.create_thought(req, created_by=current_user.user_id)

@router.get("/thoughts/{thought_id}", response_model=ThoughtCommit)
async def get_thought(
    thought_id: str = Path(..., title="The ID of the thought to get"),
    service: ThoughtService = Depends(get_thought_service)
):
    """Get a thought artifact by ID."""
    thought = await service.get_thought(thought_id)
    if not thought:
        raise HTTPException(status_code=404, detail=f"Thought {thought_id} not found")
    return thought

@router.patch("/thoughts/{thought_id}", response_model=ThoughtCommit)
async def update_thought(
    req: UpdateThoughtRequest,
    thought_id: str = Path(...),
    current_user: AuthorityContext = Depends(get_current_user),
    service: ThoughtService = Depends(get_thought_service)
):
    """Update a draft thought artifact."""
    try:
        return await service.update_thought(thought_id, req, actor_id=current_user.user_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/thoughts/{thought_id}/seal", response_model=ThoughtCommit)
async def seal_thought(
    req: SealThoughtRequest,
    thought_id: str = Path(...),
    current_user: AuthorityContext = Depends(get_current_user),
    service: ThoughtService = Depends(get_thought_service)
):
    """Seal a thought artifact, making it immutable."""
    try:
        return await service.seal_thought(thought_id, req, actor_id=current_user.user_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/thoughts/{thought_id}/link", response_model=ThoughtLink)
async def link_commit(
    req: LinkCommitRequest,
    thought_id: str = Path(...),
    current_user: AuthorityContext = Depends(get_current_user),
    service: ThoughtService = Depends(get_thought_service)
):
    """Link a commit to a thought artifact."""
    try:
        return await service.link_commit(thought_id, req, actor_id=current_user.user_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/thoughts/commit/{commit_sha}", response_model=ThoughtCommit)
async def get_thought_by_commit(
    commit_sha: str = Path(..., title="The SHA of the commit to lookup"),
    service: ThoughtService = Depends(get_thought_service)
):
    """Get the thought artifact that explains a specific commit."""
    thought = await service.get_thought_by_commit(commit_sha)
    if not thought:
        raise HTTPException(status_code=404, detail=f"No thought found for commit {commit_sha}")
    return thought
