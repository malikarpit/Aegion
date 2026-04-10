# Aegion API API Reference (v0.1.0)

The governed AI development platform backend.

## POST /api/v1/gateway/analyze
**Tags:** Prompt Gateway

Analyze Query

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/gateway/approve
**Tags:** Prompt Gateway

Approve Prompt

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/orphaned
**Tags:** Session Recovery

List Orphaned Sessions

### Parameters
- `threshold_minutes` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sessions/{session_id}/recover
**Tags:** Session Recovery

Recover Session

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/decisions/
**Tags:** decisions

List Decisions

### Parameters
- `limit` (query): Optional
- `x-workspace-id` (header): Optional
- `authorization` (header): Optional

---

## POST /api/v1/decisions/{decision_id}/supersede
**Tags:** decisions

Supersede Decision

### Parameters
- `decision_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/decisions/graph
**Tags:** decisions

Get Decision Graph

### Parameters
- `x-workspace-id` (header): Optional
- `authorization` (header): Optional

---

## GET /api/v1/decisions/{decision_id}/lineage
**Tags:** decisions

Get Decision Lineage

### Parameters
- `decision_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/evidence/submit
**Tags:** evidence

Submit Evidence

### Parameters
*None*

---

## GET /api/v1/evidence/{evidence_id}/freshness
**Tags:** evidence

Check Evidence Freshness

### Parameters
- `evidence_id` (path): Required
- `workspace_id` (query): Optional

---

## GET /api/v1/evidence/{evidence_id}/snapshots
**Tags:** evidence

List Evidence Snapshots

### Parameters
- `evidence_id` (path): Required

---

## POST /api/v1/evidence/{evidence_id}/snapshots
**Tags:** evidence

Capture Evidence Snapshots

### Parameters
- `evidence_id` (path): Required

---

## GET /api/v1/proposals/session/{session_id}
**Tags:** proposals

List Proposals By Session

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/proposals/
**Tags:** proposals

Create Proposal

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/proposals/{proposal_id}/approve
**Tags:** proposals

Approve Proposal

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/proposals/{proposal_id}/reject
**Tags:** proposals

Reject Proposal

### Parameters
- `proposal_id` (path): Required
- `reason` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/proposals/{proposal_id}
**Tags:** proposals

Get Proposal

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/proposals/{proposal_id}/review
**Tags:** proposals

Submit Review

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/proposals/{proposal_id}/vote
**Tags:** proposals

Cast Vote

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/proposals/{proposal_id}/activity
**Tags:** proposals

Get Proposal Activity

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/invoke
**Tags:** council

Invoke Council

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/stream
**Tags:** council

Stream Council Response

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/policy
**Tags:** council

Get Governance Policy

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/escalate
**Tags:** council

Escalate To Parent

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/sessions/{session_id}
**Tags:** council

Get Council Session

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/sessions/{session_id}/transcript
**Tags:** council

Get Session Transcript

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/proposals/{proposal_id}/sessions
**Tags:** council

Get Proposal Sessions

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/proposals/{proposal_id}/governance-status
**Tags:** council

Get Proposal Governance Status

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/consult
**Tags:** council

ACK — Full multi-model council consultation

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/debate
**Tags:** council

ACK — Anti-sycophancy structured debate

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/peer-review
**Tags:** council

ACK — Adversarial peer review

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/persona
**Tags:** council

ACK — Persona-driven expert debate

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/cost/summary
**Tags:** council

ACK — Workspace LLM cost summary

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/council/cache
**Tags:** council

ACK — Invalidate semantic cache

### Parameters
- `pattern` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/workspaces/
**Tags:** workspaces

Create Workspace

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/workspaces/
**Tags:** workspaces

List My Workspaces

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/workspaces/{workspace_id}
**Tags:** workspaces

Get Workspace

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/workspaces/{workspace_id}/invite
**Tags:** workspaces

