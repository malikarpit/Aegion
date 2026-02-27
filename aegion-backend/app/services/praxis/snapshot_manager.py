"""
Aegion Snapshot Manager Service.

Creates and verifies content-addressed evidence snapshots.

Doctrine: "Decision A is supported by (Snapshot Hash X + Test Result Y)."
All evidence should be reproducible from its snapshots.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib
import json
import os

from ...contracts.snapshot import (
    EvidenceSnapshot, FileSnapshot, EnvironmentSnapshot,
    SnapshotManifest, SnapshotType, SnapshotStatus,
    SnapshotCaptureRequest, compute_snapshot_id, compute_manifest_hash
)
from ...core.logging import logger
from ...core.time import TimeAuthority


class SnapshotManager:
    """
    Creates and verifies content-addressed snapshots.
    
    Uses the existing ContentAddressedStore port for storage.
    Snapshots are immutable and identified by their content hash.
    """
    
    def __init__(self, storage_port=None):
        """
        Initialize the snapshot manager.
        
        Args:
            storage_port: Storage adapter for blob storage (optional for testing)
        """
        self.storage = storage_port
    
    async def capture_input_snapshot(
        self,
        evidence_id: str,
        file_paths: List[str],
        metadata: Dict[str, Any] = None
    ) -> EvidenceSnapshot:
        """
        Capture input files as a snapshot.
        
        Args:
            evidence_id: ID of evidence this snapshot belongs to
            file_paths: List of file paths to capture
            metadata: Optional metadata
            
        Returns:
            The created snapshot
        """
        file_snapshots = []
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning(f"File not found for snapshot: {file_path}")
                continue
            
            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Compute hash
            content_hash = hashlib.sha256(content).hexdigest()
            
            file_snapshot = FileSnapshot(
                file_path=file_path,
                content_hash=content_hash,
                size_bytes=len(content)
            )
            file_snapshots.append(file_snapshot)
            
            # Store content
            if self.storage:
                storage_key = f"snapshots/files/{content_hash}"
                await self.storage.store(
                    key=storage_key,
                    content=content,
                    content_type="application/octet-stream"
                )
        
        # Compute composite hash for all files
        all_hashes = sorted([f.content_hash for f in file_snapshots])
        composite_hash = hashlib.sha256(
            json.dumps(all_hashes).encode()
        ).hexdigest()
        
        snapshot_id = compute_snapshot_id(
            evidence_id, SnapshotType.INPUT, composite_hash
        )
        storage_key = f"snapshots/manifests/{snapshot_id}"
        
        snapshot = EvidenceSnapshot(
            snapshot_id=snapshot_id,
            evidence_id=evidence_id,
            snapshot_type=SnapshotType.INPUT,
            status=SnapshotStatus.COMPLETE,
            file_snapshots=file_snapshots,
            storage_key=storage_key,
            metadata=metadata or {}
        )
        
        # Store manifest
        if self.storage:
            await self.storage.store(
                key=storage_key,
                content=snapshot.model_dump_json().encode(),
                content_type="application/json"
            )
        
        logger.audit(
            action="INPUT_SNAPSHOT_CAPTURED",
            actor="praxis",
            target=evidence_id,
            justification=f"Captured {len(file_snapshots)} input files",
            metadata={
                "snapshot_id": snapshot_id,
                "file_count": len(file_snapshots)
            }
        )
        
        return snapshot
    
    async def capture_output_snapshot(
        self,
        evidence_id: str,
        output_data: bytes,
        metadata: Dict[str, Any] = None
    ) -> EvidenceSnapshot:
        """
        Capture execution output as a snapshot.
        
        Args:
            evidence_id: ID of evidence this snapshot belongs to
            output_data: Raw output data
            metadata: Optional metadata
            
        Returns:
            The created snapshot
        """
        output_hash = hashlib.sha256(output_data).hexdigest()
        
        snapshot_id = compute_snapshot_id(
            evidence_id, SnapshotType.OUTPUT, output_hash
        )
        storage_key = f"snapshots/outputs/{output_hash}"
        
        # Store output data
        if self.storage:
            await self.storage.store(
                key=storage_key,
                content=output_data,
                content_type="application/octet-stream"
            )
        
        snapshot = EvidenceSnapshot(
            snapshot_id=snapshot_id,
            evidence_id=evidence_id,
            snapshot_type=SnapshotType.OUTPUT,
            status=SnapshotStatus.COMPLETE,
            output_hash=output_hash,
            output_size_bytes=len(output_data),
            storage_key=storage_key,
            metadata=metadata or {}
        )
        
        # Store manifest
        if self.storage:
            manifest_key = f"snapshots/manifests/{snapshot_id}"
            await self.storage.store(
                key=manifest_key,
                content=snapshot.model_dump_json().encode(),
                content_type="application/json"
            )
        
        logger.audit(
            action="OUTPUT_SNAPSHOT_CAPTURED",
            actor="praxis",
            target=evidence_id,
            justification=f"Captured output ({len(output_data)} bytes)",
            metadata={
                "snapshot_id": snapshot_id,
                "output_hash": output_hash
            }
        )
        
        return snapshot
    
    async def capture_environment_snapshot(
        self,
        evidence_id: str,
        dependencies: Dict[str, str] = None,
        env_vars: Dict[str, str] = None,
        metadata: Dict[str, Any] = None
    ) -> EvidenceSnapshot:
        """
        Capture execution environment as a snapshot.
        
        Args:
            evidence_id: ID of evidence this snapshot belongs to
            dependencies: Package name -> version mapping
            env_vars: Environment variable name -> value mapping
            metadata: Optional metadata
            
        Returns:
            The created snapshot
        """
        import sys
        import platform
        
        env_data = {
            "python_version": sys.version,
            "os_name": platform.system(),
            "os_version": platform.release(),
            "dependencies": dependencies or {},
            "environment_vars": env_vars or {}
        }
        
        env_hash = hashlib.sha256(
            json.dumps(env_data, sort_keys=True).encode()
        ).hexdigest()
        
        env_snapshot = EnvironmentSnapshot(
            python_version=sys.version,
            os_name=platform.system(),
            os_version=platform.release(),
            dependencies=dependencies or {},
            environment_vars=env_vars or {},
            content_hash=env_hash
        )
        
        snapshot_id = compute_snapshot_id(
            evidence_id, SnapshotType.ENVIRONMENT, env_hash
        )
        storage_key = f"snapshots/environments/{env_hash}"
        
        snapshot = EvidenceSnapshot(
            snapshot_id=snapshot_id,
            evidence_id=evidence_id,
            snapshot_type=SnapshotType.ENVIRONMENT,
            status=SnapshotStatus.COMPLETE,
            environment=env_snapshot,
            storage_key=storage_key,
            metadata=metadata or {}
        )
        
        # Store snapshot
        if self.storage:
            await self.storage.store(
                key=storage_key,
                content=snapshot.model_dump_json().encode(),
                content_type="application/json"
            )
        
        logger.audit(
            action="ENVIRONMENT_SNAPSHOT_CAPTURED",
            actor="praxis",
            target=evidence_id,
            justification="Captured execution environment",
            metadata={"snapshot_id": snapshot_id}
        )
        
        return snapshot
    
    async def verify_snapshot_integrity(
        self,
        snapshot_id: str
    ) -> bool:
        """
        Verify that a snapshot's content matches its hash.
        
        Args:
            snapshot_id: ID of snapshot to verify
            
        Returns:
            True if integrity is verified
        """
        if not self.storage:
            return True  # No storage, assume valid
        
        manifest_key = f"snapshots/manifests/{snapshot_id}"
        manifest_data = await self.storage.retrieve(manifest_key)
        
        if not manifest_data:
            return False
        
        snapshot = EvidenceSnapshot.model_validate_json(manifest_data)
        
        # Verify file snapshots
        for file_snap in snapshot.file_snapshots:
            file_key = f"snapshots/files/{file_snap.content_hash}"
            content = await self.storage.retrieve(file_key)
            
            if not content:
                logger.warning(f"Missing file content: {file_snap.content_hash}")
                return False
            
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != file_snap.content_hash:
                logger.warning(f"Hash mismatch for {file_snap.file_path}")
                return False
        
        # Verify output snapshot
        if snapshot.output_hash:
            output_key = f"snapshots/outputs/{snapshot.output_hash}"
            content = await self.storage.retrieve(output_key)
            
            if not content:
                return False
            
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != snapshot.output_hash:
                return False
        
        return True
    
    async def get_snapshots_for_evidence(
        self,
        evidence_id: str
    ) -> Dict[SnapshotType, List[EvidenceSnapshot]]:
        """
        Get all snapshots for a piece of evidence.
        
        Args:
            evidence_id: Evidence ID to query
            
        Returns:
            Dict mapping snapshot type to list of snapshots
        """
        result: Dict[SnapshotType, List[EvidenceSnapshot]] = {
            SnapshotType.INPUT: [],
            SnapshotType.OUTPUT: [],
            SnapshotType.ENVIRONMENT: []
        }

        # Scan storage directory for snapshots matching this evidence_id
        storage_dir = os.path.join("data", "snapshots", evidence_id)
        if not os.path.exists(storage_dir):
            return result

        try:
            for filename in os.listdir(storage_dir):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(storage_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    snapshot = EvidenceSnapshot(**data)
                    snap_type = SnapshotType(data.get("snapshot_type", "input"))
                    result[snap_type].append(snapshot)
                except Exception as e:
                    logger.warning(f"Failed to load snapshot {filepath}: {e}")
        except Exception as e:
            logger.warning(f"Error scanning snapshots for {evidence_id}: {e}")

        return result
    
    async def create_manifest(
        self,
        evidence_id: str,
        input_snapshots: List[EvidenceSnapshot],
        output_snapshots: List[EvidenceSnapshot],
        env_snapshot: Optional[EvidenceSnapshot] = None
    ) -> SnapshotManifest:
        """
        Create a manifest of all snapshots for evidence.
        
        Args:
            evidence_id: Evidence ID
            input_snapshots: List of input snapshots
            output_snapshots: List of output snapshots
            env_snapshot: Optional environment snapshot
            
        Returns:
            The manifest
        """
        input_ids = [s.snapshot_id for s in input_snapshots]
        output_ids = [s.snapshot_id for s in output_snapshots]
        env_id = env_snapshot.snapshot_id if env_snapshot else None
        
        manifest_hash = compute_manifest_hash(input_ids, output_ids, env_id)
        
        # Determine reproducibility
        is_reproducible = (
            len(input_snapshots) > 0 and
            len(output_snapshots) > 0 and
            env_snapshot is not None
        )
        
        manifest = SnapshotManifest(
            evidence_id=evidence_id,
            input_snapshot_ids=input_ids,
            output_snapshot_ids=output_ids,
            environment_snapshot_id=env_id,
            manifest_hash=manifest_hash,
            is_reproducible=is_reproducible
        )
        
        return manifest
