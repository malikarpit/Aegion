/**
 * Aegion Context Engine
 *
 * Centralizes workspace context collection for the VS Code extension.
 * Listens to editor events (file open/close, edits, focus changes)
 * and maintains a live snapshot that other services can query.
 *
 * Doctrine: "Context flows from observation, not assumption."
 */

import { Logger } from '../services/Logger';
import * as vscode from 'vscode';
import * as crypto from 'crypto';
import {
    WorkspaceContext,
    FileContext,
    EditEvent,
    GitContext,
    SessionSnapshot,
} from './types';

/** Maximum number of recent edits to retain. */
const MAX_RECENT_EDITS = 50;

/** Singleton instance. */
let _instance: ContextEngine | null = null;

export class ContextEngine implements vscode.Disposable {
    private disposables: vscode.Disposable[] = [];
    private recentEdits: EditEvent[] = [];
    private activeFilePath: string | null = null;
    private workspaceRoot: string;

    /** Session state accessor — injected from SessionManager. */
    private sessionAccessor: (() => SessionSnapshot) | null = null;

    constructor() {
        // Resolve workspace root
        const folders = vscode.workspace.workspaceFolders;
        this.workspaceRoot = folders && folders.length > 0
            ? folders[0].uri.fsPath
            : 'default';

        // Track active editor
        if (vscode.window.activeTextEditor) {
            this.activeFilePath = vscode.window.activeTextEditor.document.uri.fsPath;
        }

        // Subscribe to editor events
        this.disposables.push(
            vscode.window.onDidChangeActiveTextEditor(editor => {
                this.activeFilePath = editor?.document.uri.fsPath ?? null;
            }),
        );

        this.disposables.push(
            vscode.workspace.onDidChangeTextDocument(e => {
                if (e.document.uri.scheme !== 'file') { return; }
                const linesChanged = e.contentChanges.reduce(
                    (sum, change) => sum + Math.max(1, change.text.split('\n').length),
                    0,
                );
                this.recentEdits.push({
                    file_path: e.document.uri.fsPath,
                    timestamp: new Date().toISOString(),
                    lines_changed: linesChanged,
                });
                // Trim to cap
                if (this.recentEdits.length > MAX_RECENT_EDITS) {
                    this.recentEdits = this.recentEdits.slice(-MAX_RECENT_EDITS);
                }
            }),
        );
    }

    /**
     * Wire the session accessor so the engine can include session state
     * in its snapshots without a circular dependency on SessionManager.
     */
    setSessionAccessor(accessor: () => SessionSnapshot): void {
        this.sessionAccessor = accessor;
    }

    // ── Snapshot ──────────────────────────────────────────────

    /**
     * Capture a point-in-time snapshot of the full workspace context.
     */
    getSnapshot(): WorkspaceContext {
        const openFiles = this.getOpenFiles();
        const activeFile = this.getActiveFile();
        const git = this.getGitContext();
        const session = this.getSessionSnapshot();
        const timestamp = new Date().toISOString();

        const snapshot: WorkspaceContext = {
            workspace_root: this.workspaceRoot,
            active_file: activeFile,
            open_files: openFiles,
            recent_edits: [...this.recentEdits],
            git,
            session,
            context_hash: '', // computed below
            timestamp,
        };

        snapshot.context_hash = this.computeHash(snapshot);
        return snapshot;
    }

    /**
     * Get a compact context summary suitable for API payloads.
     * Returns only the most essential fields to keep request sizes small.
     */
    getCompactContext(): Record<string, unknown> {
        const snap = this.getSnapshot();
        return {
            workspace_root: snap.workspace_root,
            active_file: snap.active_file?.path ?? null,
            active_language: snap.active_file?.language ?? null,
            open_file_count: snap.open_files.length,
            dirty_file_count: snap.open_files.filter(f => f.is_dirty).length,
            recent_edit_count: snap.recent_edits.length,
            git_branch: snap.git.branch,
            git_dirty: snap.git.has_uncommitted,
            session_id: snap.session.session_id,
            session_status: snap.session.status,
            context_hash: snap.context_hash,
        };
    }

