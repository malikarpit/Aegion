"""
Aegion Phase 3 End-to-End Test - "The Broken Pipeline" Scenario.

This test simulates:
1. Alice creates a proposal with test evidence + snapshots
2. Bob modifies a source file the test depends on
3. Evidence becomes stale
4. Archon blocks approval due to stale evidence
5. Charlie runs fresh tests, creates new evidence
6. Approval proceeds with fresh evidence

This validates the complete Phase 3 causality & execution flow.
"""

import pytest
import asyncio
from datetime import timezone, datetime, timedelta

from app.contracts.evidence import (
    Evidence, EvidenceClassification, EvidenceType, EvidenceSource
)
from app.contracts.dependency_node import NodeType, SourceType, DependencyNode
from app.contracts.decision_intent import DecisionTier
from app.services.archon.gates import ArchonGates, GovernanceError
from app.services.praxis import (
    ExecutionDependencyGraph, StalenessDetector, SnapshotManager
)
from app.core.security import AuthorityContext, Role


def test_broken_pipeline_scenario_sync():
    """
    E2E Scenario: "The Broken Pipeline"
    
    Doctrine: "Test X is invalid because source Y changed."
    Doctrine: "Decision A is supported by (Snapshot Hash X + Test Result Y)."
    """
    async def run_scenario():
        print("\n=== THE BROKEN PIPELINE SCENARIO ===\n")
        
        # Initialize services
        edg = ExecutionDependencyGraph()
        detector = StalenessDetector(edg)
        snapshot_manager = SnapshotManager()
        archon = ArchonGates()
        
        workspace_id = "ws-aegion-prod"
        proposal_id = "prop-database-migration"
        proposal_created_at = datetime.now(timezone.utc)
        
        # ========================================
        # ACT 1: Alice creates proposal with tests
        # ========================================
        print("ACT 1: Alice creates proposal with passing tests")
        
        # Register source files in EDG
        db_schema_source = await edg.create_source_node(
            workspace_id=workspace_id,
            source_path="/src/database/schema.py",
            source_type=SourceType.FILE,
            content_hash="schema-v1-abc123"
        )
        
        migration_source = await edg.create_source_node(
            workspace_id=workspace_id,
            source_path="/src/database/migrations/001.py",
            source_type=SourceType.FILE,
            content_hash="migration-v1-def456"
        )
        
        print(f"  - Registered source: {db_schema_source.source_path}")
        print(f"  - Registered source: {migration_source.source_path}")
        
        # Alice runs tests and captures evidence
        test_evidence_id = "evd-test-001"
        test_evidence_node = await edg.create_evidence_node(
            workspace_id=workspace_id,
            evidence_id=test_evidence_id,
            content_hash="test-results-hash-v1",
            source_ids=[db_schema_source.node_id, migration_source.node_id]
        )
        
        # Capture snapshots (simulated - would capture real files)
        print("  - Captured input snapshot for test evidence")
        print("  - Captured output snapshot (tests passed)")
        
        # Create evidence object (fresh)
        alice_evidence = Evidence(
            evidence_id=test_evidence_id,
            proposal_id=proposal_id,
            evidence_type=EvidenceType.TEST_RESULT,
            classification=EvidenceClassification.SUPPORTING,
            source=EvidenceSource.AUTOMATED,
            source_id="pytest-run-001",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            content_hash="test-results-hash-v1",
            summary="All 42 database tests passed",
            is_stale=False,
            is_reproducible=True,
            dependency_node_id=test_evidence_node.node_id
        )
        
        print(f"  - Created evidence: {alice_evidence.summary}")
        
        # Verify evidence is fresh
        is_valid, errors = archon.validate_evidence(
            proposal_id=proposal_id,
            proposal_created_at=proposal_created_at,
            evidence_list=[alice_evidence],
            tier=DecisionTier.T1
        )
        assert is_valid, f"Initial evidence should be valid: {errors}"
        print("  ✓ Evidence validated successfully")
        
        # ========================================
        # ACT 2: Bob modifies source file
        # ========================================
        print("\nACT 2: Bob modifies the database schema")
        print("  - Bob pushed: 'Added new column to users table'")
        
        # Bob changes schema.py - content hash changes
        new_schema_hash = "schema-v2-xyz789"
        
        # Propagate staleness through EDG
        staleness_report = await edg.propagate_staleness(
            source_node_id=db_schema_source.node_id,
            new_content_hash=new_schema_hash,
            reason="Bob committed changes to schema.py"
        )
        
        print(f"  - Staleness propagated to {len(staleness_report.invalidated_nodes)} nodes")
        assert test_evidence_node.node_id in staleness_report.invalidated_nodes
        print(f"  ✓ Test evidence {test_evidence_id} is now STALE")
        
        # ========================================
        # ACT 3: Archon blocks approval
        # ========================================
        print("\nACT 3: Architect tries to approve - BLOCKED")
        
        # Create stale evidence (simulating what the system would return)
        stale_evidence = Evidence(
            evidence_id=test_evidence_id,
            proposal_id=proposal_id,
            evidence_type=EvidenceType.TEST_RESULT,
            classification=EvidenceClassification.SUPPORTING,
            source=EvidenceSource.AUTOMATED,
            source_id="pytest-run-001",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            content_hash="test-results-hash-v1",
            summary="All 42 database tests passed",
            is_stale=True,  # Now marked stale
            is_reproducible=True,
            dependency_node_id=test_evidence_node.node_id
        )
        
        # Try to validate stale evidence
        is_valid, errors = archon.validate_evidence(
            proposal_id=proposal_id,
            proposal_created_at=proposal_created_at,
            evidence_list=[stale_evidence],
            tier=DecisionTier.T1
        )
        
        assert is_valid is False, "Stale evidence should block approval"
        assert any("stale" in err.lower() for err in errors)
        print(f"  ✗ Archon BLOCKED: {errors[0]}")
        print("  - Source files changed after tests were run")
        print("  - Evidence is no longer trustworthy")
        
        # ========================================
        # ACT 4: Charlie runs fresh tests
        # ========================================
        print("\nACT 4: Charlie runs fresh tests")
        
        # Charlie runs tests against the new source
        fresh_evidence_id = "evd-test-002"
        fresh_evidence_node = await edg.create_evidence_node(
            workspace_id=workspace_id,
            evidence_id=fresh_evidence_id,
            content_hash="test-results-hash-v2",
            source_ids=[db_schema_source.node_id, migration_source.node_id]
        )
        
        # Create fresh evidence
        charlie_evidence = Evidence(
            evidence_id=fresh_evidence_id,
            proposal_id=proposal_id,
            evidence_type=EvidenceType.TEST_RESULT,
            classification=EvidenceClassification.SUPPORTING,
            source=EvidenceSource.AUTOMATED,
            source_id="pytest-run-002",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            content_hash="test-results-hash-v2",
            summary="All 43 database tests passed (including new column)",
            is_stale=False,
            is_reproducible=True,
            dependency_node_id=fresh_evidence_node.node_id
        )
        
        print(f"  - Created fresh evidence: {charlie_evidence.summary}")
        
        # Verify fresh evidence passes
        is_valid, errors = archon.validate_evidence(
            proposal_id=proposal_id,
            proposal_created_at=proposal_created_at,
            evidence_list=[charlie_evidence],
            tier=DecisionTier.T1
        )
        
        assert is_valid, f"Fresh evidence should be valid: {errors}"
        print("  ✓ Fresh evidence validated successfully")
        
        # ========================================
        # ACT 5: Approval proceeds
        # ========================================
        print("\nACT 5: Approval proceeds with fresh evidence")
        
        approver = AuthorityContext.from_role(
            user_id="architect-001",
            role=Role.ARCHITECT
        )
        
        # Approval succeeds
        try:
            event = await archon.approve_proposal(
                proposal_id=proposal_id,
                proposal_status="pending",
                approver=approver,
                tier=DecisionTier.T1,
                evidence_list=[charlie_evidence],
                proposal_created_at=proposal_created_at
            )
            print(f"  ✓ Proposal APPROVED by {approver.user_id}")
            print(f"  - Audit event: {event.action}")
        except GovernanceError as e:
            pytest.fail(f"Approval should have succeeded: {e}")
        
        # ========================================
        # Epilogue: System state
        # ========================================
        print("\n=== SCENARIO COMPLETE ===")
        print("✓ Causality tracking detected source change")
        print("✓ Stale evidence blocked unsafe approval")
        print("✓ Fresh evidence allowed governance to proceed")
        print("✓ Decision is backed by verifiable, fresh evidence")
        
        return True
    
    # Run the async scenario
    result = asyncio.run(run_scenario())
    assert result is True
