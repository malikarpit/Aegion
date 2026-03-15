// Aegion Skill Catalog Panel Webview
// Browse, install, and validate skill blueprints

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class SkillCatalogPanel {
    public static currentPanel: SkillCatalogPanel | undefined;
    private static readonly viewType = 'aegionSkillCatalog';
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.One;
        if (SkillCatalogPanel.currentPanel) {
            SkillCatalogPanel.currentPanel._panel.reveal(column);
            SkillCatalogPanel.currentPanel._loadData();
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            SkillCatalogPanel.viewType, 'Skill Blueprints', column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        SkillCatalogPanel.currentPanel = new SkillCatalogPanel(panel, extensionUri);
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
            const skills = await api.listSkills();
            this._panel.webview.postMessage({ command: 'updateSkills', skills });
        } catch {
            this._panel.webview.postMessage({ command: 'updateSkills', skills: [] });
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        const api = getApiClient();
        switch (msg.command) {
            case 'createSkill': {
                const name = await vscode.window.showInputBox({ prompt: 'Skill name' });
                if (!name) { return; }
                const template = await vscode.window.showInputBox({ prompt: 'Prompt template (use {{param}})' });
                if (!template) { return; }
                await api.createSkill({ name, prompt_template: template });
                await this._loadData();
                break;
            }
            case 'install': {
                const result = await api.installSkill(msg.id as string);
                vscode.window.showInformationMessage(result.message);
                await this._loadData();
                break;
            }
            case 'validate': {
                const result = await api.validateSkill(msg.id as string);
                const icon = result.valid ? '✅' : '⚠️';
                vscode.window.showInformationMessage(`${icon} ${result.message}`);
                break;
            }
            case 'deleteSkill': {
                const confirm = await vscode.window.showWarningMessage('Delete this skill?', { modal: true }, 'Delete');
                if (confirm !== 'Delete') { return; }
                await api.deleteSkill(msg.id as string);
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
    <title>Skill Blueprints</title>
    <style>
        :root {
            --accent: #f59e0b; --accent-hover: #d97706;
            --success: #22c55e; --muted: #64748b; --danger: #ef4444;
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
        .btn-primary { background: var(--accent); color: #000; }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-ghost { background: transparent; color: var(--text-muted); border: 1px solid var(--border); }
        .btn-sm { padding: 4px 10px; font-size: 0.8em; }
        .btn-success { background: rgba(34,197,94,0.15); color: var(--success); border: 1px solid rgba(34,197,94,0.3); }
        .btn-danger { background: transparent; color: var(--danger); border: 1px solid rgba(239,68,68,0.3); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; transition: all 0.15s; }
        .card:hover { background: var(--card-hover); border-color: rgba(255,255,255,0.15); }
        .card-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px; }
        .card-title { font-weight: 600; font-size: 0.95em; }
        .card-version { font-size: 0.75em; color: var(--muted); }
        .card-desc { font-size: 0.82em; color: var(--text-muted); margin-bottom: 10px; }
        .card-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.72em; font-weight: 600; }
        .badge-cat { background: rgba(245,158,11,0.15); color: var(--accent); }
        .badge-installed { background: rgba(34,197,94,0.15); color: var(--success); }
        .badge-available { background: rgba(100,116,139,0.15); color: var(--muted); }
        .badge-tag { background: rgba(100,116,139,0.1); color: var(--muted); }
        .card-actions { display: flex; gap: 6px; margin-top: 10px; }
        .installs { font-size: 0.75em; color: var(--muted); }
        .empty { text-align: center; padding: 60px; color: var(--text-muted); }
        .empty .icon { font-size: 3em; margin-bottom: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧩 Skill Blueprints</h1>
        <div style="display:flex;gap:8px">
            <button class="btn btn-ghost" onclick="refresh()">↻</button>
            <button class="btn btn-primary" onclick="createSkill()">+ New Skill</button>
        </div>
    </div>
    <div class="grid" id="catalog">
        <div class="empty"><div class="icon">🧩</div><p>No skill blueprints yet. Create one to get started.</p></div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function createSkill() { vscode.postMessage({ command: 'createSkill' }); }
        function install(id) { vscode.postMessage({ command: 'install', id }); }
        function validate(id) { vscode.postMessage({ command: 'validate', id }); }
        function deleteSkill(id) { vscode.postMessage({ command: 'deleteSkill', id }); }
        function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

        function render(skills) {
            const el = document.getElementById('catalog');
            if (!skills.length) { el.innerHTML = '<div class="empty"><div class="icon">🧩</div><p>No skill blueprints yet.</p></div>'; return; }
            el.innerHTML = skills.map(s => {
                const statusBadge = s.status === 'installed' ? 'badge-installed' : 'badge-available';
                const canInstall = s.status === 'available';
                return '<div class="card">' +
                    '<div class="card-header"><div><span class="card-title">' + esc(s.name) + '</span> <span class="card-version">v' + esc(s.version) + '</span></div>' +
                    '<span class="installs">⬇ ' + s.install_count + '</span></div>' +
                    (s.description ? '<div class="card-desc">' + esc(s.description) + '</div>' : '') +
                    '<div class="card-meta">' +
                    '<span class="badge badge-cat">' + s.category.replace('_', ' ') + '</span>' +
                    '<span class="badge ' + statusBadge + '">' + s.status + '</span>' +
                    s.tags.map(t => '<span class="badge badge-tag">' + esc(t) + '</span>').join('') +
                    '</div>' +
                    '<div class="card-actions">' +
                    (canInstall ? '<button class="btn btn-success btn-sm" onclick="install(\\'' + s.skill_id + '\\')">⬇ Install</button>' : '') +
                    '<button class="btn btn-ghost btn-sm" onclick="validate(\\'' + s.skill_id + '\\')">🔏 Verify</button>' +
                    '<button class="btn btn-danger btn-sm" onclick="deleteSkill(\\'' + s.skill_id + '\\')">🗑</button>' +
                    '</div></div>';
            }).join('');
        }

        window.addEventListener('message', event => {
            if (event.data.command === 'updateSkills') render(event.data.skills || []);
        });
    </script>
</body>
</html>`;
    }

    public dispose() {
        SkillCatalogPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) { const d = this._disposables.pop(); if (d) { d.dispose(); } }
    }
}
