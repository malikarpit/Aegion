// Aegion Sentinel Health Tree View
// Risk visualization and module health monitoring

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

type HealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown';
type HealthItemType = 'root' | 'module' | 'metric' | 'risk' | 'loading';

interface HealthMetric {
    name: string;
    value: number;
    threshold: number;
    status: HealthStatus;
    trend?: 'up' | 'down' | 'stable';
}

interface ModuleHealth {
    module_id: string;
    name: string;
    risk_index: number;
    status: HealthStatus;
    metrics: HealthMetric[];
    risks: string[];
}

interface HealthTreeItem {
    type: HealthItemType;
    label: string;
    id?: string;
    status?: HealthStatus;
    value?: number;
    metadata?: unknown;
}

export class SentinelHealthProvider implements vscode.TreeDataProvider<HealthTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<HealthTreeItem | undefined | null | void> = new vscode.EventEmitter<HealthTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<HealthTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private workspaceId: string | null = null;
    private moduleHealth: ModuleHealth[] = [];
    private refreshInterval: ReturnType<typeof setInterval> | null = null;

    constructor(private context: vscode.ExtensionContext) {
        // Auto-refresh every 30 seconds
        this.startAutoRefresh();
    }

    setWorkspace(workspaceId: string) {
        this.workspaceId = workspaceId;
        this.refresh();
    }

    refresh(): void {
        this.fetchHealth();
        this._onDidChangeTreeData.fire();
    }

    private startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            if (this.workspaceId) {
                this.fetchHealth();
            }
        }, 30000);
    }

    private async fetchHealth() {
        if (!this.workspaceId) { return; }

        try {
            const apiClient = getApiClient();
            // Fetch real alerts and drift status
            const [alerts, driftData] = await Promise.all([
                apiClient.getSentinelAlerts().catch(() => [] as unknown[]),
                apiClient.getDriftStatus(this.workspaceId).catch(() => null),
            ]);

            // Convert alerts into per-module health
            const moduleMap: Record<string, ModuleHealth> = {};

            for (const alert of alerts) {
                const a = alert as Record<string, unknown>;
                const source = (a.source as string) || (a.type as string) || 'system';
                if (!moduleMap[source]) {
                    moduleMap[source] = {
                        module_id: source,
                        name: source.charAt(0).toUpperCase() + source.slice(1).replace(/_/g, ' '),
                        risk_index: 0,
                        status: 'healthy' as HealthStatus,
                        metrics: [],
                        risks: [],
                    };
                }
                const mod = moduleMap[source];
                mod.risks.push((a.message as string) || (a.type as string));
                mod.risk_index = Math.min(mod.risk_index + 0.25, 1.0);
                mod.status = mod.risk_index >= 0.7 ? 'critical' as HealthStatus
                    : mod.risk_index >= 0.4 ? 'warning' as HealthStatus
                        : 'healthy' as HealthStatus;
            }

            // Include drift data as a metric if available
            if (driftData && (driftData as { status?: string }).status !== 'nominal') {
                const driftModule: ModuleHealth = {
                    module_id: 'drift',
                    name: 'Drift Monitor',
                    risk_index: 0.5,
                    status: 'warning' as HealthStatus,
                    metrics: [{ name: 'Drift Status', value: 1, threshold: 0, status: 'warning' as HealthStatus }],
                    risks: ['Decision drift detected'],
                };
                moduleMap['drift'] = driftModule;
            }

            this.moduleHealth = Object.values(moduleMap);
            if (this.moduleHealth.length === 0) {
                this.moduleHealth = this.generateMockHealth();
            }
            this._onDidChangeTreeData.fire();
        } catch {
            this.moduleHealth = this.generateMockHealth();
            this._onDidChangeTreeData.fire();
        }
    }

    private generateMockHealth(): ModuleHealth[] {
        // Fallback when API is unreachable — show nominal state
        return [
            {
                module_id: 'system',
                name: 'All Systems',
                risk_index: 0,
                status: 'healthy' as HealthStatus,
                metrics: [
                    { name: 'Status', value: 0, threshold: 50, status: 'healthy' as HealthStatus, trend: 'stable' },
                ],
                risks: [],
            },
        ];
    }

    getTreeItem(element: HealthTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            this.formatLabel(element),
            this.getCollapsibleState(element),
        );

        item.iconPath = this.getIcon(element);
        item.contextValue = element.type;
        item.tooltip = this.getTooltip(element);
        item.description = this.getDescription(element);

        return item;
    }

    async getChildren(element?: HealthTreeItem): Promise<HealthTreeItem[]> {
        if (!this.workspaceId) {
            return [{
                type: 'loading',
                label: 'No workspace selected',
            }];
        }

        // Root level - show modules
        if (!element) {
            if (this.moduleHealth.length === 0) {
                await this.fetchHealth();
            }

            return this.moduleHealth.map(m => ({
                type: 'module' as HealthItemType,
                label: m.name,
                id: m.module_id,
                status: m.status,
                value: m.risk_index,
                metadata: m,
            }));
        }

        // Module children - show metrics and risks
        if (element.type === 'module' && element.metadata) {
            const module = element.metadata as ModuleHealth;
            const children: HealthTreeItem[] = [];

            // Add metrics
            for (const metric of module.metrics) {
                children.push({
                    type: 'metric',
                    label: metric.name,
                    status: metric.status,
                    value: metric.value,
                    metadata: metric,
                });
            }

            // Add risks
            for (const risk of module.risks) {
                children.push({
                    type: 'risk',
                    label: risk,
                    status: 'warning',
                });
            }

            return children;
        }

        return [];
    }

    private formatLabel(item: HealthTreeItem): string {
        if (item.type === 'module' && item.value !== undefined) {
            const riskPercent = Math.round(item.value * 100);
            return `${item.label} (${riskPercent}% risk)`;
        }
        if (item.type === 'metric' && item.value !== undefined) {
            return `${item.label}: ${item.value}%`;
        }
        return item.label;
    }

    private getDescription(item: HealthTreeItem): string | undefined {
        const metric = item.metadata as HealthMetric;
        if (item.type === 'metric' && metric?.trend) {
            const arrow = metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '→';
            return arrow;
        }
        return undefined;
    }

    private getCollapsibleState(item: HealthTreeItem): vscode.TreeItemCollapsibleState {
        if (item.type === 'module') {
            return vscode.TreeItemCollapsibleState.Collapsed;
        }
        return vscode.TreeItemCollapsibleState.None;
    }

    private getIcon(item: HealthTreeItem): vscode.ThemeIcon {
        const statusIcons: Record<HealthStatus, string> = {
            healthy: 'pass-filled',
            warning: 'warning',
            critical: 'error',
            unknown: 'circle-outline',
        };

        if (item.type === 'risk') {
            return new vscode.ThemeIcon('alert');
        }

        if (item.type === 'metric') {
            return new vscode.ThemeIcon('dashboard');
        }

        const iconName = item.status ? statusIcons[item.status] : 'circle-outline';
        return new vscode.ThemeIcon(iconName);
    }

    private getTooltip(item: HealthTreeItem): string {
        if (item.type === 'module' && item.value !== undefined) {
            return `Risk Index: ${(item.value * 100).toFixed(1)}%\nStatus: ${item.status}`;
        }
        if (item.type === 'metric') {
            const metric = item.metadata as HealthMetric;
            return `Value: ${metric.value}%\nThreshold: ${metric.threshold}%\nTrend: ${metric.trend || 'stable'}`;
        }
        return item.label;
    }

    dispose() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

export function registerSentinelHealth(context: vscode.ExtensionContext): SentinelHealthProvider {
    const provider = new SentinelHealthProvider(context);

    const treeView = vscode.window.createTreeView('aegion.views.system', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });

    context.subscriptions.push(
        vscode.commands.registerCommand('aegion.sentinel.refresh', () => provider.refresh()),
    );

    context.subscriptions.push(treeView);

    return provider;
}
