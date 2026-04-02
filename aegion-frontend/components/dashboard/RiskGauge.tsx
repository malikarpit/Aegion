"use client";

import { MOCK_STATS } from "@/lib/mock-data";
import { ShieldAlert } from "lucide-react";

export function RiskGauge() {
    const score = MOCK_STATS.riskScore;
    const cacheRate = MOCK_STATS.cacheHitRate;

    // Calculate arc for semicircle gauge
    const percentage = score / 100;
    const circumference = Math.PI * 80; // half circle with r=80
    const offset = circumference * (1 - percentage);

    const getColor = (s: number) => {
        if (s < 30) return "#22c55e";
        if (s < 60) return "#eab308";
        return "#ef4444";
    };

    const getLabel = (s: number) => {
        if (s < 30) return "Low Risk";
        if (s < 60) return "Moderate";
        return "High Risk";
    };

    return (
        <div className="glass-card-static p-6">
            <div className="flex items-center gap-2 mb-4">
                <ShieldAlert size={18} className="text-amber-400" />
                <h3 className="text-lg font-semibold text-white">Risk Score</h3>
            </div>

            {/* Gauge */}
            <div className="flex justify-center mb-4">
                <div className="relative w-[180px] h-[100px]">
                    <svg
                        viewBox="0 0 200 110"
                        className="w-full h-full"
                    >
                        {/* Background arc */}
                        <path
                            d="M 20 100 A 80 80 0 0 1 180 100"
                            fill="none"
                            stroke="rgba(255,255,255,0.05)"
                            strokeWidth="12"
                            strokeLinecap="round"
                        />
                        {/* Value arc */}
                        <path
                            d="M 20 100 A 80 80 0 0 1 180 100"
                            fill="none"
                            stroke={getColor(score)}
                            strokeWidth="12"
                            strokeLinecap="round"
                            strokeDasharray={`${circumference}`}
                            strokeDashoffset={offset}
                            className="transition-all duration-1000 ease-out"
                        />
                    </svg>
                    {/* Center text */}
                    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
                        <div className="text-3xl font-bold text-white">{score}</div>
                        <div
                            className="text-xs font-medium mt-0.5"
                            style={{ color: getColor(score) }}
                        >
                            {getLabel(score)}
                        </div>
                    </div>
                </div>
            </div>

            {/* Extra metrics */}
            <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="bg-white/[0.02] rounded-lg p-3 text-center">
                    <p className="text-lg font-bold text-white">{cacheRate}%</p>
                    <p className="text-[10px] text-slate-500 uppercase">Cache Hit Rate</p>
                </div>
                <div className="bg-white/[0.02] rounded-lg p-3 text-center">
                    <p className="text-lg font-bold text-white">2</p>
                    <p className="text-[10px] text-slate-500 uppercase">Active Alerts</p>
                </div>
            </div>
        </div>
    );
}
