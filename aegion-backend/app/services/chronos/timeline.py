"""
Aegion Chronos - Architecture Timeline Service.

Advanced Epistemics
Manages ADRs and architecture evolution tracking.
"""

from typing import List, Optional, Dict, Any
import uuid
import logging

from ...contracts.adr import (
    ArchitectureDecision,
    ADRStatus,
    DecisionDriver,
    TimelineEvent,
    ArchitectureTimeline
)
from ...core.time import TimeAuthority
from ...domain.events import Event, EventMetadata
from ...adapters.persistence.event_store import EventStoreAdapter, InMemoryEventStore
from ...core.errors import ConcurrencyError
from ...core.metrics import metrics, ChronosMetrics

logger = logging.getLogger(__name__)

class ArchitectureTimelineService:
    """
    Service for managing architecture decision records and timeline via Event Sourcing.
    """
    
    def __init__(self, event_store: EventStoreAdapter):
        self.event_store = event_store
        # In-memory projections (Cache)
        self._adrs: Dict[str, ArchitectureDecision] = {}
        self._workspace_timelines: Dict[str, ArchitectureTimeline] = {}

    async def hydrate(self, workspace_id: Optional[str] = None):
        """Rebuild state from event log."""
        logger.info(f"💦 Hydrating Timeline Service (Workspace: {workspace_id or 'ALL'})...")
        
        start_time = TimeAuthority.monotonic() # Manual timing since method is async and we want event count
        
        events = await self.event_store.get_all(workspace_id)
        for event in events:
            await self._apply_event(event)

        duration = TimeAuthority.duration(start_time)
        ChronosMetrics.hydration_complete(duration, len(events), workspace_id or "all")
        
        logger.info(f"✅ Hydration complete. Loaded {len(events)} events in {duration:.2f}ms.")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get operational statistics."""
        return {
            "total_adrs": len(self._adrs),
            "workspaces": len(self._workspace_timelines),
            "backend_type": type(self.event_store).__name__,
            "sync_status": "synced"
        }

    @metrics.timed("chronos_apply_event")
    async def _apply_event(self, event: Event):
        """Apply event to in-memory projections."""
        if event.event_type == "adr.created":
            data = event.data
            adr = ArchitectureDecision(**data)
            # Ensure version starts at 1 if not present (legacy compat)
            if adr.version == 0: 
                adr.version = 1
            self._adrs[adr.adr_id] = adr
            
            # Update timeline
            timeline = self._get_or_create_timeline(event.workspace_id)
            if adr.adr_id not in timeline.current_adrs:
                timeline.current_adrs.append(adr.adr_id)
                
            # Handle supersession
            if adr.supersedes and adr.supersedes in self._adrs:
                old_adr = self._adrs[adr.supersedes]
                old_adr.status = ADRStatus.SUPERSEDED
                old_adr.superseded_by = adr.adr_id
                # Side-effect update, might bump version in strict system but skipping for now
                # to avoid complexity of multi-aggregate updates in one event

        elif event.event_type == "adr.accepted":
            adr_id = event.data["adr_id"]
            if adr_id in self._adrs:
                adr = self._adrs[adr_id]
                adr.status = ADRStatus.ACCEPTED
                adr.accepted_at = event.data["accepted_at"]
                adr.accepted_by = event.data["accepted_by"]
                adr.positive_consequences = event.data.get("positive_consequences", [])
                adr.negative_consequences = event.data.get("negative_consequences", [])
                adr.version = event.data.get("version", adr.version + 1)

        elif event.event_type == "adr.deprecated":
            adr_id = event.data["adr_id"]
            if adr_id in self._adrs:
                adr = self._adrs[adr_id]
                adr.status = ADRStatus.DEPRECATED
                adr.version = event.data.get("version", adr.version + 1)
                
                timeline = self._get_or_create_timeline(event.workspace_id)
                if adr_id in timeline.current_adrs:
                    timeline.current_adrs.remove(adr_id)
                if adr_id not in timeline.deprecated_adrs:
                    timeline.deprecated_adrs.append(adr_id)

    async def create_adr(
        self,
        title: str,
        context: str,
        decision: str,
        rationale: str,
        created_by: str,
        workspace_id: str,
        drivers: List[DecisionDriver] = [],
        supersedes: Optional[str] = None
    ) -> ArchitectureDecision:
        """Create a new ADR via Event."""
        adr_id = f"adr-{uuid.uuid4().hex[:8]}"
        created_at = TimeAuthority.now()
        
        adr_data = {
            "adr_id": adr_id,
            "title": title,
            "context": context,
            "decision": decision,
            "rationale": rationale,
            "drivers": [d.model_dump() for d in drivers],
            "supersedes": supersedes,
            "created_at": created_at,
            "created_by": created_by,
            "status": ADRStatus.PROPOSED,
            "version": 1
        }
        
        event = Event(
            event_type="adr.created",
            workspace_id=workspace_id,
            data=adr_data,
            metadata=EventMetadata(
                correlation_id=uuid.uuid4().hex,
                actor_id=created_by
            )
        )
        
        await self.event_store.append(event)
        ChronosMetrics.event_appended("adr.created", workspace_id)
        await self._apply_event(event) # Write-through

        # ── Persist to Supabase adrs table for dashboard queries ──
        try:
            from ...db.supabase_client import get_supabase_client
            get_supabase_client().table("adrs").insert({
                "workspace_id": workspace_id,
                "adr_id": adr_id,
                "title": title,
                "context": context,
                "decision": decision,
                "rationale": rationale,
                "status": ADRStatus.PROPOSED.value,
                "created_by": created_by,
                "metadata": {
                    "drivers": [d.model_dump() for d in drivers] if drivers else [],
                    "supersedes": supersedes,
                    "version": 1,
                },
            }).execute()
        except Exception as exc:
            logger.warning(f"ADR persist to adrs table failed (non-fatal): {exc}")
        
        return self._adrs[adr_id]

    async def accept_adr(
        self,
        adr_id: str,
        accepted_by: str,
        workspace_id: str,
        expected_version: int,
        positive_consequences: List[str] = [],
        negative_consequences: List[str] = []
    ) -> ArchitectureDecision:
        """Accept an ADR."""
        if adr_id not in self._adrs:
             raise ValueError(f"ADR {adr_id} not found")
        
        current_adr = self._adrs[adr_id]
        if current_adr.version != expected_version:
             raise ConcurrencyError(
                 f"ADR {adr_id} has changed. Expected v{expected_version}, got v{current_adr.version}",
                 current_version=current_adr.version,
                 expected_version=expected_version
             )

        event = Event(
            event_type="adr.accepted",
            workspace_id=workspace_id,
            data={
                "adr_id": adr_id,
                "accepted_by": accepted_by,
                "accepted_at": TimeAuthority.now(),
                "positive_consequences": positive_consequences,
                "negative_consequences": negative_consequences,
                "version": current_adr.version + 1
            },
            metadata=EventMetadata(
                correlation_id=uuid.uuid4().hex,
                actor_id=accepted_by
            )
        )
        
        await self.event_store.append(event)
        await self._apply_event(event)
        return self._adrs[adr_id]

    async def deprecate_adr(
        self,
        adr_id: str,
        deprecated_by: str,
        workspace_id: str,
        reason: str,
        expected_version: int
    ) -> ArchitectureDecision:
        """Deprecate an ADR."""
        if adr_id not in self._adrs:
             raise ValueError(f"ADR {adr_id} not found")

        current_adr = self._adrs[adr_id]
        if current_adr.version != expected_version:
             raise ConcurrencyError(
                 f"ADR {adr_id} has changed. Expected v{expected_version}, got v{current_adr.version}",
                 current_version=current_adr.version,
                 expected_version=expected_version
             )

        event = Event(
            event_type="adr.deprecated",
            workspace_id=workspace_id,
            data={
                "adr_id": adr_id,
                "reason": reason,
                "deprecated_by": deprecated_by,
                 "version": current_adr.version + 1
            },
            metadata=EventMetadata(
                correlation_id=uuid.uuid4().hex,
                actor_id=deprecated_by
            )
        )
        
        await self.event_store.append(event)
        await self._apply_event(event)
        return self._adrs[adr_id]

    # ... Queries stay largely the same, reading from self._adrs projection ...

    async def get_adr(self, adr_id: str) -> Optional[ArchitectureDecision]:
        return self._adrs.get(adr_id)
    
    async def list_adrs(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[ADRStatus] = None
    ) -> List[ArchitectureDecision]:
        adrs = list(self._adrs.values())
        if status:
            adrs = [a for a in adrs if a.status == status]
        return adrs
    
    async def get_timeline(self, workspace_id: str) -> ArchitectureTimeline:
        return self._get_or_create_timeline(workspace_id)
    
    async def get_supersession_chain(self, adr_id: str) -> List[ArchitectureDecision]:
        """Get the full supersession chain for an ADR."""
        chain = []
        # Re-using memory projection logic which is fine since we kept self._adrs populated
        current_id = adr_id
        
        # Go backwards
        while current_id:
            adr = self._adrs.get(current_id)
            if adr:
                chain.insert(0, adr)
                current_id = adr.supersedes
            else:
                break
        
        # Go forwards
        if adr_id in self._adrs and self._adrs[adr_id].superseded_by:
             current_id = self._adrs[adr_id].superseded_by
             while current_id:
                adr = self._adrs.get(current_id)
                if adr:
                    chain.append(adr)
                    current_id = adr.superseded_by
                else:
                    break
        
        return chain
    
    def _get_or_create_timeline(self, workspace_id: str) -> ArchitectureTimeline:
        if workspace_id not in self._workspace_timelines:
            self._workspace_timelines[workspace_id] = ArchitectureTimeline(
                workspace_id=workspace_id
            )
        return self._workspace_timelines[workspace_id]


# Singleton management
_timeline_service: Optional[ArchitectureTimelineService] = None

def get_timeline_service(event_store: Optional[EventStoreAdapter] = None) -> ArchitectureTimelineService:
    global _timeline_service
    if _timeline_service is None:
        if event_store is None:
             # Fallback for tests or disconnected usage
             event_store = InMemoryEventStore()
        _timeline_service = ArchitectureTimelineService(event_store)
    return _timeline_service
