/**
 * Timeline Tree View — Phase 53: Chronos events grouped by day
 *
 * Recent timeline events as a tree (grouped by day)
 * Event type icons, click to open detail
 */

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

type TimelineItemType = 'day' | 'event' | 'info';

interface TimelineTreeItem {
    type: TimelineItemType;
    label: string;
    id?: string;
    eventType?: string;
    metadata?: unknown;
}

interface TimelineEvent {
    id: string;
    event_type: string;
    entity_type: string;
    entity_id: string;
    actor: string;
    payload: Record<string, unknown>;
    timestamp: string;
}

export class TimelineTreeProvider implements vscode.TreeDataProvider<TimelineTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<TimelineTreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private workspaceId: string | null = null;
    private events: TimelineEvent[] = [];
    private refreshInterval: ReturnType<typeof setInterval> | null = null;

    constructor(private context: vscode.ExtensionContext) {
        this.startAutoRefresh();
    }

    setWorkspace(workspaceId: string): void {
        this.workspaceId = workspaceId;
        this.refresh();
    }

    refresh(): void {
        this.fetchEvents();
    }

    private startAutoRefresh(): void {
        this.refreshInterval = setInterval(() => {
            if (this.workspaceId) {
                this.fetchEvents();
            }
        }, 45000);
    }

    private async fetchEvents(): Promise<void> {
        if (!this.workspaceId) { return; }

        try {
            const api = getApiClient();
            const result = await api.getTimeline?.(this.workspaceId) || { events: [] };
            this.events = Array.isArray((result as any).events) ? (result as any).events : [];
            this._onDidChangeTreeData.fire();
        } catch {
            if (this.events.length === 0) {
                this.events = [];
            }
            this._onDidChangeTreeData.fire();
        }
    }

    getTreeItem(element: TimelineTreeItem): vscode.TreeItem {
        const item = new vscode.TreeItem(
            element.label,
            element.type === 'day'
                ? vscode.TreeItemCollapsibleState.Expanded
                : vscode.TreeItemCollapsibleState.None,
        );

        const eventIcons: Record<string, string> = {
            decision_created: 'gavel',
            proposal_approved: 'pass-filled',
            proposal_rejected: 'error',
            session_started: 'play',
            session_closed: 'primitive-square',
            risk_detected: 'warning',
            deployment_completed: 'rocket',
            error: 'bug',
        };

        if (element.type === 'day') {
            item.iconPath = new vscode.ThemeIcon('calendar');
        } else if (element.type === 'event') {
            const icon = eventIcons[element.eventType || ''] || 'circle-outline';
            item.iconPath = new vscode.ThemeIcon(icon);
            item.description = element.eventType;
        } else {
            item.iconPath = new vscode.ThemeIcon('info');
        }

        item.contextValue = element.type;
        return item;
    }

    async getChildren(element?: TimelineTreeItem): Promise<TimelineTreeItem[]> {
        if (!this.workspaceId) {
            return [{ type: 'info', label: 'No workspace selected' }];
        }

        if (!element) {
            if (this.events.length === 0) {
                await this.fetchEvents();
            }
            if (this.events.length === 0) {
                return [{ type: 'info', label: 'No timeline events' }];
            }

            // Group events by day
            const dayGroups = new Map<string, TimelineEvent[]>();
            for (const event of this.events) {
                const day = (event.timestamp || '').slice(0, 10);
                if (!dayGroups.has(day)) {
                    dayGroups.set(day, []);
                }
                dayGroups.get(day)!.push(event);
            }

            return Array.from(dayGroups.entries()).map(([day, events]) => ({
                type: 'day' as TimelineItemType,
                label: `📅 ${day} (${events.length} events)`,
                id: day,
                metadata: events,
            }));
        }

        if (element.type === 'day' && element.metadata) {
            const events = element.metadata as TimelineEvent[];
            return events.map(e => ({
                type: 'event' as TimelineItemType,
                label: `${e.entity_type}: ${e.entity_id?.slice(0, 8) || 'unknown'}`,
                id: e.id,
                eventType: e.event_type,
                metadata: e,
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

export function registerTimelineTree(context: vscode.ExtensionContext): TimelineTreeProvider {
    const provider = new TimelineTreeProvider(context);
    const treeView = vscode.window.createTreeView('aegion.views.timeline', {
        treeDataProvider: provider,
        showCollapseAll: true,
    });
    context.subscriptions.push(
        treeView,
        vscode.commands.registerCommand('aegion.timeline.refresh', () => provider.refresh()),
    );
    return provider;
}