Invite Member

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/workspaces/{workspace_id}/members/{member_user_id}
**Tags:** workspaces

Remove Member

### Parameters
- `workspace_id` (path): Required
- `member_user_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/workspaces/{workspace_id}/members/{member_user_id}/role
**Tags:** workspaces

Update Member Role

### Parameters
- `workspace_id` (path): Required
- `member_user_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/workspaces/{workspace_id}/activity
**Tags:** workspaces

Get Workspace Activity

### Parameters
- `workspace_id` (path): Required
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/events/stream/{workspace_id}
**Tags:** events

Stream Events

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/events/broadcast/{workspace_id}
**Tags:** events

Broadcast Event

### Parameters
- `workspace_id` (path): Required
- `event_type` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sessions/drafts/
**Tags:** Session Drafts

Save Draft

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/drafts/
**Tags:** Session Drafts

List Drafts

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/drafts/{draft_id}
**Tags:** Session Drafts

Get Draft

### Parameters
- `draft_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/sessions/drafts/{draft_id}
**Tags:** Session Drafts

Delete Draft

### Parameters
- `draft_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sessions/drafts/{draft_id}/restore
**Tags:** Session Drafts

Restore Draft

### Parameters
- `draft_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/active
**Tags:** sessions

Get Active Sessions

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sessions/start
**Tags:** sessions

Start Session

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/{session_id}
**Tags:** sessions

Get Session Status

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sessions/{session_id}/close
**Tags:** sessions

Close Session

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/edg/nodes
**Tags:** edg

Register Dependency Node

### Parameters
*None*

---

## GET /api/v1/edg/nodes/{node_id}/dependencies
**Tags:** edg

Get Node Dependencies

### Parameters
- `node_id` (path): Required
- `workspace_id` (query): Optional

---

## GET /api/v1/edg/nodes/{node_id}/dependents
**Tags:** edg

Get Node Dependents

### Parameters
- `node_id` (path): Required
- `workspace_id` (query): Optional

---

## GET /api/v1/edg/stale
**Tags:** edg

List Stale Nodes

### Parameters
- `workspace_id` (query): Optional

---

## POST /api/v1/sentinel/risk-score
**Tags:** sentinel

Calculate Risk Score

### Parameters
*None*

---

## POST /api/v1/sentinel/heatmap
**Tags:** sentinel

Generate Risk Heatmap

### Parameters
*None*

---

## POST /api/v1/sentinel/drift
**Tags:** sentinel

Check Drift

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sentinel/drift/{workspace_id}/status
**Tags:** sentinel

Get Drift Status

### Parameters
- `workspace_id` (path): Required

---

## GET /api/v1/sentinel/alerts
**Tags:** sentinel

Get Sentinel Alerts

### Parameters
- `workspace_id` (query): Optional

---

## POST /api/v1/noesis/cognitive-load
**Tags:** noesis

Assess Cognitive Load

### Parameters
*None*

---

## GET /api/v1/noesis/cognitive-load/{user_id}/should-break
**Tags:** noesis

Should Suggest Break

### Parameters
- `user_id` (path): Required

---

## POST /api/v1/noesis/cognitive-load/{user_id}/break
**Tags:** noesis

Record User Break

### Parameters
- `user_id` (path): Required

---

## POST /api/v1/noesis/uncertainty
**Tags:** noesis

Get Uncertainty Visualization

### Parameters
*None*

---

## POST /api/v1/noesis/impact-analysis
**Tags:** noesis

Analyze Impact

### Parameters
*None*

---

## POST /api/v1/noesis/decisions/record
**Tags:** noesis

Record Decision

### Parameters
*None*

---

## GET /api/v1/noesis/decisions/{decision_id}/provenance
**Tags:** noesis

Get Decision Provenance

### Parameters
- `decision_id` (path): Required
- `depth` (query): Optional

---

## GET /api/v1/noesis/workspace/{workspace_id}/topology
**Tags:** noesis

Get Workspace Topology

### Parameters
- `workspace_id` (path): Required

---

## POST /api/v1/ghost-text/complete
**Tags:** ghost-text

Generate Ghost Text

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/rejections/
**Tags:** rejections

Record Rejection

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/rejections/{rejection_id}
**Tags:** rejections

Get Rejection

### Parameters
- `rejection_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/rejections/query
**Tags:** rejections

