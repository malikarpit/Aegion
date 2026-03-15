/**
 * Aegion Session Explorer - Intelligence Dashboard
 *
 * Phase 3: Dashboard Intel
 * Explore sessions by intent, trace decision provenance.
 */

import * as vscode from 'vscode';
import { getApiClient, ProposalResponse, SessionResponse } from '../api/client';

export class SessionExplorerPanel {
    public static currentPanel: SessionExplorerPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static readonly viewType = 'aegion.sessionExplorer';

    private constructor(panel: vscode.WebviewPanel, private readonly _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables,
        );
        this._panel.webview.html = this._getLoadingHtml();
        this._loadData();
    }

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (SessionExplorerPanel.currentPanel) {
            SessionExplorerPanel.currentPanel._panel.reveal(column);
            SessionExplorerPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            SessionExplorerPanel.viewType,
            '🔍 Session Explorer',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        SessionExplorerPanel.currentPanel = new SessionExplorerPanel(panel, extensionUri);
    }

    private async _handleMessage(message: { command: string; sessionId?: string; decisionId?: string }): Promise<void> {
        switch (message.command) {
            case 'refresh':
                this._loadData();
                break;
            case 'viewSession':
                vscode.window.showInformationMessage(`Opening session: ${message.sessionId}`);
                break;
            case 'traceDecision':
                vscode.window.showInformationMessage(`Tracing decision: ${message.decisionId}`);
                break;
        }
    }

    private async _loadData(): Promise<void> {
        try {
            const api = getApiClient();
            const sessions = await api.getActiveSessions();
            const decisions = await api.listDecisions();
            this._panel.webview.html = this._getHtml(sessions, decisions);
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
            border-top: 4px solid var(--vscode-textLink-foreground);
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
    <h2>⚠️ Failed to load session data</h2>
    <p>${error}</p>
    <button onclick="vscode.postMessage({command: 'refresh'})">Retry</button>
</body>
</html>`;
    }

    private _getHtml(sessions: SessionResponse[], decisions: ProposalResponse[]): string {
        const sessionList = sessions.map((s) => `
            <div class="session-card" onclick="viewSession('${s.session_id}')">
                <div class="session-id">${s.session_id?.slice(0, 8) || 'Unknown'}...</div>
                <div class="session-meta">
                    <span class="status status-${s.status || 'active'}">${s.status || 'Active'}</span>
                    <span class="count">${0} decisions</span>
                </div>
            </div>
        `).join('') || '<div class="empty">No active sessions</div>';

        const decisionList = decisions.map((item) => {
            const d = item as ProposalResponse & { decision_id?: string; claim?: string; actor?: string; };
            return `
            <tr onclick="traceDecision('${d.decision_id}')">
                <td class="id">${d.decision_id?.slice(0, 8) || 'Unknown'}...</td>
                <td class="title">${d.title || d.claim || 'Untitled'}</td>
                <td><span class="tier tier-${(d.tier || 't1').toLowerCase()}">${d.tier || 'T1'}</span></td>
                <td><span class="actor">${d.actor || 'system'}</span></td>
            </tr>
        `;
        }).join('') || '<tr><td colspan="4" class="empty">No decisions found</td></tr>';

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
        }
        body { 
            font-family: var(--vscode-font-family); 
            background: var(--vscode-editor-background);
            color: var(--vscode-foreground);
            padding: 24px;
            margin: 0;
        }
        h1 { display: flex; align-items: center; gap: 12px; }
        .toolbar {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }
        .toolbar input {
            flex: 1;
            padding: 8px 12px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 6px;
            color: var(--vscode-foreground);
        }
        .toolbar button {
            padding: 8px 16px;
            background: var(--accent);
            border: none;
            border-radius: 6px;
            color: #000;
            cursor: pointer;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 24px;
        }
        .section {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
        }
        .section h2 { margin-top: 0; font-size: 1.1em; }
        .session-card {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .session-card:hover { background: rgba(255,255,255,0.1); }
        .session-id { font-family: monospace; font-size: 0.9em; }
        .session-meta {
            display: flex;
            justify-content: space-between;
            margin-top: 8px;
            font-size: 0.8em;
            opacity: 0.7;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid var(--card-border);
        }
        th { opacity: 0.7; font-size: 0.8em; text-transform: uppercase; }
        tr { cursor: pointer; transition: background 0.2s; }
        tr:hover { background: rgba(255,255,255,0.05); }
        .id { font-family: monospace; font-size: 0.85em; }
        .tier {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }
        .tier-t0 { background: #90caf9; color: #000; }
        .tier-t1 { background: var(--success); color: #000; }
        .tier-t2 { background: var(--warning); color: #000; }
        .tier-t3 { background: #e57373; color: #000; }
        .status { font-size: 0.75em; }
        .status-active { color: var(--success); }
        .actor { font-size: 0.85em; opacity: 0.8; }
        .empty { text-align: center; padding: 20px; opacity: 0.5; }
    </style>
</head>
<body>
    <h1>🔍 Session Intelligence Explorer</h1>
    
    <div class="toolbar">
        <input type="text" placeholder="Search by intent, decision ID, or actor..." id="searchInput" />
        <button onclick="refresh()">🔄 Refresh</button>
    </div>
    
    <div class="grid">
        <div class="section">
            <h2>📂 Active Sessions (${sessions.length || 0})</h2>
            ${sessionList}
        </div>
        
        <div class="section">
            <h2>📜 Recent Decisions</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Title</th>
                        <th>Tier</th>
                        <th>Actor</th>
                    </tr>
                </thead>
                <tbody>
                    ${decisionList}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        function viewSession(sessionId) {
            vscode.postMessage({ command: 'viewSession', sessionId });
        }
        
        function traceDecision(decisionId) {
            vscode.postMessage({ command: 'traceDecision', decisionId });
        }
        
        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        SessionExplorerPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
