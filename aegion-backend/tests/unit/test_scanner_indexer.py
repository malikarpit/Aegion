import pytest
import os
from app.services.repo_intelligence.scanner import RepoScanner
from app.services.repo_intelligence.analyzers.python import PythonAnalyzer
from app.services.repo_intelligence.analyzers.typescript import TypeScriptAnalyzer
from app.services.repo_intelligence.service import get_repo_service
from app.adapters.persistence.event_store import InMemoryEventStore

# ── Analyzers ──

def test_python_analyzer():
    code = """
class MyClass:
    def my_method(self):
        pass

def my_func():
    pass
"""
    analyzer = PythonAnalyzer()
    symbols = analyzer.extract_symbols(code, "test.py")
    
    assert len(symbols) == 3
    names = {s.name for s in symbols}
    assert "MyClass" in names
    assert "my_method" in names
    assert "my_func" in names
    assert symbols[0].file_path == "test.py"

def test_typescript_analyzer():
    code = """
class MyComponent {
}

function helper() {
}

export const arrow = () => {
}
"""
    analyzer = TypeScriptAnalyzer()
    symbols = analyzer.extract_symbols(code, "test.ts")
    
    assert len(symbols) == 3
    names = {s.name for s in symbols}
    assert "MyComponent" in names
    assert "helper" in names
    assert "arrow" in names

# ── Scanner ──

@pytest.mark.asyncio
async def test_scanner_traversal():
    # Scan the actual repo codebase as a smoke test
    scanner = RepoScanner(".")
    files = []
    async for f in scanner.scan_workspace():
        files.append(f)
    
    # Should find at least main.py, scanner.py
    filenames = [os.path.basename(f.file_path) for f in files]
    assert "main.py" in filenames
    assert "scanner.py" in filenames
    
    # Should NOT find .git files or .venv (if ignored)
    for f in files:
        assert ".git/" not in f.file_path
        assert ".venv/" not in f.file_path

# ── Service Integration ──

@pytest.mark.asyncio
async def test_service_full_scan():
    # Reset singleton
    import app.services.repo_intelligence.service as _svc
    _svc._repo_service = None

    store = InMemoryEventStore()
    from tests.helpers.in_memory_repo import InMemoryRepoRepository
    repo = InMemoryRepoRepository()
    service = get_repo_service(store, repository=repo)
    
    # Start scan
    scan_id = await service.start_scan("test_ws")
    
    # Wait for background scan to complete
    import asyncio
    await asyncio.sleep(3.0)
    
    # Verify scan completed (since it runs as background task)
    scan = await service.get_scan_status(scan_id)
    assert scan.status == "completed"
    assert scan.files_scanned > 0
    assert scan.total_symbols > 0
    
    # Query symbols
    results = await service.query_symbols("RepoScanner", "test_ws")
    assert len(results) >= 1
    assert results[0].name == "RepoScanner"
