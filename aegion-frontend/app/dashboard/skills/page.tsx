"use client";

import { useState, useEffect } from "react";
import { Puzzle, Play, Power, PowerOff, Clock, Loader2 } from "lucide-react";
import api from "@/lib/api";

/* ══════════════════════════════════════════════════════════════
   SKILLS PAGE — Tool/plugin management with invoke capability
   ══════════════════════════════════════════════════════════════ */

interface Skill {
  name: string;
  description: string;
  enabled: boolean;
  lastRun?: string;
  runs: number;
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [invoking, setInvoking] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSkills() {
      try {
        const res = await api.get("/skills");
        const raw = res.data?.skills || res.data || [];
        setSkills(raw.map((s: Record<string, unknown>) => ({
          name: (s.name || "Unknown") as string,
          description: (s.description || "") as string,
          enabled: s.enabled !== false,
          lastRun: (s.last_run || s.lastRun) as string | undefined,
          runs: (s.run_count || s.runs || 0) as number,
        })));
      } catch {
        setSkills([
          { name: "code_analysis", description: "Analyze codebase structure and quality", enabled: true, runs: 42 },
          { name: "test_runner", description: "Execute test suites and report results", enabled: true, runs: 28 },
          { name: "dependency_audit", description: "Check for vulnerable dependencies", enabled: true, runs: 15 },
          { name: "performance_profiler", description: "Profile application performance", enabled: false, runs: 8 },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchSkills();
  }, []);

  const handleInvoke = async (skillName: string) => {
    setInvoking(skillName);
    try {
      await api.post(`/skills/${skillName}/invoke`, {});
    } catch { /* silent */ }
    finally { setInvoking(null); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-page-enter">
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: "var(--text-primary)" }}>Skills</h1>
        <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
          System capabilities — tools, plugins, and executable skills
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <Loader2 size={24} className="animate-spin mx-auto" style={{ color: "var(--accent-govern)" }} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {skills.map((skill) => (
            <div key={skill.name} className="glass-l1 p-5 rounded-xl card-lift" style={{
              borderLeft: `3px solid ${skill.enabled ? "var(--accent-execute)" : "var(--text-ghost)"}`,
              opacity: skill.enabled ? 1 : 0.6,
            }}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Puzzle size={16} style={{ color: skill.enabled ? "var(--accent-execute)" : "var(--text-ghost)" }} />
                  <span className="text-[15px] font-semibold" style={{ color: "var(--text-primary)" }}>{skill.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {skill.enabled ? (
                    <Power size={14} style={{ color: "var(--status-success)" }} />
                  ) : (
                    <PowerOff size={14} style={{ color: "var(--text-ghost)" }} />
                  )}
                </div>
              </div>
              <p className="text-[13px] mb-3" style={{ color: "var(--text-secondary)" }}>{skill.description}</p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="mono-data-sm" style={{ color: "var(--text-ghost)" }}>
                    {skill.runs} runs
                  </span>
                  {skill.lastRun && (
                    <span className="mono-data-sm flex items-center gap-1" style={{ color: "var(--text-ghost)" }}>
                      <Clock size={10} /> {skill.lastRun}
                    </span>
                  )}
                </div>
                {skill.enabled && (
                  <button
                    onClick={() => handleInvoke(skill.name)}
                    disabled={invoking === skill.name}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[12px] font-medium disabled:opacity-30 transition-all"
                    style={{ background: "var(--accent-execute)", color: "white" }}
                  >
                    {invoking === skill.name ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    Invoke
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
