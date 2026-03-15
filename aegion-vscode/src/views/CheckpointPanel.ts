// Aegion Checkpoint Panel Webview
// Session checkpoint timeline with rollback support

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class CheckpointPanel {
    public static currentPanel: CheckpointPanel | undefined;
    private static readonly viewType = 'aegionCheckpoints';
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.One;

        if (CheckpointPanel.currentPanel) {
            CheckpointPanel.currentPanel._panel.reveal(column);
            CheckpointPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            CheckpointPanel.viewType,
            'Checkpoints',
            column,
            { enableScripts: true, retainContextWhenHidden: true },
        );

        CheckpointPanel.currentPanel = new CheckpointPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        this._panel.webview.html = this._getHtml();
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.onDidReceiveMessage(
            async (message) => this._handleMessage(message),
            null,
            this._disposables,
        );

        this._loadData();
    }

    private async _loadData(): Promise<void> {
        try {
            const api = getApiClient();
            const checkpoints = await api.listCheckpoints();
            this._panel.webview.postMessage({ command: 'updateCheckpoints', checkpoints });
        } catch (error) {
            console.error('Failed to load checkpoints:', error);
            this._panel.webview.postMessage({ command: 'updateCheckpoints', checkpoints: [] });
        }
    }

    private async _handleMessage(message: { command: string;[key: string]: unknown }): Promise<void> {
        const api = getApiClient();
        switch (message.command) {
            case 'createCheckpoint': {
                const label = await vscode.window.showInputBox({ prompt: 'Checkpoint label' });
                if (!label) { return; }

                const sessions = await api.getActiveSessions();
                const sessionId = sessions.length > 0 ? sessions[0].session_id : 'default';

                await api.createCheckpoint({ session_id: sessionId, label });
                await this._loadData();
                break;
            }
            case 'rollback': {
                const cpId = message.checkpointId as string;
                const confirm = await vscode.window.showWarningMessage(
                    'Are you sure you want to rollback to this checkpoint? This action cannot be undone.',
                    { modal: true },
                    'Rollback',
                );
                if (confirm !== 'Rollback') { return; }

                const result = await api.rollbackToCheckpoint(cpId);
                vscode.window.showInformationMessage(result.message);
                await this._loadData();
                break;
            }
            case 'deleteCheckpoint': {
                const cpId = message.checkpointId as string;
                const confirm = await vscode.window.showWarningMessage(
                    'Delete this checkpoint?',
                    { modal: true },
                    'Delete',
                );
                if (confirm !== 'Delete') { return; }

                await api.deleteCheckpoint(cpId);
                await this._loadData();
                break;
            }
            case 'refresh':
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
    <title>Checkpoints</title>
    <style>
        :root {
            --accent: #0ea5e9;
            --accent-hover: #0284c7;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
            --muted: #64748b;
            --bg: var(--vscode-editor-background);
            --card: rgba(255,255,255,0.04);
            --card-hover: rgba(255,255,255,0.08);
            --border: rgba(255,255,255,0.08);
            --text: var(--vscode-editor-foreground);
            --text-muted: var(--vscode-disabledForeground);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--vscode-font-family);
            background: var(--bg);
            color: var(--text);
            padding: 24px;
        }
        .header {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 24px;
        }
        .header h1 { font-size: 1.5em; display: flex; align-items: center; gap: 10px; }
        .header-actions { display: flex; gap: 8px; }
        .btn {
            padding: 8px 16px; border: none; border-radius: 6px;
            cursor: pointer; font-size: 0.85em; font-weight: 500; transition: all 0.15s;
        }
        .btn-primary { background: var(--accent); color: white; }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-ghost { background: transparent; color: var(--text-muted); border: 1px solid var(--border); }
        .btn-ghost:hover { background: var(--card-hover); color: var(--text); }
        .btn-danger { background: transparent; color: var(--danger); border: 1px solid rgba(239,68,68,0.3); }
        .btn-danger:hover { background: rgba(239,68,68,0.1); }
        .btn-sm { padding: 4px 10px; font-size: 0.8em; }

        .timeline { position: relative; padding-left: 30px; }
        .timeline::before {
            content: ''; position: absolute; left: 10px; top: 0; bottom: 0;
            width: 2px; background: var(--border);
        }
        .cp-card {
            position: relative;
            background: var(--card); border: 1px solid var(--border);
            border-radius: 10px; padding: 16px 20px; margin-bottom: 12px;
            transition: all 0.15s;
        }
        .cp-card:hover { background: var(--card-hover); border-color: rgba(255,255,255,0.15); }
        .cp-card::before {
            content: ''; position: absolute; left: -25px; top: 20px;
            width: 12px; height: 12px; border-radius: 50%;
            border: 2px solid var(--accent); background: var(--bg);
        }
        .cp-card.rolled-back::before { border-color: var(--warning); background: var(--warning); }
        .cp-card.expired::before { border-color: var(--muted); background: var(--muted); }

        .cp-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
        .cp-label { font-weight: 600; font-size: 0.95em; }
        .cp-meta { font-size: 0.78em; color: var(--text-muted); display: flex; gap: 12px; align-items: center; margin-top: 4px; }
        .badge {
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 0.72em; font-weight: 600; text-transform: uppercase;
        }
        .badge-active { background: rgba(34,197,94,0.15); color: var(--success); }
        .badge-rolled_back { background: rgba(245,158,11,0.15); color: var(--warning); }
        .badge-expired { background: rgba(100,116,139,0.15); color: var(--muted); }

        .cp-actions { display: flex; gap: 6px; }
        .empty-state { text-align: center; padding: 60px 20px; color: var(--text-muted); }
        .empty-state .icon { font-size: 3em; margin-bottom: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⏱️ Checkpoints</h1>
        <div class="header-actions">
            <button class="btn btn-ghost" onclick="refresh()">↻ Refresh</button>
            <button class="btn btn-primary" onclick="createCheckpoint()">+ Save Checkpoint</button>
        </div>
    </div>

    <div class="timeline" id="timeline">
        <div class="empty-state">
            <div class="icon">📍</div>
            <p>No checkpoints yet. Save one to create a restore point.</p>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function createCheckpoint() { vscode.postMessage({ command: 'createCheckpoint' }); }
        function rollback(id) { vscode.postMessage({ command: 'rollback', checkpointId: id }); }
        function deleteCheckpoint(id) { vscode.postMessage({ command: 'deleteCheckpoint', checkpointId: id }); }

        function renderCheckpoints(checkpoints) {
            const container = document.getElementById('timeline');
            if (checkpoints.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="icon">📍</div><p>No checkpoints yet. Save one to create a restore point.</p></div>';
                return;
            }

            container.innerHTML = checkpoints.map(cp => {
                const statusClass = cp.status === 'rolled_back' ? 'rolled-back' : cp.status;
                const badgeClass = 'badge-' + cp.status;
                const created = new Date(cp.created_at).toLocaleString();
                const canRollback = cp.status === 'active';

                return '<div class="cp-card ' + statusClass + '">' +
                    '<div class="cp-header">' +
                        '<span class="cp-label">' + escapeHtml(cp.label) + '</span>' +
                        '<div class="cp-actions">' +
                            (canRollback ? '<button class="btn btn-primary btn-sm" onclick="rollback(\\'' + cp.checkpoint_id + '\\')">↩ Rollback</button>' : '') +
                            '<button class="btn btn-danger btn-sm" onclick="deleteCheckpoint(\\'' + cp.checkpoint_id + '\\')">🗑</button>' +
                        '</div>' +
                    '</div>' +
                    '<div class="cp-meta">' +
                        '<span class="badge ' + badgeClass + '">' + cp.status.replace('_', ' ') + '</span>' +
                        '<span>' + cp.reason + '</span>' +
                        '<span>' + cp.state_key_count + ' state keys</span>' +
                        '<span>' + created + '</span>' +
                        (cp.rolled_back_at ? '<span>Rolled back: ' + new Date(cp.rolled_back_at).toLocaleString() + '</span>' : '') +
                    '</div>' +
                '</div>';
            }).join('');
        }

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.command === 'updateCheckpoints') {
                renderCheckpoints(msg.checkpoints || []);
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose() {
        CheckpointPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
