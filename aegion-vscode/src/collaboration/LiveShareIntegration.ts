// Aegion Live Share Integration
// Hooks into VS Code Live Share for collaborative governance

import * as vscode from 'vscode';
import { Logger } from '../services/Logger';

export interface CollaborationSession {
    sessionId: string;
    hostId: string;
    participants: string[];
    isHost: boolean;
    sharedUri?: string;
}

export class LiveShareIntegration {
    private static instance: LiveShareIntegration;
    private currentSession: CollaborationSession | null = null;
    private eventEmitter = new vscode.EventEmitter<CollaborationSession | null>();

    public readonly onSessionChanged = this.eventEmitter.event;

    private constructor() { }

    public static getInstance(): LiveShareIntegration {
        if (!LiveShareIntegration.instance) {
            LiveShareIntegration.instance = new LiveShareIntegration();
        }
        return LiveShareIntegration.instance;
    }

    public async startSession(aegionSessionId: string): Promise<CollaborationSession | null> {
        try {
            // Check if Live Share extension is available
            const liveShare = vscode.extensions.getExtension('ms-vsliveshare.vsliveshare');
            if (!liveShare) {
                vscode.window.showWarningMessage(
                    'VS Code Live Share extension is not installed. Install it for real-time collaboration.',
                );
                return null;
            }

            // Create collaboration session
            const userId = vscode.workspace.getConfiguration('aegion').get<string>('userId')
                || vscode.env.machineId;

            this.currentSession = {
                sessionId: aegionSessionId,
                hostId: userId,
                participants: [userId],
                isHost: true,
            };

            this.eventEmitter.fire(this.currentSession);
            vscode.window.showInformationMessage('Collaboration session started. Share the link to invite others.');

            return this.currentSession;
        } catch (error) {
            Logger.error('Failed to start collaboration session', error);
            return null;
        }
    }

    public async joinSession(_shareLink: string): Promise<CollaborationSession | null> {
        try {
            // ...
            return null;
        } catch (error) {
            Logger.error('Failed to join collaboration session', error);
            return null;
        }
    }

    public async endSession(): Promise<void> {
        if (this.currentSession) {
            this.currentSession = null;
            this.eventEmitter.fire(null);
            vscode.window.showInformationMessage('Collaboration session ended.');
        }
    }

    public getSession(): CollaborationSession | null {
        return this.currentSession;
    }

    public isActive(): boolean {
        return this.currentSession !== null;
    }

    public addParticipant(userId: string): void {
        if (this.currentSession) {
            this.currentSession.participants.push(userId);
            this.eventEmitter.fire(this.currentSession);
        }
    }

    public removeParticipant(userId: string): void {
        if (this.currentSession) {
            this.currentSession.participants = this.currentSession.participants.filter(
                p => p !== userId,
            );
            this.eventEmitter.fire(this.currentSession);
        }
    }
}
