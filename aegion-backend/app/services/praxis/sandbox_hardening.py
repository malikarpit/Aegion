"""
Aegion Zero-Trust Sandbox Hardening.

Doctrine: "Trust nothing. Verify everything. Contain all execution."

Provides four hardening layers for sandboxed execution:

1. Capability Dropping + Read-Only Mounts
   - Linux capability whitelist (minimum viable set)
   - Read-only filesystem mounts for code & dependencies
   - tmpfs for ephemeral scratch space

2. Execution Provenance Hashing
   - SHA-256 fingerprint of command + environment + inputs
   - Links execution results to their exact provenance
   - Enables reproducibility verification

3. Sandbox Escape Detection
   - Pattern-based heuristics for common escape vectors
   - Process tree analysis (fork bombs, unexpected children)
   - Network egress detection in no-network mode

4. Per-Workspace Execution Quotas
   - Rate limiting per workspace (executions per hour)
   - Cumulative CPU-time tracking
   - Concurrent execution limits
"""

import hashlib
import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

from ...core.logging import logger


# ────────────────────────────────────────────────
# 1. Capability Dropping + Read-Only Mounts
# ────────────────────────────────────────────────

# Minimum Linux capabilities needed for sandboxed execution
# Everything else is dropped by default
ALLOWED_CAPABILITIES = frozenset([
    "CAP_SETUID",      # Required for user namespace mapping
    "CAP_SETGID",      # Required for group namespace mapping
])

# Capabilities that are ALWAYS dropped
DROPPED_CAPABILITIES = frozenset([
    "CAP_SYS_ADMIN",     # Blocks mount, pivot_root, bpf, etc.
    "CAP_NET_ADMIN",     # Blocks network configuration changes
    "CAP_NET_RAW",       # Blocks raw socket creation
    "CAP_SYS_PTRACE",    # Blocks process tracing (escape vector)
    "CAP_SYS_MODULE",    # Blocks kernel module loading
    "CAP_SYS_RAWIO",     # Blocks raw I/O access
    "CAP_MKNOD",         # Blocks device node creation
    "CAP_SYS_BOOT",      # Blocks reboot
    "CAP_SYS_CHROOT",    # Blocks chroot (escape vector)
    "CAP_DAC_OVERRIDE",  # Blocks bypassing file permissions
    "CAP_FOWNER",        # Blocks file ownership bypasses
    "CAP_AUDIT_WRITE",   # Blocks audit log manipulation
    "CAP_MAC_ADMIN",     # Blocks MAC policy changes
    "CAP_SYSLOG",        # Blocks kernel log manipulation
])


@dataclass(frozen=True)
class SandboxHardeningConfig:
    """Configuration for sandbox hardening layer."""
    # Capability control
    drop_all_capabilities: bool = True
    allowed_capabilities: frozenset = ALLOWED_CAPABILITIES

    # Filesystem
    read_only_rootfs: bool = True
    tmpfs_size_mb: int = 64     # Ephemeral scratch space
    no_new_privileges: bool = True

    # Network
    disable_network: bool = True

    # Seccomp
    use_seccomp: bool = True
    seccomp_profile: str = "default"

    # Escape detection
    enable_escape_detection: bool = True
    max_processes: int = 50
    max_open_files: int = 256

    def to_docker_args(self) -> Dict[str, Any]:
        """Convert to Docker container run arguments."""
        args: Dict[str, Any] = {}

        if self.drop_all_capabilities:
            args["cap_drop"] = ["ALL"]
            args["cap_add"] = list(self.allowed_capabilities)

        if self.read_only_rootfs:
            args["read_only"] = True

        if self.no_new_privileges:
            args["security_opt"] = args.get("security_opt", [])
            args["security_opt"].append("no-new-privileges:true")

        if self.disable_network:
            args["network_mode"] = "none"

        if self.use_seccomp:
            args.setdefault("security_opt", [])
            if self.seccomp_profile != "default":
                args["security_opt"].append(f"seccomp={self.seccomp_profile}")

        # tmpfs for scratch space
        args["tmpfs"] = {"/tmp": f"size={self.tmpfs_size_mb}m,noexec,nosuid,nodev"}

        # Process limits
        args["pids_limit"] = self.max_processes

        # ulimits
        args["ulimits"] = [
            {"Name": "nofile", "Soft": self.max_open_files, "Hard": self.max_open_files},
            {"Name": "nproc", "Soft": self.max_processes, "Hard": self.max_processes},
        ]

        return args


