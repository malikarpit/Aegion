"""
Aegion Custom AI Orchestrator Adapter.

Phase 5: Pluggable AI orchestration for custom model integration.
Supports OpenAI, Anthropic, local models, and custom endpoints.
"""

from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json

from ...core.logging import logger


class AIProvider(str, Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"
    CUSTOM = "custom"


@dataclass
class AIConfig:
    """AI orchestrator configuration."""
    provider: AIProvider = AIProvider.OPENAI
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model: str = "gpt-4"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class AIMessage:
    """Message in a conversation."""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    """AI response."""
    content: str
    model: str
    provider: AIProvider
    usage: Dict[str, int]  # tokens used
    finish_reason: str
    latency_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIProviderInterface(ABC):
    """Abstract interface for AI providers."""
    
    @abstractmethod
    async def complete(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AIResponse:
        """Generate completion."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        pass


class OpenAIProvider(AIProviderInterface):
    """OpenAI provider implementation."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize OpenAI client."""
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout
            )
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
    
    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate completion using OpenAI."""
        start = datetime.now(timezone.utc)
        
        response = await self._client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
        )
        
        end = datetime.now(timezone.utc)
        latency_ms = int((end - start).total_seconds() * 1000)
        
        return AIResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider=AIProvider.OPENAI,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency_ms
        )
    
    async def stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Stream completion from OpenAI."""
        response = await self._client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True,
        )
        
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicProvider(AIProviderInterface):
    """Anthropic (Claude) provider implementation."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize Anthropic client."""
        try:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout
            )
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    
    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate completion using Anthropic."""
        start = datetime.now(timezone.utc)
        
        # Extract system message
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                conv_messages.append({"role": m.role, "content": m.content})
        
        response = await self._client.messages.create(
            model=kwargs.get("model", self.config.model),
            system=system_msg,
            messages=conv_messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        
        end = datetime.now(timezone.utc)
        latency_ms = int((end - start).total_seconds() * 1000)
        
        return AIResponse(
            content=response.content[0].text,
            model=response.model,
            provider=AIProvider.ANTHROPIC,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            latency_ms=latency_ms
        )
    
    async def stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Stream completion from Anthropic."""
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                conv_messages.append({"role": m.role, "content": m.content})
        
        async with self._client.messages.stream(
            model=kwargs.get("model", self.config.model),
            system=system_msg,
            messages=conv_messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        ) as stream:
            async for text in stream.text_stream:
                yield text


class CustomEndpointProvider(AIProviderInterface):
    """Custom endpoint provider for self-hosted models."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._http_client = None
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        try:
            import httpx
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers=self.config.custom_headers
            )
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx")
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
    
    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate completion using custom endpoint."""
        start = datetime.now(timezone.utc)
        
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        response = await self._http_client.post(
            f"{self.config.api_base}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        )
        
        response.raise_for_status()
        data = response.json()
        
        end = datetime.now(timezone.utc)
        latency_ms = int((end - start).total_seconds() * 1000)
        
        return AIResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", self.config.model),
            provider=AIProvider.CUSTOM,
            usage=data.get("usage", {}),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            latency_ms=latency_ms
        )
    
    async def stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Stream completion from custom endpoint."""
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }
        
        async with self._http_client.stream(
            "POST",
            f"{self.config.api_base}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


class CustomAIOrchestrator:
    """
    Custom AI orchestrator with multi-provider support.
    
    Doctrine: "Choose the best mind for the task."
    """
    
    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or AIConfig()
        self._providers: Dict[AIProvider, AIProviderInterface] = {}
        self._default_provider: Optional[AIProviderInterface] = None
    
    async def initialize(self) -> None:
        """Initialize the default provider."""
        provider = await self._get_or_create_provider(self.config.provider)
        self._default_provider = provider
        logger.info(f"Custom AI orchestrator initialized with {self.config.provider.value}")
    
    async def close(self) -> None:
        """Close all providers."""
        for provider in self._providers.values():
            if hasattr(provider, 'close'):
                await provider.close()
        self._providers.clear()
    
    async def _get_or_create_provider(
        self,
        provider_type: AIProvider
    ) -> AIProviderInterface:
        """Get or create a provider instance."""
        if provider_type in self._providers:
            return self._providers[provider_type]
        
        if provider_type == AIProvider.OPENAI:
            provider = OpenAIProvider(self.config)
        elif provider_type == AIProvider.ANTHROPIC:
            provider = AnthropicProvider(self.config)
        elif provider_type in (AIProvider.CUSTOM, AIProvider.LOCAL):
            provider = CustomEndpointProvider(self.config)
        else:
            raise ValueError(f"Unsupported provider: {provider_type}")
        
        await provider.initialize()
        self._providers[provider_type] = provider
        return provider
    
    async def complete(
        self,
        messages: List[AIMessage],
        provider: Optional[AIProvider] = None,
        **kwargs
    ) -> AIResponse:
        """Generate completion."""
        target_provider = self._default_provider
        if provider:
            target_provider = await self._get_or_create_provider(provider)
        
        return await target_provider.complete(messages, **kwargs)
    
    async def stream(
        self,
        messages: List[AIMessage],
        provider: Optional[AIProvider] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        target_provider = self._default_provider
        if provider:
            target_provider = await self._get_or_create_provider(provider)
        
        async for chunk in target_provider.stream(messages, **kwargs):
            yield chunk
    
    async def council_deliberate(
        self,
        context: str,
        question: str,
        council_members: List[str] = None
    ) -> AIResponse:
        """Have the AI Council deliberate on a question."""
        council_members = council_members or ["Architect", "Developer", "Critic"]
        
        system_prompt = f"""You are an AI Council with the following members: {', '.join(council_members)}.
        
Each member should provide their perspective on the question.
Format your response with clear sections for each member's input.
At the end, provide a synthesized recommendation.

Context:
{context}
"""
        
        messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="user", content=question)
        ]
        
        return await self.complete(messages)


# Factory function
def create_custom_ai_orchestrator(config: Optional[AIConfig] = None) -> CustomAIOrchestrator:
    """Create custom AI orchestrator instance."""
    return CustomAIOrchestrator(config)
