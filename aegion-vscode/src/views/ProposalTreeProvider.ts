/**
 * Proposal Tree View — Phase 53: Pending proposals with inline actions
 *
 * Status icons (⏳ pending, ✅ approved, ❌ rejected)
 * Context menu: approve, reject, view in Archon
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

type ProposalItemType = 'proposal' | 'detail' | 'info';

interface ProposalTreeItem {
    type: ProposalItemType;
    label: string;
    id?: string;
    status?: string;
    tier?: string;
    metadata?: unknown;
}

interface ProposalData {
    proposal_id: string;
    title: string;
    tier: string;
    status: string;
    impact_level: string;
    created_at: string;
    description?: string;
}

export class ProposalTreeProvider implements vscode.TreeDataProvider<ProposalTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<ProposalTreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private workspaceId: string | null = null;
    private proposals: ProposalData[] = [];
    private refreshInterval: ReturnType<typeof setInterval> | null = null;

    constructor(private context: vscode.ExtensionContext) {
        this.startAutoRefresh();
    }

    setWorkspace(workspaceId: string): void {
        this.workspaceId = workspaceId;
        this.refresh();
    }

    refresh(): void {
        this.fetchProposals();
    }

    private startAutoRefresh(): void {
        this.refreshInterval = setInterval(() => {
            if (this.workspaceId) {
                this.fetchProposals();
            }
        }, 15000);  // Proposals are time-sensitive
    }

    private async fetchProposals(): Promise<void> {
        if (!this.workspaceId) { return; }

        try {
            const api = getApiClient();
            const result = await api.listPendingProposals?.() || [];
            this.proposals = Array.isArray(result) ? result as unknown as ProposalData[] : [];
            this._onDidChangeTreeData.fire();
        } catch {
            this._onDidChangeTreeData.fire();
        }
    }

    getTreeItem(element: ProposalTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            element.label,
            element.type === 'proposal'
                ? vscode.TreeItemCollapsibleState.Collapsed
                : vscode.TreeItemCollapsibleState.None,
        );

        if (element.type === 'proposal') {
            const statusIcons: Record<string, string> = {
                pending: 'clock',
                approved: 'pass-filled',
                rejected: 'error',
                superseded: 'history',
            };
            const tierColors: Record<string, string> = {
                T0: '🟢',
                T1: '🟡',
                T2: '🟠',
                T3: '🔴',
            };

            item.iconPath = new vscode.ThemeIcon(statusIcons[element.status || ''] || 'question');
            item.description = `${tierColors[element.tier || ''] || ''} ${element.tier || ''} · ${element.status || ''}`;
            item.contextValue = `proposal_${element.status}`;
        } else {
            item.iconPath = new vscode.ThemeIcon('list-flat');
        }

        return item;
    }

    async getChildren(element?: ProposalTreeItem): Promise<ProposalTreeItem[]> {
        if (!this.workspaceId) {
            return [{ type: 'info', label: 'No workspace selected' }];
        }

        if (!element) {
            if (this.proposals.length === 0) {
                await this.fetchProposals();
            }
            if (this.proposals.length === 0) {
                return [{ type: 'info', label: 'No proposals found' }];
            }

            // Sort: pending first, then by date
            const sorted = [...this.proposals].sort((a, b) => {
                if (a.status === 'pending' && b.status !== 'pending') { return -1; }
                if (a.status !== 'pending' && b.status === 'pending') { return 1; }
                return (b.created_at || '').localeCompare(a.created_at || '');
            });

            return sorted.map(p => ({
                type: 'proposal' as ProposalItemType,
                label: p.title || `Proposal ${p.proposal_id.slice(0, 8)}`,
                id: p.proposal_id,
                status: p.status,
                tier: p.tier,
                metadata: p,
            }));
        }

        if (element.type === 'proposal' && element.metadata) {
            const p = element.metadata as ProposalData;
            return [
                { type: 'detail', label: `Impact: ${p.impact_level}` },
                { type: 'detail', label: `Created: ${p.created_at?.slice(0, 10) || 'unknown'}` },
                ...(p.description ? [{ type: 'detail' as ProposalItemType, label: `${p.description.slice(0, 80)}...` }] : []),
            ];
        }

        return [];
    }

    dispose(): void {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

export function registerProposalTree(context: vscode.ExtensionContext): ProposalTreeProvider {
    const provider = new ProposalTreeProvider(context);
    const treeView = vscode.window.createTreeView('aegion.views.proposals', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });
    context.subscriptions.push(
        treeView,
        vscode.commands.registerCommand('aegion.proposals.refresh', () => provider.refresh()),
        vscode.commands.registerCommand('aegion.proposals.approve', async (item: ProposalTreeItem) => {
            if (item?.id) {
                vscode.commands.executeCommand('aegion.approveProposal');
            }
        }),
        vscode.commands.registerCommand('aegion.proposals.reject', async (item: ProposalTreeItem) => {
            if (item?.id) {
                vscode.commands.executeCommand('aegion.rejectDecision');
            }
        }),
    );
    return provider;
}
