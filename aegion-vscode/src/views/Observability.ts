/**
 * Aegion Observability Console - Risk Heatmap
 *
 * Phase 4: Resilience UX
 * Visualize system risk and anomaly scores.
 */

import * as vscode from 'vscode';


interface RiskMetric {
    module: string;
    score: number;
    trend: 'up' | 'down' | 'stable';
    alerts: number;
}

export class ObservabilityPanel {
    public static currentPanel: ObservabilityPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static readonly viewType = 'aegion.observability';

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables,
        );
        this._loadData();
    }

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (ObservabilityPanel.currentPanel) {
            ObservabilityPanel.currentPanel._panel.reveal(column);
            ObservabilityPanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            ObservabilityPanel.viewType,
            '📊 Risk Observatory',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        ObservabilityPanel.currentPanel = new ObservabilityPanel(panel, extensionUri);
    }

    private async _handleMessage(message: { command: string; module?: string }): Promise<void> {
        switch (message.command) {
            case 'refresh':
                this._loadData();
                break;
            case 'drilldown':
                vscode.window.showInformationMessage(`Drilling into: ${message.module}`);
                break;
        }
    }

    private async _loadData(): Promise<void> {
        try {
            const { getApiClient } = await import('../api/client.js');
            const api = getApiClient();

            // Fetch real risk data from sentinel
            const alerts = await api.getSentinelAlerts();

            // Attempt drift detection (result unused; used for side-effects only)
            try {
                await api.detectDrift({ workspace_id: 'default', current_period: [], baseline_period: [] });
            } catch {
                // Drift endpoint may not be available yet
            }

            // Build metrics from real alert data, grouped by source module
            const moduleAlerts: Record<string, number> = {};
            for (const alert of alerts) {
                const source = alert.source || alert.type || 'Unknown';
                moduleAlerts[source] = (moduleAlerts[source] || 0) + 1;
            }

            const metrics: RiskMetric[] = Object.entries(moduleAlerts).map(([mod, count]) => ({
                module: mod,
                score: Math.min(count * 20, 100),
                trend: 'up' as const,
                alerts: count,
            }));

            // If no alerts, show a healthy baseline
            if (metrics.length === 0) {
                metrics.push({ module: 'All Systems', score: 0, trend: 'stable', alerts: 0 });
            }

            this._panel.webview.html = this._getHtml(metrics);
        } catch {
            this._panel.webview.html = this._getHtml([
                { module: 'All Systems', score: 0, trend: 'stable', alerts: 0 },
            ]);
        }
    }

    private _getHtml(metrics: RiskMetric[]): string {
        const getColor = (score: number): string => {
            if (score < 20) { return '#81c784'; }  // Green
            if (score < 40) { return '#ffb74d'; }  // Yellow
            if (score < 60) { return '#ff8a65'; }  // Orange
            return '#e57373';                   // Red
        };

        const getTrendIcon = (trend: string): string => {
            if (trend === 'up') { return '📈'; }
            if (trend === 'down') { return '📉'; }
            return '➡️';
        };

        const heatmapCells = metrics.map(m => `
            <div class="heatmap-cell" onclick="drilldown('${m.module}')" style="background: ${getColor(m.score)}22; border-color: ${getColor(m.score)};">
                <div class="cell-header">
                    <span class="module-name">${m.module}</span>
                    ${m.alerts > 0 ? `<span class="alert-badge">${m.alerts}</span>` : ''}
                </div>
                <div class="cell-score" style="color: ${getColor(m.score)};">${m.score}</div>
                <div class="cell-trend">${getTrendIcon(m.trend)}</div>
            </div>
        `).join('');

        const avgScore = Math.round(metrics.reduce((a, m) => a + m.score, 0) / metrics.length);
        const totalAlerts = metrics.reduce((a, m) => a + m.alerts, 0);

        return `<!DOCTYPE html>
<html>
<head>
    <style>
        :root {
            --card-bg: rgba(255,255,255,0.03);
            --card-border: rgba(255,255,255,0.1);
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
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .summary-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }
        .summary-value {
            font-size: 2em;
            font-weight: bold;
        }
        .summary-label {
            font-size: 0.8em;
            opacity: 0.7;
            text-transform: uppercase;
            margin-top: 4px;
        }
        .heatmap {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
        }
        .heatmap-cell {
            border: 2px solid;
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .heatmap-cell:hover {
            transform: scale(1.02);
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .cell-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .module-name {
            font-size: 0.85em;
            font-weight: 500;
        }
        .alert-badge {
            background: #e57373;
            color: white;
            font-size: 0.7em;
            padding: 2px 6px;
            border-radius: 10px;
        }
        .cell-score {
            font-size: 2em;
            font-weight: bold;
        }
        .cell-trend {
            font-size: 0.9em;
            margin-top: 4px;
        }
        .toolbar {
            margin-top: 24px;
            text-align: center;
        }
        button {
            padding: 10px 20px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 16px;
            font-size: 0.8em;
            opacity: 0.7;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .legend-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
    </style>
</head>
<body>
    <h1>📊 Sentinel Risk Observatory</h1>
    
    <div class="summary">
        <div class="summary-card">
            <div class="summary-value" style="color: ${getColor(avgScore)};">${avgScore}</div>
            <div class="summary-label">Average Risk Score</div>
        </div>
        <div class="summary-card">
            <div class="summary-value">${metrics.length}</div>
            <div class="summary-label">Monitored Modules</div>
        </div>
        <div class="summary-card">
            <div class="summary-value" style="color: ${totalAlerts > 0 ? '#e57373' : '#81c784'};">${totalAlerts}</div>
            <div class="summary-label">Active Alerts</div>
        </div>
    </div>
    
    <div class="heatmap">
        ${heatmapCells}
    </div>
    
    <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background: #81c784;"></div> Low (0-20)</div>
        <div class="legend-item"><div class="legend-dot" style="background: #ffb74d;"></div> Medium (20-40)</div>
        <div class="legend-item"><div class="legend-dot" style="background: #ff8a65;"></div> High (40-60)</div>
        <div class="legend-item"><div class="legend-dot" style="background: #e57373;"></div> Critical (60+)</div>
    </div>
    
    <div class="toolbar">
        <button onclick="refresh()">🔄 Refresh Metrics</button>
    </div>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }
        
        function drilldown(module) {
            vscode.postMessage({ command: 'drilldown', module });
        }
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        ObservabilityPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
