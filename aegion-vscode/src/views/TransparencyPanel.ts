import * as vscode from 'vscode';
import { AegionApiClient } from '../api/client';

/**
 * Transparency Panel - Shows detailed run information.
 *
 * Feature: Full run transparency panel.
 * Displays per-run: token usage, files read/written, commands executed, latency breakdown.
 */
export class TransparencyPanel {
    public static readonly viewType = 'aegion.transparencyPanel';
    private _panel: vscode.WebviewPanel | undefined;
    private _api: AegionApiClient;

    constructor(api: AegionApiClient) {
        this._api = api;
    }

    public async show(taskId: string, runId: string): Promise<void> {
        if (this._panel) {
            this._panel.reveal();
        } else {
            this._panel = vscode.window.createWebviewPanel(
                TransparencyPanel.viewType,
                'Run Transparency',
                vscode.ViewColumn.Two,
                { enableScripts: true },
            );

            this._panel.onDidDispose(() => {
                this._panel = undefined;
            });
        }

        await this._loadRunData(taskId, runId);
    }

    private async _loadRunData(taskId: string, runId: string): Promise<void> {
        if (!this._panel) { return; }

        try {
            const runs = await this._api.getTaskRuns(taskId);
            const run = runs.find(r => r.run_id === runId) || runs[0];

            if (run) {
                this._panel.webview.html = this._getHtml(run);
            } else {
                this._panel.webview.html = '<html><body><h2>No run data found</h2></body></html>';
            }
        } catch (error) {
            this._panel.webview.html = `<html><body><h2>Error loading run data</h2><p>${error}</p></body></html>`;
        }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private _getHtml(run: any): string {
        const tokenUsage = run.token_usage || { prompt: 0, completion: 0, total: 0 };
        const filesTouched = run.files_touched || [];
        const commandsRun = run.commands_run || [];
        const logs = run.logs || [];

        const filesHtml = filesTouched.length > 0
            ? filesTouched.map((f: string) => `<li class="file-item">${this._escapeHtml(f)}</li>`).join('')
            : '<li class="empty">No files touched</li>';

        const commandsHtml = commandsRun.length > 0
            ? commandsRun.map((c: string) => `<li class="cmd-item"><code>${this._escapeHtml(c)}</code></li>`).join('')
            : '<li class="empty">No commands run</li>';

        const logsHtml = logs.map((l: string) => `<div class="log-line">${this._escapeHtml(l)}</div>`).join('');

        return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-foreground); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .header h2 { margin: 0; }
        .status { padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 12px; }
        .status.completed { background: #2ea04333; color: #2ea043; }
        .status.running { background: #bf8f0033; color: #bf8f00; }
        .status.failed { background: #da363633; color: #da3636; }
        .section { margin-bottom: 20px; }
        .section h3 { border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 6px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
        .stat { background: var(--vscode-editor-background); border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 12px; text-align: center; }
        .stat .value { font-size: 24px; font-weight: bold; color: var(--vscode-textLink-foreground); }
        .stat .label { font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 4px; }
        .file-item, .cmd-item { padding: 4px 0; }
        code { background: var(--vscode-textCodeBlock-background); padding: 2px 6px; border-radius: 3px; }
        .log-line { font-family: monospace; font-size: 12px; padding: 2px 0; color: var(--vscode-descriptionForeground); }
        .empty { color: var(--vscode-descriptionForeground); font-style: italic; }
        .meta { font-size: 12px; color: var(--vscode-descriptionForeground); }
    </style>
</head>
<body>
    <div class="header">
        <h2>🔍 Run Transparency</h2>
        <span class="status ${run.status}">${run.status.toUpperCase()}</span>
    </div>

    <div class="meta">
        <strong>Run ID:</strong> ${run.run_id} &nbsp;|&nbsp;
        <strong>Agent:</strong> ${run.agent_id} &nbsp;|&nbsp;
        <strong>Duration:</strong> ${run.duration_ms || 0}ms
    </div>

    <div class="section">
        <h3>📊 Token Usage</h3>
        <div class="stats">
            <div class="stat">
                <div class="value">${tokenUsage.prompt?.toLocaleString() || 0}</div>
                <div class="label">Prompt Tokens</div>
            </div>
            <div class="stat">
                <div class="value">${tokenUsage.completion?.toLocaleString() || 0}</div>
                <div class="label">Completion Tokens</div>
            </div>
            <div class="stat">
                <div class="value">${tokenUsage.total?.toLocaleString() || 0}</div>
                <div class="label">Total Tokens</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h3>📁 Files Touched (${filesTouched.length})</h3>
        <ul>${filesHtml}</ul>
    </div>

    <div class="section">
        <h3>⚡ Commands Run (${commandsRun.length})</h3>
        <ul>${commandsHtml}</ul>
    </div>

    <div class="section">
        <h3>📋 Run Logs</h3>
        ${logsHtml || '<div class="empty">No logs</div>'}
    </div>
</body>
</html>`;
    }

    private _escapeHtml(text: string): string {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
}
