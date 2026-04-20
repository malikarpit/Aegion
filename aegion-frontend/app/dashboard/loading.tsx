export default function DashboardLoading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="skeleton h-8 w-48 rounded-lg" />
        <div className="skeleton h-6 w-32 rounded-lg" />
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-28 rounded-xl" />
        ))}
      </div>

      {/* Content area */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 skeleton h-64 rounded-xl" />
        <div className="skeleton h-64 rounded-xl" />
      </div>

      {/* Activity feed */}
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton h-16 rounded-lg" />
        ))}
      </div>
    </div>
  );
}
