
import pytest
import os
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.services.council.council_service import CouncilService
from app.adapters.persistence.council_repository import FileCouncilRepository
from app.domain.council import CouncilSession, CouncilVote, CouncilOpinion
from app.contracts.decision_intent import DecisionIntent, DecisionTier

TEST_DATA_DIR = ".test_data/council_sessions"

@pytest.fixture
def clean_repo():
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)
    
    repo = FileCouncilRepository(TEST_DATA_DIR)
    yield repo
    
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)

@pytest.mark.asyncio
async def test_council_service_persistence(clean_repo):
    # Setup
    mock_llm = AsyncMock()
    # Mock LLM complete to return a valid opinion JSON
    mock_llm.complete.return_value = '{"claim": "Approve", "reasoning": "Looks good", "uncertainty": "LOW", "alternatives": []}'
    
    service = CouncilService(llm_port=mock_llm, repository=clean_repo)
    
    # Create a dummy session manually (simulating convente_session internals or just direct save)
    # But better to test via convene_session if possible.
    # However, convene_session requires complex mocking of members.
    # Let's test repository integration directly first, then service.
    
    session = CouncilSession(
        session_id="session-123",
        proposal_id="prop-456",
        workspace_id="ws-789",
        member_ids=["member-1"],
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        consensus=CouncilVote.SUPPORT,
        synthesis="Approved",
        opinions=[
            CouncilOpinion(
                member_id="member-1",
                proposal_id="prop-456",
                vote=CouncilVote.SUPPORT,
                confidence=0.9,
                analysis="Good",
                tokens_consumed=100
            )
        ]
    )
    
    # 1. Save directly via service's repo (or just usage of service if we exposed a save method, but we didn't)
    # Service calls save_session in convene_session.
    # Let's call repository directly to verify repo logic, then service flow.
    await clean_repo.save_session(session)
    
    # 2. Retrieve via service
    loaded_session = await service.get_session("session-123")
    assert loaded_session is not None
    assert loaded_session.session_id == "session-123"
    assert loaded_session.status == "completed"
    assert len(loaded_session.opinions) == 1
    
    # 3. Retrieve transcript
    transcript = await service.get_transcript("session-123")
    assert transcript["session_id"] == "session-123"
    assert transcript["result"] == CouncilVote.SUPPORT
    assert transcript["transcript"][0]["vote"] == CouncilVote.SUPPORT
    
    # 4. Find by proposal
    sessions = await service.get_sessions_for_proposal("prop-456")
    assert len(sessions) == 1
    assert sessions[0].session_id == "session-123"