Query Rejections

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/rejections/stats/{workspace_id}
**Tags:** rejections

Get Rejection Stats

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/rejections/stats
**Tags:** rejections

Get Global Stats

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/pipelines/
**Tags:** pipelines

Create Pipeline

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/pipelines/
**Tags:** pipelines

List Pipelines

### Parameters
- `workspace_id` (query): Optional
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/pipelines/{pipeline_id}
**Tags:** pipelines

Get Pipeline

### Parameters
- `pipeline_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/pipelines/{pipeline_id}/step
**Tags:** pipelines

Execute Step

### Parameters
- `pipeline_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/pipelines/templates/all
**Tags:** pipelines

Get Templates

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/praxis/descriptors
**Tags:** praxis

List Descriptors

### Parameters
- `risk_level` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/praxis/descriptors
**Tags:** praxis

Register Descriptor

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/praxis/descriptors/{descriptor_id}
**Tags:** praxis

Get Descriptor

### Parameters
- `descriptor_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/praxis/execute
**Tags:** praxis

Execute Action

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/praxis/executions/{request_id}
**Tags:** praxis

Get Execution

### Parameters
- `request_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/audit/grants
**Tags:** audit

Create Grant

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/audit/grants/{grant_id}
**Tags:** audit

Revoke Grant

### Parameters
- `grant_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/audit/grants/me
**Tags:** audit

My Grants

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/audit/check
**Tags:** audit

Check Query Access

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/audit/events
**Tags:** audit

Record Audit Event

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/audit/events
**Tags:** audit

Query Audit Events

### Parameters
- `action` (query): Optional
- `actor` (query): Optional
- `target` (query): Optional
- `target_type` (query): Optional
- `task_id` (query): Optional
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/audit/replay/{task_id}
**Tags:** audit

Replay Task Audit

### Parameters
- `task_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/audit/stats
**Tags:** audit

Audit Stats

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/architecture/adrs
**Tags:** architecture

Create Adr

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/architecture/adrs
**Tags:** architecture

List Adrs

### Parameters
- `status` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/architecture/adrs/{adr_id}
**Tags:** architecture

Get Adr

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/architecture/adrs/{adr_id}/accept
**Tags:** architecture

Accept Adr

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/architecture/adrs/{adr_id}/deprecate
**Tags:** architecture

Deprecate Adr

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/architecture/adrs/{adr_id}/chain
**Tags:** architecture

Get Supersession Chain

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/architecture/timeline/{workspace_id}
**Tags:** architecture

Get Timeline

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/architecture/snapshots
**Tags:** architecture

Capture Snapshot

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/architecture/snapshots
**Tags:** architecture

List Snapshots

### Parameters
- `start_time` (query): Optional
- `end_time` (query): Optional
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/architecture/state-at/{timestamp}
**Tags:** architecture

Get State At

### Parameters
- `timestamp` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/architecture/diff
**Tags:** architecture

Diff States

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/architecture/adrs/extract
**Tags:** architecture

Extract Adrs From Decisions

### Parameters
- `workspace_id` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/health
**Tags:** health

Health Check

### Parameters
*None*

---

## GET /api/v1/health/live
**Tags:** health

Liveness Probe

### Parameters
*None*

---

## GET /api/v1/health/ready
**Tags:** health

Readiness Probe

### Parameters
*None*

---

## GET /api/v1/health/detailed
**Tags:** health

Detailed Health

### Parameters
*None*

---

## GET /api/v1/health/metrics
**Tags:** health

Health Metrics Endpoint

