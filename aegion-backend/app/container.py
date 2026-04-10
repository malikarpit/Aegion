"""
Aegion Dependency Injection Container.

Wires abstractions (ports) to concrete implementations (adapters).
Allows swapping implementations via environment variables.

Migration support:
- DATABASE_ADAPTER: firestore | postgres
- AUTH_ADAPTER: firebase | keycloak
- AI_ADAPTER: langgraph | custom
- EVENT_ADAPTER: inprocess | pubsub | kafka
"""

from typing import Optional, TypeVar, Generic
from enum import Enum
from functools import lru_cache

from .core.config import settings
from .core.logging import logger


class AdapterType(str, Enum):
    """Available adapter implementations."""
    # Database
    FIRESTORE = "firestore"
    POSTGRES = "postgres"
    
    # Auth
    FIREBASE = "firebase"
    KEYCLOAK = "keycloak"
    
    # AI
    LANGGRAPH = "langgraph"
    CUSTOM = "custom"
    
    # Events
    INPROCESS = "inprocess"
    PUBSUB = "pubsub"
    KAFKA = "kafka"


class Container:
    """
    Dependency Injection Container.
    Lazy-loads adapters based on configuration.
    """
    
    _instance: Optional["Container"] = None
    
    def __init__(self):
        self._database_adapter = None
        self._auth_adapter = None
        self._authorization_adapter = None
        self._ai_adapter = None
        self._event_adapter = None
        self._storage_adapter = None
        self._knowledge_graph = None
    
    @classmethod
    def get(cls) -> "Container":
        """Get singleton container instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    # ========== Database Adapters ==========
    
    @property
    def session_repository(self):
        """Get session repository."""
        adapter = getattr(settings, 'database_adapter', 'firestore')
        
        if adapter == 'firestore':
            from .adapters.firestore.session_repository import FirestoreSessionRepository
            if self._database_adapter is None:
                self._database_adapter = FirestoreSessionRepository()
            return self._database_adapter
        elif adapter == 'postgres':
            from .adapters.postgres import PostgresSessionRepository
            if self._database_adapter is None:
                self._database_adapter = PostgresSessionRepository()
            return self._database_adapter
        
        raise ValueError(f"Unknown database adapter: {adapter}")
    
    @property
    def knowledge_graph(self):
        """Get knowledge graph adapter."""
        adapter = getattr(settings, 'database_adapter', 'firestore')
        
        if adapter == 'postgres':
            from .adapters.postgres.postgres_graph import PostgresKnowledgeGraph
            if self._knowledge_graph is None:
                self._knowledge_graph = PostgresKnowledgeGraph()
            return self._knowledge_graph
            
        # Fallback to MemoryGraph
        from .adapters.memory_graph.graph import InMemoryKnowledgeGraph
        if self._knowledge_graph is None:
            self._knowledge_graph = InMemoryKnowledgeGraph()
        return self._knowledge_graph
    
    # ========== Auth Adapters ==========
    
    @property
    def auth(self):
        """Get authentication adapter."""
        adapter = getattr(settings, 'auth_adapter', 'firebase')
        
        if adapter == 'firebase':
            from .adapters.firebase.auth_adapter import FirebaseAuthAdapter
            if self._auth_adapter is None:
                self._auth_adapter = FirebaseAuthAdapter()
            return self._auth_adapter
        elif adapter == 'keycloak':
            from .adapters.keycloak import KeycloakAuthAdapter
            if self._auth_adapter is None:
                self._auth_adapter = KeycloakAuthAdapter()
            return self._auth_adapter
        
        raise ValueError(f"Unknown auth adapter: {adapter}")
    
    @property
    def authorization(self):
        """Get authorization adapter."""
        adapter = getattr(settings, 'auth_adapter', 'firebase')
        
        if adapter == 'firebase':
            from .adapters.firebase.auth_adapter import FirebaseAuthorizationAdapter
            if self._authorization_adapter is None:
                self._authorization_adapter = FirebaseAuthorizationAdapter()
            return self._authorization_adapter
        
        raise ValueError(f"Unknown auth adapter: {adapter}")
    
    # ========== AI Adapters ==========
    
    @property
    def ai_orchestrator(self):
        """Get AI orchestration adapter."""
        adapter = getattr(settings, 'ai_adapter', 'langgraph')
        
        if adapter == 'langgraph':
            from .adapters.langgraph.orchestrator import LangGraphOrchestrator
            if self._ai_adapter is None:
                self._ai_adapter = LangGraphOrchestrator()
            return self._ai_adapter
        elif adapter == 'custom':
            from .adapters.custom_ai import CustomAIOrchestrator
            if self._ai_adapter is None:
                self._ai_adapter = CustomAIOrchestrator()
            return self._ai_adapter
        
        raise ValueError(f"Unknown AI adapter: {adapter}")
    
    # ========== Event Adapters ==========
    
    @property
    def event_bus(self):
        """Get event bus adapter."""
        adapter = getattr(settings, 'event_adapter', 'inprocess')
        
        if adapter == 'inprocess':
            from .adapters.inprocess.event_bus import get_event_bus
            return get_event_bus()
        elif adapter == 'pubsub':
            from .adapters.pubsub.adapter import PubSubAdapter
            if self._event_adapter is None:
                self._event_adapter = PubSubAdapter()
            return self._event_adapter
        elif adapter == 'kafka':
            from .adapters.kafka import KafkaEventBusAdapter
            if self._event_adapter is None:
                self._event_adapter = KafkaEventBusAdapter()
            return self._event_adapter
        
        raise ValueError(f"Unknown event adapter: {adapter}")
    
    # ========== Storage Adapters ==========
    
    @property
    def storage(self):
        """Get storage adapter."""
        adapter = getattr(settings, 'storage_adapter', 'gcs')
        
        if adapter == 'gcs':
            from .adapters.gcs.storage_adapter import GCSStorageAdapter
            if self._storage_adapter is None:
                self._storage_adapter = GCSStorageAdapter()
            return self._storage_adapter
        elif adapter == 'local':
            from .adapters.local import LocalStorageAdapter
            if self._storage_adapter is None:
                self._storage_adapter = LocalStorageAdapter()
            return self._storage_adapter
        
        raise ValueError(f"Unknown storage adapter: {adapter}")


# Convenience function
def get_container() -> Container:
    """Get the DI container."""
    return Container.get()


# Shortcuts for common dependencies
def get_session_repository():
    return get_container().session_repository

def get_auth():
    return get_container().auth

def get_authorization():
    return get_container().authorization

def get_event_bus():
    return get_container().event_bus

def get_ai_orchestrator():
    return get_container().ai_orchestrator

def get_storage():
    return get_container().storage

def get_knowledge_graph():
    return get_container().knowledge_graph
