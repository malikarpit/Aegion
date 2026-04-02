import { ProjectGraph } from "@/components/graph/ProjectGraph";

export default function GraphPage() {
    return (
        <div className="p-8 h-full flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white">Project Graph</h1>
                    <p className="text-slate-400">Visualizing Decision Provenance & Lineage</p>
                </div>
                <div className="flex gap-2">
                    <button className="px-4 py-2 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-lg hover:bg-blue-600/30 transition-colors text-sm font-medium">
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
