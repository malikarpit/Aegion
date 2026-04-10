from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from ...services.repo_intelligence.service import RepoIntelligenceService, get_repo_service
from ...services.repo_intelligence.contracts import WorkspaceScan, FileRecord, SymbolRecord
from ...domain.repo import ContextPackage
from ...core.security import AuthorityContext, get_current_user
from ...adapters.persistence.event_store import FileEventStore

router = APIRouter(tags=["repo-intelligence"])

def get_service() -> RepoIntelligenceService:
    # Use default event store (Production: FileEventStore)
    # Ideally this dependency injection happens in main.py, but for now we follow pattern
    # Assuming config.py has valid path, but let's use the singleton getter which mimics main.py
    # For now, we will create a lightweight one if not initialized, but typically main app initializes.
    # We'll use the singleton properly.
    return get_repo_service()

@router.post("/scan/start", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_scan(
    workspace_id: str = "default",
    service: RepoIntelligenceService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """Start a full analysis of the repository."""
    scan_id = await service.start_scan(workspace_id)
    return {"scan_id": scan_id, "status": "pending"}

@router.get("/scan/{scan_id}", response_model=WorkspaceScan)
async def get_scan_status(
    scan_id: str,
    service: RepoIntelligenceService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """Get the status of a specific scan."""
    scan = await service.get_scan_status(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan

@router.get("/symbols", response_model=List[SymbolRecord])
async def search_symbols(
    query: str,
    workspace_id: str = "default",
    limit: int = 10,
    service: RepoIntelligenceService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """Search for code symbols (classes, functions)."""
    return await service.query_symbols(query, workspace_id, limit)

@router.get("/file/{file_path:path}", response_model=FileRecord)
async def get_file_details(
    file_path: str,
    workspace_id: str = "default",
    service: RepoIntelligenceService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """Get detailed intelligence about a specific file."""
    record = await service.get_file_record(file_path, workspace_id)
    if not record:
        raise HTTPException(status_code=404, detail="File record not found (try scanning first)")
    return record

class ContextRequest(BaseModel):
    files: List[str]
    workspace_id: str = "default"
    max_history: int = 5

@router.post("/context", response_model=ContextPackage)
async def build_repo_context(
    request: ContextRequest,
    service: RepoIntelligenceService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Build a smart context package for the requested files.
    Includes file metadata, symbols, and recent commit history.
    """
    return await service.build_context(request.files, request.workspace_id, request.max_history)

@router.get("/contributors", response_model=List[Dict[str, Any]])
async def get_top_contributors(
    limit: int = 10,
    workspace_id: str = "default",
    service: RepoIntelligenceService = Depends(get_service),
    user: AuthorityContext = Depends(get_current_user)
):
    """
    Get top contributors by commit count.
    requires prior scan for accuracy.
    """
    return await service.get_top_contributors(workspace_id, limit)
