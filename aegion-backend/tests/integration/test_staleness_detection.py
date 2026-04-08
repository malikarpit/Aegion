"""
Aegion Phase 3 Integration Tests - Staleness Detection.

Tests that stale evidence blocks approval through Archon gates.
"""

import pytest
import asyncio
from datetime import datetime, timezone

from app.contracts.evidence import (
    Evidence, EvidenceClassification, EvidenceType, EvidenceSource
)
from app.contracts.dependency_node import NodeType, SourceType
from app.contracts.decision_intent import DecisionTier
from app.services.archon.gates import ArchonGates, GovernanceError
from app.services.praxis import ExecutionDependencyGraph, StalenessDetector
from app.core.security import AuthorityContext


class TestStalenessBlocksApproval:
    """Tests that stale evidence properly blocks approval."""

    def test_stale_evidence_blocked_by_archon(self):
        """INVARIANT: Stale evidence cannot support approval."""
        # Create Archon gates
        archon = ArchonGates()
        
        # Create stale evidence
        stale_evidence = Evidence(
            evidence_id="evd-stale-001",
            proposal_id="prop-001",
            evidence_type=EvidenceType.TEST_RESULT,
            classification=EvidenceClassification.SUPPORTING,
            source=EvidenceSource.AUTOMATED,
            source_id="test-run-001",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            content_hash="abc123",
            summary="Test passed (but stale)",
            is_stale=True  # KEY: This evidence is stale
        )
        
        # Try to validate
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-001",
            proposal_created_at=datetime.now(timezone.utc),
            evidence_list=[stale_evidence],
            tier=DecisionTier.T1
        )
        
        # Should fail due to stale evidence
        assert is_valid is False
        assert any("stale" in err.lower() for err in errors)

    def test_fresh_evidence_allowed(self):
        """Fresh evidence passes validation."""
        archon = ArchonGates()
        
        # Set proposal time FIRST (evidence must be collected after proposal)
        from datetime import timedelta
        proposal_created_at = datetime.now(timezone.utc)
        
        # Create fresh evidence (collected after proposal)
        fresh_evidence = Evidence(
            evidence_id="evd-fresh-001",
            proposal_id="prop-002",
            evidence_type=EvidenceType.TEST_RESULT,
            classification=EvidenceClassification.SUPPORTING,
            source=EvidenceSource.AUTOMATED,
            source_id="test-run-002",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc) + timedelta(seconds=1),  # After proposal
            content_hash="def456",
            summary="Test passed (fresh)",
            is_stale=False  # KEY: This evidence is fresh
        )
        
        # Should pass validation
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-002",
            proposal_created_at=proposal_created_at,
            evidence_list=[fresh_evidence],
            tier=DecisionTier.T1
        )
        
        assert is_valid is True, f"Expected valid, got errors: {errors}"
        assert len(errors) == 0

    def test_mixed_evidence_blocked_if_any_stale(self):
        """If any evidence is stale, validation fails."""
        archon = ArchonGates()
        now = datetime.now(timezone.utc)
        
        evidence_list = [
            Evidence(
                evidence_id="evd-fresh",
                proposal_id="prop-003",
                evidence_type=EvidenceType.TEST_RESULT,
                classification=EvidenceClassification.SUPPORTING,
                source=EvidenceSource.AUTOMATED,
                source_id="run-1",
                created_at=now,
                collected_at=now,
                content_hash="hash1",
                summary="Fresh test",
                is_stale=False
            ),
            Evidence(
                evidence_id="evd-stale",
                proposal_id="prop-003",
                evidence_type=EvidenceType.TEST_RESULT,
                classification=EvidenceClassification.SUPPORTING,
                source=EvidenceSource.AUTOMATED,
                source_id="run-2",
                created_at=now,
                collected_at=now,
                content_hash="hash2",
                summary="Stale test",
                is_stale=True  # One stale evidence
            )
        ]
        
        is_valid, errors = archon.validate_evidence(
            proposal_id="prop-003",
            proposal_created_at=now,
            evidence_list=evidence_list,
            tier=DecisionTier.T1
        )
        
        # Should fail because of the stale evidence
        assert is_valid is False


