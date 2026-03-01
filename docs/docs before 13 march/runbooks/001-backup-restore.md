# Runbook: Event Store Backup & Restore

**ID**: RB-001
**Service**: Aegion Backend (Chronos)
**Owner**: DevOps / Data Foundation Team

## Overview
Aegion's state is derived exclusively from the immutable Event Log. To backup the system, you back up the Event Log. To restore the system (e.g., for disaster recovery or testing), you restore the Event Log and restart the service to trigger rehydration.

## 1. Storage Location
By default, Aegion uses a local file-based Event Store.
-   **Production**: `/app/.aegion/events.jsonl` (typical container mount)
-   **Development**: `.aegion/events.jsonl` (project root)

*Note: If using `PostgresEventStore`, refer to standard PostgreSQL dump/restore procedures.*

## 2. Backup Procedure
Backup can be performed while the system is running (Append-only strictu).

```bash
# 1. Identify the event log file
export EVENT_LOG_PATH=".aegion/events.jsonl"
export BACKUP_DIR="./backups"
export TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 2. Copy the file
cp "$EVENT_LOG_PATH" "$BACKUP_DIR/events_backup_$TIMESTAMP.jsonl"

# 3. Verify integrity (optional)
# Check last line is valid JSON
tail -n 1 "$BACKUP_DIR/events_backup_$TIMESTAMP.jsonl" | jq .
```

## 3. Restore Procedure
⚠️ **Warning**: This replaces the entire state of the workspace.

1.  **Stop the Backend Service**:
    ```bash
    # Kubernetes
    kubectl scale deployment aegion-backend --replicas=0
    
    # Local
    Ctrl+C or kill process
    ```

2.  **Replace the Event Log**:
    ```bash
    cp "backups/my_backup.jsonl" ".aegion/events.jsonl"
    ```

3.  **Start the Backend Service**:
    ```bash
    # Kubernetes
    kubectl scale deployment aegion-backend --replicas=1
    
    # Local
    uvicorn app.main:app
    ```

4.  **Verify Restoration**:
    The service will automatically rehydrate on startup.
    Check the logs for:
    ```
    INFO: 💦 Hydrating Timeline Service...
    INFO: ✅ Hydration complete. Loaded X events.
    ```
    
    Call the health endpoint:
    ```bash
    curl http://localhost:8000/api/v1/health/detailed | jq .components.chronos
    ```

## 4. Disaster Scenarios

### Corrupted Event Log
If `events.jsonl` contains invalid JSON:
1.  The service will crash on startup during hydration.
2.  **Fix**: Manually remove the corrupted lines from the end of the file (Atomicity guarantees writes are lines, so corruption usually means half-written line at end).
    ```bash
    # Remove last line if corrupted
    head -n -1 events.jsonl > events_clean.jsonl
    mv events_clean.jsonl events.jsonl
    ```

### Accidental Deletion
1.  Restore from the latest `events_backup_*.jsonl`.
2.  Accepted data loss: Events created since the last backup.
