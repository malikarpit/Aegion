"""
Aegion Backend Configuration.

Loads environment variables and provides a typed settings object.
"""

import os

# Hardcoded defaults — will migrate to pydantic-settings
GCP_PROJECT_ID = "aegion-dev"
API_PREFIX = "/api/v1"
DEBUG_MODE = False
ENVIRONMENT = "development"
LOG_LEVEL = "INFO"
SESSION_TIMEOUT_MINUTES = 120
GCS_BUCKET = "aegion-artifacts"
STORAGE_MODE = "LOCAL"
DATABASE_ADAPTER = "sqlite"
AUTH_ADAPTER = "mock"
AI_ADAPTER = "langgraph"
EVENT_ADAPTER = "file"
