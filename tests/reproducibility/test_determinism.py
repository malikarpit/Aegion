import asyncio
import unittest
import os
import sys
import json
from unittest.mock import patch, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "aegion-backend")))

from app.services.praxis.execution_sandbox import ExecutionSandbox, ExecutionResult
from app.services.praxis.execution_profile import ExecutionProfile, ExecutionType

class TestDeterminism(unittest.IsolatedAsyncioTestCase):
    
    async def test_provenance_stability(self):
        """
        Verify that executing the same command/inputs twice produces:
        1. Identical stdout/stderr
        2. Identical provenance_hash
        3. Different timestamps
        """
        sandbox = ExecutionSandbox()
        profile = ExecutionProfile(
            profile_id="repro-test",
            name="Repro Test",
            execution_type=ExecutionType.LOCAL # Use local for speed/simplicity in this test suite
        )
        
        cmd = "echo 'determinism check'; env | grep TEST_VAR"
        env = {"TEST_VAR": "constant_value"}
        ws_id = "ws-repro"
        
        # Mock execution to return deterministic output
        # In a real integration test, we would actually run the command
        with patch("app.services.praxis.execution_sandbox.ExecutionSandbox._execute_local", new_callable=AsyncMock) as mock_local:
            def side_effect(*args, **kwargs):
                from app.services.praxis.execution_sandbox import ExecutionResult, ExecutionStatus
                from datetime import datetime
                return ExecutionResult(
                    execution_id=kwargs["execution_id"],
                    status=ExecutionStatus.COMPLETED,
                    stdout="determinism check\nTEST_VAR=constant_value",
                    stderr="",
                    started_at=datetime.utcnow(),
                    duration_seconds=0.1
                )
            mock_local.side_effect = side_effect
            
            # Run 1
            result1 = await sandbox.execute(
                command=cmd,
                workspace_id=ws_id,
                profile=profile,
                env=env
            )
            
            # Run 2
            result2 = await sandbox.execute(
                command=cmd,
                workspace_id=ws_id,
                profile=profile,
                env=env
            )
            
            # Assertions
            self.assertEqual(result1.stdout, result2.stdout)
            self.assertEqual(result1.provenance["provenance_hash"], result2.provenance["provenance_hash"])
            self.assertEqual(result1.provenance["command_hash"], result2.provenance["command_hash"])
            self.assertEqual(result1.provenance["environment_hash"], result2.provenance["environment_hash"])
            
            # Timestamps should differ
            self.assertNotEqual(result1.provenance["timestamp"], result2.provenance["timestamp"])

if __name__ == "__main__":
    unittest.main()
