import asyncio
import sys
import os
import shutil
from datetime import datetime

# Add app to path
sys.path.append(os.getcwd())

from app.domain.session import Session
from app.adapters.persistence.session_repository import FileSessionRepository
from app.services.repo_intelligence.repository import FileRepoIntelligenceRepository
from app.domain.repo import WorkspaceScan

async def verify_session_persistence():
    print("🧪 Verifying Session Persistence...")
    repo = FileSessionRepository(".test_data/sessions")
    
    session = Session(
        owner_id="test_user",
        workspace_id="ws_1",
        status="active"
    )
    
    await repo.create(session)
    print(f"✅ Created session {session.session_id}")
    
    loaded = await repo.get_by_id(session.session_id)
    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert loaded.status == "active"
    print("✅ Loaded session correctly")
    
    await repo.close_session(session.session_id)
    loaded = await repo.get_by_id(session.session_id)
    assert loaded.status == "closed"
    print("✅ Closed session correctly")

async def verify_repo_intelligence_persistence():
    print("\n🧪 Verifying Repo Intelligence Persistence...")
    repo = FileRepoIntelligenceRepository(".test_data/intelligence")
    
    scan = WorkspaceScan(
        scan_id="scan_1",
        workspace_id="ws_1",
        start_time=datetime.now(),
        status="in_progress"
    )
    
    await repo.save_scan(scan)
    print(f"✅ Saved scan {scan.scan_id}")
    
    loaded = await repo.get_scan(scan.scan_id)
    assert loaded is not None
    assert loaded.scan_id == scan.scan_id
    print("✅ Loaded scan correctly")

async def main():
    try:
        if os.path.exists(".test_data"):
            shutil.rmtree(".test_data")
            
        await verify_session_persistence()
        await verify_repo_intelligence_persistence()
        
        print("\n🎉 All persistence checks passed!")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
