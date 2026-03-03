/**
 * Risk Tree View — Phase 53: Active risk signals from Sentinel
 *
 * Grouped by severity: critical → high → medium → low
 * Click to expand risk detail + remediation
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

type RiskItemType = 'severity_group' | 'risk' | 'remediation' | 'info';

interface RiskTreeItem {
    type: RiskItemType;
    label: string;
    severity?: string;
    metadata?: unknown;
}

interface RiskSignal {
    id: string;
    severity: string;
    description: string;
    source: string;
    resolved: boolean;
    remediation?: string;
    created_at: string;
}

export class RiskTreeProvider implements vscode.TreeDataProvider<RiskTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<RiskTreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private workspaceId: string | null = null;
    private risks: RiskSignal[] = [];
    private refreshInterval: ReturnType<typeof setInterval> | null = null;

    constructor(private context: vscode.ExtensionContext) {
        this.startAutoRefresh();
    }

    setWorkspace(workspaceId: string): void {
        this.workspaceId = workspaceId;
        this.refresh();
    }

    refresh(): void {
        this.fetchRisks();
    }

    private startAutoRefresh(): void {
        this.refreshInterval = setInterval(() => {
            if (this.workspaceId) {
                this.fetchRisks();
            }
        }, 20000);  // Risks should update frequently
    }

    private async fetchRisks(): Promise<void> {
        if (!this.workspaceId) { return; }

        try {
            const api = getApiClient();
            const alerts = await api.getSentinelAlerts?.() || [];
            this.risks = (Array.isArray(alerts) ? alerts : []).map((a: any) => ({
                id: (a.id as string) || '',
                severity: (a.severity as string) || 'medium',
                description: (a.message as string) || (a.description as string) || 'Unknown risk',
                source: (a.source as string) || (a.type as string) || 'sentinel',
                resolved: (a.resolved as boolean) || false,
                remediation: (a.remediation as string) || undefined,
                created_at: (a.created_at as string) || '',
            }));
            this._onDidChangeTreeData.fire();
        } catch {
            this._onDidChangeTreeData.fire();
        }
    }

    getTreeItem(element: RiskTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            element.label,
            element.type === 'severity_group'
                ? vscode.TreeItemCollapsibleState.Expanded
                : element.type === 'risk'
                    ? vscode.TreeItemCollapsibleState.Collapsed
                    : vscode.TreeItemCollapsibleState.None,
        );

        const severityIcons: Record<string, string> = {
            critical: 'error',
            high: 'warning',
            medium: 'info',
            low: 'circle-outline',
        };

        if (element.type === 'severity_group') {
            const icon = severityIcons[element.severity || ''] || 'shield';
            item.iconPath = new vscode.ThemeIcon(icon);
        } else if (element.type === 'risk') {
            item.iconPath = new vscode.ThemeIcon('alert');
        } else if (element.type === 'remediation') {
            item.iconPath = new vscode.ThemeIcon('lightbulb');
        } else {
            item.iconPath = new vscode.ThemeIcon('info');
        }

        item.contextValue = element.type;
        return item;
    }

    async getChildren(element?: RiskTreeItem): Promise<RiskTreeItem[]> {
        if (!this.workspaceId) {
            return [{ type: 'info', label: 'No workspace selected' }];
        }

        // Root: severity groups
        if (!element) {
            if (this.risks.length === 0) {
                await this.fetchRisks();
            }

            const unresolvedRisks = this.risks.filter(r => !r.resolved);
            if (unresolvedRisks.length === 0) {
                return [{ type: 'info', label: '✅ No active risks' }];
            }

            const groups = new Map<string, RiskSignal[]>();
            const order = ['critical', 'high', 'medium', 'low'];
            for (const risk of unresolvedRisks) {
                const sev = risk.severity || 'medium';
                if (!groups.has(sev)) {
                    groups.set(sev, []);
                }
                groups.get(sev)!.push(risk);
            }

            return order
                .filter(sev => groups.has(sev))
                .map(sev => ({
                    type: 'severity_group' as RiskItemType,
                    label: `${sev.toUpperCase()} (${groups.get(sev)!.length})`,
                    severity: sev,
                    metadata: groups.get(sev),
                }));
        }

        // Severity group → individual risks
        if (element.type === 'severity_group' && element.metadata) {
            const risks = element.metadata as RiskSignal[];
            return risks.map(r => ({
                type: 'risk' as RiskItemType,
                label: r.description.slice(0, 80),
                severity: r.severity,
                metadata: r,
            }));
        }

        // Risk detail → remediation
        if (element.type === 'risk' && element.metadata) {
            const risk = element.metadata as RiskSignal;
            const children: RiskTreeItem[] = [
                { type: 'info', label: `Source: ${risk.source}` },
                { type: 'info', label: `Created: ${risk.created_at?.slice(0, 16) || 'unknown'}` },
            ];
            if (risk.remediation) {
                children.push({
                    type: 'remediation',
                    label: `💡 ${risk.remediation}`,
                });
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

export function registerRiskTree(context: vscode.ExtensionContext): RiskTreeProvider {
    const provider = new RiskTreeProvider(context);
    const treeView = vscode.window.createTreeView('aegion.views.risks', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });
    context.subscriptions.push(
        treeView,
        vscode.commands.registerCommand('aegion.risks.refresh', () => provider.refresh()),
    );
    return provider;
}
