
import asyncio
import sys
import os
import shutil
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

from app.services.thought_service import get_thought_service
from app.services.git_checkpoint_service import get_git_checkpoint_service
from app.models.thought import CreateThoughtRequest, ThoughtState
from app.adapters.persistence.event_store import InMemoryEventStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEST_WORKSPACE = "/tmp/aegion_test_workspace"

async def test_integration():
    logger.info("🧪 Starting Integration Test...")

    # 1. Setup Workspace
    if os.path.exists(TEST_WORKSPACE):
        shutil.rmtree(TEST_WORKSPACE)
    os.makedirs(TEST_WORKSPACE)
    
    # 2. Initialize Services
    event_store = InMemoryEventStore()
    thought_service = get_thought_service(event_store)
    checkpoint_service = get_git_checkpoint_service()

    # 3. Create a Thought
    logger.info("🧠 Creating Thought...")
    thought = await thought_service.create_thought(
        req=CreateThoughtRequest(
            workspace_id="ws-test",
            session_id="sess-test",
            title="Refactoring Login",
            rationale="Security improvements"
        ),
        created_by="tester"
    )
    logger.info(f"✅ Thought Created: {thought.thought_id}")

    # 4. Create a Checkpoint (Simulating a semantic save)
    logger.info("💾 Creating Checkpoint linked to Thought...")
    snapshot = await checkpoint_service.commit_snapshot(
        workspace_path=TEST_WORKSPACE,
        checkpoint_id="cp-001",
        message="Initial refactor step",
        thought_id=thought.thought_id,
        actor_id="tester"
    )
    logger.info(f"✅ Checkpoint Created: {snapshot.commit_sha}")

    # 5. Verify Linkage
    logger.info("🔍 Verifying Linkage...")
    
    # Reload thought
    updated_thought = await thought_service.get_thought(thought.thought_id)
    
    # Check if link exists
    commit_link = next((l for l in updated_thought.links if l.target_id == snapshot.commit_sha), None)
    
    if commit_link:
        logger.info(f"✅ FOUND LINK: Thought -> Commit {commit_link.target_id}")
    else:
        logger.error("❌ MISSING LINK: Thought does not reference commit")
        sys.exit(1)

    # 6. Verify Reverse Lookup
    reverse_thought = await thought_service.get_thought_by_commit(snapshot.commit_sha)
    if reverse_thought and reverse_thought.thought_id == thought.thought_id:
        logger.info(f"✅ REVERSE LOOKUP SUCCESS: Commit -> Thought {reverse_thought.thought_id}")
    else:
        logger.error("❌ REVERSE LOOKUP FAILED")
        sys.exit(1)

    logger.info("🎉 Integration Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_integration())
