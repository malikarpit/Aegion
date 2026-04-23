"use client";

interface ProgressRingProps {
    value: number;         // 0-100
    size?: number;         // px
    strokeWidth?: number;
    label?: string;
    sublabel?: string;
    color?: string;        // CSS color value or 'auto'
    className?: string;
}

export function ProgressRing({
    value,
    size = 120,
    strokeWidth = 8,
    label,
    sublabel,
    color = "var(--accent-reason)",
    className = "",
}: ProgressRingProps) {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (Math.min(value, 100) / 100) * circumference;

    const getColor = (v: number) => {
        if (v >= 80) return "var(--status-success)";
        if (v >= 50) return "var(--status-warning)";
        if (v >= 25) return "var(--accent-cost)";
        return "var(--status-error)";
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
                    stroke="var(--border-default)"
                />
                {/* Filled ring */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    className="progress-ring-fill"
                    stroke={ringColor}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                />
            </svg>
            {/* Center text */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
                    {Math.round(value)}%
                </span>
                {label && (
                    <span className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{label}</span>
                )}
            </div>
            {sublabel && (
                <span className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>{sublabel}</span>
            )}
        </div>
    );
}
