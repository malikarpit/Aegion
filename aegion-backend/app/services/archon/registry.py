"""
Aegion Policy Registry.

Manages governance policies and invariant packs (YAML).
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

# Constants
PACKS_DIR = os.path.join(os.path.dirname(__file__), "packs")

class InvariantRule(BaseModel):
    name: str
    severity: str  # critical, high, medium, low
    pattern: str  # Regex pattern to match
    negative_constraint: Optional[str] = None  # If pattern matches, this MUST be present
    paths: List[str] = Field(default_factory=list)  # Glob patterns to apply to
    message: str

class GovernancePolicy(BaseModel):
    """
    Defines a snapshot of governance rules at a specific version.
    """
    id: str  # e.g., "core-constitution"
    version: str  # e.g., "1.0.0"
    effective_from: str  # ISO timestamp
    
    # Thresholds for Tier Classification
    tier_thresholds: Dict[str, Any] = Field(
        default_factory=lambda: {
            "blast_radius_t1_limit": 5,
            "blast_radius_t2_limit": 20,
            "reversibility_t1_required": "HIGH",
        }
    )
    
    # Critical modules that require T2+ approval
    critical_modules: List[str] = Field(
        default_factory=lambda: [
            "core",
            "security",
            "archon",
            "chronos",
        ]
    )
    
    # Quorum: minimum distinct approvers per tier
    quorum_requirements: Dict[str, int] = Field(
        default_factory=lambda: {
            "T0": 1, "T1": 1, "T2": 2, "T3": 3
        }
    )
    
    # Forbidden patterns (Regex or AST signatures)
    forbidden_patterns: List[str] = Field(default_factory=list)
    
    # Invariants that must never be broken
    invariants: List[str] = Field(
        default_factory=lambda: [
            "AI_CANNOT_DIRECTLY_WRITE_DB",
            "SESSION_MUST_HAVE_OWNER",
            "DECISION_MUST_HAVE_RATIONALE"
        ]
    )

    # Loaded Invariant Rules from Packs
    invariant_rules: List[InvariantRule] = Field(default_factory=list)

class PolicyRegistry:
    """
    In-memory store for active governance policies.
    Loads packs from YAML files on startup.
    """
    
    _policies: Dict[str, GovernancePolicy] = {}
    _active_policy_id: Optional[str] = None

    @classmethod
    def load_packs(cls) -> List[InvariantRule]:
        """Load invariant rules from YAML packs."""
        rules = []
        if not os.path.exists(PACKS_DIR):
            return rules
            
        for filename in os.listdir(PACKS_DIR):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                try:
                    with open(os.path.join(PACKS_DIR, filename), "r") as f:
                        data = yaml.safe_load(f)
                        if "invariants" in data:
                            for inv in data["invariants"]:
                                rules.append(InvariantRule(**inv))
                except Exception as e:
                    print(f"Failed to load pack {filename}: {e}")
        return rules

    @classmethod
    def register(cls, policy: GovernancePolicy):
        """Register a new policy version."""
        key = f"{policy.id}:{policy.version}"
        cls._policies[key] = policy
        cls._active_policy_id = key

    @classmethod
    def get_active(cls) -> GovernancePolicy:
        """Retrieve the currently active governance policy."""
        rules = cls.load_packs()
        
        if not cls._active_policy_id:
            # Cold Start / Day Zero Policy
            return GovernancePolicy(
                id="genesis",
                version="0.0.1",
                effective_from="2026-01-01T00:00:00Z",
                invariant_rules=rules
            )
        
        policy = cls._policies[cls._active_policy_id]
        # Merge dynamic rules
        policy.invariant_rules = rules
        return policy

# Initialize Day Zero Policy
registry = PolicyRegistry()
