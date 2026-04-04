
import sys
import os
import uuid
from datetime import datetime

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../..'))

try:
    from app.models.thought import ThoughtCommit, ThoughtLink
    from app.contracts.thought import ThoughtState, ThoughtLinkType
except ImportError as e:
    print(f"Error importing models: {e}")
    sys.exit(1)

def test_thought_models():
    print("Testing Thought Models...")
    
    # 1. Create a Link
    link = ThoughtLink(
        type=ThoughtLinkType.EXPLAINS,
        target_id="commit-sha-123",
        target_type="commit"
    )
    assert link.link_id is not None
    assert link.created_at is not None
    print(f"✅ ThoughtLink created: {link.link_id}")

    # 2. Create a Thought Commit
    thought = ThoughtCommit(
        workspace_id="ws-123",
        session_id="sess-456",
        title="Refactoring Auth",
        rationale="Improving security",
        created_by="user-789",
        links=[link]
    )
    
    assert thought.thought_id.startswith("tht-")
    assert thought.state == ThoughtState.DRAFT
    assert len(thought.links) == 1
    assert thought.links[0].type == ThoughtLinkType.EXPLAINS
    print(f"✅ ThoughtCommit created: {thought.thought_id}")
    
    # 3. Test serialization
    json_output = thought.model_dump_json()
    assert "Refactoring Auth" in json_output
    print("✅ Model serialization successful")

if __name__ == "__main__":
    test_thought_models()
