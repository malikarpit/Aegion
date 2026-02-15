import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
from app.domain.events import Event

class EventStoreAdapter(ABC):
    @abstractmethod
    async def append(self, event: Event) -> None:
        """Append a new event to the store."""
        pass

    @abstractmethod
    async def get_all(self, workspace_id: Optional[str] = None) -> List[Event]:
        """Retrieve all events, optionally filtered by workspace."""
        pass
    
    @abstractmethod
    async def get_by_id(self, event_id: str) -> Optional[Event]:
        """Retrieve a specific event by ID."""
        pass

class InMemoryEventStore(EventStoreAdapter):
    def __init__(self):
        self._events: List[Event] = []

    async def append(self, event: Event) -> None:
        self._events.append(event)

    async def get_all(self, workspace_id: Optional[str] = None) -> List[Event]:
        if workspace_id:
            return [e for e in self._events if e.workspace_id == workspace_id]
        return list(self._events)

    async def get_by_id(self, event_id: str) -> Optional[Event]:
        for e in self._events:
            if e.event_id == event_id:
                return e
        return None

class FileEventStore(EventStoreAdapter):
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.parent.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.touch()

    async def append(self, event: Event) -> None:
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

    async def get_all(self, workspace_id: Optional[str] = None) -> List[Event]:
        events = []
        if not self.file_path.exists():
            return []
            
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = Event.model_validate_json(line)
                    if workspace_id and event.workspace_id != workspace_id:
                        continue
                    events.append(event)
                except Exception as e:
                    # In a real system, we might log this or handle corruption
                    continue
        return events

    async def get_by_id(self, event_id: str) -> Optional[Event]:
        # This is inefficient for large files, but acceptable for Local Mode v1
        # Future optimization: Indexing or SQLite
        events = await self.get_all()
        for e in events:
            if e.event_id == event_id:
                return e
        return None
