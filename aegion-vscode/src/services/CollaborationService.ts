import * as vscode from 'vscode';
import { Logger } from './Logger';
import { AegionClient } from '../api/client';
import { SessionOwnership, Conflict } from '../api/types';
import { AegionSocket, WebSocketMessage } from '../api/websocket';

export class CollaborationService {
    private static instance: CollaborationService;
    private client: AegionClient;
    private _currentOwnership: SessionOwnership | undefined;

    // Event emitter for UI updates
    private _onDidChangeOwnership = new vscode.EventEmitter<SessionOwnership | undefined>();
    public readonly onDidChangeOwnership = this._onDidChangeOwnership.event;

    // Event emitter for Conflicts
    private _onConflictDetected = new vscode.EventEmitter<Conflict>();
    public readonly onConflictDetected = this._onConflictDetected.event;

    private constructor(client: AegionClient) {
        this.client = client;
    }

    public static getInstance(client: AegionClient): CollaborationService {
        if (!CollaborationService.instance) {
            CollaborationService.instance = new CollaborationService(client);
        }
        return CollaborationService.instance;
    }

    public get currentOwnership(): SessionOwnership | undefined {
        return this._currentOwnership;
    }

    public async refreshOwnership(sessionId: string): Promise<void> {
        try {
            const ownership = await this.client.getSessionOwnership(sessionId);
            this._updateOwnership(ownership);
        } catch (error) {
            console.error('Failed to fetch ownership:', error);
        }
    }

    public async claimOwnership(sessionId: string, force: boolean = false): Promise<void> {
        try {
            const ownership = await this.client.claimOwnership(sessionId, force);
            this._updateOwnership(ownership);
            vscode.window.showInformationMessage('Session ownership claimed.');
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to claim ownership: ${error}`);
            throw error;
        }
    }

    public async transferOwnership(sessionId: string, targetUserId: string): Promise<void> {
        try {
            const ownership = await this.client.transferOwnership(sessionId, targetUserId);
            this._updateOwnership(ownership);
            vscode.window.showInformationMessage(`Ownership transfer initiated to ${targetUserId}.`);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to transfer ownership: ${error}`);
            throw error;
        }
    }

    public async releaseOwnership(sessionId: string): Promise<void> {
        try {
            const ownership = await this.client.releaseOwnership(sessionId);
            this._updateOwnership(ownership);
            vscode.window.showInformationMessage('Session ownership released.');
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to release ownership: ${error}`);
            throw error; // Rethrow to let caller handle if needed
        }
    }

    private _updateOwnership(ownership: SessionOwnership) {
        this._currentOwnership = ownership;
        this._onDidChangeOwnership.fire(ownership);
    }

    // ========== Real-time Collaboration ==========

    private socket: AegionSocket | undefined;

    public connect(workspaceId: string, token: string) {
        if (this.socket) {
            return;
        }

        const baseUrl = this.client.baseUrl;
        const wsUrl = baseUrl.replace(/^http/, 'ws') + '/ws/' + workspaceId;

        Logger.info(`[CollaborationService] Connecting to ${wsUrl}`);
        this.socket = new AegionSocket(wsUrl, token);

        this.socket.on('open', () => {
            Logger.info('[CollaborationService] WebSocket connected');
            vscode.window.setStatusBarMessage('$(plug) Aegion: Connected', 3000);
        });

        this.socket.on('message', (msg: WebSocketMessage) => {
            this._handleMessage(msg);
        });

        this.socket.on('close', (code, reason) => {
            Logger.info(`[CollaborationService] WebSocket closed: ${code} ${reason}`);
            vscode.window.setStatusBarMessage('$(plug) Aegion: Disconnected', 3000);
        });

        this.socket.on('error', (err) => {
            Logger.error('[CollaborationService] WebSocket error', err);
        });

        this.socket.connect();
    }

    public disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = undefined;
        }
    }

    public joinSession(sessionId: string) {
        if (this.socket) {
            this.socket.send({
                type: 'join_session',
                session_id: sessionId,
            });
        }
    }

    public sendCursorUpdate(file: string, position: { line: number; character: number; }) {
        if (this.socket) {
            this.socket.send({
                type: 'cursor_update',
                file,
                position,
            });
        }
    }

    private _handleMessage(msg: WebSocketMessage) {
        switch (msg.type) {
            case 'participant.joined':
                vscode.window.showInformationMessage(`User ${msg.user_id} joined the session.`);
                break;
            case 'participant.left':
                vscode.window.showInformationMessage(`User ${msg.user_id} left the session.`);
                break;
            case 'proposal.updated':
                // Refresh data if needed, or notify user
                vscode.window.setStatusBarMessage('$(info) Proposal Updated', 3000);
                break;
            case 'cursor.updated':
                // Handle cursor updates (future work: render decorations)
                break;
            case 'ownership.changed':
                // Not standard backend event yet, but good to have ready
                if (msg.ownership) {
                    this._updateOwnership(msg.ownership as SessionOwnership);
                }
                break;
            case 'conflict.detected': {
                const conflict = {
                    conflict_id: msg.conflict_id,
                    workspace_id: msg.workspace_id,
                    rule_id: msg.rule_id,
                    severity: msg.severity,
                    message: msg.message,
                    file_path: msg.file_path,
                    status: 'open',
                    detected_at: msg.timestamp,
                } as Conflict;
                this._onConflictDetected.fire(conflict);
                break;
            }
        }
    }
}
