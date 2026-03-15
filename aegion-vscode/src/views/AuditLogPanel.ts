/**
 * Aegion Audit Log Viewer
 *
 * Displays the immutable governance audit trail with:
 * - Filterable event timeline
 * - Action/actor/session columns
 * - Task-based replay drill-down
 * - Export capability
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class AuditLogPanel {
    public static currentPanel: AuditLogPanel | undefined;
    public static readonly viewType = 'aegion.auditLog';
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor?.viewColumn || vscode.ViewColumn.One;

        if (AuditLogPanel.currentPanel) {
            AuditLogPanel.currentPanel._panel.reveal(column);
            AuditLogPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            AuditLogPanel.viewType,
            '📋 Audit Log',
            column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        AuditLogPanel.currentPanel = new AuditLogPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.webview.html = this._getHtml();
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            async (msg) => this._handleMessage(msg), null, this._disposables,
        );
        this._loadData();
    }

    private async _loadData(filters?: { action?: string; actor?: string }): Promise<void> {
        try {
            const api = getApiClient();
            const events = await api.audit.listEvents(filters || {});
            this._panel.webview.postMessage({ command: 'update', events });
        } catch {
            this._panel.webview.postMessage({ command: 'error', message: 'Failed to load audit events' });
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        switch (msg.command) {
            case 'refresh':
                await this._loadData();
                break;
            case 'filter':
                await this._loadData({ action: msg.action as string, actor: msg.actor as string });
                break;
            case 'replay':
                {
                    const api = getApiClient();
                    try {
                        const replay = await api.audit.replay(msg.taskId as string);
                        this._panel.webview.postMessage({ command: 'replayResult', replay });
                    } catch {
                        vscode.window.showErrorMessage('Failed to load task replay');
                    }
                }
                break;
            case 'export':
            {
                const content = JSON.stringify(msg.data, null, 2);
                const doc = await vscode.workspace.openTextDocument({ content, language: 'json' });
                await vscode.window.showTextDocument(doc);
                break;
            }
        }
    }

    private _getHtml(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audit Log</title>
    <style>
        :root {
            --bg: var(--vscode-editor-background);
            --text: var(--vscode-editor-foreground);
            --card-bg: var(--vscode-editor-inactiveSelectionBackground);
            --border: var(--vscode-panel-border, #333);
            --accent: #6366f1;
            --accent-dim: rgba(99,102,241,0.15);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bg); color: var(--text); padding: 16px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }

        .toolbar {
            display: flex; gap: 8px; align-items: center; margin-bottom: 16px; flex-wrap: wrap;
        }
        .toolbar input, .toolbar select {
            background: var(--card-bg); color: var(--text); border: 1px solid var(--border);
            padding: 6px 10px; border-radius: 6px; font-size: 13px;
        }
        .toolbar input { flex: 1; min-width: 150px; }
        .btn {
            padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer;
            font-size: 13px; font-weight: 500; transition: all 0.15s;
        }
        .btn-primary { background: var(--accent); color: white; }
        .btn-primary:hover { opacity: 0.85; }
        .btn-secondary { background: var(--card-bg); color: var(--text); border: 1px solid var(--border); }

        .stats-row {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 8px; margin-bottom: 16px;
        }
        .stat-card {
            background: var(--card-bg); padding: 12px; border-radius: 8px; text-align: center;
        }
        .stat-val { font-size: 1.5em; font-weight: 700; color: var(--accent); }
        .stat-label { font-size: 0.75em; opacity: 0.6; margin-top: 2px; }

        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--border); font-size: 0.8em; text-transform: uppercase; opacity: 0.6; }
        td { padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 0.85em; }
        tr:hover { background: var(--accent-dim); }

        .action-tag {
            display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: 600;
        }
        .action-create { background: rgba(34,197,94,0.15); color: #22c55e; }
        .action-update { background: rgba(59,130,246,0.15); color: #3b82f6; }
        .action-delete { background: rgba(239,68,68,0.15); color: #ef4444; }
        .action-approve { background: rgba(168,85,247,0.15); color: #a855f7; }
        .action-default { background: var(--accent-dim); color: var(--accent); }

        .replay-link { color: var(--accent); cursor: pointer; text-decoration: underline; }
        .replay-link:hover { opacity: 0.8; }

        .empty { text-align: center; padding: 40px; opacity: 0.5; }
        #replay-modal {
            display: none; position: fixed; top: 10%; left: 10%; right: 10%; bottom: 10%;
            background: var(--bg); border: 1px solid var(--border); border-radius: 12px;
            padding: 20px; z-index: 100; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        #modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 99; }
    </style>
</head>
<body>
    <h2 style="margin-bottom:12px">📋 Governance Audit Log</h2>

    <div class="stats-row">
        <div class="stat-card"><div class="stat-val" id="total-events">—</div><div class="stat-label">Total Events</div></div>
        <div class="stat-card"><div class="stat-val" id="unique-actors">—</div><div class="stat-label">Unique Actors</div></div>
        <div class="stat-card"><div class="stat-val" id="unique-actions">—</div><div class="stat-label">Action Types</div></div>
        <div class="stat-card"><div class="stat-val" id="unique-tasks">—</div><div class="stat-label">Tasks</div></div>
    </div>

    <div class="toolbar">
        <input type="text" id="filter-action" placeholder="Filter by action..." />
        <input type="text" id="filter-actor" placeholder="Filter by actor..." />
        <button class="btn btn-primary" onclick="applyFilter()">Filter</button>
        <button class="btn btn-secondary" onclick="refresh()">↻ Refresh</button>
        <button class="btn btn-secondary" onclick="exportLog()">⬇ Export</button>
    </div>

    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Target</th>
                <th>Task</th>
            </tr>
        </thead>
        <tbody id="events-body">
            <tr><td colspan="5" class="empty">Loading audit events...</td></tr>
        </tbody>
    </table>

    <div id="modal-overlay" onclick="closeReplay()"></div>
    <div id="replay-modal">
        <div style="display:flex;justify-content:space-between;margin-bottom:12px">
            <h3>🔄 Task Replay</h3>
            <button class="btn btn-secondary" onclick="closeReplay()">✕ Close</button>
        </div>
        <div id="replay-content"></div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentEvents = [];

        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function applyFilter() {
            const action = document.getElementById('filter-action').value;
            const actor = document.getElementById('filter-actor').value;
            vscode.postMessage({ command: 'filter', action, actor });
        }
        function exportLog() { vscode.postMessage({ command: 'export', data: currentEvents }); }
        function showReplay(taskId) { vscode.postMessage({ command: 'replay', taskId }); }
        function closeReplay() {
            document.getElementById('replay-modal').style.display = 'none';
            document.getElementById('modal-overlay').style.display = 'none';
        }

        function getActionClass(action) {
            if (action.includes('create')) return 'action-create';
            if (action.includes('update') || action.includes('modify')) return 'action-update';
            if (action.includes('delete') || action.includes('remove')) return 'action-delete';
            if (action.includes('approve') || action.includes('promote')) return 'action-approve';
            return 'action-default';
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.command === 'update') {
                currentEvents = msg.events || [];
                const body = document.getElementById('events-body');

                // Stats
                const actors = new Set(currentEvents.map(e => e.actor_id || e.user_id || 'system'));
                const actions = new Set(currentEvents.map(e => e.action));
                const tasks = new Set(currentEvents.filter(e => e.task_id).map(e => e.task_id));
                document.getElementById('total-events').textContent = currentEvents.length;
                document.getElementById('unique-actors').textContent = actors.size;
                document.getElementById('unique-actions').textContent = actions.size;
                document.getElementById('unique-tasks').textContent = tasks.size;

                if (currentEvents.length === 0) {
                    body.innerHTML = '<tr><td colspan="5" class="empty">No audit events found.</td></tr>';
                    return;
                }

                body.innerHTML = currentEvents.map(e => {
                    const time = e.timestamp ? new Date(e.timestamp).toLocaleString() : '—';
                    const actor = e.actor_id || e.user_id || 'system';
                    const taskLink = e.task_id
                        ? '<span class="replay-link" onclick="showReplay(\\'' + e.task_id + '\\')">' + e.task_id.substring(0,8) + '…</span>'
                        : '—';
                    return '<tr>' +
                        '<td>' + time + '</td>' +
                        '<td><span class="action-tag ' + getActionClass(e.action) + '">' + e.action + '</span></td>' +
                        '<td>' + actor + '</td>' +
                        '<td>' + (e.target || '—') + '</td>' +
                        '<td>' + taskLink + '</td>' +
                    '</tr>';
                }).join('');
            }
            if (msg.command === 'replayResult') {
                document.getElementById('replay-modal').style.display = 'block';
                document.getElementById('modal-overlay').style.display = 'block';
                const replay = msg.replay;
                document.getElementById('replay-content').innerHTML =
                    '<p><strong>Task:</strong> ' + replay.task_id + '</p>' +
                    '<p><strong>Events:</strong> ' + (replay.events || []).length + '</p>' +
                    '<div style="margin-top:12px">' +
                    (replay.events || []).map((e, i) =>
                        '<div style="padding:8px;border-left:3px solid var(--accent);margin:6px 0;background:var(--card-bg);border-radius:0 6px 6px 0">' +
                            '<strong>' + (i+1) + '. ' + e.action + '</strong> — ' + (e.target || '') +
                            '<div style="font-size:0.8em;opacity:0.6">' + (e.timestamp || '') + '</div>' +
                        '</div>'
                    ).join('') +
                    '</div>';
            }
            if (msg.command === 'error') {
                document.getElementById('events-body').innerHTML =
                    '<tr><td colspan="5" class="empty">⚠ ' + msg.message + '</td></tr>';
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        AuditLogPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
