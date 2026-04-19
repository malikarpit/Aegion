import * as vscode from 'vscode';
import { AegionClient } from '../api/client';
import { SessionManager } from '../session/manager';

/**
 * Phase 86 Enhanced: VS Code Webview Provider for Model Settings & Cost Analytics.
 *
 * Features:
 *  - Preset selection with instant apply
 *  - Budget tracker with progress bar + danger state
 *  - Individual setting toggles (council, ghost text, sentinel, governance)
 *  - Cascade model order drag hint
 *  - Live cost display
 *  - Settings export/import
 */
export class AegionModelSettingsProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aegion.modelSettingsView';
    private _view?: vscode.WebviewView;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly client: AegionClient,
        private readonly sessionManager: SessionManager,
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
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
                case 'updateSetting':
                    await this.updateSetting(data.path, data.value);
                    break;
                case 'exportSettings':
                    await this.exportSettings();
                    break;
                case 'openDashboard':
                    vscode.env.openExternal(vscode.Uri.parse('http://localhost:3000/dashboard/settings'));
                    break;
            }
        });

        // Initial load
        this.loadData();
    }

    public async loadData() {
        if (!this._view) { return; }

        try {
            const workspaceId = this.sessionManager.getActiveWorkspaceId();
            if (!workspaceId) {
                this._view.webview.postMessage({ type: 'error', message: 'No workspace active' });
                return;
            }

            const [settings, budget, presets] = await Promise.all([
                this.client.get('/v1/model-settings/'),
                this.client.get('/v1/model-settings/budget'),
                this.client.get('/v1/model-settings/presets'),
            ]);

            this._view.webview.postMessage({
                type: 'update',
                payload: {
                    activePreset: settings.active_preset || 'balanced',
                    budget: budget,
                    presets: presets?.built_in || presets || [],
                    settings: settings,
                },
            });
        } catch (error: unknown) {
            this._view.webview.postMessage({
                type: 'error',
                message: (error as Error)?.message || 'Failed to load model settings',
            });
        }
    }

    private async applyPreset(presetKey: string) {
        try {
            await this.client.post('/v1/model-settings/preset', { preset: presetKey });
            vscode.window.showInformationMessage(`Aegion: Applied '${presetKey}' model profile`);
            await this.loadData();
        } catch (error: unknown) {
            vscode.window.showErrorMessage(`Failed to apply profile: ${(error as Error)?.message}`);
        }
    }

    private async updateSetting(path: string, value: unknown) {
        try {
            await this.client.patch('/v1/model-settings/setting', { path, value });
            vscode.window.showInformationMessage(`Aegion: Updated ${path}`);
            await this.loadData();
        } catch (error: unknown) {
            vscode.window.showErrorMessage(`Failed to update setting: ${(error as Error)?.message}`);
        }
    }

    private async exportSettings() {
        try {
            const settings = await this.client.get('/v1/model-settings/');
            const doc = await vscode.workspace.openTextDocument({
                content: JSON.stringify(settings, null, 2),
                language: 'json',
            });
            vscode.window.showTextDocument(doc);
        } catch (error: unknown) {
            vscode.window.showErrorMessage(`Export failed: ${(error as Error)?.message}`);
        }
    }

    private _getHtmlForWebview(_webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Settings</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--vscode-font-family);
            font-size: 12px;
            padding: 12px;
            color: var(--vscode-editor-foreground);
            background: var(--vscode-editor-background);
        }

        /* Section */
        .section { margin-bottom: 16px; }
        .section-title {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--vscode-sideBarTitle-foreground);
            margin-bottom: 8px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Budget Card */
        .budget-card {
            background: var(--vscode-editorWidget-background);
            border: 1px solid var(--vscode-widget-border);
            border-radius: 6px;
            padding: 12px;
        }
        .budget-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            margin-bottom: 4px;
        }
        .budget-label { opacity: 0.7; }
        .budget-value { font-weight: 600; font-variant-numeric: tabular-nums; }
        .progress-bar {
            height: 4px;
            background: var(--vscode-progressBar-background, rgba(255,255,255,0.1));
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            background: var(--vscode-activityBarBadge-background);
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .progress-fill.warning { background: #eab308; }
        .progress-fill.danger { background: var(--vscode-testing-iconFailed, #ef4444); }

        /* Preset Cards */
        .preset-grid { display: flex; flex-direction: column; gap: 6px; }
        .preset-card {
            background: var(--vscode-sideBar-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 6px;
            padding: 8px 10px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .preset-card:hover {
            background: var(--vscode-list-hoverBackground);
            border-color: var(--vscode-focusBorder);
        }
        .preset-card.active {
            border-color: var(--vscode-focusBorder);
            background: var(--vscode-list-activeSelectionBackground);
            color: var(--vscode-list-activeSelectionForeground);
        }
        .preset-info { flex: 1; }
        .preset-name { font-weight: 600; font-size: 12px; margin-bottom: 2px; }
        .preset-desc { font-size: 10px; opacity: 0.7; line-height: 1.3; }
        .preset-icon { font-size: 16px; width: 24px; text-align: center; }

        /* Toggle Switch */
        .setting-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            border-bottom: 1px solid var(--vscode-panel-border, rgba(255,255,255,0.05));
        }
        .setting-row:last-child { border-bottom: none; }
        .setting-label { font-size: 11px; flex: 1; }
        .toggle {
            width: 32px; height: 16px;
            background: var(--vscode-panel-border, rgba(255,255,255,0.2));
            border-radius: 10px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
            flex-shrink: 0;
        }
        .toggle.on { background: var(--vscode-activityBarBadge-background, #0078d4); }
        .toggle::after {
            content: '';
            position: absolute;
            width: 12px; height: 12px;
            border-radius: 50%;
            background: white;
            top: 2px; left: 2px;
            transition: transform 0.2s;
        }
        .toggle.on::after { transform: translateX(16px); }

        /* Actions */
        .actions { display: flex; gap: 6px; margin-top: 8px; }
        .btn {
            flex: 1;
            padding: 6px 0;
            border: 1px solid var(--vscode-button-border, var(--vscode-panel-border));
            background: var(--vscode-button-secondaryBackground, var(--vscode-sideBar-background));
            color: var(--vscode-button-secondaryForeground, var(--vscode-editor-foreground));
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            text-align: center;
            transition: all 0.15s;
        }
        .btn:hover {
            background: var(--vscode-button-secondaryHoverBackground, var(--vscode-list-hoverBackground));
        }
        .btn.primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-color: var(--vscode-button-background);
        }
        .btn.primary:hover { background: var(--vscode-button-hoverBackground); }

        /* Loader */
        .loader {
            text-align: center;
            padding: 30px 10px;
            opacity: 0.6;
            font-size: 11px;
        }
        .hidden { display: none !important; }

        /* Separator */
        .sep {
            height: 1px;
            background: var(--vscode-panel-border);
            margin: 12px 0;
        }
    </style>
</head>
<body>
    <div id="loader" class="loader">Loading settings...</div>

    <div id="content" class="hidden">
        <!-- Budget Section -->
        <div class="section">
            <div class="section-title">📊 Budget Tracker</div>
            <div class="budget-card">
                <div class="budget-row">
                    <span class="budget-label">Daily</span>
                    <span class="budget-value" id="dailySpend">$0.00 / ∞</span>
                </div>
                <div class="budget-row">
                    <span class="budget-label">Monthly</span>
                    <span class="budget-value" id="monthlySpend">$0.00 / ∞</span>
                </div>
                <div class="progress-bar">
                    <div id="budgetProgress" class="progress-fill" style="width: 0%"></div>
                </div>
            </div>
        </div>

        <!-- Presets Section -->
        <div class="section">
            <div class="section-title">⚡ Optimization Profile</div>
            <div id="presetList" class="preset-grid"></div>
        </div>

        <div class="sep"></div>

        <!-- Quick Toggles -->
        <div class="section">
            <div class="section-title">🔧 Quick Settings</div>
            <div id="toggles">
                <div class="setting-row">
                    <span class="setting-label">Ghost Text (AI Completions)</span>
                    <div class="toggle on" data-path="ghost_text.enabled" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Weighted Synthesis</span>
                    <div class="toggle on" data-path="council.weighted_synthesis" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Constitutional AI</span>
                    <div class="toggle on" data-path="council.constitution_enforcement" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Red Team Validation</span>
                    <div class="toggle" data-path="sentinel.red_team_enabled" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Auto-Approve T0</span>
                    <div class="toggle on" data-path="governance.auto_approve_t0" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Context Pruning</span>
                    <div class="toggle on" data-path="council.context_pruning" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Auto-Gather Evidence</span>
                    <div class="toggle on" data-path="memory.evidence_auto_gather" onclick="toggleSetting(this)"></div>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Budget Auto-Pause</span>
                    <div class="toggle on" data-path="budget.auto_pause" onclick="toggleSetting(this)"></div>
                </div>
            </div>
        </div>

        <div class="sep"></div>

        <!-- Actions -->
        <div class="section">
            <div class="actions">
                <button class="btn" onclick="doExport()">📥 Export</button>
                <button class="btn primary" onclick="openDashboard()">🌐 Full Settings</button>
            </div>
            <div class="actions" style="margin-top: 4px;">
                <button class="btn" onclick="doRefresh()">🔄 Refresh</button>
            </div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        const loader = document.getElementById('loader');
        const content = document.getElementById('content');
        const dailySpend = document.getElementById('dailySpend');
        const monthlySpend = document.getElementById('monthlySpend');
        const budgetProgress = document.getElementById('budgetProgress');
        const presetList = document.getElementById('presetList');

        let currentState = { activePreset: '', presets: [], settings: {} };

        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'update') {
                loader.classList.add('hidden');
                content.classList.remove('hidden');

                const p = message.payload;
                currentState = p;

                // Budget
                if (p.budget) {
                    const ds = p.budget.daily_spend || 0;
                    const dl = p.budget.daily_limit;
                    const ms = p.budget.monthly_spend || 0;
                    const ml = p.budget.monthly_limit;

                    dailySpend.innerText = dl
                        ? \`$\${ds.toFixed(2)} / $\${dl.toFixed(2)}\`
                        : \`$\${ds.toFixed(2)} (∞)\`;

                    monthlySpend.innerText = ml
                        ? \`$\${ms.toFixed(2)} / $\${ml.toFixed(2)}\`
                        : \`$\${ms.toFixed(2)} (∞)\`;

                    if (ml) {
                        const pct = Math.min((ms / ml) * 100, 100);
                        budgetProgress.style.width = \`\${pct}%\`;
                        budgetProgress.className = 'progress-fill' +
                            (pct > 90 ? ' danger' : pct > 70 ? ' warning' : '');
                    } else {
                        budgetProgress.style.width = '0%';
                    }
                }

                // Presets
                const presets = Array.isArray(p.presets) ? p.presets : [];
                if (presets.length > 0) {
                    presetList.innerHTML = '';
                    presets.forEach(preset => {
                        const div = document.createElement('div');
                        div.className = 'preset-card' + (preset.key === p.activePreset ? ' active' : '');
                        div.onclick = () => selectPreset(preset.key);
                        div.innerHTML = \`
                            <span class="preset-icon">\${preset.icon || '⚙️'}</span>
                            <div class="preset-info">
                                <div class="preset-name">\${preset.name}</div>
                                <div class="preset-desc">\${preset.description}</div>
                            </div>
                        \`;
                        presetList.appendChild(div);
                    });
                }

                // Sync toggles with server state
                if (p.settings) {
                    document.querySelectorAll('.toggle[data-path]').forEach(el => {
                        const path = el.dataset.path;
                        const parts = path.split('.');
                        let val = p.settings;
                        for (const part of parts) {
                            val = val?.[part];
                        }
                        if (typeof val === 'boolean') {
                            el.classList.toggle('on', val);
                        }
                    });
                }

            } else if (message.type === 'error') {
                loader.innerText = '⚠ ' + message.message;
            }
        });

        function selectPreset(key) {
            if (key === currentState.activePreset) return;
            document.querySelectorAll('.preset-card').forEach(el => el.classList.remove('active'));
            event?.currentTarget?.classList?.add('active');
            vscode.postMessage({ type: 'applyPreset', presetKey: key });
        }

        function toggleSetting(el) {
            const isOn = el.classList.toggle('on');
            const path = el.dataset.path;
            vscode.postMessage({ type: 'updateSetting', path, value: isOn });
        }

        function doRefresh() {
            loader.classList.remove('hidden');
            content.classList.add('hidden');
            loader.innerText = 'Refreshing...';
            vscode.postMessage({ type: 'refresh' });
        }

        function doExport() {
            vscode.postMessage({ type: 'exportSettings' });
        }

        function openDashboard() {
            vscode.postMessage({ type: 'openDashboard' });
        }
    </script>
</body>
</html>`;
    }
}
