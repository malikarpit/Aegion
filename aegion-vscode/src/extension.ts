import * as vscode from 'vscode';
import * as cp from 'child_process';
import { Logger } from './services/Logger';
import { SessionManager, SessionState } from './session/manager';

import { registerContextEngine } from './context/ContextEngine';
import { registerGhostText } from './services/GhostTextService';
import { CollaborationService } from './services/CollaborationService';
import { getApiClient, ImpactLevel, ReversibilityLevel, MemorySearchResult } from './api/client';
import { AegionSidebarProvider } from './views/sidebar';
import { IdentityManager, getIdentityManager } from './identity/IdentityManager';
import { DiffManager } from './services/DiffManager';
import { GovernanceStatusBar } from './views/statusBar';
import { DashboardPanel } from './views/Dashboard';
import { ArchonUIPanel } from './views/ArchonUI';
import { ThoughtService } from './services/ThoughtService';
import { ThoughtPanel } from './views/ThoughtPanel';
import { FeatureFlagService } from './services/features';
import { SessionExplorerPanel } from './views/SessionExplorer';
import { TelemetryService } from './services/TelemetryService';
import { FailureModePanel } from './views/FailureMode';
import { ObservabilityPanel } from './views/Observability';
import { TimelinePanel } from './views/Timeline';
import { TaskInboxPanel } from './views/TaskInbox';
import { CheckpointPanel } from './views/CheckpointPanel';
import { MemoryRulesPanel } from './views/MemoryRulesPanel';
import { SkillCatalogPanel } from './views/SkillCatalogPanel';
import { CollaborationPanel } from './views/CollaborationPanel';
import { ConflictDecorator } from './views/ConflictDecorator';
import { WarRoomPanel } from './views/WarRoomPanel';
import { DelegatePanel } from './views/DelegatePanel';
import { AuditLogPanel } from './views/AuditLogPanel';
import { AdminDashboardPanel } from './views/AdminDashboardPanel';
import { MultiFileReviewPanel } from './views/MultiFileReviewPanel';
import { registerConceptNavigation } from './services/ConceptNavigator';
import { registerADRGraph } from './views/ADRGraph';
import { registerChronosExplorer } from './views/ChronosExplorer';
import { registerSentinelHealth } from './views/SentinelHealth';
import { registerRecoveryView } from './views/RecoveryView';

// Phase 52-55 imports
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { FirebaseAuthProvider, getFirebaseAuth } from './auth/FirebaseAuthProvider';
import { registerSessionTree } from './views/SessionTreeProvider';
import { registerTimelineTree } from './views/TimelineTreeProvider';
import { registerProposalTree } from './views/ProposalTreeProvider';
import { registerRiskTree } from './views/RiskTreeProvider';
import { registerCostTree } from './views/CostTreeProvider';
import { CouncilPanel } from './views/CouncilPanel';
import { AegionModelSettingsProvider } from './providers/AegionModelSettingsProvider';
import { ModelStatusBar } from './views/ModelStatusBar';



let sessionManager: SessionManager;
let identityManager: IdentityManager;

