"""Supabase client singleton for AEGION backend."""

from supabase import create_client, Client
from functools import lru_cache
from app.core.config import settings

@lru_cache()
def get_supabase_client() -> Client:
    """Get singleton Supabase client."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in settings")
        
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_KEY
    )

class SupabaseDB:
    """Database abstraction over Supabase PostgreSQL (via HTTP/PostgREST)."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    # --- Sessions ---
    async def create_session(self, workspace_id: str, user_id: str, intent: str = None) -> dict:
        result = self.client.table("sessions").insert({
            "workspace_id": workspace_id,
            "user_id": user_id,
            "intent": intent,
            "status": "active"
        }).execute()
        return result.data[0] if result.data else None
    
    async def get_session(self, session_id: str) -> dict:
        result = self.client.table("sessions") \
            .select("*") \
            .eq("id", session_id) \
            .single() \
            .execute()
        return result.data
    
    async def close_session(self, session_id: str) -> dict:
        result = self.client.table("sessions") \
            .update({"status": "closed", "closed_at": "now()"}) \
            .eq("id", session_id) \
            .execute()
        return result.data[0] if result.data else None
