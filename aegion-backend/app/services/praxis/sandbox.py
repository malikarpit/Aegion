"""
Aegion Praxis - Sandboxed Execution Service.

Phase 4: Execution & Resilience
Isolated execution environment for high-risk actions.

security Hardening:
- Subprocess fallback blocked in production/staging
- Cgroup enforcement: pids-limit, ulimit, core dump disable
- Post-execution violation detection
- Network egress isolation by default
"""

from typing import Optional, Dict, Any, List
import uuid
import asyncio
import subprocess
import tempfile
import os
import re
import resource
import shutil

from ...contracts.execution import (
    ExecutionDescriptor,
    ExecutionRequest,
    ExecutionResult,
    SandboxConfig,
    RiskLevel
)
from ...core.config import settings
from ...core.logging import logger
from ...core.time import TimeAuthority
from .registry import get_descriptor_registry


# ========== Production Safety ==========

class SandboxUnavailableError(RuntimeError):
    """Raised when Docker is required but unavailable in production/staging."""
    pass


# Patterns that indicate suspicious sandbox activity
_VIOLATION_PATTERNS = [
    (re.compile(r'/proc/\d+/'), "PROC_ACCESS: attempted to read /proc filesystem"),
    (re.compile(r'/sys/'), "SYS_ACCESS: attempted to read /sys filesystem"),
    (re.compile(r'/dev/(?!null|zero|urandom|random)'), "DEV_ACCESS: attempted to access restricted device"),
    (re.compile(r'mount\s'), "MOUNT_ATTEMPT: attempted mount syscall"),
]


