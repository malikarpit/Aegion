"""
Aegion Cloud Pub/Sub Event Adapter.

Implements EventBusPort using Google Cloud Pub/Sub.
Enables distributed event processing across services.

Doctrine: "Events are facts, not commands."
"""

from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone
import json
import asyncio

from google.cloud import pubsub_v1
from google.api_core import exceptions as gcp_exceptions

from ...ports.events import EventBusPort, EventMessage, EventSubscription
from ...core.logging import logger
from ...core.config import settings


class PubSubAdapter(EventBusPort):
    """
    Cloud Pub/Sub implementation of EventBusPort.
    
    Topics:
    - aegion.workspace.{workspace_id}
    - aegion.proposal.{proposal_id}
    - aegion.decision.{decision_id}
    - aegion.session.{session_id}
    """
    
    def __init__(self, project_id: str = None):
        self.project_id = project_id or settings.gcp_project_id
        self._publisher = None
        self._subscriber = None
        self._subscriptions: Dict[str, pubsub_v1.subscriber.futures.StreamingPullFuture] = {}
        self._handlers: Dict[str, List[Callable]] = {}
    
    @property
    def publisher(self) -> pubsub_v1.PublisherClient:
        if self._publisher is None:
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher
    
    @property
    def subscriber(self) -> pubsub_v1.SubscriberClient:
        if self._subscriber is None:
            self._subscriber = pubsub_v1.SubscriberClient()
        return self._subscriber
    
    def _topic_path(self, topic: str) -> str:
        """Get full topic path."""
        return self.publisher.topic_path(self.project_id, topic)
    
    def _subscription_path(self, subscription: str) -> str:
        """Get full subscription path."""
        return self.subscriber.subscription_path(self.project_id, subscription)
    
    async def publish(self, topic: str, message: EventMessage) -> str:
        """
        Publish event to topic.
        Returns message ID.
        """
        topic_path = self._topic_path(topic)
        
        # Serialize message
        data = json.dumps({
            "event_id": message.event_id,
            "event_type": message.event_type,
            "payload": message.payload,
            "metadata": message.metadata,
            "timestamp": message.timestamp.isoformat(),
        }).encode("utf-8")
        
        # Publish with attributes
        future = self.publisher.publish(
            topic_path,
            data,
            event_type=message.event_type,
            event_id=message.event_id,
        )
        
        message_id = future.result()
        
        logger.info(
            f"Published event {message.event_type} to {topic}",
            event_id=message.event_id,
            message_id=message_id
        )
        
        return message_id
    
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[EventMessage], None],
        subscription_id: str = None
    ) -> EventSubscription:
        """
        Subscribe to topic with handler.
        Creates subscription if not exists.
        """
        subscription_id = subscription_id or f"{topic}-{settings.instance_id}"
        subscription_path = self._subscription_path(subscription_id)
        topic_path = self._topic_path(topic)
        
        # Create subscription if not exists
        try:
            self.subscriber.create_subscription(
                request={
                    "name": subscription_path,
                    "topic": topic_path,
                    "ack_deadline_seconds": 60,
                }
            )
            logger.info(f"Created subscription {subscription_id}")
        except gcp_exceptions.AlreadyExists:
            pass  # Subscription exists
        
        # Track handler
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        
        # Start streaming pull
        def callback(message: pubsub_v1.subscriber.message.Message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                event = EventMessage(
                    event_id=data["event_id"],
                    event_type=data["event_type"],
                    payload=data["payload"],
                    metadata=data.get("metadata", {}),
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                )
                
                # Call all handlers for this topic
                for h in self._handlers.get(topic, []):
                    h(event)
                
                message.ack()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                message.nack()
        
        streaming_pull_future = self.subscriber.subscribe(
            subscription_path, callback=callback
        )
        self._subscriptions[subscription_id] = streaming_pull_future
        
        return EventSubscription(
            subscription_id=subscription_id,
            topic=topic,
            created_at=datetime.now(timezone.utc)
        )
    
    async def unsubscribe(self, subscription_id: str) -> None:
        """Cancel subscription."""
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id].cancel()
            del self._subscriptions[subscription_id]
            logger.info(f"Cancelled subscription {subscription_id}")
    
    async def acknowledge(self, subscription_id: str, message_id: str) -> None:
        """Acknowledge message (handled automatically in callback)."""
        pass  # Ack is done in callback
    
    def close(self) -> None:
        """Close all connections."""
        for sub_id, future in self._subscriptions.items():
            future.cancel()
        self._subscriptions.clear()
        
        if self._publisher:
            self._publisher.transport.close()
        if self._subscriber:
            self._subscriber.close()


# Factory function
def create_pubsub_adapter() -> PubSubAdapter:
    """Create Pub/Sub adapter instance."""
    return PubSubAdapter()
