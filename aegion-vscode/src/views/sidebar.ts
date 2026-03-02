// Aegion Sidebar Webview Provider - 4-Panel Governance UI

import * as vscode from 'vscode';
import { SessionManager, SessionState } from '../session/manager';

export class AegionSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aegion.views.context';
    private _view?: vscode.WebviewView;
    private sessionManager: SessionManager;

    constructor(
        private readonly extensionUri: vscode.Uri,
        sessionManager: SessionManager,
    ) {
        this.sessionManager = sessionManager;

        // Listen for session state changes
        sessionManager.onStateChange((state) => {
            this.updateWebview(state);
        });
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'startSession':
                    await this.sessionManager.startSession();
                    break;
                case 'closeSession':
                    await this.sessionManager.closeSession(message.distill ?? true);
                    break;
                case 'setStage':
                    this.sessionManager.setExplorationStage(message.stage);
                    break;
                case 'createProposal':
                    vscode.commands.executeCommand('aegion.createProposal');
                    break;
                case 'invokeCouncil':
                    vscode.commands.executeCommand('aegion.invokeCouncil', message.prompt);
                    break;
            }
        });

        // Initial state update
        this.updateWebview(this.sessionManager.getState());
    }

    private updateWebview(state: SessionState): void {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'stateUpdate',
                state,
            });
        }
    }

    private _getHtmlForWebview(_webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aegion</title>
    <style>
        :root {
            --vscode-font-family: var(--vscode-editor-font-family);
        }
        body {
            font-family: var(--vscode-font-family);
            padding: 0;
            margin: 0;
            color: var(--vscode-foreground);
            background: var(--vscode-sideBar-background);
        }
        .panel {
            padding: 12px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .panel-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            color: var(--vscode-sideBarSectionHeader-foreground);
        }
        .panel-header .icon { font-size: 14px; }
        
        /* Session Panel */
        .session-status {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            border-radius: 4px;
            background: var(--vscode-input-background);
            margin-bottom: 8px;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .status-dot.active { background: #4ade80; }
        .status-dot.inactive { background: #fbbf24; }
        .status-dot.closing { background: #60a5fa; }
        
        /* Stage Selector */
        .stage-selector {
            display: flex;
            gap: 4px;
            margin: 8px 0;
        }
        .stage-btn {
            flex: 1;
            padding: 6px 8px;
            font-size: 11px;
            border: 1px solid var(--vscode-button-secondaryBorder);
            border-radius: 4px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            cursor: pointer;
            text-align: center;
        }
        .stage-btn.active {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-color: var(--vscode-button-background);
        }
        .stage-btn:hover { opacity: 0.9; }
        
        /* Buttons */
        .btn {
            width: 100%;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            margin-top: 8px;
        }
        .btn-primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
        .btn:hover { opacity: 0.9; }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: 8px 0;
        }
        .stat-item {
            padding: 8px;
            background: var(--vscode-input-background);
            border-radius: 4px;
            text-align: center;
        }
        .stat-value {
            font-size: 20px;
            font-weight: 600;
        }
        .stat-label {
            font-size: 10px;
            text-transform: uppercase;
            opacity: 0.7;
        }
        
        /* Council Chat */
        .chat-input {
            width: 100%;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 4px;
            resize: vertical;
            min-height: 60px;
            font-family: inherit;
        }
        .chat-input:focus {
            outline: 1px solid var(--vscode-focusBorder);
        }
        
        /* Visibility Labels */
        .label {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 500;
        }
        .label-ai { background: rgba(147, 51, 234, 0.2); color: #a855f7; }
        .label-human { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .label-governed { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        
        /* Hidden state */
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <!-- Session Panel -->
    <div class="panel" id="sessionPanel">
        <div class="panel-header">
            <span class="icon">🛡️</span> Session
        </div>
        <div class="session-status">
            <div class="status-dot" id="statusDot"></div>
            <span id="sessionStatus">Inactive</span>
        </div>
        
        <div id="activeSessionContent" class="hidden">
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value" id="decisionCount">0</div>
                    <div class="stat-label">Decisions</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="evidenceCount">0</div>
                    <div class="stat-label">Evidence</div>
                </div>
            </div>
            
            <div class="panel-header" style="margin-top: 12px;">
                <span class="icon">🎯</span> Stage
            </div>
            <div class="stage-selector">
                <button class="stage-btn" data-stage="exploration">🧠 Explore</button>
                <button class="stage-btn" data-stage="proposed">🏗️ Propose</button>
                <button class="stage-btn" data-stage="governed">🏛️ Govern</button>
            </div>
            
            <button class="btn btn-secondary" id="closeSessionBtn">Close Session</button>
        </div>
        
        <button class="btn btn-primary" id="startSessionBtn">Start Session</button>
    </div>
    
    <!-- Council Panel -->
    <div class="panel" id="councilPanel">
        <div class="panel-header">
            <span class="icon">⚖️</span> AI Council
        </div>
        <textarea class="chat-input" id="councilInput" placeholder="Ask the council for guidance..."></textarea>
        <button class="btn btn-primary" id="invokeCouncilBtn" disabled>Invoke Council</button>
        <div style="margin-top: 8px; font-size: 10px; opacity: 0.7;">
            Child → Parent → Sentinel pipeline
        </div>
    </div>
    
    <!-- Decisions Panel -->
    <div class="panel" id="decisionsPanel">
        <div class="panel-header">
            <span class="icon">📋</span> Recent Decisions
        </div>
        <div id="decisionsList" style="font-size: 12px; opacity: 0.7;">
            No decisions yet
        </div>
        <button class="btn btn-secondary" id="createProposalBtn" disabled>Create Proposal</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        
        // State
        let currentState = {
            sessionId: null,
            status: 'inactive',
            explorationStage: 'exploration',
            decisionCount: 0,
            evidenceCount: 0
        };
        
        // Elements
        const statusDot = document.getElementById('statusDot');
        const sessionStatus = document.getElementById('sessionStatus');
        const activeContent = document.getElementById('activeSessionContent');
        const startBtn = document.getElementById('startSessionBtn');
        const closeBtn = document.getElementById('closeSessionBtn');
        const stageBtns = document.querySelectorAll('.stage-btn');
        const decisionCount = document.getElementById('decisionCount');
        const evidenceCount = document.getElementById('evidenceCount');
        const councilInput = document.getElementById('councilInput');
        const invokeBtn = document.getElementById('invokeCouncilBtn');
        const proposalBtn = document.getElementById('createProposalBtn');
        
        // Event Listeners
        startBtn.addEventListener('click', () => {
            vscode.postMessage({ command: 'startSession' });
        });
        
        closeBtn.addEventListener('click', () => {
            vscode.postMessage({ command: 'closeSession', distill: true });
        });
        
        stageBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const stage = btn.dataset.stage;
                vscode.postMessage({ command: 'setStage', stage });
            });
        });
        
        invokeBtn.addEventListener('click', () => {
            const prompt = councilInput.value.trim();
            if (prompt) {
                vscode.postMessage({ command: 'invokeCouncil', prompt });
                councilInput.value = '';
            }
        });
        
        proposalBtn.addEventListener('click', () => {
            vscode.postMessage({ command: 'createProposal' });
        });
        
        councilInput.addEventListener('input', () => {
            invokeBtn.disabled = !councilInput.value.trim() || currentState.status !== 'active';
        });
        
        // State Update Handler
        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'stateUpdate') {
                currentState = message.state;
                updateUI();
            }
        });
        
        function updateUI() {
            // Status dot
            statusDot.className = 'status-dot ' + currentState.status;
            
            // Session status text
            if (currentState.status === 'active') {
                sessionStatus.textContent = 'Active: ' + (currentState.sessionId?.slice(0, 8) || '') + '...';
                activeContent.classList.remove('hidden');
                startBtn.classList.add('hidden');
                invokeBtn.disabled = !councilInput.value.trim();
                proposalBtn.disabled = false;
            } else if (currentState.status === 'closing') {
                sessionStatus.textContent = 'Closing...';
                activeContent.classList.add('hidden');
                startBtn.classList.add('hidden');
            } else {
                sessionStatus.textContent = 'Inactive';
                activeContent.classList.add('hidden');
                startBtn.classList.remove('hidden');
                invokeBtn.disabled = true;
                proposalBtn.disabled = true;
            }
            
            // Stats
            decisionCount.textContent = currentState.decisionCount;
            evidenceCount.textContent = currentState.evidenceCount;
            
            // Stage buttons
            stageBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.stage === currentState.explorationStage);
            });
        }
        
        // Initial UI update
        updateUI();
    </script>
</body>
</html>`;
    }
}
