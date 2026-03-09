// Aegion Chronos Explorer Tree View
// Timeline visualization of session history, decisions, and artifacts

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

// Tree item types
type ChronosItemType = 'sessions' | 'session' | 'decisions' | 'decision' | 'artifacts' | 'artifact' | 'loading';

interface ChronosTreeItem {
    type: ChronosItemType;
    label: string;
    id?: string;
    timestamp?: string;
    metadata?: Record<string, unknown>;
    children?: ChronosTreeItem[];
}

export class ChronosExplorerProvider implements vscode.TreeDataProvider<ChronosTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ChronosTreeItem | undefined | null | void> = new vscode.EventEmitter<ChronosTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ChronosTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private workspaceId: string | null = null;
    private cache: Map<string, ChronosTreeItem[]> = new Map();

    constructor(private context: vscode.ExtensionContext) { }

    setWorkspace(workspaceId: string) {
        this.workspaceId = workspaceId;
        this.cache.clear();
        this.refresh();
    }

    refresh(): void {
        this.cache.clear();
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: ChronosTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            element.label,
            this.getCollapsibleState(element),
        );

        // Set icon based on type
        item.iconPath = this.getIcon(element.type);
        item.contextValue = element.type;
        item.tooltip = this.getTooltip(element);

        // Set command for leaf items
        if (element.type === 'decision' || element.type === 'artifact') {
            item.command = {
                command: 'aegion.chronos.openItem',
                title: 'Open',
                arguments: [element],
            };
        }

        return item;
    }

    async getChildren(element?: ChronosTreeItem): Promise<ChronosTreeItem[]> {
        if (!this.workspaceId) {
            return [{
                type: 'loading',
                label: 'No workspace selected',
            }];
        }

        // Root level - show categories
        if (!element) {
            return [
                { type: 'sessions', label: 'Sessions' },
                { type: 'decisions', label: 'Decisions' },
                { type: 'artifacts', label: 'Artifacts' },
            ];
        }

        // Fetch children based on type
        try {
            // const api = getApiClient(); // This line was already commented out, removing it.

            switch (element.type) {
                case 'sessions':
                    return await this.fetchSessions();
                case 'decisions':
                    return await this.fetchDecisions();
                case 'artifacts':
                    return await this.fetchArtifacts();
                case 'session':
                    if (!element.id) { return []; }
                    return await this.fetchSessionChildren(element.id);
                default:
                    return [];
            }
        } catch (error) {
            console.error('Failed to fetch Chronos data:', error);
            return [{
                type: 'loading',
                label: 'Error loading data',
            }];
        }
    }

    private async fetchSessions(): Promise<ChronosTreeItem[]> {
        if (!this.workspaceId) { return []; }
        const api = getApiClient();
        try {
            // Use workspace activity endpoint to get sessions
            const activity = await api.workspaces.getActivity(this.workspaceId, 50);
            const sessionEvents = (activity as Array<{ event_type?: string; session_id?: string; payload?: { session_id?: string; }; timestamp?: string; }>).filter(e =>
                e.event_type?.includes('session'),
            );

            const sessions = new Map<string, { event_type?: string; session_id?: string; payload?: { session_id?: string; }; timestamp?: string; }>();
            for (const event of sessionEvents) {
                const sessionId = event.session_id || event.payload?.session_id;
                if (sessionId && !sessions.has(sessionId)) {
                    sessions.set(sessionId, event);
                }
            }

            return Array.from(sessions.entries()).map(([id, event]) => ({
                type: 'session' as ChronosItemType,
                label: `Session ${id.slice(0, 8)}...`,
                id,
                timestamp: event.timestamp,
            }));
        } catch {
            return [{ type: 'loading', label: 'No sessions found' }];
        }
    }

    private async fetchDecisions(): Promise<ChronosTreeItem[]> {
        const api = getApiClient();
        try {
            const results = await api.queryMemory('decisions');
            return results.results.slice(0, 20).map((d) => {
                const meta = (d.metadata as Record<string, unknown>) || {};
                return {
                    type: 'decision' as ChronosItemType,
                    label: (meta.title as string) || `Decision ${d.id.slice(0, 8)}`,
                    id: d.id,
                    timestamp: undefined, // timestamp not on root result
                    metadata: meta,
                };
            });
        } catch {
            return [{ type: 'loading', label: 'No decisions found' }];
        }
    }

    private async fetchArtifacts(): Promise<ChronosTreeItem[]> {
        const api = getApiClient();
        try {
            const results = await api.queryMemory('artifacts');
            return results.results.slice(0, 20).map((a) => {
                const meta = (a.metadata as Record<string, unknown>) || {};
                return {
                    type: 'artifact' as ChronosItemType,
                    label: (meta.name as string) || a.id.slice(0, 8),
                    id: a.id,
                    timestamp: undefined, // timestamp not on root result
                    metadata: meta,
                };
            });
        } catch {
            return [{ type: 'loading', label: 'No artifacts found' }];
        }
    }

    private async fetchSessionChildren(sessionId: string): Promise<ChronosTreeItem[]> {
        const api = getApiClient();
        try {
            const proposals = await api.listProposals(sessionId);
            return proposals.map(p => ({
                type: 'decision' as ChronosItemType,
                label: p.title || `Proposal ${p.proposal_id.slice(0, 8)}`,
                id: p.proposal_id,
                // timestamp: p.created_at, // Not available in ProposalResponse
                metadata: p as unknown as Record<string, unknown>,
            }));
        } catch {
            return [{ type: 'loading', label: 'No data found' }];
        }
    }

    private getCollapsibleState(item: ChronosTreeItem): vscode.TreeItemCollapsibleState {
        switch (item.type) {
            case 'sessions':
            case 'decisions':
            case 'artifacts':
            case 'session':
                return vscode.TreeItemCollapsibleState.Collapsed;
            default:
                return vscode.TreeItemCollapsibleState.None;
        }
    }

    private getIcon(type: ChronosItemType): vscode.ThemeIcon {
        switch (type) {
            case 'sessions':
                return new vscode.ThemeIcon('history');
            case 'session':
                return new vscode.ThemeIcon('folder');
            case 'decisions':
                return new vscode.ThemeIcon('law');
            case 'decision':
                return new vscode.ThemeIcon('check');
            case 'artifacts':
                return new vscode.ThemeIcon('package');
            case 'artifact':
                return new vscode.ThemeIcon('file-code');
            default:
                return new vscode.ThemeIcon('circle-outline');
        }
    }

    private getTooltip(item: ChronosTreeItem): string {
        let tooltip = item.label;
        if (item.timestamp) {
            tooltip += `\nCreated: ${new Date(item.timestamp).toLocaleString()}`;
        }
        if (item.id) {
            tooltip += `\nID: ${item.id}`;
        }
        return tooltip;
    }
}

export function registerChronosExplorer(context: vscode.ExtensionContext): ChronosExplorerProvider {
    const provider = new ChronosExplorerProvider(context);

    // Register tree view
    const treeView = vscode.window.createTreeView('aegion.views.governance', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('aegion.chronos.refresh', () => provider.refresh()),
        vscode.commands.registerCommand('aegion.chronos.openItem', async (item: ChronosTreeItem) => {
            if (item.metadata) {
                const doc = await vscode.workspace.openTextDocument({
                    content: JSON.stringify(item.metadata, null, 2),
                    language: 'json',
                });
                await vscode.window.showTextDocument(doc);
            }
        }),
    );

    context.subscriptions.push(treeView);

    return provider;
}
