/* eslint-disable no-case-declarations */
/**
 * Aegion Multi-File Review Panel
 *
 * Multi-file review interface for proposal diffs:
 * - File tree with change indicators (added/modified/deleted)
 * - Side-by-side or inline diff view
 * - Per-file approve/reject with comments
 * - Overall decision controls
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

interface FileChange {
    path: string;
    status: 'added' | 'modified' | 'deleted' | 'renamed';
    additions: number;
    deletions: number;
    diff?: string;
}

export class MultiFileReviewPanel {
    public static currentPanel: MultiFileReviewPanel | undefined;
    public static readonly viewType = 'aegion.multiFileReview';
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];
    private _proposalId?: string;
    private _sessionId?: string;

    public static show(extensionUri: vscode.Uri, proposalId?: string): void {
        const column = vscode.ViewColumn.One;

        if (MultiFileReviewPanel.currentPanel) {
            MultiFileReviewPanel.currentPanel._panel.reveal(column);
            if (proposalId) {
                MultiFileReviewPanel.currentPanel._proposalId = proposalId;
                MultiFileReviewPanel.currentPanel._loadData(proposalId);
            }
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            MultiFileReviewPanel.viewType,
            '📝 Multi-File Review',
            column,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        MultiFileReviewPanel.currentPanel = new MultiFileReviewPanel(panel, extensionUri, proposalId);
    }

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri, proposalId?: string) {
        this._panel = panel;
        this._proposalId = proposalId;
        this._panel.webview.html = this._getHtml();
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            async (msg) => this._handleMessage(msg), null, this._disposables,
        );
        if (proposalId) {
            this._loadData(proposalId);
        }
    }

    private async _loadData(proposalId?: string): Promise<void> {
        const id = proposalId || this._proposalId;
        if (!id) {
            this._panel.webview.postMessage({ command: 'noProposal' });
            return;
        }

        try {
            const api = getApiClient();
            // Need sessionId for getProposal
            let sessionId = this._sessionId;
            if (!sessionId) {
                try {
                    const sessions = await api.getActiveSessions();
                    sessionId = sessions?.[0]?.session_id;
                } catch { /* ignore */ }
            }
            if (!sessionId) {
                this._panel.webview.postMessage({ command: 'error', message: 'No active session — start a session first' });
                return;
            }
            this._sessionId = sessionId;

            const proposal = await api.getProposal(sessionId, id);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const proposalAny = proposal as any;
            const diffContent = (proposalAny.diff as string) || '';
            // Synthesise file changes from the diff field
            const files: FileChange[] = diffContent
                ? [{
                    path: ((proposalAny.affected_modules as string[]) || ['changes'])[0],
                    status: 'modified' as const,
                    additions: (diffContent.match(/^\+/gm) || []).length,
                    deletions: (diffContent.match(/^-/gm) || []).length,
                    diff: diffContent,
                }]
                : [];
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const p = proposal as any;
            this._panel.webview.postMessage({
                command: 'update',
                proposal: {
                    id: p.proposal_id || id,
                    title: p.claim || p.title || 'Unnamed Proposal',
                    description: p.reasoning || '',
                    author: p.author_id || 'unknown',
                    tier: p.tier || 'tier_1',
                    status: p.status || 'pending',
                    created_at: p.created_at,
                },
                files,
            });
        } catch {
            this._panel.webview.postMessage({ command: 'error', message: 'Failed to load proposal data' });
        }
    }

    private async _handleMessage(msg: { command: string;[k: string]: unknown }): Promise<void> {
        switch (msg.command) {
            case 'refresh':
                await this._loadData();
                break;
            case 'selectProposal':
                const proposals = await vscode.window.showQuickPick(
                    ['Enter proposal ID manually'],
                    { placeHolder: 'Select proposal to review' },
                );
                if (proposals) {
                    const id = await vscode.window.showInputBox({ prompt: 'Enter proposal ID' });
                    if (id) {
                        this._proposalId = id;
                        await this._loadData(id);
                    }
                }
                break;
            case 'openFile':
                const filePath = msg.path as string;
                try {
                    const doc = await vscode.workspace.openTextDocument(filePath);
                    await vscode.window.showTextDocument(doc, vscode.ViewColumn.Two);
                } catch {
                    vscode.window.showWarningMessage(`Cannot open file: ${filePath}`);
                }
                break;
            case 'addComment':
                const comment = await vscode.window.showInputBox({
                    prompt: `Comment on ${msg.file}`,
                    placeHolder: 'Enter your review comment...',
                });
                if (comment) {
                    this._panel.webview.postMessage({
                        command: 'commentAdded',
                        file: msg.file,
                        comment,
                    });
                }
                break;
            case 'approve':
                if (!this._sessionId || !this._proposalId) {
                    vscode.window.showErrorMessage('Session or proposal Not initialized');
                    break;
                }
                const api = getApiClient();
                try {
                    const comments = msg.comments as Record<string, string>;
                    const reason = Object.values(comments).filter(Boolean).join('; ') || 'Approved via Multi-File Review';
                    await api.approveProposal(this._sessionId, this._proposalId, {
                        evidence_ids: [],
                        justification: reason,
                    });
                    vscode.window.showInformationMessage('Proposal approved!');
                    await this._loadData();
                } catch {
                    vscode.window.showErrorMessage('Failed to approve proposal');
                }
                break;
            case 'reject':
                const rejectReason = await vscode.window.showInputBox({
                    prompt: 'Rejection reason',
                    placeHolder: 'Explain why this proposal should be rejected...',
                });
                if (rejectReason) {
                    if (!this._sessionId || !this._proposalId) {
                        vscode.window.showErrorMessage('Session or proposal Not initialized');
                        break;
                    }
                    try {
                        const api2 = getApiClient();
                        await api2.rejectProposal(this._sessionId, this._proposalId, rejectReason);
                        vscode.window.showInformationMessage('Proposal rejected');
                        await this._loadData();
                    } catch {
                        vscode.window.showErrorMessage('Failed to reject proposal');
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
    <title>Multi-File Review</title>
    <style>
        :root {
            --bg: var(--vscode-editor-background);
            --text: var(--vscode-editor-foreground);
            --card-bg: var(--vscode-editor-inactiveSelectionBackground);
            --border: var(--vscode-panel-border, #333);
            --accent: #6366f1;
            --added: #22c55e;
            --deleted: #ef4444;
            --modified: #3b82f6;
            --renamed: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: grid; grid-template-columns: 280px 1fr; height: 100vh; }

        /* File Tree Sidebar */
        .sidebar {
            border-right: 1px solid var(--border); padding: 12px; overflow-y: auto;
            display: flex; flex-direction: column;
        }
        .sidebar-header { margin-bottom: 12px; }
        .sidebar-header h3 { font-size: 0.9em; margin-bottom: 4px; }
        .proposal-meta { font-size: 0.75em; opacity: 0.6; }
        .file-stats { display: flex; gap: 12px; margin: 8px 0; font-size: 0.8em; }
        .stat-added { color: var(--added); }
        .stat-deleted { color: var(--deleted); }

        .file-list { flex: 1; overflow-y: auto; }
        .file-item {
            display: flex; align-items: center; gap: 6px; padding: 6px 8px;
            border-radius: 4px; cursor: pointer; font-size: 0.85em; margin-bottom: 2px;
        }
        .file-item:hover { background: rgba(255,255,255,0.05); }
        .file-item.active { background: rgba(99,102,241,0.15); border-left: 3px solid var(--accent); }
        .file-icon { width: 14px; height: 14px; border-radius: 3px; display: inline-block; flex-shrink: 0; }
        .icon-added { background: var(--added); }
        .icon-modified { background: var(--modified); }
        .icon-deleted { background: var(--deleted); }
        .icon-renamed { background: var(--renamed); }
        .file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-changes { font-size: 0.75em; opacity: 0.5; }

        .review-actions {
            border-top: 1px solid var(--border); padding-top: 12px; margin-top: 12px;
            display: flex; flex-direction: column; gap: 6px;
        }
        .btn { padding: 8px 14px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; width: 100%; }
        .btn-approve { background: var(--added); color: white; }
        .btn-reject { background: var(--deleted); color: white; }
        .btn-select { background: var(--card-bg); color: var(--text); border: 1px solid var(--border); }

        /* Main Content */
        .main { padding: 16px; overflow-y: auto; }

        .diff-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .diff-filename { font-weight: 600; font-size: 1.1em; }
        .diff-badge { padding: 2px 10px; border-radius: 10px; font-size: 0.75em; font-weight: 600; text-transform: uppercase; }

        .diff-content {
            background: var(--card-bg); border-radius: 8px; padding: 12px;
            font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px;
            overflow-x: auto; line-height: 1.6; white-space: pre; tab-size: 4;
        }
        .diff-line-add { background: rgba(34,197,94,0.1); color: var(--added); }
        .diff-line-del { background: rgba(239,68,68,0.1); color: var(--deleted); }
        .diff-line-ctx { opacity: 0.5; }
        .diff-line-hunk { color: var(--accent); font-weight: 600; }

        .comment-section {
            margin-top: 12px; padding: 12px; background: var(--card-bg); border-radius: 8px;
        }
        .comment-btn {
            padding: 4px 10px; border: 1px dashed var(--border); border-radius: 6px;
            background: transparent; color: var(--text); cursor: pointer; font-size: 0.85em; opacity: 0.6;
        }
        .comment-btn:hover { opacity: 1; border-style: solid; }
        .comment-bubble {
            margin-top: 8px; padding: 8px 12px; background: rgba(99,102,241,0.1);
            border-left: 3px solid var(--accent); border-radius: 0 6px 6px 0; font-size: 0.85em;
        }

        .empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; opacity: 0.5; gap: 12px; }
        .empty-state .icon { font-size: 3em; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h3 id="proposal-title">📝 Multi-File Review</h3>
            <div class="proposal-meta" id="proposal-meta">Select a proposal to review</div>
            <div class="file-stats">
                <span class="stat-added" id="total-added">+0</span>
                <span class="stat-deleted" id="total-deleted">-0</span>
                <span id="file-count">0 files</span>
            </div>
        </div>
        <div class="file-list" id="file-list"></div>
        <div class="review-actions">
            <button class="btn btn-select" onclick="selectProposal()">📂 Load Proposal</button>
            <button class="btn btn-approve" id="btn-approve" onclick="approveAll()" disabled>✓ Approve</button>
            <button class="btn btn-reject" id="btn-reject" onclick="rejectAll()" disabled>✕ Reject</button>
        </div>
    </div>

    <div class="main" id="main-content">
        <div class="empty-state">
            <div class="icon">📂</div>
            <div>Select a file from the sidebar to view changes</div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentFiles = [];
        let selectedFile = null;
        let fileComments = {};

        function selectProposal() { vscode.postMessage({ command: 'selectProposal' }); }
        function approveAll() { vscode.postMessage({ command: 'approve', comments: fileComments }); }
        function rejectAll() { vscode.postMessage({ command: 'reject' }); }
        function openInEditor(path) { vscode.postMessage({ command: 'openFile', path }); }
        function addComment(file) { vscode.postMessage({ command: 'addComment', file }); }

        function selectFile(path) {
            selectedFile = path;
            // Update active state
            document.querySelectorAll('.file-item').forEach(el => {
                el.classList.toggle('active', el.dataset.path === path);
            });

            const file = currentFiles.find(f => f.path === path);
            if (!file) return;

            const statusColor = { added: 'var(--added)', modified: 'var(--modified)', deleted: 'var(--deleted)', renamed: 'var(--renamed)' };
            const diffHtml = file.diff ? file.diff.split('\\n').map(line => {
                if (line.startsWith('@@')) return '<div class="diff-line-hunk">' + escHtml(line) + '</div>';
                if (line.startsWith('+')) return '<div class="diff-line-add">' + escHtml(line) + '</div>';
                if (line.startsWith('-')) return '<div class="diff-line-del">' + escHtml(line) + '</div>';
                return '<div class="diff-line-ctx">' + escHtml(line) + '</div>';
            }).join('') : '<div style="opacity:0.5;padding:20px;text-align:center">No diff available for this file</div>';

            const comments = fileComments[path] || [];
            const commentsHtml = comments.map(c => '<div class="comment-bubble">' + escHtml(c) + '</div>').join('');

            document.getElementById('main-content').innerHTML =
                '<div class="diff-header">' +
                    '<span class="diff-filename">' + path.split('/').pop() + '</span>' +
                    '<div>' +
                        '<span class="diff-badge" style="background:' + (statusColor[file.status] || 'var(--accent)') + '22;color:' + (statusColor[file.status] || 'var(--accent)') + '">' + file.status + '</span> ' +
                        '<button class="btn" style="display:inline;width:auto;padding:4px 10px;background:var(--card-bg);border:1px solid var(--border)" onclick="openInEditor(\\'' + file.path + '\\')">Open</button>' +
                    '</div>' +
                '</div>' +
                '<div style="font-size:0.8em;opacity:0.5;margin-bottom:8px">' + file.path + ' &nbsp; <span class="stat-added">+' + file.additions + '</span> <span class="stat-deleted">-' + file.deletions + '</span></div>' +
                '<div class="diff-content">' + diffHtml + '</div>' +
                '<div class="comment-section">' +
                    '<button class="comment-btn" onclick="addComment(\\'' + file.path + '\\')">💬 Add Comment</button>' +
                    commentsHtml +
                '</div>';
        }

        function escHtml(s) {
            const div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }

        window.addEventListener('message', event => {
            const msg = event.data;

            if (msg.command === 'update') {
                currentFiles = msg.files || [];
                const proposal = msg.proposal;

                document.getElementById('proposal-title').textContent = proposal.title || 'Review';
                document.getElementById('proposal-meta').textContent =
                    'by ' + proposal.author + ' • ' + proposal.tier.toUpperCase() + ' • ' + proposal.status;

                const totalAdded = currentFiles.reduce((s, f) => s + f.additions, 0);
                const totalDeleted = currentFiles.reduce((s, f) => s + f.deletions, 0);
                document.getElementById('total-added').textContent = '+' + totalAdded;
                document.getElementById('total-deleted').textContent = '-' + totalDeleted;
                document.getElementById('file-count').textContent = currentFiles.length + ' files';

                document.getElementById('btn-approve').disabled = false;
                document.getElementById('btn-reject').disabled = false;

                const list = document.getElementById('file-list');
                list.innerHTML = currentFiles.map(f => {
                    const iconClass = 'icon-' + f.status;
                    const shortName = f.path.split('/').pop();
                    const dir = f.path.split('/').slice(0, -1).join('/');
                    return '<div class="file-item" data-path="' + f.path + '" onclick="selectFile(\\'' + f.path + '\\')">' +
                        '<span class="file-icon ' + iconClass + '"></span>' +
                        '<span class="file-name" title="' + f.path + '">' + shortName + '</span>' +
                        '<span class="file-changes">+' + f.additions + ' -' + f.deletions + '</span>' +
                    '</div>';
                }).join('');

                // Auto-select first file
                if (currentFiles.length > 0 && !selectedFile) {
                    selectFile(currentFiles[0].path);
                }
            }

            if (msg.command === 'commentAdded') {
                if (!fileComments[msg.file]) fileComments[msg.file] = [];
                fileComments[msg.file].push(msg.comment);
                if (selectedFile === msg.file) selectFile(msg.file);
            }

            if (msg.command === 'noProposal') {
                document.getElementById('main-content').innerHTML =
                    '<div class="empty-state"><div class="icon">📂</div><div>Click "Load Proposal" to begin review</div></div>';
            }

            if (msg.command === 'error') {
                document.getElementById('main-content').innerHTML =
                    '<div class="empty-state"><div class="icon">⚠️</div><div>' + msg.message + '</div></div>';
            }
        });
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        MultiFileReviewPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
