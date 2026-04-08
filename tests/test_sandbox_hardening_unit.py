import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add project root to path
# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aegion-backend")))

from app.services.praxis.sandbox_hardening import SandboxHardeningConfig
from app.services.praxis.execution_profile import ExecutionProfile, ExecutionType
from app.services.praxis.execution_sandbox import ExecutionSandbox, ExecutionStatus

class TestSandboxHardening(unittest.TestCase):
    
    def test_hardening_config_to_args(self):
        """Test conversion of config to docker args."""
        config = SandboxHardeningConfig(
            disable_network=True,
            read_only_rootfs=True,
            drop_all_capabilities=True,
            allowed_capabilities=frozenset(["CAP_SETUID"]),
            tmpfs_size_mb=128
        )
        args = config.to_docker_args()
        
        self.assertEqual(args["network_mode"], "none")
        self.assertTrue(args["read_only"])
        self.assertEqual(args["cap_drop"], ["ALL"])
        self.assertEqual(args["cap_add"], ["CAP_SETUID"])
        self.assertIn("no-new-privileges:true", args["security_opt"])
        self.assertEqual(args["tmpfs"]["/tmp"], "size=128m,noexec,nosuid,nodev")

class TestExecutionSandboxHardening(unittest.IsolatedAsyncioTestCase):
    
    async def test_execute_container_hardening(self):
        """Verify ExecutionSandbox applies hardening args to docker command."""
        
        sandbox = ExecutionSandbox()
        profile = ExecutionProfile(
            profile_id="test-secure",
            name="Secure Test",
            execution_type=ExecutionType.CONTAINER,
            allow_network_egress=False,
            memory_limit_mb=128,
            cpu_limit=0.5
        )
        
        # Mock create_subprocess_exec
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            # Mock process return value
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"ok", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process
            
            await sandbox.execute(
                command="echo hello",
                workspace_id="ws-123",
                profile=profile
            )
            
            # Verify arguments passed to docker
            call_args = mock_exec.call_args[0]
            docker_cmd = list(call_args)
            
            # Check for hardening flags
            self.assertIn("--network", docker_cmd)
            self.assertIn("none", docker_cmd)
            self.assertIn("--read-only", docker_cmd)
            self.assertIn("--cap-drop", docker_cmd)
            self.assertIn("ALL", docker_cmd)
            self.assertIn("--security-opt", docker_cmd)
            self.assertTrue(any("seccomp" in custom_arg for custom_arg in docker_cmd))
            
            # Check resource limits
            self.assertIn("--memory", docker_cmd)
            self.assertIn("128m", docker_cmd)

    async def test_provenance_calculation(self):
        """Verify provenance is calculated and returned."""
        sandbox = ExecutionSandbox()
        profile = ExecutionProfile(
            profile_id="test-prov",
            name="Test Prov",
            execution_type=ExecutionType.LOCAL
        )
        
        with patch("app.services.praxis.execution_sandbox.ExecutionSandbox._execute_local", new_callable=AsyncMock) as mock_local:
             # Mock result
             from app.services.praxis.execution_sandbox import ExecutionResult
             from datetime import datetime
             mock_local.return_value = ExecutionResult(
                 execution_id="exec-1",
                 status=ExecutionStatus.COMPLETED,
                 started_at=datetime.utcnow()
             )
             
             
             # Mock _hash_input_files to avoid file system access
             with patch.object(sandbox, '_hash_input_files', return_value={"test.py": "hash123"}):
                 result = await sandbox.execute(
                     command="echo hello",
                     workspace_id="ws-1",
                     profile=profile,
                     env={"TEST": "1"},
                     capture_files=["test.py"]
                 )
             
             # Check provenance
             self.assertIsNotNone(result.provenance)
             self.assertIn("provenance_hash", result.provenance)
             self.assertIn("command_hash", result.provenance)
             self.assertEqual(result.provenance["workspace_id"], "ws-1")
             # Verify input hash made it in
             input_hash_in_prov = result.provenance.get("input_hash")
             self.assertIsNotNone(input_hash_in_prov)

if __name__ == "__main__":
    unittest.main()