### Parameters
*None*

---

## GET /api/v1/chronos/adrs
**Tags:** chronos

List Adrs

### Parameters
- `workspace_id` (query): Optional
- `status` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/chronos/adrs
**Tags:** chronos

Create Adr

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/chronos/adrs/{adr_id}
**Tags:** chronos

Get Adr

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/chronos/adrs/{adr_id}/accept
**Tags:** chronos

Accept Adr

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/chronos/adrs/{adr_id}/deprecate
**Tags:** chronos

Deprecate Adr

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/chronos/lineage/{adr_id}
**Tags:** chronos

Get Lineage

### Parameters
- `adr_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tasks
**Tags:** tasks

Create Task

### Parameters
- `x-workspace-id` (header): Optional
- `authorization` (header): Optional

---

## GET /api/v1/tasks
**Tags:** tasks

List Tasks

### Parameters
- `status_filter` (query): Optional
- `session_id` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/tasks/{task_id}
**Tags:** tasks

Get Task

### Parameters
- `task_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/tasks/{task_id}
**Tags:** tasks

Update Task

### Parameters
- `task_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tasks/{task_id}/run
**Tags:** tasks

Run Task

### Parameters
- `task_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/tasks/{task_id}/runs/{run_id}
**Tags:** tasks

Update Run

### Parameters
- `task_id` (path): Required
- `run_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tasks/{task_id}/worktree
**Tags:** tasks

Create Task Worktree

### Parameters
- `task_id` (path): Required
- `repo_path` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/tasks/{task_id}/worktree
**Tags:** tasks

Cleanup Task Worktree

### Parameters
- `task_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/tasks/{task_id}/runs
**Tags:** tasks

Get Task Runs

### Parameters
- `task_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/checkpoints
**Tags:** checkpoints

Create Checkpoint

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/checkpoints
**Tags:** checkpoints

List Checkpoints

### Parameters
- `session_id` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/checkpoints/{checkpoint_id}
**Tags:** checkpoints

Get Checkpoint

### Parameters
- `checkpoint_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/checkpoints/{checkpoint_id}
**Tags:** checkpoints

Delete Checkpoint

### Parameters
- `checkpoint_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/checkpoints/{checkpoint_id}/rollback
**Tags:** checkpoints

Rollback To Checkpoint

### Parameters
- `checkpoint_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/checkpoints/auto
**Tags:** checkpoints

Create Auto Checkpoint

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/checkpoints/{checkpoint_id}/git-snapshot
**Tags:** checkpoints

Create Git Snapshot

### Parameters
- `checkpoint_id` (path): Required
- `workspace_path` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/checkpoints/{checkpoint_id}/git-diff
**Tags:** checkpoints

Get Git Diff

### Parameters
- `checkpoint_id` (path): Required
- `workspace_path` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/memory
**Tags:** memory

Store Memory

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/memory
**Tags:** memory

List Memory

### Parameters
- `scope` (query): Optional
- `tag` (query): Optional
- `key_prefix` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/memory/{memory_id}
**Tags:** memory

Get Memory

### Parameters
- `memory_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/memory/{memory_id}/supersede
**Tags:** memory

Supersede Memory

### Parameters
- `memory_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/memory/query
**Tags:** memory

Query Memory

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/memory/extract
**Tags:** memory

Extract Memory

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/rules
**Tags:** rules

Create Rule

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/rules
**Tags:** rules

List Rules

### Parameters
- `scope` (query): Optional
- `enabled_only` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/rules/{rule_id}
**Tags:** rules

Get Rule

### Parameters
- `rule_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/rules/{rule_id}
**Tags:** rules

Update Rule

### Parameters
- `rule_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/rules/{rule_id}
**Tags:** rules

Delete Rule

