# Sandbox Operations Runbook

## Overview
The Aegion Sandbox is the isolated execution environment for all user code. It uses Docker containers with strict security hardening.

## Diagnostic Commands

### Check Sandbox Health
```bash
# Get sandbox statistics and docker daemon status
curl -H "Authorization: Bearer <token>" https://api.aegion.dev/api/v1/sandbox/stats
```

### Check Docker Status
```bash
docker info
docker ps --filter "label=aegion.sandbox=true"
```

## Common Issues

### 1. "Docker daemon not available"
**Symptoms**:
- API returns `503 Service Unavailable` for execution requests.
- `GET /sandbox/stats` shows `docker_available: false`.

**Resolution**:
1. Check if Docker is running on the host.
2. Verify the backend has access to `/var/run/docker.sock`.
3. Restart Docker service: `sudo systemctl restart docker`.

### 2. "Quota Exceeded"
**Symptoms**:
- Execution fails with `429 Too Many Requests`.
- Log message: `Execution quota exceeded for <workspace_id>: ...`

**Resolution**:
1. Check usage via `/sandbox/stats`.
2. Wait for the rolling hour window to reset.
3. (Admin) Increase quota for the workspace via database or admin panel.

### 3. "Network is unreachable"
**Symptoms**:
- Code fails to connect to external APIs.
- `curl`, `pip install` fail inside sandbox.

**Cause**:
- Sandbox defaults to `network: none`.

**Resolution**:
1. If network is required, update the `ExecutionProfile` for this task to set `allow_network_egress=True`.
2. **Warning**: This reduces security isolation. Only enable for trusted tasks.

## Maintenance

### Pruning Stale Containers
Run the reaper script to clean up any containers that failed to exit or were left behind by a crash.

```bash
./scripts/prune_sandbox.sh
```

**Automated**: This script is scheduled via cron to run every hour on the production backend.
