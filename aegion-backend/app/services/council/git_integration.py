"""
Git-Native Integration Service — Phase 103.

Provides git-aware context for the council engine:
  - Current branch, uncommitted changes, recent commits
  - Diff extraction for proposal review
  - Commit message generation from council decisions
  - File change classification (risk assessment)

This is used by:
  - Council members to understand code context
  - Sentinel to assess change risk
  - Ghost text engine for project-aware completions
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ...core.logging import logger


class ChangeRisk(str, Enum):
    """Risk classification for file changes."""
    LOW = "low"           # Docs, tests, comments
    MEDIUM = "medium"     # Application logic
    HIGH = "high"         # Auth, security, config
    CRITICAL = "critical" # Migrations, deployments, secrets


@dataclass
class GitChange:
    """A single file change in the working tree."""
    file_path: str
    status: str        # "modified", "added", "deleted", "renamed"
    lines_added: int = 0
    lines_removed: int = 0
    risk: ChangeRisk = ChangeRisk.MEDIUM
    diff: str = ""


@dataclass
class GitContext:
    """Complete git context for a workspace."""
    branch: str = "unknown"
    is_clean: bool = True
    uncommitted_changes: List[GitChange] = field(default_factory=list)
    recent_commits: List[Dict[str, str]] = field(default_factory=list)
    total_lines_changed: int = 0


# High-risk file patterns
_RISK_PATTERNS = {
    ChangeRisk.CRITICAL: re.compile(
        r"(migration|deploy|Dockerfile|\.env|secret|cloudbuild|\.github/workflows)",
        re.IGNORECASE,
    ),
    ChangeRisk.HIGH: re.compile(
        r"(auth|security|password|permission|rbac|middleware|firewall|cors)",
        re.IGNORECASE,
    ),
    ChangeRisk.LOW: re.compile(
        r"\.(md|txt|rst|test\.\w+|spec\.\w+|__test__|_test\.py|\.snap)$",
        re.IGNORECASE,
    ),
}


class GitService:
    """
    Git context provider for the Aegion council ecosystem.

    All methods are async and shell out to `git` via asyncio.subprocess.
    Falls back gracefully if git is not available or the directory is not a repo.
    """

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = workspace_path

    async def get_context(self, commit_count: int = 10) -> GitContext:
        """Get comprehensive git context for the workspace."""
        ctx = GitContext()

        try:
            ctx.branch = await self._run("git rev-parse --abbrev-ref HEAD")
            status_raw = await self._run("git status --porcelain")
            ctx.is_clean = len(status_raw.strip()) == 0

            if not ctx.is_clean:
                ctx.uncommitted_changes = await self._parse_changes(status_raw)
                ctx.total_lines_changed = sum(
                    c.lines_added + c.lines_removed for c in ctx.uncommitted_changes
                )

            ctx.recent_commits = await self._get_recent_commits(commit_count)

        except Exception as e:
            logger.debug(f"Git context unavailable: {e}")

        return ctx

    async def get_diff(self, staged_only: bool = False) -> str:
        """Get the current diff (staged or unstaged)."""
        try:
            cmd = "git diff --cached" if staged_only else "git diff"
            return await self._run(cmd)
        except Exception:
            return ""

    async def get_file_diff(self, file_path: str) -> str:
        """Get diff for a specific file."""
        try:
            return await self._run(f"git diff -- {file_path}")
        except Exception:
            return ""

    async def generate_commit_message(self, style: str = "conventional") -> str:
        """
        Generate a commit message from the current staged changes.

        Returns a conventional-commits formatted message based on the diff.
        """
        diff = await self.get_diff(staged_only=True)
        if not diff:
            return "chore: empty commit"

        changes = await self._parse_changes(
            await self._run("git diff --cached --name-status")
        )

        # Classify the primary change type
        has_feat = any("feat" in c.file_path.lower() or c.status == "added" for c in changes)
        has_fix = any("fix" in c.file_path.lower() for c in changes)
        has_test = any("test" in c.file_path.lower() for c in changes)
        has_docs = any(c.risk == ChangeRisk.LOW for c in changes)

        if has_feat:
            prefix = "feat"
        elif has_fix:
            prefix = "fix"
        elif has_test:
            prefix = "test"
        elif has_docs:
            prefix = "docs"
        else:
            prefix = "chore"

        # Get the primary scope
        files = [c.file_path for c in changes]
        scope = self._detect_scope(files)

        # Build message
        file_list = ", ".join(os.path.basename(f) for f in files[:3])
        if len(files) > 3:
            file_list += f" (+{len(files) - 3} more)"

        return f"{prefix}({scope}): update {file_list}"

    def classify_risk(self, file_path: str) -> ChangeRisk:
        """Classify the risk level of a file change."""
        for risk, pattern in _RISK_PATTERNS.items():
            if pattern.search(file_path):
                return risk
        return ChangeRisk.MEDIUM

    def for_council_prompt(self, ctx: GitContext) -> str:
        """Format git context as a council-friendly prompt section."""
        lines = [
            f"Branch: {ctx.branch}",
            f"Uncommitted changes: {len(ctx.uncommitted_changes)} files, {ctx.total_lines_changed} lines",
        ]

        if ctx.uncommitted_changes:
            lines.append("\nChanged files:")
            for c in ctx.uncommitted_changes[:10]:
                lines.append(
                    f"  [{c.risk.value.upper()}] {c.status} {c.file_path} "
                    f"(+{c.lines_added}/-{c.lines_removed})"
                )

        if ctx.recent_commits:
            lines.append("\nRecent commits:")
            for commit in ctx.recent_commits[:5]:
                lines.append(f"  {commit.get('hash', '?')[:8]} {commit.get('message', '?')}")

        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    async def _run(self, cmd: str) -> str:
        """Run a git command and return stdout."""
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {cmd} → {stderr.decode().strip()}")
        return stdout.decode().strip()

    async def _parse_changes(self, status_raw: str) -> List[GitChange]:
        """Parse git status --porcelain output into GitChange objects."""
        changes = []
        for line in status_raw.strip().split("\n"):
            if not line.strip():
                continue
            status_code = line[:2].strip()
            file_path = line[3:].strip()

            status_map = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed"}
            status = status_map.get(status_code[0] if status_code else "?", "modified")

            # Get line counts
            try:
                numstat = await self._run(f"git diff --numstat -- {file_path}")
                parts = numstat.split("\t")
                added = int(parts[0]) if parts[0] != "-" else 0
                removed = int(parts[1]) if len(parts) > 1 and parts[1] != "-" else 0
            except Exception:
                added, removed = 0, 0

            changes.append(GitChange(
                file_path=file_path,
                status=status,
                lines_added=added,
                lines_removed=removed,
                risk=self.classify_risk(file_path),
            ))

        return changes

    async def _get_recent_commits(self, count: int) -> List[Dict[str, str]]:
        """Get recent commit log."""
        try:
            log = await self._run(
                f"git log --oneline --no-decorate -n {count} --format='%h|%s|%an|%ar'"
            )
            commits = []
            for line in log.split("\n"):
                parts = line.strip("'").split("|")
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "time": parts[3],
                    })
            return commits
        except Exception:
            return []

    def _detect_scope(self, files: List[str]) -> str:
        """Detect the scope (component) from a list of files."""
        # Find common directory
        if not files:
            return "general"
        dirs = [os.path.dirname(f) for f in files]
        common = os.path.commonpath(dirs) if dirs else ""
        parts = common.split("/")
        # Use the last meaningful directory name
        for part in reversed(parts):
            if part and part not in (".", "src", "app", "lib"):
                return part
        return "general"


# ──────────────────────────────────────────────
# Singleton factory
# ──────────────────────────────────────────────

_instances: Dict[str, GitService] = {}


def get_git_service(workspace_path: str) -> GitService:
    """Get or create a GitService for the given workspace."""
    if workspace_path not in _instances:
        _instances[workspace_path] = GitService(workspace_path)
    return _instances[workspace_path]
