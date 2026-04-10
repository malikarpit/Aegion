// Aegion Collaboration Panel
// Real-time presence and session ownership governance.

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';
import { CollaborationService } from '../services/CollaborationService';


export class CollaborationPanel {
    public static currentPanel: CollaborationPanel | undefined;
    private static readonly viewType = 'aegionCollaboration';
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _timer: NodeJS.Timeout | undefined;
    private _collaborationService: CollaborationService;

    public static show(extensionUri: vscode.Uri, collaborationService: CollaborationService) {
        const column = vscode.ViewColumn.One;
        if (CollaborationPanel.currentPanel) {
            CollaborationPanel.currentPanel._panel.reveal(column);
            CollaborationPanel.currentPanel._refresh();
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            CollaborationPanel.viewType, 'Collaboration', column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        CollaborationPanel.currentPanel = new CollaborationPanel(panel, extensionUri, collaborationService);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, collaborationService: CollaborationService) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._collaborationService = collaborationService;

        this._panel.webview.html = this._getHtml();
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            async (msg) => this._handleMessage(msg), null, this._disposables,
        );

        // Listen for ownership changes
        this._collaborationService.onDidChangeOwnership(ownership => {
            this._panel.webview.postMessage({ command: 'updateOwnership', ownership });
        });

        // Initial load
        this._refresh();

