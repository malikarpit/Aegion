#!/usr/bin/env python3
"""
Verification script for Notification Service.
"""

import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle logger fallback for standalone execution
try:
    from app.services.archon.notifications import get_notification_service
except ImportError:
    # Set up basic config for imports that need it
    logging.basicConfig(level=logging.INFO)
    
    # Mock fallback import
    import importlib.util
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "app/services/archon/notifications.py")
    
    # We need to mock ...core.logging first
    core_pkg = type(sys)("app.core")
    core_logging = type(sys)("app.core.logging")
    core_logging.logger = logging.getLogger("MockLogger")
    sys.modules["app.core"] = core_pkg
    sys.modules["app.core.logging"] = core_logging
    
    spec = importlib.util.spec_from_file_location("notifications", file_path)
    notifications_mod = importlib.util.module_from_spec(spec)
    sys.modules["app.services.archon.notifications"] = notifications_mod
    spec.loader.exec_module(notifications_mod)
    get_notification_service = notifications_mod.get_notification_service


async def test_notifications():
    print("📢 Testing Notification Service...")
    
    service = get_notification_service()
    
    print(f"   Service Enabled: {service.enabled}")
    if not service.enabled:
        print("   (Running in simulation mode)")

    # Test Decision Approved
    print("   Sending decision approval alert...")
    await service.notify_decision_approved(
        proposal_id="PROP-123",
        title="Upgrade Core Engine",
        approver="admin-user",
        tier="T2"
    )
    
    # Test Freeze Activated
    print("   Sending freeze alert...")
    await service.notify_freeze_activated(
        reason="Detected anomalous invariant storm",
        actor="StormWatcher"
    )

    # Test Freeze Deactivated
    print("   Sending thaw alert...")
    await service.notify_freeze_deactivated(
        reason="Resolved via hotfix",
        actor="admin-user"
    )
    
    print("✅ Notification Service verification complete (check logs for output).")

if __name__ == "__main__":
    asyncio.run(test_notifications())
