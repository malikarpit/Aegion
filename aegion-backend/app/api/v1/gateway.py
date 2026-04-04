"""Prompt Gateway API endpoints."""

from fastapi import APIRouter, Depends
from ...core.security import get_current_user
from app.services.council_kernel.prompt_gateway import prompt_gateway
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/gateway", tags=["Prompt Gateway"])

class GatewayRequest(BaseModel):
    query: str

class ApproveRequest(BaseModel):
    approved_prompt: str
    user_edits: Optional[str] = None

@router.post("/analyze")
async def analyze_query(req: GatewayRequest, user: dict = Depends(get_current_user)):
    """Analyze and optimize a user query before sending to council."""
    return await prompt_gateway.process(user["workspace_id"], req.query)

@router.post("/approve")
async def approve_prompt(req: ApproveRequest, user: dict = Depends(get_current_user)):
    """User approves or edits the optimized prompt."""
    final = await prompt_gateway.submit_approved_prompt(
        user["workspace_id"], req.approved_prompt, req.user_edits)
    return {"final_prompt": final, "ready_for_council": True}
