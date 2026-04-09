"""
Aegion API v1 - Memory Endpoints.

Workspace-scoped memory management for knowledge entries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.memory import MemoryEntry, MemoryScope


router = APIRouter(prefix="/memory", tags=["memory"])


# ========== Durable Store ==========

class DurableMemoryStore:
    """
    JSON-file-backed memory store for persistence across restarts.
    Falls back to in-memory if file path is not writable.
    """

    def __init__(self, persist_path: str = "data/memory_store.json"):
        self._persist_path = persist_path
        self._store: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self):
        import json as _json
        import os
        if os.path.exists(self._persist_path):
            try:
                with open(self._persist_path, 'r') as f:
                    raw = _json.load(f)
                for mid, data in raw.items():
                    self._store[mid] = MemoryEntry.model_validate(data)
                logger.info(f"Loaded {len(self._store)} memory entries from {self._persist_path}")
            except Exception as e:
                logger.warning(f"Failed to load memory store: {e}")

    def _persist(self):
        import json as _json
        import os
        try:
            os.makedirs(os.path.dirname(self._persist_path) or ".", exist_ok=True)
            with open(self._persist_path, 'w') as f:
                _json.dump(
                    {mid: entry.model_dump(mode="json") for mid, entry in self._store.items()},
                    f, default=str, indent=2
                )
        except Exception as e:
            logger.warning(f"Failed to persist memory store: {e}")

    def get(self, key: str) -> Optional[MemoryEntry]:
        return self._store.get(key)

    def put(self, key: str, entry: MemoryEntry):
        self._store[key] = entry
        self._persist()

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            self._persist()
            return True
        return False

    def values(self):
        return self._store.values()

    def __contains__(self, key: str) -> bool:
        return key in self._store


_memory_store = DurableMemoryStore()


# ========== Request/Response Models ==========


class CreateMemoryRequest(BaseModel):
    key: str
    value: Any
    scope: Optional[str] = "repository"
    scope_id: Optional[str] = ""
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    confidence: Optional[float] = 1.0


class MemoryResponse(BaseModel):
    memory_id: str
    key: str
    value: Any
    scope: str
    scope_id: str
    tags: List[str]
    created_by: str
    created_at: str
    updated_at: Optional[str] = None
    source: Optional[str] = None
    confidence: float


# ========== Helpers ==========


def _entry_to_response(entry: MemoryEntry) -> MemoryResponse:
    return MemoryResponse(
        memory_id=entry.memory_id,
        key=entry.key,
        value=entry.value,
        scope=entry.scope.value,
        scope_id=entry.scope_id,
        tags=entry.tags,
        created_by=entry.created_by,
        created_at=entry.created_at.isoformat(),
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        source=entry.source,
        confidence=entry.confidence,
    )


# ========== Endpoints ==========


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def store_memory(
    request: CreateMemoryRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Store a memory entry."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    memory_id = str(uuid.uuid4())

    entry = MemoryEntry(
        memory_id=memory_id,
        key=request.key,
        value=request.value,
        scope=MemoryScope(request.scope) if request.scope else MemoryScope.REPOSITORY,
        scope_id=request.scope_id or "",
        tags=request.tags or [],
        created_by=user.user_id,
        created_at=now,
        source=request.source,
        confidence=request.confidence or 1.0,
    )

    _memory_store.put(memory_id, entry)
    logger.info(f"Memory stored: {memory_id} key={request.key}")
    return _entry_to_response(entry)


@router.get("", response_model=List[MemoryResponse])
async def list_memory(
    scope: Optional[str] = None,
    tag: Optional[str] = None,
    key_prefix: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List memory entries with optional filtering."""
    entries = list(_memory_store.values())

    if scope:
        entries = [e for e in entries if e.scope.value == scope]

    if tag:
        entries = [e for e in entries if tag in e.tags]

    if key_prefix:
        entries = [e for e in entries if e.key.startswith(key_prefix)]

    # Sort by creation time, newest first
    entries.sort(key=lambda e: e.created_at.timestamp(), reverse=True)
    return [_entry_to_response(e) for e in entries]


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get a specific memory entry."""
    entry = _memory_store.get(memory_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Memory entry {memory_id} not found")
    return _entry_to_response(entry)


class SupersedeMemoryRequest(BaseModel):
    """Request to supersede (soft-delete) a memory entry."""
    reason: str = "Superseded by user"
    replacement_id: Optional[str] = None


class SupersessionResponse(BaseModel):
    """Response confirming supersession."""
    memory_id: str
    superseded: bool
    superseded_at: str
    superseded_by: Optional[str]
    reason: str


@router.post("/{memory_id}/supersede", response_model=SupersessionResponse)
async def supersede_memory(
    memory_id: str,
    request: SupersedeMemoryRequest = SupersedeMemoryRequest(),
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Supersede a memory entry (immutability doctrine).

    Instead of deleting, marks the entry as superseded with a reason
    and optional replacement ID. The original entry is preserved.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    entry = _memory_store.get(memory_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Memory entry {memory_id} not found")

    if entry.superseded:
        raise HTTPException(status_code=409, detail=f"Memory entry {memory_id} is already superseded")

    now = datetime.now(timezone.utc)
    entry.superseded = True
    entry.superseded_by = request.replacement_id
    entry.superseded_at = now
    entry.supersession_reason = request.reason
    _memory_store.put(memory_id, entry)

    logger.info(f"Memory superseded: {memory_id} reason={request.reason}")
    return SupersessionResponse(
        memory_id=memory_id,
        superseded=True,
        superseded_at=now.isoformat(),
        superseded_by=request.replacement_id,
        reason=request.reason,
    )



# ========== Query Endpoint ==========


class MemoryQueryRequest(BaseModel):
    """Filtered search over memory entries."""
    scope: Optional[str] = None
    tags: Optional[List[str]] = None
    key_prefix: Optional[str] = None
    min_confidence: Optional[float] = None
    limit: int = 50


class MemoryQueryResponse(BaseModel):
    results: List[MemoryResponse]
    summary: str = ""

@router.post("/query", response_model=MemoryQueryResponse)
async def query_memory(
    request: MemoryQueryRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Query memory entries with structured filters."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    entries = list(_memory_store.values())

    if request.scope:
        entries = [e for e in entries if e.scope.value == request.scope]

    if request.tags:
        entries = [e for e in entries if any(t in e.tags for t in request.tags)]

    if request.key_prefix:
        entries = [e for e in entries if e.key.startswith(request.key_prefix)]

    if request.min_confidence is not None:
        entries = [e for e in entries if e.confidence >= request.min_confidence]

    # Sort by confidence descending, then by creation time
    entries.sort(key=lambda e: (-e.confidence, -e.created_at.timestamp()))
    entries = entries[:request.limit]

    return MemoryQueryResponse(
        results=[_entry_to_response(e) for e in entries],
        summary=f"Found {len(entries)} entries"
    )


# ========== Feature: Auto-Memory Extraction ==========


class ExtractMemoryRequest(BaseModel):
    """Request to auto-extract memory from recent activity."""
    workspace_id: str = ""
    task_id: Optional[str] = None
    run_result: Optional[str] = None
    run_logs: Optional[List[str]] = None
    decision_id: Optional[str] = None
    decision_text: Optional[str] = None
    rationale: Optional[str] = None


@router.post("/extract", status_code=status.HTTP_201_CREATED)
async def extract_memory(
    request: ExtractMemoryRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Auto-extract memory entries from agent activity."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from ...services.memory_extractor import get_memory_extractor
    extractor = get_memory_extractor()

    candidates = []

    # Extract from run results
    if request.run_result or request.run_logs:
        candidates.extend(
            extractor.extract_from_run(
                task_id=request.task_id or "unknown",
                run_result=request.run_result or "",
                run_logs=request.run_logs or [],
                workspace_id=request.workspace_id,
            )
        )

    # Extract from decisions
    if request.decision_id and request.decision_text:
        candidates.extend(
            extractor.extract_from_decision(
                decision_id=request.decision_id,
                decision_text=request.decision_text,
                rationale=request.rationale or "",
                workspace_id=request.workspace_id,
            )
        )

    # Store all extracted entries
    stored = []
    for entry_dict in candidates:
        entry = MemoryEntry(
            memory_id=entry_dict["memory_id"],
            key=entry_dict["key"],
            value=entry_dict["value"],
            scope=MemoryScope(entry_dict["scope"]),
            scope_id=entry_dict["scope_id"],
            tags=entry_dict["tags"],
            created_by=entry_dict["created_by"],
            created_at=entry_dict["created_at"],
            source=entry_dict["source"],
            confidence=entry_dict["confidence"],
        )
        _memory_store[entry.memory_id] = entry
        stored.append(_entry_to_response(entry))

    return {
        "extracted_count": len(stored),
        "entries": stored,
    }

