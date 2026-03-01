# Aegion API Reference

**Base URL**: `http://localhost:8000/api/v1`

## Authentication
All requests requires a valid Firebase Auth token in the `Authorization` header, unless checking `health`.
`Authorization: Bearer <token>`

---

## 1. System Health
### Get System Health
`GET /health`
Returns the operational status of the backend.
**Response**:
```json
{"status": "healthy", "version": "0.1.0"}
```

---

## 2. Sessions
Sessions are the container for governance. All work must happen within a session.

### Start Session
`POST /sessions/start`
Initializes a new session. Closes any existing active session for the user.
**Body**:
```json
{"workspace_id": "string", "context_hash": "string"}
```

### Get Session Status
`GET /sessions/{session_id}`
Returns status, decision count, and active stage.

### Close Session
`POST /sessions/{session_id}/close`
Ends the session. Optional `distill: true` triggers artifact generation.
**Body**:
```json
{"distill": true}
```

---

## 3. Proposals & Decisions
The core of Aegion's governance model.

### Create Proposal
`POST /proposals/`
Submit a new change intent. Archon will calculate the Tier (T0-T3).
**Body**:
```json
{
  "session_id": "uuid",
  "title": "Refactor Auth Middleware",
  "description": "Moving auth logic...",
  "impact_level": "module|app|cross_app",
  "reasoning": {...}
}
```

### Approve Proposal
`POST /proposals/{id}/approve`
Sign off on a proposal. Requires evidence for T2+.
**Body**:
```json
{
  "verdict": "approve",
  "evidence_ids": ["ev-123"]
}
```

---

## 4. AI Council
Augmented intelligence for code review and policy.

### Invoke Council
`POST /council/invoke`
Request an AI debate and recommendation on the current context.
**Body**:
```json
{
  "session_id": "uuid",
  "prompt": "Is this secure?",
  "context": {...}
}
```

---

## 5. Evidence
Proof of correctness (test logs, snapshots).

### Submit Evidence
`POST /evidence/submit`
Link a test run or validation output to a proposal.
**Body**:
```json
{
  "proposal_id": "uuid",
  "evidence_type": "test_log",
  "content_hash": "sha256",
  "summary": "Tests passed"
}
```
