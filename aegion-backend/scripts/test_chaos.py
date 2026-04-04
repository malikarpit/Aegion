#!/usr/bin/env python3
"""
Verification script for Chaos Monkey.
"""

import sys
import os
import asyncio
import time
import importlib.util

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import chaos module dynamically or directly
try:
    from app.services.praxis.chaos import ChaosMonkey, set_chaos_config, chaos_monkey
except ImportError:
    # Fallback to direct file loading if app package not importable
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "app/services/praxis/chaos.py")
    spec = importlib.util.spec_from_file_location("chaos", file_path)
    chaos = importlib.util.module_from_spec(spec)
    sys.modules["chaos"] = chaos
    spec.loader.exec_module(chaos)
    ChaosMonkey = chaos.ChaosMonkey
    set_chaos_config = chaos.set_chaos_config
    chaos_monkey = chaos.chaos_monkey


async def test_chaos_monkey():
    print("🍌 Testing Chaos Monkey...")
    
    # 1. Test Disabled (Default)
    start = time.time()
    await ChaosMonkey.maybe_inject_chaos(probability=1.0, latency_ms=500)
    duration = time.time() - start
    if duration >= 0.5:
        print("❌ Chaos active when disabled!")
        sys.exit(1)
    print("✅ Disabled mode respected.")

    # 2. Test Latency Injection
    set_chaos_config(enabled=True, probability=1.0, latency_ms=200)
    
    start = time.time()
    # Force latency only (hack internals or retry until latency happens? logic randomly chooses latency or exception)
    # The current implementation chooses random.choice(["latency", "failure"])
    # We can't easily force latency unless we mock random. But let's just run it multiple times.
    
    # Actually, let's mock _unleash_chaos to check calls? No, integration test is better.
    # We expect EITHER latency OR exception.
    
    print("   Running 5 trials with p=1.0...")
    latency_count = 0
    failure_count = 0
    
    for i in range(5):
        try:
            t0 = time.time()
            await ChaosMonkey.maybe_inject_chaos()
            dur = time.time() - t0
            if dur >= 0.2:
                print(f"   Trial {i}: Latency injected ({dur:.3f}s)")
                latency_count += 1
            else:
                print(f"   Trial {i}: No effect? (should not happen with p=1.0 unless failure raised)")
        except Exception as e:
            print(f"   Trial {i}: Failure injected ({type(e).__name__})")
            failure_count += 1

    if latency_count + failure_count < 5:
        print("❌ Chaos probability 1.0 failed to trigger consistently.")
        sys.exit(1)
        
    print(f"✅ active mode functional ({latency_count} latency, {failure_count} failures).")
    
    # 3. Test Decorator
    print("   Testing @chaos_monkey decorator...")
    
    @chaos_monkey(probability=1.0, latency_ms=100)
    async def protected_op():
        return "success"
        
    try:
        await protected_op()
        print("   Decorator executed (latency or success)")
    except Exception:
        print("   Decorator executed (failure)")

    print("✅ Chaos Monkey verification complete.")

if __name__ == "__main__":
    asyncio.run(test_chaos_monkey())
