#!/usr/bin/env python3
"""
Verification script for Decision Regression Testing.
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

# Mock app.services.archon.opa because regression.py imports it via package
# Wait, regression.py imports: from .opa import get_opa_service
# If we load regression.py via importlib without loading opa first, that import will fail (relative import)
# So we must load opa first or mock it.
# We'll load the REAL opa service so we test the integration with OPA.

# Load opa.py first
import importlib.util
opa_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                         "app/services/archon/opa.py")
spec_opa = importlib.util.spec_from_file_location("opa", opa_path)
opa_mod = importlib.util.module_from_spec(spec_opa)
sys.modules["app.services.archon.opa"] = opa_mod
spec_opa.loader.exec_module(opa_mod)

# Now load regression.py
reg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                         "app/services/archon/regression.py")
spec_reg = importlib.util.spec_from_file_location("regression", reg_path)
reg_mod = importlib.util.module_from_spec(spec_reg)
sys.modules["app.services.archon.regression"] = reg_mod
spec_reg.loader.exec_module(reg_mod)

get_regression_tester = reg_mod.get_regression_tester

async def test_regression():
    print("📉 Testing Decision Regression...")
    
    tester = get_regression_tester()
    
    report = await tester.run_regression_test()
    
    print(f"   Status: {report['status']}")
    print(f"   Total Checked: {report['total_checked']}")
    print(f"   Passed: {report['passed']}")
    print(f"   Regressions: {report['regressions_count']}")
    
    # We expect some regressions because our mock data includes a T1 decision with NO evidence,
    # but our current policy requires 1 evidence item for T1.
    
    expected_regression = [r for r in report["regressions"] if "REGRESSION" in r["issue"]]
    
    if len(expected_regression) > 0:
        print("✅ Correctly detected regression in mock data (T1 missing evidence).")
        for r in expected_regression:
             print(f"      - {r['decision_id']}: {r['reason']}")
    else:
        print("❌ Failed to detect expected regression!")
        sys.exit(1)
        
    print("✅ Regression Tester verification complete.")

if __name__ == "__main__":
    asyncio.run(test_regression())
