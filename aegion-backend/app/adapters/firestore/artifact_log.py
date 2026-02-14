"""
Aegion Adapters - Firestore Artifact Log.

Implements storage for immutable Chronos artifacts.
"""

from typing import Optional
from google.cloud import firestore
import base64

class FirestoreArtifactLog:
    """
    Firestore implementation of artifact storage.
    
    Mapping:
    Key: "artifacts/sessions/{hash}" -> Collection: "artifacts", Doc: "{hash}"
    """
    
    COLLECTION = "artifacts"

    def __init__(self, db: firestore.AsyncClient = None):
        self._db = db

    @property
    def db(self) -> firestore.AsyncClient:
        if self._db is None:
            self._db = firestore.AsyncClient()
        return self._db

    async def store(self, key: str, content: bytes, content_type: str) -> None:
        """
        Store artifact content.
        
        Key format: "artifacts/{type}/{id}"
        """
        # Split key to get ID and type context
        parts = key.split("/")
        artifact_id = parts[-1]
        artifact_type = parts[-2] if len(parts) > 1 else "unknown"
        
        # In a real BLOB store we'd write to GCS/S3.
        # For Firestore, we store as a document with a blob field if small,
        # or string field if JSON.    
        
        doc_data = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "content_type": content_type,
            "path": key,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        
        if content_type == "application/json":
            # Store as string for queryability/readability
            doc_data["data"] = content.decode("utf-8")
        else:
            # Store as blob
            doc_data["blob"] = content
            
        doc_ref = self.db.collection(self.COLLECTION).document(artifact_id)
        await doc_ref.set(doc_data)

    async def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve artifact content."""
        parts = key.split("/")
        artifact_id = parts[-1]
        
        doc_ref = self.db.collection(self.COLLECTION).document(artifact_id)
        doc = await doc_ref.get()
        
        if not doc.exists:
            return None
            
        data = doc.to_dict()
        
        if "data" in data:
            return data["data"].encode("utf-8")
        elif "blob" in data:
            return data["blob"]
            
        return None

    async def list_by_owner(self, owner_id: str, limit: int = 50) -> list:
        """List artifacts owned by a user."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("type", "==", "sessions")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        async for doc in query.stream():
            doc_data = doc.to_dict()
            if "data" in doc_data:
                import json
                try:
                    parsed = json.loads(doc_data["data"])
                    if parsed.get("owner_id") == owner_id:
                        results.append(parsed)
                except (json.JSONDecodeError, KeyError):
                    continue
        return results

    async def list_by_workspace(self, workspace_id: str, limit: int = 50) -> list:
        """List artifacts for a workspace."""
        query = (
            self.db.collection(self.COLLECTION)
            .where("type", "==", "sessions")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        async for doc in query.stream():
            doc_data = doc.to_dict()
            if "data" in doc_data:
                import json
                try:
                    parsed = json.loads(doc_data["data"])
                    if parsed.get("workspace_id") == workspace_id:
                        results.append(parsed)
                except (json.JSONDecodeError, KeyError):
                    continue
        return results
