/**
 * Cost Tree View — Phase 53: Cost summary and breakdown
 *
 * Shows: total spend, cache hit rate, cost by model
 * Expandable: cost breakdown by date/model/council type
 */

import * as vscode from 'vscode';

type CostItemType = 'summary' | 'breakdown' | 'model_cost' | 'info';

interface CostTreeItem {
    type: CostItemType;
    label: string;
    description?: string;
    metadata?: unknown;
}

interface CostSummary {
    total_actual_cost: number;
    total_frontier_estimate: number;
    savings_percentage: number;
    cache_hit_rate: number;
    total_queries: number;
    avg_cost_per_query: number;
    daily_breakdown?: Record<string, number>;
}

export class CostTreeProvider implements vscode.TreeDataProvider<CostTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<CostTreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private workspaceId: string | null = null;
    private costData: CostSummary | null = null;
    private refreshInterval: ReturnType<typeof setInterval> | null = null;

    constructor(private context: vscode.ExtensionContext) {
        this.startAutoRefresh();
    }

    setWorkspace(workspaceId: string): void {
        this.workspaceId = workspaceId;
        this.refresh();
    }

    refresh(): void {
        this.fetchCosts();
    }

    private startAutoRefresh(): void {
        this.refreshInterval = setInterval(() => {
            if (this.workspaceId) {
                this.fetchCosts();
            }
        }, 60000);
    }

    private async fetchCosts(): Promise<void> {
        if (!this.workspaceId) { return; }

        try {
            const baseUrl = vscode.workspace.getConfiguration('aegion').get<string>('backendUrl') || 'http://localhost:8000';
            const response = await fetch(`${baseUrl}/api/v1/council/analytics/cost-efficiency/${this.workspaceId}?days=30`, {
                headers: { 'Authorization': `Bearer ${await this.getToken()}` },
            });
            if (response.ok) {
                this.costData = await response.json() as CostSummary;
            }
            this._onDidChangeTreeData.fire();
        } catch {
            this._onDidChangeTreeData.fire();
        }
    }

    private async getToken(): Promise<string> {
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const { getFirebaseAuth } = require('../auth/FirebaseAuthProvider');
            return await getFirebaseAuth().getToken() || '';
        } catch {
            return vscode.workspace.getConfiguration('aegion').get<string>('authToken') || '';
        }
    }

    getTreeItem(element: CostTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            element.label,
            element.type === 'breakdown'
                ? vscode.TreeItemCollapsibleState.Collapsed
                : vscode.TreeItemCollapsibleState.None,
        );

        const icons: Record<string, string> = {
            summary: 'credit-card',
            breakdown: 'graph-line',
            model_cost: 'server-process',
            info: 'info',
        };

        item.iconPath = new vscode.ThemeIcon(icons[element.type] || 'circle-outline');
        item.contextValue = element.type;
        if (element.description) {
            item.description = element.description;
        }

        return item;
    }

    async getChildren(element?: CostTreeItem): Promise<CostTreeItem[]> {
        if (!this.workspaceId) {
            return [{ type: 'info', label: 'No workspace selected' }];
        }

        if (!element) {
            if (!this.costData) {
                await this.fetchCosts();
            }

            if (!this.costData || this.costData.total_queries === 0) {
                return [{ type: 'info', label: 'No cost data yet' }];
            }

            const d = this.costData;
            return [
                {
                    type: 'summary',
                    label: `💰 Total: $${d.total_actual_cost.toFixed(4)}`,
                    description: `${d.total_queries} queries`,
                },
                {
                    type: 'summary',
                    label: `📊 Savings: ${d.savings_percentage.toFixed(1)}%`,
                    description: `vs $${d.total_frontier_estimate.toFixed(4)} frontier`,
                },
                {
                    type: 'summary',
                    label: `⚡ Cache Hit Rate: ${(d.cache_hit_rate * 100).toFixed(1)}%`,
                },
                {
                    type: 'summary',
                    label: `📉 Avg: $${d.avg_cost_per_query.toFixed(6)}/query`,
                },
                {
                    type: 'breakdown',
                    label: '📅 Daily Breakdown',
                    metadata: d.daily_breakdown,
                },
            ];
        }

        if (element.type === 'breakdown' && element.metadata) {
            const daily = element.metadata as Record<string, number>;
            return Object.entries(daily)
                .sort(([a], [b]) => b.localeCompare(a))
                .slice(0, 14)
                .map(([date, cost]) => ({
                    type: 'model_cost' as CostItemType,
                    label: `${date}: $${cost.toFixed(4)}`,
                }));
        }

        return [];
    }

    dispose(): void {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

export function registerCostTree(context: vscode.ExtensionContext): CostTreeProvider {
    const provider = new CostTreeProvider(context);
    const treeView = vscode.window.createTreeView('aegion.views.costs', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });
    context.subscriptions.push(
        treeView,
        vscode.commands.registerCommand('aegion.costs.refresh', () => provider.refresh()),
    );
    return provider;
}
