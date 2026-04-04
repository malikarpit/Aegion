#!/usr/bin/env python3
"""
Verification script for Metrics Service.
"""

import sys
import os
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services.archon.metrics import get_metrics_service, PROMETHEUS_AVAILABLE
except ImportError:
    # Use dynamic import fallback if path issues
    import importlib.util
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "app/services/archon/metrics.py")
    spec = importlib.util.spec_from_file_location("metrics", file_path)
    metrics_mod = importlib.util.module_from_spec(spec)
    sys.modules["app.services.archon.metrics"] = metrics_mod
    sys.modules["app.services.archon"] = type(sys)("app.services.archon") # mock parent
    spec.loader.exec_module(metrics_mod)
    get_metrics_service = metrics_mod.get_metrics_service
    PROMETHEUS_AVAILABLE = metrics_mod.PROMETHEUS_AVAILABLE

def test_metrics():
    print("📊 Testing Metrics Service...")
    
    service = get_metrics_service()
    
    print(f"   Prometheus Client Available: {PROMETHEUS_AVAILABLE}")
    
    # 1. Increment Counters
    print("   Incrementing counters...")
    service.proposals_created.labels(type="standard", workspace="ws-1").inc()
    service.decisions_approved.labels(tier="critical", workspace="ws-1").inc()
    service.invariant_violations.labels(severity="blocking", invariant_id="INV-001").inc()
    service.council_sessions.labels(result="consensus").inc()
    
    # 2. observe Histogram
    print("   Observing histogram...")
    service.council_duration.observe(1.5)
    
    # 3. Get Data
    data = service.get_metrics_data()
    
    if PROMETHEUS_AVAILABLE:
        output = data.decode('utf-8')
        if "aegion_decisions_approved_total" in output:
            print("✅ Metric 'decisions_approved_total' found in output.")
        else:
            print("❌ Metric missing from output!")
            print(output)
            sys.exit(1)
            
        if 'tier="critical"' in output:
             print("✅ Labels correctly applied.")
        else:
             print("❌ Labels missing.")
             sys.exit(1)
    else:
        print("⚠️  Prometheus client not installed, verify dummy mode checks out.")
        if b"# Prometheus client not installed" in data:
             print("✅ Fallback message confirmed.")
        else:
             print("❌ Unexpected fallback output.")
             sys.exit(1)

    print("✅ Metrics Service verification complete.")

if __name__ == "__main__":
    test_metrics()
