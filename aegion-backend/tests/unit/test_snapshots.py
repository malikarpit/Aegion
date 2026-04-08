"""
Aegion Phase 3 Unit Tests - Snapshots.

Tests for verifiable evidence snapshots.
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from pydantic import ValidationError

from app.contracts.snapshot import (
    EvidenceSnapshot, FileSnapshot, EnvironmentSnapshot,
    SnapshotManifest, SnapshotType, SnapshotStatus,
    compute_snapshot_id, compute_manifest_hash
)
from app.services.praxis.snapshot_manager import SnapshotManager


class TestFileSnapshotContract:
    """Tests for FileSnapshot data contract."""

    def test_file_snapshot_creation(self):
        """FileSnapshot can be created with required fields."""
        snapshot = FileSnapshot(
            file_path="/path/to/file.py",
            content_hash="abc123def456",
            size_bytes=1024
        )
        
        assert snapshot.file_path == "/path/to/file.py"
        assert snapshot.content_hash == "abc123def456"
        assert snapshot.size_bytes == 1024

    def test_file_snapshot_is_immutable(self):
        """INVARIANT: FileSnapshot is frozen after creation."""
        snapshot = FileSnapshot(
            file_path="/path/to/file.py",
            content_hash="abc123",
            size_bytes=100
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            snapshot.content_hash = "modified"


class TestEnvironmentSnapshotContract:
    """Tests for EnvironmentSnapshot data contract."""

    def test_environment_snapshot_creation(self):
        """EnvironmentSnapshot can be created with required fields."""
        snapshot = EnvironmentSnapshot(
            python_version="3.9.6",
            os_name="Darwin",
            os_version="21.0.0",
            dependencies={"pydantic": "2.0.0"},
            content_hash="env-hash-123"
        )
        
        assert snapshot.python_version == "3.9.6"
        assert snapshot.dependencies["pydantic"] == "2.0.0"

    def test_environment_snapshot_is_immutable(self):
        """INVARIANT: EnvironmentSnapshot is frozen after creation."""
        snapshot = EnvironmentSnapshot(
            content_hash="hash123"
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            snapshot.python_version = "3.10.0"


class TestEvidenceSnapshotContract:
    """Tests for EvidenceSnapshot data contract."""

    def test_evidence_snapshot_creation(self):
        """EvidenceSnapshot can be created with required fields."""
        snapshot = EvidenceSnapshot(
            snapshot_id="snap-123",
            evidence_id="evd-456",
            snapshot_type=SnapshotType.INPUT,
            storage_key="snapshots/snap-123"
        )
        
        assert snapshot.snapshot_id == "snap-123"
        assert snapshot.evidence_id == "evd-456"
        assert snapshot.snapshot_type == SnapshotType.INPUT

    def test_evidence_snapshot_is_immutable(self):
        """INVARIANT: EvidenceSnapshot is frozen after creation."""
        snapshot = EvidenceSnapshot(
            snapshot_id="snap-123",
            evidence_id="evd-456",
            snapshot_type=SnapshotType.OUTPUT,
            storage_key="snapshots/snap-123"
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            snapshot.is_verified = True

    def test_snapshot_total_size_calculation(self):
        """Snapshot calculates total size from files + output."""
        file1 = FileSnapshot(
            file_path="/file1.py",
            content_hash="hash1",
            size_bytes=500
        )
        file2 = FileSnapshot(
            file_path="/file2.py",
            content_hash="hash2",
            size_bytes=300
        )
        
        snapshot = EvidenceSnapshot(
            snapshot_id="snap-123",
            evidence_id="evd-456",
            snapshot_type=SnapshotType.INPUT,
            storage_key="snapshots/snap-123",
            file_snapshots=[file1, file2],
            output_size_bytes=200
        )
        
        assert snapshot.total_files == 2
        assert snapshot.total_size_bytes == 1000  # 500 + 300 + 200


class TestSnapshotManifest:
    """Tests for SnapshotManifest data contract."""

    def test_manifest_creation(self):
        """SnapshotManifest can be created with required fields."""
        manifest = SnapshotManifest(
            evidence_id="evd-123",
            input_snapshot_ids=["inp-1", "inp-2"],
            output_snapshot_ids=["out-1"],
            manifest_hash="manifest-hash-123",
            is_reproducible=True
        )
        
        assert manifest.evidence_id == "evd-123"
        assert len(manifest.input_snapshot_ids) == 2
        assert manifest.is_reproducible is True

    def test_manifest_is_immutable(self):
        """INVARIANT: SnapshotManifest is frozen after creation."""
        manifest = SnapshotManifest(
            evidence_id="evd-123",
            manifest_hash="hash123"
        )
        
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            manifest.is_reproducible = True


class TestSnapshotUtilities:
    """Tests for snapshot utility functions."""

    def test_compute_snapshot_id_is_deterministic(self):
        """compute_snapshot_id returns same result for same inputs."""
        id1 = compute_snapshot_id("evd-1", SnapshotType.INPUT, "hash123")
        id2 = compute_snapshot_id("evd-1", SnapshotType.INPUT, "hash123")
        
        assert id1 == id2

    def test_compute_snapshot_id_differs_by_type(self):
        """compute_snapshot_id differs by snapshot type."""
        id_input = compute_snapshot_id("evd-1", SnapshotType.INPUT, "hash123")
        id_output = compute_snapshot_id("evd-1", SnapshotType.OUTPUT, "hash123")
        
        assert id_input != id_output

    def test_compute_manifest_hash_is_deterministic(self):
        """compute_manifest_hash returns same result for same inputs."""
        hash1 = compute_manifest_hash(["inp-1", "inp-2"], ["out-1"], "env-1")
        hash2 = compute_manifest_hash(["inp-1", "inp-2"], ["out-1"], "env-1")
        
        assert hash1 == hash2

    def test_compute_manifest_hash_handles_no_env(self):
        """compute_manifest_hash works without environment snapshot."""
        hash1 = compute_manifest_hash(["inp-1"], ["out-1"], None)
        
        assert hash1 is not None
        assert len(hash1) == 64  # SHA-256 hex


class TestSnapshotManager:
    """Tests for SnapshotManager service."""

    def test_capture_input_snapshot_with_files_sync(self):
        """SnapshotManager can capture input files."""
        async def run_test():
            manager = SnapshotManager(storage_port=None)
            # Create a temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write("print('hello world')")
                temp_path = f.name
            
            try:
                snapshot = await manager.capture_input_snapshot(
                    evidence_id="evd-123",
                    file_paths=[temp_path]
                )
                
                assert snapshot.snapshot_type == SnapshotType.INPUT
                assert snapshot.evidence_id == "evd-123"
                assert len(snapshot.file_snapshots) == 1
                assert snapshot.file_snapshots[0].file_path == temp_path
            finally:
                os.unlink(temp_path)
        
        asyncio.run(run_test())

    def test_capture_output_snapshot_sync(self):
        """SnapshotManager can capture output data."""
        async def run_test():
            manager = SnapshotManager(storage_port=None)
            output_data = b"Test output result: PASSED"
            
            snapshot = await manager.capture_output_snapshot(
                evidence_id="evd-456",
                output_data=output_data
            )
            
            assert snapshot.snapshot_type == SnapshotType.OUTPUT
            assert snapshot.output_hash is not None
            assert snapshot.output_size_bytes == len(output_data)
        
        asyncio.run(run_test())

    def test_capture_environment_snapshot_sync(self):
        """SnapshotManager can capture environment."""
        async def run_test():
            manager = SnapshotManager(storage_port=None)
            snapshot = await manager.capture_environment_snapshot(
                evidence_id="evd-789",
                dependencies={"pytest": "7.0.0"},
                env_vars={"PATH": "/usr/bin"}
            )
            
            assert snapshot.snapshot_type == SnapshotType.ENVIRONMENT
            assert snapshot.environment is not None
            assert snapshot.environment.dependencies.get("pytest") == "7.0.0"
        
        asyncio.run(run_test())

    def test_create_manifest_sync(self):
        """SnapshotManager can create a manifest."""
        async def run_test():
            manager = SnapshotManager(storage_port=None)
            input_snap = EvidenceSnapshot(
                snapshot_id="inp-1",
                evidence_id="evd-1",
                snapshot_type=SnapshotType.INPUT,
                storage_key="snapshots/inp-1"
            )
            output_snap = EvidenceSnapshot(
                snapshot_id="out-1",
                evidence_id="evd-1",
                snapshot_type=SnapshotType.OUTPUT,
                storage_key="snapshots/out-1"
            )
            env_snap = EvidenceSnapshot(
                snapshot_id="env-1",
                evidence_id="evd-1",
                snapshot_type=SnapshotType.ENVIRONMENT,
                storage_key="snapshots/env-1"
            )
            
            manifest = await manager.create_manifest(
                evidence_id="evd-1",
                input_snapshots=[input_snap],
                output_snapshots=[output_snap],
                env_snapshot=env_snap
            )
            
            assert manifest.evidence_id == "evd-1"
            assert manifest.is_reproducible is True
            assert manifest.manifest_hash is not None
        
        asyncio.run(run_test())
