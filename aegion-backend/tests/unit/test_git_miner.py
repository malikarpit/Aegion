import pytest
import os
import git
from app.services.repo_intelligence.git_miner import GitMiner
from app.services.repo_intelligence.service import get_repo_service
from app.adapters.persistence.event_store import InMemoryEventStore

def test_intent_classification():
    miner = GitMiner(".")
    
    assert miner._infer_intent("feat(auth): login") == "feat"
    assert miner._infer_intent("fix: minor bug") == "fix"
    assert miner._infer_intent("chore: update deps") == "chore"
    assert miner._infer_intent("random commit message") == "other"

@pytest.fixture
def temp_git_repo(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Init repo
    r = git.Repo.init(repo_dir)
    
    # Configure user
    r.config_writer().set_value("user", "name", "Test User").release()
    r.config_writer().set_value("user", "email", "test@example.com").release()
    
    # Create file and commit
    file_path = repo_dir / "README.md"
    file_path.write_text("# Test Repo")
    r.index.add([str(file_path)])
    r.index.commit("feat: initial commit")
    
    # Create another file
    file2 = repo_dir / "app.py"
    file2.write_text("print('hello')")
    r.index.add([str(file2)])
    r.index.commit("fix: add app")
    
    return str(repo_dir)

@pytest.mark.asyncio
async def test_miner_history(temp_git_repo):
    miner = GitMiner(temp_git_repo)
    commits = []
    async for c in miner.mine_history(limit=5):
        commits.append(c)
    
    assert len(commits) == 2
    assert commits[0].message == "fix: add app"
    assert commits[0].intent_type == "fix"
    assert commits[1].message == "feat: initial commit"
    assert commits[1].intent_type == "feat"

@pytest.mark.asyncio
async def test_service_lineage(temp_git_repo):
    store = InMemoryEventStore()
    
    # Inject temp repo path
    from app.services.repo_intelligence.service import RepoIntelligenceService
    from tests.helpers.in_memory_repo import InMemoryRepoRepository
    repo = InMemoryRepoRepository()
    service = RepoIntelligenceService(store, repo, root_path=temp_git_repo)
    
    # Start scan (triggers mining in background)
    await service.start_scan("test_ws")
    
    # Wait for background scan to complete
    import asyncio
    await asyncio.sleep(2.0)
    
    # Mine should have found 2 commits
    scan = await service.get_latest_scan("test_ws")
    assert scan.commits_mined == 2
    
    # Lineage for README.md (added in initial commit)
    lineage = await service.get_file_lineage("README.md", "test_ws")
    
    # Current limitation: lineage mapping is simple filename match
    # "README.md" is in "feat: initial commit"
    # But "fix: add app" touched app.py, not README.md
    
    # However, GitMiner iterates all commits.
    # Service filter:
    # if any(f.endswith(file_path) or file_path.endswith(f) for f in commit.changed_files):
    
    # In temp repo:
    # Commit 2: "fix: add app" -> changed "app.py"
    # Commit 1: "feat: initial commit" -> changed "README.md"
    
    assert len(lineage) == 1
    assert lineage[0].intent_type == "feat"
    assert "README.md" in lineage[0].changed_files
