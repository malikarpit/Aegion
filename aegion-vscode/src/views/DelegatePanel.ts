/* eslint-disable no-case-declarations */
import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

export class DelegatePanel {
    public static currentPanel: DelegatePanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.html = this._getWebviewContent();
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.command) {
                    case 'refresh':
                        await this._refresh();
                        return;
                    case 'deploy':
                        await this._deploy(message.artifactId, message.env);
                        return;
                    case 'triggerRun':
                        await this._triggerRun(message.command, message.image);
                        return;
                }
            },
            null,
            this._disposables,
        );

        // Initial load
        this._refresh();
    }

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (DelegatePanel.currentPanel) {
            DelegatePanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'aegionDelegate',
            'Cloud Delegate',
            column || vscode.ViewColumn.One,
            { enableScripts: true },
        );

        DelegatePanel.currentPanel = new DelegatePanel(panel, extensionUri);
    }

    public dispose() {
        DelegatePanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private async _refresh() {
        const client = getApiClient();
        try {
            const resources = await client.delegation.listResources('dev');
            this._panel.webview.postMessage({ command: 'updateResources', resources });
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to fetch cloud resources: ${error}`);
        }
        await this._refreshRuns();
    }

    private async _refreshRuns() {
        const client = getApiClient();
        try {
            const runs = await client.delegation.runs.list();
            this._panel.webview.postMessage({ command: 'updateRuns', runs });
        } catch (error) {
            console.error('Failed to fetch runs:', error);
        }
    }

    private async _deploy(artifactId: string, env: string) {
        const client = getApiClient();
        try {
            this._panel.webview.postMessage({ command: 'deploymentStarted' });
            const result = await client.delegation.deploy({ artifact_id: artifactId, target_env: env });

            this._panel.webview.postMessage({ command: 'deploymentCheck', deploymentId: result.deployment_id });
            this._pollDeployment(result.deployment_id);

            vscode.window.showInformationMessage(`Deployment started: ${result.deployment_id}`);
        } catch (error) {
            vscode.window.showErrorMessage(`Deployment failed: ${error}`);
        }
    }

    private async _triggerRun(command: string, image: string) {
        const client = getApiClient();
        try {
            const run = await client.delegation.runs.trigger({ command, image });
            vscode.window.showInformationMessage(`Run triggered: ${run.run_id}`);
            this._refreshRuns();
            this._pollRun(run.run_id);
        } catch (error) {
            vscode.window.showErrorMessage(`Run failed: ${error}`);
        }
    }

    private async _pollRun(runId: string) {
        const client = getApiClient();
        const poll = setInterval(async () => {
            try {
                const run = await client.delegation.runs.get(runId);
                // Update UI if needed, or just let refresh handle it
                if (['completed', 'failed', 'cancelled'].includes(run.status)) {
                    clearInterval(poll);
                    this._refreshRuns();
                    vscode.window.showInformationMessage(`Run ${runId} finished: ${run.status}`);
                }
            } catch (e) {
                clearInterval(poll);
            }
        }, 2000);
    }

    private async _pollDeployment(deploymentId: string) {
        const client = getApiClient();
        const poll = setInterval(async () => {
            try {
                const status = await client.delegation.status(deploymentId);
                this._panel.webview.postMessage({ command: 'deploymentUpdate', status });

                if (status.status === 'success' || status.status === 'failed') {
                    clearInterval(poll);
                    this._refresh(); // Refresh resource list
                }
            } catch (e) {
                clearInterval(poll);
            }
        }, 2000);
    }

    // eslint-disable-next-line @typescript-eslint/class-methods-use-this
    private _getWebviewContent() {
        // eslint-disable no-case-declarations -- inline webview script uses const in case blocks
        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cloud Delegate</title>
            <style>
                body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-editor-foreground); }
                .card { background: var(--vscode-editor-background); border: 1px solid var(--vscode-widget-border); padding: 15px; margin-bottom: 10px; border-radius: 4px; }
                .btn { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 8px 12px; cursor: pointer; }
                .btn:hover { background: var(--vscode-button-hoverBackground); }
                .status-success, .status-completed { color: #4ec9b0; }
                .status-failed, .status-cancelled { color: #f14c4c; }
                .status-pending, .status-running { color: #cca700; }
                .resource-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }
                
                /* Tabs */
                .tab { overflow: hidden; border-bottom: 1px solid var(--vscode-widget-border); margin-bottom: 20px; }
                .tab button { background-color: inherit; float: left; border: none; outline: none; cursor: pointer; padding: 10px 16px; transition: 0.3s; color: var(--vscode-foreground); }
                .tab button:hover { background-color: var(--vscode-button-hoverBackground); }
                .tab button.active { border-bottom: 2px solid var(--vscode-activityBar-activeBorder); font-weight: bold; }
                .tabcontent { display: none; animation: fadeEffect 1s; }
                @keyframes fadeEffect { from {opacity: 0;} to {opacity: 1;} }
            </style>
        </head>
        <body>
            <h1>Cloud Delegate</h1>
            
            <div class="tab">
                <button class="tablinks active" onclick="openTab(event, 'Deployments')">Deployments</button>
                <button class="tablinks" onclick="openTab(event, 'RemoteRuns')">Remote Runs</button>
            </div>

            <!-- Deployments Tab -->
            <div id="Deployments" class="tabcontent" style="display: block;">
                <div class="card">
                    <h3>Deploy Artifact</h3>
                    <input type="text" id="artifactId" placeholder="Artifact ID (e.g., build-123)" style="padding: 5px; width: 200px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border);">
                    <select id="targetEnv" style="padding: 5px; background: var(--vscode-dropdown-background); color: var(--vscode-dropdown-foreground); border: 1px solid var(--vscode-dropdown-border);">
                        <option value="dev">Dev</option>
                        <option value="staging">Staging</option>
                        <option value="prod">Prod</option>
                    </select>
                    <button class="btn" onclick="deploy()">Deploy</button>
                </div>

                <div id="activeDeployment" class="card" style="display:none;">
                    <h3>Deployment Status</h3>
                    <div id="deployStatus">No active deployment</div>
                    <pre id="deployLogs" style="background: rgba(0,0,0,0.2); padding: 10px; max-height: 150px; overflow-y: auto;"></pre>
                </div>

                <h2>Managed Resources</h2>
                <button class="btn" onclick="refresh()">Refresh Resources</button>
                <div id="resourceContainer" class="resource-list" style="margin-top: 10px;">
                    <!-- Resources injected here -->
                </div>
            </div>

            <!-- Remote Runs Tab -->
            <div id="RemoteRuns" class="tabcontent">
                <div class="card">
                    <h3>Trigger Remote Run</h3>
                    <input type="text" id="runCommand" placeholder="Command (e.g., pytest tests/)" style="padding: 5px; width: 300px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border);">
                    <input type="text" id="runImage" placeholder="Image (default: aegion-runner)" style="padding: 5px; width: 150px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border);">
                    <button class="btn" onclick="triggerRun()">Trigger Run</button>
                </div>

                <h2>Run History</h2>
                <button class="btn" onclick="refresh()">Refresh Runs</button>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <thead>
                        <tr style="text-align: left; border-bottom: 1px solid var(--vscode-widget-border);">
                            <th style="padding: 8px;">ID</th>
                            <th style="padding: 8px;">Command</th>
                            <th style="padding: 8px;">Status</th>
                            <th style="padding: 8px;">Created</th>
                        </tr>
                    </thead>
                    <tbody id="runsTableBody">
                        <!-- Runs injected here -->
                    </tbody>
                </table>
            </div>

            <script>
                const vscode = acquireVsCodeApi();
                
                function openTab(evt, tabName) {
                    var i, tabcontent, tablinks;
                    tabcontent = document.getElementsByClassName("tabcontent");
                    for (i = 0; i < tabcontent.length; i++) {
                        tabcontent[i].style.display = "none";
                    }
                    tablinks = document.getElementsByClassName("tablinks");
                    for (i = 0; i < tablinks.length; i++) {
                        tablinks[i].className = tablinks[i].className.replace(" active", "");
                    }
                    document.getElementById(tabName).style.display = "block";
                    evt.currentTarget.className += " active";
                }

                function refresh() {
                    vscode.postMessage({ command: 'refresh' });
                }

                function deploy() {
                    const artifactId = document.getElementById('artifactId').value;
                    const env = document.getElementById('targetEnv').value;
                    if (!artifactId) return;
                    vscode.postMessage({ command: 'deploy', artifactId, env });
                }

                function triggerRun() {
                    const command = document.getElementById('runCommand').value;
                    const image = document.getElementById('runImage').value || 'aegion-runner:latest';
                    if (!command) return;
                    vscode.postMessage({ command: 'triggerRun', command, image });
                }

                window.addEventListener('message', event => {
                    const message = event.data;
                    switch (message.command) {
                        case 'updateResources':
                            {
                                const container = document.getElementById('resourceContainer');
                                container.innerHTML = message.resources.map(r => 
                                    \`<div class="card">
                                        <strong>\${r.name}</strong><br>
                                        <small>\${r.type} • \${r.region}</small><br>
                                        Status: <span class="status-\${r.status === 'active' ? 'success' : 'failed'}">\${r.status}</span>
                                    </div>\`
                                ).join('');
                                break;
                            }
                        case 'updateRuns':
                            {
                                const tbody = document.getElementById('runsTableBody');
                                tbody.innerHTML = message.runs.map(r => 
                                    \`<tr style="border-bottom: 1px solid var(--vscode-widget-border);">
                                        <td style="padding: 8px;"><small>\${r.run_id}</small></td>
                                        <td style="padding: 8px;"><code>\${r.config.command}</code></td>
                                        <td style="padding: 8px;"><span class="status-\${r.status}">\${r.status}</span></td>
                                        <td style="padding: 8px;"><small>\${new Date(r.created_at).toLocaleString()}</small></td>
                                    </tr>\`
                                ).join('');
                                break;
                            }
                        case 'deploymentStarted':
                            document.getElementById('activeDeployment').style.display = 'block';
                            document.getElementById('deployStatus').innerText = 'Initializing...';
                            document.getElementById('deployLogs').innerText = '';
                            break;
                        case 'deploymentUpdate':
                            {
                                const status = message.status;
                                document.getElementById('deployStatus').innerHTML = 
                                    \`ID: \${status.deployment_id} <br> Status: <span class="status-\${status.status}">\${status.status}</span>\`;
                                document.getElementById('deployLogs').innerText = status.logs.join('\\n');
                                break;
                            }
                    }
                });
            </script>
        </body>
        </html>`;
    }
}
