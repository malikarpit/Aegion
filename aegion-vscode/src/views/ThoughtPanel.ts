
import * as vscode from 'vscode';
import { ThoughtService } from '../services/ThoughtService';
import { getActiveWorkspaceId } from '../config';

export class ThoughtPanel {
    public static currentPanel: ThoughtPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _thoughtService: ThoughtService;

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, thoughtService: ThoughtService) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._thoughtService = thoughtService;

        // Set the webview's initial html content
        this._update();

        // Listen for when the panel is disposed
        // This happens when the user closes the panel or when the panel is closed programmatically
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Update the content based on view state changes
        this._panel.onDidChangeViewState(
            _e => {
                if (this._panel.visible) {
                    this._update();
                }
            },
            null,
            this._disposables,
        );

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async message => {
                switch (message.command) {
                    case 'alert':
                        vscode.window.showErrorMessage(message.text);
                        return;
                    case 'saveDraft':
                        await this._handleSaveDraft(message.data);
                        return;
                    case 'seal':
                        await this._handleSeal();
                        return;
                }
            },
            null,
            this._disposables,
        );

        // Listen to service updates
        this._thoughtService.onDidChangeDraft(_draft => {
            this._update();
        });
    }

    public static createOrShow(extensionUri: vscode.Uri, thoughtService: ThoughtService) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        // If we already have a panel, show it.
        if (ThoughtPanel.currentPanel) {
            ThoughtPanel.currentPanel._panel.reveal(column);
            return;
        }

        // Otherwise, create a new panel.
        const panel = vscode.window.createWebviewPanel(
            'aegionThought',
            'Capture Thought',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')],
            },
        );

        ThoughtPanel.currentPanel = new ThoughtPanel(panel, extensionUri, thoughtService);
    }

    public dispose() {
        ThoughtPanel.currentPanel = undefined;

        this._panel.dispose();

        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private async _handleSaveDraft(data: { title: string, rationale: string, alternatives: string }) {
        const alternativesList = data.alternatives.split('\n').filter(s => s.trim().length > 0);

        // Derive real workspace and session IDs from context
        const workspaceId = getActiveWorkspaceId();
        const sessionId = vscode.workspace.getConfiguration('aegion').get<string>('activeSessionId') || 'current-session';

        if (!this._thoughtService.currentDraft) {
            await this._thoughtService.startDraft(data.title, data.rationale, sessionId, workspaceId);
        } else {
            await this._thoughtService.updateDraft({
                title: data.title,
                rationale: data.rationale,
                alternatives: alternativesList,
            });
        }

        vscode.window.showInformationMessage('Thought draft saved.');
    }

    private async _handleSeal() {
        if (!this._thoughtService.currentDraft) {
            vscode.window.showErrorMessage('No draft to seal.');
            return;
        }
        await this._thoughtService.sealDraft();
    }

    private _update() {
        const webview = this._panel.webview;
        this._panel.webview.html = this._getHtmlForWebview(webview);
    }

    private _getHtmlForWebview(_webview: vscode.Webview) {
        // Use a nonce to whitelist which scripts can be run
        const nonce = getNonce();

        const draft = this._thoughtService.currentDraft;
        const title = draft?.title || '';
        const rationale = draft?.rationale || '';
        const alternatives = draft ? (draft.alternatives || []).join('\n') : '';
        const isSealed = draft?.state === 'sealed';

        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Capture Thought</title>
                <style>
                    body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-editor-foreground); }
                    input, textarea { width: 100%; margin-bottom: 10px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 5px; }
                    button { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 8px 12px; cursor: pointer; }
                    button:hover { background: var(--vscode-button-hoverBackground); }
                    .sealed { opacity: 0.6; pointer-events: none; }
                    label { display: block; margin-top: 10px; font-weight: bold; }
                    .status { margin-bottom: 10px; font-style: italic; color: var(--vscode-descriptionForeground); }
                </style>
            </head>
            <body>
                <h2>Capture Thought</h2>
                <div class="status">Status: ${draft ? draft.state.toUpperCase() : 'NEW'}</div>
                
                <div class="${isSealed ? 'sealed' : ''}">
                    <label>Title (Short Summary)</label>
                    <input type="text" id="title" value="${title}" placeholder="E.g., Refactoring Auth Middleware">
                    
                    <label>Rationale (The "Why")</label>
                    <textarea id="rationale" rows="6" placeholder="Explain the reasoning behind this change...">${rationale}</textarea>
                    
                    <label>Alternatives Considered (One per line)</label>
                    <textarea id="alternatives" rows="4" placeholder="- Using JWT\n- Using Session Cookies">${alternatives}</textarea>
                    
                    <button id="saveBtn">Save Draft</button>
                    <button id="sealBtn" style="background: var(--vscode-statusBarItem-warningBackground); color: var(--vscode-statusBarItem-warningForeground);">Seal Thought</button>
                </div>

                ${isSealed ? '<p>This thought is SEALED. <button id="linkBtn">Link to Commit</button></p>' : ''}

                <script nonce="${nonce}">
                    const vscode = acquireVsCodeApi();
                    
                    document.getElementById('saveBtn').addEventListener('click', () => {
                        const title = document.getElementById('title').value;
                        const rationale = document.getElementById('rationale').value;
                        const alternatives = document.getElementById('alternatives').value;
                        vscode.postMessage({
                            command: 'saveDraft',
                            data: { title, rationale, alternatives }
                        });
                    });

                    document.getElementById('sealBtn').addEventListener('click', () => {
                        vscode.postMessage({ command: 'seal' });
                    });
                    
                    // If sealed, we might have a link button (logic simplified here)
                    const linkBtn = document.getElementById('linkBtn');
                    if (linkBtn) {
                        linkBtn.addEventListener('click', () => {
                            // Trigger VS Code command to link? 
                            // For now just alert or use command URI
                            vscode.postMessage({ command: 'alert', text: 'Please use the "Aegion: Link Thought to Commit" command.' });
                        });
                    }
                </script>
            </body>
            </html>`;
    }
}

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
