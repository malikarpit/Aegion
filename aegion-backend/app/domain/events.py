from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
import ulid

def generate_ulid() -> str:
    return str(ulid.ULID())

class EventMetadata(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str
    causation_id: Optional[str] = None
    actor_id: str
    version: int = 1

class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=generate_ulid)
    event_type: str
    workspace_id: str
    data: Dict[str, Any]
    metadata: EventMetadata
    hash: Optional[str] = None
