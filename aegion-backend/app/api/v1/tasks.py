"""
Aegion API v1 - Task Endpoints.

Task management endpoints for the Task Inbox & Parallel Agents system.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.task import Task, TaskRun, TaskStatus, TaskPriority, RunStatus
from ...services.durable_store import JsonFileStore


router = APIRouter(prefix="/tasks", tags=["tasks"])


# ========== Durable Store ==========
_tasks = JsonFileStore(".aegion_data/tasks.json", Task, "task_id")
_runs = JsonFileStore(".aegion_data/task_runs.json", TaskRun, "run_id")


# ========== Request/Response Models ==========


class CreateTaskRequest(BaseModel):
    session_id: str
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    assignee: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None
    repo_path: Optional[str] = None  # for worktree isolation
    parent_task_id: Optional[str] = None  # W4.2: subtask of parent


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    tags: Optional[List[str]] = None


class RunTaskRequest(BaseModel):
    agent_id: str = "noesis"
    parameters: Optional[dict] = None
    async_execution: bool = True  # default to async


class UpdateRunRequest(BaseModel):
    """For async run completion callbacks."""
    status: str  # completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    logs: Optional[List[str]] = None
    token_usage: Optional[dict] = None  # {prompt, completion, total}
    files_touched: Optional[List[str]] = None
    commands_run: Optional[List[str]] = None


class TaskResponse(BaseModel):
    task_id: str
    session_id: str
    workspace_id: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    assignee: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    run_count: int = 0
    tags: List[str] = []
    worktree_path: Optional[str] = None
    parent_task_id: Optional[str] = None
    child_task_ids: List[str] = []


class TaskRunResponse(BaseModel):
    run_id: str
    task_id: str
    agent_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = []
    token_usage: Optional[dict] = None
    files_touched: List[str] = []
    commands_run: List[str] = []


# ========== Helpers ==========


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        task_id=task.task_id,
        session_id=task.session_id,
        workspace_id=task.workspace_id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        priority=task.priority.value,
        assignee=task.assignee,
        created_by=task.created_by,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        run_count=task.run_count,
        tags=task.tags,
        worktree_path=task.worktree_path,
        parent_task_id=getattr(task, 'parent_task_id', None),
        child_task_ids=getattr(task, 'child_task_ids', []),
    )


def _run_to_response(run: TaskRun) -> TaskRunResponse:
    return TaskRunResponse(
        run_id=run.run_id,
        task_id=run.task_id,
        agent_id=run.agent_id,
        status=run.status.value,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        duration_ms=run.duration_ms,
        result=run.result,
        error=run.error,
        logs=run.logs,
        token_usage=run.token_usage,
        files_touched=run.files_touched,
        commands_run=run.commands_run,
    )


# ========== Endpoints ==========


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: CreateTaskRequest,
    user: AuthorityContext = Depends(get_current_user),
    x_workspace_id: Optional[str] = Header(None),
):
    """Create a new task."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    task_id = str(uuid.uuid4())

    task = Task(
        task_id=task_id,
        session_id=request.session_id,
        workspace_id=x_workspace_id or "default",
        title=request.title,
        description=request.description,
        status=TaskStatus.PENDING,
        priority=TaskPriority(request.priority or "medium"),
        assignee=request.assignee,
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        tags=request.tags or [],
        metadata=request.metadata or {},
    )

    # W4.2: Link to parent task if specified
    if request.parent_task_id:
        parent = await _tasks.get(request.parent_task_id)
        if not parent:
            raise HTTPException(status_code=404, detail=f"Parent task {request.parent_task_id} not found")
        task.parent_task_id = request.parent_task_id
        if not hasattr(parent, 'child_task_ids') or parent.child_task_ids is None:
            parent.child_task_ids = []
        parent.child_task_ids.append(task_id)
        parent.updated_at = now
        await _tasks.save(parent)

    await _tasks.save(task)

    logger.info(f"Task created: {task_id} by {user.user_id}")
    return _task_to_response(task)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[str] = None,
    session_id: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List tasks, optionally filtered by status or session."""
    tasks = await _tasks.list_all()

    if status_filter:
        tasks = [t for t in tasks if t.status.value == status_filter]

    if session_id:
        tasks = [t for t in tasks if t.session_id == session_id]

    # Sort by priority (critical first), then by created_at (newest first)
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(key=lambda t: (priority_order.get(t.priority.value, 2), -t.created_at.timestamp()))

    return [_task_to_response(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get task details."""
    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return _task_to_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Update a task."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    now = datetime.now(timezone.utc)

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.status is not None:
        task.status = TaskStatus(request.status)
        if task.status == TaskStatus.COMPLETED:
            task.completed_at = now
    if request.priority is not None:
        task.priority = TaskPriority(request.priority)
    if request.assignee is not None:
        task.assignee = request.assignee
    if request.tags is not None:
        task.tags = request.tags

    task.updated_at = now
    await _tasks.save(task)

    logger.info(f"Task updated: {task_id}")
    return _task_to_response(task)