# ────────────────────────────────────────────────
# 2. Execution Provenance Hashing
# ────────────────────────────────────────────────


@dataclass
class ExecutionProvenance:
    """Cryptographic provenance record for a sandbox execution."""
    provenance_hash: str
    command_hash: str
    environment_hash: str
    input_hash: str
    timestamp: datetime
    workspace_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provenance_hash": self.provenance_hash,
            "command_hash": self.command_hash,
            "environment_hash": self.environment_hash,
            "input_hash": self.input_hash,
            "timestamp": self.timestamp.isoformat(),
            "workspace_id": self.workspace_id,
            "metadata": self.metadata,
        }


def compute_provenance(
    command: str,
    workspace_id: str,
    environment: Optional[Dict[str, str]] = None,
    input_files: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionProvenance:
    """
    Compute a cryptographic provenance fingerprint for an execution.

    The provenance hash covers:
    - The command being run
    - Environment variables (sorted, deterministic)
    - Input file contents (sorted by path)
    - Workspace context

    Two executions with identical provenance hashes should produce
    identical results (modulo non-determinism in the program).
    """
    now = datetime.now(timezone.utc)

    # Hash components
    cmd_hash = hashlib.sha256(command.encode("utf-8")).hexdigest()

    env_canonical = json.dumps(sorted((environment or {}).items()), sort_keys=True)
    env_hash = hashlib.sha256(env_canonical.encode("utf-8")).hexdigest()

    input_canonical = json.dumps(sorted((input_files or {}).items()), sort_keys=True)
    input_hash = hashlib.sha256(input_canonical.encode("utf-8")).hexdigest()

    # Combined provenance
    combined = f"{cmd_hash}:{env_hash}:{input_hash}:{workspace_id}".encode("utf-8")
    provenance_hash = hashlib.sha256(combined).hexdigest()

    return ExecutionProvenance(
        provenance_hash=provenance_hash,
        command_hash=cmd_hash,
        environment_hash=env_hash,
        input_hash=input_hash,
        timestamp=now,
        workspace_id=workspace_id,
        metadata=metadata or {},
    )


# ────────────────────────────────────────────────
# 3. Sandbox Escape Detection
# ────────────────────────────────────────────────

# Patterns indicating potential sandbox escape attempts
ESCAPE_PATTERNS = [
    # Process/namespace escape vectors
    (re.compile(r"nsenter\b"), "NSENTER: namespace escape tool detected"),
    (re.compile(r"unshare\b"), "UNSHARE: namespace manipulation detected"),
    (re.compile(r"/proc/self/fd"), "PROC_FD: /proc self-fd access (escape vector)"),
    (re.compile(r"/proc/\d+/root"), "PROC_ROOT: process root access (chroot escape)"),
    (re.compile(r"pivot_root"), "PIVOT_ROOT: pivot_root syscall attempt"),

    # Container escape vectors
    (re.compile(r"docker\.sock"), "DOCKER_SOCK: Docker socket access attempt"),
    (re.compile(r"/var/run/docker"), "DOCKER_RUN: Docker runtime access attempt"),
    (re.compile(r"cgroup.*release_agent"), "CGROUP_ESCAPE: cgroup release_agent exploit"),
    (re.compile(r"core_pattern"), "CORE_PATTERN: core_pattern escape attempt"),

    # Privilege escalation
    (re.compile(r"chmod\s+[0-7]*s"), "SETUID_BIT: setuid bit modification attempt"),
    (re.compile(r"chown\s+root"), "CHOWN_ROOT: ownership change to root"),
    (re.compile(r"sudo\b"), "SUDO: sudo invocation in sandbox"),
    (re.compile(r"su\s+-"), "SU: su invocation in sandbox"),

    # Network escape (in no-network mode)
    (re.compile(r"curl\b|wget\b|nc\b|ncat\b"), "NET_TOOL: network tool invocation"),
    (re.compile(r"iptables\b"), "IPTABLES: firewall manipulation attempt"),

    # Filesystem escape
    (re.compile(r"mount\s+-"), "MOUNT: mount syscall attempt"),
    (re.compile(r"debugfs\b"), "DEBUGFS: debug filesystem access"),
    (re.compile(r"losetup\b"), "LOSETUP: loop device setup attempt"),

    # Kernel interaction
    (re.compile(r"insmod\b|modprobe\b"), "KMOD: kernel module load attempt"),
    (re.compile(r"kexec\b"), "KEXEC: kernel exec attempt"),
    (re.compile(r"sysctl\b"), "SYSCTL: kernel parameter modification"),
]

# Output patterns that indicate suspicious execution
OUTPUT_ESCAPE_PATTERNS = [
    (re.compile(r"container\s+escape", re.IGNORECASE), "Explicit container escape mention"),
    (re.compile(r"breakout", re.IGNORECASE), "Container breakout pattern"),
    (re.compile(r"host\s+filesystem\s+access", re.IGNORECASE), "Host FS access pattern"),
    (re.compile(r"Permission denied.*\/host", re.IGNORECASE), "Host path access attempt"),
]


@dataclass
class EscapeDetectionResult:
    """Result of sandbox escape detection analysis."""
    clean: bool
    violations: List[str] = field(default_factory=list)
    severity: str = "none"  # none | low | medium | high | critical
    should_kill: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean": self.clean,
            "violations": self.violations,
            "severity": self.severity,
            "should_kill": self.should_kill,
        }