    // ── Internals ────────────────────────────────────────────

    private getOpenFiles(): FileContext[] {
        const files: FileContext[] = [];
        // tabGroups API (VS Code 1.67+)
        if (vscode.window.tabGroups) {
            for (const group of vscode.window.tabGroups.all) {
                for (const tab of group.tabs) {
                    const input = tab.input;
                    if (input && typeof input === 'object' && 'uri' in input) {
                        const uri = (input as { uri: vscode.Uri }).uri;
                        if (uri.scheme === 'file') {
                            // Find corresponding document for metadata
                            const doc = vscode.workspace.textDocuments.find(
                                d => d.uri.fsPath === uri.fsPath,
                            );
                            files.push({
                                path: uri.fsPath,
                                language: doc?.languageId ?? 'unknown',
                                line_count: doc?.lineCount ?? 0,
                                is_dirty: doc?.isDirty ?? false,
                            });
                        }
                    }
                }
            }
        } else {
            // Fallback: visible editors
            for (const editor of vscode.window.visibleTextEditors) {
                if (editor.document.uri.scheme === 'file') {
                    files.push({
                        path: editor.document.uri.fsPath,
                        language: editor.document.languageId,
                        line_count: editor.document.lineCount,
                        is_dirty: editor.document.isDirty,
                    });
                }
            }
        }
        return files;
    }

    private getActiveFile(): FileContext | null {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.uri.scheme !== 'file') { return null; }
        return {
            path: editor.document.uri.fsPath,
            language: editor.document.languageId,
            line_count: editor.document.lineCount,
            is_dirty: editor.document.isDirty,
        };
    }

    private getGitContext(): GitContext {
        const gitExt = vscode.extensions.getExtension('vscode.git');
        if (!gitExt?.isActive) {
            return { branch: 'unknown', has_uncommitted: false, repo_root: null };
        }

        try {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const git = gitExt.exports.getAPI(1) as any;
            const repo = git?.repositories?.[0];
            if (!repo) {
                return { branch: 'unknown', has_uncommitted: false, repo_root: null };
            }
            return {
                branch: repo.state?.HEAD?.name ?? 'unknown',
                has_uncommitted: (repo.state?.workingTreeChanges?.length ?? 0) > 0
                    || (repo.state?.indexChanges?.length ?? 0) > 0,
                repo_root: repo.rootUri?.fsPath ?? null,
            };
        } catch {
            return { branch: 'unknown', has_uncommitted: false, repo_root: null };
        }
    }

    private getSessionSnapshot(): SessionSnapshot {
        if (this.sessionAccessor) {
            return this.sessionAccessor();
        }
        return {
            session_id: null,
            status: 'inactive',
            decision_count: 0,
            evidence_count: 0,
            exploration_stage: 'exploration',
        };
    }

    private computeHash(snapshot: WorkspaceContext): string {
        const significant = {
            workspace_root: snapshot.workspace_root,
            active_file: snapshot.active_file?.path ?? '',
            open_files: snapshot.open_files.map(f => f.path).sort(),
            git_branch: snapshot.git.branch,
            session_id: snapshot.session.session_id ?? '',
        };
        return crypto
            .createHash('sha256')
            .update(JSON.stringify(significant))
            .digest('hex')
            .slice(0, 16); // 16-char prefix is sufficient for dedup
    }

    // ── Lifecycle ────────────────────────────────────────────

    dispose(): void {
        for (const d of this.disposables) {
            d.dispose();
        }
        this.disposables = [];
        _instance = null;
    }
}

// ── Public API ───────────────────────────────────────────────

/**
 * Get the singleton ContextEngine instance.
 * Returns null if `registerContextEngine` hasn't been called yet.
 */
export function getContextEngine(): ContextEngine | null {
    return _instance;
}

/**
 * Register the ContextEngine with the extension.
 * Called from `activate()` in extension.ts.
 */
export function registerContextEngine(context: vscode.ExtensionContext): ContextEngine {
    if (_instance) { return _instance; }

    _instance = new ContextEngine();
    context.subscriptions.push(_instance);

    Logger.info('Aegion ContextEngine registered');
    return _instance;
}
