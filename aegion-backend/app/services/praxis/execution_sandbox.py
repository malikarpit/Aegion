"""
Aegion Execution Sandbox Service.

Provides sandboxed execution of tests and builds with resource limits.

Doctrine: "Evidence must be reproducible."
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import subprocess
import os
import tempfile
import hashlib
import json
import asyncio
from enum import Enum

from .execution_profile import ExecutionProfile, ExecutionType, get_default_profile
from .snapshot_manager import SnapshotManager
from .sandbox_hardening import (
    compute_provenance, 
    ExecutionProvenance, 
    SandboxHardeningConfig,
    get_quota_manager,
    WorkspaceQuotaManager
)
from ...core.logging import logger


class ExecutionStatus(str, Enum):
    """Status of sandbox execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ExecutionResult(BaseModel):
    """Result of sandbox execution."""
    execution_id: str
    status: ExecutionStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Snapshot information
    input_snapshot_hash: Optional[str] = None
    output_snapshot_hash: Optional[str] = None
    environment_hash: Optional[str] = None
    
    # Resources used
    peak_memory_mb: Optional[float] = None
    
    # Evidence classification (set later)
    evidence_id: Optional[str] = None
    evidence_classification: Optional[str] = None

    # Provenance
    provenance: Optional[Dict[str, Any]] = None  # Serialized ExecutionProvenance


