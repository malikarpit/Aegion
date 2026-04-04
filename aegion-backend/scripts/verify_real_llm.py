#!/usr/bin/env python3
"""
Verification script for Real Cognitive Engine.
Tests if the MultiModelLLMAdapter correctly initializes real adapters 
and routes requests or falls back to simulation.
"""

import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock app.core.logging
import types
core_pkg = types.ModuleType("app.core")
core_logging = types.ModuleType("app.core.logging")
core_logging.logger = logging.getLogger("VERIFY_LLM")
sys.modules["app.core"] = core_pkg
sys.modules["app.core.logging"] = core_logging

logging.basicConfig(level=logging.INFO)

# Set dummy keys for verification of initialization logic
# Comment out to test simulation fallback
# os.environ["OPENAI_API_KEY"] = "sk-dummy"
# os.environ["ANTHROPIC_API_KEY"] = "sk-ant-dummy"
# os.environ["GOOGLE_API_KEY"] = "AIza-dummy"

async def verify_llm_adapter():
    print("\n🤖 Verifying MultiModelLLMAdapter Initialization...")
    
    # Import after setting env vars
    from app.adapters.multi_model_llm import MultiModelLLMAdapter
    
    adapter = MultiModelLLMAdapter()
    
    print(f"   [OpenAI] Client active: {adapter.has_openai}")
    print(f"   [Anthropic] Client active: {adapter.has_anthropic}")
    print(f"   [Gemini] Client active: {adapter.has_google}")
    
    # Test call (should simulate if no keys)
    print("\n🧪 Testing Completion (Model: gpt-4o)...")
    try:
        response = await adapter.complete(
            prompt="Vote: SUPPORT. Logic: LGTM.",
            model="gpt-4o"
        )
        print(f"   Response type: {type(response)}")
        print(f"   Vote: {response.get('vote')}")
        print(f"   Confidence: {response.get('confidence')}")
        
        # Check if it was a simulation match or real error
        if "Simulated analysis" in response.get("analysis", ""):
            print("   ✅ Fallback to simulation worked.")
        else:
             print("   ⚠️ Real response received (unexpected if no keys).")

    except Exception as e:
        print(f"   ❌ Completion failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_llm_adapter())
