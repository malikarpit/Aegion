
import uuid
from typing import List, Optional
from datetime import datetime, timezone
import logging

from app.models.conflict import Conflict, ConflictSeverity, ConflictStatus
from app.models.rule import Rule, RulePriority
from app.adapters.persistence.event_store import InMemoryEventStore
from app.models.session import Session 
from app.domain.events import Event, EventMetadata

logger = logging.getLogger(__name__)

class GovernanceConflictService:
    def __init__(self, event_store=None):
        self._conflicts: List[Conflict] = []
        self._event_store = event_store
        # Mock rules for demonstration
        self._rules: List[Rule] = [
            Rule(
                rule_id="r1",
                name="No Direct DB Access in Controllers",
                description="Controllers should not import DB models directly.",
                condition="import_check",
                action="warn",
                priority=RulePriority.HIGH,
                created_by="system",
                created_at=datetime.now(timezone.utc),
                config={"forbidden_imports": ["app.infrastructure.database", "sqlalchemy"]}
            )
        ]

    async def hydrate(self, workspace_id: Optional[str] = None):
        """Restore conflict state from event store after restart."""
        if not self._event_store:
            return

        try:
            events = await self._event_store.get_all(workspace_id)
            for event in events:
                if event.event_type == "conflict.detected":
                    conflict = Conflict(**event.data)
                    self._conflicts.append(conflict)
                elif event.event_type == "conflict.resolved":
                    cid = event.data.get("conflict_id")
                    for c in self._conflicts:
                        if c.conflict_id == cid:
                            c.status = ConflictStatus.RESOLVED
                            c.resolved_at = event.data.get("resolved_at")
                            c.resolved_by = event.data.get("resolved_by")
            logger.info(f"Hydrated {len(self._conflicts)} conflicts for workspace {workspace_id}")
        except Exception as e:
            logger.warning(f"Failed to hydrate conflict state: {e}")

    async def detect_conflicts(self, workspace_id: str, file_path: str, content: str) -> List[Conflict]:
        """
        Analyzes a file update for governance violations.
        """
        new_conflicts = []
        
        # Simple heuristic check for the mock rule
        for rule in self._rules:
            if rule.condition == "import_check":
                forbidden = rule.config.get("forbidden_imports", [])
                for imp in forbidden:
                    if f"import {imp}" in content or f"from {imp}" in content:
                        conflict = Conflict(
                            conflict_id=str(uuid.uuid4()),
                            workspace_id=workspace_id,
                            rule_id=rule.rule_id,
                            severity=ConflictSeverity(rule.priority.value), # Map priority to severity
                            file_path=file_path,
                            message=f"Violation: {rule.name}. Found usage of '{imp}'",
                            detected_at=datetime.now(timezone.utc)
                        )
                        new_conflicts.append(conflict)
                        self._conflicts.append(conflict)
                        
                        # Persist to event store
                        if self._event_store:
                            event = Event(
                                event_type="conflict.detected",
                                workspace_id=workspace_id,
                                data=conflict.model_dump(mode="json"),
                                metadata=EventMetadata(
                                    actor_id="system",
                                    correlation_id=conflict.conflict_id
                                )
                            )
                            await self._event_store.append(event)
                        
                        # Broadcast immediately
                        await self._broadcast_conflict(workspace_id, conflict)
        
        return new_conflicts

    async def _broadcast_conflict(self, workspace_id: str, conflict: Conflict):
        """
        Broadcasts a conflict event to all connected clients in the workspace.
        """
        event = {
            "type": "conflict.detected",
            "conflict_id": conflict.conflict_id,
            "rule_id": conflict.rule_id,
            "severity": conflict.severity,
            "message": conflict.message,
            "file_path": conflict.file_path,
            "timestamp": conflict.detected_at.isoformat()
        }
        # Lazy import to avoid circular dependency
        from app.api.v1.websocket import manager
        await manager.broadcast_to_workspace(workspace_id, event)

    def get_active_conflicts(self, workspace_id: str) -> List[Conflict]:
        return [c for c in self._conflicts if c.workspace_id == workspace_id and c.status == ConflictStatus.OPEN]

    def resolve_conflict(self, conflict_id: str, user_id: str) -> Optional[Conflict]:
        for c in self._conflicts:
            if c.conflict_id == conflict_id:
                c.status = ConflictStatus.RESOLVED
                c.resolved_at = datetime.now(timezone.utc)
                c.resolved_by = user_id
                
                # Persist resolution to event store (fire-and-forget for sync method)
                if self._event_store:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(self._event_store.append(Event(
                                event_type="conflict.resolved",
                                workspace_id=c.workspace_id,
                                data={
                                    "conflict_id": conflict_id,
                                    "resolved_at": c.resolved_at.isoformat(),
                                    "resolved_by": user_id,
                                },
                                metadata=EventMetadata(
                                    actor_id=user_id,
                                    correlation_id=conflict_id
                                )
                            )))
                    except Exception:
                        pass  # Best-effort persistence
                
                return c
        return None

    async def detect_branch_conflicts(self, workspace_id: str, base_branch: str, head_branch: str) -> List[Conflict]:
        """
        Analyze branch drift for governance violations.
        """
        from app.services.repo_intelligence.service import get_repo_service
        
        repo_service = get_repo_service()
        drift = await repo_service.detect_branch_drift(workspace_id, base_branch, head_branch)
        
        if "error" in drift:
            logger.error(f"Drift detection failed: {drift['error']}")
            return []
            
        stats = drift["stats"]
        changes = drift["changes"]
        new_conflicts = []
        
        # Rule 1: Mass Deletion
        if stats["deleted"] > 20: 
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                rule_id="mass_deletion",
                severity=ConflictSeverity.CRITICAL,
                message=f"Mass Deletion Detected: {stats['deleted']} files deleted. This requires Council review.",
                detected_at=datetime.now(timezone.utc),
                context={"stats": stats}
            )
            new_conflicts.append(conflict)
            self._conflicts.append(conflict)
            await self._broadcast_conflict(workspace_id, conflict)

        # Rule 2: Critical Infrastructure Change
        infra_changes = [c['file_path'] for c in changes if "infrastructure/" in c['file_path'] or "migrations/" in c['file_path']]
        if infra_changes:
             conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                rule_id="infra_change",
                severity=ConflictSeverity.HIGH,
                message=f"Core Infrastructure Changed: {len(infra_changes)} files modified in sensitive paths.",
                detected_at=datetime.now(timezone.utc),
                context={"files": infra_changes[:5]} # Limit context
            )
             new_conflicts.append(conflict)
             self._conflicts.append(conflict)
             await self._broadcast_conflict(workspace_id, conflict)
             
        return new_conflicts

# Singleton instance
conflict_service = GovernanceConflictService()
