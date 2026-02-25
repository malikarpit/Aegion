"""
Aegion Collaboration Services.

Provides session ownership, attribution, and conflict resolution.
"""

from .session_ownership import SessionOwnership, Participant
from .attribution import EditAttribution, AttributedEdit

__all__ = [
    "SessionOwnership",
    "Participant",
    "EditAttribution", 
    "AttributedEdit",
]
