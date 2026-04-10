"use client";

interface ProgressRingProps {
    value: number;         // 0-100
    size?: number;         // px
    strokeWidth?: number;
    label?: string;
    sublabel?: string;
    color?: string;        // Tailwind color class for stroke
    className?: string;
}

export function ProgressRing({
    value,
    size = 120,
    strokeWidth = 8,
    label,
    sublabel,
    color = "stroke-blue-500",
    className = "",
}: ProgressRingProps) {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (Math.min(value, 100) / 100) * circumference;

    const getColor = (v: number) => {
        if (v >= 80) return "stroke-emerald-400";
        if (v >= 50) return "stroke-yellow-400";
        if (v >= 25) return "stroke-orange-400";
        return "stroke-red-400";
    };

    const ringColor = color === "auto" ? getColor(value) : color;

    return (
        <div className={`relative inline-flex flex-col items-center ${className}`}>
            <svg
                width={size}
                height={size}
                viewBox={`0 0 ${size} ${size}`}
                className="transform -rotate-90"
            >
                {/* Background ring */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    className="progress-ring-bg"
                    strokeWidth={strokeWidth}
                />
                {/* Filled ring */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    className={`${ringColor} progress-ring-fill`}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                />
            </svg>
            {/* Center text */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold text-white tabular-nums">
                    {Math.round(value)}%
                </span>
                {label && (
                    <span className="text-xs text-slate-400 mt-0.5">{label}</span>
                )}
            </div>
            {sublabel && (
                <span className="text-xs text-slate-500 mt-2">{sublabel}</span>
            )}
        </div>
    );
}
