/**
 * Aegion API Client — initial fetch-based implementation.
 *
 * TODO: Add EventSource SSE streaming and WebSocket support.
 */

import * as vscode from 'vscode';

export class AegionClient {
    private baseUrl: string;

    constructor() {
        const config = vscode.workspace.getConfiguration('aegion');
        this.baseUrl = config.get('backendUrl', 'http://localhost:8000');
    }

    private async request(path: string, options?: RequestInit): Promise<any> {
        const url = `${this.baseUrl}/api/v1${path}`;
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options?.headers,
            },
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async startSession(workspaceId: string): Promise<any> {
        return this.request('/sessions', {
            method: 'POST',
            body: JSON.stringify({ workspace_id: workspaceId }),
        });
    }

    async createProposal(sessionId: string, title: string, description: string): Promise<any> {
        return this.request('/proposals', {
            method: 'POST',
            body: JSON.stringify({ session_id: sessionId, title, description }),
        });
    }

    async getProposal(proposalId: string): Promise<any> {
        return this.request(`/proposals/${proposalId}`);
    }
}