### Parameters
- `rule_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/rules/evaluate
**Tags:** rules

Evaluate Rules

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills
**Tags:** skills

Create Skill

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/skills
**Tags:** skills

List Skills

### Parameters
- `category` (query): Optional
- `status_filter` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/skills/marketplace
**Tags:** skills

Search Marketplace

### Parameters
- `query` (query): Optional
- `category` (query): Optional
- `tag` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/skills/{skill_id}
**Tags:** skills

Get Skill

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/skills/{skill_id}
**Tags:** skills

Delete Skill

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills/{skill_id}/install
**Tags:** skills

Install Skill

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills/{skill_id}/validate
**Tags:** skills

Validate Skill

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills/{skill_id}/attest
**Tags:** skills

Attest Skill

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills/sync
**Tags:** skills

Sync Skills From Repo

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/presence/heartbeat
**Tags:** presence

Send Heartbeat

### Parameters
- `x-workspace-id` (header): Optional
- `authorization` (header): Optional

---

## GET /api/v1/presence
**Tags:** presence

Get Workspace Presence

### Parameters
- `x-workspace-id` (header): Optional
- `authorization` (header): Optional

---

## GET /api/v1/presence/{user_id}
**Tags:** presence

Get User Presence

### Parameters
- `user_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/presence/leave
**Tags:** presence

Leave Presence

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/warroom/overview
**Tags:** warroom

Get Warroom Overview

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/warroom/incidents
**Tags:** warroom

Create Incident

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/warroom/incidents
**Tags:** warroom

List Incidents

### Parameters
- `status_filter` (query): Optional
- `severity` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/warroom/incidents/{incident_id}
**Tags:** warroom

Get Incident

### Parameters
- `incident_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/warroom/incidents/{incident_id}
**Tags:** warroom

Update Incident

### Parameters
- `incident_id` (path): Required
- `status_update` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/warroom/telemetry
**Tags:** warroom

Get System Metrics

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/warroom/alerts
**Tags:** warroom

Get Active Alerts

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/delegation/deploy
**Tags:** delegation

Deploy Artifact

### Parameters
*None*

---

## GET /api/v1/delegation/deployments/{deployment_id}
**Tags:** delegation

Get Deployment Status

### Parameters
- `deployment_id` (path): Required

---

## GET /api/v1/delegation/resources
**Tags:** delegation

List Resources

### Parameters
- `env` (query): Optional
- `type` (query): Optional

---

## GET /api/v1/delegation/resources/{resource_id}/logs
**Tags:** delegation

Get Resource Logs

### Parameters
- `resource_id` (path): Required

---

## GET /api/v1/delegation/health
**Tags:** delegation

Provider Health

### Parameters
*None*

---

## POST /api/v1/delegation/runs
**Tags:** delegation

Trigger Run

### Parameters
- `X-Aegion-Session` (header): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/delegation/runs
**Tags:** delegation

List Runs

### Parameters
- `status` (query): Optional

---

## GET /api/v1/delegation/runs/{run_id}
**Tags:** delegation

Get Run Status

### Parameters
- `run_id` (path): Required

---

## POST /api/v1/governance/freeze
**Tags:** governance

Activate Freeze

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/governance/unfreeze
**Tags:** governance

Deactivate Freeze

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/governance/status
**Tags:** governance

Get Governance Status

### Parameters
*None*

---

## GET /api/v1/governance/policy
**Tags:** governance

Get Governance Policy

### Parameters
*None*

---

## POST /api/v1/governance/workspaces/{workspace_id}/ai-toggle
**Tags:** governance

Toggle Workspace Ai

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/governance/workspaces/{workspace_id}/ai-status
**Tags:** governance

Get Workspace Ai Status

### Parameters
- `workspace_id` (path): Required

---

## POST /api/v1/governance/scan
**Tags:** governance

Scan File

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/governance/scan/branch
**Tags:** governance

Scan Branch

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/governance/workspaces/{workspace_id}/conflicts
**Tags:** governance

Get Active Conflicts

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/governance/proposals/{proposal_id}/export
**Tags:** governance

Export Proposal Summary

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/reasoning/decisions
**Tags:** reasoning

Query Decisions

### Parameters
- `workspace_id` (query): Required
- `tier` (query): Optional
- `status` (query): Optional
- `since` (query): Optional
- `limit` (query): Optional

---

## GET /api/v1/reasoning/evidence/{proposal_id}
**Tags:** reasoning

Query Evidence

### Parameters
- `proposal_id` (path): Required
- `classification` (query): Optional

---

## GET /api/v1/reasoning/provenance/{decision_id}
**Tags:** reasoning

Query Provenance

### Parameters
- `decision_id` (path): Required
- `depth` (query): Optional

---

## POST /api/v1/proposals/{proposal_id}/comments
**Tags:** diff-review

Add Diff Comment

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/proposals/{proposal_id}/comments
**Tags:** diff-review

List Diff Comments

### Parameters
- `proposal_id` (path): Required
- `resolved` (query): Optional
- `file_path` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/proposals/{proposal_id}/comments/{comment_id}/resolve
**Tags:** diff-review

Resolve Comment

### Parameters
- `proposal_id` (path): Required
- `comment_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/proposals/{proposal_id}/apply
**Tags:** diff-review

