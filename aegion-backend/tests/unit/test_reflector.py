import pytest
from app.services.council_kernel.reflector import (
    CognitiveReflector,
    PathologyType,
    InterventionAction,
    Pathology,
)

def test_detect_groupthink():
    reflector = CognitiveReflector(groupthink_threshold=0.8)
    # Simulate a round where everyone agrees early (round 2 is still early, but round > 2 avoids early exit)
    # Wait, the code says: if round_number > 2 or len(responses) < 3: return None
    responses = [
        {"model": "gpt-4", "position": "I approve this proposal", "confidence": 0.8},
        {"model": "claude", "position": "Yes, approve", "confidence": 0.9},
        {"model": "gemini", "position": "Agree to approve", "confidence": 0.85},
    ]
    pathology = reflector._detect_groupthink(responses, round_number=2)
    assert pathology is not None
    assert pathology.type == PathologyType.GROUPTHINK
    assert pathology.intervention == InterventionAction.INJECT_CONTRARIAN

def test_detect_no_groupthink():
    reflector = CognitiveReflector(groupthink_threshold=0.8)
    responses = [
        {"model": "gpt-4", "position": "I approve this proposal", "confidence": 0.8},
        {"model": "claude", "position": "I strongly reject this", "confidence": 0.9},
        {"model": "gemini", "position": "I will stay neutral", "confidence": 0.85},
    ]
    pathology = reflector._detect_groupthink(responses, round_number=2)
    assert pathology is None

def test_detect_authority_bias():
    reflector = CognitiveReflector()
    history = [
        [{"model": "gpt-4", "position": "We should use a postgres queue because it is transactional. It lowers our infrastructure operational burden."}]
    ]
    responses = [
        {"model": "gpt-4", "position": "I maintain my position on the postgres queue."},
        {"model": "claude", "position": "We should use a postgres queue because it is transactional. It lowers our infrastructure operational burden."},
        {"model": "gemini", "position": "We should use a postgres queue because it is transactional. It lowers our infrastructure operational burden."},
    ]
    
    pathology = reflector._detect_authority_bias(responses, history, round_number=2)
    assert pathology is not None
    assert pathology.type == PathologyType.AUTHORITY_BIAS
    assert pathology.intervention == InterventionAction.RANDOMIZE_ORDER

def test_detect_anchoring():
    reflector = CognitiveReflector()
    responses = [
        {"model": "gpt-4", "position": "This process will take 120 ms to complete."},
        {"model": "claude", "position": "I estimate execution time at 122 ms duration."},
        {"model": "gemini", "position": "Performance should hover around 118 ms latency."},
    ]
    pathology = reflector._detect_anchoring(responses)
    assert pathology is not None
    assert pathology.type == PathologyType.ANCHORING
    assert pathology.intervention == InterventionAction.PARALLEL_ESTIMATES

def test_detect_circular_reasoning():
    reflector = CognitiveReflector(circular_window=2)
    # Round 1
    history = [
        [], # Round 1
        [], # Round 2
    ]
    # In round 1, claude said X. Now it's round 3, and claude says the exact same X.
    history[0] = [
        {"model": "gpt-4", "position": "I think X"},
        {"model": "claude", "position": "This security flaw allows direct unauthorized privilege escalation via the JWT payload manipulation vector."}
    ]
    
    # In round 3 (current)
    responses = [
        {"model": "claude", "position": "As I said before, this security flaw allows direct unauthorized privilege escalation via the JWT payload manipulation vector."}
    ]
    
    pathologies = reflector._detect_circular_reasoning(responses, history, round_number=3)
    assert len(pathologies) == 1
    assert pathologies[0].type == PathologyType.CIRCULAR_REASONING

def test_reflector_analyze_round():
    reflector = CognitiveReflector()
    responses = [
        {"model": "gpt-4", "position": "I approve this because it is good.", "confidence": 0.9},
        {"model": "claude", "position": "I approve this completely.", "confidence": 0.8},
        {"model": "gemini", "position": "Yes, I agree to approve.", "confidence": 0.85},
    ]
    
    pathologies = reflector.analyze_round(responses, [], round_number=1)
    assert len(pathologies) > 0
    assert any(p.type == PathologyType.GROUPTHINK for p in pathologies)
    
    report = reflector.get_report(debate_id="debate_123", rounds_analyzed=1)
    assert report.has_issues is True
    assert report.interventions_taken > 0
