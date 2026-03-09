/**
 * Collaboration Panel — initial implementation.
 *
 * TODO: Add input sanitization for XSS prevention.
 */

import * as vscode from 'vscode';

export class CollaborationPanel {
    public static currentPanel: CollaborationPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.html = this._getHtmlForWebview();
    }

    public static createOrShow(extensionUri: vscode.Uri) {
        const panel = vscode.window.createWebviewPanel(
            'aegionCollaboration',
            'Aegion Collaboration',
            vscode.ViewColumn.One,
            { enableScripts: true }
        );
        CollaborationPanel.currentPanel = new CollaborationPanel(panel);
    }

    private _getHtmlForWebview(): string {
        return `<!DOCTYPE html>
        <html>
        <head><title>Collaboration</title></head>
        <body>
            <h1>Team Collaboration</h1>
            <div id="participants"></div>
            <div id="chat"></div>
        </body>
        </html>`;
    }

    public dispose() {
        CollaborationPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