class ExecutionSandbox:
    """
    Executes commands in a sandbox with resource limits and capture.
    
    Phase 3: Local execution with subprocess
    Phase 4+: Docker container execution
    """
    
    def __init__(self, snapshot_manager: SnapshotManager = None):
        self._snapshot_manager = snapshot_manager
        self._active_executions: Dict[str, subprocess.Popen] = {}
    
    async def execute(
        self,
        command: str,
        workspace_id: str,
        profile: ExecutionProfile = None,
        env: Dict[str, str] = None,
        working_dir: str = None,
        capture_files: List[str] = None
    ) -> ExecutionResult:
        """
        Execute command in sandbox.
        
        Args:
            command: Command to execute
            workspace_id: Workspace context
            profile: Execution profile (default: standard)
            env: Environment variables
            working_dir: Working directory
            capture_files: Files to capture as inputs
            
        Returns:
            ExecutionResult with outputs and snapshots
        """
        import uuid
        execution_id = str(uuid.uuid4())
        profile = profile or get_default_profile()
        
        logger.info(
            f"Starting sandbox execution",
            execution_id=execution_id,
            command=command[:100],
            profile=profile.name
        )
        
        started_at = datetime.now(timezone.utc)
        
        # Enforce quotas
        quota_manager = get_quota_manager()
        allowed, reason = quota_manager.check_quota(workspace_id)
        if not allowed:
            logger.warning(f"Execution quota exceeded for {workspace_id}: {reason}")
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                stderr=f"Quota exceeded: {reason}",
                started_at=started_at,
                completed_at=started_at
            )
            
        quota_manager.record_start(workspace_id, execution_id)
        
        try:
            # Capture input snapshot if configured
            input_snapshot_hash = None
            if profile.capture_inputs and capture_files and self._snapshot_manager:
                try:
                    input_snapshot_hash = await self._capture_inputs(
                        capture_files, workspace_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to capture inputs: {e}")
            
            # Capture environment if configured
            environment_hash = None
            if profile.capture_environment:
                environment_hash = self._hash_environment(env)
            
            # Execute based on profile type
            if profile.execution_type == ExecutionType.LOCAL:
                result = await self._execute_local(
                    command=command,
                    execution_id=execution_id,
                    timeout=profile.timeout_seconds,
                    env=env,
                    working_dir=working_dir or profile.working_directory,
                    started_at=started_at
                )
            elif profile.execution_type == ExecutionType.CONTAINER:
                result = await self._execute_container(
                    command=command,
                    execution_id=execution_id,
                    profile=profile,
                    env=env,
                    started_at=started_at
                )
            else:
                result = ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionStatus.FAILED,
                    stderr=f"Unsupported execution type: {profile.execution_type}",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc)
                )
            
            # Add snapshot hashes
            result.input_snapshot_hash = input_snapshot_hash
            result.environment_hash = environment_hash
            
            # Capture output snapshot
            if profile.capture_outputs and result.status == ExecutionStatus.COMPLETED:
                result.output_snapshot_hash = self._hash_output(
                    result.stdout, result.stderr, result.exit_code
                )
            
            # Compute provenance
            input_hashes = self._hash_input_files(capture_files or [])
            
            provenance = compute_provenance(
                command=command,
                workspace_id=workspace_id,
                environment=env,
                input_files=input_hashes,
                metadata={"profile": profile.name, "execution_id": execution_id}
            )
            result.provenance = provenance.to_dict()

            logger.info(
                f"Sandbox execution completed",
                execution_id=execution_id,
                status=result.status,
                duration=result.duration_seconds,
                provenance_hash=provenance.provenance_hash
            )
            
            return result
        
        finally:
             if 'quota_manager' in locals():
                 # Record end (approximate cpu time for now, can be refined later)
                 # If result exists use its duration, else 0
                 cpu_time = 0.0
                 if 'result' in locals() and result.status == ExecutionStatus.COMPLETED:
                     # For container, we might get actual cpu usage later, for now use wall time as upper bound
                     cpu_time = result.duration_seconds 
                 
                 quota_manager.record_end(workspace_id, execution_id, cpu_seconds=cpu_time)
    
    async def _execute_local(
        self,
        command: str,
        execution_id: str,
        timeout: int,
        env: Dict[str, str] = None,
        working_dir: str = None,
        started_at: datetime = None
    ) -> ExecutionResult:
        """Execute command locally with subprocess."""
        
        # Prepare environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        try:
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
                cwd=working_dir
            )
            
            self._active_executions[execution_id] = process
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                completed_at = datetime.now(timezone.utc)
                duration = (completed_at - started_at).total_seconds()
                
                return ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionStatus.COMPLETED if process.returncode == 0 else ExecutionStatus.FAILED,
                    exit_code=process.returncode,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration
                )
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                
                return ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionStatus.TIMEOUT,
                    stderr=f"Execution timed out after {timeout}s",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc)
                )
            finally:
                self._active_executions.pop(execution_id, None)
                
        except Exception as e:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                stderr=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
    
    async def _execute_container(
        self,
        command: str,
        execution_id: str,
        profile: ExecutionProfile,
        env: Dict[str, str] = None,
        started_at: datetime = None
    ) -> ExecutionResult:
        """Execute command in Docker container."""
        
        # Resolve path to custom seccomp profile
        seccomp_path = os.path.join(os.path.dirname(__file__), "seccomp_profile.json")
        
        # Create hardening config from profile
        hardening = SandboxHardeningConfig(
            disable_network=not profile.allow_network_egress,
            # Enforce defaults for isolation
            drop_all_capabilities=True,
            read_only_rootfs=True,
            no_new_privileges=True,
            use_seccomp=True,
            seccomp_profile=seccomp_path
        )
        
        # Base command
        docker_cmd = ["docker", "run", "--rm"]
        
        # Apply hardening args
        hardening_args = hardening.to_docker_args()
        
        if hardening_args.get("network_mode"):
            docker_cmd.extend(["--network", hardening_args["network_mode"]])
            
        if hardening_args.get("read_only"):
            docker_cmd.append("--read-only")
            
        if hardening_args.get("cap_drop"):
            for cap in hardening_args["cap_drop"]:
                docker_cmd.extend(["--cap-drop", cap])
                
        if hardening_args.get("cap_add"):
            for cap in hardening_args["cap_add"]:
                docker_cmd.extend(["--cap-add", cap])
                
        if hardening_args.get("security_opt"):
            for opt in hardening_args["security_opt"]:
                docker_cmd.extend(["--security-opt", opt])
        
        # Explicitly handle non-default seccomp if not already added by to_docker_args logic
        # Now handled by SandboxHardeningConfig.to_docker_args
        
        if hardening_args.get("tmpfs"):
            for mount, opts in hardening_args["tmpfs"].items():
                docker_cmd.extend(["--tmpfs", f"{mount}:{opts}"])

        # Resource limits from profile
        if profile.memory_limit_mb:
            docker_cmd.extend(["--memory", f"{profile.memory_limit_mb}m"])
        if profile.cpu_limit:
            docker_cmd.extend(["--cpus", str(profile.cpu_limit)])
            
        # Hardening process limits
        if "pids_limit" in hardening_args:
             docker_cmd.extend(["--pids-limit", str(hardening_args["pids_limit"])])
             
        if "ulimits" in hardening_args:
            for ulimit in hardening_args["ulimits"]:
                docker_cmd.extend(["--ulimit", f"{ulimit['Name']}={ulimit['Soft']}:{ulimit['Hard']}"])
        
        # Environment
        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])
        
        # Image and command
        docker_cmd.extend([
            "aegion/sandbox:latest",
            "sh", "-c", command
        ])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=profile.timeout_seconds
            )
            
            completed_at = datetime.now(timezone.utc)
            
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED if process.returncode == 0 else ExecutionStatus.FAILED,
                exit_code=process.returncode,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds()
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.TIMEOUT,
                stderr=f"Container timed out after {profile.timeout_seconds}s",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
        except Exception as e:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                stderr=f"Container execution failed: {e}",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
    
    async def cancel(self, execution_id: str) -> bool:
        """Cancel an active execution."""
        if execution_id in self._active_executions:
            process = self._active_executions[execution_id]
            process.kill()
            return True
        return False
    
    async def _capture_inputs(
        self, 
        files: List[str], 
        workspace_id: str
    ) -> Optional[str]:
        """Capture input files as snapshot."""
        if not self._snapshot_manager:
            return None
        
        # Simple hash of file contents
        hasher = hashlib.sha256()
        for file_path in sorted(files):
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
        
        return hasher.hexdigest()

    def _hash_input_files(self, files: List[str]) -> Dict[str, str]:
        """Compute SHA256 hash for each input file."""
        hashes = {}
        import hashlib
        import os
        
        for file_path in files:
            # Resolving path relative to CWD if strictly needed, but assuming absolute or CWD-relative for now
            if os.path.exists(file_path):
                sha256 = hashlib.sha256()
                try:
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            sha256.update(chunk)
                    hashes[file_path] = sha256.hexdigest()
                except Exception as e:
                    logger.warning(f"Failed to hash input file {file_path}: {e}")
        return hashes
    
    def _hash_environment(self, env: Dict[str, str] = None) -> str:
        """Hash environment for reproducibility check."""
        import sys
        
        env_data = {
            "python_version": sys.version,
            "platform": sys.platform,
            "custom_env": env or {}
        }
        
        return hashlib.sha256(
            json.dumps(env_data, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def _hash_output(
        self, 
        stdout: str, 
        stderr: str, 
        exit_code: int
    ) -> str:
        """Hash execution output."""
        output_data = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code
        }
        return hashlib.sha256(
            json.dumps(output_data, sort_keys=True).encode()
        ).hexdigest()


# Singleton instance
_sandbox: Optional[ExecutionSandbox] = None


def get_execution_sandbox() -> ExecutionSandbox:
    """Get execution sandbox singleton."""
    global _sandbox
    if _sandbox is None:
        _sandbox = ExecutionSandbox()
    return _sandbox
