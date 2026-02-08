"""
Aegion Local Storage Adapter.

Phase 5: Local filesystem storage for development and testing.
Provides file-based storage without cloud dependencies.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import asyncio

from ...core.logging import logger


@dataclass
class LocalStorageConfig:
    """Local storage configuration."""
    base_path: str = ".aegion/storage"
    create_directories: bool = True
    use_content_addressing: bool = True
    max_file_size_mb: int = 100


class LocalStorageAdapter:
    """
    Local filesystem storage adapter.
    
    Provides development/testing storage without cloud dependencies.
    Uses content-addressed storage with SHA256 hashing.
    
    Doctrine: "Simple storage for rapid development."
    """
    
    def __init__(self, config: Optional[LocalStorageConfig] = None):
        self.config = config or LocalStorageConfig()
        self._base_path = Path(self.config.base_path)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize storage directories."""
        if self.config.create_directories:
            self._base_path.mkdir(parents=True, exist_ok=True)
            (self._base_path / "blobs").mkdir(exist_ok=True)
            (self._base_path / "metadata").mkdir(exist_ok=True)
            (self._base_path / "sessions").mkdir(exist_ok=True)
            (self._base_path / "evidence").mkdir(exist_ok=True)
        
        self._initialized = True
        logger.info(f"Local storage initialized at {self._base_path}")
    
    def _ensure_initialized(self):
        """Ensure storage is initialized."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
    
    # ========== Blob Storage ==========
    
    async def store(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store content and return the storage key.
        
        If content_addressing is enabled, returns SHA256 hash.
        Otherwise returns the provided key.
        """
        self._ensure_initialized()
        
        # Check size limit
        size_mb = len(content) / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise ValueError(f"Content exceeds max size: {size_mb:.2f}MB > {self.config.max_file_size_mb}MB")
        
        # Calculate hash for content addressing
        content_hash = hashlib.sha256(content).hexdigest()
        
        if self.config.use_content_addressing:
            storage_key = content_hash
        else:
            storage_key = key
        
        # Store blob
        blob_path = self._base_path / "blobs" / storage_key
        await asyncio.to_thread(blob_path.write_bytes, content)
        
        # Store metadata
        meta = {
            "key": key,
            "storage_key": storage_key,
            "content_hash": content_hash,
            "content_type": content_type,
            "size_bytes": len(content),
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "custom_metadata": metadata or {}
        }
        
        meta_path = self._base_path / "metadata" / f"{storage_key}.json"
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(meta, indent=2)
        )
        
        logger.debug(f"Stored {len(content)} bytes as {storage_key}")
        return storage_key
    
    async def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve content by key."""
        self._ensure_initialized()
        
        blob_path = self._base_path / "blobs" / key
        if not blob_path.exists():
            return None
        
        return await asyncio.to_thread(blob_path.read_bytes)
    
    async def retrieve_with_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve content and metadata."""
        self._ensure_initialized()
        
        content = await self.retrieve(key)
        if content is None:
            return None
        
        meta_path = self._base_path / "metadata" / f"{key}.json"
        metadata = {}
        if meta_path.exists():
            metadata = json.loads(await asyncio.to_thread(meta_path.read_text))
        
        return {
            "content": content,
            "metadata": metadata
        }
    
    async def delete(self, key: str) -> bool:
        """Delete content by key."""
        self._ensure_initialized()
        
        blob_path = self._base_path / "blobs" / key
        meta_path = self._base_path / "metadata" / f"{key}.json"
        
        deleted = False
        if blob_path.exists():
            await asyncio.to_thread(blob_path.unlink)
            deleted = True
        if meta_path.exists():
            await asyncio.to_thread(meta_path.unlink)
        
        return deleted
    
    async def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all storage keys."""
        self._ensure_initialized()
        
        blobs_path = self._base_path / "blobs"
        keys = []
        
        for path in blobs_path.iterdir():
            if path.is_file():
                key = path.name
                if prefix is None or key.startswith(prefix):
                    keys.append(key)
        
        return sorted(keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        self._ensure_initialized()
        blob_path = self._base_path / "blobs" / key
        return blob_path.exists()
    
    # ========== Session Storage ==========
    
    async def store_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Store session data as JSON."""
        self._ensure_initialized()
        
        session_path = self._base_path / "sessions" / f"{session_id}.json"
        data["_stored_at"] = datetime.now(timezone.utc).isoformat()
        
        await asyncio.to_thread(
            session_path.write_text,
            json.dumps(data, indent=2, default=str)
        )
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        self._ensure_initialized()
        
        session_path = self._base_path / "sessions" / f"{session_id}.json"
        if not session_path.exists():
            return None
        
        content = await asyncio.to_thread(session_path.read_text)
        return json.loads(content)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session data."""
        self._ensure_initialized()
        
        session_path = self._base_path / "sessions" / f"{session_id}.json"
        if session_path.exists():
            await asyncio.to_thread(session_path.unlink)
            return True
        return False
    
    async def list_sessions(self) -> List[str]:
        """List all session IDs."""
        self._ensure_initialized()
        
        sessions_path = self._base_path / "sessions"
        return [
            p.stem for p in sessions_path.iterdir()
            if p.is_file() and p.suffix == ".json"
        ]
    
    # ========== Evidence Storage ==========
    
    async def store_evidence(
        self,
        evidence_id: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> str:
        """Store evidence with metadata."""
        self._ensure_initialized()
        
        # Store content
        content_hash = await self.store(
            evidence_id,
            content,
            metadata.get("content_type", "application/octet-stream")
        )
        
        # Store evidence metadata
        evidence_meta = {
            "evidence_id": evidence_id,
            "content_hash": content_hash,
            "size_bytes": len(content),
            "stored_at": datetime.now(timezone.utc).isoformat(),
            **metadata
        }
        
        evidence_path = self._base_path / "evidence" / f"{evidence_id}.json"
        await asyncio.to_thread(
            evidence_path.write_text,
            json.dumps(evidence_meta, indent=2, default=str)
        )
        
        return content_hash
    
    async def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Get evidence with content."""
        self._ensure_initialized()
        
        evidence_path = self._base_path / "evidence" / f"{evidence_id}.json"
        if not evidence_path.exists():
            return None
        
        metadata = json.loads(await asyncio.to_thread(evidence_path.read_text))
        content_hash = metadata.get("content_hash")
        
        content = None
        if content_hash:
            content = await self.retrieve(content_hash)
        
        return {
            "metadata": metadata,
            "content": content
        }
    
    # ========== Utility Methods ==========
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        self._ensure_initialized()
        
        blobs_path = self._base_path / "blobs"
        total_size = 0
        file_count = 0
        
        for path in blobs_path.iterdir():
            if path.is_file():
                total_size += path.stat().st_size
                file_count += 1
        
        sessions_count = len(await self.list_sessions())
        
        return {
            "total_blobs": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "sessions_count": sessions_count,
            "storage_path": str(self._base_path)
        }
    
    async def clear_all(self) -> int:
        """Clear all storage (use with caution)."""
        self._ensure_initialized()
        
        deleted_count = 0
        
        for subdir in ["blobs", "metadata", "sessions", "evidence"]:
            dir_path = self._base_path / subdir
            if dir_path.exists():
                for path in dir_path.iterdir():
                    if path.is_file():
                        await asyncio.to_thread(path.unlink)
                        deleted_count += 1
        
        logger.warning(f"Cleared {deleted_count} files from local storage")
        return deleted_count


# Factory function
def create_local_storage(config: Optional[LocalStorageConfig] = None) -> LocalStorageAdapter:
    """Create local storage adapter instance."""
    return LocalStorageAdapter(config)
