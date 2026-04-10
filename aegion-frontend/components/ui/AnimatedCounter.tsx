"use client";

import { useEffect, useState, useRef } from "react";

interface AnimatedCounterProps {
    value: number;
    prefix?: string;
    suffix?: string;
    duration?: number;
    decimals?: number;
    className?: string;
}

export function AnimatedCounter({
    value,
    prefix = "",
    suffix = "",
    duration = 1000,
    decimals = 0,
    className = "",
}: AnimatedCounterProps) {
    const [displayValue, setDisplayValue] = useState(0);
    const prevValue = useRef(0);
    const startTime = useRef(0);
    const rafId = useRef<number | undefined>(undefined);

    useEffect(() => {
        const from = prevValue.current;
        const to = value;
        startTime.current = performance.now();

        const animate = (now: number) => {
            const elapsed = now - startTime.current;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = from + (to - from) * eased;
            setDisplayValue(current);

            if (progress < 1) {
                rafId.current = requestAnimationFrame(animate);
            } else {
                prevValue.current = to;
            }
        };

        rafId.current = requestAnimationFrame(animate);
        return () => {
            if (rafId.current) cancelAnimationFrame(rafId.current);
        };
    }, [value, duration]);

    const formatted = decimals > 0
        ? displayValue.toFixed(decimals)
        : Math.round(displayValue).toLocaleString();

    return (
        <span className={`animate-number tabular-nums ${className}`}>
            {prefix}{formatted}{suffix}
        </span>
    );
}
