"use client";

import React from "react";

/* ══════════════════════════════════════════════════════════════
   ARCHITECTURE FLOW — Animated SVG Architecture Diagram
   
   Perpetual traveling-dash animation on connections.
   System feels alive even without scroll.
   ══════════════════════════════════════════════════════════════ */

const NODES = [
  {
    id: "user",
    label: "Developer",
    x: 80,
    y: 200,
    color: "var(--text-secondary)",
    icon: "⌘",
  },
  {
    id: "session",
    label: "Session",
    x: 250,
    y: 200,
    color: "var(--accent-reason)",
    icon: "◉",
  },
  {
    id: "council",
    label: "Council",
    x: 420,
    y: 120,
    color: "var(--accent-govern)",
    icon: "⚙",
  },
  {
    id: "sentinel",
    label: "Sentinel",
    x: 420,
    y: 280,
    color: "var(--accent-risk)",
    icon: "🛡",
  },
  {
    id: "archon",
    label: "Archon",
    x: 590,
    y: 200,
    color: "var(--accent-execute)",
    icon: "△",
  },
  {
    id: "chronos",
    label: "Chronos",
    x: 760,
    y: 200,
    color: "var(--accent-memory)",
    icon: "⏳",
  },
];

const EDGES = [
  { from: "user", to: "session" },
  { from: "session", to: "council" },
  { from: "session", to: "sentinel" },
  { from: "council", to: "archon" },
  { from: "sentinel", to: "archon" },
  { from: "archon", to: "chronos" },
  { from: "chronos", to: "session" }, // feedback loop
];

function getConnectorPath(
  from: { x: number; y: number },
  to: { x: number; y: number }
): string {
  const midX = (from.x + to.x) / 2;
  return `M ${from.x + 40} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x - 40} ${to.y}`;
}

export function ArchitectureFlow() {
  return (
    <div className="w-full max-w-[900px] mx-auto">
      <svg
        viewBox="0 0 840 400"
        className="w-full h-auto"
        style={{ filter: "drop-shadow(0 0 30px hsla(217, 85%, 60%, 0.08))" }}
      >
        <defs>
          {/* Traveling dash animation */}
          <style>
            {`
              @keyframes dashTravel {
                0% { stroke-dashoffset: 20; }
                100% { stroke-dashoffset: 0; }
              }
              .flow-edge {
                stroke-dasharray: 8 12;
                animation: dashTravel 1.5s linear infinite;
              }
              .flow-edge-reverse {
                stroke-dasharray: 8 12;
                animation: dashTravel 1.5s linear infinite reverse;
              }
            `}
          </style>

          {/* Glow filter */}
          <filter id="node-glow">
            <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur" />
            <feFlood floodColor="var(--accent-reason)" floodOpacity="0.2" />
            <feComposite in2="blur" operator="in" />
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Edges */}
        {EDGES.map((edge, i) => {
          const from = NODES.find((n) => n.id === edge.from)!;
          const to = NODES.find((n) => n.id === edge.to)!;
          const isReverse = edge.from === "chronos";
          const path = getConnectorPath(from, to);

          return (
            <path
              key={i}
              d={path}
              fill="none"
              stroke="var(--border-default)"
              strokeWidth={1}
              className={isReverse ? "flow-edge-reverse" : "flow-edge"}
              style={{
                animationDelay: `${i * 200}ms`,
                animationDuration: `${1.5 + i * 0.3}s`,
              }}
            />
          );
        })}

        {/* Nodes */}
        {NODES.map((node) => (
          <g key={node.id} filter="url(#node-glow)">
            {/* Outer ring */}
            <circle
              cx={node.x}
              cy={node.y}
              r={36}
              fill="none"
              stroke={node.color}
              strokeWidth={0.5}
              strokeOpacity={0.3}
            />
            {/* Inner circle */}
            <circle
              cx={node.x}
              cy={node.y}
              r={24}
              fill="var(--surface-2)"
              stroke={node.color}
              strokeWidth={1}
              strokeOpacity={0.5}
            />
            {/* Icon */}
            <text
              x={node.x}
              y={node.y + 1}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={14}
              fill={node.color}
            >
              {node.icon}
            </text>
            {/* Label */}
            <text
              x={node.x}
              y={node.y + 48}
              textAnchor="middle"
              fontSize={11}
              fontFamily="var(--font-mono)"
              fontWeight={500}
              fill={node.color}
              letterSpacing="0.04em"
            >
              {node.label.toUpperCase()}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
