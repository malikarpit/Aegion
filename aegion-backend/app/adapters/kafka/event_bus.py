"""
Aegion Kafka Event Bus Adapter.

Phase 5: Kafka-based event streaming for high-throughput scenarios.
Alternative to Pub/Sub for on-premise or Kafka-preferred deployments.
"""

from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass, field
import json
import asyncio

from ...core.logging import logger


@dataclass
class KafkaConfig:
    """Kafka connection configuration."""
    bootstrap_servers: str = "localhost:9092"
    client_id: str = "aegion-backend"
    group_id: str = "aegion-consumers"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    security_protocol: str = "PLAINTEXT"  # PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
    sasl_mechanism: Optional[str] = None  # PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None


@dataclass
class KafkaMessage:
    """Kafka message representation."""
    topic: str
    key: Optional[str]
    value: Dict[str, Any]
    partition: Optional[int] = None
    offset: Optional[int] = None
    timestamp: Optional[datetime] = None
    headers: Dict[str, str] = field(default_factory=dict)


EventHandler = Callable[[KafkaMessage], Awaitable[None]]


class KafkaEventBusAdapter:
    """
    Kafka event bus adapter.
    
    Provides high-throughput event streaming via Apache Kafka.
    
    Doctrine: "Events flow at scale."
    """
    
    def __init__(self, config: Optional[KafkaConfig] = None):
        self.config = config or KafkaConfig()
        self._producer = None
        self._consumers: Dict[str, Any] = {}
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []
    
    async def connect(self) -> None:
        """Initialize Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            
            producer_config = {
                "bootstrap_servers": self.config.bootstrap_servers,
                "client_id": self.config.client_id,
                "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
                "key_serializer": lambda k: k.encode("utf-8") if k else None,
            }
            
            # Add security config if needed
            if self.config.security_protocol != "PLAINTEXT":
                producer_config["security_protocol"] = self.config.security_protocol
                if self.config.sasl_mechanism:
                    producer_config["sasl_mechanism"] = self.config.sasl_mechanism
                    producer_config["sasl_plain_username"] = self.config.sasl_username
                    producer_config["sasl_plain_password"] = self.config.sasl_password
            
            self._producer = AIOKafkaProducer(**producer_config)
            await self._producer.start()
            
            logger.info(f"Connected to Kafka at {self.config.bootstrap_servers}")
        except ImportError:
            raise ImportError("aiokafka package not installed. Run: pip install aiokafka")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close all connections."""
        self._running = False
        
        # Stop consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Close consumers
        for consumer in self._consumers.values():
            await consumer.stop()
        self._consumers.clear()
        
        # Close producer
        if self._producer:
            await self._producer.stop()
            self._producer = None
        
        logger.info("Disconnected from Kafka")
    
    # ========== Publishing ==========
    
    async def publish(
        self,
        topic: str,
        event: Dict[str, Any],
        key: Optional[str] = None,
        partition: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Publish an event to a topic."""
        if not self._producer:
            logger.warning("Producer not connected")
            return False
        
        try:
            # Add metadata
            event_with_meta = {
                **event,
                "_published_at": datetime.now(timezone.utc).isoformat(),
                "_topic": topic,
            }
            
            # Convert headers
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]
            
            await self._producer.send_and_wait(
                topic,
                value=event_with_meta,
                key=key,
                partition=partition,
                headers=kafka_headers
            )
            
            logger.debug(f"Published event to {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            return False
    
    async def publish_batch(
        self,
        topic: str,
        events: List[Dict[str, Any]],
        key_extractor: Optional[Callable[[Dict], str]] = None
    ) -> int:
        """Publish multiple events to a topic."""
        if not self._producer:
            return 0
        
        success_count = 0
        for event in events:
            key = key_extractor(event) if key_extractor else None
            if await self.publish(topic, event, key):
                success_count += 1
        
        return success_count
    
    # ========== Subscribing ==========
    
    async def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        group_id: Optional[str] = None
    ) -> None:
        """Subscribe to a topic with a handler."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        
        # Create consumer if not exists
        if topic not in self._consumers:
            await self._create_consumer(topic, group_id or self.config.group_id)
    
    async def _create_consumer(self, topic: str, group_id: str) -> None:
        """Create a consumer for a topic."""
        try:
            from aiokafka import AIOKafkaConsumer
            
            consumer_config = {
                "bootstrap_servers": self.config.bootstrap_servers,
                "group_id": group_id,
                "auto_offset_reset": self.config.auto_offset_reset,
                "enable_auto_commit": self.config.enable_auto_commit,
                "value_deserializer": lambda v: json.loads(v.decode("utf-8")),
                "key_deserializer": lambda k: k.decode("utf-8") if k else None,
            }
            
            # Add security config
            if self.config.security_protocol != "PLAINTEXT":
                consumer_config["security_protocol"] = self.config.security_protocol
                if self.config.sasl_mechanism:
                    consumer_config["sasl_mechanism"] = self.config.sasl_mechanism
                    consumer_config["sasl_plain_username"] = self.config.sasl_username
                    consumer_config["sasl_plain_password"] = self.config.sasl_password
            
            consumer = AIOKafkaConsumer(topic, **consumer_config)
            await consumer.start()
            self._consumers[topic] = consumer
            
            # Start consumer loop
            task = asyncio.create_task(self._consume_loop(topic, consumer))
            self._consumer_tasks.append(task)
            
            logger.info(f"Subscribed to Kafka topic: {topic}")
        except Exception as e:
            logger.error(f"Failed to create consumer for {topic}: {e}")
            raise
    
    async def _consume_loop(self, topic: str, consumer) -> None:
        """Consumer loop for a topic."""
        self._running = True
        
        try:
            async for msg in consumer:
                if not self._running:
                    break
                
                kafka_message = KafkaMessage(
                    topic=msg.topic,
                    key=msg.key,
                    value=msg.value,
                    partition=msg.partition,
                    offset=msg.offset,
                    timestamp=datetime.fromtimestamp(msg.timestamp / 1000) if msg.timestamp else None,
                    headers={k: v.decode("utf-8") for k, v in (msg.headers or [])}
                )
                
                # Dispatch to handlers
                handlers = self._handlers.get(topic, [])
                for handler in handlers:
                    try:
                        await handler(kafka_message)
                    except Exception as e:
                        logger.error(f"Handler error for {topic}: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Consumer loop error for {topic}: {e}")
    
    # ========== Topic Management ==========
    
    async def create_topic(
        self,
        topic: str,
        num_partitions: int = 3,
        replication_factor: int = 1
    ) -> bool:
        """Create a topic (requires admin privileges)."""
        try:
            from aiokafka.admin import AIOKafkaAdminClient, NewTopic
            
            admin = AIOKafkaAdminClient(
                bootstrap_servers=self.config.bootstrap_servers
            )
            await admin.start()
            
            try:
                new_topic = NewTopic(
                    name=topic,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor
                )
                await admin.create_topics([new_topic])
                logger.info(f"Created Kafka topic: {topic}")
                return True
            except Exception as e:
                if "TopicExistsException" in str(e):
                    logger.debug(f"Topic {topic} already exists")
                    return True
                raise
            finally:
                await admin.close()
        except Exception as e:
            logger.error(f"Failed to create topic {topic}: {e}")
            return False
    
    async def list_topics(self) -> List[str]:
        """List all topics."""
        try:
            from aiokafka.admin import AIOKafkaAdminClient
            
            admin = AIOKafkaAdminClient(
                bootstrap_servers=self.config.bootstrap_servers
            )
            await admin.start()
            
            try:
                topics = await admin.list_topics()
                return [t for t in topics if not t.startswith("_")]
            finally:
                await admin.close()
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    # ========== Health Check ==========
    
    async def health_check(self) -> bool:
        """Check Kafka connectivity."""
        if not self._producer:
            return False
        
        try:
            # Try to get cluster metadata
            await self._producer.client.fetch_all_metadata()
            return True
        except Exception:
            return False


# Factory function
def create_kafka_adapter(config: Optional[KafkaConfig] = None) -> KafkaEventBusAdapter:
    """Create Kafka adapter instance."""
    return KafkaEventBusAdapter(config)
