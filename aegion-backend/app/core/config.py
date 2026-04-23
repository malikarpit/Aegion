"""
Aegion Backend Configuration.

Loads environment variables and provides a typed settings object.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Central configuration for Aegion Backend.
    Values are loaded from environment variables.
    """
    # GCP
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "aegion-dev")
    
    # Firebase
    firebase_credentials_path: Optional[str] = None
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # API
    api_prefix: str = "/api/v1"
    debug_mode: bool = os.getenv("DEBUG", "false").lower() == "true"
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Session Defaults
    session_timeout_minutes: int = 120  # 2 hours
    
    # Storage (GCS)
    gcs_bucket: str = os.getenv("GCS_BUCKET", "aegion-artifacts")
    storage_mode: str = os.getenv("STORAGE_MODE", "LOCAL")  # LOCAL or TEAM
    
    # Adapters (Derived from Mode)
    database_adapter: str = "sqlite" if storage_mode == "LOCAL" else os.getenv("DATABASE_ADAPTER", "firestore")
    auth_adapter: str = "mock" if storage_mode == "LOCAL" else os.getenv("AUTH_ADAPTER", "firebase")
    ai_adapter: str = os.getenv("AI_ADAPTER", "langgraph")
    event_adapter: str = "file" if storage_mode == "LOCAL" else os.getenv("EVENT_ADAPTER", "inprocess")
    
    # Audit integrity 
    audit_signing_key: str  # Required — set via Secret Manager in production
    
    model_config = SettingsConfigDict(env_prefix="AEGION_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
