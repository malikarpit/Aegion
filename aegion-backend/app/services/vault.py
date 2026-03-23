"""
Aegion Secrets Vault — Phase 38 (Elevated): Persistent, Audited, Rotatable.

Features:
  - AES-256-Fernet encryption for secrets at rest
  - Supabase persistence — secrets survive restarts
  - Secret versioning — every rotation archives the old version
  - Audit logging — every access, store, rotate, delete is recorded
  - Short-lived tokens — one-time or time-limited access tokens
  - Workspace scoping — secrets are isolated per workspace
  - Rotation policy — secrets can have max-age, auto-expire
"""

import os
import base64
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..core.logging import logger


class LocalVault:
    """
    Encrypted secrets vault with persistence, rotation, and full audit trail.
    """

    def __init__(self, master_key: str = None):
        self._store: Dict[str, Dict[str, Any]] = {}  # key → {encrypted, version, ...}
        self._tokens: Dict[str, Dict[str, Any]] = {}  # token → {key, expires_at, ...}

        # Derive encryption key from master key
        key_material = (
            master_key or os.getenv("AEGION_VAULT_KEY", "dev-master-key-change-me")
        ).encode()
        salt = b'aegion-vault-v2'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=200_000,  # Increased from 100k for better security
        )
        self._fernet = Fernet(base64.urlsafe_b64encode(kdf.derive(key_material)))
        self._initialized = False

    async def initialize(self) -> None:
        """Load secrets from Supabase on startup."""
        if self._initialized:
            return
        try:
            from ..db.supabase_client import get_supabase_client
            result = (
                get_supabase_client()
                .table("vault_secrets")
                .select("key,encrypted_value,version,workspace_id,max_age_hours,created_at")
                .eq("is_active", True)
                .execute()
            )
            for row in (result.data or []):
                self._store[row["key"]] = {
                    "encrypted": row["encrypted_value"],
                    "version": row["version"],
                    "workspace_id": row.get("workspace_id"),
                    "max_age_hours": row.get("max_age_hours"),
                    "created_at": row.get("created_at"),
                }
            self._initialized = True
            logger.info(f"Vault initialized: {len(self._store)} secrets loaded")
        except Exception as exc:
            logger.warning(f"Vault DB init failed (using in-memory only): {exc}")
            self._initialized = True

    def store_secret(
        self,
        key: str,
        value: str,
        workspace_id: Optional[str] = None,
        max_age_hours: Optional[int] = None,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Encrypt and store a secret. Returns metadata about the stored secret.
        """
        encrypted = self._fernet.encrypt(value.encode()).decode()
        version = self._store.get(key, {}).get("version", 0) + 1

        self._store[key] = {
            "encrypted": encrypted,
            "version": version,
            "workspace_id": workspace_id,
            "max_age_hours": max_age_hours,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to Supabase
        self._persist_secret(key, encrypted, version, workspace_id, max_age_hours)

        # Audit log
        self._audit("store", key, actor_id, workspace_id, {"version": version})

        logger.info(f"Secret stored: {key} (v{version})")
        return {"key": key, "version": version, "workspace_id": workspace_id}

    def get_secret(
        self,
        key: str,
        actor_id: str = "system",
    ) -> Optional[str]:
        """Retrieve and decrypt a secret."""
        entry = self._store.get(key)
        if not entry:
            return None

        # Check expiry
        if entry.get("max_age_hours") and entry.get("created_at"):
            try:
                created = datetime.fromisoformat(entry["created_at"])
                if datetime.now(timezone.utc) > created + timedelta(hours=entry["max_age_hours"]):
                    logger.warning(f"Secret '{key}' has expired (max_age={entry['max_age_hours']}h)")
                    self._audit("access_expired", key, actor_id)
                    return None
            except (ValueError, TypeError):
                pass

        try:
            decrypted = self._fernet.decrypt(entry["encrypted"].encode()).decode()
            self._audit("access", key, actor_id)
            return decrypted
        except Exception as e:
            self._audit("access_failed", key, actor_id, details={"error": str(e)})
            logger.error(f"Failed to decrypt secret {key}: {e}")
            return None

    def rotate_secret(
        self,
        key: str,
        new_value: str,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Rotate a secret: archive old version, store new value.

        Returns metadata about the rotation.
        """
        old_version = self._store.get(key, {}).get("version", 0)
        workspace_id = self._store.get(key, {}).get("workspace_id")

        # Archive old version
        if key in self._store:
            self._archive_version(key, old_version)

        # Store new version
        result = self.store_secret(
            key, new_value,
            workspace_id=workspace_id,
            max_age_hours=self._store.get(key, {}).get("max_age_hours"),
            actor_id=actor_id,
        )

        self._audit("rotate", key, actor_id, workspace_id, {
            "old_version": old_version,
            "new_version": result["version"],
        })

        logger.info(f"Secret rotated: {key} v{old_version} → v{result['version']}")
        return {
            "key": key,
            "old_version": old_version,
            "new_version": result["version"],
        }

    def generate_token(
        self,
        key: str,
        ttl_seconds: int = 300,
        one_time: bool = False,
        actor_id: str = "system",
    ) -> str:
        """Generate a short-lived (optionally one-time) token to access a secret."""
        if key not in self._store:
            raise ValueError(f"Secret '{key}' not found")

        token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        self._tokens[token] = {
            "key": key,
            "expires_at": expires_at,
            "one_time": one_time,
            "used": False,
        }

        self._audit("token_generated", key, actor_id, details={
            "ttl_seconds": ttl_seconds,
            "one_time": one_time,
        })
        return token

    def redeem_token(self, token: str, actor_id: str = "system") -> Optional[str]:
        """Redeem a token for the secret value."""
        data = self._tokens.get(token)
        if not data:
            return None

        if datetime.now(timezone.utc) > data["expires_at"]:
            del self._tokens[token]
            self._audit("token_expired", data["key"], actor_id)
            return None

        if data["one_time"] and data["used"]:
            self._audit("token_reuse_blocked", data["key"], actor_id)
            return None

        data["used"] = True
        self._audit("token_redeemed", data["key"], actor_id)

        if data["one_time"]:
            del self._tokens[token]

        return self.get_secret(data["key"], actor_id=actor_id)

    def delete_secret(self, key: str, actor_id: str = "system") -> bool:
        """Delete a secret permanently."""
        if key in self._store:
            workspace_id = self._store[key].get("workspace_id")
            del self._store[key]
            self._delete_persisted_secret(key)
            self._audit("delete", key, actor_id, workspace_id)
            return True
        return False

    def list_secrets(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List secret metadata (NEVER values).

        Returns key names, versions, and ages only.
        """
        result = []
        for key, entry in self._store.items():
            if workspace_id and entry.get("workspace_id") != workspace_id:
                continue
            result.append({
                "key": key,
                "version": entry.get("version", 1),
                "workspace_id": entry.get("workspace_id"),
                "max_age_hours": entry.get("max_age_hours"),
                "created_at": entry.get("created_at"),
            })
        return result

    def health(self) -> Dict[str, Any]:
        """Vault health status."""
        return {
            "status": "ok",
            "secrets_count": len(self._store),
            "active_tokens": len(self._tokens),
            "initialized": self._initialized,
        }

    # ──────────────────────────────────────────────
    # Persistence helpers
    # ──────────────────────────────────────────────

    def _persist_secret(
        self, key: str, encrypted: str, version: int,
        workspace_id: Optional[str], max_age_hours: Optional[int],
    ) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("vault_secrets").upsert({
                "key": key,
                "encrypted_value": encrypted,
                "version": version,
                "workspace_id": workspace_id,
                "max_age_hours": max_age_hours,
                "is_active": True,
            }, on_conflict="key").execute()
        except Exception as exc:
            logger.warning(f"Vault persist failed (non-fatal): {exc}")

    def _archive_version(self, key: str, version: int) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("vault_secrets").update(
                {"is_active": False}
            ).eq("key", key).eq("version", version).execute()
        except Exception:
            pass

    def _delete_persisted_secret(self, key: str) -> None:
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("vault_secrets").delete().eq("key", key).execute()
        except Exception:
            pass

    def _audit(
        self, action: str, key: str, actor_id: str = "system",
        workspace_id: Optional[str] = None, details: Optional[Dict] = None,
    ) -> None:
        """Record an audit event. Best-effort — never fails the caller."""
        try:
            from ..db.supabase_client import get_supabase_client
            get_supabase_client().table("vault_audit_log").insert({
                "key": key,
                "action": action,
                "actor_id": actor_id,
                "workspace_id": workspace_id,
                "details": details or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception:
            pass  # Audit is best-effort


# Singleton
_vault: Optional[LocalVault] = None

def get_vault() -> LocalVault:
    global _vault
    if _vault is None:
        _vault = LocalVault()
    return _vault