class DockerSandboxRunner:
    """
    Runs commands inside ephemeral Docker containers with resource limits.

    Security Guarantees:
    - In production/staging: Docker is REQUIRED. No subprocess fallback.
    - Cgroup enforcement: memory, CPU, PIDs, file descriptors, core dumps.
    - Network isolation: --network=none by default.
    - Read-only rootFS with tmpfs for /tmp.
    - All Linux capabilities dropped.
    - Seccomp profile restricts dangerous syscalls.
    """

    # Environments where subprocess fallback is forbidden
    _PRODUCTION_ENVIRONMENTS = frozenset({"production", "staging"})

    def __init__(
        self,
        image: str = "python:3.12-slim",
        hardening_config: Optional['SandboxHardeningConfig'] = None,
        memory_limit_mb: int = 256,
        cpu_limit: float = 1.0,
        network_enabled: bool = False,
        pids_limit: int = 100,
        nofile_limit: int = 256,
    ):
        from .sandbox_hardening import SandboxHardeningConfig
        self.image = image
        self.hardening_config = hardening_config or SandboxHardeningConfig()
        # Overrides from legacy init args if needed, but prefer config
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        self.pids_limit = pids_limit
        self.nofile_limit = nofile_limit
        self._docker_available: Optional[bool] = None
        self._environment = getattr(settings, 'environment', 'development')

    async def docker_available(self) -> bool:
        """Check once whether Docker daemon is reachable."""
        if self._docker_available is not None:
            return self._docker_available
        if not shutil.which("docker"):
            self._docker_available = False
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await proc.wait()
            self._docker_available = proc.returncode == 0
        except Exception:
            self._docker_available = False
        return self._docker_available

    def _seccomp_profile_path(self) -> str:
        """Get absolute path to the seccomp profile JSON."""
        return os.path.join(os.path.dirname(__file__), "seccomp_profile.json")

    @property
    def _is_production(self) -> bool:
        """Check if running in a production-class environment."""
        return self._environment in self._PRODUCTION_ENVIRONMENTS

    async def run(
        self,
        command: str,
        timeout_sec: float,
        working_directory: Optional[str] = None,
    ) -> tuple[str, int, List[str]]:
        """
        Execute *command* inside a Docker container.

        Returns (output, return_code, violations).

        Security:
        - In production/staging: raises SandboxUnavailableError if Docker is not available.
        - In development: falls back to subprocess with violation warning.
        - Pre-execution escape detection on command text.
        """
        violations: List[str] = []

        # Pre-execution escape detection
        from .sandbox_hardening import detect_escape_attempts
        pre_check = detect_escape_attempts(command, output="", scan_output=False)
        if not pre_check.clean:
            violations.extend(pre_check.violations)
            if pre_check.should_kill:
                logger.audit(
                    action="SANDBOX_EXECUTION_BLOCKED",
                    actor="sandbox_hardening",
                    target="pre_execution",
                    justification=f"Escape attempt detected (severity={pre_check.severity}): {pre_check.violations}",
                )
                return "", 1, violations
        if not await self.docker_available():
            if self._is_production:
                logger.error(
                    "SECURITY: Docker unavailable in production. "
                    "Subprocess fallback is BLOCKED.",
                    extra={"environment": self._environment, "command_prefix": command[:50]},
                )
                raise SandboxUnavailableError(
                    "Docker is required in production/staging environments. "
                    "Subprocess fallback is disabled for security."
                )
            return await self._subprocess_fallback(
                command, timeout_sec, working_directory
            )

        # Build arguments from hardening config
        # We overlay legacy overrides (network_enabled) on top of config if needed
        # But generally we trust the config object.
        
        # If network was explicitly enabled via legacy arg/method, we override config
        if self.network_enabled:
             # Create a new config with network enabled (unsafe copy)
             from dataclasses import replace
             run_config = replace(self.hardening_config, disable_network=False)
        else:
             run_config = self.hardening_config

        # Map resource limits from legacy args if they differ from default
        # (This logic is a bit messy due to partial migration, simplifying to use legacy args for limits)
        
        docker_args = run_config.to_docker_args()
        
        # Override resource limits with current instance values (which might have been set by descriptor)
        docker_args["pids_limit"] = self.pids_limit
        
        # Construct command line
        docker_cmd = ["docker", "run", "--rm"]
        
        # Apply args from config
        if docker_args.get("network_mode"):
            docker_cmd.extend(["--network", docker_args["network_mode"]])
        
        # Add identification labels
        docker_cmd.extend(["--label", "aegion.sandbox=true"])
        
        if docker_args.get("read_only"):
            docker_cmd.append("--read-only")
            
        if docker_args.get("cap_drop"):
            for cap in docker_args["cap_drop"]:
                docker_cmd.extend(["--cap-drop", cap])
                
        if docker_args.get("cap_add"):
            for cap in docker_args["cap_add"]:
                docker_cmd.extend(["--cap-add", cap])
                
        if docker_args.get("security_opt"):
            for opt in docker_args["security_opt"]:
                docker_cmd.extend(["--security-opt", opt])
                
        if docker_args.get("tmpfs"):
            for mount, opts in docker_args["tmpfs"].items():
                docker_cmd.extend(["--tmpfs", f"{mount}:{opts}"])
                
        # Resource limits
        docker_cmd.extend(["--memory", f"{self.memory_limit_mb}m"])
        docker_cmd.extend(["--cpus", str(self.cpu_limit)])
        docker_cmd.extend(["--pids-limit", str(self.pids_limit)])
        docker_cmd.extend(["--ulimit", f"nofile={self.nofile_limit}:{self.nofile_limit}"])
        docker_cmd.extend(["--ulimit", "core=0:0"]) # Always disable core dumps
        
        # Explicitly add seccomp if requested and not 'default'
        # The to_docker_args handles logic, but we need the path
        if run_config.use_seccomp:
             docker_cmd.extend(["--security-opt", "seccomp=" + self._seccomp_profile_path()])

        if working_directory:
            docker_cmd.extend(["-v", f"{working_directory}:/workspace:ro", "-w", "/workspace"])

        docker_cmd.extend([self.image, "sh", "-c", command])

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ),
                timeout=timeout_sec,
            )
            stdout, stderr = await proc.communicate()
            output = (stdout.decode(errors="replace") + stderr.decode(errors="replace"))[:10000]

            # Check for resource violations
            if proc.returncode == 137:
                violations.append("OOM_KILLED: container exceeded memory limit")
            elif proc.returncode == 139:
                violations.append("SEGFAULT: container process crashed")

            # Post-execution violation detection
            violations.extend(self._detect_output_violations(output))

            # Enhanced post-execution escape detection
            post_check = detect_escape_attempts(command, output=output, scan_output=True)
            if not post_check.clean:
                violations.extend(post_check.violations)
                logger.audit(
                    action="SANDBOX_ESCAPE_POST_EXEC",
                    actor="sandbox_hardening",
                    target="post_execution",
                    justification=f"Severity={post_check.severity}, violations={len(post_check.violations)}",
                )

            if violations:
                logger.warning(
                    "Sandbox execution violations detected",
                    extra={
                        "violations": violations,
                        "return_code": proc.returncode,
                        "command_prefix": command[:50],
                    },
                )

            return output, proc.returncode or 0, violations

        except asyncio.TimeoutError:
            violations.append(f"TIMEOUT: exceeded {timeout_sec}s")
            raise
        except Exception as e:
            if self._is_production:
                logger.error(
                    "SECURITY: Docker exec failed in production. "
                    "Subprocess fallback is BLOCKED.",
                    extra={"error": str(e), "environment": self._environment},
                )
                raise SandboxUnavailableError(
                    f"Docker execution failed in production: {e}. "
                    "Subprocess fallback is disabled for security."
                )
            logger.warning(f"Docker exec failed, falling back to subprocess: {e}")
            return await self._subprocess_fallback(
                command, timeout_sec, working_directory
            )

    # ---- private ----

    @staticmethod
    def _detect_output_violations(output: str) -> List[str]:
        """Scan container output for suspicious activity patterns."""
        found: List[str] = []
        for pattern, description in _VIOLATION_PATTERNS:
            if pattern.search(output):
                found.append(description)
        return found

    async def _subprocess_fallback(
        self,
        command: str,
        timeout_sec: float,
        working_directory: Optional[str] = None,
    ) -> tuple[str, int, List[str]]:
        """
        Plain subprocess execution (no isolation).

        WARNING: Only available in development. Blocked in production/staging.
        """
        violations = ["UNSANDBOXED: Docker unavailable — executing without container isolation"]
        logger.warning(
            "SECURITY: Executing command without sandbox isolation",
            extra={"environment": self._environment, "command_prefix": command[:50]},
        )
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_directory,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise asyncio.TimeoutError(f"TIMEOUT: exceeded {timeout_sec}s")
            
        output = (stdout.decode(errors="replace") + stderr.decode(errors="replace"))[:10000]
        return output, proc.returncode or 0, violations


