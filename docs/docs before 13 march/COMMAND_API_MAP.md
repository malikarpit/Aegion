# Aegion Command & API Truth Table

**Version**: 1.0.0
**Status**: Active

This document maps every user-facing command (VS Code Palette) to its underlying API endpoint and documentation. If a command is not listed here, it is considered internal or deprecated.

## 1. Session Management
| Command | Title | API Endpoint | Description |
| :--- | :--- | :--- | :--- |
| `aegion.startSession` | Start Session | `POST /api/v1/sessions/start` | Initializes a new governance session. |
| `aegion.closeSession` | Close Session | `POST /api/v1/sessions/{id}/close` | Ends the session and optionally distills artifacts. |
| `aegion.openSessionExplorer` | Open Session Explorer | `GET /api/v1/sessions/active` | View active and past sessions. |

## 2. Governance & Proposals
| Command | Title | API Endpoint | Description |
| :--- | :--- | :--- | :--- |
| `aegion.createProposal` | Create Proposal | `POST /api/v1/proposals/` | Submit a new change proposal. |
| `aegion.approveProposal` | Approve Proposal | `POST /api/v1/proposals/{id}/approve` | Sign off on a proposal (requires authority). |
| `aegion.rejectDecision` | Reject Proposal | `POST /api/v1/proposals/{id}/reject` | Block a proposal with justification. |
| `aegion.invokeCouncil` | Invoke AI Council | `POST /api/v1/council/invoke` | Request AI review of current context. |
| `aegion.explainWhy` | Explain Why | `GET /api/v1/proposals/{id}` | Retrieve reasoning for a specific decision. |

## 3. Observability & System
| Command | Title | API Endpoint | Description |
| :--- | :--- | :--- | :--- |
| `aegion.openSystemHealth` | Open System Health | `GET /api/v1/health/ready` | View backend status. |
| `aegion.openSentinelHealth` | Refresh Sentinel | `GET /api/v1/sentinel/status` | Check status of governance sentinels. |
| `aegion.openAuditLog` | Open Audit Log | `GET /api/v1/audit/logs` | View immutable audit trail. |

## 4. Advanced / Experimental
| Command | Title | Status | API Endpoint |
| :--- | :--- | :--- | :--- |
| `aegion.openWarRoom` | Open War Room | Beta | `GET /api/v1/collaboration/warroom` |
| `aegion.generateADR` | Generate ADR | Beta | `POST /api/v1/chronos/generate-adr` |
| `aegion.openCloudDelegate` | Open Cloud Delegate | Alpha | `POST /api/v1/delegation/tasks` |

## 5. Configuration Keys
| Key | Default | Description |
| :--- | :--- | :--- |
| `aegion.backendUrl` | `http://localhost:8000` | API Server URL. |
| `aegion.authToken` | `""` | Firebase Auth Token (if enabled). |
| `aegion.clientGenerationMode` | `automatic` | TS Client generation strategy. |
