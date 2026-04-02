"use client";

import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";
import { MOCK_COST_OVER_TIME } from "@/lib/mock-data";

const COLORS = {
    openai: "#22c55e",
    anthropic: "#a855f7",
    google: "#3b82f6",
    deepseek: "#f59e0b",
};

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
    if (!active || !payload) return null;

    const total = payload.reduce((sum, p) => sum + p.value, 0);

    return (
        <div className="bg-[#111118] border border-white/10 rounded-xl p-4 shadow-xl text-sm">
            <p className="text-slate-400 text-xs mb-2">{label}</p>
            {payload.map((p) => (
                <div key={p.name} className="flex items-center justify-between gap-6">
                    <div className="flex items-center gap-2">
                        <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: p.color }}
                        />
                        <span className="text-slate-300 capitalize">{p.name}</span>
                    </div>
                    <span className="text-white font-medium">${p.value.toFixed(2)}</span>
                </div>
            ))}
            <div className="mt-2 pt-2 border-t border-white/10 flex justify-between">
                <span className="text-slate-400">Total</span>
                <span className="text-white font-bold">${total.toFixed(2)}</span>
            </div>
        </div>
    );
}

export function CostChart() {
    return (
        <div className="glass-card-static p-6">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-lg font-semibold text-white">
                        Cost Over Time
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">
                        Last 30 days by provider
                    </p>
                </div>
                <div className="flex gap-3">
                    {Object.entries(COLORS).map(([name, color]) => (
                        <div key={name} className="flex items-center gap-1.5 text-xs text-slate-400">
                            <div
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: color }}
                            />
                            <span className="capitalize">{name}</span>
                        </div>
                    ))}
                </div>
            </div>

            <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={MOCK_COST_OVER_TIME}>
                        <defs>
                            {Object.entries(COLORS).map(([key, color]) => (
                                <linearGradient
                                    key={key}
                                    id={`gradient-${key}`}
                                    x1="0"
                                    y1="0"
                                    x2="0"
                                    y2="1"
                                >
                                    <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                                </linearGradient>
                            ))}
                        </defs>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(255,255,255,0.03)"
                            vertical={false}
                        />
                        <XAxis
                            dataKey="date"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: "#64748b", fontSize: 11 }}
                            interval={4}
                        />
                        <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: "#64748b", fontSize: 11 }}
                            tickFormatter={(v) => `$${v}`}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        {Object.entries(COLORS).map(([key, color]) => (
                            <Area
                                key={key}
                                type="monotone"
                                dataKey={key}
                                stackId="1"
                                stroke={color}
                                strokeWidth={2}
                                fill={`url(#gradient-${key})`}
                            />
                        ))}
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
