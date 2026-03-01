# Aegion Troubleshooting Guide

## Common Issues

### 1. "Failed to connect to Aegion Backend"
**Symptoms**:
- VS Code notification: "Connection refused".
- Status bar icon is gray/disconnected.

**Possible Causes**:
- The backend server is not running.
- `aegion.backendUrl` is configured incorrectly.
- Firewall blocking port 8000.

**Resolution**:
1. Check if the backend process is running: `ps aux | grep uvicorn`.
2. Verify the URL in VS Code settings matches the server address.
3. Try accessing `http://localhost:8000/health` in your browser.

### 2. "Authentication Failed" or "401 Unauthorized"
**Symptoms**:
- Cannot start a session.
- API requests return 401.

**Possible Causes**:
- Your session token has expired.
- The `AUTH_ADAPTER` in backend config assumes a different provider.

**Resolution**:
1. Run `Aegion: Set Governance Role` to refresh your local context.
2. Check backend logs for validation errors: `poetry run logs`.

### 3. "Drift Detected" Alert
**Symptoms**:
- Sentinel warns about "Unapproved Code".
- CI/CD pipeline fails.

**Possible Causes**:
- You modified code without an active session.
- You committed code without linking it to a Decision ID.

**Resolution**:
1. Start a "Retroactive Session" (`Aegion: Start Session`).
2. Create a decision covering the changes you made.
3. Link the decision to your commit using `Aegion: Link Decision to Current Commit`.

---

## Logs

### VS Code Extension Logs
- Open **Output Panel** (`Cmd+Shift+U`).
- Select **Aegion** from the dropdown.

### Backend Logs
- **Local**: Output to stdout where you ran `uvicorn`.
- **Production**: Check Cloud Logging (GCP) or your container logs.

### Audit Trail
- A persistent audit log is maintained in `.aegion/audit.log` (if local adapter is used) or in the SQL database.
