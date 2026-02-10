import os
from typing import Optional
import google.generativeai as genai
try:
    from app.core.logging import logger
except ImportError:
    import logging
    logger = logging.getLogger("GeminiAdapter")

class GeminiAdapter:
    """
    Adapter for Google's Gemini models (e.g., gemini-1.5-pro).
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.client_enabled = True
        else:
            self.client_enabled = False
            logger.warning("Google API key not found. Adapter disabled.")

    async def complete(self, prompt: str, model: str = "gemini-1.5-pro", max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """
        Generate completion from Gemini.
        """
        if not self.client_enabled:
            raise ValueError("Google client not initialized (missing API key)")

        try:
            # Configure generation config
            config = genai.types.GenerationConfig(
                candidate_count=1,
                max_output_tokens=max_tokens,
                temperature=temperature,
                response_mime_type="application/json"  # Enforce JSON
            )
            
            model_instance = genai.GenerativeModel(
                model_name=model,
                system_instruction="You are a governance AI agent for the Aegion platform. Return valid JSON only."
            )
            
            # Gemini async call
            response = await model_instance.generate_content_async(prompt, generation_config=config)
            return response.text
        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            raise
