// Aegion Session Manager - Client-Side Session State

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';
import { getContextEngine } from '../context';

export interface SessionState {
    sessionId: string | null;
    status: 'inactive' | 'active' | 'closing';
    workspaceId: string;
    startedAt: string | null;
    decisionCount: number;
    evidenceCount: number;
    explorationStage: 'exploration' | 'proposed' | 'governed';
}

export class SessionManager {
    private state: SessionState;
    private onStateChangeEmitter = new vscode.EventEmitter<SessionState>();

    public readonly onStateChange = this.onStateChangeEmitter.event;

    constructor(private context: vscode.ExtensionContext) {
        // Initialize state
        this.state = {
            sessionId: null,
            status: 'inactive',
            workspaceId: this.getWorkspaceId(),
            startedAt: null,
            decisionCount: 0,
            evidenceCount: 0,
            explorationStage: 'exploration',
        };
    }

    private getWorkspaceId(): string {
        const folders = vscode.workspace.workspaceFolders;
        if (folders && folders.length > 0) {
            return folders[0].uri.fsPath;
        }
        return 'default';
    }

    public getState(): SessionState {
        return { ...this.state };
    }

    public async startSession(): Promise<void> {
        if (this.state.status === 'active') {
            const choice = await vscode.window.showWarningMessage(
                'A session is already active. Close it first?',
                'Close & Start New',
                'Cancel',
            );
            if (choice !== 'Close & Start New') {
                return;
            }
            await this.closeSession(true);
        }

        try {
            const api = getApiClient();

            const response = await api.startSession({
                workspace_id: this.state.workspaceId,
                context_hash: getContextEngine()?.getSnapshot().context_hash ?? `vscode:${this.state.workspaceId}`,
            });

            this.state = {
                ...this.state,
                sessionId: response.session_id,
                status: 'active',
                startedAt: response.created_at,
                decisionCount: 0,
                evidenceCount: 0,
                explorationStage: 'exploration',
            };

            this.onStateChangeEmitter.fire(this.state);

            vscode.window.showInformationMessage(`Aegion session started: ${response.session_id.slice(0, 8)}...`);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to start session: ${error}`);
        }
    }

    public async closeSession(distill: boolean = true): Promise<void> {
        if (!this.state.sessionId) {
            return;
        }

        try {
            this.state.status = 'closing';


            const api = getApiClient();
            // closeSession only takes sessionId
            await api.closeSession(this.state.sessionId);

            const closedSessionId = this.state.sessionId;

            this.state = {
                ...this.state,
                sessionId: null,
                status: 'inactive',
                startedAt: null,
                decisionCount: 0,
                evidenceCount: 0,
            };

            this.onStateChangeEmitter.fire(this.state);

            if (distill) {
                vscode.window.showInformationMessage(
                    `Session ${closedSessionId.slice(0, 8)}... closed and distilled to artifact`,
                );
            } else {
                vscode.window.showInformationMessage(
                    `Session ${closedSessionId.slice(0, 8)}... closed`,
                );
            }
        } catch (error) {
            this.state.status = 'active';
            vscode.window.showErrorMessage(`Failed to close session: ${error}`);
        }
    }

    public setExplorationStage(stage: 'exploration' | 'proposed' | 'governed'): void {
        this.state.explorationStage = stage;
        this.onStateChangeEmitter.fire(this.state);
    }

    public incrementDecisionCount(): void {
        this.state.decisionCount++;
        this.onStateChangeEmitter.fire(this.state);
    }

    public incrementEvidenceCount(): void {
        this.state.evidenceCount++;
        this.onStateChangeEmitter.fire(this.state);
    }

    public dispose(): void {
        this.onStateChangeEmitter.dispose();
    }
}
