
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from app.main import app
from app.core.security import get_current_user, AuthorityContext, Role
from app.models.draft import SessionDraft
from anyio import run

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def override_auth():
    mock_user = AuthorityContext(
        user_id="user-persist-1",
        role=Role.DEVELOPER
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides = {}

@pytest.fixture
def mock_firestore():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc_ref = MagicMock()
    mock_doc_snapshot = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref
    
    # Async methods need AsyncMock
    mock_doc_ref.set = AsyncMock()
    mock_doc_ref.get = AsyncMock(return_value=mock_doc_snapshot)
    mock_doc_ref.delete = AsyncMock()
    
    # Query mock
    mock_query = MagicMock()
    mock_collection.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.get = AsyncMock(return_value=[mock_doc_snapshot])
    
    return mock_db

def mock_firestore_dep(func):
    """Dummy decorator if we use it."""
    return func


def test_draft_repository_persistence(mock_firestore):
    """Test FirestoreDraftRepository directly."""
    from app.adapters.firestore.draft_repository import FirestoreDraftRepository
    
    async def _test():
        repo = FirestoreDraftRepository(db=mock_firestore)
        
        draft = SessionDraft(
            draft_id="draft-persist-1",
            user_id="user-persist-1",
            workspace_id="ws-1",
            title="Persistent Draft",
            context_data={"foo": "bar"}
        )
        
        # Save
        await repo.save(draft)
        mock_firestore.collection.assert_called_with("session_drafts")
        mock_firestore.collection().document.assert_called_with("draft-persist-1")
        # Verify set called
        assert mock_firestore.collection().document().set.called
        
        # Retrieve
        # Setup mock return
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = draft.model_dump()
        mock_firestore.collection().document().get.return_value = mock_snapshot
        
        fetched = await repo.get("draft-persist-1")
        assert fetched is not None
        assert fetched.title == "Persistent Draft"
        
        # Delete
        await repo.delete("draft-persist-1")
        assert mock_firestore.collection().document().delete.called

    run(_test)

def test_artifact_log_persistence(mock_firestore):
    """Test FirestoreArtifactLog directly."""
    from app.adapters.firestore.artifact_log import FirestoreArtifactLog
    import json
    
    async def _test():
        log = FirestoreArtifactLog(db=mock_firestore)
        key = "artifacts/sessions/hash-123"
        content = {"session_id": "sess-1", "data": "test"}
        content_bytes = json.dumps(content).encode("utf-8")
        
        # Store
        await log.store(key, content_bytes, "application/json")
        mock_firestore.collection.assert_called_with("artifacts")
        mock_firestore.collection().document.assert_called_with("hash-123")
        assert mock_firestore.collection().document().set.called
        
        # Retrieve
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            "data": content_bytes.decode("utf-8"),
            "content_type": "application/json"
        }
        mock_firestore.collection().document().get.return_value = mock_snapshot
        
        retrieved = await log.retrieve(key)
        assert retrieved is not None
        assert json.loads(retrieved) == content

    run(_test)

@mock_firestore_dep
def test_session_distillation_integration(client, override_auth):
    """Test that closing a session creates an artifact."""
    from app.api.v1.sessions import get_session_repo
    
    # Mock Repository
    mock_repo = AsyncMock()
    
    # Mock active session
    from app.domain.session import Session
    import uuid
    sid = str(uuid.uuid4())
    mock_session = Session(
        session_id=sid,
        owner_id="user-persist-1",
        workspace_id="ws-1",
        status="active"
    )
    mock_repo.get_by_id.return_value = mock_session
    mock_repo.close_session.return_value = mock_session
    mock_repo.distill_session.return_value = mock_session
    
    # Override dependency
    app.dependency_overrides[get_session_repo] = lambda: mock_repo
    
    # Mock Artifact Log (still used directly in sessions.py unfortunately - TODO fix)
    # We patch it because it is instantiated inside close_session
    with patch("app.adapters.firestore.artifact_log.FirestoreArtifactLog") as MockArtifactLog:
        mock_log = MockArtifactLog.return_value
        mock_log.store = AsyncMock()
        
        # Mock Graph Service
        with patch("app.api.v1.analytics._graph_service") as mock_graph:
             mock_graph.list_proposals = AsyncMock(return_value=[])
             mock_graph.list_decisions = AsyncMock(return_value=[])
             mock_graph.record_proposal = AsyncMock()

             # Call Close Session
             headers_close = {
                 "X-Aegion-Session": sid,
                 "X-Aegion-Intent": "session.close"
             }
             
             resp = client.post(
                 f"/api/v1/sessions/{sid}/close",
                 json={"distill": True},
                 headers=headers_close
             )
             
             # Cleanup override
             del app.dependency_overrides[get_session_repo]
             
             if resp.status_code != 200:
                 print(f"Failed: {resp.json()}")

             assert resp.status_code == 200
             assert resp.json()["distilled"] is True
             
             # Verify store was called
             assert mock_log.store.called
             # Verify repo updated
             assert mock_repo.distill_session.called
