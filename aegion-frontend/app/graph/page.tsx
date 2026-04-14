import { ProjectGraph } from "@/components/graph/ProjectGraph";

export default function GraphPage() {
    return (
        <div className="p-8 h-full flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>Project Graph</h1>
                    <p style={{ color: "var(--text-secondary)" }}>Visualizing Decision Provenance &amp; Lineage</p>
                </div>
                <div className="flex gap-2">
                    <button
                        className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                        style={{
                            background: "hsla(260, 100%, 70%, 0.1)",
                            color: "var(--accent-reason)",
                            border: "1px solid hsla(260, 100%, 70%, 0.2)",
                        }}
                    >
                        Export Topology
                    </button>
                </div>
            </div>

            <div className="flex-1 min-h-0">
                <ProjectGraph />
            </div>
        </div>
    );
}
