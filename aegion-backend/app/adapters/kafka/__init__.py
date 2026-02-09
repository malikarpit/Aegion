"""
Aegion Kafka Adapter Module.

Phase 5: Kafka event bus for high-throughput scenarios.
"""

from .event_bus import KafkaEventBusAdapter, KafkaConfig, KafkaMessage, create_kafka_adapter

__all__ = [
    "KafkaEventBusAdapter",
    "KafkaConfig",
    "KafkaMessage",
    "create_kafka_adapter",
]