Apply Proposal

### Parameters
- `proposal_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/{session_id}/mode
**Tags:** modes

Get Session Mode

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PUT /api/v1/sessions/{session_id}/mode
**Tags:** modes

Set Session Mode

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sessions/modes/available
**Tags:** modes

List Available Modes

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools
**Tags:** mcp-tools

Register Tool

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/tools
**Tags:** mcp-tools

List Tools

### Parameters
- `enabled_only` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/mcp/servers
**Tags:** mcp-tools

Register Mcp Server

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/tools/mcp/servers
**Tags:** mcp-tools

List Mcp Servers

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/mcp/servers/{server_id}/connect
**Tags:** mcp-tools

Connect Mcp Server

### Parameters
- `server_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/mcp/servers/{server_id}/disconnect
**Tags:** mcp-tools

Disconnect Mcp Server

### Parameters
- `server_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/tools/mcp/servers/{server_id}
**Tags:** mcp-tools

Remove Mcp Server

### Parameters
- `server_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/tools/mcp/tools
**Tags:** mcp-tools

List Mcp Tools

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/mcp/servers/{server_id}/invoke
**Tags:** mcp-tools

Invoke Mcp Tool

### Parameters
- `server_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/tools/{tool_name}
**Tags:** mcp-tools

Get Tool

### Parameters
- `tool_name` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/tools/{tool_name}
**Tags:** mcp-tools

Unregister Tool

### Parameters
- `tool_name` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/{tool_name}/invoke
**Tags:** mcp-tools

Invoke Tool

### Parameters
- `tool_name` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/terminal/execute
**Tags:** terminal

Execute Command

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/terminal/profiles
**Tags:** terminal

List Profiles

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/terminal/history
**Tags:** terminal

List Executions

### Parameters
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/browser/fetch
**Tags:** browser-tool

Fetch Url

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/browser/browse
**Tags:** browser-tool

Browse Page

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/browser/extract
**Tags:** browser-tool

Extract Structured

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/tools/browser/screenshot
**Tags:** browser-tool

Take Screenshot

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/chatops/slack/webhook
**Tags:** chatops

Slack Slash Command

### Parameters
*None*

---

## POST /api/v1/chatops/slack/events
**Tags:** chatops

Slack Events

### Parameters
*None*

---

## GET /api/v1/chatops/slack/install
**Tags:** chatops

Slack Install

### Parameters
*None*

---

## POST /api/v1/chatops/webhooks/configure
**Tags:** chatops

Configure Webhook

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/chatops/webhooks
**Tags:** chatops

List Webhooks

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/chatops/webhooks/{workspace_id}
**Tags:** chatops

Get Webhook

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/chatops/webhooks/{workspace_id}
**Tags:** chatops

Remove Webhook

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/chatops/notify
**Tags:** chatops

Send Notification

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/chatops/notifications/log
**Tags:** chatops

Notification Log

### Parameters
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/ai/transform
**Tags:** ai-commands

Transform Code

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/ai/explain
**Tags:** ai-commands

Explain Code

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/ai/debug
**Tags:** ai-commands

Debug Code

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/models
**Tags:** model-routing

List Models

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/models/active
**Tags:** model-routing

Get Active Model

### Parameters
- `workspace_id` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PUT /api/v1/models/active
**Tags:** model-routing

Set Active Model

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/models/register
**Tags:** model-routing

Register Custom Model

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/models/catalog
**Tags:** model-routing

Full ACK model catalog with pricing

### Parameters
- `provider` (query): Optional
- `capability` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/models/catalog/providers
**Tags:** model-routing

List available ACK providers

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/analytics/analyze
**Tags:** council-analytics

Analyze Council Debate

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/health
**Tags:** council-analytics

Governance Health

### Parameters
- `workspace_id` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/trends
**Tags:** council-analytics

Decision Trends

### Parameters
- `workspace_id` (query): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/drift
**Tags:** council-analytics

Cognitive Drift

### Parameters
- `workspace_id` (query): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/consensus
**Tags:** council-analytics

Consensus Evolution

### Parameters
- `workspace_id` (query): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/models
**Tags:** council-analytics

Model Ranking

### Parameters
- `workspace_id` (query): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/config/{workspace_id}
**Tags:** council-analytics

Get Council Config

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## PATCH /api/v1/council/analytics/config/{workspace_id}
**Tags:** council-analytics

Update Council Config

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/council/analytics/config/{workspace_id}/reset
**Tags:** council-analytics

Reset Council Config

### Parameters
- `workspace_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/hallucination-rate/{workspace_id}
**Tags:** council-analytics

