"""
Aegion GCS Adapter - Google Cloud Storage Implementation.

Implements StoragePort and ContentAddressedStore interfaces.
"""

from .storage_adapter import GCSStorageAdapter

__all__ = ["GCSStorageAdapter"]
