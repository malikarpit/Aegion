"""
Aegion Adapters - Local Artifact Log.

Replaces FirestoreArtifactLog with a local-first implementation.
Stores artifacts in-memory with optional Supabase persistence.
Matches the same interface as FirestoreArtifactLog (store/retrieve/list_by_*).
"""

import json
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class LocalArtifactLog:
    """
    Local artifact storage implementation.

    Primary: in-memory dict.
    Secondary: Supabase `kv_store` table (if available).
    """

    NAMESPACE = "artifacts"

    def __init__(self):
        self._store: Dict[str, dict] = {}

    def _supabase_client(self):
        """Lazily try to get Supabase client; return None if unavailable."""
        try:
            from ..db.supabase_client import get_supabase_client
            return get_supabase_client()
        except Exception:
            return None

    async def store(self, key: str, content: bytes, content_type: str) -> None:
        """
        Store artifact content.

        Key format: "artifacts/{type}/{id}"
        """
        parts = key.split("/")
        artifact_id = parts[-1]
        artifact_type = parts[-2] if len(parts) > 1 else "unknown"

        entry = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "content_type": content_type,
            "path": key,
        }

        if content_type == "application/json":
            entry["data"] = content.decode("utf-8")
        else:
            import base64
            entry["blob_b64"] = base64.b64encode(content).decode("ascii")

        # In-memory primary
        self._store[key] = entry

        # Supabase secondary (non-blocking)
        client = self._supabase_client()
        if client:
            try:
                client.table("kv_store").upsert({
                    "workspace_id": "global",
                    "namespace": self.NAMESPACE,
                    "key": key,
                    "value": entry,
                }, on_conflict="workspace_id,namespace,key").execute()
            except Exception as exc:
                logger.debug(f"Artifact supabase persist failed (non-fatal): {exc}")

    async def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve artifact content."""
        # Try in-memory first
        entry = self._store.get(key)

        # Fallback to Supabase
        if not entry:
            client = self._supabase_client()
            if client:
                try:
                    result = client.table("kv_store").select("value").eq(
                        "namespace", self.NAMESPACE
                    ).eq("key", key).execute()
                    if result.data:
                        entry = result.data[0].get("value", {})
                        self._store[key] = entry  # Cache locally
                except Exception:
                    pass

        if not entry:
            return None

        if "data" in entry:
            return entry["data"].encode("utf-8")
        elif "blob_b64" in entry:
            import base64
            return base64.b64decode(entry["blob_b64"])

        return None

    async def list_by_owner(self, owner_id: str, limit: int = 50) -> list:
        """List artifacts owned by a user."""
        results = []
        for entry in self._store.values():
            if entry.get("type") == "sessions":
                try:
                    data = entry.get("data")
                    if data:
                        parsed = json.loads(data) if isinstance(data, str) else data
                        if parsed.get("owner_id") == owner_id:
                            results.append(parsed)
                except (json.JSONDecodeError, KeyError):
                    continue
            if len(results) >= limit:
                break
        return results

    async def list_by_workspace(self, workspace_id: str, limit: int = 50) -> list:
        """List artifacts for a workspace."""
        results = []
        for entry in self._store.values():
            if entry.get("type") == "sessions":
                try:
                    data = entry.get("data")
                    if data:
                        parsed = json.loads(data) if isinstance(data, str) else data
                        if parsed.get("workspace_id") == workspace_id:
                            results.append(parsed)
                except (json.JSONDecodeError, KeyError):
                    continue
            if len(results) >= limit:
                break
        return results