Get Hallucination Rate

### Parameters
- `workspace_id` (path): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/dissent-score/{workspace_id}
**Tags:** council-analytics

Get Dissent Score

### Parameters
- `workspace_id` (path): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/decision-regret/{workspace_id}
**Tags:** council-analytics

Get Decision Regret

### Parameters
- `workspace_id` (path): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/model-accuracy/{workspace_id}
**Tags:** council-analytics

Get Model Accuracy

### Parameters
- `workspace_id` (path): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/council/analytics/cost-efficiency/{workspace_id}
**Tags:** council-analytics

Get Cost Efficiency

### Parameters
- `workspace_id` (path): Required
- `days` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/admin/usage
**Tags:** admin

Get Usage Stats

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/admin/policy-dashboard
**Tags:** admin

Get Policy Dashboard

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/admin/env
**Tags:** admin

Get Env Config

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/admin/env
**Tags:** admin

Update Env Config

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/secrets
**Tags:** secrets

Store Secret

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/secrets/{key}/token
**Tags:** secrets

Get Secret Token

### Parameters
- `key` (path): Required
- `ttl` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/secrets/redeem
**Tags:** secrets

Redeem Secret Token

### Parameters
- `token` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/secrets/{key}
**Tags:** secrets

Delete Secret

### Parameters
- `key` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills/{skill_id}/invoke
**Tags:** skill-invoke

Invoke Skill

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/skills/{skill_id}/invoke-link
**Tags:** skill-invoke

Generate Invoke Link

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/skills/invoke/{token}
**Tags:** skill-invoke

Redeem Invoke Link

### Parameters
- `token` (path): Required

---

## GET /api/v1/skills/{skill_id}/invocations
**Tags:** skill-invoke

List Invocations

### Parameters
- `skill_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/agents
**Tags:** agents

Register Agent

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/agents
**Tags:** agents

List Agents

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/agents/{agent_id}
**Tags:** agents

Get Agent

### Parameters
- `agent_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## DELETE /api/v1/agents/{agent_id}
**Tags:** agents

