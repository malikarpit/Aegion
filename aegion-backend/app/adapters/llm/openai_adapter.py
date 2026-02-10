import os
from typing import Optional
from openai import AsyncOpenAI
try:
    from app.core.logging import logger
except ImportError:
    import logging
    logger = logging.getLogger("OpenAIAdapter")

class OpenAIAdapter:
    """
    Adapter for OpenAI's GPT models (e.g., gpt-4o).
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OpenAI API key not found. Adapter disabled.")

    async def complete(self, prompt: str, model: str = "gpt-4o", max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """
        Generate completion from OpenAI.
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized (missing API key)")

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a governance AI agent for the Aegion platform. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}  # Enforce JSON if model supports it
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            raise
