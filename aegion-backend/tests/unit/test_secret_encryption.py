"""
Secrets Vault Tests.

Validates:
- Per-workspace key derivation (HKDF)
- Secret storage and retrieval (encrypt/decrypt)
- Secret versioning and max version enforcement
- Rollback to previous versions
- Cross-workspace isolation
- Access logging
- Tamper detection
"""

import sys
from unittest.mock import MagicMock

# Mock imports for standalone test execution
_mock_logger = MagicMock()
_mock_logging = MagicMock()
_mock_logging.logger = _mock_logger
for prefix in ["app.services.core", "app.core"]:
    sys.modules.setdefault(f"{prefix}", MagicMock())
    sys.modules.setdefault(f"{prefix}.logging", _mock_logging)
    config_mod = MagicMock()
    config_mod.settings = MagicMock()
    sys.modules.setdefault(f"{prefix}.config", config_mod)

import pytest

from app.services.archon.secret_encryption import (
    SecretsVault,
    SecretIntegrityError,
    SecretEntry,
    derive_workspace_key,
    MAX_SECRET_VERSIONS,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Key Derivation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestKeyDerivation:
    def test_deterministic(self):
        k1 = derive_workspace_key(b"master", "ws-1")
        k2 = derive_workspace_key(b"master", "ws-1")
        assert k1 == k2

    def test_different_workspaces_different_keys(self):
        k1 = derive_workspace_key(b"master", "ws-1")
        k2 = derive_workspace_key(b"master", "ws-2")
        assert k1 != k2

    def test_different_master_different_keys(self):
        k1 = derive_workspace_key(b"master-a", "ws-1")
        k2 = derive_workspace_key(b"master-b", "ws-1")
        assert k1 != k2

    def test_key_length_is_32_bytes(self):
        k = derive_workspace_key(b"key", "ws")
        assert len(k) == 32


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Store and Retrieve
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStoreRetrieve:
    def setup_method(self):
        self.vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")

    def test_store_and_get(self):
        self.vault.store_secret("ws-1", "db_password", "s3cret!", "user-1")
        result = self.vault.get_secret("ws-1", "db_password", "user-1")
        assert result == "s3cret!"

    def test_get_nonexistent(self):
        result = self.vault.get_secret("ws-1", "nope", "user-1")
        assert result is None

    def test_overwrite_returns_new_version(self):
        v1 = self.vault.store_secret("ws-1", "key", "val1", "u1")
        v2 = self.vault.store_secret("ws-1", "key", "val2", "u1")
        assert v2 == v1 + 1

    def test_latest_after_overwrite(self):
        self.vault.store_secret("ws-1", "key", "old", "u1")
        self.vault.store_secret("ws-1", "key", "new", "u1")
        result = self.vault.get_secret("ws-1", "key", "u1")
        assert result == "new"

    def test_get_specific_version(self):
        v1 = self.vault.store_secret("ws-1", "key", "version-1", "u1")
        self.vault.store_secret("ws-1", "key", "version-2", "u1")
        result = self.vault.get_secret("ws-1", "key", "u1", version=v1)
        assert result == "version-1"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Workspace Isolation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestWorkspaceIsolation:
    def setup_method(self):
        self.vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")

    def test_same_name_different_workspace(self):
        self.vault.store_secret("ws-1", "api_key", "key-for-ws1", "u1")
        self.vault.store_secret("ws-2", "api_key", "key-for-ws2", "u1")
        assert self.vault.get_secret("ws-1", "api_key", "u1") == "key-for-ws1"
        assert self.vault.get_secret("ws-2", "api_key", "u1") == "key-for-ws2"

    def test_list_secrets_per_workspace(self):
        self.vault.store_secret("ws-1", "a", "v", "u1")
        self.vault.store_secret("ws-1", "b", "v", "u1")
        self.vault.store_secret("ws-2", "c", "v", "u1")
        names = self.vault.list_secrets("ws-1")
        assert set(names) == {"a", "b"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Versioning
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestVersioning:
    def test_max_versions_enforced(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        for i in range(MAX_SECRET_VERSIONS + 5):
            vault.store_secret("ws-1", "key", f"val-{i}", "u1")

        sk = vault._secret_key("ws-1", "key")
        entry = vault._secrets[sk]
        assert len(entry.versions) <= MAX_SECRET_VERSIONS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Delete
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDelete:
    def test_delete_existing(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        vault.store_secret("ws-1", "key", "val", "u1")
        assert vault.delete_secret("ws-1", "key", "u1") is True
        assert vault.get_secret("ws-1", "key", "u1") is None

    def test_delete_nonexistent(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        assert vault.delete_secret("ws-1", "nope", "u1") is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Access Log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAccessLog:
    def test_store_logs_write(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        vault.store_secret("ws-1", "key", "val", "u1")
        log = vault.get_access_log("ws-1")
        assert len(log) == 1
        assert log[0].action == "write"
        assert log[0].actor_id == "u1"

    def test_get_logs_read(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        vault.store_secret("ws-1", "key", "val", "u1")
        vault.get_secret("ws-1", "key", "u2")
        log = vault.get_access_log("ws-1")
        assert len(log) == 2
        assert log[1].action == "read"
        assert log[1].actor_id == "u2"

    def test_log_filtered_by_workspace(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        vault.store_secret("ws-1", "a", "v", "u1")
        vault.store_secret("ws-2", "b", "v", "u1")
        log = vault.get_access_log("ws-1")
        assert len(log) == 1
        assert log[0].workspace_id == "ws-1"

    def test_stats(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        vault.store_secret("ws-1", "a", "v", "u1")
        vault.store_secret("ws-2", "b", "v", "u1")
        stats = vault.stats
        assert stats["total_secrets"] == 2
        assert stats["workspaces"] == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tamper Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTamperDetection:
    def test_tampered_ciphertext(self):
        vault = SecretsVault(master_key=b"test-master-key-32-bytes-long!xx")
        vault.store_secret("ws-1", "key", "secret-value", "u1")

        # Tamper with encrypted data
        sk = vault._secret_key("ws-1", "key")
        entry = vault._secrets[sk]
        version = entry.latest
        # Flip a byte in ciphertext
        tampered = bytearray(version.encrypted_value)
        tampered[-1] ^= 0xFF
        version.encrypted_value = bytes(tampered)

        with pytest.raises(SecretIntegrityError, match="tampering"):
            vault.get_secret("ws-1", "key", "u1")
