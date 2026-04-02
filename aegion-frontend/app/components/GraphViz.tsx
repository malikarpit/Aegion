"use client";

import React, { useEffect, useState } from 'react';
import { ReactFlow, Controls, Background, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const initialNodes = [
    { id: '1', position: { x: 0, y: 0 }, data: { label: 'Proposal: P-101' }, type: 'input' },
    { id: '2', position: { x: 0, y: 100 }, data: { label: 'Decision: D-101' } },
];
const initialEdges = [{ id: 'e1-2', source: '1', target: '2' }];

export default function GraphViz() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    // In a real implementation, fetch from /api/v1/graph
    useEffect(() => {
        // const fetchGraph = async () => { ... }
    }, []);

    return (
        <div style={{ width: '100%', height: '500px', border: '1px solid #ccc' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
            >
                <Background />
                <Controls />
            </ReactFlow>
        </div>
    );
}
