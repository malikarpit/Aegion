import * as vscode from 'vscode';

/**
 * AG-005: Recovery View.
 *
 * Sidebar TreeView showing:
 * - Drafts (restorable paused sessions)
 * - Orphaned sessions (recoverable crashed sessions)
 *
 * Actions: Restore Draft, Recover Session, Delete Draft.
 */

interface RecoveryItem {
    id: string;
    label: string;
    type: 'draft' | 'orphan';
    detail?: string;
    tags?: string[];
}

class RecoveryTreeItem extends vscode.TreeItem {
    constructor(
        public readonly item: RecoveryItem,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
    ) {
        super(item.label, collapsibleState);

        this.tooltip = `${item.type === 'draft' ? '📝 Draft' : '⚠️ Orphan'}: ${item.label}`;
        this.description = item.detail || '';
        this.contextValue = item.type;

        this.iconPath = new vscode.ThemeIcon(
            item.type === 'draft' ? 'file-text' : 'warning',
        );
    }
}

class RecoverySectionItem extends vscode.TreeItem {
    constructor(
        label: string,
        public readonly sectionType: 'drafts' | 'orphans',
        count: number,
    ) {
        super(label, count > 0 ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.Collapsed);
        this.description = `(${count})`;
        this.iconPath = new vscode.ThemeIcon(
            sectionType === 'drafts' ? 'notebook' : 'debug-disconnect',
        );
        this.contextValue = 'section';
    }
}

export class RecoveryViewProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined | null>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private drafts: RecoveryItem[] = [];
    private orphans: RecoveryItem[] = [];
    private _apiBase: string;

    constructor(private readonly _context: vscode.ExtensionContext) {
        const config = vscode.workspace.getConfiguration('aegion');
        this._apiBase = config.get<string>('backendUrl', 'http://localhost:8000');
    }

    refresh(): void {
        this._fetchData();
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
        if (!element) {
            // Root level: sections
            return [
                new RecoverySectionItem('Drafts', 'drafts', this.drafts.length),
                new RecoverySectionItem('Orphaned Sessions', 'orphans', this.orphans.length),
            ];
        }

        if (element instanceof RecoverySectionItem) {
            const items = element.sectionType === 'drafts' ? this.drafts : this.orphans;
            return items.map(item => new RecoveryTreeItem(item));
        }

        return [];
    }

    private async _fetchData(): Promise<void> {
        try {
            // Fetch drafts
            const draftResp = await fetch(`${this._apiBase}/api/v1/sessions/drafts/`, {
                headers: this._getHeaders(),
            });
            if (draftResp.ok) {
                const draftsData = await draftResp.json() as Record<string, unknown>[];
                this.drafts = draftsData.map(d => ({
                    id: String(d.draft_id),
                    label: String(d.title || 'Untitled Draft'),
                    type: 'draft' as const,
                    detail: String(d.workspace_id),
                    tags: Array.isArray(d.tags) ? d.tags.map(String) : [],
                }));
            }

            // Fetch orphaned sessions
            const orphanResp = await fetch(`${this._apiBase}/api/v1/sessions/orphaned?threshold_minutes=60`, {
                headers: this._getHeaders(),
            });
            if (orphanResp.ok) {
                const orphansData = await orphanResp.json() as Record<string, unknown>[];
                this.orphans = orphansData.map(s => ({
                    id: String(s.session_id),
                    label: `Session ${s.session_id}`,
                    type: 'orphan' as const,
                    detail: `Inactive since ${s.last_activity_at || 'unknown'}`,
                }));
            }
        } catch {
            // API unavailable — show empty
            this.drafts = [];
            this.orphans = [];
        }
    }

    private _getHeaders(): Record<string, string> {
        return {
            'Content-Type': 'application/json',
            'X-Aegion-Session': 'vscode-recovery',
            'X-Aegion-Intent': 'recovery_view',
        };
    }

    // ── Commands ──

    async restoreDraft(item: RecoveryTreeItem): Promise<void> {
        try {
            const resp = await fetch(
                `${this._apiBase}/api/v1/sessions/drafts/${item.item.id}/restore`,
                { method: 'POST', headers: this._getHeaders() },
            );
            if (resp.ok) {
                const data = await resp.json() as Record<string, unknown>;
                vscode.window.showInformationMessage(`Draft restored → Session ${data.session_id}`);
                this.refresh();
            } else {
                const err = await resp.json() as Record<string, unknown>;
                vscode.window.showErrorMessage(`Restore failed: ${err.detail}`);
            }
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            vscode.window.showErrorMessage(`Restore failed: ${msg}`);
        }
    }

    async recoverSession(item: RecoveryTreeItem): Promise<void> {
        const confirm = await vscode.window.showWarningMessage(
            `Recover session ${item.item.id}? This will expire the original and create a draft.`,
            'Recover', 'Cancel',
        );
        if (confirm !== 'Recover') { return; }

        try {
            const resp = await fetch(
                `${this._apiBase}/api/v1/sessions/${item.item.id}/recover`,
                { method: 'POST', headers: this._getHeaders() },
            );
            if (resp.ok) {
                vscode.window.showInformationMessage('Session recovered as draft');
                this.refresh();
            } else {
                const err = await resp.json() as Record<string, unknown>;
                vscode.window.showErrorMessage(`Recovery failed: ${err.detail}`);
            }
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            vscode.window.showErrorMessage(`Recovery failed: ${msg}`);
        }
    }

    async deleteDraft(item: RecoveryTreeItem): Promise<void> {
        const confirm = await vscode.window.showWarningMessage(
            `Delete draft "${item.item.label}"? This cannot be undone.`,
            'Delete', 'Cancel',
        );
        if (confirm !== 'Delete') { return; }

        try {
            await fetch(
                `${this._apiBase}/api/v1/sessions/drafts/${item.item.id}`,
                { method: 'DELETE', headers: this._getHeaders() },
            );
            vscode.window.showInformationMessage('Draft deleted');
            this.refresh();
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            vscode.window.showErrorMessage(`Delete failed: ${msg}`);
        }
    }
}

export function registerRecoveryView(context: vscode.ExtensionContext): RecoveryViewProvider {
    const provider = new RecoveryViewProvider(context);

    const treeView = vscode.window.createTreeView('aegion.recoveryView', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });

    context.subscriptions.push(
        treeView,
        vscode.commands.registerCommand('aegion.recovery.refresh', () => provider.refresh()),
        vscode.commands.registerCommand('aegion.recovery.restoreDraft', (item: RecoveryTreeItem) => provider.restoreDraft(item)),
        vscode.commands.registerCommand('aegion.recovery.recoverSession', (item: RecoveryTreeItem) => provider.recoverSession(item)),
        vscode.commands.registerCommand('aegion.recovery.deleteDraft', (item: RecoveryTreeItem) => provider.deleteDraft(item)),
    );

    // Auto-refresh on activation
    provider.refresh();

    return provider;
}
