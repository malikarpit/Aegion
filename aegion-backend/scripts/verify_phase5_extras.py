#!/usr/bin/env python3
"""
Verification script for Phase 5 Extras: Compliance, Predictive, Knowledge.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock imports for standalone execution
logging.basicConfig(level=logging.INFO)

# Mock app.core.logging
import types
core_pkg = types.ModuleType("app.core")
core_logging = types.ModuleType("app.core.logging")
core_logging.logger = logging.getLogger("MockLogger")
sys.modules["app.core"] = core_pkg
sys.modules["app.core.logging"] = core_logging

# Helper to load module directly
import importlib.util
def load_module(name, rel_path):
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel_path)
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"app.services.archon.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod

# Load services
compliance_mod = load_module("compliance", "app/services/archon/compliance.py")
predictive_mod = load_module("predictive", "app/services/archon/predictive.py")
knowledge_mod = load_module("knowledge", "app/services/archon/knowledge.py")

async def verify_compliance():
    print("\n📄 Testing Compliance Exporter (15b)...")
    exporter = compliance_mod.get_compliance_exporter()
    report = await exporter.generate_report(datetime.now() - timedelta(days=7), datetime.now())
    if "# Aegion Governance Audit Report" in report and "Executive Summary" in report:
        print("✅ Report generated successfully.")
    else:
        print("❌ Report generation failed or malformed.")
        sys.exit(1)

async def verify_predictive():
    print("\n🔮 Testing Predictive Monitoring (16b)...")
    monitor = predictive_mod.get_dependency_monitor()
    
    # Test 1: Conflict
    result1 = monitor.predict_conflicts(["app/core/security.py"])
    if result1["conflict_detected"] and result1["risk_score"] >= 30:
        print("✅ Correctly detected high-risk conflict in security.py.")
    else:
        print(f"❌ Failed to detect conflict: {result1}")
        sys.exit(1)
        
    # Test 2: Safe
    result2 = monitor.predict_conflicts(["app/utils/helper.py"])
    if not result2["conflict_detected"]:
        print("✅ Correctly identified safe change.")
    else:
         print(f"❌ False positive on safe file: {result2}")
         sys.exit(1)

async def verify_knowledge():
    print("\n🧠 Testing Knowledge Transfer (13b)...")
    service = knowledge_mod.get_knowledge_service()
    
    template = service.export_template("prop-success")
    if template.get("template_id") == "tmpl-prop-success":
        print("✅ Template exported successfully.")
    else:
        print(f"❌ Template export failed: {template}")
        sys.exit(1)

async def main():
    await verify_compliance()
    await verify_predictive()
    await verify_knowledge()
    print("\n🎉 Phase 5 Extras Verification Complete!")

if __name__ == "__main__":
    asyncio.run(main())
