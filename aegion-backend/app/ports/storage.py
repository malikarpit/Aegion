"""
Aegion Storage Port (Abstract Interface).

This is the hexagonal architecture PORT for blob/file storage.
Implementations (adapters) include:
- GCSAdapter (Phase 1+): Google Cloud Storage
- S3Adapter (AWS alternative)
- LocalFileAdapter (Development/Testing)

Doctrine: All stored artifacts are content-addressed.
Immutable files identified by their hash.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, BinaryIO
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
import hashlib


class StorageTier(str, Enum):
    """Storage tiers for cost optimization."""
    HOT = "hot"          # Frequently accessed (Standard)
    WARM = "warm"        # Infrequently accessed (Nearline)
    COLD = "cold"        # Rarely accessed (Coldline)
    ARCHIVE = "archive"  # Long-term archive (Archive)


class StoredObject(BaseModel):
    """Metadata for a stored object."""
    key: str  # Path/key in storage
    content_hash: str  # SHA-256 hash
    size_bytes: int
    content_type: str
    created_at: datetime
    tier: StorageTier
    metadata: Dict[str, Any] = {}


class StoragePort(ABC):
    """
    Abstract interface for blob storage.
    All artifacts are content-addressed for immutability.
    """
    
    @abstractmethod
    async def store(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, Any] = None,
        tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        """
        Store content. Returns metadata including content hash.
        If content with same hash exists, returns existing object.
        """
        pass
    
    @abstractmethod
    async def store_stream(
        self,
        key: str,
        stream: BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, Any] = None,
        tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        """Store content from a stream (for large files)."""
        pass
    
    @abstractmethod
    async def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve content by key. Returns None if not found."""
        pass
    
    @abstractmethod
    async def retrieve_by_hash(self, content_hash: str) -> Optional[bytes]:
        """Retrieve content by its hash (content-addressed)."""
        pass
    
    @abstractmethod
    async def get_metadata(self, key: str) -> Optional[StoredObject]:
        """Get object metadata without downloading content."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if object exists."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete object. 
        WARNING: Use sparingly - most artifacts should be immutable.
        """
        pass
    
    @abstractmethod
    async def list_prefix(
        self, prefix: str, limit: int = 1000
    ) -> list[StoredObject]:
        """List objects with a given prefix."""
        pass
    
    @abstractmethod
    async def generate_signed_url(
        self, key: str, expires_in_seconds: int = 3600
    ) -> str:
        """Generate a signed URL for temporary access."""
        pass
    
    @abstractmethod
    async def move_tier(self, key: str, new_tier: StorageTier) -> StoredObject:
        """Move object to a different storage tier."""
        pass


class ContentAddressedStore(ABC):
    """
    Content-addressed storage extension.
    Files stored by their hash, guaranteeing immutability.
    """
    
    @abstractmethod
    async def store_content_addressed(
        self,
        content: bytes,
        prefix: str = "artifacts"
    ) -> str:
        """
        Store content by its hash.
        Returns the content hash (which is the key).
        """
        pass
    
    @abstractmethod
    async def verify_integrity(self, key: str, expected_hash: str) -> bool:
        """Verify stored content matches expected hash."""
        pass


class ArtifactArchiver(ABC):
    """
    High-level interface for archiving session artifacts.
    Combines storage with metadata.
    """
    
    @abstractmethod
    async def archive_session_artifact(
        self,
        session_id: str,
        artifact_content: Dict[str, Any],
        evidence_hashes: list[str]
    ) -> str:
        """
        Archive a session artifact.
        Returns the archive key.
        """
        pass
    
    @abstractmethod
    async def retrieve_session_artifact(
        self, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve archived session artifact."""
        pass


def compute_content_hash(content: bytes) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content).hexdigest()
