"""
Compliance & Audit Export Service.

Generates audit-ready reports (SOC2/ISO) from decision history.
Outputs Markdown/JSON for easy consumption by external auditors.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
try:
    from ...core.logging import logger
except (ImportError, ValueError):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ComplianceExporter")

from ...services.graph_provider import get_shared_graph_service
from ...models.decision import DecisionTier
from ...ports.knowledge_graph import GraphEdgeType

class ComplianceExporter:
    """
    Exports governance decisions for compliance audits.
    """
    
    async def generate_pr_description(self, proposal_id: str) -> str:
        """
        Generate a summary card for a PR based on a proposal.
        """
        graph = get_shared_graph_service()
        
        # Fetch data
        proposal = await graph.get_proposal(proposal_id)
        if not proposal:
            return f"**Aegion Usage:** Proposal `{proposal_id}` not found."
            
        evidence_nodes = await graph.get_evidence_for_proposal(proposal_id)
        
        edges = await graph.get_edges(source_id=proposal_id, edge_type=GraphEdgeType.SUPERSEDES)
        decision_id = edges[0].target_id if edges else None
        
        decision_status = "Pending"
        approver = "None"
        decision = None
        
        if decision_id:
            decision = await graph.get_node(decision_id)
            if decision:
                # Find approver
                app_edges = await graph.get_edges(source_id=decision_id, edge_type=GraphEdgeType.APPROVED_BY)
                if app_edges:
                    approver = app_edges[0].target_id
                decision_status = "Approved" if decision.properties.get("verdict") != "rejected" else "Rejected"

        # Format
        lines = []
        lines.append("## 🧠 Logic & Compliance")
        lines.append(f"**Proposal:** {proposal.properties.get('title')}")
        lines.append(f"**Tier:** {proposal.properties.get('tier', 'T1')}")
        lines.append(f"**Status:** {decision_status}")
        
        lines.append("### Reasoning")
        lines.append(proposal.properties.get("description", "No description provided."))
        
        if evidence_nodes:
            lines.append("### Evidence")
            for e in evidence_nodes:
                lines.append(f"- [{e.properties.get('evidence_type', 'manual')}] {e.properties.get('summary', 'Evidence')}")
                
        if decision and decision_id:
             lines.append("### 🛡 Architect/Council Certificate")
             lines.append(f"> Decision `{decision_id}` confirmed by `{approver}`.")
             
        return "\n".join(lines)

    async def generate_report(self, start_date: datetime, end_date: datetime, format: str = "markdown") -> str:
        """
        Generate compliance report for a given period.
        """
        logger.info(f"Generating compliance report from {start_date} to {end_date} (format={format})...")
        
        decisions = self._fetch_decisions(start_date, end_date)
        
        if format == "json":
            return json.dumps(decisions, indent=2, default=str)
        
        # Markdown Generaton
        lines = []
        lines.append(f"# Aegion Governance Audit Report")
        lines.append(f"**Period:** {start_date.date()} to {end_date.date()}")
        lines.append(f"**Generated At:** {datetime.now()}")
        lines.append("")
        
        lines.append("## Executive Summary")
        total = len(decisions)
        approved = len([d for d in decisions if d["status"] == "approved"])
        rejected = len([d for d in decisions if d["status"] == "rejected"])
        lines.append(f"- **Total Decisions:** {total}")
        lines.append(f"- **Approved:** {approved}")
        lines.append(f"- **Rejected:** {rejected}")
        lines.append("")
        
        lines.append("## Decision Log")
        lines.append("| ID | Date | Tier | Status | Approvers | Evidence Count |")
        lines.append("|----|------|------|--------|-----------|----------------|")
        
        for d in decisions:
            approvers = ", ".join([a["user_id"] for a in d.get("approvals", [])])
            lines.append(f"| {d['id']} | {d['timestamp']} | {d['tier']} | {d['status']} | {approvers} | {len(d.get('evidence', []))} |")
            
        lines.append("")
        lines.append("## Detailed Audit Trail")
        for d in decisions:
            lines.append(f"### {d['id']}: {d.get('title', 'Untitled')}")
            lines.append(f"- **Tier:** {d['tier']}")
            lines.append(f"- **Justification:** {d.get('justification', 'N/A')}")
            lines.append(f"- **Evidence:**")
            for e in d.get("evidence", []):
                lines.append(f"  - {e}")
            lines.append("---")
            
        return "\n".join(lines)

    def _fetch_decisions(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """
        Simulate fetching decisions from EventStore/Graph.
        """
        # Mock data (preserving original mock for compatibility, but ideal to replace with graph calls)
        return [
            {
                "id": "dec-101",
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "tier": "T2",
                "status": "approved",
                "title": "Update Payment Gateway",
                "approvals": [{"user_id": "alice@Example.com", "role": "architect"}],
                "evidence": ["ev-struct-1", "ev-load-test-5"],
                "justification": "Required for compliance upgrade."
            },
            {
                "id": "dec-102",
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                "tier": "T1",
                "status": "rejected",
                "title": "Quick Fix Login",
                "approvals": [],
                "evidence": [],
                "justification": "Bypassing checks due to urgency." 
            }
        ]

# Singleton
_exporter: Optional[ComplianceExporter] = None

def get_compliance_exporter() -> ComplianceExporter:
    global _exporter
    if _exporter is None:
        _exporter = ComplianceExporter()
    return _exporter