Deregister Agent

### Parameters
- `agent_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/agents/{agent_id}/verify
**Tags:** agents

Start Verification

### Parameters
- `agent_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/agents/{agent_id}/verify/complete
**Tags:** agents

Complete Verification

### Parameters
- `agent_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/agents/{agent_id}/claims
**Tags:** agents

Create Claim

### Parameters
- `agent_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/agents/{agent_id}/claims
**Tags:** agents

List Claims

### Parameters
- `agent_id` (path): Required
- `direction` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/agents/{agent_id}/claims/{claim_id}/verify
**Tags:** agents

Verify Claim

### Parameters
- `agent_id` (path): Required
- `claim_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/repo/scan/start
**Tags:** repo-intelligence, repo-intelligence

Start Scan

### Parameters
- `workspace_id` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/repo/scan/{scan_id}
**Tags:** repo-intelligence, repo-intelligence

Get Scan Status

### Parameters
- `scan_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/repo/symbols
**Tags:** repo-intelligence, repo-intelligence

Search Symbols

### Parameters
- `query` (query): Required
- `workspace_id` (query): Optional
- `limit` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/repo/file/{file_path}
**Tags:** repo-intelligence, repo-intelligence

Get File Details

### Parameters
- `file_path` (path): Required
- `workspace_id` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/repo/context
**Tags:** repo-intelligence, repo-intelligence

Build Repo Context

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/repo/contributors
**Tags:** repo-intelligence, repo-intelligence

Get Top Contributors

### Parameters
- `limit` (query): Optional
- `workspace_id` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/thoughts
**Tags:** Thoughts

Create Thought

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/thoughts/{thought_id}
**Tags:** Thoughts

Get Thought

### Parameters
- `thought_id` (path): Required

---

## PATCH /api/v1/thoughts/{thought_id}
**Tags:** Thoughts

Update Thought

### Parameters
- `thought_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/thoughts/{thought_id}/seal
**Tags:** Thoughts

Seal Thought

### Parameters
- `thought_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/thoughts/{thought_id}/link
**Tags:** Thoughts

Link Commit

### Parameters
- `thought_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/thoughts/commit/{commit_sha}
**Tags:** Thoughts

Get Thought By Commit

### Parameters
- `commit_sha` (path): Required

---

## GET /api/v1/collaboration/session/{session_id}/ownership
**Tags:** collaboration, collaboration

Get Session Ownership

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/collaboration/session/{session_id}/claim
**Tags:** collaboration, collaboration

Claim Ownership

### Parameters
- `session_id` (path): Required
- `force` (query): Optional
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/collaboration/session/{session_id}/transfer
**Tags:** collaboration, collaboration

Transfer Ownership

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/collaboration/session/{session_id}/release
**Tags:** collaboration, collaboration

Release Ownership

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/collaboration/session/{session_id}/handoff
**Tags:** collaboration, collaboration

Get Handoff Summary

### Parameters
- `session_id` (path): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/auth/logout
**Tags:** auth

Logout

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/auth/revoke-token
**Tags:** auth

Revoke Specific Token

### Parameters
- `jti` (query): Required
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/system/features/
**Tags:** features

Get Features

### Parameters
*None*

---

## GET /api/v1/system/features/manifest
**Tags:** features

Get Feature Manifest

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sentinel/risk/analyze
**Tags:** sentinel

Analyze code change for risk signals

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /api/v1/sentinel/drift/adr
**Tags:** sentinel

Detect ADR compliance drift

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## POST /api/v1/sentinel/security/scan
**Tags:** sentinel

AI-powered security audit

### Parameters
- `authorization` (header): Optional
- `x-workspace-id` (header): Optional

---

## GET /
**Tags:** 

Root

### Parameters
*None*

---

## GET /metrics
**Tags:** observability

Metrics

### Parameters
*None*

---

