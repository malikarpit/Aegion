from fastapi.testclient import TestClient
from app.main import app
from app.services.repo_intelligence.service import get_repo_service
from app.api.v1.repo import get_service
from app.adapters.persistence.event_store import InMemoryEventStore
from app.domain.repo import FileRecord, SymbolRecord
from app.domain.git_models import CommitRecord
from datetime import datetime, timezone
import pytest

# Test Client
client = TestClient(app)
client.headers = {
    "X-Aegion-Session": "test_session",
    "X-Aegion-Intent": "unit-test"
}

from app.services.repo_intelligence.service import RepoIntelligenceService

# Mock Service Injection
def get_mock_service():
    store = InMemoryEventStore()
    # Direct instantiation to avoid singleton state from other tests
    service = RepoIntelligenceService(store, root_path=".")
    
    # Pre-populate data
    service._scans["scan-1"] = None # Just a placeholder key
    
    symbol = SymbolRecord(symbol_id="s1", name="Main", type="class", file_path="main.py", line_start=1, line_end=10)
    
    service._files["main.py"] = FileRecord(
        file_path="main.py", content_hash="h1", language="python", size_bytes=100,
        last_modified=datetime.now(timezone.utc), loc=20,
        symbols=[symbol]
    )
    service._symbols["s1"] = symbol
    
    service._commits["c1"] = CommitRecord(
        sha="c1", message="feat: init", author_name="User", author_email="u@e.com",
        timestamp=datetime.now(timezone.utc), changed_files=["main.py"]
    )
    
    return service

from app.core.security import get_current_user, AuthorityContext, Role

def get_mock_user():
    return AuthorityContext(
        user_id="test_user",
        role=Role.DEVELOPER,
        session_id="test_session",
        permissions=["repo:read"]
    )

# Override dependencies
app.dependency_overrides[get_service] = get_mock_service
app.dependency_overrides[get_current_user] = get_mock_user

def test_get_file_details():
    response = client.get("/api/v1/repo/file/main.py")
    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] == "main.py"
    assert len(data["symbols"]) == 1

def test_query_symbols():
    response = client.get("/api/v1/repo/symbols?query=Main")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Main"

def test_build_context():
    payload = {
        "files": ["main.py"],
        "workspace_id": "test_ws",
        "max_history": 5
    }
    response = client.post("/api/v1/repo/context", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["workspace_id"] == "test_ws"
    assert len(data["file_records"]) == 1
    assert data["file_records"][0]["file_path"] == "main.py"
    assert len(data["relevant_commits"]) == 1
    assert data["relevant_commits"][0]["message"] == "feat: init"

def test_get_top_contributors():
    response = client.get("/api/v1/repo/contributors?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "User"
    assert data[0]["commits"] == 1
