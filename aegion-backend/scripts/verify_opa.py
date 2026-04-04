#!/usr/bin/env python3
"""
Verification script for OPA Policy Engine.
"""

import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle logger fallback/mocking for standalone execution
import logging
logging.basicConfig(level=logging.INFO)

# Mock app.core.logging
import types
core_pkg = types.ModuleType("app.core")
core_logging = types.ModuleType("app.core.logging")
core_logging.logger = logging.getLogger("MockLogger")
sys.modules["app.core"] = core_pkg
sys.modules["app.core.logging"] = core_logging

# Load opa.py directly to avoid app.services init (which needs pydantic)
import importlib.util
file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                         "app/services/archon/opa.py")
spec = importlib.util.spec_from_file_location("opa", file_path)
opa_mod = importlib.util.module_from_spec(spec)
sys.modules["app.services.archon.opa"] = opa_mod
spec.loader.exec_module(opa_mod)
get_opa_service = opa_mod.get_opa_service

def test_opa():
    print("📜 Testing OPA Policy Engine...")
    
    service = get_opa_service()
    print(f"   Loaded policy from: {service.policy_path}")
    
    # Test Cases
    scenarios = [
        {
            "name": "T0 Auto-Approve",
            "input": {"tier": "T0", "impact_score": 5},
            "expect": True
        },
        {
            "name": "T1 Valid",
            "input": {
                "tier": "T1", 
                "approvals": [{"role": "developer"}], 
                "evidence": ["ev-1"]
            },
            "expect": True
        },
        {
            "name": "T1 Missing Evidence",
            "input": {
                "tier": "T1", 
                "approvals": [{"role": "developer"}], 
                "evidence": []
            },
            "expect": False
        },
        {
            "name": "T2 Valid (Architect)",
            "input": {
                "tier": "T2", 
                "approvals": [{"role": "architect"}], # Adjusted to Quorum=1
                "evidence": ["ev-1", "ev-2"]
            },
            "expect": True
        },
        {
            "name": "T2 Invalid Role (Dev)",
            "input": {
                "tier": "T2", 
                "approvals": [{"role": "developer"}], 
                "evidence": ["ev-1", "ev-2"]
            },
            "expect": False
        },
        {
            "name": "T3 Valid (Admin)",
            "input": {
                "tier": "T3", 
                "approvals": [{"role": "admin"}], 
                "evidence": ["ev-1", "ev-2", "ev-3"]
            },
            "expect": True
        }
    ]
    
    passed = 0
    failed = 0
    
    for case in scenarios:
        result = service.evaluate_policy(case["input"])
        is_success = result["allow"] == case["expect"]
        
        status = "✅ PASS" if is_success else "❌ FAIL"
        if not is_success:
            failed += 1
            print(f"   {status} - {case['name']}")
            print(f"      Input: {case['input']}")
            print(f"      Got: {result}, Expected: {case['expect']}")
        else:
            passed += 1
            print(f"   {status} - {case['name']}")
            
    print(f"\nResults: {passed} passed, {failed} failed.")
    
    if failed > 0:
        sys.exit(1)
        
    print("✅ OPA Service verification complete.")

if __name__ == "__main__":
    test_opa()
