"""
Aegion Git Checkpoint Service.

Shadow git repository for checkpointing workspace state.
Uses a hidden `.aegion-checkpoints/` git repo to create immutable
snapshots that can be diffed and restored.

Doctrine: "Every state is recoverable."
"""

import asyncio
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..core.logging import logger


@dataclass
class GitSnapshot:
    """A git-backed checkpoint snapshot."""
    checkpoint_id: str
    commit_sha: str
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    files_changed: int = 0


class GitCheckpointService:
    """
    Shadow git repository for session state checkpointing.

    Maintains a hidden git repo per workspace where each checkpoint
    is a git commit. This enables:
    - Diff between any two checkpoints
    - Full state restoration via git checkout
    - Immutable audit trail via commit history
    """

    def __init__(self):
        self._snapshots: Dict[str, GitSnapshot] = {}

    async def _run_git(self, *args: str, cwd: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "GIT_AUTHOR_NAME": "Aegion", "GIT_AUTHOR_EMAIL": "aegion@system"},
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

    def _shadow_path(self, workspace_path: str) -> str:
        """Get the shadow checkpoint repo path."""
        return os.path.join(workspace_path, ".aegion-checkpoints")

    async def init_shadow_repo(self, workspace_path: str) -> str:
        """
        Initialize the shadow checkpoint repo for a workspace.

        Creates `.aegion-checkpoints/` with an initial commit.
        Returns the shadow repo path.
        """
        shadow = self._shadow_path(workspace_path)
        if os.path.isdir(os.path.join(shadow, ".git")):
            return shadow

        os.makedirs(shadow, exist_ok=True)
        await self._run_git("init", cwd=shadow)
        await self._run_git("commit", "--allow-empty", "-m", "Initial checkpoint repo", cwd=shadow)

        logger.info(f"Shadow checkpoint repo initialized at {shadow}")
        return shadow

    async def commit_snapshot(
        self,
        workspace_path: str,
        checkpoint_id: str,
        message: str,
        files: Optional[Dict[str, str]] = None,
        state_snapshot: Optional[Dict[str, Any]] = None,
        thought_id: Optional[str] = None,
        actor_id: Optional[str] = "system",
    ) -> GitSnapshot:
        """
        Create a git commit snapshot for a checkpoint.

        Args:
            workspace_path: Root workspace directory.
            checkpoint_id: ID of the Aegion checkpoint.
            message: Commit message.
            files: Optional dict of {filename: content} to snapshot.
            state_snapshot: Optional session state dict to serialize.

        Returns:
            GitSnapshot with commit SHA.
        """
        import json

        shadow = await self.init_shadow_repo(workspace_path)

        # Write state snapshot
        if state_snapshot:
            state_file = os.path.join(shadow, f"state-{checkpoint_id}.json")
            with open(state_file, "w") as f:
                json.dump(state_snapshot, f, indent=2, default=str)

        # Write any explicit files
        if files:
            for fname, content in files.items():
                fpath = os.path.join(shadow, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w") as f:
                    f.write(content)

        # Stage all changes
        await self._run_git("add", "-A", cwd=shadow)

        # Check if there are changes to commit
        rc, status, _ = await self._run_git("status", "--porcelain", cwd=shadow)
        if not status:
            # No changes, create empty commit for the marker
            commit_msg = f"[{checkpoint_id}] {message} (no changes)"
            await self._run_git("commit", "--allow-empty", "-m", commit_msg, cwd=shadow)
        else:
            commit_msg = f"[{checkpoint_id}] {message}"
            await self._run_git("commit", "-m", commit_msg, cwd=shadow)

        # Get commit SHA
        _, sha, _ = await self._run_git("rev-parse", "HEAD", cwd=shadow)

        # Count changed files
        _, diff_stat, _ = await self._run_git("diff", "--stat", "HEAD~1", "HEAD", cwd=shadow)
        files_changed = len([l for l in diff_stat.split("\n") if l.strip() and "|" in l])

        snapshot = GitSnapshot(
            checkpoint_id=checkpoint_id,
            commit_sha=sha,
            message=commit_msg,
            files_changed=files_changed,
        )
        self._snapshots[checkpoint_id] = snapshot

        logger.info(f"Git snapshot created: {sha[:8]} for checkpoint {checkpoint_id}")

        # Link to Thought Artifact if provided
        if thought_id:
            try:
                from .thought_service import get_thought_service
                from ..models.thought import LinkCommitRequest
                
                thought_service = get_thought_service()
                await thought_service.link_commit(
                    thought_id=thought_id,
                    req=LinkCommitRequest(
                        commit_sha=sha,
                        repo_path=workspace_path,
                        branch="checkpoint" 
                    ),
                    actor_id=actor_id or "system"
                )
                logger.info(f"🔗 Linked checkpoint {sha[:8]} to thought {thought_id}")
            except Exception as e:
                logger.error(f"Failed to link thought {thought_id}: {e}")

        return snapshot

    async def diff_from_checkpoint(
        self,
        workspace_path: str,
        checkpoint_id: str,
    ) -> str:
        """
        Get the diff of all changes since a checkpoint.

        Returns unified diff string.
        """
        snapshot = self._snapshots.get(checkpoint_id)
        if not snapshot:
            return "Checkpoint not found in git history"

        shadow = self._shadow_path(workspace_path)
        _, diff, _ = await self._run_git(
            "diff", snapshot.commit_sha, "HEAD", cwd=shadow
        )
        return diff or "(no changes since checkpoint)"

    async def restore_to_checkpoint(
        self,
        workspace_path: str,
        checkpoint_id: str,
    ) -> bool:
        """
        Restore the shadow repo state to a specific checkpoint.

        Returns True if restore succeeded.
        """
        snapshot = self._snapshots.get(checkpoint_id)
        if not snapshot:
            return False

        shadow = self._shadow_path(workspace_path)
        rc, _, err = await self._run_git(
            "checkout", snapshot.commit_sha, "--", ".", cwd=shadow
        )
        if rc != 0:
            logger.error(f"Failed to restore checkpoint {checkpoint_id}: {err}")
            return False

        logger.info(f"Restored to checkpoint {checkpoint_id} (commit {snapshot.commit_sha[:8]})")
        return True

    async def list_snapshots(
        self,
        workspace_path: str,
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """List recent git checkpoint commits."""
        shadow = self._shadow_path(workspace_path)
        if not os.path.isdir(os.path.join(shadow, ".git")):
            return []

        _, log, _ = await self._run_git(
            "log", f"--max-count={limit}", "--format=%H|%s|%aI", cwd=shadow
        )
        if not log:
            return []

        return [
            {"sha": parts[0], "message": parts[1], "date": parts[2]}
            for line in log.split("\n")
            if line and len(parts := line.split("|", 2)) == 3
        ]

    def get_snapshot(self, checkpoint_id: str) -> Optional[GitSnapshot]:
        return self._snapshots.get(checkpoint_id)


# Singleton
_git_checkpoint_service: Optional[GitCheckpointService] = None


def get_git_checkpoint_service() -> GitCheckpointService:
    global _git_checkpoint_service
    if _git_checkpoint_service is None:
        _git_checkpoint_service = GitCheckpointService()
    return _git_checkpoint_service
