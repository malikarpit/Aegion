// Aegion ADR Graph Webview
// Interactive D3.js visualization of decision relationships

import * as vscode from 'vscode';
import { getApiClient } from '../api/client';

interface ADRNode {
    id: string;
    title: string;
    tier: string;
    status: string;
    created_at: string;
    supersedes?: string;
    superseded_by?: string;
}

interface ADREdge {
    source: string;
    target: string;
    type: 'supersedes' | 'depends_on' | 'related';
}

export class ADRGraphPanel {
    public static currentPanel: ADRGraphPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionUri: vscode.Uri, workspaceId?: string) {
        const column = vscode.ViewColumn.Beside;

        // If we already have a panel, show it
        if (ADRGraphPanel.currentPanel) {
            ADRGraphPanel.currentPanel._panel.reveal(column);
            ADRGraphPanel.currentPanel.refresh(workspaceId);
            return;
        }

        // Create new panel
        const panel = vscode.window.createWebviewPanel(
            'aegionADRGraph',
            'ADR Graph',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        ADRGraphPanel.currentPanel = new ADRGraphPanel(panel, extensionUri, workspaceId);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, workspaceId?: string) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        // Set initial HTML content
        this._panel.webview.html = this.getHtmlContent();

        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(
            async message => {
                switch (message.command) {
                    case 'openDecision':
                        vscode.commands.executeCommand('aegion.chronos.openItem', {
                            type: 'decision',
                            id: message.decisionId,
                        });
                        break;
                    case 'refresh':
                        await this.refresh(workspaceId);
                        break;
                }
            },
            null,
            this._disposables,
        );

        // Handle panel disposal
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Load initial data
        this.refresh(workspaceId);
    }

    public async refresh(workspaceId?: string) {
        await this._loadGraph(workspaceId || '');
    }

    private async _loadGraph(workspaceId: string): Promise<void> {
        try {
            const api = getApiClient();

            // Try real graph topology first
            let nodes: ADRNode[] = [];
            let edges: ADREdge[] = [];

            try {
                const graphData = await api.getDecisionGraph(workspaceId || 'default');
                nodes = (graphData.nodes || []).slice(0, 50).map((n) => ({
                    id: n.node_id,
                    title: (n.properties?.title as string) || n.label || 'Untitled',
                    tier: (n.properties?.tier as string) || 'T1',
                    status: (n.properties?.status as string) || 'approved',
                    created_at: (n.properties?.created_at as string) || '',
                    supersedes: (n.properties?.supersedes as string) || undefined,
                    superseded_by: (n.properties?.superseded_by as string) || undefined,
                }));

                // Use real edges from graph (supersedes, depends_on)
                edges = (graphData.edges || []).map((e) => ({
                    source: e.source_id,
                    target: e.target_id,
                    type: (e.edge_type === 'supersedes' ? 'supersedes'
                        : e.edge_type === 'depends_on' ? 'depends_on'
                            : 'related') as ADREdge['type'],
                }));
            } catch {
                // Fallback to memory query if graph endpoint unavailable
                const decisions = await api.queryMemory('decisions');
                nodes = decisions.slice(0, 50).map((item: unknown) => {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    const d = item as any;
                    return {
                        id: d.decision_id || d.id,
                        title: d.title || 'Untitled',
                        tier: d.tier || 'T1',
                        status: d.status || 'approved',
                        created_at: d.created_at,
                    };
                });
                // No edges available from memory query
            }

            this._panel.webview.postMessage({
                command: 'updateGraph',
                nodes,
                edges,
            });
        } catch (error) {
            console.error('Failed to load ADR graph:', error);
        }
    }

    private getHtmlContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADR Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            font-family: var(--vscode-font-family);
            overflow: hidden;
        }
        #container { width: 100vw; height: 100vh; }
        .toolbar {
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 100;
        }
        .toolbar button {
            padding: 8px 16px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            cursor: pointer;
            border-radius: 4px;
            margin-right: 8px;
        }
        .toolbar button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .node circle {
            cursor: pointer;
            stroke: var(--vscode-editor-foreground);
            stroke-width: 2px;
        }
        .node text {
            font-size: 11px;
            fill: var(--vscode-editor-foreground);
        }
        .link {
            stroke: var(--vscode-editor-foreground);
            stroke-opacity: 0.5;
            fill: none;
        }
        .link.supersedes {
            stroke: #ff6b6b;
            stroke-dasharray: 5,3;
        }
        .tooltip {
            position: absolute;
            background: var(--vscode-editorWidget-background);
            border: 1px solid var(--vscode-editorWidget-border);
            padding: 8px 12px;
            border-radius: 4px;
            pointer-events: none;
            opacity: 0;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="toolbar">
        <button onclick="refresh()">↻ Refresh</button>
        <button onclick="resetZoom()">Reset Zoom</button>
    </div>
    <div id="container">
        <svg id="graph"></svg>
    </div>
    <div id="tooltip" class="tooltip"></div>

    <script>
        const vscode = acquireVsCodeApi();
        let svg, simulation, zoom;

        function initGraph() {
            const container = document.getElementById('container');
            svg = d3.select('#graph')
                .attr('width', container.clientWidth)
                .attr('height', container.clientHeight);

            zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', (event) => {
                    svg.select('g').attr('transform', event.transform);
                });

            svg.call(zoom);
            svg.append('g');
        }

        function updateGraph(nodes, edges) {
            const width = document.getElementById('container').clientWidth;
            const height = document.getElementById('container').clientHeight;
            const g = svg.select('g');

            // Clear existing
            g.selectAll('*').remove();

            // Create simulation
            simulation = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(edges).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2));

            // Draw links
            const link = g.selectAll('.link')
                .data(edges)
                .join('line')
                .attr('class', d => 'link ' + d.type);

            // Draw nodes
            const node = g.selectAll('.node')
                .data(nodes)
                .join('g')
                .attr('class', 'node')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            // Color by tier
            const tierColors = {
                T0: '#6c757d',
                T1: '#0d6efd',
                T2: '#198754',
                T3: '#dc3545',
            };

            node.append('circle')
                .attr('r', 20)
                .attr('fill', d => tierColors[d.tier] || '#0d6efd')
                .on('click', (event, d) => {
                    vscode.postMessage({ command: 'openDecision', decisionId: d.id });
                })
                .on('mouseover', (event, d) => showTooltip(event, d))
                .on('mouseout', hideTooltip);

            node.append('text')
                .attr('dy', 4)
                .attr('text-anchor', 'middle')
                .text(d => d.tier);

            // Update positions on tick
            simulation.on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
            });
        }

        function showTooltip(event, d) {
            const tooltip = document.getElementById('tooltip');
            let html = '<strong>' + d.title + '</strong><br>Tier: ' + d.tier + '<br>Status: ' + d.status;
            if (d.supersedes) { html += '<br><span style="color:#ff6b6b">Supersedes: ' + d.supersedes + '</span>'; }
            if (d.superseded_by) { html += '<br><span style="color:#ff6b6b">Superseded by: ' + d.superseded_by + '</span>'; }
            tooltip.innerHTML = html;
            tooltip.style.left = event.pageX + 10 + 'px';
            tooltip.style.top = event.pageY + 10 + 'px';
            tooltip.style.opacity = 1;
        }

        function hideTooltip() {
            document.getElementById('tooltip').style.opacity = 0;
        }

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }
        function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }

        function refresh() { vscode.postMessage({ command: 'refresh' }); }
        function resetZoom() { svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity); }

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            if (message.command === 'updateGraph') {
                updateGraph(message.nodes, message.edges);
            }
        });

        // Initialize
        initGraph();
    </script>
</body>
</html>`;
    }

    public dispose() {
        ADRGraphPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) { disposable.dispose(); }
        }
    }
}

export function registerADRGraph(context: vscode.ExtensionContext) {
    context.subscriptions.push(
        vscode.commands.registerCommand('aegion.showADRGraph', () => {
            ADRGraphPanel.createOrShow(context.extensionUri);
        }),
    );
}
