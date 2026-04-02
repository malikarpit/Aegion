"use client";

import { Puzzle, Play, Power, PowerOff, Clock } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MOCK_SKILLS } from "@/lib/mock-data";
import { formatDistanceToNow } from "date-fns";

export default function SkillsPage() {
    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Skills</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Installed automation skills and their execution status
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {MOCK_SKILLS.map((skill) => (
                    <div key={skill.id} className="glass-card p-6">
                        <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center gap-3">
                                <div className={`p-2.5 rounded-xl ${skill.status === "active" ? "bg-emerald-500/10" : "bg-white/5"}`}>
                                    <Puzzle size={18} className={skill.status === "active" ? "text-emerald-400" : "text-slate-500"} />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">{skill.name}</h3>
                                    <Badge
                                        variant={skill.status === "active" ? "success" : "neutral"}
                                        size="sm"
                                        dot
                                        pulse={skill.status === "active"}
                                    >
                                        {skill.status}
                                    </Badge>
                                </div>
                            </div>
                        </div>

                        <p className="text-xs text-slate-400 leading-relaxed mb-4">
                            {skill.description}
                        </p>

                        <div className="flex items-center gap-2 mb-4">
                            {skill.triggers.map((t) => (
                                <span key={t} className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-slate-500 font-mono">
                                    {t}
                                </span>
                            ))}
                        </div>

                        <div className="flex items-center justify-between pt-3 border-t border-white/5">
                            <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                                <Clock size={12} />
                                Last run: {formatDistanceToNow(new Date(skill.lastRun), { addSuffix: true })}
                            </div>
                            <div className="flex gap-2">
                                <Button variant="ghost" size="sm">
                                    {skill.status === "active" ? <PowerOff size={14} /> : <Power size={14} />}
                                </Button>
                                <Button variant="secondary" size="sm" icon={<Play size={12} />}>
                                    Run
                                </Button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
