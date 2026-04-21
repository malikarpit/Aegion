import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.council_kernel.persona import PersonaEngine, get_persona_engine, PERSONAS

@pytest.mark.asyncio
async def test_debate_with_personas():
    mock_router = AsyncMock()
    mock_result = MagicMock()
    mock_result.response = "I am a persona response"
    mock_result.cost_usd = 0.005
    mock_result.tokens_in = 100
    mock_result.tokens_out = 50
    mock_router.call.return_value = mock_result
    
    engine = PersonaEngine(model_router=mock_router)
    
    proposition = "Should we adopt Rust?"
    persona_keys = ["security_auditor", "performance_architect"]
    models = [("openai", "gpt-4"), ("anthropic", "claude-3-5-sonnet")]
    
    result = await engine.debate_with_personas(proposition, persona_keys, models)
    
    assert result["proposition"] == proposition
    assert len(result["persona_responses"]) == 2
    
    # First response check
    assert result["persona_responses"][0]["persona"] == "Security Auditor"
    assert result["persona_responses"][0]["position"] == "I am a persona response"
    assert result["persona_responses"][0]["model"] == "gpt-4"
    assert result["persona_responses"][0]["cost_usd"] == 0.005
    assert result["persona_responses"][0]["tokens"] == 150
    
    # Second response check
    assert result["persona_responses"][1]["persona"] == "Performance Architect"
    assert result["persona_responses"][1]["model"] == "claude-3-5-sonnet"
    
    assert result["total_cost_usd"] == 0.01

@pytest.mark.asyncio
async def test_debate_with_missing_persona():
    mock_router = AsyncMock()
    mock_result = MagicMock()
    mock_result.response = "Fallback response"
    mock_result.cost_usd = 0.001
    mock_result.tokens_in = 10
    mock_result.tokens_out = 10
    mock_router.call.return_value = mock_result
    
    engine = PersonaEngine(model_router=mock_router)
    
    # "unknown_persona" should fallback to "user_advocate"
    result = await engine.debate_with_personas("Prop", ["unknown_persona"], [("mock", "model")])
    
    assert len(result["persona_responses"]) == 1
    assert result["persona_responses"][0]["persona"] == PERSONAS["user_advocate"]["name"]

def test_available_personas():
    engine = get_persona_engine()
    personas = engine.available_personas()
    assert "security_auditor" in personas
    assert "devils_advocate" in personas
    assert len(personas) == 6
