"""Supabase client singleton for AEGION backend.

Provides:
  - get_supabase_client() → raw Client singleton
  - SupabaseDB → comprehensive CRUD abstraction for all 22+ tables
"""

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
    """Database abstraction over Supabase PostgreSQL (via HTTP/PostgREST).

    Covers all tables from supabase/migrations/:
      sessions, proposals, decisions, adrs, knowledge_nodes, knowledge_edges,
      timeline_events, risk_signals, audit_log, memories, rules, semantic_cache,
      cost_tracking, skills, tasks, checkpoints, kv_store, council_findings,
      workspace_model_settings, vault_secrets, vault_audit_log
    """

    def __init__(self):
        self.client = get_supabase_client()

    # ═══════════════════════════════════════════════════════════════════════
    # Sessions
    # ═══════════════════════════════════════════════════════════════════════

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
            .maybe_single() \
            .execute()
        return result.data

    async def close_session(self, session_id: str) -> dict:
        result = self.client.table("sessions") \
            .update({"status": "closed"}) \
            .eq("id", session_id) \
            .execute()
        return result.data[0] if result.data else None

    async def list_active_sessions(self, workspace_id: str) -> list:
        return self.client.table("sessions") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .eq("status", "active") \
            .order("created_at", desc=True) \
            .execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Proposals
    # ═══════════════════════════════════════════════════════════════════════

    async def create_proposal(self, data: dict) -> dict:
        result = self.client.table("proposals").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_proposal(self, proposal_id: str) -> dict:
        result = self.client.table("proposals") \
            .select("*") \
            .eq("id", proposal_id) \
            .maybe_single() \
            .execute()
        return result.data

    async def list_proposals(self, workspace_id: str, status: str = None) -> list:
        q = self.client.table("proposals").select("*").eq("workspace_id", workspace_id)
        if status:
            q = q.eq("status", status)
        return q.order("created_at", desc=True).execute().data or []

    async def update_proposal(self, proposal_id: str, data: dict) -> dict:
        result = self.client.table("proposals") \
            .update(data) \
            .eq("id", proposal_id) \
            .execute()
        return result.data[0] if result.data else None

    # ═══════════════════════════════════════════════════════════════════════
    # Decisions
    # ═══════════════════════════════════════════════════════════════════════

    async def create_decision(self, data: dict) -> dict:
        result = self.client.table("decisions").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_decision(self, decision_id: str) -> dict:
        result = self.client.table("decisions") \
            .select("*") \
            .eq("id", decision_id) \
            .maybe_single() \
            .execute()
        return result.data

    async def list_decisions(self, workspace_id: str, limit: int = 100) -> list:
        return self.client.table("decisions") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # ADRs
    # ═══════════════════════════════════════════════════════════════════════

    async def create_adr(self, data: dict) -> dict:
        result = self.client.table("adrs").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_adrs(self, workspace_id: str) -> list:
        return self.client.table("adrs") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True) \
            .execute().data or []

    async def get_adr(self, adr_id: str) -> dict:
        result = self.client.table("adrs") \
            .select("*") \
            .eq("id", adr_id) \
            .maybe_single() \
            .execute()
        return result.data

    # ═══════════════════════════════════════════════════════════════════════
    # Timeline Events
    # ═══════════════════════════════════════════════════════════════════════

    async def append_timeline_event(self, data: dict) -> dict:
        result = self.client.table("timeline_events").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_timeline(self, workspace_id: str, limit: int = 100) -> list:
        return self.client.table("timeline_events") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Risk Signals
    # ═══════════════════════════════════════════════════════════════════════

    async def insert_risk_signal(self, data: dict) -> dict:
        result = self.client.table("risk_signals").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_risk_signals(self, workspace_id: str, severity: str = None, limit: int = 50) -> list:
        q = self.client.table("risk_signals").select("*").eq("workspace_id", workspace_id)
        if severity:
            q = q.eq("severity", severity)
        return q.order("created_at", desc=True).limit(limit).execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Audit Log
    # ═══════════════════════════════════════════════════════════════════════

    async def append_audit_event(self, data: dict) -> dict:
        result = self.client.table("audit_log").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_audit_log(self, workspace_id: str, limit: int = 200) -> list:
        return self.client.table("audit_log") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("timestamp", desc=True) \
            .limit(limit) \
            .execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Memories
    # ═══════════════════════════════════════════════════════════════════════

    async def store_memory(self, data: dict) -> dict:
        result = self.client.table("memories").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_memories(self, workspace_id: str, memory_type: str = None, limit: int = 100) -> list:
        q = self.client.table("memories").select("*").eq("workspace_id", workspace_id)
        if memory_type:
            q = q.eq("memory_type", memory_type)
        return q.order("created_at", desc=True).limit(limit).execute().data or []

    async def search_memories(self, workspace_id: str, query: str, limit: int = 10) -> list:
        return self.client.table("memories") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .ilike("concept", f"%{query}%") \
            .limit(limit) \
            .execute().data or []

    async def delete_memory(self, memory_id: str) -> bool:
        self.client.table("memories").delete().eq("id", memory_id).execute()
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # Rules
    # ═══════════════════════════════════════════════════════════════════════

    async def create_rule(self, data: dict) -> dict:
        result = self.client.table("rules").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_rules(self, workspace_id: str, active_only: bool = True) -> list:
        q = self.client.table("rules").select("*").eq("workspace_id", workspace_id)
        if active_only:
            q = q.eq("is_active", True)
        return q.execute().data or []

    async def update_rule(self, rule_id: str, data: dict) -> dict:
        result = self.client.table("rules").update(data).eq("id", rule_id).execute()
        return result.data[0] if result.data else None

    # ═══════════════════════════════════════════════════════════════════════
    # Skills
    # ═══════════════════════════════════════════════════════════════════════

    async def create_skill(self, data: dict) -> dict:
        result = self.client.table("skills").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_skills(self, workspace_id: str) -> list:
        return self.client.table("skills") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Tasks
    # ═══════════════════════════════════════════════════════════════════════

    async def create_task(self, data: dict) -> dict:
        result = self.client.table("tasks").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_tasks(self, workspace_id: str, status: str = None) -> list:
        q = self.client.table("tasks").select("*").eq("workspace_id", workspace_id)
        if status:
            q = q.eq("status", status)
        return q.order("created_at", desc=True).execute().data or []

    async def update_task(self, task_id: str, data: dict) -> dict:
        result = self.client.table("tasks").update(data).eq("id", task_id).execute()
        return result.data[0] if result.data else None

    # ═══════════════════════════════════════════════════════════════════════
    # Checkpoints
    # ═══════════════════════════════════════════════════════════════════════

    async def create_checkpoint(self, data: dict) -> dict:
        result = self.client.table("checkpoints").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_checkpoints(self, workspace_id: str) -> list:
        return self.client.table("checkpoints") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True) \
            .execute().data or []

    async def get_checkpoint(self, checkpoint_id: str) -> dict:
        result = self.client.table("checkpoints") \
            .select("*") \
            .eq("id", checkpoint_id) \
            .maybe_single() \
            .execute()
        return result.data

    # ═══════════════════════════════════════════════════════════════════════
    # Council Findings
    # ═══════════════════════════════════════════════════════════════════════

    async def insert_council_finding(self, data: dict) -> dict:
        result = self.client.table("council_findings").insert(data).execute()
        return result.data[0] if result.data else None

    async def list_council_findings(self, workspace_id: str, limit: int = 50) -> list:
        return self.client.table("council_findings") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Cost Tracking
    # ═══════════════════════════════════════════════════════════════════════

    async def insert_cost_record(self, data: dict) -> dict:
        result = self.client.table("cost_tracking").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_cost_records(self, workspace_id: str, since: str = None, limit: int = 500) -> list:
        q = self.client.table("cost_tracking") \
            .select("*") \
            .eq("workspace_id", workspace_id)
        if since:
            q = q.gte("created_at", since)
        return q.order("created_at", desc=True).limit(limit).execute().data or []

    # ═══════════════════════════════════════════════════════════════════════
    # Workspace Model Settings
    # ═══════════════════════════════════════════════════════════════════════

    async def get_model_settings(self, workspace_id: str) -> dict:
        result = self.client.table("workspace_model_settings") \
            .select("*") \
            .eq("workspace_id", workspace_id) \
            .maybe_single() \
            .execute()
        return result.data

    async def upsert_model_settings(self, data: dict) -> dict:
        result = self.client.table("workspace_model_settings") \
            .upsert(data, on_conflict="workspace_id") \
            .execute()
        return result.data[0] if result.data else None

    # ═══════════════════════════════════════════════════════════════════════
    # KV Store (generic)
    # ═══════════════════════════════════════════════════════════════════════

    async def kv_put(self, workspace_id: str, namespace: str, key: str, value: dict) -> dict:
        result = self.client.table("kv_store").upsert({
            "workspace_id": workspace_id,
            "namespace": namespace,
            "key": key,
            "value": value,
        }, on_conflict="workspace_id,namespace,key").execute()
        return result.data[0] if result.data else None

    async def kv_get(self, workspace_id: str, namespace: str, key: str) -> dict:
        result = self.client.table("kv_store") \
            .select("value") \
            .eq("workspace_id", workspace_id) \
            .eq("namespace", namespace) \
            .eq("key", key) \
            .maybe_single() \
            .execute()
        return result.data.get("value") if result.data else None

    async def kv_delete(self, workspace_id: str, namespace: str, key: str) -> bool:
        self.client.table("kv_store") \
            .delete() \
            .eq("workspace_id", workspace_id) \
            .eq("namespace", namespace) \
            .eq("key", key) \
            .execute()
        return True
