"use client";

import { useState } from "react";
import {
  CheckSquare, Square, Clock, AlertCircle, Plus,
  ChevronDown, ChevronRight, Loader2,
} from "lucide-react";
import { TemporalMeta } from "@/components/cognitive/TemporalMeta";

/* ══════════════════════════════════════════════════════════════
   TASKS PAGE — Task tree with status, priority, temporal meta
   ══════════════════════════════════════════════════════════════ */

interface Task {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "completed" | "blocked";
  priority: "critical" | "high" | "medium" | "low";
  assignee: string;
  createdAt: number;
  children?: Task[];
}

const STATUS_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
  pending: { icon: Square, color: "var(--text-muted)" },
  in_progress: { icon: Clock, color: "var(--accent-reason)" },
  completed: { icon: CheckSquare, color: "var(--status-success)" },
  blocked: { icon: AlertCircle, color: "var(--status-error)" },
};

const PRIORITY_COLORS: Record<string, string> = {
  critical: "var(--tier-3)",
  high: "var(--tier-2)",
  medium: "var(--tier-1)",
  low: "var(--text-muted)",
};

const SEED_TASKS: Task[] = [
  {
    id: "t-1", title: "Implement Redis caching layer", status: "in_progress", priority: "high", assignee: "system", createdAt: Date.now() - 2 * 86400000,
    children: [
      { id: "t-1a", title: "Set up Redis connection pool", status: "completed", priority: "high", assignee: "system", createdAt: Date.now() - 2 * 86400000 },
      { id: "t-1b", title: "Implement cache invalidation", status: "in_progress", priority: "high", assignee: "system", createdAt: Date.now() - 1 * 86400000 },
      { id: "t-1c", title: "Add cache metrics", status: "pending", priority: "medium", assignee: "system", createdAt: Date.now() - 1 * 86400000 },
    ],
  },
  { id: "t-2", title: "Review rate limiting configuration", status: "pending", priority: "medium", assignee: "user", createdAt: Date.now() - 3 * 86400000 },
  { id: "t-3", title: "Deploy JWT auth migration", status: "blocked", priority: "critical", assignee: "system", createdAt: Date.now() - 1 * 86400000 },
  { id: "t-4", title: "Update API documentation", status: "completed", priority: "low", assignee: "user", createdAt: Date.now() - 5 * 86400000 },
];

function TaskRow({ task, depth = 0 }: { task: Task; depth?: number }) {
  const [expanded, setExpanded] = useState(true);
  const { icon: StatusIcon, color: statusColor } = STATUS_ICONS[task.status];
  const hasChildren = task.children && task.children.length > 0;

  return (
    <>
      <div className="flex items-center gap-3 py-2.5 px-3 rounded-lg transition-colors hover:bg-[var(--surface-hover)]" style={{ paddingLeft: `${12 + depth * 24}px` }}>
        {hasChildren ? (
          <button onClick={() => setExpanded(!expanded)} className="shrink-0">
            {expanded ? <ChevronDown size={14} style={{ color: "var(--text-ghost)" }} /> : <ChevronRight size={14} style={{ color: "var(--text-ghost)" }} />}
          </button>
        ) : (
          <div className="w-[14px]" />
        )}
        <StatusIcon size={16} style={{ color: statusColor }} />
        <span className="text-[14px] flex-1" style={{ color: task.status === "completed" ? "var(--text-muted)" : "var(--text-primary)", textDecoration: task.status === "completed" ? "line-through" : "none" }}>
          {task.title}
        </span>
        <span className="hud-label px-1.5 py-[1px] rounded-[4px]" style={{ background: `color-mix(in srgb, ${PRIORITY_COLORS[task.priority]} 10%, transparent)`, color: PRIORITY_COLORS[task.priority] }}>
          {task.priority.toUpperCase()}
        </span>
        <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>{task.assignee}</span>
        <TemporalMeta createdAt={task.createdAt} stability="stable" inline />
      </div>
      {expanded && task.children?.map((child) => <TaskRow key={child.id} task={child} depth={depth + 1} />)}
    </>
  );
}

export default function TasksPage() {
  const counts = {
    total: SEED_TASKS.length + SEED_TASKS.reduce((a, t) => a + (t.children?.length || 0), 0),
    completed: SEED_TASKS.filter((t) => t.status === "completed").length + SEED_TASKS.reduce((a, t) => a + (t.children?.filter((c) => c.status === "completed").length || 0), 0),
    blocked: SEED_TASKS.filter((t) => t.status === "blocked").length,
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Tasks</h1>
          <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
            System and user task tracking with priority and lineage
          </p>
        </div>
        <button className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium" style={{ background: "var(--accent-reason)", color: "white" }}>
          <Plus size={14} /> New Task
        </button>
      </div>

      {/* Stats */}
      <div className="flex gap-4">
        <div className="glass-l1 px-4 py-3 rounded-lg">
          <span className="mono-data font-medium" style={{ color: "var(--text-primary)" }}>{counts.total}</span>
          <span className="hud-label ml-2">TOTAL</span>
        </div>
        <div className="glass-l1 px-4 py-3 rounded-lg">
          <span className="mono-data font-medium" style={{ color: "var(--status-success)" }}>{counts.completed}</span>
          <span className="hud-label ml-2">DONE</span>
        </div>
        <div className="glass-l1 px-4 py-3 rounded-lg">
          <span className="mono-data font-medium" style={{ color: "var(--status-error)" }}>{counts.blocked}</span>
          <span className="hud-label ml-2">BLOCKED</span>
        </div>
      </div>

      {/* Task Tree */}
      <div className="glass-l1 rounded-xl overflow-hidden divide-y" style={{ borderColor: "var(--border-subtle)" }}>
        {SEED_TASKS.map((task) => <TaskRow key={task.id} task={task} />)}
      </div>
    </div>
  );
}
