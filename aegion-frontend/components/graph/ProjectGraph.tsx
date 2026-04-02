"use client";

import { useCallback, useEffect, useState } from "react";
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Node,
    Edge,
    BackgroundVariant,
    Connection
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import api from "@/lib/api";

const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

export function ProjectGraph() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [loading, setLoading] = useState(true);

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            // Fetch graph data from backend
            // Using /noesis/decisions/graph endpoint (or similar from client.ts)
            const workspaceId = "default"; // TODO: Get from context/route

            // Fallback/Mock data for now until backend is fully reachable
            // In production, uncomment:
            // const response = await api.get(`/noesis/workspace/${workspaceId}/topology`);

            // MOCK DATA START
            const mockNodes: Node[] = [
                { id: '1', position: { x: 0, y: 0 }, data: { label: 'Project Start' }, type: 'input', style: { background: '#1e293b', color: '#fff', border: '1px solid #3b82f6' } },
                { id: '2', position: { x: 0, y: 100 }, data: { label: 'Auth System Decision' }, style: { background: '#1e293b', color: '#fff', border: '1px solid #a855f7' } },
                { id: '3', position: { x: -100, y: 200 }, data: { label: 'Firebase Impl' }, style: { background: '#0f172a', color: '#94a3b8', border: '1px solid #334155' } },
                { id: '4', position: { x: 100, y: 200 }, data: { label: 'JWT Fallback' }, style: { background: '#0f172a', color: '#94a3b8', border: '1px solid #334155' } },
            ];
            const mockEdges: Edge[] = [
                { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#64748b' } },
                { id: 'e2-3', source: '2', target: '3', style: { stroke: '#64748b' } },
                { id: 'e2-4', source: '2', target: '4', style: { stroke: '#64748b' } },
            ];
            // MOCK DATA END

            setNodes(mockNodes);
            setEdges(mockEdges);
        } catch (error) {
            console.error("Failed to fetch graph data", error);
        } finally {
            setLoading(false);
        }
    }, [setNodes, setEdges]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full text-blue-400 animate-pulse">
                Loading Neural Graph...
            </div>
        );
    }

    return (
        <div className="w-full h-[600px] border border-white/10 rounded-xl bg-black/40 backdrop-blur-sm overflow-hidden shadow-2xl">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                fitView
                className="bg-black/90"
            >
                <Controls className="bg-white/10 border-white/10 text-white fill-white" />
                <MiniMap
                    className="bg-black/80 border border-white/10"
                    nodeColor={(n) => {
                        if (n.style?.background) return n.style.background as string;
                        return '#fff';
                    }}
                />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} color="#333" />
            </ReactFlow>
        </div>
    );
}
