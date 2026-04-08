"""
Execution Sandbox Hardening Tests.

Validates:
- Subprocess fallback blocked in production/staging
- Subprocess fallback allowed in development
- Cgroup parameters present in Docker command
- Post-execution violation detection
- SandboxUnavailableError raised correctly
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.praxis.sandbox import (
    DockerSandboxRunner,
    SandboxUnavailableError,
    _VIOLATION_PATTERNS,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Production Subprocess Fallback Block
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_sandbox_blocks_subprocess_in_production():
    """In production, if Docker is unavailable, SandboxUnavailableError is raised."""
    runner = DockerSandboxRunner()
    runner._environment = "production"
    runner._docker_available = False  # Simulate Docker unavailable

    with pytest.raises(SandboxUnavailableError, match="production/staging"):
        await runner.run("echo hello", timeout_sec=5.0)


@pytest.mark.asyncio
async def test_sandbox_blocks_subprocess_in_staging():
    """In staging, if Docker is unavailable, SandboxUnavailableError is raised."""
    runner = DockerSandboxRunner()
    runner._environment = "staging"
    runner._docker_available = False

    with pytest.raises(SandboxUnavailableError, match="production/staging"):
        await runner.run("echo hello", timeout_sec=5.0)


@pytest.mark.asyncio
async def test_sandbox_allows_subprocess_in_development():
    """In development, subprocess fallback is allowed with violation warning."""
    runner = DockerSandboxRunner()
    runner._environment = "development"
    runner._docker_available = False

    with patch("asyncio.wait_for") as mock_wait:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"hello", b""))
        mock_proc.returncode = 0
        mock_wait.return_value = mock_proc

        output, code, violations = await runner.run("echo hello", timeout_sec=5.0)
        assert "UNSANDBOXED" in violations[0]


@pytest.mark.asyncio
async def test_sandbox_blocks_docker_exec_failure_in_production():
    """In production, Docker exec failure also raises SandboxUnavailableError."""
    runner = DockerSandboxRunner()
    runner._environment = "production"
    runner._docker_available = True  # Docker is "available"

    with patch("asyncio.create_subprocess_exec", side_effect=OSError("Docker socket error")):
        with pytest.raises(SandboxUnavailableError, match="Docker execution failed"):
            await runner.run("echo hello", timeout_sec=5.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cgroup Parameters
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_sandbox_docker_cmd_includes_cgroup_limits():
    """Docker command includes pids-limit, nofile ulimit, and core dump disable."""
    runner = DockerSandboxRunner(pids_limit=50, nofile_limit=128)
    runner._docker_available = True

    captured_cmd = None

    async def capture_exec(*args, **kwargs):
        nonlocal captured_cmd
        captured_cmd = list(args)
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_proc.returncode = 0
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=capture_exec):
        await runner.run("echo test", timeout_sec=10.0)

    assert captured_cmd is not None
    cmd_str = " ".join(captured_cmd)

    assert "--pids-limit" in cmd_str
    assert "50" in cmd_str
    assert "--ulimit" in cmd_str
    assert "nofile=128:128" in cmd_str
    assert "core=0:0" in cmd_str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Post-Execution Violation Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_violation_detection_proc_access():
    """Detects /proc filesystem access in output."""
    violations = DockerSandboxRunner._detect_output_violations(
        "Reading /proc/1/status for PID info"
    )
    assert any("PROC_ACCESS" in v for v in violations)


def test_violation_detection_sys_access():
    """Detects /sys filesystem access in output."""
    violations = DockerSandboxRunner._detect_output_violations(
        "Trying to access /sys/class/net"
    )
    assert any("SYS_ACCESS" in v for v in violations)


def test_violation_detection_dev_access():
    """Detects restricted /dev access but allows /dev/null, /dev/zero, /dev/urandom."""
    # Restricted device should trigger
    violations_restricted = DockerSandboxRunner._detect_output_violations(
        "Opening /dev/sda for disk access"
    )
    assert any("DEV_ACCESS" in v for v in violations_restricted)

    # Safe devices should NOT trigger
    violations_safe = DockerSandboxRunner._detect_output_violations(
        "Writing to /dev/null and reading /dev/urandom"
    )
    assert not any("DEV_ACCESS" in v for v in violations_safe)


def test_violation_detection_mount_attempt():
    """Detects mount syscall attempts."""
    violations = DockerSandboxRunner._detect_output_violations(
        "mount /dev/sda1 /mnt"
    )
    assert any("MOUNT_ATTEMPT" in v for v in violations)


def test_violation_detection_clean_output():
    """Clean output produces no violations."""
    violations = DockerSandboxRunner._detect_output_violations(
        "Hello world! Result: 42\nDone processing."
    )
    assert violations == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SandboxUnavailableError Type
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_sandbox_unavailable_error_is_runtime_error():
    """SandboxUnavailableError inherits from RuntimeError."""
    err = SandboxUnavailableError("test")
    assert isinstance(err, RuntimeError)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OOM / Segfault Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_sandbox_detects_oom_kill():
    """Return code 137 is flagged as OOM_KILLED."""
    runner = DockerSandboxRunner()
    runner._docker_available = True

    async def mock_exec(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"killed", b""))
        mock_proc.returncode = 137
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        output, code, violations = await runner.run("stress --vm 1", timeout_sec=10.0)

    assert any("OOM_KILLED" in v for v in violations)


@pytest.mark.asyncio
async def test_sandbox_detects_segfault():
    """Return code 139 is flagged as SEGFAULT."""
    runner = DockerSandboxRunner()
    runner._docker_available = True

    async def mock_exec(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"segfault", b""))
        mock_proc.returncode = 139
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        output, code, violations = await runner.run("./crash", timeout_sec=10.0)

    assert any("SEGFAULT" in v for v in violations)
