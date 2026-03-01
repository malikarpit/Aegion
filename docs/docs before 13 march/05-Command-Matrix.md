# Aegion Command Matrix

| Command ID | Title | Status | Notes |
| :--- | :--- | :--- | :--- |
| `aegion.startSession` | Aegion: Start Session | ✅ Active | Core workflow. |
| `aegion.closeSession` | Aegion: Close Session | ✅ Active | Replaces `End Session`. |
| `aegion.showSessionMenu` | Aegion: Session Menu | ✅ Active | Helper for session actions. |
| `aegion.createProposal` | Aegion: Create Proposal | ✅ Active | Replaces `Propose Decision`. |
| `aegion.promoteDecision` | Aegion: Promote Decision (T1) | ✅ Active | Alias for `createProposal`. |
| `aegion.invokeCouncil` | Aegion: Invoke AI Council | ✅ Active | Replaces `Ask Child Council`. |
| `aegion.approveProposal` | Aegion: Approve Proposal | ✅ Active | Core governance action. |
| `aegion.setRole` | Aegion: Set Governance Role | ✅ Active | Identity management. |
| `aegion.rejectDecision` | Aegion: Reject Proposal | ✅ Active | Governance action. |
| `aegion.supersedeDecision` | Aegion: Supersede Decision | ✅ Active | Lifecycle management. |
| `aegion.generateADR` | Aegion: Generate ADR | ✅ Active | Documentation generation. |
| `aegion.queryMemory` | Aegion: Query Memory | ✅ Active | Knowledge retrieval. |
| `aegion.showADRGraph` | Aegion: Show ADR Graph | ✅ Active | Visualization. |
| `aegion.chronos.refresh` | Aegion: Refresh Chronos | ✅ Active | UI Helper. |
| `aegion.openCloudDelegate` | Aegion: Open Cloud Delegate | ✅ Active | Phase 35 feature. |
| `aegion.sentinel.refresh` | Aegion: Refresh Sentinel Health | ✅ Active | UI Helper. |
| `aegion.openAuditLog` | Aegion: Open Audit Log | ✅ Active | Phase F feature. |
| `aegion.openAdminDashboard` | Aegion: Open Admin Dashboard | ✅ Active | Phase F feature. |
| `aegion.openMultiFileReview` | Aegion: Open Multi-File Review | ✅ Active | Phase F feature. |
| `aegion.openWarRoom` | Aegion: Open War Room | ✅ Active | Phase 33 feature. |
| `aegion.openDashboard` | Aegion: Open Dashboard | ✅ Active | Main entry point. |
| `aegion.openCollaboration` | Aegion: Open Collaboration Panel | ✅ Active | Phase 32 feature. |
| `aegion.openGovernanceCenter` | Aegion: Open Governance Center | ✅ Active | Archon UI. |
| `aegion.openSkillCatalog` | Aegion: Open Skill Catalog | ✅ Active | Phase 31 feature. |
| `aegion.openTimeline` | Aegion: Open Timeline | ✅ Active | Phase 5 feature. |
| `aegion.openCheckpoints` | Aegion: Open Checkpoints | ✅ Active | Phase 29 feature. |
| `aegion.openObservability` | Aegion: Open Observability | ✅ Active | Phase 5 feature. |
| `aegion.openTaskInbox` | Aegion: Open Task Inbox | ✅ Active | Phase 28 feature. |
| `aegion.openSessionExplorer` | Aegion: Open Session Explorer | ✅ Active | Dashboard Intel. |
| `aegion.openMemoryRules` | Aegion: Open Memory Rules | ✅ Active | Phase 30 feature. |
| `aegion.openSystemHealth` | Aegion: Open System Health | ✅ Active | Failure Mode UI. |
| `aegion.showGovernancePolicy` | Aegion: Show Governance Policy | ✅ Active | Read-only view. |
| `aegion.lookupConcept` | Aegion: Lookup Concept | ✅ Active | Context feature. |
| `aegion.chronos.openItem` | Aegion: Open Chronos Item | ✅ Active | UI Helper. |
| `aegion.recovery.recoverSession`| Aegion: Recover Session | ✅ Active | Reliability feature. |
| `aegion.recovery.restoreDraft` | Aegion: Restore Draft | ✅ Active | Reliability feature. |
| `aegion.recovery.deleteDraft` | Aegion: Delete Draft | ✅ Active | Reliability feature. |
| `aegion.recovery.refresh` | Aegion: Refresh Recovery | ✅ Active | UI Helper. |

## Deprecated / Removed
- `Aegion: Propose Decision` -> Renamed to `createProposal`.
- `Aegion: Ask Child Council` -> Renamed to `invokeCouncil`.
- `Aegion: Classify Current Selection` -> Removed (integrated into proposal flow).
- `Aegion: Run Evidence Execution` -> Removed (handled by automated evidence gathering).
- `Aegion: Link Decision to Current Commit` -> Removed (handled by session tracking).
- `Aegion: End Session` -> Renamed to `closeSession`.
- `Aegion: Open Archon UI` -> Renamed to `openGovernanceCenter`.
