"""
Aegion Chronos Artifact Immutability.

Manifest hashing and signature verification for tamper-resistant artifacts.
Improves audit credibility and ensures data integrity.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import base64
from pathlib import Path

from ...core.logging import logger


@dataclass
class ArtifactManifest:
    """
    Manifest for an immutable artifact.
    Contains hash and signature for verification.
    """
    artifact_id: str
    artifact_type: str
    content_hash: str  # SHA256 of content
    metadata_hash: str  # SHA256 of metadata
    combined_hash: str  # SHA256 of content_hash + metadata_hash
    signature: str  # HMAC signature
    created_at: str
    created_by: str
    version: int = 1
    parent_hash: Optional[str] = None  # For versioned artifacts
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "content_hash": self.content_hash,
            "metadata_hash": self.metadata_hash,
            "combined_hash": self.combined_hash,
            "signature": self.signature,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "version": self.version,
            "parent_hash": self.parent_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactManifest":
        return cls(**data)


class ChronosIntegrityService:
    """
    Cryptographic integrity service for Chronos artifacts.
    
    Provides:
    - Content hashing (SHA256)
    - Manifest generation
    - HMAC signing
    - Verification on read
    - Tamper detection
    """
    
    def __init__(self, signing_key: Optional[str] = None):
        """
        Initialize with signing key.
        In production, key should come from secure key management.
        """
        self._signing_key = (signing_key or "aegion-chronos-default-key").encode('utf-8')
        self._manifests: Dict[str, ArtifactManifest] = {}
    
    # ========== Hashing ==========
    
    def hash_content(self, content: bytes) -> str:
        """Generate SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()
    
    def hash_metadata(self, metadata: Dict[str, Any]) -> str:
        """Generate SHA256 hash of metadata."""
        # Sort keys for deterministic hashing
        canonical = json.dumps(metadata, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def hash_combined(self, content_hash: str, metadata_hash: str) -> str:
        """Generate combined hash."""
        combined = f"{content_hash}:{metadata_hash}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    # ========== Signing ==========
    
    def sign_manifest(self, combined_hash: str) -> str:
        """Generate HMAC signature for manifest."""
        signature = hmac.new(
            self._signing_key,
            combined_hash.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def verify_signature(self, combined_hash: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self.sign_manifest(combined_hash)
        return hmac.compare_digest(expected, signature)
    
    # ========== Manifest Operations ==========
    
    def create_manifest(
        self,
        artifact_id: str,
        artifact_type: str,
        content: bytes,
        metadata: Dict[str, Any],
        created_by: str,
        parent_hash: Optional[str] = None
    ) -> ArtifactManifest:
        """Create a signed manifest for an artifact."""
        
        # Calculate hashes
        content_hash = self.hash_content(content)
        metadata_hash = self.hash_metadata(metadata)
        combined_hash = self.hash_combined(content_hash, metadata_hash)
        
        # Sign
        signature = self.sign_manifest(combined_hash)
        
        # Determine version
        version = 1
        if parent_hash and artifact_id in self._manifests:
            version = self._manifests[artifact_id].version + 1
        
        manifest = ArtifactManifest(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            metadata_hash=metadata_hash,
            combined_hash=combined_hash,
            signature=signature,
            created_at=datetime.now(timezone.utc).isoformat() + "Z",
            created_by=created_by,
            version=version,
            parent_hash=parent_hash
        )
        
        self._manifests[artifact_id] = manifest
        
        logger.info(
            f"Created manifest for artifact {artifact_id} "
            f"(v{version}, hash={combined_hash[:16]}...)"
        )
        
        return manifest
    
    def verify_artifact(
        self,
        artifact_id: str,
        content: bytes,
        metadata: Dict[str, Any],
        manifest: ArtifactManifest
    ) -> Dict[str, Any]:
        """
        Verify artifact integrity on read.
        
        Returns verification result with details.
        """
        result = {
            "artifact_id": artifact_id,
            "verified": False,
            "content_valid": False,
            "metadata_valid": False,
            "signature_valid": False,
            "errors": []
        }
        
        # Verify content hash
        actual_content_hash = self.hash_content(content)
        result["content_valid"] = actual_content_hash == manifest.content_hash
        if not result["content_valid"]:
            result["errors"].append("Content hash mismatch - possible tampering")
        
        # Verify metadata hash
        actual_metadata_hash = self.hash_metadata(metadata)
        result["metadata_valid"] = actual_metadata_hash == manifest.metadata_hash
        if not result["metadata_valid"]:
            result["errors"].append("Metadata hash mismatch - possible tampering")
        
        # Verify combined hash
        actual_combined = self.hash_combined(actual_content_hash, actual_metadata_hash)
        combined_valid = actual_combined == manifest.combined_hash
        if not combined_valid:
            result["errors"].append("Combined hash mismatch")
        
        # Verify signature
        result["signature_valid"] = self.verify_signature(
            manifest.combined_hash,
            manifest.signature
        )
        if not result["signature_valid"]:
            result["errors"].append("Signature verification failed")
        
        # Overall verification
        result["verified"] = (
            result["content_valid"] and
            result["metadata_valid"] and
            result["signature_valid"]
        )
        
        if result["verified"]:
            logger.debug(f"Artifact {artifact_id} verified successfully")
        else:
            logger.warning(
                f"Artifact {artifact_id} verification FAILED: {result['errors']}"
            )
        
        return result
    
    def get_manifest(self, artifact_id: str) -> Optional[ArtifactManifest]:
        """Get manifest for an artifact."""
        return self._manifests.get(artifact_id)
    
    def verify_chain(self, artifact_id: str) -> Dict[str, Any]:
        """
        Verify the complete version chain of an artifact.
        Ensures no version has been tampered with.
        """
        manifest = self._manifests.get(artifact_id)
        if not manifest:
            return {"valid": False, "error": "Manifest not found"}
        
        chain = []
        current = manifest
        
        while current:
            chain.append({
                "version": current.version,
                "hash": current.combined_hash,
                "signature_valid": self.verify_signature(
                    current.combined_hash,
                    current.signature
                )
            })
            
            if current.parent_hash:
                # Find parent manifest
                parent = None
                for m in self._manifests.values():
                    if m.combined_hash == current.parent_hash:
                        parent = m
                        break
                current = parent
            else:
                current = None
        
        all_valid = all(entry["signature_valid"] for entry in chain)
        
        return {
            "artifact_id": artifact_id,
            "chain_length": len(chain),
            "all_valid": all_valid,
            "chain": chain
        }


# ========== Wrapper for Chronos Storage ==========

class ImmutableArtifactStore:
    """
    Immutable artifact storage with verification-on-read.
    Wraps underlying storage with integrity verification.
    """
    
    def __init__(self, storage_path: str = ".aegion/artifacts"):
        self._storage_path = Path(storage_path)
        self._integrity = ChronosIntegrityService()
        self._storage_path.mkdir(parents=True, exist_ok=True)
    
    async def store(
        self,
        artifact_id: str,
        artifact_type: str,
        content: bytes,
        metadata: Dict[str, Any],
        created_by: str
    ) -> ArtifactManifest:
        """Store artifact with manifest."""
        
        # Check for existing version
        parent_hash = None
        existing = self._integrity.get_manifest(artifact_id)
        if existing:
            parent_hash = existing.combined_hash
        
        # Create manifest
        manifest = self._integrity.create_manifest(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content=content,
            metadata=metadata,
            created_by=created_by,
            parent_hash=parent_hash
        )
        
        # Store content
        artifact_dir = self._storage_path / artifact_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        content_path = artifact_dir / f"v{manifest.version}.content"
        content_path.write_bytes(content)
        
        metadata_path = artifact_dir / f"v{manifest.version}.metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str))
        
        manifest_path = artifact_dir / f"v{manifest.version}.manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))
        
        return manifest
    
    async def retrieve(self, artifact_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve artifact with verification.
        Returns None if artifact not found or verification fails.
        """
        artifact_dir = self._storage_path / artifact_id
        if not artifact_dir.exists():
            return None
        
        # Find version
        if version is None:
            # Get latest version
            manifest_files = list(artifact_dir.glob("*.manifest.json"))
            if not manifest_files:
                return None
            version = max(
                int(f.stem.split('.')[0][1:])
                for f in manifest_files
            )
        
        # Load files
        content_path = artifact_dir / f"v{version}.content"
        metadata_path = artifact_dir / f"v{version}.metadata.json"
        manifest_path = artifact_dir / f"v{version}.manifest.json"
        
        if not all(p.exists() for p in [content_path, metadata_path, manifest_path]):
            return None
        
        content = content_path.read_bytes()
        metadata = json.loads(metadata_path.read_text())
        manifest_data = json.loads(manifest_path.read_text())
        manifest = ArtifactManifest.from_dict(manifest_data)
        
        # Verify on read
        verification = self._integrity.verify_artifact(
            artifact_id, content, metadata, manifest
        )
        
        if not verification["verified"]:
            logger.error(f"TAMPER DETECTED: Artifact {artifact_id} v{version}")
            return {
                "artifact_id": artifact_id,
                "version": version,
                "tampered": True,
                "verification": verification,
                "content": None,
                "metadata": None
            }
        
        return {
            "artifact_id": artifact_id,
            "version": version,
            "tampered": False,
            "verification": verification,
            "content": content,
            "metadata": metadata,
            "manifest": manifest.to_dict()
        }
    
    async def get_audit_trail(self, artifact_id: str) -> Dict[str, Any]:
        """Get complete audit trail for an artifact."""
        return self._integrity.verify_chain(artifact_id)


# Singleton
_artifact_store: Optional[ImmutableArtifactStore] = None


def get_immutable_store() -> ImmutableArtifactStore:
    """Get the immutable artifact store singleton."""
    global _artifact_store
    if _artifact_store is None:
        _artifact_store = ImmutableArtifactStore()
    return _artifact_store
