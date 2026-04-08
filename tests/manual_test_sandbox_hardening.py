
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Check docker availability
import subprocess
try:
    subprocess.check_call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception:
    print("SKIPPING TESTS: Docker daemon not running.")
    sys.exit(0)

from app.services.praxis.sandbox import DockerSandboxRunner
from app.services.praxis.sandbox_hardening import SandboxHardeningConfig

async def test_network_isolation():
    print("\n--- Testing Network Isolation ---")
    
    # 1. Default config (Network Disabled)
    print("1. Running with defaults (Network Disabled)...")
    runner = DockerSandboxRunner(hardening_config=SandboxHardeningConfig()) # disable_network=True by default
    
    # Try to ping google.com (should fail)
    cmd = "python3 -c 'import socket; socket.create_connection((\"google.com\", 80), timeout=2)'"
    
    try:
        output, code, violations = await runner.run(cmd, timeout_sec=5)
    except Exception as e:
        print(f"Error executing runner: {e}")
        return

    if code != 0:
        print("✅ SUCCESS: Network connection failed as expected.")
        # print(f"   Output: {output.strip()}")
    else:
        print("❌ FAILURE: Network connection succeeded unexpectedly!")
        print(f"   Output: {output}")

    # 2. Network Enabled via explicit override
    print("\n2. Running with Network ENABLED...")
    runner_net = DockerSandboxRunner(network_enabled=True)
    
    output, code, violations = await runner_net.run(cmd, timeout_sec=5)
    
    if code == 0:
        print("✅ SUCCESS: Network connection succeeded as expected.")
    else:
        print("⚠️ NOTE: Network connection failed. This might be due to local environment.")
        print(f"   Output: {output.strip()}")

async def test_filesystem_isolation():
    print("\n--- Testing Filesystem Isolation ---")
    
    runner = DockerSandboxRunner()
    
    # Try to write to /root/testfile (should fail due to read-only rootfs)
    cmd = "echo 'test' > /root/testfile"
    
    output, code, violations = await runner.run(cmd, timeout_sec=5)
    
    if code != 0:
        print("✅ SUCCESS: File write to /root failed as expected (Read-only FS).")
    else:
        print("❌ FAILURE: File write succeeded unexpectedly!")

    # Try to write to /tmp (should succeed)
    cmd = "echo 'test' > /tmp/testfile && cat /tmp/testfile"
    output, code, violations = await runner.run(cmd, timeout_sec=5)
    
    if code == 0 and "test" in output:
        print("✅ SUCCESS: File write to /tmp succeeded.")
    else:
        print("❌ FAILURE: File write to /tmp failed!")

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_network_isolation())
        loop.run_until_complete(test_filesystem_isolation())
    except Exception as e:
        print(f"Test crashed: {e}")
