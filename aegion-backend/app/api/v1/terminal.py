"""
Aegion API v1 - Sandboxed Terminal Execution.

Terminal execution with policy-enforced sandbox profiles.
Combines feature (sandboxed terminal profiles) and feature (built-in terminal).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import asyncio
import uuid
import re

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/terminal", tags=["terminal"])


# ========== Execution Profiles ==========


class TerminalProfile(BaseModel):
    """Sandbox profile defining allowed/blocked commands."""
    name: str
    description: str
    allowed_patterns: List[str]   # Regex patterns for allowed commands
    blocked_patterns: List[str]   # Regex patterns for blocked commands
    timeout_seconds: int = 60
    working_directory: Optional[str] = None
    env_vars: Dict[str, str] = {}
    max_output_bytes: int = 1_000_000  # 1MB


# Built-in profiles
DEFAULT_PROFILES: Dict[str, TerminalProfile] = {
    "build": TerminalProfile(
        name="build",
        description="Build and compile tools only",
        allowed_patterns=[r"npm\s+", r"npx\s+", r"yarn\s+", r"make\s+", r"cargo\s+", r"go\s+build", r"pip\s+install", r"python.*setup\.py"],
        blocked_patterns=[r"rm\s+-rf", r"sudo\s+", r"curl\s+.*\|.*sh", r"wget\s+.*\|.*sh"],
        timeout_seconds=300,
    ),
    "test": TerminalProfile(
        name="test",
        description="Test runners only",
        allowed_patterns=[r"pytest\s*", r"npm\s+test", r"npm\s+run\s+test", r"jest\s*", r"go\s+test", r"cargo\s+test"],
        blocked_patterns=[r"rm\s+", r"sudo\s+", r"curl\s+", r"wget\s+"],
        timeout_seconds=120,
    ),
    "lint": TerminalProfile(
        name="lint",
        description="Linters and formatters",
        allowed_patterns=[r"eslint\s*", r"prettier\s*", r"black\s*", r"ruff\s*", r"flake8\s*", r"mypy\s*", r"tsc\s+--noEmit"],
        blocked_patterns=[r"rm\s+", r"sudo\s+"],
        timeout_seconds=60,
    ),
    "read": TerminalProfile(
        name="read",
        description="Read-only file operations",
        allowed_patterns=[r"cat\s+", r"head\s+", r"tail\s+", r"ls\s*", r"find\s+", r"grep\s+", r"wc\s+", r"git\s+log", r"git\s+status", r"git\s+diff"],
        blocked_patterns=[r"rm\s+", r"mv\s+", r"cp\s+", r"chmod\s+", r"chown\s+", r"sudo\s+"],
        timeout_seconds=30,
    ),
    "unrestricted": TerminalProfile(
        name="unrestricted",
        description="Full terminal access (admin only)",
        allowed_patterns=[r".*"],
        blocked_patterns=[],
        timeout_seconds=300,
    ),
}

# Custom profiles
_custom_profiles: Dict[str, TerminalProfile] = {}


# ========== Execution History ==========
_executions: Dict[str, Dict[str, Any]] = {}


# ========== Models ==========


class ExecuteRequest(BaseModel):
    command: str
    profile: str = "read"
    working_directory: Optional[str] = None
    timeout_seconds: Optional[int] = None


class ExecutionResponse(BaseModel):
    execution_id: str
    command: str
    profile: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool = False


class ProfileResponse(BaseModel):
    name: str
    description: str
    allowed_patterns: List[str]
    blocked_patterns: List[str]
    timeout_seconds: int


# ========== Helpers ==========


def _get_profile(name: str) -> Optional[TerminalProfile]:
    return _custom_profiles.get(name) or DEFAULT_PROFILES.get(name)


def _check_policy(command: str, profile: TerminalProfile) -> tuple[bool, str]:
    """Check if command is allowed by profile policy."""
    # Check blocked patterns first
    for pattern in profile.blocked_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Command blocked by pattern: {pattern}"

    # Check allowed patterns
    if profile.allowed_patterns:
        for pattern in profile.allowed_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True, "Allowed"
        return False, "Command does not match any allowed pattern"

    return True, "No restrictions"


# ========== Endpoints ==========


@router.post("/execute", response_model=ExecutionResponse)
async def execute_command(
    request: ExecuteRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Execute a command in a sandboxed terminal profile."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    profile = _get_profile(request.profile)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile '{request.profile}'. Available: {list(DEFAULT_PROFILES.keys())}",
        )

    # Admin-only check for unrestricted
    if request.profile == "unrestricted" and user.role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Unrestricted profile requires admin role")

    # Policy check
    allowed, reason = _check_policy(request.command, profile)
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Policy violation: {reason}")

    timeout = request.timeout_seconds or profile.timeout_seconds
    cwd = request.working_directory or profile.working_directory
    execution_id = str(uuid.uuid4())
    start = datetime.now(timezone.utc)

    try:
        proc = await asyncio.create_subprocess_shell(
            request.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env={**dict(__import__("os").environ), **profile.env_vars},
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise HTTPException(
                status_code=408,
                detail=f"Command timed out after {timeout}s",
            )

        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        # Truncate large outputs
        truncated = False
        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")
        if len(stdout) > profile.max_output_bytes:
            stdout = stdout[:profile.max_output_bytes] + "\n... (truncated)"
            truncated = True

        result = ExecutionResponse(
            execution_id=execution_id,
            command=request.command,
            profile=request.profile,
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            duration_ms=elapsed,
            truncated=truncated,
        )

        _executions[execution_id] = {
            "result": result.model_dump(),
            "user": user.user_id,
            "timestamp": start.isoformat(),
        }

        logger.info(f"Terminal execution: {execution_id} profile={request.profile} exit={proc.returncode}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Terminal execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/profiles", response_model=List[ProfileResponse])
async def list_profiles(
    user: AuthorityContext = Depends(get_current_user),
):
    """List available terminal execution profiles."""
    all_profiles = {**DEFAULT_PROFILES, **_custom_profiles}
    return [
        ProfileResponse(
            name=p.name,
            description=p.description,
            allowed_patterns=p.allowed_patterns,
            blocked_patterns=p.blocked_patterns,
            timeout_seconds=p.timeout_seconds,
        )
        for p in all_profiles.values()
    ]


@router.get("/history")
async def list_executions(
    limit: int = 20,
    user: AuthorityContext = Depends(get_current_user),
):
    """List recent terminal executions."""
    executions = list(_executions.values())
    executions.sort(key=lambda e: e["timestamp"], reverse=True)
    return executions[:limit]
