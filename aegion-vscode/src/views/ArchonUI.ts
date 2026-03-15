/**
 * Aegion ArchonUI - Decision Governance Center
 *
 * Central hub for proposal lifecycle management:
 * - Proposal listing with filters
 * - Proposal detail view
 * - Approve/Reject/Supersede actions
 */

import * as vscode from 'vscode';
import { getApiClient, ProposalResponse } from '../api/client';

export class ArchonUIPanel {
    public static currentPanel: ArchonUIPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static readonly viewType = 'aegion.archonUI';

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables,
        );
        this._panel.webview.html = this._getLoadingHtml();
        this._loadProposals();
    }

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (ArchonUIPanel.currentPanel) {
            ArchonUIPanel.currentPanel._panel.reveal(column);
            ArchonUIPanel.currentPanel._loadProposals();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            ArchonUIPanel.viewType,
            '📋 Governance Center',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        ArchonUIPanel.currentPanel = new ArchonUIPanel(panel, extensionUri);
    }

    private async _handleMessage(message: { command: string; sessionId?: string; proposalId?: string; justification?: string; reason?: string }): Promise<void> {
        const api = getApiClient();

        switch (message.command) {
            case 'approve':
                if (message.sessionId && message.proposalId) {
                    try {
                        await api.approveProposal(message.sessionId, message.proposalId, {
                            evidence_ids: [],
                            justification: message.justification || 'Approved via Archon UI',
                        });
                        vscode.window.showInformationMessage(`Proposal ${message.proposalId} approved`);
                        this._loadProposals();
                    } catch (error) {
                        vscode.window.showErrorMessage(`Failed to approve: ${error}`);
                    }
                }
                break;
            case 'reject':
                if (message.sessionId && message.proposalId) {
                    try {
                        await api.rejectProposal(message.sessionId, message.proposalId, message.reason || 'Rejected via Archon UI');
                        vscode.window.showInformationMessage(`Proposal ${message.proposalId} rejected`);
                        this._loadProposals();
                    } catch (error) {
                        vscode.window.showErrorMessage(`Failed to reject: ${error}`);
                    }
                }
                break;
            case 'refresh':
                this._loadProposals();
                break;
        }
    }

    private async _loadProposals(): Promise<void> {
        try {
            const api = getApiClient();
            const proposals = await api.listDecisions();
            this._panel.webview.html = this._getHtml(proposals);
        } catch (error) {
            this._panel.webview.html = this._getErrorHtml(String(error));
        }
    }

    private _getLoadingHtml(): string {
        return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { 
            font-family: var(--vscode-font-family); 
            background: var(--vscode-editor-background);
            color: var(--vscode-foreground);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .loader {
            border: 4px solid var(--vscode-widget-border);
            border-top: 44px solid var(--vscode-textLink-foreground);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body><div class="loader"></div></body>
</html>`;
    }

    private _getErrorHtml(error: string): string {
        return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { 
            font-family: var(--vscode-font-family); 
            background: var(--vscode-editor-background);
            color: var(--vscode-errorForeground);
            padding: 20px;
        }
    </style>
</head>
<body>
    <h2>⚠️ Failed to load proposals</h2>
    <p>${error}</p>
    <button onclick="vscode.postMessage({command: 'refresh'})">Retry</button>
</body>
</html>`;
    }

    private _getHtml(proposals: ProposalResponse[]): string {
        const proposalRows = proposals.map(p => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const pAny = p as any;
            const quorum = p.quorum_required || 1;
            const approvals = p.approvals_count || 0;
            const quorumMet = approvals >= quorum;
            const reasons = (p.tier_reasons || []).join('; ') || '—';
            const reasonShort = reasons.length > 40 ? reasons.substring(0, 37) + '...' : reasons;
            return `
            <tr class="proposal-row">
                <td><span class="tier tier-${(p.tier || 't1').toLowerCase()}">${p.tier || 'T1'}</span></td>
                <td class="title">${p.title || 'Untitled'}</td>
                <td><span class="quorum ${quorumMet ? 'quorum-met' : 'quorum-pending'}">${approvals}/${quorum}</span></td>
                <td class="reason" title="${reasons}">${reasonShort}</td>
                <td><span class="status status-${(p.status || 'pending').toLowerCase()}">${p.status || 'Pending'}</span></td>
                <td>
                    ${p.status === 'pending' && !quorumMet ? `
                        <button class="btn btn-approve" onclick="handleApprove('${p.proposal_id}', '${pAny.session_id}')">✓</button>
                        <button class="btn btn-reject" onclick="handleReject('${p.proposal_id}', '${pAny.session_id}')">✕</button>
                    ` : '-'}
                </td>
            </tr>
        `;
        }).join('');

        return `<!DOCTYPE html>
<html>
<head>
    <style>
        :root {
            --card-bg: rgba(255,255,255,0.03);
            --card-border: rgba(255,255,255,0.1);
            --accent: #4fc3f7;
            --warning: #ffb74d;
            --success: #81c784;
            --error: #e57373;
        }
        body { 
            font-family: var(--vscode-font-family); 
            background: var(--vscode-editor-background);
            color: var(--vscode-foreground);
            padding: 24px;
            margin: 0;
        }
        h1 {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
        }
        .toolbar {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        .toolbar select, .toolbar button {
            padding: 6px 12px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 6px;
            color: var(--vscode-foreground);
            cursor: pointer;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--card-border);
        }
        th {
            opacity: 0.7;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 1px;
        }
        .tier {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }
        .tier-t0 { background: #90caf9; color: #000; }
        .tier-t1 { background: var(--success); color: #000; }
        .tier-t2 { background: var(--warning); color: #000; }
        .tier-t3 { background: var(--error); color: #000; }
        .status { font-size: 0.85em; }
        .status-pending { color: var(--warning); }
        .status-approved { color: var(--success); }
        .status-rejected { color: var(--error); }
        .quorum {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .quorum-met { background: rgba(129,199,132,0.2); color: var(--success); }
        .quorum-pending { background: rgba(255,183,77,0.2); color: var(--warning); }
        .reason {
            font-size: 0.8em;
            opacity: 0.7;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            cursor: help;
        }
        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            margin-right: 4px;
        }
        .btn-approve { background: var(--success); color: #000; }
        .btn-reject { background: var(--error); color: #fff; }
        .btn:hover { opacity: 0.8; }
        .empty {
            text-align: center;
            padding: 40px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <h1>📋 Decision Governance Center</h1>
    
    <div class="toolbar">
        <select id="filterStatus" onchange="filterProposals()">
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
        </select>
        <button onclick="refreshList()">🔄 Refresh</button>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Tier</th>
                <th>Title</th>
                <th>Quorum</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            ${proposalRows || '<tr><td colspan="6" class="empty">No proposals found</td></tr>'}
        </tbody>
    </table>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        function handleApprove(proposalId, sessionId) {
            const justification = prompt('Approval justification (optional):');
            vscode.postMessage({ command: 'approve', proposalId, sessionId, justification });
        }
        
        function handleReject(proposalId, sessionId) {
            const reason = prompt('Rejection reason:');
            if (reason) {
                vscode.postMessage({ command: 'reject', proposalId, sessionId, reason });
            }
        }
        
        function refreshList() {
            vscode.postMessage({ command: 'refresh' });
        }
        
        function filterProposals() {
            const status = document.getElementById('filterStatus').value;
            const rows = document.querySelectorAll('.proposal-row');
            rows.forEach(row => {
                const rowStatus = row.querySelector('.status').textContent.toLowerCase();
                if (status === 'all' || rowStatus === status) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        ArchonUIPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
