import json
import asyncio
import logging
from typing import Type, TypeVar, Any, Dict, Optional
from pydantic import BaseModel, ValidationError

from ...core.logging import logger

T = TypeVar("T", bound=BaseModel)

class LLMGateway:
    """
    Gateway for LLM interactions with strict schema validation and retries.
    Wraps the raw LLM port to ensure deterministic outputs.
    """
    
    def __init__(self, llm_port: Any):
        """
        Initialize with a raw LLM port.
        :param llm_port: Object with .complete() method returning Dict or Str.
        """
        self.llm_port = llm_port
        self.max_retries = 3
        self.base_delay = 1.0  # Seconds

    async def complete_with_schema(
        self, 
        prompt: str, 
        model: str, 
        schema: Type[T],
        temperature: float = 0.0
    ) -> T:
        """
        Execute LLM call and enforce strict Pydantic schema validation.
        Retries on validation errors or malformed JSON.
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # 1. Invoke LLM
                # We assume llm_port.complete returns a Dict (parsed JSON) or maybe raw string?
                # Based on council_service.py it returns a Dict.
                # If it returns a Dict, we just validate it.
                # If strict_mode is on, we might want to ask for raw string to handle parsing ourselves,
                # but let's start with the existing interface.
                
                raw_response = await self.llm_port.complete(
                    prompt=prompt,
                    model=model,
                    max_tokens=2000,
                    temperature=temperature
                )
                
                # Handle if raw_response is already a dict
                if isinstance(raw_response, dict):
                    data = raw_response
                elif isinstance(raw_response, str):
                    # Robust parsing for string output (e.g. markdown blocks)
                    data = self._parse_json_from_text(raw_response)
                else:
                    raise ValueError(f"Unexpected LLM response type: {type(raw_response)}")

                # 2. Validate against Schema
                return schema.model_validate(data)

            except (ValidationError, ValueError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"LLM Schema Validation Failed (Attempt {attempt+1}/{self.max_retries}): {e}")
                
                # Exponential backoff
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.base_delay * (2 ** attempt))
                
        # If we exhaust retries, raise the last error
        raise last_error

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from text, handling markdown blocks.
        """
        text = text.strip()
        
        # Strip markdown code blocks if present
        if text.startswith("```"):
            # Find first newline
            first_newline = text.find("\n")
            if first_newline == -1:
                # Malformed block?
                pass
            else:
                # Check if it specifies json
                # e.g. ```json
                # We essentially just want to remove the first line and the last line (```)
                text = text[first_newline+1:]
                if text.endswith("```"):
                    text = text[:-3]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find { ... }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
            raise
