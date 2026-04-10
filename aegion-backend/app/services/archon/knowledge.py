"""
Cross-Workspace Knowledge Transfer.

Allows exporting successful governance patterns as templates.
"Learn once, govern everywhere."
"""

import json
from typing import Dict, Any

try:
    from ...core.logging import logger
except (ImportError, ValueError):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("KnowledgeTransferService")

class KnowledgeTransferService:
    """
    Exports decision patterns as templates for other workspaces.
    """
    
    def export_template(self, proposal_id: str) -> Dict[str, Any]:
        """
        Convert a successful proposal into a reusable template.
        """
        logger.info(f"Exporting proposal {proposal_id} as template...")
        
        # Simulate fetching proposal details
        proposal = self._fetch_proposal(proposal_id)
        
        if not proposal:
            return {"error": "Proposal not found"}
            
        template = {
            "template_id": f"tmpl-{proposal_id}",
            "name": f"Template from {proposal['title']}",
            "description": "Standardized governance pattern based on successful implementation.",
            "structure": {
                "tier": proposal["tier"],
                "required_evidence": ["architectural_review", "security_scan"], # Inferred
                "approval_roles": ["architect"] if proposal["tier"] == "T2" else ["lead_dev"]
            },
            "best_practices": [
                "Ensure rollback plan is defined",
                "Verify zero-downtime deployment strategy"
            ]
        }
        
        return template

    def _fetch_proposal(self, proposal_id: str) -> Dict[str, Any]:
        # Mock data
        if proposal_id == "prop-success":
            return {
                "id": "prop-success",
                "title": "Microservice Extraction",
                "tier": "T2",
                "status": "approved"
            }
        return None

# Singleton
_knowledge_service = None

def get_knowledge_service() -> KnowledgeTransferService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeTransferService()
    return _knowledge_service
