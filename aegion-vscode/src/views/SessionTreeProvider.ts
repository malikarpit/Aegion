/**
 * Session Tree View — Phase 53: Active sessions with checkpoints
 *
 * Expandable: session → artifacts → individual items
 * Auto-refresh with click to open session details
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

type SessionItemType = 'session' | 'checkpoint' | 'artifact' | 'info' | 'loading';

interface SessionTreeItem {
    type: SessionItemType;
    label: string;
    id?: string;
    status?: string;
    metadata?: unknown;
}

interface SessionData {
    id: string;
    status: string;
    decision_count: number;
    evidence_count: number;
    created_at: string;
    checkpoints?: Array<{ id: string; label: string; timestamp: string }>;
}

export class SessionTreeProvider implements vscode.TreeDataProvider<SessionTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<SessionTreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private sessions: SessionData[] = [];
    private refreshInterval: ReturnType<typeof setInterval> | null = null;

    constructor(private context: vscode.ExtensionContext) {
        this.startAutoRefresh();
    }

    refresh(): void {
        this.fetchSessions();
        this._onDidChangeTreeData.fire();
    }

    private startAutoRefresh(): void {
        this.refreshInterval = setInterval(() => this.fetchSessions(), 30000);
    }

    private async fetchSessions(): Promise<void> {
        try {
            const api = getApiClient();
            const data = await api.getActiveSessions?.() || [];
            this.sessions = Array.isArray(data) ? data.map((s: any) => ({
                id: (s.session_id as string) || (s.id as string) || '',
                status: (s.status as string) || 'unknown',
                decision_count: (s.decision_count as number) || 0,
                evidence_count: (s.evidence_count as number) || 0,
                created_at: (s.created_at as string) || '',
            })) : [];
            this._onDidChangeTreeData.fire();
        } catch {
            if (this.sessions.length === 0) {
                this.sessions = [];
            }
        }
    }

    getTreeItem(element: SessionTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            element.label,
            element.type === 'session'
                ? vscode.TreeItemCollapsibleState.Collapsed
                : vscode.TreeItemCollapsibleState.None,
        );

        const icons: Record<string, string> = {
            session: 'symbol-event',
            checkpoint: 'history',
            artifact: 'file-text',
            info: 'info',
            loading: 'loading~spin',
        };

        item.iconPath = new vscode.ThemeIcon(icons[element.type] || 'circle-outline');
        item.contextValue = element.type;

        if (element.type === 'session' && element.status) {
            item.description = element.status;
        }

        return item;
    }

    async getChildren(element?: SessionTreeItem): Promise<SessionTreeItem[]> {
        if (!element) {
            if (this.sessions.length === 0) {
                await this.fetchSessions();
            }
            if (this.sessions.length === 0) {
                return [{ type: 'info', label: 'No active sessions' }];
            }
            return this.sessions.map(s => ({
                type: 'session' as SessionItemType,
                label: `Session ${s.id.slice(0, 8)}...`,
                id: s.id,
                status: s.status,
                metadata: s,
            }));
        }

        if (element.type === 'session' && element.metadata) {
            const s = element.metadata as SessionData;
            const children: SessionTreeItem[] = [
                { type: 'info', label: `Decisions: ${s.decision_count}` },
                { type: 'info', label: `Evidence: ${s.evidence_count}` },
                { type: 'info', label: `Created: ${s.created_at?.slice(0, 10) || 'unknown'}` },
            ];

            if (s.checkpoints) {
                for (const cp of s.checkpoints) {
                    children.push({
                        type: 'checkpoint',
                        label: cp.label || `Checkpoint ${cp.id.slice(0, 8)}`,
                        id: cp.id,
                    });
                }
            }

            return children;
        }

        return [];
    }

    dispose(): void {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

export function registerSessionTree(context: vscode.ExtensionContext): SessionTreeProvider {
    const provider = new SessionTreeProvider(context);
    const treeView = vscode.window.createTreeView('aegion.views.sessions', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });
    context.subscriptions.push(
        treeView,
        vscode.commands.registerCommand('aegion.sessions.refresh', () => provider.refresh()),
    );
    return provider;
}
