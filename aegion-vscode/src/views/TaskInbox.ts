// Aegion Task Inbox Webview
// Task management panel with run history

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class TaskInboxPanel {
    public static currentPanel: TaskInboxPanel | undefined;
    private static readonly viewType = 'aegionTaskInbox';
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.One;

        if (TaskInboxPanel.currentPanel) {
            TaskInboxPanel.currentPanel._panel.reveal(column);
            TaskInboxPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            TaskInboxPanel.viewType,
            'Task Inbox',
            column,
            { enableScripts: true, retainContextWhenHidden: true },
        );

        TaskInboxPanel.currentPanel = new TaskInboxPanel(panel, extensionUri);
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
            const tasks = await api.listTasks();
            this._panel.webview.postMessage({ command: 'updateTasks', tasks });
        } catch (error) {
            console.error('Failed to load tasks:', error);
            this._panel.webview.postMessage({ command: 'updateTasks', tasks: [] });
        }
    }

    private async _handleMessage(message: { command: string;[key: string]: unknown }): Promise<void> {
        const api = getApiClient();
        switch (message.command) {
            case 'createTask': {
                const title = await vscode.window.showInputBox({ prompt: 'Task title' });
                if (!title) { return; }
                const description = await vscode.window.showInputBox({ prompt: 'Description (optional)' });
                const priority = await vscode.window.showQuickPick(
                    ['low', 'medium', 'high', 'critical'],
                    { placeHolder: 'Priority' },
                );

                const sessions = await api.getActiveSessions();
                const sessionId = sessions.length > 0 ? sessions[0].session_id : 'default';

                await api.createTask({
                    session_id: sessionId,
                    title,
                    description: description || undefined,
                    priority: priority || 'medium',
                });
                await this._loadData();
                break;
            }
            case 'runTask': {
                const taskId = message.taskId as string;
                const agent = await vscode.window.showQuickPick(
                    ['noesis', 'archon', 'sentinel'],
                    { placeHolder: 'Select agent to run this task' },
                );
                if (!agent) { return; }
                await api.runTask(taskId, { agent_id: agent });
                await this._loadData();
                break;
            }
            case 'viewRuns': {
                const taskId = message.taskId as string;
                const runs = await api.getTaskRuns(taskId);
                this._panel.webview.postMessage({ command: 'showRuns', taskId, runs });
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
    <title>Task Inbox</title>
    <style>
        :root {
            --accent: #7c3aed;
            --accent-hover: #6d28d9;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #3b82f6;
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
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
        }
        .header h1 {
            font-size: 1.5em;
            display: flex; align-items: center; gap: 10px;
        }
        .header-actions { display: flex; gap: 8px; }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
            font-weight: 500;
            transition: all 0.15s;
        }
        .btn-primary { background: var(--accent); color: white; }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-ghost {
            background: transparent;
            color: var(--text-muted);
            border: 1px solid var(--border);
        }
        .btn-ghost:hover { background: var(--card-hover); color: var(--text); }
        .btn-sm { padding: 4px 10px; font-size: 0.8em; }

        .stats-bar {
            display: flex; gap: 16px; margin-bottom: 20px;
        }
        .stat {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 18px;
            flex: 1;
            text-align: center;
        }
        .stat .value { font-size: 1.6em; font-weight: bold; }
        .stat .label { font-size: 0.75em; color: var(--text-muted); margin-top: 2px; }

        .task-list { display: flex; flex-direction: column; gap: 8px; }
        .task-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 14px;
            transition: all 0.15s;
            cursor: default;
        }
        .task-card:hover { background: var(--card-hover); border-color: rgba(255,255,255,0.15); }
        .task-card .priority-bar {
            width: 4px; height: 40px; border-radius: 2px;
        }
        .priority-critical { background: var(--danger); }
        .priority-high { background: var(--warning); }
        .priority-medium { background: var(--info); }
        .priority-low { background: var(--text-muted); }
        .task-info { flex: 1; }
        .task-title { font-weight: 600; font-size: 0.95em; }
        .task-meta {
            font-size: 0.78em;
            color: var(--text-muted);
            margin-top: 4px;
            display: flex; gap: 12px; align-items: center;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.72em;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-pending { background: rgba(59,130,246,0.15); color: var(--info); }
        .badge-running { background: rgba(245,158,11,0.15); color: var(--warning); }
        .badge-completed { background: rgba(34,197,94,0.15); color: var(--success); }
        .badge-failed { background: rgba(239,68,68,0.15); color: var(--danger); }
        .badge-cancelled { background: rgba(128,128,128,0.15); color: var(--text-muted); }

        .task-actions { display: flex; gap: 6px; }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }
        .empty-state .icon { font-size: 3em; margin-bottom: 12px; }

        .run-panel {
            margin-top: 8px;
            background: rgba(0,0,0,0.15);
            border-radius: 8px;
            padding: 12px 16px;
        }
        .run-panel h4 { margin-bottom: 8px; font-size: 0.85em; }
        .run-item {
            display: flex; align-items: center; gap: 10px;
            padding: 6px 0;
            border-bottom: 1px solid var(--border);
            font-size: 0.82em;
        }
        .run-item:last-child { border-bottom: none; }
        .run-agent { font-weight: 600; min-width: 70px; }
        .run-result { flex: 1; color: var(--text-muted); }
        .run-duration { font-size: 0.75em; color: var(--text-muted); }
    </style>
</head>
<body>
    <div class="header">
        <h1>📥 Task Inbox</h1>
        <div class="header-actions">
            <button class="btn btn-ghost" onclick="refresh()">↻ Refresh</button>
            <button class="btn btn-primary" onclick="createTask()">+ New Task</button>
        </div>
    </div>

    <div class="stats-bar" id="stats">
        <div class="stat"><div class="value" id="stat-total">0</div><div class="label">Total</div></div>
        <div class="stat"><div class="value" id="stat-pending">0</div><div class="label">Pending</div></div>
        <div class="stat"><div class="value" id="stat-running">0</div><div class="label">Running</div></div>
        <div class="stat"><div class="value" id="stat-completed">0</div><div class="label">Completed</div></div>
    </div>

    <div class="task-list" id="taskList">
        <div class="empty-state">
            <div class="icon">📋</div>
            <p>No tasks yet. Create one to get started.</p>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentTasks = [];

        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function createTask() { vscode.postMessage({ command: 'createTask' }); }
        function runTask(taskId) { vscode.postMessage({ command: 'runTask', taskId }); }
        function viewRuns(taskId) { vscode.postMessage({ command: 'viewRuns', taskId }); }

        function renderTasks(tasks) {
            currentTasks = tasks;
            const list = document.getElementById('taskList');

            // Stats
            document.getElementById('stat-total').textContent = tasks.length;
            document.getElementById('stat-pending').textContent = tasks.filter(t => t.status === 'pending').length;
            document.getElementById('stat-running').textContent = tasks.filter(t => t.status === 'running').length;
            document.getElementById('stat-completed').textContent = tasks.filter(t => t.status === 'completed').length;

            if (tasks.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="icon">📋</div><p>No tasks yet. Create one to get started.</p></div>';
                return;
            }

            list.innerHTML = tasks.map(task => {
                const statusClass = 'badge-' + task.status;
                const priorityClass = 'priority-' + task.priority;
                const created = new Date(task.created_at).toLocaleString();
                const canRun = task.status !== 'completed' && task.status !== 'cancelled';
                return '<div class="task-card" id="task-' + task.task_id + '">' +
                    '<div class="priority-bar ' + priorityClass + '"></div>' +
                    '<div class="task-info">' +
                        '<div class="task-title">' + escapeHtml(task.title) + '</div>' +
                        '<div class="task-meta">' +
                            '<span class="badge ' + statusClass + '">' + task.status + '</span>' +
                            '<span>' + task.priority + ' priority</span>' +
                            (task.assignee ? '<span>→ ' + escapeHtml(task.assignee) + '</span>' : '') +
                            '<span>' + task.run_count + ' runs</span>' +
                            '<span>' + created + '</span>' +
                        '</div>' +
                    '</div>' +
                    '<div class="task-actions">' +
                        (canRun ? '<button class="btn btn-primary btn-sm" onclick="runTask(\\'' + task.task_id + '\\')">▶ Run</button>' : '') +
                        '<button class="btn btn-ghost btn-sm" onclick="viewRuns(\\'' + task.task_id + '\\')">📜 Runs</button>' +
                    '</div>' +
                    '<div id="runs-' + task.task_id + '"></div>' +
                '</div>';
            }).join('');
        }

        function renderRuns(taskId, runs) {
            const container = document.getElementById('runs-' + taskId);
            if (!container) return;
            if (runs.length === 0) {
                container.innerHTML = '<div class="run-panel"><p style="color:var(--text-muted);font-size:0.85em">No runs yet.</p></div>';
                return;
            }
            container.innerHTML = '<div class="run-panel"><h4>Run History</h4>' +
                runs.map(run => {
                    const duration = run.duration_ms ? (run.duration_ms / 1000).toFixed(1) + 's' : '—';
                    const statusClass = 'badge-' + run.status;
                    return '<div class="run-item">' +
                        '<span class="run-agent">' + escapeHtml(run.agent_id) + '</span>' +
                        '<span class="badge ' + statusClass + '">' + run.status + '</span>' +
                        '<span class="run-result">' + escapeHtml(run.result || '') + '</span>' +
                        '<span class="run-duration">' + duration + '</span>' +
                    '</div>';
                }).join('') +
            '</div>';
        }

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            switch (msg.command) {
                case 'updateTasks':
                    renderTasks(msg.tasks || []);
                    break;
                case 'showRuns':
                    renderRuns(msg.taskId, msg.runs || []);
                    break;
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose() {
        TaskInboxPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
