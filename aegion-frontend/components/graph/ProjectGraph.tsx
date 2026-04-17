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
                { id: '1', position: { x: 0, y: 0 }, data: { label: 'Project Start' }, type: 'input', style: { background: 'hsl(248, 15%, 12%)', color: 'hsl(260, 20%, 95%)', border: '1px solid hsl(260, 100%, 70%)' } },
                { id: '2', position: { x: 0, y: 100 }, data: { label: 'Auth System Decision' }, style: { background: 'hsl(248, 15%, 12%)', color: 'hsl(260, 20%, 95%)', border: '1px solid hsl(280, 85%, 65%)' } },
                { id: '3', position: { x: -100, y: 200 }, data: { label: 'Firebase Impl' }, style: { background: 'hsl(248, 18%, 7%)', color: 'hsl(250, 10%, 65%)', border: '1px solid hsl(248, 12%, 20%)' } },
                { id: '4', position: { x: 100, y: 200 }, data: { label: 'JWT Fallback' }, style: { background: 'hsl(248, 18%, 7%)', color: 'hsl(250, 10%, 65%)', border: '1px solid hsl(248, 12%, 20%)' } },
            ];
            const mockEdges: Edge[] = [
                { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: 'hsl(250, 10%, 40%)' } },
                { id: 'e2-3', source: '2', target: '3', style: { stroke: 'hsl(250, 10%, 40%)' } },
                { id: 'e2-4', source: '2', target: '4', style: { stroke: 'hsl(250, 10%, 40%)' } },
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
            <div className="flex items-center justify-center h-full animate-pulse" style={{ color: "var(--accent-reason)" }}>
                Loading Neural Graph...
            </div>
        );
    }

    return (
        <div className="w-full h-[600px] rounded-xl backdrop-blur-sm overflow-hidden shadow-2xl" style={{ border: '1px solid var(--border-default)', background: 'hsla(248, 15%, 5%, 0.6)' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                fitView
                className="" style={{ background: 'hsl(248, 18%, 4%)' }}
            >
                <Controls className="" style={{ background: 'hsla(260, 20%, 80%, 0.08)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
                <MiniMap
                    className="" style={{ background: 'hsl(248, 18%, 5%)', border: '1px solid var(--border-default)' }}
                    nodeColor={(n) => {
                        if (n.style?.background) return n.style.background as string;
                        return '#fff';
                    }}
                />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} color="hsl(248, 12%, 20%)" />
            </ReactFlow>
        </div>
    );
}