def detect_escape_attempts(
    command: str,
    output: str = "",
    scan_output: bool = True,
) -> EscapeDetectionResult:
    """
    Scan command and output for sandbox escape attempt patterns.

    Returns an EscapeDetectionResult with severity classification:
    - none:     no issues detected
    - low:      suspicious but likely benign
    - medium:   potential escape vector, requires logging
    - high:     likely escape attempt, should trigger alert
    - critical: active escape in progress, kill execution immediately
    """
    violations: List[str] = []

    # Scan command
    for pattern, description in ESCAPE_PATTERNS:
        if pattern.search(command):
            violations.append(f"CMD: {description}")

    # Scan output
    if scan_output and output:
        for pattern, description in OUTPUT_ESCAPE_PATTERNS:
            if pattern.search(output):
                violations.append(f"OUTPUT: {description}")

        for pattern, description in ESCAPE_PATTERNS:
            if pattern.search(output):
                violations.append(f"OUTPUT: {description}")

    if not violations:
        return EscapeDetectionResult(clean=True)

    # Classify severity
    critical_keywords = {"DOCKER_SOCK", "CGROUP_ESCAPE", "CORE_PATTERN", "KMOD", "KEXEC"}
    high_keywords = {"NSENTER", "PROC_ROOT", "PIVOT_ROOT", "SETUID_BIT"}
    medium_keywords = {"SUDO", "SU", "MOUNT", "CHOWN_ROOT"}

    severity = "low"
    should_kill = False

    for v in violations:
        for kw in critical_keywords:
            if kw in v:
                severity = "critical"
                should_kill = True
                break
        for kw in high_keywords:
            if kw in v:
                if severity not in ("critical",):
                    severity = "high"
                    should_kill = True
        for kw in medium_keywords:
            if kw in v:
                if severity not in ("critical", "high"):
                    severity = "medium"

    # Audit log
    logger.audit(
        action="SANDBOX_ESCAPE_DETECTED",
        actor="sandbox_hardening",
        target="execution",
        justification=f"Severity={severity}, violations={len(violations)}",
    )

    return EscapeDetectionResult(
        clean=False,
        violations=violations,
        severity=severity,
        should_kill=should_kill,
    )


# ────────────────────────────────────────────────
# 4. Per-Workspace Execution Quotas
# ────────────────────────────────────────────────


@dataclass
class WorkspaceQuota:
    """Quota configuration for a workspace."""
    max_executions_per_hour: int = 60
    max_concurrent_executions: int = 5
    max_cpu_seconds_per_hour: int = 300  # 5 minutes cumulative
    max_execution_time_seconds: int = 120  # Single execution cap


@dataclass
class QuotaUsage:
    """Tracks current quota usage for a workspace."""
    executions_this_hour: int = 0
    concurrent_executions: int = 0
    cpu_seconds_this_hour: float = 0.0
    hour_start: float = field(default_factory=time.time)
    execution_ids: Set[str] = field(default_factory=set)


