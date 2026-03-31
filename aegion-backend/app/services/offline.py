"""
Aegion Offline/Degradation Service.

Feature: Offline mode degrades safely.
Monitors connectivity and provides context for degradation.
"""

import httpx
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from ..core.logging import logger

class OfflineMonitor:
    """
    Monitors external connectivity and determines system degradation state.
    """
    
    def __init__(self):
        self._is_online = True
        self._last_check = datetime.min.replace(tzinfo=timezone.utc)
        self._check_interval = 60 # seconds
        self._force_offline = False

    async def check_connectivity(self) -> bool:
        """Check if system can reach external world."""
        if self._force_offline:
            return False
            
        now = datetime.now(timezone.utc)
        if (now - self._last_check).total_seconds() < self._check_interval:
            return self._is_online
            
        try:
            # Ping a reliable uptime check (or just Google/Cloudflare)
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.get("https://1.1.1.1")
            self._is_online = True
        except Exception:
            self._is_online = False
            logger.warning("Connectivity lost: System entering offline degradation mode")
            
        self._last_check = now
        return self._is_online

    def force_offline(self, state: bool):
        """Manually toggle offline mode for testing."""
        self._force_offline = state
        self._is_online = not state
        logger.info(f"Offline mode manually set to: {state}")

    def get_degradation_policy(self) -> Dict[str, Any]:
        """Get current feature capabilities based on connectivity."""
        online = self._is_online
        
        return {
            "is_online": online,
            "can_access_llm": online, # Assuming LLM is external
            "can_access_tools": online, # External tools
            "can_deploy": online,
            "features": {
                "ghost_text": "local_only" if not online else "full",
                "council": "mock" if not online else "full",
                "marketplace": "cached" if not online else "full",
            }
        }

# Singleton
_monitor: Optional[OfflineMonitor] = None

def get_offline_monitor() -> OfflineMonitor:
    global _monitor
    if _monitor is None:
        _monitor = OfflineMonitor()
    return _monitor
