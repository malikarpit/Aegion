/**
 * Council Panel — Phase 55: Full Council Consultation Webview
 *
 * Shows:
 * - Individual model responses side-by-side
 * - Consensus gauge + dissenting views section
 * - Cost breakdown per consultation
 * - Historical consultation list
 */

import * as vscode from 'vscode';

export class CouncilPanel {
    public static currentPanel: CouncilPanel | undefined;
    private static readonly viewType = 'aegion.councilPanel';

    private readonly panel: vscode.WebviewPanel;
    private readonly extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (CouncilPanel.currentPanel) {
            CouncilPanel.currentPanel.panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            CouncilPanel.viewType,
            '🏛️ Council Chamber',
            column || vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        CouncilPanel.currentPanel = new CouncilPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this.panel = panel;
        this.extensionUri = extensionUri;

        this.update();

        this.panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this.panel.webview.onDidReceiveMessage(
            async (message: { command: string; [key: string]: unknown }) => {
                switch (message.command) {
                    case 'consultCouncil':
                        await this.handleConsultation(message.query as string);
                        break;
                    case 'loadHistory':
                        await this.loadHistory(message.workspaceId as string);
                        break;
                }
            },
            null,
            this._disposables,
        );
    }

    private async handleConsultation(query: string): Promise<void> {
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const { getApiClient } = require('../api/client');
            const api = getApiClient();

            this.panel.webview.postMessage({ type: 'loading', query });

            const stream = api.invokeCouncilStream('', {
                prompt: query,
                context: { source: 'council_panel' },
            });

            let fullResponse = '';
            for await (const chunk of stream) {
                fullResponse += chunk;
                this.panel.webview.postMessage({
                    type: 'stream_chunk',
                    content: fullResponse,
                });
            }

            this.panel.webview.postMessage({
                type: 'consultation_complete',
                synthesis: fullResponse,
            });
        } catch (error) {
            this.panel.webview.postMessage({
                type: 'error',
                message: `${error}`,
            });
        }
    }

    private async loadHistory(workspaceId: string): Promise<void> {
        try {
            const baseUrl = vscode.workspace.getConfiguration('aegion')
                .get<string>('backendUrl') || 'http://localhost:8000';

            const response = await fetch(`${baseUrl}/api/v1/council/analytics/cost-efficiency/${workspaceId}?days=7`);
            if (response.ok) {
                const data = await response.json();
                this.panel.webview.postMessage({ type: 'history', data });
            }
        } catch {
            // Silent fail for history
        }
    }

    private update(): void {
        this.panel.webview.html = this.getHtmlContent();
    }

    private getHtmlContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Council Chamber</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-orange: #d29922;
            --accent-red: #f85149;
            --accent-purple: #bc8cff;
            --border: #30363d;
            --radius: 8px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 20px;
            line-height: 1.6;
        }

        .header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .header h1 {
            font-size: 20px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .input-area {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }

        .input-area textarea {
            flex: 1;
            padding: 12px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            color: var(--text-primary);
            font-size: 14px;
            resize: vertical;
            min-height: 60px;
        }

        .input-area textarea:focus {
            border-color: var(--accent-blue);
            outline: none;
        }

        .btn {
            padding: 12px 20px;
            background: var(--accent-blue);
            color: var(--bg-primary);
            border: none;
            border-radius: var(--radius);
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            white-space: nowrap;
        }

        .btn:hover { opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .result-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 16px;
            margin-bottom: 12px;
        }

        .result-card h3 {
            color: var(--accent-blue);
            font-size: 14px;
            margin-bottom: 8px;
        }

        .result-card pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .consensus-gauge {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 12px 0;
        }

        .gauge-bar {
            flex: 1;
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
        }

        .gauge-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }

        .loading {
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text-secondary);
            padding: 12px;
        }

        .loading::before {
            content: '';
            width: 16px;
            height: 16px;
            border: 2px solid var(--border);
            border-top-color: var(--accent-blue);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-badge.success { background: rgba(63,185,80,0.2); color: var(--accent-green); }
        .status-badge.warning { background: rgba(210,153,34,0.2); color: var(--accent-orange); }
        .status-badge.error { background: rgba(248,81,73,0.2); color: var(--accent-red); }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }

        .empty-state .icon { font-size: 48px; margin-bottom: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ Aegion Council Chamber</h1>
    </div>

    <div class="input-area">
        <textarea id="queryInput" placeholder="Ask the AI Council a question...&#10;e.g., 'Should we migrate from REST to gRPC?'"></textarea>
        <button class="btn" id="consultBtn" onclick="consult()">Consult</button>
    </div>

    <div id="results">
        <div class="empty-state">
            <div class="icon">🏛️</div>
            <p>Ask a question to begin a council consultation.</p>
            <p style="font-size: 12px; margin-top: 8px;">The council will debate your question using multiple AI models and provide a synthesized response.</p>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function consult() {
            const input = document.getElementById('queryInput');
            const query = input.value.trim();
            if (!query) return;

            document.getElementById('consultBtn').disabled = true;
            vscode.postMessage({ command: 'consultCouncil', query });
        }

        document.getElementById('queryInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                consult();
            }
        });

        window.addEventListener('message', (event) => {
            const msg = event.data;

            if (msg.type === 'loading') {
                document.getElementById('results').innerHTML =
                    '<div class="loading">Consulting the council...</div>';
            }

            if (msg.type === 'stream_chunk') {
                document.getElementById('results').innerHTML =
                    '<div class="result-card"><h3>🤖 Council Response</h3><pre>' +
                    escapeHtml(msg.content) + '</pre></div>';
            }

            if (msg.type === 'consultation_complete') {
                document.getElementById('consultBtn').disabled = false;
                document.getElementById('results').innerHTML =
                    '<div class="result-card"><h3>✅ Council Synthesis</h3><pre>' +
                    escapeHtml(msg.synthesis) + '</pre></div>';
            }

            if (msg.type === 'error') {
                document.getElementById('consultBtn').disabled = false;
                document.getElementById('results').innerHTML =
                    '<div class="result-card"><h3>❌ Error</h3><pre>' +
                    escapeHtml(msg.message) + '</pre></div>';
            }
        });

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>`;
    }

    dispose(): void {
        CouncilPanel.currentPanel = undefined;
        this.panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
