/**
 * Aegion Timeline Panel - Architecture Decision Timeline
 *
 * Phase 5: Advanced Epistemics
 * Visual architecture decision history and evolution.
 */

import * as vscode from 'vscode';
import { getApiClient, TimelineEvent } from '../api/client';
import { getActiveWorkspaceId } from '../config';

interface ADR {
    adr_id: string;
    title: string;
    status: string;
    created_at: string;
    decision: string;
}

interface TimelineViewEvent {
    event_id: string;
    event_type: string;
    timestamp: string;
    title: string;
    description: string;
    actor: string;
}

export class TimelinePanel {
    public static currentPanel: TimelinePanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static readonly viewType = 'aegion.timeline';

    private constructor(panel: vscode.WebviewPanel, _extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables,
        );
        this._loadData();
    }

    public static show(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (TimelinePanel.currentPanel) {
            TimelinePanel.currentPanel._panel.reveal(column);
            TimelinePanel.currentPanel._loadData();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            TimelinePanel.viewType,
            '📜 Architecture Timeline',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        TimelinePanel.currentPanel = new TimelinePanel(panel, extensionUri);
    }

    private async _handleMessage(message: { command: string; adr_id?: string }): Promise<void> {
        switch (message.command) {
            case 'refresh':
                this._loadData();
                break;
            case 'viewADR':
                vscode.window.showInformationMessage(`Opening ADR: ${message.adr_id}`);
                break;
            case 'createADR':
                vscode.window.showInputBox({
                    prompt: 'Enter ADR title',
                }).then(title => {
                    if (title) {
                        vscode.window.showInformationMessage(`Creating ADR: ${title}`);
                    }
                });
                break;
        }
    }

    private async _loadData(): Promise<void> {
        try {
            const api = getApiClient();
            const workspaceId = getActiveWorkspaceId();

            const [adrs, timeline] = await Promise.all([
                api.getADRs().catch(() => []),
                api.getTimeline(workspaceId).then((t) => t.events || []).catch(() => []),
            ]);

            // Map ADRs to view format if needed
            const mappedAdrs = adrs.map((a) => ({
                adr_id: a.adr_id,
                title: a.title,
                status: a.status,
                created_at: a.created_at || new Date().toISOString(),
                decision: 'decision' in a ? ((a as { decision?: string }).decision || '') : '',
            }));

            // Map events
            const mappedEvents: TimelineViewEvent[] = timeline.map((e: TimelineEvent) => {
                const details = (e as unknown as Record<string, unknown>);
                return {
                    event_id: (details.event_id as string) || e.event_id,
                    event_type: e.event_type,
                    timestamp: e.timestamp,
                    title: (details.summary as string) || e.event_type,
                    description: JSON.stringify(details.details || {}),
                    actor: (details.actor_id as string) || 'system',
                };
            });

            this._panel.webview.html = this._getHtml(mappedAdrs, mappedEvents);
        } catch (error) {
            // Fallback to empty state
            this._panel.webview.html = this._getHtml([], []);
        }
    }

    private _getHtml(adrs: ADR[], events: TimelineViewEvent[]): string {
        const statusColors: Record<string, string> = {
            'proposed': '#4fc3f7',
            'accepted': '#81c784',
            'deprecated': '#bdbdbd',
            'superseded': '#ffb74d',
        };

        const adrCards = adrs.map(adr => `
            <div class="adr-card" onclick="viewADR('${adr.adr_id}')">
                <div class="adr-header">
                    <span class="adr-id">${adr.adr_id}</span>
                    <span class="status" style="background: ${statusColors[adr.status] || '#888'};">${adr.status}</span>
                </div>
                <div class="adr-title">${adr.title}</div>
                <div class="adr-decision">${adr.decision}</div>
                <div class="adr-date">${adr.created_at}</div>
            </div>
        `).join('');

        const eventItems = events.map(e => `
            <div class="timeline-event">
                <div class="event-dot"></div>
                <div class="event-content">
                    <div class="event-time">${e.timestamp}</div>
                    <div class="event-title">${e.title}</div>
                    <div class="event-desc">${e.description}</div>
                </div>
            </div>
        `).join('');

        return `<!DOCTYPE html>
<html>
<head>
    <style>
        :root {
            --card-bg: rgba(255,255,255,0.03);
            --card-border: rgba(255,255,255,0.1);
            --accent: #4fc3f7;
        }
        body { 
            font-family: var(--vscode-font-family); 
            background: var(--vscode-editor-background);
            color: var(--vscode-foreground);
            padding: 24px;
            margin: 0;
        }
        h1 { 
            display: flex; 
            align-items: center; 
            gap: 12px;
            margin-bottom: 24px;
        }
        .toolbar {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }
        button {
            padding: 10px 20px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }
        .section {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
        }
        .section h2 { margin-top: 0; font-size: 1.1em; }
        .adr-card {
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .adr-card:hover { background: rgba(255,255,255,0.1); }
        .adr-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .adr-id { font-family: monospace; opacity: 0.6; font-size: 0.8em; }
        .status {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7em;
            font-weight: bold;
            text-transform: uppercase;
            color: #000;
        }
        .adr-title { font-weight: 600; margin-bottom: 6px; }
        .adr-decision { font-size: 0.85em; opacity: 0.7; margin-bottom: 6px; }
        .adr-date { font-size: 0.75em; opacity: 0.5; }
        .timeline-event {
            display: flex;
            gap: 12px;
            padding: 12px 0;
            border-left: 2px solid var(--card-border);
            margin-left: 6px;
            padding-left: 16px;
            position: relative;
        }
        .event-dot {
            position: absolute;
            left: -7px;
            top: 16px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--accent);
        }
        .event-time { font-size: 0.75em; opacity: 0.5; }
        .event-title { font-weight: 500; margin: 4px 0; }
        .event-desc { font-size: 0.85em; opacity: 0.7; }
    </style>
</head>
<body>
    <h1>📜 Architecture Timeline</h1>
    
    <div class="toolbar">
        <button onclick="createADR()">+ New ADR</button>
        <button onclick="refresh()">🔄 Refresh</button>
    </div>
    
    <div class="grid">
        <div class="section">
            <h2>Architecture Decision Records</h2>
            ${adrCards}
        </div>
        
        <div class="section">
            <h2>Recent Events</h2>
            ${eventItems}
        </div>
    </div>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        function viewADR(adr_id) {
            vscode.postMessage({ command: 'viewADR', adr_id });
        }
        
        function createADR() {
            vscode.postMessage({ command: 'createADR' });
        }
        
        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }
    </script>
</body>
</html>`;
    }

    public dispose(): void {
        TimelinePanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) { x.dispose(); }
        }
    }
}
