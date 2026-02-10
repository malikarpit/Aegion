import os
from typing import Optional
from anthropic import AsyncAnthropic
try:
    from app.core.logging import logger
except ImportError:
    import logging
    logger = logging.getLogger("AnthropicAdapter")

class AnthropicAdapter:
    """
    Adapter for Anthropic's Claude models (e.g., claude-3-5-sonnet).
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = AsyncAnthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Anthropic API key not found. Adapter disabled.")

    async def complete(self, prompt: str, model: str = "claude-3-5-sonnet-20240620", max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """
        Generate completion from Anthropic.
        """
        if not self.client:
            raise ValueError("Anthropic client not initialized (missing API key)")

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system="You are a governance AI agent for the Aegion platform. Return valid JSON only.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            raise
