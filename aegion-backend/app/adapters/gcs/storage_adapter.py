"""
Aegion GCS Storage Adapter.

Implements StoragePort and ContentAddressedStore for Google Cloud Storage.
Content-addressed storage with SHA256 keys for immutability.

Doctrine: "Memory is governed, not generated."
All artifacts are immutable and content-addressable.
"""

from typing import Optional, Dict, Any, BinaryIO, List
from datetime import timezone, datetime, timedelta
import hashlib
import io

from google.cloud import storage
from google.cloud.exceptions import NotFound

from ...core.config import settings
from ...core.logging import logger
from ...ports.storage import (
    StoragePort, ContentAddressedStore,
    StoredObject, StorageTier, compute_content_hash
)


# Map our tiers to GCS storage classes
TIER_TO_GCS_CLASS = {
    StorageTier.HOT: "STANDARD",
    StorageTier.WARM: "NEARLINE",
    StorageTier.COLD: "COLDLINE",
    StorageTier.ARCHIVE: "ARCHIVE",
}

GCS_CLASS_TO_TIER = {v: k for k, v in TIER_TO_GCS_CLASS.items()}


class GCSStorageAdapter(StoragePort, ContentAddressedStore):
    """
    Google Cloud Storage adapter.
    Implements both StoragePort and ContentAddressedStore interfaces.
    """
    
    def __init__(
        self,
        bucket_name: str = None,
        project_id: str = None
    ):
        """
        Initialize GCS adapter.
        
        Args:
            bucket_name: GCS bucket name (defaults to settings.gcs_bucket)
            project_id: GCP project ID (defaults to settings.gcp_project)
        """
        self._bucket_name = bucket_name or getattr(settings, 'gcs_bucket', 'aegion-artifacts')
        self._project_id = project_id or getattr(settings, 'gcp_project', None)
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        
        # Content hash to key mapping for content-addressed retrieval
        self._hash_index: Dict[str, str] = {}
    
    @property
    def client(self) -> storage.Client:
        """Lazy-load GCS client."""
        if self._client is None:
            self._client = storage.Client(project=self._project_id)
        return self._client
    
    @property
    def bucket(self) -> storage.Bucket:
        """Lazy-load GCS bucket."""
        if self._bucket is None:
            self._bucket = self.client.bucket(self._bucket_name)
        return self._bucket
    
    async def store(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, Any] = None,
        tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        """
        Store content in GCS.
        
        Args:
            key: Object key/path
            content: Binary content
            content_type: MIME type
            metadata: Custom metadata
            tier: Storage tier
            
        Returns:
            StoredObject with metadata
        """
        content_hash = compute_content_hash(content)
        blob = self.bucket.blob(key)
        
        # Set storage class
        blob.storage_class = TIER_TO_GCS_CLASS.get(tier, "STANDARD")
        
        # Set metadata including content hash
        custom_metadata = metadata or {}
        custom_metadata["content_hash"] = content_hash
        blob.metadata = custom_metadata
        
        # Upload
        blob.upload_from_string(content, content_type=content_type)
        
        # Update hash index
        self._hash_index[content_hash] = key
        
        stored = StoredObject(
            key=key,
            content_hash=content_hash,
            size_bytes=len(content),
            content_type=content_type,
            created_at=datetime.now(timezone.utc),
            tier=tier,
            metadata=custom_metadata
        )
        
        logger.info(
            f"Stored object: key={key}, hash={content_hash[:16]}..., size={len(content)}"
        )
        
        return stored
    
    async def store_stream(
        self,
        key: str,
        stream: BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, Any] = None,
        tier: StorageTier = StorageTier.HOT
    ) -> StoredObject:
        """Store content from stream."""
        # Read stream to get hash (GCS requires knowing content for hash)
        content = stream.read()
        return await self.store(key, content, content_type, metadata, tier)
    
    async def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve content by key."""
        try:
            blob = self.bucket.blob(key)
            content = blob.download_as_bytes()
            return content
        except NotFound:
            logger.debug(f"Object not found: {key}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving {key}: {e}")
            return None
    
    async def retrieve_by_hash(self, content_hash: str) -> Optional[bytes]:
        """Retrieve content by its hash."""
        # Check local cache first
        if content_hash in self._hash_index:
            return await self.retrieve(self._hash_index[content_hash])
        
        # Search by metadata (expensive - use sparingly)
        # For production, consider a separate index in Firestore
        prefix = "artifacts/"
        blobs = self.bucket.list_blobs(prefix=prefix)
        
        for blob in blobs:
            blob.reload()  # Load metadata
            if blob.metadata and blob.metadata.get("content_hash") == content_hash:
                self._hash_index[content_hash] = blob.name
                return blob.download_as_bytes()
        
        return None
    
    async def get_metadata(self, key: str) -> Optional[StoredObject]:
        """Get object metadata without downloading."""
        try:
            blob = self.bucket.blob(key)
            blob.reload()
            
            # Map storage class back to tier
            gcs_class = blob.storage_class or "STANDARD"
            tier = GCS_CLASS_TO_TIER.get(gcs_class, StorageTier.HOT)
            
            return StoredObject(
                key=key,
                content_hash=blob.metadata.get("content_hash", "") if blob.metadata else "",
                size_bytes=blob.size or 0,
                content_type=blob.content_type or "application/octet-stream",
                created_at=blob.time_created or datetime.now(timezone.utc),
                tier=tier,
                metadata=blob.metadata or {}
            )
        except NotFound:
            return None
    
    async def exists(self, key: str) -> bool:
        """Check if object exists."""
        blob = self.bucket.blob(key)
        return blob.exists()
    
    async def delete(self, key: str) -> bool:
        """
        Delete object.
        WARNING: Use sparingly - most artifacts should be immutable.
        """
        try:
            blob = self.bucket.blob(key)
            blob.delete()
            
            # Remove from hash index
            for h, k in list(self._hash_index.items()):
                if k == key:
                    del self._hash_index[h]
            
            logger.audit(
                action="ARTIFACT_DELETED",
                actor="system",
                target=key,
                justification="Explicit deletion requested"
            )
            return True
        except NotFound:
            return False
    
    async def list_prefix(
        self, prefix: str, limit: int = 1000
    ) -> List[StoredObject]:
        """List objects with a given prefix."""
        blobs = self.bucket.list_blobs(prefix=prefix, max_results=limit)
        
        objects = []
        for blob in blobs:
            blob.reload()
            gcs_class = blob.storage_class or "STANDARD"
            tier = GCS_CLASS_TO_TIER.get(gcs_class, StorageTier.HOT)
            
            objects.append(StoredObject(
                key=blob.name,
                content_hash=blob.metadata.get("content_hash", "") if blob.metadata else "",
                size_bytes=blob.size or 0,
                content_type=blob.content_type or "application/octet-stream",
                created_at=blob.time_created or datetime.now(timezone.utc),
                tier=tier,
                metadata=blob.metadata or {}
            ))
        
        return objects
    
    async def generate_signed_url(
        self, key: str, expires_in_seconds: int = 3600
    ) -> str:
        """Generate a signed URL for temporary access."""
        blob = self.bucket.blob(key)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in_seconds),
            method="GET"
        )
        return url
    
    async def move_tier(self, key: str, new_tier: StorageTier) -> StoredObject:
        """Move object to a different storage tier."""
        blob = self.bucket.blob(key)
        new_class = TIER_TO_GCS_CLASS.get(new_tier, "STANDARD")
        blob.update_storage_class(new_class)
        
        return await self.get_metadata(key)
    
    # ========== ContentAddressedStore Interface ==========
    
    async def store_content_addressed(
        self,
        content: bytes,
        prefix: str = "artifacts"
    ) -> str:
        """
        Store content by its hash.
        Returns the content hash (which becomes part of the key).
        """
        content_hash = compute_content_hash(content)
        key = f"{prefix}/{content_hash[:2]}/{content_hash}"
        
        # Check if already exists (deduplication)
        if await self.exists(key):
            logger.debug(f"Content already exists: {content_hash[:16]}...")
            return content_hash
        
        await self.store(
            key=key,
            content=content,
            content_type="application/octet-stream",
            metadata={"content_addressed": "true"}
        )
        
        return content_hash
    
    async def verify_integrity(self, key: str, expected_hash: str) -> bool:
        """Verify stored content matches expected hash."""
        content = await self.retrieve(key)
        if content is None:
            return False
        
        actual_hash = compute_content_hash(content)
        return actual_hash == expected_hash


# Singleton instance
_gcs_adapter: Optional[GCSStorageAdapter] = None


def get_gcs_storage() -> GCSStorageAdapter:
    """Get the GCS storage adapter singleton."""
    global _gcs_adapter
    if _gcs_adapter is None:
        _gcs_adapter = GCSStorageAdapter()
    return _gcs_adapter
