"""
Aegion Monotonic Time Authority.

Doctrine: "Time does not come from agents, UI, or execution."
Reliable ordering of events in a distributed system (or async local system) 
must rely on a monotonic clock for duration and sequencing, 
and a strictly controlled UTC source for timestamps.

This module provides the single source of truth for:
1. Event sequencing (monotonic)
2. Audit timestamps (UTC)
"""

import time
import datetime
from typing import NewType

# Type definitions to prevent raw float usage
MonotonicTime = NewType("MonotonicTime", float)
AuditTime = NewType("AuditTime", str)

class TimeAuthority:
    """
    The only authorized source of time for Aegion.
    Prevents usage of `datetime.now()` scattered across the codebase.
    """

    @staticmethod
    def now() -> AuditTime:
        """
        Returns strict UTC timestamp for audit logs.
        Format: ISO 8601 with timezone (Z).
        """
        return AuditTime(datetime.datetime.now(datetime.timezone.utc).isoformat())

    @staticmethod
    def now_dt() -> datetime.datetime:
        """Returns datetime object in UTC for calculations."""
        return datetime.datetime.now(datetime.timezone.utc)

    @staticmethod
    def monotonic() -> MonotonicTime:
        """
        Returns monotonic clock time for measuring durations and strict ordering.
        Not affected by system clock updates.
        """
        return MonotonicTime(time.monotonic())

    @staticmethod
    def duration(start: MonotonicTime) -> float:
        """Calculates duration in seconds from a monotonic start time."""
        return time.monotonic() - start

# Global instance (if needed, though static methods are fine here)
clock = TimeAuthority()
