"""
OPA Policy Engine Adapter.

Provides Policy-as-Code enforcement using Rego rules.
Includes a lightweight Python evaluator for zero-dependency execution.
"""

import os
import re
from typing import Dict, Any, List, Optional
try:
    from ...core.logging import logger
except (ImportError, ValueError):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("OPAService")

class OPAService:
    """
    Enforces governance policies defined in Rego.
    """
    
    def __init__(self, policy_path: str = "app/policies/governance.rego"):
        self.policy_path = policy_path
        self.rules = self._load_rules()
        logger.info(f"Loaded OPA policy rules from {policy_path}")

    def _load_rules(self) -> Dict[str, Any]:
        """
        Parses the .rego file to extract simple rule logic.
        This is a lightweight parser for the specific subset of Rego used.
        """
        rules = {
            "tiers": {},
            "default_deny": True
        }
        
        try:
            with open(self.policy_path, 'r') as f:
                content = f.read()
                
            # Extract allow blocks
            # Very basic regex parsing for demo purposes
            # Matches: allow { input.tier == "TIER" ... count >= N ... }
            
            # T0
            if 'input.tier == "T0"' in content:
                rules["tiers"]["T0"] = {"quorum": 0, "evidence": 0}
                
            # T1
            if 'input.tier == "T1"' in content:
                # Extract quorum
                quorum_match = re.search(r'input\.tier == "T1".*?count\(input\.approvals\) >= (\d+)', content, re.DOTALL)
                evidence_match = re.search(r'input\.tier == "T1".*?count\(input\.evidence\) >= (\d+)', content, re.DOTALL)
                rules["tiers"]["T1"] = {
                    "quorum": int(quorum_match.group(1)) if quorum_match else 1,
                    "evidence": int(evidence_match.group(1)) if evidence_match else 1
                }

            # T2
            if 'input.tier == "T2"' in content:
                quorum_match = re.search(r'input\.tier == "T2".*?count\(input\.approvals\) >= (\d+)', content, re.DOTALL)
                evidence_match = re.search(r'input\.tier == "T2".*?count\(input\.evidence\) >= (\d+)', content, re.DOTALL)
                rules["tiers"]["T2"] = {
                    "quorum": int(quorum_match.group(1)) if quorum_match else 2,
                    "evidence": int(evidence_match.group(1)) if evidence_match else 2,
                    "role_required": "architect"
                }

            # T3
            if 'input.tier == "T3"' in content:
                quorum_match = re.search(r'input\.tier == "T3".*?count\(input\.approvals\) >= (\d+)', content, re.DOTALL)
                evidence_match = re.search(r'input\.tier == "T3".*?count\(input\.evidence\) >= (\d+)', content, re.DOTALL)
                rules["tiers"]["T3"] = {
                    "quorum": int(quorum_match.group(1)) if quorum_match else 3,
                    "evidence": int(evidence_match.group(1)) if evidence_match else 3,
                    "role_required": "admin"
                }
                
        except FileNotFoundError:
            logger.error(f"Policy file not found: {self.policy_path}")
            # Fallback to defaults
            return rules
            
        return rules

    def evaluate_policy(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate policy against input.
        Returns {"allow": bool, "reason": str}
        """
        tier = input_data.get("tier")
        approvals = input_data.get("approvals", [])
        evidence = input_data.get("evidence", [])
        
        rule = self.rules["tiers"].get(tier)
        
        if not rule:
            return {"allow": False, "reason": f"No policy defined for tier {tier}"}
            
        # Check Quorum
        if len(approvals) < rule["quorum"]:
            return {
                "allow": False, 
                "reason": f"Insufficient approvals. Need {rule['quorum']}, got {len(approvals)}"
            }
            
        # Check Evidence
        if len(evidence) < rule.get("evidence", 0):
             return {
                "allow": False, 
                "reason": f"Insufficient evidence. Need {rule.get('evidence', 0)}, got {len(evidence)}"
            }

        # Check Roles
        if "role_required" in rule:
            required = rule["role_required"]
            has_role = any(a.get("role") == required for a in approvals)
            if not has_role:
                return {
                    "allow": False,
                    "reason": f"Missing required approval from {required}"
                }

        return {"allow": True, "reason": "Policy passed"}

# Singleton
_opa_service = None

def get_opa_service() -> OPAService:
    global _opa_service
    if _opa_service is None:
        # Check absolute path or relative
        import os
        # Try to find the policy file relative to project root
        base_dir = os.getcwd()
        if "app" not in os.listdir(base_dir):
            if "aegion-backend" in base_dir:
                 pass # we are good
            else:
                 # fallback search
                 pass
        
        policy_path = os.path.join(base_dir, "app/policies/governance.rego")
        if not os.path.exists(policy_path):
             # Try relative to this file
             current_dir = os.path.dirname(os.path.abspath(__file__))
             policy_path = os.path.join(current_dir, "../../../policies/governance.rego")
             
        _opa_service = OPAService(policy_path=policy_path)
    return _opa_service
