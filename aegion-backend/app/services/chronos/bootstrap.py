"""
Aegion Chronos Bootstrap (Cold-Start Phase).

Doctrine: "Day Zero is not Day One."
This module handles the initialization of Chronos when:
1. No prior decisions exist
2. No prior sessions exist
3. The system is starting "fresh"

This is critical for:
- New project onboarding
- Recovery from catastrophic data loss
- Testing environments
"""

from typing import Optional
from datetime import datetime, timezone
from ...core.time import TimeAuthority
from ...core.logging import logger

class ChronosBootstrap:
    """
    Handles the Cold-Start scenario for Chronos memory system.
    """
    
    @staticmethod
    def is_cold_start(session_count: int, decision_count: int) -> bool:
        """Determine if this is a cold start scenario."""
        return session_count == 0 and decision_count == 0
    
    @staticmethod
    def initialize_genesis(workspace_id: str, owner_id: str) -> dict:
        """
        Create the Genesis state for a new workspace.
        Returns the initial architecture document that becomes Decision #0.
        """
        genesis_time = TimeAuthority.now()
        
        genesis_decision = {
            "decision_id": f"{workspace_id}-genesis",
            "tier": "T3",  # Architecture-level
            "title": "Genesis: Workspace Initialization",
            "rationale": "This is the founding decision that establishes the workspace.",
            "status": "APPROVED",  # Auto-approved (Day Zero)
            "created_at": genesis_time,
            "approvals": [
                {
                    "user_id": owner_id,
                    "timestamp": genesis_time,
                    "tier": "T3",
                    "type": "GENESIS_AUTO_APPROVAL"
                }
            ],
            "evidence_links": [],
            "risk_score": 0,  # Genesis has no risk
            "metadata": {
                "is_genesis": True,
                "workspace_id": workspace_id
            }
        }
        
        logger.audit(
            action="GENESIS_CREATED",
            actor=owner_id,
            target=workspace_id,
            justification="Cold-start initialization of Chronos memory"
        )
        
        return genesis_decision
    
    @staticmethod
    def validate_genesis(decision: dict) -> bool:
        """Validate that a genesis decision is well-formed."""
        required_fields = ["decision_id", "tier", "title", "status", "created_at"]
        return all(field in decision for field in required_fields)
