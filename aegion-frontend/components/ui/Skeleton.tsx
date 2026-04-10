"use client";

interface SkeletonProps {
    className?: string;
    lines?: number;
    circle?: boolean;
}

export function Skeleton({ className = "", lines, circle }: SkeletonProps) {
    if (circle) {
        return <div className={`skeleton rounded-full ${className}`} />;
    }
    if (lines) {
        return (
            <div className="space-y-2">
                {Array.from({ length: lines }).map((_, i) => (
                    <div
                        key={i}
                        className={`skeleton h-4 ${i === lines - 1 ? "w-3/4" : "w-full"} ${className}`}
                    />
                ))}
            </div>
        );
    }
    return <div className={`skeleton ${className}`} />;
}

export function CardSkeleton() {
    return (
        <div className="glass-card-static p-6 space-y-4">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-8 w-1/2" />
            <Skeleton className="h-3 w-2/3" />
        </div>
    );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
    return (
        <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: rows }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
            ))}
        </div>
    );
}
