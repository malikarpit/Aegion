/**
 * Aegion Dashboard - System Overview Panel
 *
 * Displays governance health at a glance:
 * - Active sessions count
 * - Pending proposals
 * - Recent decisions
 * - Sentinel alerts
 */

import * as vscode from 'vscode';
import { getApiClient, ProposalResponse, HealthResponse, SessionResponse, SentinelAlert } from '../api/client';

export class DashboardPanel {
    public static currentPanel: DashboardPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static readonly viewType = 'aegion.dashboard';

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.html = this._getLoadingHtml();
        this._loadData();
    }

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (DashboardPanel.currentPanel) {
            DashboardPanel.currentPanel._panel.reveal(column);
            DashboardPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            DashboardPanel.viewType,
            '🛡️ Aegion Dashboard',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        DashboardPanel.currentPanel = new DashboardPanel(panel, extensionUri);
    }

    private async _loadData(): Promise<void> {
        try {
            const api = getApiClient();

            const [sessions, proposals, decisions, alerts, policy, health] = await Promise.all([
                api.getActiveSessions().catch(() => []),
                api.listPendingProposals().catch(() => []),
                api.listDecisions().catch(() => []),
                api.getSentinelAlerts().catch(() => []),
                api.getGovernancePolicy().catch(() => ({ version: 'unknown' })),
                api.checkHealth().catch(() => ({ status: 'unknown', components: {}, version: 'unknown', timestamp: new Date().toISOString() })),
            ]);

            // Map data to match view expectations
            const sessionData = { count: sessions.length, sessions };
            const alertData = { count: alerts.length, alerts: alerts };

            this._panel.webview.html = this._getHtml(sessionData, proposals, decisions, alertData, policy, health);
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
            padding: 20px;
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
<body>
    <div class="loader"></div>
</body>
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
    <h2>⚠️ Failed to load dashboard</h2>
    <p>${error}</p>
</body>
</html>`;
    }

    private _getHtml(
        sessions: { count: number; sessions: SessionResponse[] },
        proposals: ProposalResponse[],
        decisions: ProposalResponse[],
        alerts: { count: number; alerts: SentinelAlert[] },
        policy: Record<string, unknown>,
        health: HealthResponse,
    ): string {
        const proposalItems = proposals.slice(0, 5).map(p =>
            `<div class="list-item">
                <span class="tier tier-${p.tier?.toLowerCase() || 't1'}">${p.tier || 'T1'}</span>
                <span class="title">${p.title || 'Untitled'}</span>
            </div>`,
        ).join('') || '<div class="empty">No pending proposals</div>';

        const decisionItems = decisions.slice(0, 8).map((item) => {
            // Cast to allow accessing runtime properties not in ProposalResponse
            const d = item as ProposalResponse & {
                decided_at?: string;
                claim?: string;
                visibility?: string;
                origin?: string;
                decision_id?: string;
            };
            const tierEmoji: Record<string, string> = { T0: '🟢', T1: '🟡', T2: '🟠', T3: '🔴' };
            const tier = d.tier || 'T1';
            const visibility = d.visibility || d.origin || '';
            const visIcon = visibility.includes('ai') ? '🤖' : visibility === 'governed' ? '🏛️' : '✋';
            const decidedAt = d.decided_at ? new Date(d.decided_at).toLocaleDateString() : '';
            return `<div class="list-item">
                <span class="tier tier-${tier.toLowerCase()}">${tierEmoji[tier] || ''} ${tier}</span>
                <span class="title">${d.title || d.claim || d.decision_id || 'Untitled'}</span>
                <span class="meta">${visIcon} ${decidedAt}</span>
            </div>`;
        }).join('') || '<div class="empty">No recent decisions</div>';

        const alertItems = (alerts.alerts || []).slice(0, 3).map((alert) =>
            `<div class="alert alert-${alert.severity}">
                <span class="icon">⚠️</span>
                <span>${alert.message}</span>
            </div>`,
        ).join('') || '';

        // Council Status Mapping
        const getStatusColor = (status: string) => {
            switch (status) {
                case 'healthy': return 'var(--success)';
                case 'degraded': return 'var(--warning)';
                case 'unhealthy': return '#ef5350';
                default: return 'var(--vscode-disabledForeground)';
            }
        };

        const components = health.components || {};
        const councilItems = [
            { name: 'Noesis AI', role: 'Child', type: 'child', status: components['orchestrator']?.status || 'unknown' },
            { name: 'Archon AI', role: 'Parent', type: 'parent', status: components['governance']?.status || 'unknown' },
            { name: 'Sentinel', role: 'Sentinel', type: 'sentinel', status: components['sentinel']?.status || 'unknown' },
        ].map(agent =>
            `<div class="council-item">
                <span class="agent-badge ${agent.type}">${agent.role}</span>
                <span class="agent-name">${agent.name}</span>
                <span class="status-dot" style="background:${getStatusColor(agent.status)}" title="${agent.status}"></span>
            </div>`,
        ).join('');

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
        h1 {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            font-size: 1.5em;
        }
        .badge {
            background: var(--accent);
            color: #000;
            padding: 4px 12px;
            border-radius: 16px;
            font-size: 0.7em;
            font-weight: bold;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
        }
        .card h3 {
            margin: 0 0 12px 0;
            font-size: 0.9em;
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric {
            font-size: 2.5em;
            font-weight: bold;
            color: var(--accent);
        }
        .list-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 0;
            border-bottom: 1px solid var(--card-border);
        }
        .list-item:last-child { border-bottom: none; }
        .tier {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }
        .tier-t1 { background: var(--success); color: #000; }
        .tier-t2 { background: var(--warning); color: #000; }
        .tier-t3 { background: #e57373; color: #000; }
        .status-approved { color: var(--success); }
        .title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .empty { opacity: 0.5; font-style: italic; padding: 8px 0; }
        .alert {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: rgba(255,183,77,0.1);
            border-left: 3px solid var(--warning);
        }
        .footer {
            margin-top: 24px;
            opacity: 0.5;
            font-size: 0.85em;
        }
        .council-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 0;
            border-bottom: 1px solid var(--card-border);
        }
        .council-item:last-child { border-bottom: none; }
        .agent-badge {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7em;
            font-weight: bold;
            text-transform: uppercase;
            min-width: 60px;
            text-align: center;
        }
        .agent-badge.child { background: #90caf9; color: #000; }
        .agent-badge.parent { background: #ce93d8; color: #000; }
        .agent-badge.sentinel { background: #ffab91; color: #000; }
        .agent-name { flex: 1; }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
    </style>
</head>
<body>
    <h1>🛡️ Aegion Dashboard <span class="badge">v${policy.version || '0.0.1'}</span></h1>
    
    <div class="grid">
        <div class="card">
            <h3>🟢 Active Sessions</h3>
            <div class="metric">${sessions.count || 0}</div>
        </div>
        
        <div class="card">
            <h3>⏳ Pending Proposals</h3>
            ${proposalItems}
        </div>
        
        <div class="card">
            <h3>✅ Recent Decisions</h3>
            ${decisionItems}
        </div>
        
        <div class="card">
            <h3>⚠️ Sentinel Alerts</h3>
            ${alerts.count > 0 ? alertItems : '<div class="empty">All clear</div>'}
        </div>
        
        <div class="card">
            <h3>🤖 AI Councils</h3>
            ${councilItems}
        </div>
    </div>
    
    <div class="footer">
        Policy: ${policy.id || 'genesis'} | Last updated: ${new Date().toLocaleTimeString()}
    </div>
</body>
</html>`;
    }

    public dispose(): void {
        DashboardPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
