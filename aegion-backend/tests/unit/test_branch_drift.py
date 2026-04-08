import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.governance_conflict import GovernanceConflictService
from app.models.conflict import ConflictSeverity

@pytest.mark.asyncio
async def test_detect_branch_conflicts_no_miner():
    """Test graceful failure when miner is missing"""
    service = GovernanceConflictService()
    
    with patch("app.services.repo_intelligence.service.get_repo_service") as mock_get_repo:
        mock_repo = AsyncMock()
        mock_repo.detect_branch_drift.return_value = {"error": "Git miner not available"}
        mock_get_repo.return_value = mock_repo
        
        conflicts = await service.detect_branch_conflicts("ws1", "main", "feature")
        assert len(conflicts) == 0

@pytest.mark.asyncio
async def test_detect_mass_deletion():
    """Test Mass Deletion rule"""
    service = GovernanceConflictService()
    service._broadcast_conflict = AsyncMock()
    
    with patch("app.services.repo_intelligence.service.get_repo_service") as mock_get_repo:
        mock_repo = AsyncMock()
        mock_repo.detect_branch_drift.return_value = {
            "stats": {"deleted": 25, "modified": 0, "added": 0, "renamed": 0, "total_files_changed": 25},
            "changes": [],
            "timestamp": datetime.now().isoformat()
        }
        mock_get_repo.return_value = mock_repo
        
        conflicts = await service.detect_branch_conflicts("ws1", "main", "feature")
        
        assert len(conflicts) == 1
        assert conflicts[0].rule_id == "mass_deletion"
        assert conflicts[0].severity == ConflictSeverity.CRITICAL
        assert "Mass Deletion Detected" in conflicts[0].message
        service._broadcast_conflict.assert_called_once()


@pytest.mark.asyncio
async def test_detect_infra_change():
    """Test Critical Infrastructure Change rule"""
    service = GovernanceConflictService()
    service._broadcast_conflict = AsyncMock()
    
    with patch("app.services.repo_intelligence.service.get_repo_service") as mock_get_repo:
        mock_repo = AsyncMock()
        mock_repo.detect_branch_drift.return_value = {
            "stats": {"deleted": 0, "modified": 2, "added": 0, "renamed": 0, "total_files_changed": 2},
            "changes": [
                {"file_path": "app/infrastructure/database.py", "change_type": "M"},
                {"file_path": "migrations/versions/123_init.py", "change_type": "A"}
            ],
            "timestamp": datetime.now().isoformat()
        }
        mock_get_repo.return_value = mock_repo
        
        conflicts = await service.detect_branch_conflicts("ws1", "main", "feature")
        
        assert len(conflicts) == 1
        assert conflicts[0].rule_id == "infra_change"
        assert conflicts[0].severity == ConflictSeverity.HIGH
        assert "Core Infrastructure Changed" in conflicts[0].message
