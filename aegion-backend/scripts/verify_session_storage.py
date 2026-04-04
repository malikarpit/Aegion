import asyncio
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.domain.session import Session
from app.adapters.persistence.session_repository import FileSessionRepository
from app.core.time import TimeAuthority

async def test_file_repository():
    print("\n📦 Testing FileSessionRepository...")
    
    # Setup clean test environment
    test_dir = ".aegion/test_sessions"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
        
    repo = FileSessionRepository(test_dir)
    
    # 1. Create
    session = Session(
        owner_id="test_user",
        workspace_id="test_workspace",
        status="active"
    )
    created = await repo.create(session)
    print(f"✅ Created session: {created.session_id}")
    
    # 2. Get by ID
    fetched = await repo.get_by_id(session.session_id)
    assert fetched is not None
    assert fetched.session_id == session.session_id
    assert fetched.owner_id == "test_user"
    print(f"✅ Fetched session by ID: {fetched.session_id}")
    
    # 3. List active by user
    active = await repo.get_active_by_user("test_user")
    assert active is not None
    assert active.session_id == session.session_id
    print(f"✅ Found active session for user")
    
    # 4. Update (Close)
    closed = await repo.close_session(session.session_id)
    assert closed.status == "closed"
    assert closed.closed_at is not None
    print(f"✅ Closed session")
    
    # 5. Verify no active session
    active_after_close = await repo.get_active_by_user("test_user")
    assert active_after_close is None
    print(f"✅ Verified no active session after close")
    
    # 6. Distill
    distilled = await repo.distill_session(session.session_id)
    assert distilled.status == "distilled"
    assert distilled.distilled_at is not None
    print(f"✅ Distilled session")
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    print("✨ FileSessionRepository tests passed!")

async def main():
    try:
        await test_file_repository()
        # We can add tests for other adapters here if needed/configured
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