export function activate(context: vscode.ExtensionContext) {
    Logger.initialize(context);
    Logger.info('Aegion extension is now active');

    // Initialize Managers
    sessionManager = new SessionManager(context);
    identityManager = getIdentityManager(context);

    // Initialize API Client
    const apiClient = getApiClient();

    // Initialize Services
    const thoughtService = ThoughtService.getInstance(apiClient);
    const collaborationService = CollaborationService.getInstance(apiClient);

    // Initialize Feature Flags
    const _featureService = FeatureFlagService.getInstance(context);

    // Initialize Conflict Decorator (Phase 3)
    const conflictDecorator = new ConflictDecorator(collaborationService);
    context.subscriptions.push(conflictDecorator);

    // Initialize Telemetry
    const telemetry = TelemetryService.getInstance();
    context.subscriptions.push(telemetry);
    telemetry.sendEvent('ExtensionActivate', { version: context.extension.packageJSON.version });

    // Register sidebar webview provider for all sidebar views
    const sidebarProvider = new AegionSidebarProvider(context.extensionUri, sessionManager);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('aegion.views.context', sidebarProvider),
        vscode.window.registerWebviewViewProvider('aegion.views.participants', sidebarProvider),
    );

    // Phase 86: Register Model Settings Webview View
    const modelSettingsProvider = new AegionModelSettingsProvider(context.extensionUri, apiClient, sessionManager);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('aegion.modelSettingsView', modelSettingsProvider),
    );

    // Initialize Governance Status Bar
    const governanceStatusBar = new GovernanceStatusBar(context);
    const modelStatusBar = new ModelStatusBar(context, apiClient, sessionManager);
    sessionManager.onStateChange((state: SessionState) => {
        governanceStatusBar.update(state);
        modelStatusBar.update();
    });

    // Register Ghost Text (Phase 2.5)
    registerGhostText(context, sessionManager);

    // Register Concept Navigation
    registerConceptNavigation(context);

    // Context Engine
    const contextEngine = registerContextEngine(context);
    contextEngine.setSessionAccessor(() => {
        const s = sessionManager.getState();
        return {
            session_id: s.sessionId,
            status: s.status,
            decision_count: s.decisionCount,
            evidence_count: s.evidenceCount,
            exploration_stage: s.explorationStage,
        };
    });

    // Phase 4 View Registrations (previously missing from activate)
    registerADRGraph(context);
    registerChronosExplorer(context);
    registerSentinelHealth(context);
    registerRecoveryView(context);

    // Phase 52: Initialize Firebase Auth
    const firebaseAuth = getFirebaseAuth(context);
    firebaseAuth.restoreSession();  // Try to restore previous session
    firebaseAuth.onAuthStateChanged((state) => {
        if (state.authenticated) {
            Logger.info(`Authenticated as ${state.email}`);
        }
    });

    // Phase 53: TreeView providers
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _sessionTreeProvider = registerSessionTree(context);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _timelineTreeProvider = registerTimelineTree(context);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _proposalTreeProvider = registerProposalTree(context);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _riskTreeProvider = registerRiskTree(context);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _costTreeProvider = registerCostTree(context);

    // ========== Command Registrations ==========

    // Start Session
    const startSessionCmd = vscode.commands.registerCommand('aegion.startSession', async () => {
        await sessionManager.startSession();
    });

    // Close Session
    const closeSessionCmd = vscode.commands.registerCommand('aegion.closeSession', async () => {
        const distill = await vscode.window.showQuickPick(['Yes, distill artifacts', 'No, discard'], {
            placeHolder: 'Distill session into artifacts?',
        });
        await sessionManager.closeSession(distill === 'Yes, distill artifacts');
    });

    // Show Session Menu
    const showSessionMenuCmd = vscode.commands.registerCommand('aegion.showSessionMenu', async () => {
        const state = sessionManager.getState();
        const items = state.status === 'active'
            ? ['Close Session', 'View Session Info', 'Create Proposal']
            : ['Start Session', 'Set Auth Token'];

        const choice = await vscode.window.showQuickPick(items, {
            placeHolder: 'Aegion Session',
        });

        switch (choice) {
            case 'Start Session':
                await sessionManager.startSession();
                break;
            case 'Set Auth Token':
                vscode.commands.executeCommand('aegion.setAuthToken');
                break;
            case 'Close Session':
                await sessionManager.closeSession(true);
                break;
            case 'Create Proposal':
                vscode.commands.executeCommand('aegion.createProposal');
                break;
            case 'View Session Info':
                vscode.window.showInformationMessage(
                    `Session: ${state.sessionId}\nDecisions: ${state.decisionCount}\nEvidence: ${state.evidenceCount}`,
                );
                break;
        }
    });

    // Set Auth Token
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _setAuthTokenCmd = vscode.commands.registerCommand('aegion.setAuthToken', async () => {
        const token = await vscode.window.showInputBox({
            prompt: 'Enter Aegion Auth Token',
            password: true,
            placeHolder: 'Paste your Firebase auth token here',
        });

        if (token) {
            await vscode.workspace.getConfiguration('aegion').update('authToken', token, vscode.ConfigurationTarget.Global);
            vscode.window.showInformationMessage('Auth token updated. Please reload the window to apply.');
            // Ideally we'd update the client instance dynamically, but reload is safer for now.
        }
    });

    // Create Proposal (T1)
    const createProposalCmd = vscode.commands.registerCommand('aegion.createProposal', async () => {
        const state = sessionManager.getState();
        if (!state.sessionId) {
            vscode.window.showWarningMessage('Start a session first');
            return;
        }

        // Gather proposal details
        const title = await vscode.window.showInputBox({
            prompt: 'Proposal Title',
            placeHolder: 'e.g., "Add user authentication"',
        });
        if (!title) { return; }

        const description = await vscode.window.showInputBox({
            prompt: 'Description',
            placeHolder: 'What does this change accomplish?',
        });
        if (!description) { return; }

        const impact = await vscode.window.showQuickPick(['trivial', 'local', 'cross_module', 'system_wide', 'external'], {
            placeHolder: 'Impact Level',
        });
        if (!impact) { return; }

        const reversibility = await vscode.window.showQuickPick(['trivial', 'easy', 'moderate', 'difficult', 'irreversible'], {
            placeHolder: 'Reversibility',
        });
        if (!reversibility) { return; }

        try {
            const api = getApiClient();

            // Collect structured reasoning from the user
            const assumptions = await collectMultiInput(
                'What assumptions are you making?',
                'e.g., "Database supports JSONB columns" (leave empty to finish)',
            );

            const constraints = await collectMultiInput(
                'What constraints apply?',
                'e.g., "Must not break existing API contracts" (leave empty to finish)',
            );

            const alternatives = await collectMultiInput(
                'What alternatives did you consider?',
                'e.g., "Considered REST instead of gRPC" (leave empty to finish)',
            );

            const proposal = await api.createProposal(state.sessionId, {
                session_id: state.sessionId,
                title: title,
                description: description,
                impact_level: impact as ImpactLevel,
                reversibility: reversibility as ReversibilityLevel,
                affected_modules: [],
                affected_files: [],
                reasoning: {
                    problem_framing: description,
                    assumptions: assumptions,
                    constraints: constraints,
                    alternatives_considered: alternatives,
                },
            });

            vscode.window.showInformationMessage(
                `Proposal created: ${proposal.proposal_id.slice(0, 8)}... (Tier: ${proposal.tier})`,
            );

            TelemetryService.getInstance().sendEvent('ProposalCreated', {
                proposalId: proposal.proposal_id,
                tier: proposal.tier,
                impact: impact,
                reversibility: reversibility,
            });

            // Update session stage to 'proposed'
            sessionManager.setExplorationStage('proposed');
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to create proposal: ${error}`);
        }
    });

    // Promote Decision (legacy alias)
    const promoteDecisionCmd = vscode.commands.registerCommand('aegion.promoteDecision', async () => {
        vscode.commands.executeCommand('aegion.createProposal');
    });


    // Initialize Diff Manager
    const diffManager = new DiffManager(context);

    // ========== Command Registrations ==========

    // ... (Start/Close/ShowSessionMenu/CreateProposal commands remain the same)

    // Invoke AI Council
    const invokeCouncilCmd = vscode.commands.registerCommand('aegion.invokeCouncil', async (prompt?: string) => {
        const state = sessionManager.getState();
        if (!state.sessionId) {
            vscode.window.showWarningMessage('Start a session first');
            return;
        }

        // Get prompt if not provided
        if (!prompt) {
            prompt = await vscode.window.showInputBox({
                prompt: 'Ask the AI Council',
                placeHolder: 'e.g., "How should I implement authentication?"',
            });
        }
        if (!prompt) { return; }

        try {
            const api = getApiClient();

            // Show progress with streaming
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Consulting AI Council...',
                cancellable: true,
            }, async (progress, token) => {
                let fullResponse = '';

                try {
                    const stream = api.invokeCouncilStream(state.sessionId || '', {
                        prompt,
                        context: {
                            workspace: state.workspaceId,
                            stage: state.explorationStage,
                        },
                    });

                    TelemetryService.getInstance().sendEvent('CouncilInvoke', {
                        sessionId: state.sessionId,
                        workspaceId: state.workspaceId,
                        promptLength: prompt.length,
                    });

                    for await (const chunk of stream) {
                        if (token.isCancellationRequested) { break; }
                        fullResponse += chunk;
                        // Show liveness
                        progress.report({ message: `Thinking... ${fullResponse.slice(-30).replace(/[\r\n]+/g, ' ')}` });
                    }
                } catch (err) {
                    vscode.window.showErrorMessage(`Stream error: ${err}`);
                    return;
                }

                if (token.isCancellationRequested) { return; }

                // Simple heuristic to extract code for diff
                const recommendation = fullResponse;
                let codeBlock: string | undefined;

                if (recommendation.includes('```')) {
                    const parts = recommendation.split('```');
                    if (parts.length >= 2) {
                        let code = parts[1];
                        // Strip language identifier
                        const firstLineBreak = code.indexOf('\n');
                        if (firstLineBreak > -1) {
                            code = code.substring(firstLineBreak + 1);
                        }
                        codeBlock = code.trim();
                    }
                }

                const displayMsg = `✅ Council Response:\n${recommendation.slice(0, 300)}${recommendation.length > 300 ? '...' : ''}`;

                if (codeBlock) {
                    const selection = await vscode.window.showInformationMessage(displayMsg, 'Show Diff', 'Close');
                    if (selection === 'Show Diff') {
                        // Use active editor or untitled
                        const uri = vscode.window.activeTextEditor?.document.uri || vscode.Uri.parse('untitled:proposal');
                        // Use DiffManager to show diff (it treats string as full content if not unified checksum)
                        await diffManager.showDiff(uri, codeBlock, 'AI Proposal');
                    }
                } else {
                    vscode.window.showInformationMessage(displayMsg);
                }
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Council failed: ${error}`);
        }
    });

    // Approve Proposal (T1+)
    const approveProposalCmd = vscode.commands.registerCommand('aegion.approveProposal', async () => {
        const state = sessionManager.getState();
        if (!state.sessionId) {
            vscode.window.showWarningMessage('Start a session first');
            return;
        }

        const proposalId = await vscode.window.showInputBox({
            prompt: 'Proposal ID to approve',
        });
        if (!proposalId) { return; }

        // Fetch proposal info to show tier-aware confirmation
        try {
            const api = getApiClient();
            let proposalTier = 'T1';
            try {
                const proposalInfo = await api.getProposal(state.sessionId, proposalId);
                proposalTier = proposalInfo?.tier || 'T1';
            } catch {
                // If can't fetch, proceed with default tier
            }

            const tierLabels: Record<string, string> = {
                'T0': '🟢 T0 (Auto-approve)',
                'T1': '🟡 T1 (Single approval)',
                'T2': '🟠 T2 (Architect review required)',
                'T3': '🔴 T3 (Admin-only, high impact)',
            };

            const tierWarnings: Record<string, string> = {
                'T2': '⚠️ T2 proposals require architect-level authority.',
                'T3': '🚨 T3 proposals require admin authority and carry system-wide impact.',
            };

            const tierLabel = tierLabels[proposalTier] || proposalTier;
            const tierWarning = tierWarnings[proposalTier];

            // Show tier info and warning for T2+
            if (tierWarning) {
                const proceed = await vscode.window.showWarningMessage(
                    `${tierLabel}\n${tierWarning}\nAre you sure you have the authority to approve?`,
                    'Yes, Approve',
                    'Cancel',
                );
                if (proceed !== 'Yes, Approve') { return; }
            }

            const justification = await vscode.window.showInputBox({
                prompt: `Approval justification for ${tierLabel}`,
                placeHolder: 'Why are you approving this?',
            });
            if (!justification) { return; }

            const result = await api.approveProposal(state.sessionId, proposalId, {
                evidence_ids: [],
                justification: justification,
            });

            vscode.window.showInformationMessage(
                `✅ Approved! ${tierLabel} → Proposal: ${result.proposal_id.slice(0, 8)}...`,
            );

            sessionManager.incrementDecisionCount();
            sessionManager.setExplorationStage('governed');

            TelemetryService.getInstance().sendEvent('ProposalApproved', {
                proposalId: result.proposal_id,
                tier: proposalTier,
                approverRole: identityManager.getRole(),
            });

            // Clean up old diffs
            diffManager.cleanup();

        } catch (error) {
            vscode.window.showErrorMessage(`Approval failed: ${error}`);
        }
    });

    // ========== NEW COMMANDS (Phase 3) ==========

    // Set Role
    const setRoleCmd = vscode.commands.registerCommand('aegion.setRole', async () => {
        await identityManager.promptRoleSelection();
    });

    // Reject Decision
    const rejectDecisionCmd = vscode.commands.registerCommand('aegion.rejectDecision', async () => {
        if (!identityManager.requirePermission('proposal.reject')) { return; }

        const state = sessionManager.getState();
        if (!state.sessionId) {
            vscode.window.showWarningMessage('Start a session first');
            return;
        }

        const proposalId = await vscode.window.showInputBox({
            prompt: 'Proposal ID to reject',
        });
        if (!proposalId) { return; }

        const reason = await vscode.window.showInputBox({
            prompt: 'Rejection reason',
            placeHolder: 'Why is this being rejected?',
        });
        if (!reason) { return; }

        try {
            const api = getApiClient();
            await api.rejectProposal(state.sessionId, proposalId, reason);
            vscode.window.showInformationMessage(`❌ Proposal rejected: ${proposalId.slice(0, 8)}...`);

            TelemetryService.getInstance().sendEvent('ProposalRejected', {
                proposalId: proposalId,
                rejectorRole: identityManager.getRole(),
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Rejection failed: ${error}`);
        }
    });

    // Supersede Decision
    const supersedeDecisionCmd = vscode.commands.registerCommand('aegion.supersedeDecision', async () => {
        if (!identityManager.requirePermission('decision.supersede')) { return; }

        const state = sessionManager.getState();
        if (!state.sessionId) {
            vscode.window.showWarningMessage('Start a session first');
            return;
        }

        const oldDecisionId = await vscode.window.showInputBox({
            prompt: 'Decision ID to supersede',
        });
        if (!oldDecisionId) { return; }

        const reason = await vscode.window.showInputBox({
            prompt: 'Reason for supersession',
            placeHolder: 'Why is this decision being replaced?',
        });
        if (!reason) { return; }

        vscode.window.showInformationMessage(
            `Creating new proposal to supersede decision ${oldDecisionId.slice(0, 8)}...`,
        );

        // Trigger proposal creation with supersession context
        vscode.commands.executeCommand('aegion.createProposal');
    });

    // Generate ADR
    const generateADRCmd = vscode.commands.registerCommand('aegion.generateADR', async () => {
        if (!identityManager.requirePermission('adr.generate')) { return; }

        const decisionId = await vscode.window.showInputBox({
            prompt: 'Decision ID to generate ADR for',
        });
        if (!decisionId) { return; }

        try {
            const api = getApiClient();

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Generating ADR...',
                cancellable: false,
            }, async () => {
                const adr = await api.generateADR(decisionId);

                // Create new document with ADR content
                const doc = await vscode.workspace.openTextDocument({
                    content: adr.markdown,
                    language: 'markdown',
                });
                await vscode.window.showTextDocument(doc);

                vscode.window.showInformationMessage(
                    `📝 ADR generated: ${adr.title}`,
                );
            });
        } catch (error) {
            vscode.window.showErrorMessage(`ADR generation failed: ${error}`);
        }
    });

    // Query Memory
    const queryMemoryCmd = vscode.commands.registerCommand('aegion.queryMemory', async () => {
        const query = await vscode.window.showInputBox({
            prompt: 'Search Chronos memory',
            placeHolder: 'e.g., "authentication decisions" or "security proposals"',
        });
        if (!query) { return; }

        try {
            const api = getApiClient();

            const results = await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Searching Chronos...',
                cancellable: false,
            }, async () => {
                return await api.queryMemory(query);
            });

            if (results.length === 0) {
                vscode.window.showInformationMessage('No results found');
                return;
            }

            // Show results in quick pick
            interface MemoryMetadata {
                title?: string;
                type?: string;
                decision_id?: string;
                summary?: string;
            }

            const items = results.map((r: MemorySearchResult) => {
                const meta = (r.metadata || {}) as unknown as MemoryMetadata;
                return {
                    label: meta.title || r.id.slice(0, 8) || 'Unknown',
                    description: meta.type || r.source,
                    detail: r.content.slice(0, 100),
                    result: r,
                };
            });

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: `Found ${results.length} results`,
            });

            if (selected) {
                // Show full result
                const doc = await vscode.workspace.openTextDocument({
                    content: JSON.stringify(selected.result, null, 2),
                    language: 'json',
                });
                await vscode.window.showTextDocument(doc);
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Memory query failed: ${error}`);
        }
    });

    // Governance Policy Viewer
    const showGovernancePolicyCmd = vscode.commands.registerCommand('aegion.showGovernancePolicy', async () => {
        try {
            const api = getApiClient();

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Fetching Governance Policy...',
                cancellable: false,
            }, async () => {
                const policy = await api.getGovernancePolicy();

                // Open JSON document
                const doc = await vscode.workspace.openTextDocument({
                    content: JSON.stringify(policy, null, 2),
                    language: 'json',
                });
                await vscode.window.showTextDocument(doc);
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load governance policy: ${error}`);
        }
    });

    // Dashboard Panel
    const openDashboardCmd = vscode.commands.registerCommand('aegion.openDashboard', () => {
        DashboardPanel.show(context.extensionUri);
    });

    // Governance Center (Archon UI)
    const openGovernanceCenterCmd = vscode.commands.registerCommand('aegion.openGovernanceCenter', () => {
        ArchonUIPanel.show(context.extensionUri);
    });



    // Session Explorer (Dashboard Intel)
    const openSessionExplorerCmd = vscode.commands.registerCommand('aegion.openSessionExplorer', () => {
        SessionExplorerPanel.show(context.extensionUri);
    });

    // System Health (Failure Mode)
    const openHealthCmd = vscode.commands.registerCommand('aegion.openSystemHealth', () => {
        FailureModePanel.show(context.extensionUri);
    });

    // Risk Observatory (Observability)
    const openObservabilityCmd = vscode.commands.registerCommand('aegion.openObservability', () => {
        ObservabilityPanel.show(context.extensionUri);
    });

    // Architecture Timeline (Phase 5)
    const openTimelineCmd = vscode.commands.registerCommand('aegion.openTimeline', () => {
        TimelinePanel.show(context.extensionUri);
    });

    // Task Inbox (Phase 28)
    const openTaskInboxCmd = vscode.commands.registerCommand('aegion.openTaskInbox', () => {
        TaskInboxPanel.show(context.extensionUri);
    });

    // Checkpoints (Phase 29)
    const openCheckpointsCmd = vscode.commands.registerCommand('aegion.openCheckpoints', () => {
        CheckpointPanel.show(context.extensionUri);
    });

    // Memory & Rules (Phase 30)
    const openMemoryRulesCmd = vscode.commands.registerCommand('aegion.openMemoryRules', () => {
        MemoryRulesPanel.show(context.extensionUri);
    });

    // Skill Catalog (Phase 31)
    const openSkillCatalogCmd = vscode.commands.registerCommand('aegion.openSkillCatalog', () => {
        SkillCatalogPanel.show(context.extensionUri);
    });

    // Collaboration (Phase 5)
    const openCollaborationCmd = vscode.commands.registerCommand('aegion.openCollaboration', () => {
        CollaborationPanel.show(context.extensionUri, collaborationService);
    });

    // War Room (Phase 33)
    const openWarRoomCmd = vscode.commands.registerCommand('aegion.openWarRoom', () => {
        WarRoomPanel.show(context.extensionUri);
    });

    // Cloud Delegate (Phase 35)
    const openCloudDelegateCmd = vscode.commands.registerCommand('aegion.openCloudDelegate', () => {
        DelegatePanel.createOrShow(context.extensionUri);
    });

    // Phase F: Audit Log Viewer
    const openAuditLogCmd = vscode.commands.registerCommand('aegion.openAuditLog', () => {
        AuditLogPanel.show(context.extensionUri);
    });

    // Phase F: Admin Dashboard
    const openAdminDashboardCmd = vscode.commands.registerCommand('aegion.openAdminDashboard', () => {
        AdminDashboardPanel.show(context.extensionUri);
    });

    // Phase F: Multi-File Review
    const openMultiFileReviewCmd = vscode.commands.registerCommand('aegion.openMultiFileReview', () => {
        MultiFileReviewPanel.show(context.extensionUri);
    });

    // Phase 52: Firebase Auth commands
    const loginCmd = vscode.commands.registerCommand('aegion.login', async () => {
        const method = await vscode.window.showQuickPick(
            ['Email & Password', 'Google OAuth'],
            { placeHolder: 'Choose login method' },
        );

        if (method === 'Email & Password') {
            const email = await vscode.window.showInputBox({ prompt: 'Email' });
            if (!email) { return; }
            const password = await vscode.window.showInputBox({ prompt: 'Password', password: true });
            if (!password) { return; }
            await firebaseAuth.loginWithEmail(email, password);
        } else if (method === 'Google OAuth') {
            await firebaseAuth.loginWithGoogle();
        }
    });

    const logoutCmd = vscode.commands.registerCommand('aegion.logout', async () => {
        await firebaseAuth.logout();
    });

    // Phase 55: Council Panel
    const openCouncilPanelCmd = vscode.commands.registerCommand('aegion.openCouncilPanel', () => {
        CouncilPanel.show(context.extensionUri);
    });

    // Phase 55: Sentinel scan
    const sentinelScanCmd = vscode.commands.registerCommand('aegion.sentinel.scan', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('Open a file to scan');
            return;
        }

        try {
            const api = getApiClient();
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Running Sentinel scan...',
                cancellable: false,
            }, async () => {
                const result = await (api as any).runSentinelScan?.({
                    file_path: editor.document.uri.fsPath,
                    content: editor.document.getText(),
                    language: editor.document.languageId,
                });
                if (result?.risks?.length > 0) {
                    vscode.window.showWarningMessage(
                        `Sentinel found ${result.risks.length} risk(s): ${result.risks.map((r: { description: string }) => r.description).join('; ')}`,
                    );
                } else {
                    vscode.window.showInformationMessage('✅ Sentinel scan: No risks detected');
                }
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Sentinel scan failed: ${error}`);
        }
    });

    // Register all commands
    context.subscriptions.push(
        startSessionCmd,
        closeSessionCmd,
        showSessionMenuCmd,
        createProposalCmd,
        promoteDecisionCmd,
        invokeCouncilCmd,
        approveProposalCmd,
        // New Phase 3 commands
        setRoleCmd,
        rejectDecisionCmd,
        supersedeDecisionCmd,
        generateADRCmd,
        queryMemoryCmd,
        // Governance Policy Viewer
        showGovernancePolicyCmd,
        // Dashboard
        openDashboardCmd,
        // Archon UI
        openGovernanceCenterCmd,
        // War Room
        openWarRoomCmd,
        // Session Explorer
        openSessionExplorerCmd,
        // System Health
        openHealthCmd,
        // Observability
        openObservabilityCmd,
        // Timeline
        openTimelineCmd,
        // Task Inbox
        openTaskInboxCmd,
        // Checkpoints
        openCheckpointsCmd,
        // Memory & Rules
        openMemoryRulesCmd,
        // Skill Catalog
        openSkillCatalogCmd,
        // Collaboration
        openCollaborationCmd,
        // Cloud Delegate
        openCloudDelegateCmd,
        // Audit Log, Admin, Multi-File Review
        openAuditLogCmd,
        openAdminDashboardCmd,
        openMultiFileReviewCmd,
        // Phase 52: Auth
        loginCmd,
        logoutCmd,
        // Phase 55: Council Panel + Sentinel
        openCouncilPanelCmd,
        sentinelScanCmd,

        // Resolve Conflict (Phase 3)
        vscode.commands.registerCommand('aegion.resolveConflict', async (conflict: { message: string } | undefined) => {
            // If triggered from codelens/decoration, we might get an arg.
            // For now, let's assume we invoke this and pick a conflict or use active editor context.

            // Invoke Council with specific context
            vscode.commands.executeCommand('aegion.invokeCouncil',
                `Help me resolve this governance conflict: ${conflict ? conflict.message : 'Unknown violation'}`,
            );
        }),

        // Phase 4: Thought-Commit Protocol
        vscode.commands.registerCommand('aegion.captureThought', () => {
            ThoughtPanel.createOrShow(context.extensionUri, thoughtService);
        }),
        vscode.commands.registerCommand('aegion.linkCurrentThought', async () => {
            // Get current commit hash (mock or via git extension API)
            // For MVP, ask user or assume they want to link manual SHA
            const sha = await vscode.window.showInputBox({
                prompt: 'Enter commit SHA to link (or leave empty to pick from git history if available)',
                placeHolder: 'git commit sha',
            });

            if (sha) {
                await thoughtService.linkToCommit(sha);
            } else {
                // Integrate with vscode.git extension to get HEAD
                const gitExtension = vscode.extensions.getExtension('vscode.git');
                if (gitExtension) {
                    const git = gitExtension.exports.getAPI(1);
                    const repo = git.repositories[0];
                    if (repo && repo.state.HEAD && repo.state.HEAD.commit) {
                        const headSha = repo.state.HEAD.commit;
                        await thoughtService.linkToCommit(headSha);
                    } else {
                        vscode.window.showErrorMessage('No active git repository or HEAD commit found.');
                    }
                }
            }
        }),

        vscode.commands.registerCommand('aegion.commitThought', async () => {
            const draft = thoughtService.currentDraft;
            if (!draft) {
                vscode.window.showWarningMessage('No active thought to commit.');
                return;
            }

            // Format commit message
            const message = `${draft.title}\n\n${draft.rationale}\n\nCloses-Thought: ${draft.thought_id}`;

            // Populate SCM input box
            const gitExtension = vscode.extensions.getExtension('vscode.git');
            if (gitExtension) {
                const git = gitExtension.exports.getAPI(1);
                const repo = git.repositories[0];
                if (repo) {
                    repo.inputBox.value = message;
                    vscode.window.showInformationMessage('Commit message populated from Thought.');
                } else {
                    vscode.window.showErrorMessage('No active git repository found.');
                }
            }
        }),



        // Explain Why (Phase 4)
        vscode.commands.registerCommand('aegion.explainWhy', async () => {
            const state = sessionManager.getState();
            if (!state.sessionId) {
                vscode.window.showWarningMessage('Start a session first to track rationale.');
                return;
            }

            const rationale = await vscode.window.showInputBox({
                prompt: 'Why are you making this change?',
                placeHolder: 'e.g., Fixing timeout bug in CouncilService',
            });
            if (!rationale) { return; }

            const title = `Rationale: ${rationale.slice(0, 50)}...`;

            try {
                await thoughtService.startDraft(title, rationale, state.sessionId, state.workspaceId);
                vscode.window.showInformationMessage('Thought draft created.');
                ThoughtPanel.createOrShow(context.extensionUri, thoughtService);
            } catch (error) {
                vscode.window.showErrorMessage(`Failed to create thought: ${error}`);
            }
        }),

        // Show Rationale (Phase 4)
        vscode.commands.registerCommand('aegion.showRationale', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Open a file to see rationale.');
                return;
            }

            const line = editor.selection.active.line + 1;
            const fsPath = editor.document.uri.fsPath;
            const cwd = vscode.workspace.getWorkspaceFolder(editor.document.uri)?.uri.fsPath;

            if (!cwd) { return; }

            // Simple git blame to get hash
            const cmd = `git blame -L ${line},${line} -s --no-show-name "${fsPath}"`;

            cp.exec(cmd, { cwd }, async (err, stdout, _stderr) => {
                if (err || !stdout) {
                    vscode.window.showInformationMessage('Could not determine commit for this line.');
                    return;
                }

                const hash = stdout.split(' ')[0].trim();
                // git blame might return caret if boundary, or 00000000 if not committed
                if (hash && hash.length > 5 && !hash.startsWith('0000')) {
                    try {
                        const client = getApiClient();
                        // We need to use the raw client to fetch by commit if exposed, or add to service
                        // The ThoughtService doesn't expose getByCommit publicly, but we can access client directly
                        // Or better, add it to ThoughtService.
                        // For now, let's assume we can access client as per imports.

                        // We need access to the `thoughts` resource on client.
                        // client type is AegionClient.
                        // Let's use the any cast if strictly needed or assume client has it as seen in ThoughtService.ts

                        const thought = await client.thoughts.getByCommit(hash);

                        if (thought) {
                            const _detail = `**${thought.title}**\n\n${thought.rationale}`;
                            vscode.window.showInformationMessage(`Rationale [${hash.slice(0, 7)}]: ${thought.title}`, { modal: true, detail: thought.rationale });
                        } else {
                            vscode.window.showInformationMessage(`No Aegion rationale found for commit ${hash.slice(0, 7)}`);
                        }
                    } catch (e) {
                        // Silent fail or log
                        console.error(e);
                        vscode.window.showInformationMessage(`No rationale found (or API error) for ${hash.slice(0, 7)}`);
                    }
                } else {
                    vscode.window.showInformationMessage('Line is not committed yet.');
                }
            });
        }),

        vscode.commands.registerCommand('aegion.generateThoughtReport', async () => {
            const countStr = await vscode.window.showInputBox({
                prompt: 'How many recent commits to scan for thoughts?',
                value: '10',
            });
            if (!countStr) { return; }
            const count = parseInt(countStr);

            const gitExtension = vscode.extensions.getExtension('vscode.git');
            if (!gitExtension) {
                vscode.window.showErrorMessage('Git extension not found');
                return;
            }
            const git = gitExtension.exports.getAPI(1);
            const repo = git.repositories[0];
            if (!repo) {
                vscode.window.showErrorMessage('No git repository found');
                return;
            }

            try {
                const log = await repo.log({ maxEntries: count });
                const shas = log.map((c: { hash: string }) => c.hash);

                const report = await thoughtService.generateReport(shas);

                const doc = await vscode.workspace.openTextDocument({
                    content: report,
                    language: 'markdown',
                });
                await vscode.window.showTextDocument(doc);

            } catch (e) {
                vscode.window.showErrorMessage(`Failed to generate report: ${e}`);
            }
        }),
    );

    // ========== Governance SCM Boundary ==========

    // Warn on save without active session
    context.subscriptions.push(
        vscode.workspace.onWillSaveTextDocument(async (e) => {
            const state = sessionManager.getState();
            // Skip if active session or if it's a system file/temp file
            if (state.status === 'active' || e.document.uri.scheme !== 'file') {
                return;
            }

            // Simple throttle or just always warn for now (it's a "Boundary")
            // We use waitUntil to potentially block save (optional) or just warn async.
            // onWillSave is synchronous/blocking in some contexts but for UX warning we can just show message.
            // Actually, showing a modal dialog here might block the save or be ignored if save happens background.

            // We'll show a warning message.
            // Note: We can't easily block the save from here without 'waitUntil' and a promise rejection,
            // but blocking save is hostile. We just warn.

            const selection = await vscode.window.showWarningMessage(
                `⚠️ Saving ungoverned change in '${e.document.fileName.split('/').pop()}'. Start a session to track?`,
                'Start Session',
                'Ignore',
            );

            if (selection === 'Start Session') {
                await sessionManager.startSession();
            }
        }),
    );

    // Health check on activation
    checkBackendHealth();
}

async function checkBackendHealth(): Promise<void> {
    try {
        const api = getApiClient();
        await api.healthCheck();
        Logger.info('Aegion backend is healthy');
    } catch {
        Logger.warn('Aegion backend not reachable - running in offline mode');
    }
}

export function deactivate() {
    if (sessionManager) {
        sessionManager.dispose();
    }
    Logger.info('Aegion extension deactivated');
}

/**
 * Collect multiple text inputs from the user.
 * Shows an input box repeatedly until the user submits an empty value.
 */
async function collectMultiInput(prompt: string, placeholder: string): Promise<string[]> {
    const items: string[] = [];
    let adding = true;
    while (adding) {
        const input = await vscode.window.showInputBox({
            prompt: `${prompt} (${items.length} added, leave empty to finish)`,
            placeHolder: placeholder,
        });
        if (input && input.trim()) {
            items.push(input.trim());
        } else {
            adding = false;
        }
    }
    return items;
}
