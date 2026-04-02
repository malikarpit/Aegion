"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { MOCK_DECISIONS_DISTRIBUTION } from "@/lib/mock-data";

export function DecisionPie() {
    const total = MOCK_DECISIONS_DISTRIBUTION.reduce((s, d) => s + d.value, 0);

    return (
        <div className="glass-card-static p-6">
            <h3 className="text-lg font-semibold text-white mb-1">Decisions</h3>
            <p className="text-xs text-slate-500 mb-4">Distribution by status</p>

            <div className="flex items-center gap-6">
                <div className="w-[160px] h-[160px] relative">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={MOCK_DECISIONS_DISTRIBUTION}
                                cx="50%"
                                cy="50%"
                                innerRadius={50}
                                outerRadius={72}
                                paddingAngle={3}
                                dataKey="value"
                                strokeWidth={0}
                            >
                                {MOCK_DECISIONS_DISTRIBUTION.map((entry, i) => (
                                    <Cell key={i} fill={entry.color} />
                                ))}
                            </Pie>
                            <Tooltip
                                content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null;
                                    const { name, value } = payload[0].payload;
                                    return (
                                        <div className="bg-[#111118] border border-white/10 rounded-lg px-3 py-2 text-xs shadow-xl">
                                            <span className="text-slate-300">{name}: </span>
                                            <span className="text-white font-bold">{value}</span>
                                        </div>
                                    );
                                }}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                    {/* Center label */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold text-white">{total}</span>
                        <span className="text-[10px] text-slate-500 uppercase">Total</span>
                    </div>
                </div>

                <div className="flex-1 space-y-3">
                    {MOCK_DECISIONS_DISTRIBUTION.map((d) => (
                        <div key={d.name} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-2.5 h-2.5 rounded-full"
                                    style={{ backgroundColor: d.color }}
                                />
                                <span className="text-sm text-slate-300">{d.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-white">
                                    {d.value}
                                </span>
                                <span className="text-xs text-slate-500">
                                    {((d.value / total) * 100).toFixed(0)}%
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
