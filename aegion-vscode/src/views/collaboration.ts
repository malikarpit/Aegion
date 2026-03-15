/**
 * Aegion Collaboration Panel.
 *
 * Shows workspace members, pending reviews, and activity feed.
 *
 * Doctrine: "Collaboration requires visibility."
 */

import * as vscode from 'vscode';
import { AegionApiClient, WorkspaceMember, Proposal, TimelineEvent } from '../api/client';
import { EventSourceClient, WorkspaceEvent } from '../api/eventSource';

export class CollaborationPanel implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aegion.collaborationView';

    private _view?: vscode.WebviewView;
    private eventSource: EventSourceClient;
    private workspaceId: string | null = null;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly apiClient: AegionApiClient,
    ) {
        const backendUrl = vscode.workspace.getConfiguration('aegion').get<string>('backendUrl') || 'http://localhost:8000';
        this.eventSource = new EventSourceClient(backendUrl);

        // Register event handlers
        this.setupEventHandlers();
    }

    private setupEventHandlers(): void {
        this.eventSource.onProposalCreated((event) => {
            this.updateView();
            vscode.window.showInformationMessage(
                `New proposal: ${event.payload.title || 'Untitled'}`,
            );
        });

        this.eventSource.onProposalReviewSubmitted((_event) => {
            this.updateView();
        });



        this.eventSource.onMemberJoined((event) => {
            this.updateView();
            vscode.window.showInformationMessage(
                `${event.payload.email || 'Someone'} joined the workspace`,
            );
        });
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ): void {
        this._view = webviewView;

        webviewView.onDidChangeVisibility(() => {
            this.updateView();
        });

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'refresh':
                    await this.updateView();
                    break;
                case 'reviewProposal':
                    await this.reviewProposal(message.proposalId);
                    break;
                case 'connectWorkspace':
                    await this.connectToWorkspace(message.workspaceId);
                    break;
            }
        });
    }

    private async connectToWorkspace(workspaceId: string): Promise<void> {
        this.workspaceId = workspaceId;

        // Get auth token from VS Code settings
        const authToken = vscode.workspace.getConfiguration('aegion').get<string>('authToken') || '';
        if (authToken) {
            this.apiClient.setAuthToken(authToken);
        }

        // Connect SSE for real-time updates
        try {
            await this.eventSource.connect(workspaceId, authToken);
        } catch (error) {
            console.warn('SSE connection failed, falling back to polling:', error);
        }

        await this.updateView();
    }

    private async reviewProposal(proposalId: string): Promise<void> {
        // Open review dialog
        const verdict = await vscode.window.showQuickPick(
            ['Approve', 'Request Changes', 'Comment'],
            { placeHolder: 'Select review verdict' },
        );

        if (!verdict) {
            return;
        }

        const comments = await vscode.window.showInputBox({
            prompt: 'Review comments',
            placeHolder: 'Enter your review comments...',
        });

        if (comments === undefined) {
            return;
        }

        try {
            // Get active session for context
            const sessions = await this.apiClient.getActiveSessions();
            const sessionId = sessions.length > 0 ? sessions[0].session_id : 'unknown';

            await this.apiClient.proposals.addReview(sessionId, proposalId, verdict.toLowerCase().replace(' ', '_'), comments);

            vscode.window.showInformationMessage('Review submitted!');
            await this.updateView();
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to submit review: ${error}`);
        }
    }

    private async updateView(): Promise<void> {
        if (!this._view) {
            return;
        }

        const members: WorkspaceMember[] = [];
        let pendingReviews: Proposal[] = [];
        let recentActivity: WorkspaceEvent[] = [];

        try {
            // Fetch workspace activity to derive participants
            if (this.workspaceId) {
                const activity = await this.apiClient.workspaces.getActivity(this.workspaceId, 50) as unknown as TimelineEvent[];

                // Extract unique members from activity events
                const seen = new Set<string>();
                for (const event of (activity || [])) {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    const userId = event.actor_id || (event as any).user_id;
                    if (userId && !seen.has(userId)) {
                        seen.add(userId);
                        members.push({
                            user_id: userId,
                            display_name: userId,
                            role: 'member',
                            joined_at: event.timestamp || '',
                            status: 'active',
                        });
                    }
                }

                // Map recent events
                recentActivity = (activity || []).slice(0, 15).map((e: TimelineEvent) => ({
                    type: (e.event_type as string) || 'unknown',
                    event_id: (e.event_id as string) || '',
                    timestamp: (e.timestamp as string) || '',
                    payload: e.details || {},
                    user_id: (e.actor_id as string) || 'unknown',
                    actor_id: (e.actor_id as string) || 'unknown',
                }));
            }

            // Fetch pending proposals
            try {
                pendingReviews = await this.apiClient.listPendingProposals() || [];
            } catch (error) {
                console.warn('Failed to fetch pending proposals', error);
            }
        } catch (error) {
            console.error('Failed to fetch collaboration data:', error);
        }

        this._view.webview.postMessage({
            command: 'update',
            data: { members, pendingReviews, recentActivity },
        });
    }

    private _getHtmlForWebview(_webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Collaboration</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 10px;
            color: var(--vscode-foreground);
        }
        .section {
            margin-bottom: 20px;
        }
        .section-header {
            font-weight: bold;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .member {
            display: flex;
            align-items: center;
            padding: 4px 0;
        }
        .member-avatar {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--vscode-button-background);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 8px;
            font-size: 12px;
        }
        .proposal-card {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            padding: 8px;
            margin-bottom: 8px;
        }
        .proposal-title {
            font-weight: bold;
        }
        .proposal-tier {
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 3px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
        }
        .activity-item {
            font-size: 12px;
            padding: 4px 0;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .activity-time {
            color: var(--vscode-descriptionForeground);
            font-size: 11px;
        }
        .btn {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 4px 8px;
            border-radius: 3px;
            cursor: pointer;
        }
        .btn:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .empty-state {
            color: var(--vscode-descriptionForeground);
            font-style: italic;
            text-align: center;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="section">
        <div class="section-header">
            <span>👥 Team Members</span>
        </div>
        <div id="members-list">
            <div class="empty-state">Connect to a workspace to see members</div>
        </div>
    </div>

    <div class="section">
        <div class="section-header">
            <span>📋 Pending Reviews</span>
            <button class="btn" onclick="refresh()">↻</button>
        </div>
        <div id="pending-reviews">
            <div class="empty-state">No proposals pending review</div>
        </div>
    </div>

    <div class="section">
        <div class="section-header">
            <span>📊 Recent Activity</span>
        </div>
        <div id="activity-feed">
            <div class="empty-state">No recent activity</div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }

        function reviewProposal(proposalId) {
            vscode.postMessage({ command: 'reviewProposal', proposalId });
        }

        window.addEventListener('message', event => {
            const message = event.data;
            if (message.command === 'update') {
                updateUI(message.data);
            }
        });

        function updateUI(data) {
            // Update members
            const membersList = document.getElementById('members-list');
            if (data.members && data.members.length > 0) {
                membersList.innerHTML = data.members.map(m => 
                    '<div class="member">' +
                    '<div class="member-avatar">' + (m.display_name || m.email)[0].toUpperCase() + '</div>' +
                    '<span>' + (m.display_name || m.email) + ' (' + m.role + ')</span>' +
                    '</div>'
                ).join('');
            }

            // Update pending reviews
            const reviewsList = document.getElementById('pending-reviews');
            if (data.pendingReviews && data.pendingReviews.length > 0) {
                reviewsList.innerHTML = data.pendingReviews.map(p =>
                    '<div class="proposal-card">' +
                    '<div class="proposal-title">' + p.title + '</div>' +
                    '<span class="proposal-tier">' + p.tier + '</span>' +
                    '<button class="btn" style="float:right" onclick="reviewProposal(\\''+p.proposal_id+'\\')">Review</button>' +
                    '</div>'
                ).join('');
            }

            // Update activity feed
            const activityFeed = document.getElementById('activity-feed');
            if (data.recentActivity && data.recentActivity.length > 0) {
                activityFeed.innerHTML = data.recentActivity.map(a =>
                    '<div class="activity-item">' +
                    '<div>' + a.type + '</div>' +
                    '<div class="activity-time">' + a.timestamp + '</div>' +
                    '</div>'
                ).join('');
            }
        }
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        this.eventSource.disconnect();
    }
}
