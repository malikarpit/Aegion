/**
 * Aegion Failure Mode Panel - Degraded State Banners
 *
 * Phase 4: Resilience UX
 * Shows system health status and degraded state notifications.
 */

import * as vscode from 'vscode';


export interface SystemHealth {
    status: 'healthy' | 'degraded' | 'critical';
    message: string;
    degradedServices: string[];
    lastChecked: string;
}

export class FailureModePanel {
    public static currentPanel: FailureModePanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];
    private _refreshInterval: NodeJS.Timeout | undefined;

    public static readonly viewType = 'aegion.failureMode';

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables,
        );
        this._panel.webview.html = this._getLoadingHtml();
        this._loadHealth();

        // Auto-refresh every 30 seconds
        this._refreshInterval = setInterval(() => this._loadHealth(), 30000);
    }

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (FailureModePanel.currentPanel) {
            FailureModePanel.currentPanel._panel.reveal(column);
            FailureModePanel.currentPanel._loadHealth();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            FailureModePanel.viewType,
            '🏥 System Health',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        FailureModePanel.currentPanel = new FailureModePanel(panel, extensionUri);
    }

    private async _handleMessage(message: { command: string }): Promise<void> {
        switch (message.command) {
            case 'refresh':
                this._loadHealth();
                break;
            case 'acknowledge':
                vscode.window.showInformationMessage('Degraded state acknowledged');
                break;
        }
    }

    private async _loadHealth(): Promise<void> {
        try {
            // Simulated health check - in production, call actual health endpoint
            const health: SystemHealth = {
                status: 'healthy',
                message: 'All systems operational',
                degradedServices: [],
                lastChecked: new Date().toISOString(),
            };

            this._panel.webview.html = this._getHtml(health);
        } catch (error) {
            const health: SystemHealth = {
                status: 'critical',
                message: `Health check failed: ${error}`,
                degradedServices: ['unknown'],
                lastChecked: new Date().toISOString(),
            };
            this._panel.webview.html = this._getHtml(health);
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
<body><div class="loader"></div></body>
</html>`;
    }

    private _getHtml(health: SystemHealth): string {
        const statusColor = {
            healthy: '#81c784',
            degraded: '#ffb74d',
            critical: '#e57373',
        }[health.status];

        const statusIcon = {
            healthy: '✅',
            degraded: '⚠️',
            critical: '🚨',
        }[health.status];

        const degradedList = health.degradedServices.length > 0
            ? health.degradedServices.map(s => `<li>${s}</li>`).join('')
            : '<li class="empty">No degraded services</li>';

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
        .status-banner {
            background: linear-gradient(135deg, ${statusColor}22 0%, ${statusColor}11 100%);
            border: 2px solid ${statusColor};
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            margin-bottom: 24px;
        }
        .status-icon {
            font-size: 4em;
            margin-bottom: 16px;
        }
        .status-text {
            font-size: 1.5em;
            font-weight: bold;
            color: ${statusColor};
            text-transform: uppercase;
        }
        .message {
            margin-top: 12px;
            opacity: 0.8;
        }
        .section {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }
        .section h2 {
            margin-top: 0;
            font-size: 1em;
            opacity: 0.7;
            text-transform: uppercase;
        }
        ul {
            padding-left: 20px;
            margin: 0;
        }
        li {
            padding: 4px 0;
        }
        .empty {
            opacity: 0.5;
            font-style: italic;
        }
        .toolbar {
            display: flex;
            gap: 12px;
            justify-content: center;
        }
        button {
            padding: 10px 20px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
        }
        button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .footer {
            text-align: center;
            opacity: 0.5;
            font-size: 0.8em;
            margin-top: 24px;
        }
    </style>
</head>
<body>
    <div class="status-banner">
        <div class="status-icon">${statusIcon}</div>
        <div class="status-text">${health.status}</div>
        <div class="message">${health.message}</div>
    </div>
    
    <div class="section">
        <h2>Degraded Services</h2>
        <ul>${degradedList}</ul>
    </div>
    
    <div class="toolbar">
        <button onclick="refresh()">🔄 Refresh</button>
        ${health.status !== 'healthy' ? '<button onclick="acknowledge()">✓ Acknowledge</button>' : ''}
    </div>
    
    <div class="footer">
        Last checked: ${new Date(health.lastChecked).toLocaleTimeString()}
    </div>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }
        
        function acknowledge() {
            vscode.postMessage({ command: 'acknowledge' });
        }
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        FailureModePanel.currentPanel = undefined;
        if (this._refreshInterval) {
            clearInterval(this._refreshInterval);
        }
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