class TestStalenessPropagation:
    """Tests that staleness propagates through the EDG."""

    def test_source_change_invalidates_evidence_sync(self):
        """When source changes, downstream evidence becomes stale."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            
            # Create source node
            source = await edg.create_source_node(
                workspace_id="ws-test",
                source_path="/src/module.py",
                source_type=SourceType.FILE,
                content_hash="original-hash"
            )
            
            # Create evidence that depends on source
            evidence = await edg.create_evidence_node(
                workspace_id="ws-test",
                evidence_id="evd-123",
                content_hash="evidence-hash",
                source_ids=[source.node_id]
            )
            
            # Verify not stale initially
            evd_node = await edg.get_node(evidence.node_id)
            assert evd_node.is_stale is False
            
            # Source changes
            report = await edg.propagate_staleness(
                source.node_id, "new-hash"
            )
            
            # Evidence should now be stale
            assert evidence.node_id in report.invalidated_nodes
            
            # Verify node is marked stale
            evd_node = await edg.get_node(evidence.node_id)
            assert evd_node.is_stale is True
        
        asyncio.run(run_test())

    def test_cascade_through_multiple_levels_sync(self):
        """Staleness cascades through multiple dependency levels."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            from app.contracts.dependency_node import DependencyNode, EdgeType
            
            # Create: source -> evidence -> decision
            source = await edg.create_source_node(
                workspace_id="ws-test",
                source_path="/src/deep.py",
                source_type=SourceType.FILE,
                content_hash="src-hash"
            )
            
            evidence = await edg.create_evidence_node(
                workspace_id="ws-test",
                evidence_id="evd-cascade",
                content_hash="evd-hash",
                source_ids=[source.node_id]
            )
            
            decision = DependencyNode(
                node_id="dec-001",
                node_type=NodeType.DECISION,
                content_hash="dec-hash",
                workspace_id="ws-test"
            )
            await edg.add_node(decision)
            await edg.add_edge(evidence.node_id, "dec-001", EdgeType.SUPPORTS)
            
            # Propagate from source
            report = await edg.propagate_staleness(source.node_id, "changed")
            
            # Both evidence and decision should be invalidated
            assert evidence.node_id in report.invalidated_nodes
            assert "dec-001" in report.invalidated_nodes
            assert "dec-001" in report.affected_decisions
        
        asyncio.run(run_test())


class TestStalenessDetector:
    """Tests for the StalenessDetector service."""

    def test_check_evidence_freshness_sync(self):
        """StalenessDetector correctly checks evidence freshness."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            detector = StalenessDetector(edg)
            
            # Create fresh evidence node
            evidence = await edg.create_evidence_node(
                workspace_id="ws-test",
                evidence_id="evd-check",
                content_hash="check-hash",
                source_ids=[]
            )
            
            # Should be fresh
            is_fresh, reason = await detector.check_evidence_freshness("evd-check")
            assert is_fresh is True
            assert reason is None
        
        asyncio.run(run_test())

    def test_validate_multiple_evidence_sync(self):
        """StalenessDetector validates multiple evidence items."""
        async def run_test():
            edg = ExecutionDependencyGraph()
            detector = StalenessDetector(edg)
            from app.contracts.dependency_node import DependencyNode
            
            # Create one fresh and one stale evidence
            fresh = DependencyNode(
                node_id="evd-evd-fresh123",
                node_type=NodeType.EVIDENCE,
                content_hash="fresh",
                workspace_id="ws-test",
                is_stale=False
            )
            stale = DependencyNode(
                node_id="evd-evd-stale456",
                node_type=NodeType.EVIDENCE,
                content_hash="stale",
                workspace_id="ws-test",
                is_stale=True,
                stale_reason="Source changed"
            )
            
            await edg.add_node(fresh)
            await edg.add_node(stale)
            
            # Validate
            all_fresh, reasons = await detector.validate_evidence_for_approval(
                ["evd-fresh123", "evd-stale456"]
            )
            
            assert all_fresh is False
            assert len(reasons) == 1
        
        asyncio.run(run_test())
