# Aegion Configuration Reference

## VS Code Extension Settings

These settings can be configured in your `.vscode/settings.json` or global user settings.

| Setting | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `aegion.backendUrl` | `string` | `http://localhost:8000` | The URL of the running Aegion backend service. change this if deploying to a remote server. |
| `aegion.autoStartSession` | `boolean` | `false` | If true, Aegion will automatically start a new session when you open a VS Code window. |

---

## Backend Environment Variables

The backend is configured via environment variables. You can set these in a `.env` file or your deployment environment (e.g., Kubernetes, Cloud Run).

### Core
| Variable | Default | Description |
| :--- | :--- | :--- |
| `AEGION_ENVIRONMENT` | `development` | The runtime environment (`development`, `staging`, `production`). |
| `AEGION_DEBUG` | `false` | Enable verbose debug logging and retrace. |
| `AEGION_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `AEGION_API_PREFIX` | `/api/v1` | Prefix for all API routes. |

### Infrastructure
| Variable | Default | Description |
| :--- | :--- | :--- |
| `GCP_PROJECT_ID` | `aegion-dev` | Google Cloud Project ID for Firestore/GCS. |
| `AEGION_DATABASE_ADAPTER` | `firestore` | Database backend (`firestore`, `postgres`, `memory`). |
| `AEGION_STORAGE_ADAPTER` | `gcs` | Artifact storage backend (`gcs`, `s3`, `local`). |
| `AEGION_AUTH_ADAPTER` | `firebase` | Authentication provider (`firebase`, `keycloak`, `mock`). |

### Security
| Variable | Description |
| :--- | :--- |
| `AEGION_AUDIT_SIGNING_KEY` | **CRITICAL**: The private key used to sign audit logs. Must be rotated regularly in production. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the GCP Service Account JSON key (standard library requirement). |

### Session Policies
| Variable | Default | Description |
| :--- | :--- | :--- |
| `AEGION_SESSION_TIMEOUT_MINUTES` | `120` | Auto-close sessions after X minutes of inactivity. |
