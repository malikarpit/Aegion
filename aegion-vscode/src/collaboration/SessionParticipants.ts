// Aegion Session Participants
// UI component showing current session participants

import * as vscode from 'vscode';
import { LiveShareIntegration, CollaborationSession } from './LiveShareIntegration';

interface Participant {
    userId: string;
    displayName: string;
    role: 'owner' | 'collaborator' | 'viewer';
    isOnline: boolean;
    lastSeen?: Date;
}

export class SessionParticipants implements vscode.TreeDataProvider<Participant> {
    private _onDidChangeTreeData: vscode.EventEmitter<Participant | undefined | null | void> = new vscode.EventEmitter<Participant | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<Participant | undefined | null | void> = this._onDidChangeTreeData.event;

    private participants: Participant[] = [];
    private liveShare: LiveShareIntegration;

    constructor() {
        this.liveShare = LiveShareIntegration.getInstance();

        // Listen for session changes
        this.liveShare.onSessionChanged(session => {
            if (session) {
                this.updateFromSession(session);
            } else {
                this.participants = [];
            }
            this.refresh();
        });
    }

    private updateFromSession(session: CollaborationSession): void {
        this.participants = session.participants.map(userId => ({
            userId,
            displayName: userId === session.hostId ? `${userId} (Host)` : userId,
            role: userId === session.hostId ? 'owner' : 'collaborator',
            isOnline: true,
        }));
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: Participant): vscode.TreeItem {
        const item = new vscode.TreeItem(element.displayName);

        // Set icon based on role and status
        if (!element.isOnline) {
            item.iconPath = new vscode.ThemeIcon('circle-outline');
            item.description = 'offline';
        } else if (element.role === 'owner') {
            item.iconPath = new vscode.ThemeIcon('account', new vscode.ThemeColor('charts.green'));
            item.description = '👑 owner';
        } else if (element.role === 'collaborator') {
            item.iconPath = new vscode.ThemeIcon('account', new vscode.ThemeColor('charts.blue'));
            item.description = 'editing';
        } else {
            item.iconPath = new vscode.ThemeIcon('eye');
            item.description = 'viewing';
        }

        item.tooltip = `${element.displayName}\nRole: ${element.role}\nStatus: ${element.isOnline ? 'online' : 'offline'}`;

        return item;
    }

    async getChildren(): Promise<Participant[]> {
        return this.participants;
    }

    addParticipant(userId: string, displayName: string, role: Participant['role'] = 'collaborator'): void {
        const existing = this.participants.find(p => p.userId === userId);
        if (!existing) {
            this.participants.push({
                userId,
                displayName,
                role,
                isOnline: true,
            });
            this.refresh();
        }
    }

    removeParticipant(userId: string): void {
        this.participants = this.participants.filter(p => p.userId !== userId);
        this.refresh();
    }

    setOnlineStatus(userId: string, isOnline: boolean): void {
        const participant = this.participants.find(p => p.userId === userId);
        if (participant) {
            participant.isOnline = isOnline;
            participant.lastSeen = isOnline ? undefined : new Date();
            this.refresh();
        }
    }

    getParticipantCount(): number {
        return this.participants.filter(p => p.isOnline).length;
    }
}

export function registerSessionParticipants(context: vscode.ExtensionContext): SessionParticipants {
    const provider = new SessionParticipants();

    const treeView = vscode.window.createTreeView('aegion.views.participants', {
        treeDataProvider: provider,
    });

    context.subscriptions.push(treeView);

    return provider;
}
