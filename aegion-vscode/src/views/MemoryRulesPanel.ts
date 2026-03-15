// Aegion Memory & Rules Panel Webview
// Tabbed view for managing memory entries and governance rules

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class MemoryRulesPanel {
    public static currentPanel: MemoryRulesPanel | undefined;
    private static readonly viewType = 'aegionMemoryRules';
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.One;
        if (MemoryRulesPanel.currentPanel) {
            MemoryRulesPanel.currentPanel._panel.reveal(column);
            MemoryRulesPanel.currentPanel._loadData();
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            MemoryRulesPanel.viewType, 'Memory & Rules', column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        MemoryRulesPanel.currentPanel = new MemoryRulesPanel(panel, extensionUri);
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
            const [memories, rules] = await Promise.all([api.listMemory(), api.listRules()]);
            this._panel.webview.postMessage({ command: 'update', memories, rules });
        } catch {
            this._panel.webview.postMessage({ command: 'update', memories: [], rules: [] });
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        const api = getApiClient();
        switch (msg.command) {
            case 'addMemory': {
                const key = await vscode.window.showInputBox({ prompt: 'Memory key' });
                if (!key) { return; }
                const value = await vscode.window.showInputBox({ prompt: 'Value' });
                await api.storeMemory({ key, value: value || '' });
                await this._loadData();
                break;
            }
            case 'deleteMemory': {
                await api.deleteMemory(msg.id as string);
                await this._loadData();
                break;
            }
            case 'addRule': {
                const name = await vscode.window.showInputBox({ prompt: 'Rule name' });
                if (!name) { return; }
                const condition = await vscode.window.showInputBox({ prompt: 'Condition' });
                if (!condition) { return; }
                const action = await vscode.window.showInputBox({ prompt: 'Action (e.g., require_review, block, warn)' });
                if (!action) { return; }
                await api.createRule({ name, condition, action });
                await this._loadData();
                break;
            }
            case 'toggleRule': {
                const id = msg.id as string;
                const enabled = msg.enabled as boolean;
                await api.updateRule(id, { enabled: !enabled });
                await this._loadData();
                break;
            }
            case 'deleteRule': {
                await api.deleteRule(msg.id as string);
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
    <title>Memory & Rules</title>
    <style>
        :root {
            --accent: #8b5cf6; --accent-hover: #7c3aed;
            --success: #22c55e; --warning: #f59e0b; --danger: #ef4444; --muted: #64748b;
            --bg: var(--vscode-editor-background);
            --card: rgba(255,255,255,0.04); --card-hover: rgba(255,255,255,0.08);
            --border: rgba(255,255,255,0.08);
            --text: var(--vscode-editor-foreground); --text-muted: var(--vscode-disabledForeground);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: var(--vscode-font-family); background: var(--bg); color: var(--text); padding: 24px; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .header h1 { font-size: 1.5em; }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85em; font-weight: 500; transition: all 0.15s; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-ghost { background: transparent; color: var(--text-muted); border: 1px solid var(--border); }
        .btn-ghost:hover { background: var(--card-hover); }
        .btn-danger { background: transparent; color: var(--danger); border: 1px solid rgba(239,68,68,0.3); font-size: 0.8em; padding: 4px 10px; }
        .btn-sm { padding: 4px 10px; font-size: 0.8em; }
        .tabs { display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }
        .tab { padding: 10px 20px; cursor: pointer; border: none; background: none; color: var(--text-muted); font-size: 0.9em; border-bottom: 2px solid transparent; }
        .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .item { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px 18px; margin-bottom: 8px; transition: all 0.15s; }
        .item:hover { background: var(--card-hover); }
        .item-header { display: flex; align-items: center; justify-content: space-between; }
        .item-title { font-weight: 600; font-size: 0.92em; }
        .item-meta { font-size: 0.78em; color: var(--text-muted); margin-top: 4px; display: flex; gap: 10px; flex-wrap: wrap; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.72em; font-weight: 600; }
        .badge-scope { background: rgba(139,92,246,0.15); color: var(--accent); }
        .badge-tag { background: rgba(100,116,139,0.15); color: var(--muted); }
        .badge-priority-critical { background: rgba(239,68,68,0.15); color: var(--danger); }
        .badge-priority-high { background: rgba(245,158,11,0.15); color: var(--warning); }
        .badge-priority-medium { background: rgba(34,197,94,0.15); color: var(--success); }
        .badge-priority-low { background: rgba(100,116,139,0.15); color: var(--muted); }
        .toggle { cursor: pointer; padding: 4px 10px; border-radius: 4px; border: 1px solid var(--border); font-size: 0.8em; background: transparent; }
        .toggle.on { color: var(--success); border-color: rgba(34,197,94,0.3); }
        .toggle.off { color: var(--danger); border-color: rgba(239,68,68,0.3); }
        .actions { display: flex; gap: 6px; }
        .empty { text-align: center; padding: 40px; color: var(--text-muted); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 Memory & Rules</h1>
        <div style="display:flex;gap:8px">
            <button class="btn btn-ghost" onclick="refresh()">↻</button>
        </div>
    </div>

    <div class="tabs">
        <button class="tab active" onclick="switchTab('memory')">📝 Memory</button>
        <button class="tab" onclick="switchTab('rules')">⚖️ Rules</button>
    </div>

    <div class="tab-content active" id="tab-memory">
        <div style="margin-bottom:12px"><button class="btn btn-primary" onclick="addMemory()">+ Add Memory</button></div>
        <div id="memoryList"><div class="empty">No memory entries yet.</div></div>
    </div>

    <div class="tab-content" id="tab-rules">
        <div style="margin-bottom:12px"><button class="btn btn-primary" onclick="addRule()">+ Add Rule</button></div>
        <div id="rulesList"><div class="empty">No rules defined yet.</div></div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function addMemory() { vscode.postMessage({ command: 'addMemory' }); }
        function deleteMemory(id) { vscode.postMessage({ command: 'deleteMemory', id }); }
        function addRule() { vscode.postMessage({ command: 'addRule' }); }
        function toggleRule(id, enabled) { vscode.postMessage({ command: 'toggleRule', id, enabled }); }
        function deleteRule(id) { vscode.postMessage({ command: 'deleteRule', id }); }

        function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('.tab-content#tab-' + tab).classList.add('active');
            document.querySelectorAll('.tab').forEach(t => { if (t.textContent.toLowerCase().includes(tab)) t.classList.add('active'); });
        }

        function renderMemory(entries) {
            const el = document.getElementById('memoryList');
            if (!entries.length) { el.innerHTML = '<div class="empty">No memory entries yet.</div>'; return; }
            el.innerHTML = entries.map(e =>
                '<div class="item"><div class="item-header"><span class="item-title">' + esc(e.key) + '</span>' +
                '<div class="actions"><button class="btn-danger" onclick="deleteMemory(\\'' + e.memory_id + '\\')">🗑</button></div></div>' +
                '<div class="item-meta"><span class="badge badge-scope">' + e.scope + '</span>' +
                e.tags.map(t => '<span class="badge badge-tag">' + esc(t) + '</span>').join('') +
                '<span>' + JSON.stringify(e.value).substring(0, 60) + '</span></div></div>'
            ).join('');
        }

        function renderRules(rules) {
            const el = document.getElementById('rulesList');
            if (!rules.length) { el.innerHTML = '<div class="empty">No rules defined yet.</div>'; return; }
            el.innerHTML = rules.map(r =>
                '<div class="item"><div class="item-header"><span class="item-title">' + esc(r.name) + '</span>' +
                '<div class="actions">' +
                '<button class="toggle ' + (r.enabled ? 'on' : 'off') + '" onclick="toggleRule(\\'' + r.rule_id + '\\',' + r.enabled + ')">' + (r.enabled ? '✓ ON' : '✗ OFF') + '</button>' +
                '<button class="btn-danger" onclick="deleteRule(\\'' + r.rule_id + '\\')">🗑</button></div></div>' +
                '<div class="item-meta"><span class="badge badge-priority-' + r.priority + '">' + r.priority + '</span>' +
                '<span>' + esc(r.condition) + ' → ' + esc(r.action) + '</span></div></div>'
            ).join('');
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.command === 'update') { renderMemory(msg.memories || []); renderRules(msg.rules || []); }
        });
    </script>
</body>
</html>`;
    }

    public dispose() {
        MemoryRulesPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) { const d = this._disposables.pop(); if (d) { d.dispose(); } }
    }
}
