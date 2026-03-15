/**
 * Aegion Admin Dashboard Panel
 *
 * System administration panel with:
 * - Usage analytics (tokens, sessions, proposals)
 * - Policy compliance overview
 * - Governance tier distribution
 * - System health monitoring
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class AdminDashboardPanel {
    public static currentPanel: AdminDashboardPanel | undefined;
    public static readonly viewType = 'aegion.adminDashboard';
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor?.viewColumn || vscode.ViewColumn.One;

        if (AdminDashboardPanel.currentPanel) {
            AdminDashboardPanel.currentPanel._panel.reveal(column);
            AdminDashboardPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            AdminDashboardPanel.viewType,
            '⚙️ Admin Dashboard',
            column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        AdminDashboardPanel.currentPanel = new AdminDashboardPanel(panel, extensionUri);
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

    private async _loadData(): Promise<void> {
        try {
            const api = getApiClient();
            const [usage, policy, health] = await Promise.all([
                api.admin.getUsage().catch(() => null),
                api.getGovernancePolicy().catch(() => null),
                api.checkHealth().catch(() => null),
            ]);
            this._panel.webview.postMessage({ command: 'update', usage, policy, health });
        } catch {
            this._panel.webview.postMessage({ command: 'error', message: 'Failed to load admin data' });
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        switch (msg.command) {
            case 'refresh':
                await this._loadData();
                break;
            case 'updatePolicy':
                {
                    const api = getApiClient();
                    try {
                        // Note: backend only supports GET policy-dashboard, no update endpoint yet
                        const currentPolicy = await api.admin.getPolicyDashboard();
                        this._panel.webview.postMessage({ command: 'update', policy: currentPolicy });
                        vscode.window.showInformationMessage('Policy refreshed (update endpoint not yet implemented)');
                        await this._loadData();
                    } catch {
                        vscode.window.showErrorMessage('Failed to refresh policy');
                    }
                }
                break;
        }
    }

    private _getHtml(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard</title>
    <style>
        :root {
            --bg: var(--vscode-editor-background);
            --text: var(--vscode-editor-foreground);
            --card-bg: var(--vscode-editor-inactiveSelectionBackground);
            --border: var(--vscode-panel-border, #333);
            --accent: #8b5cf6;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bg); color: var(--text); padding: 16px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }

        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h2 { display: flex; align-items: center; gap: 8px; }

        .btn { padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-secondary { background: var(--card-bg); color: var(--text); border: 1px solid var(--border); }

        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
        .grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 20px; }

        .metric-card {
            background: var(--card-bg); padding: 16px; border-radius: 10px; text-align: center;
        }
        .metric-val { font-size: 1.8em; font-weight: 700; }
        .metric-label { font-size: 0.75em; opacity: 0.6; margin-top: 4px; }
        .metric-trend { font-size: 0.75em; margin-top: 4px; }
        .trend-up { color: var(--success); }
        .trend-down { color: var(--danger); }

        .section { background: var(--card-bg); border-radius: 10px; padding: 16px; }
        .section h3 { margin-bottom: 12px; font-size: 0.9em; text-transform: uppercase; opacity: 0.7; }

        .bar-chart { display: flex; flex-direction: column; gap: 8px; }
        .bar-row { display: flex; align-items: center; gap: 8px; }
        .bar-label { width: 80px; font-size: 0.8em; text-align: right; }
        .bar-track { flex: 1; height: 22px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }
        .bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 0.75em; color: white; font-weight: 600; min-width: 30px; }

        .health-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .health-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 12px; border-radius: 6px; background: rgba(255,255,255,0.03);
        }
        .health-dot { width: 8px; height: 8px; border-radius: 50%; }
        .dot-healthy { background: var(--success); }
        .dot-degraded { background: var(--warning); }
        .dot-unhealthy { background: var(--danger); }

        .policy-list { display: flex; flex-direction: column; gap: 6px; }
        .policy-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.85em; }
        .policy-val { font-weight: 600; }

        .loading { text-align: center; padding: 40px; opacity: 0.5; }
    </style>
</head>
<body>
    <div class="header">
        <h2>⚙️ Admin Dashboard</h2>
        <div style="display:flex;gap:6px">
            <span id="health-badge" style="padding:4px 10px;border-radius:12px;font-size:0.8em;font-weight:600">—</span>
            <button class="btn btn-secondary" onclick="refresh()">↻ Refresh</button>
        </div>
    </div>

    <div class="grid-4" id="metrics">
        <div class="metric-card"><div class="metric-val" id="m-tokens">—</div><div class="metric-label">Tokens (24h)</div></div>
        <div class="metric-card"><div class="metric-val" id="m-sessions">—</div><div class="metric-label">Active Sessions</div></div>
        <div class="metric-card"><div class="metric-val" id="m-proposals">—</div><div class="metric-label">Proposals Today</div></div>
        <div class="metric-card"><div class="metric-val" id="m-decisions">—</div><div class="metric-label">Decisions Today</div></div>
    </div>

    <div class="grid-2">
        <div class="section">
            <h3>📊 Tier Distribution</h3>
            <div class="bar-chart" id="tier-chart">
                <div class="loading">Loading...</div>
            </div>
        </div>
        <div class="section">
            <h3>💚 System Health</h3>
            <div class="health-grid" id="health-grid">
                <div class="loading">Loading...</div>
            </div>
        </div>
    </div>

    <div class="grid-2">
        <div class="section">
            <h3>📜 Governance Policy</h3>
            <div class="policy-list" id="policy-list">
                <div class="loading">Loading...</div>
            </div>
        </div>
        <div class="section">
            <h3>🕐 Recent Activity</h3>
            <div id="activity-feed">
                <div class="loading">Loading...</div>
            </div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        function refresh() { vscode.postMessage({ command: 'refresh' }); }

        const tierColors = { tier_1: '#22c55e', tier_2: '#3b82f6', tier_3: '#f59e0b', tier_4: '#ef4444' };

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.command === 'update') {
                const { usage, policy, health } = msg;

                // Metrics
                if (usage) {
                    document.getElementById('m-tokens').textContent = (usage.total_tokens_24h || 0).toLocaleString();
                    document.getElementById('m-sessions').textContent = usage.active_sessions || 0;
                    document.getElementById('m-proposals').textContent = usage.proposals_today || 0;
                    document.getElementById('m-decisions').textContent = usage.decisions_today || 0;
                }

                // Tier Distribution
                if (usage && usage.tier_distribution) {
                    const tiers = usage.tier_distribution;
                    const max = Math.max(...Object.values(tiers).map(Number), 1);
                    document.getElementById('tier-chart').innerHTML = Object.entries(tiers).map(([tier, count]) => {
                        const pct = Math.round((Number(count) / max) * 100);
                        const color = tierColors[tier] || '#6366f1';
                        return '<div class="bar-row">' +
                            '<span class="bar-label">' + tier.replace('_', ' ').toUpperCase() + '</span>' +
                            '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + color + '">' + count + '</div></div>' +
                        '</div>';
                    }).join('');
                }

                // Health
                if (health && health.components) {
                    const badge = document.getElementById('health-badge');
                    const status = health.status || 'unknown';
                    badge.textContent = status.toUpperCase();
                    badge.style.background = status === 'healthy' ? 'rgba(34,197,94,0.2)' :
                                             status === 'degraded' ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.2)';
                    badge.style.color = status === 'healthy' ? '#22c55e' :
                                        status === 'degraded' ? '#f59e0b' : '#ef4444';

                    document.getElementById('health-grid').innerHTML = Object.entries(health.components).map(([name, comp]) => {
                        const s = (comp && typeof comp === 'object') ? (comp.status || 'unknown') : 'unknown';
                        const dotClass = s === 'healthy' ? 'dot-healthy' : s === 'degraded' ? 'dot-degraded' : 'dot-unhealthy';
                        return '<div class="health-item"><span>' + name + '</span><span class="health-dot ' + dotClass + '"></span></div>';
                    }).join('');
                }

                // Policy
                if (policy) {
                    const items = Object.entries(policy).filter(([k]) => k !== 'id').slice(0, 8);
                    document.getElementById('policy-list').innerHTML = items.map(([key, val]) =>
                        '<div class="policy-item"><span>' + key.replace(/_/g, ' ') + '</span><span class="policy-val">' + val + '</span></div>'
                    ).join('');
                }

                // Activity feed placeholder
                document.getElementById('activity-feed').innerHTML =
                    '<div style="font-size:0.85em;opacity:0.6;text-align:center;padding:20px">Connect to backend for live activity feed</div>';
            }
            if (msg.command === 'error') {
                document.getElementById('metrics').innerHTML = '<div class="loading">⚠ ' + msg.message + '</div>';
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        AdminDashboardPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
