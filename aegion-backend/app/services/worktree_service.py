"""
Aegion Worktree Service.

Manages isolated git worktrees for parallel agent task execution.
Each task can operate in its own worktree, preventing interference
between concurrent agent runs.

Doctrine: "Isolation enables parallelism."
"""

import asyncio
import os
import shutil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..core.logging import logger


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""
    task_id: str
    worktree_path: str
    branch_name: str
    repo_path: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


class WorktreeService:
    """
    Manages git worktrees for parallel task execution.
    
    Each task gets an isolated worktree branched from the workspace HEAD,
    so agents can read/write files without conflicts.
    """

    def __init__(self):
        self._worktrees: Dict[str, WorktreeInfo] = {}

    async def _run_git(self, *args: str, cwd: str) -> tuple[int, str, str]:
        """Execute a git command and return (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

    async def create_worktree(
        self,
        task_id: str,
        repo_path: str,
        base_branch: str = "HEAD",
    ) -> WorktreeInfo:
        """
        Create an isolated git worktree for a task.

        Args:
            task_id: Unique task identifier (used for branch + directory naming).
            repo_path: Path to the main git repository.
            base_branch: Branch or ref to base the worktree on (default: HEAD).

        Returns:
            WorktreeInfo with the new worktree path.
        """
        if task_id in self._worktrees:
            return self._worktrees[task_id]

        branch_name = f"aegion/task-{task_id[:8]}"
        worktree_dir = os.path.join(repo_path, ".aegion-worktrees", task_id[:12])

        # Create worktree directory parent
        os.makedirs(os.path.dirname(worktree_dir), exist_ok=True)

        # Create a new branch + worktree
        rc, out, err = await self._run_git(
            "worktree", "add", "-b", branch_name, worktree_dir, base_branch,
            cwd=repo_path,
        )

        if rc != 0:
            logger.error(f"Failed to create worktree for task {task_id}: {err}")
            raise RuntimeError(f"git worktree add failed: {err}")

        info = WorktreeInfo(
            task_id=task_id,
            worktree_path=worktree_dir,
            branch_name=branch_name,
            repo_path=repo_path,
        )
        self._worktrees[task_id] = info

        logger.info(
            f"Worktree created for task {task_id}: {worktree_dir} on branch {branch_name}"
        )
        return info

    async def cleanup_worktree(self, task_id: str) -> bool:
        """
        Remove a worktree and its branch after task completion.

        Returns True if cleanup succeeded.
        """
        info = self._worktrees.get(task_id)
        if not info:
            return False

        # Remove worktree
        rc, _, err = await self._run_git(
            "worktree", "remove", info.worktree_path, "--force",
            cwd=info.repo_path,
        )
        if rc != 0:
            logger.warning(f"git worktree remove failed: {err}, trying manual cleanup")
            if os.path.isdir(info.worktree_path):
                shutil.rmtree(info.worktree_path, ignore_errors=True)

        # Delete the branch
        await self._run_git(
            "branch", "-D", info.branch_name,
            cwd=info.repo_path,
        )

        info.active = False
        del self._worktrees[task_id]

        logger.info(f"Worktree cleaned up for task {task_id}")
        return True

    async def list_worktrees(self, repo_path: str) -> List[Dict[str, Any]]:
        """List all git worktrees for a repo."""
        rc, out, _ = await self._run_git("worktree", "list", "--porcelain", cwd=repo_path)
        if rc != 0:
            return []

        worktrees = []
        current: Dict[str, str] = {}
        for line in out.split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "":
                if current:
                    worktrees.append(current)
                current = {}
        if current:
            worktrees.append(current)

        return worktrees

    def get_worktree(self, task_id: str) -> Optional[WorktreeInfo]:
        """Get worktree info for a task."""
        return self._worktrees.get(task_id)


# Singleton
_worktree_service: Optional[WorktreeService] = None


def get_worktree_service() -> WorktreeService:
    global _worktree_service
    if _worktree_service is None:
        _worktree_service = WorktreeService()
    return _worktree_service