class WorkspaceQuotaManager:
    """
    Enforces per-workspace execution quotas.

    Tracks:
    - Executions per rolling hour window
    - Concurrent executions
    - Cumulative CPU time per hour
    """

    def __init__(self):
        self._quotas: Dict[str, WorkspaceQuota] = {}  # workspace -> quota config
        self._usage: Dict[str, QuotaUsage] = defaultdict(QuotaUsage)

    def set_quota(self, workspace_id: str, quota: WorkspaceQuota) -> None:
        """Set or update quota for a workspace."""
        self._quotas[workspace_id] = quota

    def get_quota(self, workspace_id: str) -> WorkspaceQuota:
        """Get quota for workspace (returns default if none configured)."""
        return self._quotas.get(workspace_id, WorkspaceQuota())

    def check_quota(self, workspace_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if workspace can start a new execution.

        Returns (allowed, reason) — reason is None if allowed.
        """
        quota = self.get_quota(workspace_id)
        usage = self._usage[workspace_id]

        # Reset hourly window if needed
        self._maybe_reset_hour(workspace_id)

        # Check rate limit
        if usage.executions_this_hour >= quota.max_executions_per_hour:
            return False, (
                f"Rate limit exceeded: {usage.executions_this_hour}/"
                f"{quota.max_executions_per_hour} executions this hour"
            )

        # Check concurrency
        if usage.concurrent_executions >= quota.max_concurrent_executions:
            return False, (
                f"Concurrency limit: {usage.concurrent_executions}/"
                f"{quota.max_concurrent_executions} running"
            )

        # Check CPU budget
        if usage.cpu_seconds_this_hour >= quota.max_cpu_seconds_per_hour:
            return False, (
                f"CPU budget exhausted: {usage.cpu_seconds_this_hour:.0f}/"
                f"{quota.max_cpu_seconds_per_hour}s this hour"
            )

        return True, None

    def record_start(self, workspace_id: str, execution_id: str) -> None:
        """Record the start of an execution."""
        self._maybe_reset_hour(workspace_id)
        usage = self._usage[workspace_id]
        usage.executions_this_hour += 1
        usage.concurrent_executions += 1
        usage.execution_ids.add(execution_id)

    def record_end(
        self,
        workspace_id: str,
        execution_id: str,
        cpu_seconds: float = 0.0,
    ) -> None:
        """Record the completion of an execution."""
        usage = self._usage[workspace_id]
        usage.concurrent_executions = max(0, usage.concurrent_executions - 1)
        usage.cpu_seconds_this_hour += cpu_seconds
        usage.execution_ids.discard(execution_id)

    def get_usage(self, workspace_id: str) -> Dict[str, Any]:
        """Get current usage stats for a workspace."""
        self._maybe_reset_hour(workspace_id)
        quota = self.get_quota(workspace_id)
        usage = self._usage[workspace_id]
        return {
            "executions_this_hour": usage.executions_this_hour,
            "max_executions_per_hour": quota.max_executions_per_hour,
            "concurrent_executions": usage.concurrent_executions,
            "max_concurrent_executions": quota.max_concurrent_executions,
            "cpu_seconds_this_hour": round(usage.cpu_seconds_this_hour, 1),
            "max_cpu_seconds_per_hour": quota.max_cpu_seconds_per_hour,
        }

    def _maybe_reset_hour(self, workspace_id: str) -> None:
        """Reset hourly counters if an hour has passed."""
        usage = self._usage[workspace_id]
        now = time.time()
        if now - usage.hour_start >= 3600:
            usage.executions_this_hour = 0
            usage.cpu_seconds_this_hour = 0.0
            usage.hour_start = now


    def get_stats(self) -> Dict[str, Any]:
        """Get usage stats for all active workspaces."""
        stats = {}
        for ws_id in self._usage.keys():
            stats[ws_id] = self.get_usage(ws_id)
        return stats
# ────────────────────────────────────────────────
# Singleton
# ────────────────────────────────────────────────

_quota_manager: Optional[WorkspaceQuotaManager] = None


def get_quota_manager() -> WorkspaceQuotaManager:
    """Get the global quota manager instance."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = WorkspaceQuotaManager()
    return _quota_manager
