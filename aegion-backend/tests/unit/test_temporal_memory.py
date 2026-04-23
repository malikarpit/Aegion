import pytest
from unittest.mock import MagicMock, patch
from app.services.council_kernel.temporal_memory import TemporalMemory, PastDecision

@pytest.fixture
def mock_supabase():
    with patch("app.db.supabase_client.get_supabase_client") as mock:
        yield mock

@pytest.mark.asyncio
async def test_recall_similar_decisions(mock_supabase):
    # Setup mock data
    mock_client = MagicMock()
    mock_supabase.return_value = mock_client
    
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "d1", "title": "Migrate database to postgres", "verdict": "approved", "created_at": "2024-01-01T00:00:00Z"},
        {"id": "d2", "title": "Change frontend to React", "verdict": "rejected", "created_at": "2024-01-02T00:00:00Z"}
    ]
    
    # Mock outcome tracker subquery
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.count = 0
    
    memory = TemporalMemory(top_k=5)
    
    # Query mentions postgres migration
    query = "Should we use postgres for our new database instead of json files?"
    
    results = await memory.recall_similar_decisions("ws-123", query)
    
    # Needs to match d1 much more strongly than d2
    assert len(results) > 0
    assert results[0].decision_id == "d1"
    assert results[0].relevance_score > 0.05

@pytest.mark.asyncio
async def test_get_council_accuracy(mock_supabase):
    mock_client = MagicMock()
    mock_supabase.return_value = mock_client
    
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "d1", "title": "Migrate database to postgres", "verdict": "approved"},
        {"id": "d2", "title": "Migrate to redis cache", "verdict": "approved"},
        {"id": "d3", "title": "Add api rate limiting", "verdict": "rejected"}
    ]
    
    memory = TemporalMemory()
    accuracy = await memory.get_council_accuracy("ws-123", "migrate database cache")
    
    # Out of 3 total, the 2 matching "migrate/database/cache" are both approved
    assert accuracy.total_decisions == 2
    assert accuracy.best_pattern == "Council approves most proposals"

def test_extract_concepts():
    memory = TemporalMemory()
    text = "We should Migrate our Database to Postgres. Also enable rate limiting on the API."
    
    concepts = memory._extract_concepts(text)
    
    # Should find 'postgres', 'api' from tech_terms, 'migrat' from actions, 
    # and maybe 'rate_limit' (no, it extracts 'rate_limit' only if one is an anchor, 
    # 'rate' and 'api' are anchors)
    assert 'postgres' in concepts
    assert 'api' in concepts
    assert any(c.startswith('migrat') for c in concepts)
