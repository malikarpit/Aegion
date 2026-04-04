#!/usr/bin/env python3
"""
Verification script for Retention Service.
"""

import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle logger fallback for standalone execution
try:
    from app.services.archon.retention import get_retention_service, RetentionService
except ImportError:
    # Set up basic config for imports that need it
    logging.basicConfig(level=logging.INFO)
    
    # Mock fallback import
    import importlib.util
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "app/services/archon/retention.py")
    
    # We need to mock ...core.logging first
    core_pkg = type(sys)("app.core")
    core_logging = type(sys)("app.core.logging")
    core_logging.logger = logging.getLogger("MockLogger")
    sys.modules["app.core"] = core_pkg
    sys.modules["app.core.logging"] = core_logging
    
    spec = importlib.util.spec_from_file_location("retention", file_path)
    retention_mod = importlib.util.module_from_spec(spec)
    sys.modules["app.services.archon.retention"] = retention_mod
    spec.loader.exec_module(retention_mod)
    get_retention_service = retention_mod.get_retention_service
    RetentionService = retention_mod.RetentionService


async def test_retention():
    print("🗑️ Testing Retention Service...")
    
    service = get_retention_service()
    
    # 1. Test Archival
    print("   Running archival policy (older than 365 days)...")
    archived = await service.run_archive_policy(retention_days=365)
    
    if archived > 0:
        print(f"✅ Archived {archived} simulated events successfully.")
    else:
        print("❌ Archival failed to simulate count.")
        sys.exit(1)
        
    # 2. Test GDPR Purge
    print("   Running GDPR user data purge for 'user-123'...")
    purged = await service.purge_user_data(user_id="user-123", reason="Test Purge")
    
    if purged:
        print("✅ Data purge executed successfully.")
    else:
        print("❌ Purge operation failed.")
        sys.exit(1)

    print("✅ Retention Service verification complete.")

if __name__ == "__main__":
    asyncio.run(test_retention())
