"""
Aegion Chaos Engineering Service.

Doctrine: "If it hurts, do it more often."

Provides:
- Controlled injection of latency and failures
- Decorators for resilience testing
- Configuration to enable/disable chaos dynamically
"""

import asyncio
import random
import time
from functools import wraps
from typing import Optional, Type, List

# Handle imports for both app context and standalone verification
try:
    from ...core.logging import logger
except (ImportError, ValueError):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ChaosMonkey")

class ChaosConfiguration:
    enabled: bool = False
    default_probability: float = 0.1
    default_latency_ms: int = 100
    allowed_exceptions: List[Type[Exception]] = [TimeoutError, ConnectionError, RuntimeError]

_config = ChaosConfiguration()

def set_chaos_config(enabled: bool = False, probability: float = 0.1, latency_ms: int = 100):
    _config.enabled = enabled
    _config.default_probability = probability
    _config.default_latency_ms = latency_ms
    logger.warning(f"Chaos Monkey configuration updated: enabled={enabled}, prob={probability}")

class ChaosMonkey:
    """
    Agent of chaos. Randomly disrupts operations.
    """
    
    @staticmethod
    async def maybe_inject_chaos(probability: Optional[float] = None, latency_ms: Optional[int] = None):
        if not _config.enabled:
            return

        prob = probability if probability is not None else _config.default_probability
        
        if random.random() < prob:
            await ChaosMonkey._unleash_chaos(latency_ms)

    @staticmethod
    async def _unleash_chaos(latency_ms: Optional[int] = None):
        action = random.choice(["latency", "failure"])
        
        if action == "latency":
            ms = latency_ms if latency_ms is not None else _config.default_latency_ms
            logger.info(f"🐒 Chaos Monkey injecting {ms}ms latency")
            await asyncio.sleep(ms / 1000.0)
        elif action == "failure":
             exception_type = random.choice(_config.allowed_exceptions)
             logger.error(f"🐒 Chaos Monkey injecting failure: {exception_type.__name__}")
             raise exception_type("Chaos Monkey struck!")

def chaos_monkey(probability: float = 0.1, latency_ms: int = 100):
    """Decorator to inject chaos into async functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if _config.enabled and random.random() < probability:
                action = random.choice(["latency", "failure"])
                
                if action == "latency":
                    logger.info(f"🐒 Chaos Monkey injecting {latency_ms}ms latency into {func.__name__}")
                    await asyncio.sleep(latency_ms / 1000.0)
                else:
                    exception_type = random.choice(_config.allowed_exceptions)
                    logger.error(f"🐒 Chaos Monkey injecting {exception_type.__name__} into {func.__name__}")
                    raise exception_type(f"Chaos Monkey disruption in {func.__name__}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
