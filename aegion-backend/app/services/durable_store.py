"""
Aegion Durable Store — PostgreSQL Backend.

Phase 5: Replaces file-based JsonFileStore with Supabase PostgreSQL kv_store table.
Maintains the same interface so callers don't need changing.

Doctrine: "Data survives crashes. Writes are atomic. Sessions are never lost."

The kv_store table provides namespaced key-value storage backed by PostgreSQL.
All data is workspace-scoped for multi-tenant isolation.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar
from datetime import datetime, timezone
from pydantic import BaseModel

from ..db.supabase_client import get_supabase_client
from ..core.logging import logger

T = TypeVar("T", bound=BaseModel)


class PostgresKVStore:
    """
    PostgreSQL-backed key-value store replacing JsonFileStore.

    Uses the kv_store table (from migration 20260409000001_durable_store.sql).
    Maintains a compatible interface with the original JsonFileStore so callers
    can be migrated with minimal disruption.
    """

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._client = get_supabase_client()

    async def set(
        self,
        key: str,
        value: dict,
        workspace_id: str = "default",
    ) -> None:
        """Upsert a key-value pair for a workspace/namespace."""
        existing = (
            self._client.table("kv_store")
            .select("id")
            .eq("workspace_id", workspace_id)
            .eq("namespace", self.namespace)
            .eq("key", key)
            .execute()
        )

        if existing.data:
            self._client.table("kv_store").update(
                {"value": value, "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", existing.data[0]["id"]).execute()
        else:
            self._client.table("kv_store").insert(
                {
                    "workspace_id": workspace_id,
                    "namespace": self.namespace,
                    "key": key,
                    "value": value,
                }
            ).execute()

    async def get(self, key: str, workspace_id: str = "default") -> Optional[dict]:
        """Retrieve a value by key."""
        result = (
            self._client.table("kv_store")
            .select("value")
            .eq("workspace_id", workspace_id)
            .eq("namespace", self.namespace)
            .eq("key", key)
            .execute()
        )
        if result.data:
            return result.data[0]["value"]
        return None

    async def delete(self, key: str, workspace_id: str = "default") -> bool:
        """Delete a key-value pair."""
        self._client.table("kv_store").delete().eq(
            "workspace_id", workspace_id
        ).eq("namespace", self.namespace).eq("key", key).execute()
        return True

    async def list_keys(self, workspace_id: str = "default") -> List[str]:
        """List all keys for a workspace/namespace."""
        result = (
            self._client.table("kv_store")
            .select("key")
            .eq("workspace_id", workspace_id)
            .eq("namespace", self.namespace)
            .execute()
        )
        return [r["key"] for r in result.data]

    async def list_all(self, workspace_id: str = "default") -> List[dict]:
        """List all values for a workspace/namespace."""
        result = (
            self._client.table("kv_store")
            .select("key, value")
            .eq("workspace_id", workspace_id)
            .eq("namespace", self.namespace)
            .execute()
        )
        return result.data


class PostgresModelStore(PostgresKVStore):
    """
    Typed model store backed by PostgreSQL.

    Provides the same typed save/load interface as JsonFileStore,
    making it a drop-in replacement for callers using Pydantic models.
    """

    def __init__(self, namespace: str, model_class: Type[T], key_field: str):
        super().__init__(namespace=namespace)
        self.model_class = model_class
        self.key_field = key_field

    async def save(self, item: T, workspace_id: str = "default") -> T:
        """Save a Pydantic model instance."""
        # Infer workspace_id from item if present
        if hasattr(item, "workspace_id") and getattr(item, "workspace_id"):
            workspace_id = str(getattr(item, "workspace_id"))
        key = str(getattr(item, self.key_field))
        await self.set(key, item.model_dump(mode="json"), workspace_id)
        return item

    async def get(self, key: str, workspace_id: str = "default") -> Optional[T]:
        """Load a Pydantic model instance by key."""
        data = await super().get(key, workspace_id)
        if data is None:
            return None
        return self.model_class.model_validate(data)

    async def list_all(self, workspace_id: str = "default") -> List[T]:
        """Load all model instances for a workspace."""
        rows = await super().list_all(workspace_id)
        results = []
        for row in rows:
            try:
                results.append(self.model_class.model_validate(row["value"]))
            except Exception as e:
                logger.warning(f"Failed to deserialize {self.namespace}/{row['key']}: {e}")
        return results

    async def remove(self, key: str, workspace_id: str = "default") -> bool:
        """Remove a model instance by key."""
        return await super().delete(key, workspace_id)


# ─── Legacy shim ────────────────────────────────────────────────────────────
# JsonFileStore is kept as a class alias for backward compatibility.
# Existing imports of `from durable_store import JsonFileStore` continue
# to work but now back data to PostgreSQL instead of disk.
# The file_path and auto_flush_interval arguments are silently ignored.

class JsonFileStore(PostgresModelStore):
    """
    Backward-compatible shim over PostgresModelStore.

    Existing callers that do:
        JsonFileStore(".aegion_data/sessions.json", Session, "session_id")
    will continue to work — the file_path is ignored; data goes to PostgreSQL.
    """

    def __init__(
        self,
        file_path: str,
        model_class: Type[T],
        key_field: str,
        auto_flush_interval: float = 30.0,  # Ignored — no file to flush
    ):
        # Derive a namespace from the file path stem (e.g. "sessions" from "sessions.json")
        import os
        stem = os.path.splitext(os.path.basename(file_path))[0]
        super().__init__(namespace=stem, model_class=model_class, key_field=key_field)
        logger.info(
            f"JsonFileStore: migrated '{file_path}' → PostgreSQL namespace '{stem}'"
        )
