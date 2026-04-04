#!/usr/bin/env python3
"""
Verification script for Neuro-Symbolic Governance.
"""

import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock imports for standalone execution
import logging
logging.basicConfig(level=logging.INFO)

# Mock app.core.logging
import types
core_pkg = types.ModuleType("app.core")
core_logging = types.ModuleType("app.core.logging")
core_logging.logger = logging.getLogger("MockLogger")
sys.modules["app.core"] = core_pkg
sys.modules["app.core.logging"] = core_logging

# Load semantic.py directly
import importlib.util
file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                         "app/services/archon/semantic.py")
spec = importlib.util.spec_from_file_location("semantic", file_path)
semantic_mod = importlib.util.module_from_spec(spec)
sys.modules["app.services.archon.semantic"] = semantic_mod
spec.loader.exec_module(semantic_mod)
get_semantic_auditor = semantic_mod.get_semantic_auditor

async def test_semantic_audit():
    print("🧠 Testing Neuro-Symbolic Governance...")
    
    auditor = get_semantic_auditor()
    
    # Test Case 1: Safe Justification
    print("   Testing SAFE justification...")
    safe_result = await auditor.audit_proposal(
        "prop-safe", 
        "Standard refactor of user service to improve performance."
    )
    if not safe_result["flagged"]:
        print(f"✅ Correctly allowed safe proposal (Score: {safe_result['score']})")
    else:
        print(f"❌ False Positive! Flagged safe proposal: {safe_result}")
        sys.exit(1)
        
    # Test Case 2: Risky Justification
    print("   Testing RISKY justification...")
    risky_text = "Urgent fix to bypass validation logic for VIP users. Must merge now."
    risky_result = await auditor.audit_proposal("prop-risky", risky_text)
    
    if risky_result["flagged"]:
        print(f"✅ Correctly flagged risky proposal (Score: {risky_result['score']})")
        print(f"      Reason: {risky_result['reason']}")
    else:
        print(f"❌ False Negative! Allowed risky proposal: {risky_result}")
        sys.exit(1)

    print("✅ Semantic Auditor verification complete.")

if __name__ == "__main__":
    asyncio.run(test_semantic_audit())
