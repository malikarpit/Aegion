"""
Aegion Edit Attribution Service.

Tags decisions and proposals with author information.

Doctrine: "Every decision has an author."
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from ...core.logging import logger


class AttributedEdit(BaseModel):
    """A single attributed edit."""
    edit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    author_id: str
    entity_type: str  # "proposal", "decision", "evidence"
    entity_id: str
    field_path: str  # e.g., "rationale", "claim", "metadata.priority"
    old_value: Optional[str] = None
    new_value: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class EditHistory(BaseModel):
    """History of edits for an entity."""
    entity_type: str
    entity_id: str
    edits: List[AttributedEdit] = Field(default_factory=list)
    current_author: Optional[str] = None  # Last editor
    original_author: Optional[str] = None  # First creator


class EditAttribution:
    """
    Tracks authorship of edits to governance entities.
    
    Provides:
    - Full edit history per entity
    - Conflict detection (concurrent edits)
    - Author trail for audit
    """
    
    def __init__(self):
        # (entity_type, entity_id) -> EditHistory
        self._histories: Dict[tuple, EditHistory] = {}
    
    def _key(self, entity_type: str, entity_id: str) -> tuple:
        return (entity_type, entity_id)
    
    def record_creation(
        self,
        entity_type: str,
        entity_id: str,
        author_id: str,
        content: str,
        session_id: str = None
    ) -> AttributedEdit:
        """Record entity creation."""
        key = self._key(entity_type, entity_id)
        
        edit = AttributedEdit(
            author_id=author_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_path="*",  # Whole entity
            old_value=None,
            new_value=content,
            session_id=session_id
        )
        
        history = EditHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            edits=[edit],
            current_author=author_id,
            original_author=author_id
        )
        
        self._histories[key] = history
        
        logger.info(
            f"Entity created by {author_id}",
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        return edit
    
    def record_edit(
        self,
        entity_type: str,
        entity_id: str,
        author_id: str,
        field_path: str,
        old_value: str,
        new_value: str,
        session_id: str = None
    ) -> Optional[AttributedEdit]:
        """Record an edit to an entity."""
        key = self._key(entity_type, entity_id)
        
        history = self._histories.get(key)
        if not history:
            # Entity doesn't exist, create implicit history
            history = EditHistory(
                entity_type=entity_type,
                entity_id=entity_id,
                original_author=author_id
            )
            self._histories[key] = history
        
        edit = AttributedEdit(
            author_id=author_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            session_id=session_id
        )
        
        history.edits.append(edit)
        history.current_author = author_id
        
        logger.info(
            f"Entity edited by {author_id}",
            entity_type=entity_type,
            entity_id=entity_id,
            field_path=field_path
        )
        
        return edit
    
    def get_history(
        self, 
        entity_type: str, 
        entity_id: str
    ) -> Optional[EditHistory]:
        """Get full edit history for entity."""
        return self._histories.get(self._key(entity_type, entity_id))
    
    def get_authors(
        self, 
        entity_type: str, 
        entity_id: str
    ) -> List[str]:
        """Get all unique authors who edited entity."""
        history = self.get_history(entity_type, entity_id)
        if not history:
            return []
        return list(set(edit.author_id for edit in history.edits))
    
    def get_original_author(
        self, 
        entity_type: str, 
        entity_id: str
    ) -> Optional[str]:
        """Get the original creator of entity."""
        history = self.get_history(entity_type, entity_id)
        return history.original_author if history else None
    
    def get_edits_by_author(
        self, 
        author_id: str,
        since: datetime = None
    ) -> List[AttributedEdit]:
        """Get all edits by a specific author."""
        edits = []
        for history in self._histories.values():
            for edit in history.edits:
                if edit.author_id == author_id:
                    if since is None or edit.timestamp >= since:
                        edits.append(edit)
        return sorted(edits, key=lambda e: e.timestamp, reverse=True)
    
    def detect_conflict(
        self,
        entity_type: str,
        entity_id: str,
        field_path: str,
        expected_value: str
    ) -> bool:
        """
        Check if there's a conflict (concurrent edit).
        Returns True if current value differs from expected.
        """
        history = self.get_history(entity_type, entity_id)
        if not history or not history.edits:
            return False
        
        # Find last edit to this field
        for edit in reversed(history.edits):
            if edit.field_path == field_path or edit.field_path == "*":
                return edit.new_value != expected_value
        
        return False


# Singleton instance
_edit_attribution: Optional[EditAttribution] = None


def get_edit_attribution() -> EditAttribution:
    """Get edit attribution service singleton."""
    global _edit_attribution
    if _edit_attribution is None:
        _edit_attribution = EditAttribution()
    return _edit_attribution
