import * as vscode from 'vscode';
import { AegionClient } from '../client/AegionClient';
import { SessionManager } from '../auth/SessionManager';

/**
 * Phase 86: VS Code Webview Provider for Model Settings & Cost Analytics.
 * Injects a lightweight React/HTML interface directly into the IDE sidebar
 * to let developers toggle cost modes (e.g. going into "No Limits" mode for complex tasks)
 * without opening the web dashboard.
 */
export class AegionModelSettingsProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aegion.modelSettingsView';
    private _view?: vscode.WebviewView;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly client: AegionClient,
        private readonly sessionManager: SessionManager
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'refresh':
                    await this.loadData();
                    break;
                case 'applyPreset':
                    await this.applyPreset(data.presetKey);
                    break;
            }
        });

        // Initial load
        this.loadData();
    }

    public async loadData() {
        if (!this._view) return;

        try {
            const workspaceId = this.sessionManager.getActiveWorkspaceId();
            if (!workspaceId) {
                this._view.webview.postMessage({ type: 'error', message: 'No workspace active' });
                return;
            }

            // Parallel fetch to local aegion-backend instance (or prod if configured)
            const [settings, budget, presets] = await Promise.all([
                this.client.get(`/v1/model-settings/`),
                this.client.get(`/v1/model-settings/budget`),
                this.client.get(`/v1/model-settings/presets`)
            ]);

            this._view.webview.postMessage({
                type: 'update',
                payload: {
                    activePreset: settings.active_preset || 'balanced',
                    budget: budget,
                    presets: presets
                }
            });
        } catch (error: any) {
            this._view.webview.postMessage({ 
                type: 'error', 
                message: error?.message || 'Failed to load model settings' 
            });
        }
    }

    private async applyPreset(presetKey: string) {
        try {
            await this.client.post(`/v1/model-settings/preset`, { preset: presetKey });
            vscode.window.showInformationMessage(`Aegion: Applied '${presetKey}' model profile`);
            await this.loadData();
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to apply profile: ${error?.message}`);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        // A clean, compact UI optimized for the VS Code sidebar
        // We use VS Code's native CSS variables for seamless theme integration
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Settings</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 10px;
            color: var(--vscode-editor-foreground);
            background-color: var(--vscode-editor-background);
        }
        .header {
            margin-bottom: 20px;
        }
        .header h2 {
            font-size: 14px;
            text-transform: uppercase;
            color: var(--vscode-sideBarTitle-foreground);
            letter-spacing: 0.5px;
            margin: 0 0 5px 0;
        }
        .budget-card {
            background: var(--vscode-editorWidget-background);
            border: 1px solid var(--vscode-widget-border);
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 20px;
        }
        .budget-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 13px;
        }
        .progress-bar {
            height: 4px;
            background: var(--vscode-progressBar-background);
            border-radius: 2px;
            overflow: hidden;
            margin-top: 8px;
        }
        .progress-fill {
            height: 100%;
            background: var(--vscode-activityBarBadge-background);
            transition: width 0.3s ease;
        }
        .progress-fill.danger {
            background: var(--vscode-testing-iconFailed);
        }
        .preset-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .preset-card {
            background: var(--vscode-sideBar-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            padding: 8px 10px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .preset-card:hover {
            background: var(--vscode-list-hoverBackground);
        }
        .preset-card.active {
            border-color: var(--vscode-focusBorder);
            background: var(--vscode-list-activeSelectionBackground);
            color: var(--vscode-list-activeSelectionForeground);
        }
        .preset-header {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 4px;
        }
        .preset-desc {
            font-size: 11px;
            opacity: 0.8;
            margin: 0;
            line-height: 1.4;
        }
        .loader {
            text-align: center;
            padding: 20px;
            opacity: 0.7;
            font-size: 12px;
        }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div id="loader" class="loader">Loading settings...</div>
    
    <div id="content" class="hidden">
        <div class="header">
            <h2>Budget Tracker</h2>
            <div class="budget-card" id="budgetCard">
                <div class="budget-row">
                    <span>Daily Spend</span>
                    <strong id="dailySpend">$0.00 / ∞</strong>
                </div>
                <div class="progress-bar">
                    <div id="budgetProgress" class="progress-fill" style="width: 0%"></div>
                </div>
            </div>
        </div>

        <div class="header">
            <h2>Optimization Profile</h2>
            <div id="presetList" class="preset-list">
                <!-- Populated by JS -->
            </div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        
        const loader = document.getElementById('loader');
        const content = document.getElementById('content');
        const budgetCard = document.getElementById('budgetCard');
        const dailySpend = document.getElementById('dailySpend');
        const budgetProgress = document.getElementById('budgetProgress');
        const presetList = document.getElementById('presetList');

        let currentState = { activePreset: '', presets: [] };

        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'update') {
                loader.classList.add('hidden');
                content.classList.remove('hidden');
                
                const payload = message.payload;
                currentState = payload;
                
                // Update Budget UI
                if (payload.budget) {
                    const spend = payload.budget.daily_spend || 0;
                    const limit = payload.budget.daily_limit;
                    
                    if (limit) {
                        dailySpend.innerText = \`$\${spend.toFixed(2)} / $\${limit.toFixed(2)}\`;
                        const pct = Math.min((spend / limit) * 100, 100);
                        budgetProgress.style.width = \`\${pct}%\`;
                        if (pct > 90) budgetProgress.classList.add('danger');
                        else budgetProgress.classList.remove('danger');
                    } else {
                        dailySpend.innerText = \`$\${spend.toFixed(2)} (Unlimited)\`;
                        budgetProgress.style.width = '0%';
                    }
                }

                // Render Preset List
                if (payload.presets && payload.presets.length > 0) {
                    presetList.innerHTML = '';
                    payload.presets.forEach(p => {
                        const div = document.createElement('div');
                        div.className = 'preset-card ' + (p.key === payload.activePreset ? 'active' : '');
                        div.onclick = () => selectPreset(p.key);
                        
                        div.innerHTML = \`
                            <div class="preset-header">
                                <span>\${p.icon}</span>
                                <span>\${p.name}</span>
                            </div>
                            <p class="preset-desc">\${p.description}</p>
                        \`;
                        presetList.appendChild(div);
                    });
                }
            } else if (message.type === 'error') {
                loader.innerText = 'Error: ' + message.message;
            }
        });

        function selectPreset(key) {
            if (key === currentState.activePreset) return;
            
            // Optimistic UI update
            document.querySelectorAll('.preset-card').forEach(el => el.classList.remove('active'));
            event.currentTarget.classList.add('active');
            
            vscode.postMessage({ type: 'applyPreset', presetKey: key });
        }
    </script>
</body>
</html>`;
    }
}
