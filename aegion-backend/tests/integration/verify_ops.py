import asyncio
import sys
import os

# Setup path
sys.path.append(os.getcwd())

from app.api.v1.health import check_chronos, detailed_health
from app.services.chronos.timeline import get_timeline_service
from app.adapters.persistence.event_store import InMemoryEventStore
from app.api.v1.health import _startup_time # Hack to ensure it initialized

async def test_ops():
    print("🏥 Starting Operational Readiness Verification...")
    
    # 1. Initialize Service
    print("   Initializing backing services...")
    store = InMemoryEventStore()
    svc = get_timeline_service(store)
    
    # Create some state
    await svc.create_adr("Test Ops", "Ctx", "Dec", "Rat", "ops_bot", "ops_ws")
    
    # 2. Test Check Function
    print("   Testing check_chronos()...")
    ok, msg = await check_chronos()
    assert ok is True
    assert "adrs=1" in msg
    assert "backend=InMemoryEventStore" in msg
    print(f"   ✅ check_chronos passed: {msg}")
    
    # 3. Test Full Health Endpoint Logic
    print("   Testing detailed_health()...")
    # Mock other checks to avoid real network calls failing the aggregator
    # We can't easily mock imports inside the function without patching
    # But detailed_health catches exceptions and reports as unhealthy component, 
    # so overall status might be DEGRADED but structure should exist.
    
    res = await detailed_health()
    
    assert "chronos" in res["components"]
    comp = res["components"]["chronos"]
    assert comp["status"] == "healthy"
    assert "adrs=1" in comp["message"]
    
    print("   ✅ detailed_health output verified.")
    print("🎉 Operational Readiness Confirmed.")

if __name__ == "__main__":
    asyncio.run(test_ops())
