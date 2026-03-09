// Aegion War Room Cockpit Panel
// Operational dashboard for system status and incident management.

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class WarRoomPanel {
    public static currentPanel: WarRoomPanel | undefined;
    private static readonly viewType = 'aegionWarRoom';
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.One;
        if (WarRoomPanel.currentPanel) {
            WarRoomPanel.currentPanel._panel.reveal(column);
            WarRoomPanel.currentPanel._loadData();
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            WarRoomPanel.viewType, 'War Room', column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        WarRoomPanel.currentPanel = new WarRoomPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._panel.webview.html = this._getHtml();
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            async (msg) => this._handleMessage(msg), null, this._disposables,
        );
        this._loadData();
    }

    private async _loadData(): Promise<void> {
        try {
            const api = getApiClient();
            const overview = await api.warroom.overview();
            // Fetch conflicts if workspaceId is available
            let conflicts: unknown[] = [];
            if (api.workspaceId) {
                conflicts = await api.getConflicts(api.workspaceId);
            }
            this._panel.webview.postMessage({ command: 'update', overview, conflicts });
        } catch (e) {
            console.error(e);
            this._panel.webview.postMessage({ command: 'error', message: 'Failed to load War Room data' });
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        const api = getApiClient();
        switch (msg.command) {
            case 'refresh':
                await this._loadData();
                break;
            case 'createIncident':
            {
                const title = await vscode.window.showInputBox({ prompt: 'Incident title' });
                if (!title) { return; }
                const severity = await vscode.window.showQuickPick(['low', 'medium', 'high', 'critical'], { placeHolder: 'Severity' });
                if (!severity) { return; }

                await api.warroom.createIncident({
                    title,
                    severity,
                    service: 'general',
                    description: 'Reported via War Room Panel',
                });
                vscode.window.showInformationMessage('Incident reported');
                await this._loadData();
                break;
            }
            case 'resolveIncident':
                await api.warroom.resolveIncident(msg.id as string);
                vscode.window.showInformationMessage('Incident resolved');
                await this._loadData();
                break;
            case 'resolveGovernanceConflict':
                // Delegate to the extension command which triggers AI Council
                await vscode.commands.executeCommand('aegion.resolveConflict', msg.conflict);
                await this._loadData();
                break;
        }
    }

    private _getHtml(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>War Room Cockpit</title>
    <style>
        :root {
            --bg: var(--vscode-editor-background);
            --text: var(--vscode-editor-foreground);
            --card-bg: var(--vscode-editor-inactiveSelectionBackground);
            --critical: #ef4444;
            --high: #f97316;
            --medium: #eab308;
            --low: #22c55e;
            --operational: #22c55e;
            --degraded: #f59e0b;
        }
        body { background: var(--bg); color: var(--text); padding: 20px; font-family: sans-serif; display: grid; gap: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
        .metric-card { background: var(--card-bg); padding: 16px; border-radius: 8px; text-align: center; }
        .metric-val { font-size: 2em; font-weight: bold; }
        .metric-label { font-size: 0.8em; opacity: 0.7; }
        
        .status-badge { padding: 4px 12px; border-radius: 12px; font-weight: bold; text-transform: uppercase; font-size: 0.8em; }
        .status-operational { background: rgba(34,197,94,0.2); color: var(--operational); }
        .status-degraded { background: rgba(245,158,11,0.2); color: var(--degraded); }
        .status-critical { background: rgba(239,68,68,0.2); color: var(--critical); }

        .incident-list { display: grid; gap: 10px; }
        .incident-card { background: var(--card-bg); padding: 12px; border-radius: 6px; border-left: 4px solid transparent; }
        .sev-critical { border-left-color: var(--critical); }
        .sev-high { border-left-color: var(--high); }
        .sev-medium { border-left-color: var(--medium); }
        .sev-low { border-left-color: var(--low); }
        
        .incident-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
        .incident-title { font-weight: 600; }
        .incident-meta { font-size: 0.8em; opacity: 0.6; }
        .btn { padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; background: #3b82f6; color: white; }
        .btn-sm { padding: 2px 8px; font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡 War Room Cockpit</h1>
        <div>
            <span id="sys-status" class="status-badge">Loading...</span>
            <button class="btn" onclick="refresh()">↻</button>
            <button class="btn" style="background:#ef4444" onclick="createIncident()">+ Incident</button>
        </div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-val" id="active-incidents">-</div>
            <div class="metric-label">Active Incidents</div>
        </div>
        <div class="metric-card">
            <div class="metric-val" id="online-users">-</div>
            <div class="metric-label">Online Users</div>
        </div>
        <div class="metric-card">
            <div class="metric-val" id="checkpoints">-</div>
            <div class="metric-label">Checkpoints</div>
        </div>
        <div class="metric-card">
            <div class="metric-val" id="crit-incidents">-</div>
            <div class="metric-label">Critical</div>
        </div>
    </div>

    <h3>Governance Conflicts</h3>
    <div id="conflicts" class="incident-list">
        <div style="opacity:0.6;text-align:center">Loading data...</div>
    </div>

    <h3>Recent Activity</h3>
    <div id="incidents" class="incident-list">
        <div style="opacity:0.6;text-align:center">Loading data...</div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function createIncident() { vscode.postMessage({ command: 'createIncident' }); }
        function resolve(id) { vscode.postMessage({ command: 'resolveIncident', id }); }
        function resolveConflict(conflictId) {
            // Find conflict object from global data or just send ID? 
            // The handler expects 'conflict' object. Let's find it.
            const conflict = window.conflictsData.find(c => c.conflict_id === conflictId);
            vscode.postMessage({ command: 'resolveGovernanceConflict', conflict }); 
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.command === 'update') {
                const data = msg.overview;
                const conflicts = msg.conflicts || [];
                window.conflictsData = conflicts; // Store for lookup
                
                // Update Status Badge
                const badge = document.getElementById('sys-status');
                badge.className = 'status-badge status-' + data.system_status;
                badge.textContent = data.system_status;
                
                // Update Metrics
                document.getElementById('active-incidents').textContent = data.active_incidents;
                document.getElementById('online-users').textContent = data.online_users;
                document.getElementById('checkpoints').textContent = data.active_checkpoints;
                document.getElementById('crit-incidents').textContent = data.critical_incidents;
                
                // Update Conflicts
                const conflictList = document.getElementById('conflicts');
                if (conflicts.length === 0) {
                    conflictList.innerHTML = '<div style="opacity:0.6;text-align:center">No active conflicts. Compliance 100%.</div>';
                } else {
                    conflictList.innerHTML = conflicts.map(c => 
                        '<div class="incident-card sev-' + (c.severity === 4 ? 'critical' : c.severity === 3 ? 'high' : 'medium') + '">' +
                            '<div class="incident-header">' +
                                '<span class="incident-title">' + c.rule_id + '</span>' +
                                '<span class="status-badge" style="font-size:0.6em">' + c.severity + '</span>' +
                            '</div>' +
                            '<div class="incident-meta">' + c.message + '<br>' + c.file_path + '</div>' +
                            '<div style="margin-top:8px;text-align:right"><button class="btn btn-sm" onclick="resolveConflict(\\'' + c.conflict_id + '\\')">Resolve (Council)</button></div>' +
                        '</div>'
                    ).join('');
                }

                // Update Incidents
                const list = document.getElementById('incidents');
                if (data.recent_incidents.length === 0) {
                    list.innerHTML = '<div style="opacity:0.6;text-align:center">No recent incidents. System nominal.</div>';
                } else {
                    list.innerHTML = data.recent_incidents.map(i => 
                        '<div class="incident-card sev-' + i.severity + '">' +
                            '<div class="incident-header">' +
                                '<span class="incident-title">' + i.title + '</span>' +
                                '<span class="status-badge" style="font-size:0.6em">' + i.status + '</span>' +
                            '</div>' +
                            '<div class="incident-meta">' + i.service + ' • ' + new Date(i.created_at).toLocaleTimeString() + '</div>' +
                            (i.status !== 'resolved' ? 
                                '<div style="margin-top:8px;text-align:right"><button class="btn btn-sm" onclick="resolve(\\'' + i.incident_id + '\\')">Resolve</button></div>' 
                                : '') +
                        '</div>'
                    ).join('');
                }
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose() {
        WarRoomPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
