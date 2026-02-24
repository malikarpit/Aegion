"""
Aegion Thought Service.

Manages the lifecycle of Thought Artifacts using Event Sourcing.
Ensures every meaningful change has an immutable "why" chain.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..contracts.thought import ThoughtState, ThoughtLinkType
from ..models.thought import (
    ThoughtCommit,
    ThoughtLink,
    CreateThoughtRequest,
    UpdateThoughtRequest,
    SealThoughtRequest,
    LinkCommitRequest
)
from ..domain.events import Event, EventMetadata
from ..adapters.persistence.event_store import EventStoreAdapter
from ..core.time import TimeAuthority
from ..core.errors import ResourceNotFoundError, ValidationError, ConflictError

logger = logging.getLogger(__name__)


class ThoughtService:
    """
    Service for managing Thought Artifacts ('Git for Thoughts').
    Uses Event Sourcing to maintain a perfect audit trail of reasoning.
    """

    def __init__(self, event_store: EventStoreAdapter):
        self.event_store = event_store
        # In-memory projection of active thoughts
        self._thoughts: Dict[str, ThoughtCommit] = {}
        self._commit_index: Dict[str, str] = {}  # sha -> thought_id

    async def hydrate(self, workspace_id: Optional[str] = None):
        """Rebuild state from event log."""
        logger.info(f"🧠 Hydrating Thought Service (Workspace: {workspace_id or 'ALL'})...")
        events = await self.event_store.get_all(workspace_id)
        count = 0
        for event in events:
            if event.event_type.startswith("thought."):
                await self._apply_event(event)
                count += 1
        logger.info(f"✅ Thought Service hydrated. Loaded {count} events.")

    async def _apply_event(self, event: Event):
        """Apply event to in-memory projections."""
        if event.event_type == "thought.created":
            data = event.data
            thought = ThoughtCommit(**data)
            self._thoughts[thought.thought_id] = thought
            
            # Index links
            for link in thought.links:
                if link.target_type == "commit":
                    self._commit_index[link.target_id] = thought.thought_id

        elif event.event_type == "thought.updated":
            thought_id = event.data["thought_id"]
            if thought_id in self._thoughts:
                thought = self._thoughts[thought_id]
                updates = event.data.get("updates", {})
                
                if "title" in updates: thought.title = updates["title"]
                if "rationale" in updates: thought.rationale = updates["rationale"]
                if "alternatives" in updates: thought.alternatives = updates["alternatives"]
                
                # Handle link updates
                if "added_links" in updates:
                    new_links = [ThoughtLink(**l) for l in updates["added_links"]]
                    thought.links.extend(new_links)
                    # Update index
                    for link in new_links:
                        if link.target_type == "commit":
                            self._commit_index[link.target_id] = thought.thought_id
                            
                if "removed_link_ids" in updates:
                    thought.links = [l for l in thought.links if l.link_id not in updates["removed_link_ids"]]
                    # Rebuild index for this thought (simplest safe way)
                    # In a real DB, this would be a delete query. 
                    # In-memory, we might leave stale index entries if we are not careful, 
                    # but for now we assume commit links are additive.

                thought.updated_at = event.metadata.timestamp

        elif event.event_type == "thought.sealed":
            thought_id = event.data["thought_id"]
            if thought_id in self._thoughts:
                thought = self._thoughts[thought_id]
                thought.state = ThoughtState.SEALED
                thought.sealed_at = event.metadata.timestamp
                thought.content_hash = event.data.get("content_hash")
                thought.updated_at = event.metadata.timestamp

        elif event.event_type == "thought.linked":
            thought_id = event.data["thought_id"]
            link_data = event.data["link"]
            if thought_id in self._thoughts:
                thought = self._thoughts[thought_id]
                link = ThoughtLink(**link_data)
                thought.links.append(link)
                thought.updated_at = event.metadata.timestamp
                
                if link.target_type == "commit":
                    self._commit_index[link.target_id] = thought.thought_id

    # --- Commands ---

    async def create_thought(self, req: CreateThoughtRequest, created_by: str) -> ThoughtCommit:
        """Create a new Draft Thought."""
        thought_id = f"tht-{uuid.uuid4().hex[:8]}"
        
        # Initial links setup
        items = []
        if req.proposal_id:
            items.append(ThoughtLink(
                type=ThoughtLinkType.DERIVES_FROM,
                target_id=req.proposal_id,
                target_type="proposal"
            ))
        if req.decision_id:
             items.append(ThoughtLink(
                type=ThoughtLinkType.DERIVES_FROM,
                target_id=req.decision_id,
                target_type="decision"
            ))

        thought = ThoughtCommit(
            thought_id=thought_id,
            workspace_id=req.workspace_id,
            session_id=req.session_id,
            title=req.title,
            rationale=req.rationale,
            links=items,
            created_by=created_by,
            state=ThoughtState.DRAFT
        )

        event = Event(
            event_type="thought.created",
            workspace_id=req.workspace_id,
            data=thought.model_dump(),
            metadata=EventMetadata(
                actor_id=created_by,
                correlation_id=uuid.uuid4().hex
            )
        )

        await self.event_store.append(event)
        await self._apply_event(event)
        return self._thoughts[thought_id]

    async def update_thought(self, thought_id: str, req: UpdateThoughtRequest, actor_id: str) -> ThoughtCommit:
        """Update a Draft Thought."""
        thought = await self.get_thought(thought_id)
        if not thought:
            raise ResourceNotFoundError(f"Thought {thought_id} not found")
        
        if thought.state != ThoughtState.DRAFT:
             raise ConflictError(f"Cannot edit thought {thought_id} in state {thought.state}")

        updates = {}
        if req.title is not None: updates["title"] = req.title
        if req.rationale is not None: updates["rationale"] = req.rationale
        if req.alternatives is not None: updates["alternatives"] = req.alternatives
        
        if req.add_links:
            updates["added_links"] = [l.model_dump() for l in req.add_links]
        
        if req.remove_link_ids:
            updates["removed_link_ids"] = req.remove_link_ids

        if not updates:
            return thought

        event = Event(
            event_type="thought.updated",
            workspace_id=thought.workspace_id,
            data={
                "thought_id": thought_id,
                "updates": updates
            },
            metadata=EventMetadata(
                actor_id=actor_id,
                correlation_id=uuid.uuid4().hex
            )
        )

        await self.event_store.append(event)
        await self._apply_event(event)
        return self._thoughts[thought_id]

    async def seal_thought(self, thought_id: str, req: SealThoughtRequest, actor_id: str) -> ThoughtCommit:
        """Seal a thought, making it immutable."""
        thought = await self.get_thought(thought_id)
        if not thought:
            raise ResourceNotFoundError(f"Thought {thought_id} not found")

        if thought.state != ThoughtState.DRAFT:
            return thought # Idempotent-ish for now, or raise error

        # Compute canonical content hash from immutable thought fields
        import hashlib, json
        canonical = json.dumps({
            "thought_id": thought_id,
            "title": thought.title,
            "rationale": thought.rationale,
            "claim": getattr(thought, 'claim', ''),
            "workspace_id": thought.workspace_id,
        }, sort_keys=True, default=str)
        content_hash = req.content_hash or hashlib.sha256(canonical.encode()).hexdigest()

        event = Event(
            event_type="thought.sealed",
            workspace_id=thought.workspace_id,
            data={
                "thought_id": thought_id,
                "content_hash": content_hash
            },
            metadata=EventMetadata(
                actor_id=actor_id,
                correlation_id=uuid.uuid4().hex
            )
        )
        
        await self.event_store.append(event)
        await self._apply_event(event)
        return self._thoughts[thought_id]

    async def link_commit(self, thought_id: str, req: LinkCommitRequest, actor_id: str) -> ThoughtLink:
        """Link a commit to a thought."""
        thought = await self.get_thought(thought_id)
        if not thought:
            raise ResourceNotFoundError(f"Thought {thought_id} not found")
            
        # Check if already linked
        for link in thought.links:
            if link.target_type == "commit" and link.target_id == req.commit_sha:
                return link

        new_link = ThoughtLink(
            type=ThoughtLinkType.EXPLAINS,
            target_id=req.commit_sha,
            target_type="commit",
            metadata={
                "repo_path": req.repo_path,
                "branch": req.branch
            }
        )

        event = Event(
            event_type="thought.linked",
            workspace_id=thought.workspace_id,
            data={
                "thought_id": thought_id,
                "link": new_link.model_dump()
            },
            metadata=EventMetadata(
                actor_id=actor_id,
                correlation_id=uuid.uuid4().hex
            )
        )

        await self.event_store.append(event)
        await self._apply_event(event)
        return new_link

    # --- Queries ---

    async def get_thought(self, thought_id: str) -> Optional[ThoughtCommit]:
        return self._thoughts.get(thought_id)

    async def get_thought_by_commit(self, commit_sha: str) -> Optional[ThoughtCommit]:
        if commit_sha in self._commit_index:
            return self._thoughts[self._commit_index[commit_sha]]
        return None

    async def list_thoughts(self, workspace_id: str) -> List[ThoughtCommit]:
        return [t for t in self._thoughts.values() if t.workspace_id == workspace_id]


# Singleton
_thought_service: Optional[ThoughtService] = None

def initialize_thought_service(event_store: Optional[EventStoreAdapter] = None) -> ThoughtService:
    global _thought_service
    if _thought_service is None:
        from ..adapters.persistence.event_store import InMemoryEventStore # Default fallback
        if event_store is None:
             event_store = InMemoryEventStore()
        _thought_service = ThoughtService(event_store)
    return _thought_service

def get_thought_service() -> ThoughtService:
    """FastAPI dependency to get the singleton thought service."""
    return initialize_thought_service()
