"""
Aegion Handoff Service.

Generates summaries of session activities for ownership transfer or session closure.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

from ...core.logging import logger
from .session_ownership import get_session_ownership
from .attribution import get_edit_attribution
from ..graph_provider import get_shared_graph_service
from ..governance_conflict import conflict_service

class HandoffService:
    def __init__(self):
        self.ownership = get_session_ownership()
        self.attribution = get_edit_attribution()
        # self.graph = get_shared_graph_service() # Graph service is async, might need to call it in methods
        self.conflicts = conflict_service

    async def generate_handoff_summary(self, session_id: str) -> str:
        """
        Generates a markdown summary of the session for handoff.
        """
        graph = get_shared_graph_service()
        
        # 1. Session Metadata
        owner_id = self.ownership.get_owner(session_id)
        participants = self.ownership.get_participants(session_id)
        if participants:
            participant_names = ", ".join([p.user_id for p in participants])
        else:
            participant_names = "None"
        
        # 2. Proposals
        proposals = await graph.list_proposals(workspace_id=session_id, limit=50)
        pending_proposals = [p for p in proposals if p.properties.get("status") == "pending"]
        
        # 3. Conflicts
        # Note: In Aegion, workspace_id often equates to session_id for ephemeral sessions
        active_conflicts = self.conflicts.get_active_conflicts(session_id)
        
        # 4. Decisions (Recent)
        decisions = await graph.list_decisions(workspace_id=session_id, limit=10)
        
        # 5. Generate Markdown
        lines = []
        lines.append(f"# Handoff Report: Session `{session_id}`")
        lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"**Owner:** `{owner_id or 'Unknown'}`")
        lines.append(f"**Participants:** {participant_names}")
        lines.append("")
        
        lines.append("## 1. Active Context")
        lines.append(f"- **Proposals Pending**: {len(pending_proposals)}")
        lines.append(f"- **Governance Conflicts**: {len(active_conflicts)}")
        lines.append("")
        
        if active_conflicts:
            lines.append("### 🚨 Active Conflicts")
            for c in active_conflicts:
                severity_str = c.severity.value if hasattr(c.severity, 'value') else str(c.severity)
                is_high = severity_str in ["high", "critical"]
                severity_icon = "🔴" if is_high else "⚠️"
                lines.append(f"- {severity_icon} **{c.rule_id}**: {c.message} (`{c.file_path}`)")
            lines.append("")

        if pending_proposals:
            lines.append("### 📝 Pending Proposals")
            for p in pending_proposals[:5]:
                tier = p.properties.get("tier", "T1")
                lines.append(f"- [{tier}] **{p.properties.get('title', 'Untitled')}**")
            lines.append("")

        lines.append("## 2. Key Decisions (This Session)")
        if not decisions:
            lines.append("_No decisions recorded._")
        else:
            for d in decisions:
                # Decision node usually links to proposal, doesn't always have title.
                decided_at = d.properties.get('decided_at', 'Unknown time')
                lines.append(f"- Decision `{d.node_id}` ({decided_at})")
        lines.append("")
        
        lines.append("## 3. Pending Actions")
        if not pending_proposals and not active_conflicts:
            lines.append("_No pending actions._")
        else:
            for p in pending_proposals:
                lines.append(f"- [ ] Review Proposal `{p.node_id}`")
            for c in active_conflicts:
                lines.append(f"- [ ] Resolve Conflict `{c.conflict_id}`")
                
        return "\n".join(lines)

# Singleton
_handoff_service: Optional[HandoffService] = None

def get_handoff_service() -> HandoffService:
    global _handoff_service
    if _handoff_service is None:
        _handoff_service = HandoffService()
    return _handoff_service
