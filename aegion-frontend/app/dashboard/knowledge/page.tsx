"use client";

import { useState, useCallback, useMemo } from "react";
import { Search, ZoomIn, ZoomOut, Maximize2, X } from "lucide-react";
import {
    ReactFlow,
    Node,
    Edge,
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const nodeColors: Record<string, string> = {
    concept: "#3b82f6",
    decision: "#22c55e",
    adr: "#a855f7",
    proposal: "#f59e0b",
    service: "#06b6d4",
};

const initialNodes: Node[] = [
    { id: "1", position: { x: 400, y: 100 }, data: { label: "Council Engine", type: "service" }, style: { background: "#06b6d4/20", border: "1px solid #06b6d4", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "2", position: { x: 200, y: 250 }, data: { label: "FrugalGPT Cascade", type: "concept" }, style: { background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "3", position: { x: 600, y: 250 }, data: { label: "Sentinel", type: "service" }, style: { background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "4", position: { x: 100, y: 400 }, data: { label: "Use Supabase Realtime", type: "decision" }, style: { background: "rgba(34,197,94,0.15)", border: "1px solid rgba(34,197,94,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "5", position: { x: 350, y: 400 }, data: { label: "ADR-022: Cascade Pattern", type: "adr" }, style: { background: "rgba(168,85,247,0.15)", border: "1px solid rgba(168,85,247,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "6", position: { x: 600, y: 400 }, data: { label: "ADR-024: gRPC Migration", type: "adr" }, style: { background: "rgba(168,85,247,0.15)", border: "1px solid rgba(168,85,247,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "7", position: { x: 750, y: 300 }, data: { label: "Add Rate Limiting", type: "proposal" }, style: { background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "8", position: { x: 200, y: 550 }, data: { label: "pgvector Embeddings", type: "concept" }, style: { background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "9", position: { x: 500, y: 550 }, data: { label: "GraphRAG", type: "concept" }, style: { background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "10", position: { x: 400, y: 700 }, data: { label: "Semantic Cache", type: "service" }, style: { background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "11", position: { x: 50, y: 300 }, data: { label: "Token Budgeting", type: "concept" }, style: { background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
    { id: "12", position: { x: 800, y: 500 }, data: { label: "PKCE Auth Migration", type: "proposal" }, style: { background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.4)", borderRadius: 12, padding: "8px 16px", color: "white", fontSize: 12 } },
];

const initialEdges: Edge[] = [
    { id: "e1-2", source: "1", target: "2", animated: true, style: { stroke: "rgba(255,255,255,0.1)" } },
    { id: "e1-3", source: "1", target: "3", animated: true, style: { stroke: "rgba(255,255,255,0.1)" } },
    { id: "e2-5", source: "2", target: "5", style: { stroke: "rgba(168,85,247,0.3)" } },
    { id: "e2-11", source: "2", target: "11", style: { stroke: "rgba(59,130,246,0.2)" } },
    { id: "e3-7", source: "3", target: "7", style: { stroke: "rgba(245,158,11,0.3)" } },
    { id: "e3-6", source: "3", target: "6", style: { stroke: "rgba(168,85,247,0.3)" } },
    { id: "e3-12", source: "3", target: "12", style: { stroke: "rgba(245,158,11,0.3)" } },
    { id: "e4-8", source: "4", target: "8", style: { stroke: "rgba(34,197,94,0.3)" } },
    { id: "e8-10", source: "8", target: "10", style: { stroke: "rgba(59,130,246,0.2)" } },
    { id: "e9-10", source: "9", target: "10", style: { stroke: "rgba(59,130,246,0.2)" } },
    { id: "e1-4", source: "1", target: "4", style: { stroke: "rgba(255,255,255,0.08)" } },
    { id: "e5-9", source: "5", target: "9", style: { stroke: "rgba(168,85,247,0.2)" } },
];

export default function KnowledgePage() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [search, setSearch] = useState("");
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);

    const highlightedNodes = useMemo(() => {
        if (!search) return new Set<string>();
        return new Set(
            nodes
                .filter((n) => String(n.data.label).toLowerCase().includes(search.toLowerCase()))
                .map((n) => n.id)
        );
    }, [search, nodes]);

    const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
        setSelectedNode(node);
    }, []);

    return (
        <div className="h-[calc(100vh)] flex flex-col animate-fade-in">
            {/* Header */}
            <div className="p-4 lg:px-8 border-b border-white/5 flex items-center justify-between shrink-0">
                <div>
                    <h1 className="text-lg font-bold text-white">Knowledge Graph</h1>
                    <p className="text-xs text-slate-500">Interactive concept and decision network</p>
                </div>

                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search nodes..."
                            className="glass-input pl-9 pr-4 py-2 text-xs w-56"
                        />
                    </div>

                    {/* Legend */}
                    <div className="hidden lg:flex items-center gap-3">
                        {Object.entries(nodeColors).map(([type, color]) => (
                            <div key={type} className="flex items-center gap-1.5 text-[10px] text-slate-500">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                                <span className="capitalize">{type}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Graph */}
            <div className="flex-1 relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={onNodeClick}
                    fitView
                    minZoom={0.3}
                    maxZoom={2}
                    proOptions={{ hideAttribution: true }}
                    style={{ background: "#000" }}
                >
                    <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="rgba(255,255,255,0.03)" />
                    <MiniMap
                        nodeStrokeWidth={2}
                        style={{ background: "rgba(0,0,0,0.8)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 8 }}
                        maskColor="rgba(0,0,0,0.6)"
                    />
                </ReactFlow>

                {/* Detail panel */}
                {selectedNode && (
                    <div className="absolute right-4 top-4 w-72 glass-card-static p-5 animate-slide-down z-10">
                        <div className="flex items-center justify-between mb-3">
                            <span
                                className="text-[10px] px-2 py-0.5 rounded-full font-medium capitalize"
                                style={{
                                    backgroundColor: `${nodeColors[selectedNode.data.type as string]}20`,
                                    color: nodeColors[selectedNode.data.type as string],
                                    border: `1px solid ${nodeColors[selectedNode.data.type as string]}40`,
                                }}
                            >
                                {selectedNode.data.type as string}
                            </span>
                            <button
                                onClick={() => setSelectedNode(null)}
                                className="text-slate-500 hover:text-white transition-colors"
                            >
                                <X size={14} />
                            </button>
                        </div>
                        <h3 className="text-sm font-semibold text-white mb-2">
                            {selectedNode.data.label as string}
                        </h3>
                        <p className="text-xs text-slate-400 mb-3">
                            Node ID: <code className="text-slate-300">{selectedNode.id}</code>
                        </p>
                        <div className="text-xs text-slate-500">
                            <p>
                                Connections:{" "}
                                {edges.filter(
                                    (e) => e.source === selectedNode.id || e.target === selectedNode.id
                                ).length}
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