@router.post("/{task_id}/run", response_model=TaskRunResponse, status_code=status.HTTP_201_CREATED)
async def run_task(
    task_id: str,
    request: RunTaskRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Trigger an agent run on a task (async by default)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot run a completed task")

    now = datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())

    run = TaskRun(
        run_id=run_id,
        task_id=task_id,
        agent_id=request.agent_id,
        status=RunStatus.RUNNING,
        started_at=now,
        logs=[f"Run started by {user.user_id} at {now.isoformat()}"],
        metadata=request.parameters or {},
    )

    if not request.async_execution:
        # Synchronous dispatch: mark as running, response includes initial run record.
        # Agent processing happens via background workers or the PATCH callback.
        task.status = TaskStatus.RUNNING
        run.logs.append("Synchronous dispatch: task marked RUNNING, awaiting agent completion")
    else:
        # Async: set task to RUNNING, await callback via PATCH
        task.status = TaskStatus.RUNNING
        run.logs.append("Async execution started, awaiting completion callback")

    await _runs.save(run)
    task.run_count += 1
    task.updated_at = datetime.now(timezone.utc)
    await _tasks.save(task)

    logger.info(f"Task run {'completed' if not request.async_execution else 'started'}: {run_id} for task {task_id}")
    return _run_to_response(run)


@router.patch("/{task_id}/runs/{run_id}", response_model=TaskRunResponse)
async def update_run(
    task_id: str,
    run_id: str,
    request: UpdateRunRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Update an async run's status (completion callback)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    all_runs = await _runs.list_all()
    task_runs = [r for r in all_runs if r.task_id == task_id]
    run = next((r for r in task_runs if r.run_id == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status != RunStatus.RUNNING:
        raise HTTPException(status_code=400, detail=f"Run is not in RUNNING state")

    now = datetime.now(timezone.utc)
    run.status = RunStatus(request.status)
    run.completed_at = now
    run.duration_ms = int((now - run.started_at).total_seconds() * 1000) if run.started_at else 0
    if request.result:
        run.result = request.result
    if request.error:
        run.error = request.error
    if request.logs:
        run.logs.extend(request.logs)
    if request.token_usage:
        run.token_usage = request.token_usage
    if request.files_touched:
        run.files_touched = request.files_touched
    if request.commands_run:
        run.commands_run = request.commands_run

    # Update task status based on run outcome
    if run.status == RunStatus.COMPLETED:
        task.status = TaskStatus.COMPLETED
        task.completed_at = now
    elif run.status == RunStatus.FAILED:
        task.status = TaskStatus.FAILED

    task.updated_at = now
    await _tasks.save(task)

    logger.info(f"Run {run_id} updated to {request.status}")
    return _run_to_response(run)


@router.post("/{task_id}/worktree", status_code=status.HTTP_201_CREATED)
async def create_task_worktree(
    task_id: str,
    repo_path: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create an isolated git worktree for this task."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.worktree_path:
        return {"task_id": task_id, "worktree_path": task.worktree_path, "message": "Worktree already exists"}

    from ...services.worktree_service import get_worktree_service
    wt = get_worktree_service()

    try:
        info = await wt.create_worktree(task_id, repo_path)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    task.worktree_path = info.worktree_path
    task.updated_at = datetime.now(timezone.utc)
    await _tasks.save(task)

    logger.info(f"Worktree created for task {task_id}: {info.worktree_path}")
    return {
        "task_id": task_id,
        "worktree_path": info.worktree_path,
        "branch": info.branch_name,
        "message": "Worktree created",
    }


@router.delete("/{task_id}/worktree", status_code=status.HTTP_204_NO_CONTENT)
async def cleanup_task_worktree(
    task_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Clean up the worktree for a completed task."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    from ...services.worktree_service import get_worktree_service
    wt = get_worktree_service()
    await wt.cleanup_worktree(task_id)

    task.worktree_path = None
    task.updated_at = datetime.now(timezone.utc)
    await _tasks.save(task)


@router.get("/{task_id}/runs", response_model=List[TaskRunResponse])
async def get_task_runs(
    task_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get run history for a task."""
    task = await _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    all_runs = await _runs.list_all()
    task_runs = [r for r in all_runs if r.task_id == task_id]
    return [_run_to_response(r) for r in task_runs]