        // Start polling per minute (or on refresh click)
        this._timer = setInterval(() => this._refresh(), 30000);
    }

    private async _refresh(): Promise<void> {
        try {
            const api = getApiClient();
            // Send heartbeat first
            const editor = vscode.window.activeTextEditor;
            await api.presence.heartbeat({
                status: 'online',
                active_file: editor ? vscode.workspace.asRelativePath(editor.document.uri) : undefined,
                cursor_line: editor ? editor.selection.active.line : undefined,
            });

            const presence = await api.presence.list();

            // Get session ID from the collaboration service's active session context.
            // SessionManager broadcasts state changes via events, which the
            // CollaborationService picks up. We use its cached session ID if available.

            this._panel.webview.postMessage({ command: 'updatePresence', presence });

            if (this._collaborationService.currentOwnership) {
                this._panel.webview.postMessage({
                    command: 'updateOwnership',
                    ownership: this._collaborationService.currentOwnership,
                });
            }

        } catch {
            // Ignore errors
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        switch (msg.command) {
            case 'refresh':
                await this._refresh();
                break;
            case 'claimOwnership':
                if (typeof msg.sessionId === 'string') {
                    await this._collaborationService.claimOwnership(msg.sessionId, !!msg.force);
                    this._refresh();
                }
                break;
            case 'releaseOwnership':
                if (typeof msg.sessionId === 'string') {
                    await this._collaborationService.releaseOwnership(msg.sessionId);
                    this._refresh();
                }
                break;
            case 'openFile':
                {
                    const file = msg.file as string;
                    if (file) {
                        vscode.window.showInformationMessage(`User is working on: ${file}`);
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
    <title>Collaboration</title>
    <style>
        :root {
            --online: #22c55e;
            --away: #f59e0b;
            --busy: #ef4444;
            --offline: #64748b;
            --bg: var(--vscode-editor-background);
            --text: var(--vscode-editor-foreground);
            --card-bg: var(--vscode-editor-inactiveSelectionBackground);
            --button-bg: var(--vscode-button-background);
            --button-fg: var(--vscode-button-foreground);
            --button-hover: var(--vscode-button-hoverBackground);
        }
        body { background: var(--bg); color: var(--text); padding: 20px; font-family: sans-serif; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .refresh-btn { background: none; border: 1px solid var(--text); color: var(--text); padding: 5px 10px; cursor: pointer; border-radius: 4px; }
        
        .section-title { font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; created: 0.5; border-bottom: 1px solid var(--card-bg); padding-bottom: 5px; }

        /* Ownership Section */
        .ownership-card { background: var(--card-bg); padding: 15px; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid var(--busy); }
        .ownership-status { font-weight: bold; margin-bottom: 5px; }
        .owner-actions { display: flex; gap: 10px; margin-top: 10px; }
        .btn { background: var(--button-bg); color: var(--button-fg); border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: var(--button-hover); }
        .btn-secondary { background: transparent; border: 1px solid var(--text); }
        
        /* User List */
        .user-list { display: grid; gap: 10px; }
        .user-card { background: var(--card-bg); padding: 10px; border-radius: 6px; display: flex; align-items: center; gap: 12px; }
        .avatar { width: 32px; height: 32px; border-radius: 50%; background: #333; display: flex; align-items: center; justify-content: center; font-weight: bold; position: relative; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; position: absolute; bottom: 0; right: 0; border: 2px solid var(--card-bg); }
        .status-online { background: var(--online); }
        .status-away { background: var(--away); }
        .status-busy { background: var(--busy); }
        .user-info { flex: 1; }
        .user-name { font-weight: 600; }
        .user-file { font-size: 0.8em; opacity: 0.8; font-family: monospace; }
        .meta { font-size: 0.75em; opacity: 0.6; }
    </style>
</head>
<body>
    <div class="header">
        <h2>👥 Team Presence</h2>
        <button class="refresh-btn" onclick="refresh()">↻</button>
    </div>

    <!-- Ownership Section -->
    <div id="ownership-section" style="display:none;">
        <div class="section-title">Session Control</div>
        <div class="ownership-card">
            <div class="ownership-status">
                Current Owner: <span id="owner-name">Loading...</span>
            </div>
            <div class="meta" id="ownership-status-text">Status: Checking...</div>
            <div class="owner-actions" id="owner-actions">
                <!-- Buttons injected by JS -->
            </div>
        </div>
    </div>
    
    <div class="section-title">Online Members</div>
    <div id="users" class="user-list">
        <div style="text-align:center; opacity:0.6;">Loading...</div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentSessionId = null; 
        let currentUserId = '${vscode.env.machineId}'; // Unique per-machine identity

        function refresh() {
            document.getElementById('users').innerHTML = '<div style="text-align:center; opacity:0.6;">Refreshing...</div>';
            vscode.postMessage({ command: 'refresh' });
        }
        function openFile(file) {
            if(file) vscode.postMessage({ command: 'openFile', file });
        }
        
        function claimOwnership() {
            if(currentSessionId) {
                vscode.postMessage({ command: 'claimOwnership', sessionId: currentSessionId });
            }
        }
        
        function releaseOwnership() {
            if(currentSessionId) {
                 vscode.postMessage({ command: 'releaseOwnership', sessionId: currentSessionId });
            }
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            
            if (msg.command === 'updateOwnership') {
                const o = msg.ownership;
                if (!o) return;
                
                currentSessionId = o.session_id;
                
                const section = document.getElementById('ownership-section');
                section.style.display = 'block';
                
                document.getElementById('owner-name').innerText = o.owner_id || 'None';
                document.getElementById('ownership-status-text').innerText = 'Status: ' + o.status;
                
                const actions = document.getElementById('owner-actions');
                actions.innerHTML = '';
                
                if (o.status === 'claimed') {
                    // If current user is the owner, allow release
                     actions.innerHTML += '<button class="btn btn-secondary" onclick="releaseOwnership()">Release Control</button>';
                     // Force claim button
                     actions.innerHTML += '<button class="btn btn-secondary" onclick="claimOwnership()" style="margin-left:auto; opacity:0.5; font-size:0.8em;" title="Force Takeover">Force Claim</button>';
                } else {
                    actions.innerHTML = '<button class="btn" onclick="claimOwnership()">✋ Claim Control</button>';
                }
            }

            if (msg.command === 'updatePresence') {
                const data = msg.presence;
                const container = document.getElementById('users');
                if (data.users.length === 0) {
                    container.innerHTML = '<div style="text-align:center;">No one else is online.</div>';
                    return;
                }
                
                container.innerHTML = data.users.map(u => {
                    const initials = u.user_id.substring(0, 2).toUpperCase();
                    const statusClass = 'status-' + u.status;
                    const fileInfo = u.active_file ? 
                        '<div class="user-file" onclick="openFile(\\'' + u.active_file + '\\')" style="cursor:pointer">📄 ' + u.active_file + (u.cursor_line ? ':' + u.cursor_line : '') + '</div>' : 
                        '<div class="meta">Idle</div>';
                        
                    return '<div class="user-card">' +
                        '<div class="avatar">' + initials + '<div class="status-dot ' + statusClass + '"></div></div>' +
                        '<div class="user-info">' +
                            '<div class="user-name">' + u.user_id + '</div>' +
                            fileInfo +
                        '</div>' +
                    '</div>';
                }).join('');
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose() {
        CollaborationPanel.currentPanel = undefined;
        this._panel.dispose();
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = undefined;
        }
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}

