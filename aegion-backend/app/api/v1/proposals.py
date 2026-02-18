"""
Aegion Proposal Routes — basic CRUD.

Phase 1: Simple proposal creation and retrieval.
Governance tiers and voting will be added later.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/proposals", tags=["proposals"])


class ProposalCreate(BaseModel):
    title: str
    description: str
    session_id: str


class ProposalResponse(BaseModel):
    proposal_id: str
    title: str
    description: str
    status: str


@router.post("/", response_model=ProposalResponse)
async def create_proposal(payload: ProposalCreate):
    """Create a new proposal."""
    import uuid
    return ProposalResponse(
        proposal_id=str(uuid.uuid4()),
        title=payload.title,
        description=payload.description,
        status="pending"
    )


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(proposal_id: str):
    """Get proposal by ID."""
    raise HTTPException(status_code=404, detail="Not found")
