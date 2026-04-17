"""
Aegion Data Models - Task.

Task and TaskRun models for the Task Inbox & Parallel Agents system.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority level for a task."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RunStatus(str, Enum):
    """Status of a task run."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """A task in the task inbox."""

    # Identity
    task_id: str = Field(..., description="Unique task ID")
    session_id: str = Field(..., description="Session this task belongs to")
    workspace_id: str = Field(..., description="Workspace")

    # Content
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")

    # Status
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)

    # Assignment
    assignee: Optional[str] = Field(None, description="Agent or user assigned")
    created_by: str = Field(..., description="User who created the task")

    # Isolation
    worktree_path: Optional[str] = Field(None, description="Isolated git worktree path for this task")

    # W4.2: Task Tree (parent-child hierarchy)
    parent_task_id: Optional[str] = Field(None, description="Parent task ID for subtask hierarchy")
    child_task_ids: List[str] = Field(default_factory=list, description="Child subtask IDs")

    # Timing
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    # Metrics
    run_count: int = 0

    # Metadata
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskRun(BaseModel):
    """A single execution run of a task by an agent."""

    # Identity
    run_id: str = Field(..., description="Unique run ID")
    task_id: str = Field(..., description="Task this run belongs to")

    # Agent
    agent_id: str = Field(..., description="Agent that executed the run")

    # Status
    status: RunStatus = Field(default=RunStatus.QUEUED)

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Result
    result: Optional[str] = Field(None, description="Run result summary")
    error: Optional[str] = Field(None, description="Error message if failed")
    logs: List[str] = Field(default_factory=list, description="Run log entries")

    # Transparency
    token_usage: Optional[Dict[str, int]] = Field(None, description="Token usage: {prompt, completion, total}")
    files_touched: List[str] = Field(default_factory=list, description="Files read/written during run")
    commands_run: List[str] = Field(default_factory=list, description="Commands executed during run")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
