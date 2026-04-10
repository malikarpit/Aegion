"""
Decision Regression Testing Service (Enhancement 12).

Provides automated re-validation of past governance decisions against current policies.
Detects policy drift where valid past decisions would now be rejected.
"""

import json
import json
from typing import List, Dict, Any
try:
    from ...core.logging import logger
except (ImportError, ValueError):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("RegressionTester")
    
try:
    from .opa import get_opa_service
except ImportError:
    # Fallback for standalone execution
    try:
        from app.services.archon.opa import get_opa_service
    except ImportError:
        # If running in same dir with path set
        import opa
        get_opa_service = opa.get_opa_service

class RegressionTester:
    """
    Replays historical decisions against current OPA policies.
    """
    
    def __init__(self):
        self.opa = get_opa_service()

    async def run_regression_test(self, limit: int = 100) -> Dict[str, Any]:
        """
        Fetch last N decisions and re-validate them.
        Returns report of regressions.
        """
        logger.info(f"Starting decision regression test (limit={limit})...")
        
        # In a real system, we'd query the Graph or Event Store.
        # Here we simulate fetching historical decisions with their metadata.
        decisions = self._fetch_historical_decisions(limit)
        
        passed = 0
        failed = 0
        regressions = []
        
        for decision in decisions:
            # Construct OPA input from historical data
            opa_input = {
                "tier": decision.get("tier"),
                "approvals": decision.get("approvals"),
                "evidence": decision.get("evidence")
            }
            
            result = self.opa.evaluate_policy(opa_input)
            
            # Logic:
            # If historical decision was APPROVED, and current policy says DENY -> Regression.
            # If historical was REJECTED, and current says ALLOW -> Relaxed Policy (Warning).
            
            historical_outcome = decision.get("status") # "approved" or "rejected"
            current_allow = result["allow"]
            
            if historical_outcome == "approved" and not current_allow:
                failed += 1
                regressions.append({
                    "decision_id": decision["id"],
                    "issue": "REGRESSION: Previously approved, now denied.",
                    "reason": result.get("reason")
                })
            elif historical_outcome == "rejected" and current_allow:
                # Not necessarily a failure, but worth noting
                regressions.append({
                    "decision_id": decision["id"],
                    "issue": "RELAXATION: Previously rejected, now allowed.",
                    "reason": "Policy loosened."
                })
            else:
                passed += 1
                
        report = {
            "total_checked": len(decisions),
            "passed": passed,
            "regressions_count": failed,
            "regressions": regressions,
            "status": "PASSED" if failed == 0 else "FAILED"
        }
        
        logger.info(f"Regression Test Complete. Status: {report['status']}")
        return report

    def _fetch_historical_decisions(self, limit: int) -> List[Dict[str, Any]]:
        """
        Simulate fetching past decisions.
        """
        # Mock data representing the history of the system
        return [
            {
                "id": "dec-001",
                "tier": "T1",
                "status": "approved",
                "approvals": [{"role": "developer"}],
                "evidence": ["ev-1"]
            },
            {
                "id": "dec-002",
                "tier": "T2",
                "status": "approved",
                "approvals": [{"role": "architect"}], # Valid under current policy (Quorum=1)
                "evidence": ["ev-1", "ev-2"]
            },
            {
                "id": "dec-003", # This one simulates a regression (e.g. if we raised T1 evidence req)
                "tier": "T1",
                "status": "approved",
                "approvals": [{"role": "developer"}],
                "evidence": [] # Missing evidence, but was approved (maybe policy was weaker then?)
            }
        ]

# Singleton
_regression_tester = None

def get_regression_tester() -> RegressionTester:
    global _regression_tester
    if _regression_tester is None:
        _regression_tester = RegressionTester()
    return _regression_tester
