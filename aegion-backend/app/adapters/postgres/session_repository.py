"""
Aegion PostgreSQL Session Repository.

Phase 5: PostgreSQL Adapter for relational session/decision storage.
Alternative to Firestore for on-premise or RDBMS-preferred deployments.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import json

from ...ports.database import SessionRepositoryPort
from ...domain.session import Session
from ...core.logging import logger
from ...core.time import TimeAuthority


@dataclass
class PostgresConfig:
    """PostgreSQL connection configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "aegion"
    user: str = "aegion"
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10


class PostgresSessionRepository(SessionRepositoryPort):
    """
    PostgreSQL implementation of session repository.
    Provides relational storage for sessions.
    """
    
    def __init__(self, config: Optional[PostgresConfig] = None):
        self.config = config or PostgresConfig()
        self._pool = None
    
    async def connect(self) -> None:
        """Establish connection pool."""
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections
            )
            logger.info(f"Connected to PostgreSQL at {self.config.host}:{self.config.port}")
            
            # Initialize schema
            await self._init_schema()
        except ImportError:
            raise ImportError("asyncpg package not installed. Run: pip install asyncpg")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Disconnected from PostgreSQL")
    
    async def _init_schema(self) -> None:
        """Initialize database schema."""
        async with self._pool.acquire() as conn:
            # We assume valid UUIDs for session_id
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id UUID PRIMARY KEY,
                    workspace_id UUID NOT NULL,
                    owner_id VARCHAR(255) NOT NULL,
                    status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity_at TIMESTAMP,
                    closed_at TIMESTAMP,
                    distilled_at TIMESTAMP,
                    context_hash TEXT,
                    reasoning_phase JSONB DEFAULT '{}',
                    metadata JSONB DEFAULT '{}'
                );
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_sessions_workspace ON sessions(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(owner_id);
            """)
    
    async def create(self, entity: Session) -> Session:
        """Create a new session."""
        async with self._pool.acquire() as conn:
            # We map Session fields to columns
            await conn.execute("""
                INSERT INTO sessions (
                    session_id, workspace_id, owner_id, status, 
                    created_at, last_activity_at, closed_at, distilled_at,
                    context_hash, reasoning_phase, metadata
                )
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb)
            """, 
            entity.session_id, 
            entity.workspace_id, 
            entity.owner_id, 
            entity.status,
            entity.created_at,
            entity.last_activity_at,
            entity.closed_at,
            entity.distilled_at,
            entity.context_hash,
            json.dumps(entity.reasoning_phase),
            json.dumps(entity.metadata)
            )
            
            return entity

    async def get_by_id(self, entity_id: str) -> Optional[Session]:
        """Get session by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE session_id = $1::uuid",
                entity_id
            )
            if row:
                return self._map_row_to_session(row)
            return None

    def _map_row_to_session(self, row) -> Session:
        """Helper to map PG row to Session domain model."""
        data = dict(row)
        # Convert UUIDs to strings if necessary (asyncpg returns UUID objects)
        data['session_id'] = str(data['session_id'])
        data['workspace_id'] = str(data['workspace_id'])
        
        # JSONB fields are returned as strings or dicts depending on asyncpg config.
        # Assuming we need to parse if string
        if isinstance(data.get('reasoning_phase'), str):
             data['reasoning_phase'] = json.loads(data['reasoning_phase'])
        if isinstance(data.get('metadata'), str):
             data['metadata'] = json.loads(data['metadata'])
             
        return Session.model_validate(data)

    async def update(self, entity_id: str, data: Dict[str, Any]) -> Session:
        """Partial update — only allows explicitly whitelisted columns to be updated."""
        # Allowlist of columns that may be mutated via this method.
        # Rejects any key not on this list to prevent SQL injection or
        # accidental update of immutable fields (e.g. session_id, workspace_id).
        MUTABLE_COLUMNS = {
            "status",
            "last_activity_at",
            "closed_at",
            "distilled_at",
            "context_hash",
            "reasoning_phase",
            "metadata",
        }

        unknown = set(data.keys()) - MUTABLE_COLUMNS
        if unknown:
            raise ValueError(
                f"Attempt to update disallowed session fields: {unknown}. "
                f"Permitted fields: {MUTABLE_COLUMNS}"
            )

        if not data:
            # Nothing to update; return current state
            return await self.get_by_id(entity_id)

        # Dynamic SQL update using parameterised placeholders — safe against injection
        set_clauses = []
        values = []
        idx = 1

        for key, value in data.items():
            if key in ('reasoning_phase', 'metadata'):
                value = json.dumps(value)
                set_clauses.append(f"{key} = ${idx}::jsonb")
            else:
                set_clauses.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1

        values.append(entity_id)

        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                UPDATE sessions 
                SET {', '.join(set_clauses)}
                WHERE session_id = ${idx}::uuid
            """, *values)

        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: str) -> bool:
        """Delete session."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE session_id = $1::uuid",
                entity_id
            )
            return "DELETE 1" in result

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Session]:
        """List sessions."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM sessions 
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)
            
            return [self._map_row_to_session(row) for row in rows]

    async def get_active_by_user(self, user_id: str) -> Optional[Session]:
        """Get active session for user."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM sessions 
                WHERE owner_id = $1 AND status = 'active'
                LIMIT 1
            """, user_id)
            if row:
                return self._map_row_to_session(row)
            return None

    async def close_session(self, session_id: str) -> Session:
        """Close session."""
        closed_at = TimeAuthority.now()
        return await self.update(session_id, {
            "status": "closed",
            "closed_at": closed_at
        })

    async def distill_session(self, session_id: str) -> Session:
        """Distill session."""
        distilled_at = TimeAuthority.now()
        return await self.update(session_id, {
            "status": "distilled",
            "distilled_at": distilled_at
        })

# Factory function
def create_postgres_repository(config: Optional[PostgresConfig] = None) -> PostgresSessionRepository:
    """Create PostgreSQL repository instance."""
    return PostgresSessionRepository(config)