class SandboxService:
    """
    Service for executing actions in isolated environments.
    
    Features:
    - Timeout enforcement
    - Output capture
    - Resource isolation (Docker when available)
    - Violation detection
    """
    
    def __init__(self):
        self._executions: Dict[str, ExecutionResult] = {}
        self._docker_runner = DockerSandboxRunner()
    
    async def execute(
        self,
        request: ExecutionRequest,
        sandbox_config: Optional[SandboxConfig] = None
    ) -> ExecutionResult:
        """
        Execute an action, applying sandbox if configured.
        """
        registry = get_descriptor_registry()
        descriptor = await registry.get(request.descriptor_id)
        
        if not descriptor:
            return self._create_error_result(
                request,
                "DESCRIPTOR_NOT_FOUND",
                f"Unknown descriptor: {request.descriptor_id}"
            )
        
        # Check if approval required
        if descriptor.requires_approval:
            # In production, check approval status
            logger.info(f"Approval required for {descriptor.name}")
        
        # Determine sandbox
        use_sandbox = descriptor.requires_sandbox
        config = sandbox_config or SandboxConfig()
        
        started_at = TimeAuthority.now()
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Execute based on action type
            output, return_code, violations = await self._execute_action(
                descriptor,
                request,
                config if use_sandbox else None
            )
            
            end_time = asyncio.get_event_loop().time()
            duration_ms = int((end_time - start_time) * 1000)
            
            result = ExecutionResult(
                request_id=request.request_id,
                descriptor_id=request.descriptor_id,
                status="success" if return_code == 0 else "failed",
                output=output,
                return_code=return_code,
                started_at=started_at,
                completed_at=TimeAuthority.now(),
                duration_ms=duration_ms,
                was_sandboxed=use_sandbox,
                sandbox_violations=violations
            )
            
        except asyncio.TimeoutError:
            end_time = asyncio.get_event_loop().time()
            duration_ms = int((end_time - start_time) * 1000)
            
            result = ExecutionResult(
                request_id=request.request_id,
                descriptor_id=request.descriptor_id,
                status="timeout",
                error=f"Exceeded timeout of {descriptor.timeout_ms}ms",
                started_at=started_at,
                completed_at=TimeAuthority.now(),
                duration_ms=duration_ms,
                was_sandboxed=use_sandbox
            )
            
        except Exception as e:
            end_time = asyncio.get_event_loop().time()
            duration_ms = int((end_time - start_time) * 1000)
            
            result = ExecutionResult(
                request_id=request.request_id,
                descriptor_id=request.descriptor_id,
                status="failed",
                error=str(e),
                started_at=started_at,
                completed_at=TimeAuthority.now(),
                duration_ms=duration_ms,
                was_sandboxed=use_sandbox
            )
        
        self._executions[result.request_id] = result
        
        logger.audit(
            action="EXECUTION_COMPLETED",
            actor=request.requested_by,
            target=request.request_id,
            justification=f"Executed {descriptor.name}",
            metadata={
                "status": result.status,
                "duration_ms": result.duration_ms,
                "sandboxed": result.was_sandboxed
            }
        )
        
        return result
    
    async def _execute_action(
        self,
        descriptor: ExecutionDescriptor,
        request: ExecutionRequest,
        sandbox_config: Optional[SandboxConfig]
    ) -> tuple[Optional[str], int, list[str]]:
        """
        Execute the actual action with optional sandboxing.
        Returns (output, return_code, violations).
        """
        violations = []
        
        # Simulated execution for now
        # In production, this would dispatch to actual executors
        action_type = descriptor.action_type.value
        
        if action_type == "file_read":
            path = request.parameters.get("path", "")
            if sandbox_config and not self._validate_path(path, sandbox_config):
                violations.append(f"Path outside sandbox: {path}")
                return None, 1, violations
            
            try:
                with open(path, 'r') as f:
                    content = f.read()
                return content[:10000], 0, violations  # Limit output
            except Exception as e:
                return str(e), 1, violations
        
        elif action_type == "shell_command":
            command = request.parameters.get("command", "echo 'no command'")
            timeout_sec = descriptor.timeout_ms / 1000

            if sandbox_config:
                # Configure Docker runner per-request
                self._docker_runner.network_enabled = not sandbox_config.isolate_network
                if sandbox_config.working_directory:
                    working_dir = sandbox_config.working_directory
                else:
                    working_dir = None
            else:
                working_dir = None

            output, return_code, docker_violations = await self._docker_runner.run(
                command=command,
                timeout_sec=timeout_sec,
                working_directory=working_dir,
            )
            violations.extend(docker_violations)
            return output, return_code, violations
        
        else:
            # Implement file_write and api_call action types
            if action_type == "file_write":
                path = request.parameters.get("path", "")
                content = request.parameters.get("content", "")
                if sandbox_config and not self._validate_path(path, sandbox_config):
                    violations.append(f"Path outside sandbox: {path}")
                    return None, 1, violations
                try:
                    import os
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    with open(path, 'w') as f:
                        f.write(content)
                    return f"Written {len(content)} bytes to {path}", 0, violations
                except Exception as e:
                    return str(e), 1, violations

            elif action_type == "api_call":
                url = request.parameters.get("url", "")
                method = request.parameters.get("method", "GET").upper()
                body = request.parameters.get("body")
                try:
                    import aiohttp
                    timeout_sec = descriptor.timeout_ms / 1000
                    async with aiohttp.ClientSession() as session:
                        async with session.request(
                            method, url,
                            json=body if body else None,
                            timeout=aiohttp.ClientTimeout(total=timeout_sec)
                        ) as resp:
                            text = await resp.text()
                            return text[:10000], resp.status, violations
                except ImportError:
                    return "aiohttp not installed — cannot execute API calls", 1, violations
                except Exception as e:
                    return str(e), 1, violations

            else:
                return f"Unknown action type: {action_type}", 1, [f"Unsupported action: {action_type}"]
    
    def _validate_path(self, path: str, config: SandboxConfig) -> bool:
        """Validate path is within sandbox."""
        if not config.working_directory:
            return True
        
        abs_path = os.path.abspath(path)
        sandbox_root = os.path.abspath(config.working_directory)
        return abs_path.startswith(sandbox_root)
    
    def _create_error_result(
        self,
        request: ExecutionRequest,
        status: str,
        error: str
    ) -> ExecutionResult:
        """Create an error result."""
        now = TimeAuthority.now()
        return ExecutionResult(
            request_id=request.request_id,
            descriptor_id=request.descriptor_id,
            status=status,
            error=error,
            started_at=now,
            completed_at=now,
            duration_ms=0
        )
    
    async def get_result(self, request_id: str) -> Optional[ExecutionResult]:
        """Get a previous execution result."""
        return self._executions.get(request_id)


# Singleton
_sandbox_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    """Get singleton sandbox service."""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service
