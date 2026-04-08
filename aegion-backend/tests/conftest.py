"""
Global test fixtures for Aegion backend tests.
"""

import pytest
import os
import glob
from unittest.mock import MagicMock, patch

# Ensure required config values are set BEFORE app imports
os.environ["AEGION_ENVIRONMENT"] = "testing"
os.environ["AEGION_AUDIT_SIGNING_KEY"] = "dummy_test_key"
os.environ["AEGION_FIREBASE_PROJECT_ID"] = "test-project"
os.environ["AEGION_SUPABASE_URL"] = "https://test.supabase.co"
os.environ["AEGION_SUPABASE_SERVICE_KEY"] = "dummy_service_key"
import supabase
from typing import Optional, List, Dict

# Mock the supabase module entirely at load time
_mock_client = MagicMock()
_mock_table = MagicMock()
for method in ['select', 'insert', 'update', 'delete', 'eq', 'neq', 'in_', 'order', 'limit', 'single', 'maybe_single', 'upsert']:
    getattr(_mock_table, method).return_value = _mock_table
_mock_table.execute.return_value = MagicMock(data=[], count=0)
_mock_client.table.return_value = _mock_table

def _fake_create_client(*args, **kwargs):
    return _mock_client
supabase.create_client = _fake_create_client


# In-memory store to patch PostgresKVStore in tests
# Now a flat Dict[namespace, Dict[key, tuple]] ignoring workspace_id to mimic legacy JsonFileStore.
_in_memory_store: Dict[str, Dict[str, dict]] = {}

import app.services.durable_store

# Patch PostgresKVStore methods directly so subclasses inherit them
async def fake_set(self, key: str, value: dict, workspace_id: str = "default") -> None:
    if self.namespace not in _in_memory_store:
        _in_memory_store[self.namespace] = {}
    _in_memory_store[self.namespace][key] = value

async def fake_get(self, key: str, workspace_id: str = "default") -> Optional[dict]:
    return _in_memory_store.get(self.namespace, {}).get(key)

async def fake_delete(self, key: str, workspace_id: str = "default") -> bool:
    if self.namespace in _in_memory_store:
        if key in _in_memory_store[self.namespace]:
            del _in_memory_store[self.namespace][key]
    return True

async def fake_list_keys(self, workspace_id: str = "default") -> List[str]:
    return list(_in_memory_store.get(self.namespace, {}).keys())

async def fake_list_all(self, workspace_id: str = "default") -> List[dict]:
    items = _in_memory_store.get(self.namespace, {}).items()
    return [{"key": k, "value": v} for k, v in items]

@pytest.fixture(autouse=True)
def _clear_in_memory_store():
    """Clear the in-memory durable store before each test to prevent state leakage."""
    _in_memory_store.clear()
    yield

@pytest.fixture(autouse=True)
def _clear_graph():
    """Clear the in-memory knowledge graph before each test to prevent state leakage."""
    from app.api.v1.analytics import _graph_service
    from app.adapters.memory_graph import InMemoryKnowledgeGraph
    _graph_service.graph = InMemoryKnowledgeGraph()
    yield

app.services.durable_store.PostgresKVStore.set = fake_set
app.services.durable_store.PostgresKVStore.get = fake_get
app.services.durable_store.PostgresKVStore.delete = fake_delete
app.services.durable_store.PostgresKVStore.list_keys = fake_list_keys
app.services.durable_store.PostgresKVStore.list_all = fake_list_all



from app.middleware import session_security


@pytest.fixture(autouse=True)
def _clear_session_state():
    """
    Clear in-memory session security stores between tests.
    
    Without this, accumulated session state causes spurious 422 
    "concurrent session limit" failures when tests share session IDs.
    """
    yield
    session_security._session_fingerprints.clear()
    session_security._session_components.clear()
    session_security._user_sessions.clear()
    session_security._session_token_bindings.clear()
    session_security._security_events.clear()


@pytest.fixture(autouse=True)
def _clear_durable_stores():
    """
    Clear durable JSON store files before each test to prevent data leakage.
    Also clears the in-memory PostgresKVStore mock.
    """
    store_dir = ".aegion_data"
    if os.path.isdir(store_dir):
        for f in glob.glob(os.path.join(store_dir, "*.json")):
            with open(f, "w") as fh:
                fh.write("{}")
    
    _in_memory_store.clear()
    
    yield
    # Also clear after test for clean state
    if os.path.isdir(store_dir):
        for f in glob.glob(os.path.join(store_dir, "*.json")):
            with open(f, "w") as fh:
                fh.write("{}")
    
    _in_memory_store.clear()

@pytest.fixture(autouse=True)
def _disable_rate_limiting():
    """
    Globally disable rate limiting for all tests by patching the middleware dispatch.
    """
    from app.middleware.rate_limit import RateLimitMiddleware
    
    # Original method
    original_dispatch = RateLimitMiddleware.dispatch
    
    async def mock_dispatch(self, request, call_next):
        # Bypass rate limiting logic completely
        return await call_next(request)
        
    RateLimitMiddleware.dispatch = mock_dispatch
    yield
    RateLimitMiddleware.dispatch = original_dispatch


