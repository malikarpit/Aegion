import { StatusControls } from "@/components/admin/StatusControls";
import { DoctrineEditor } from "@/components/admin/DoctrineEditor";

export default function AdminPage() {
    return (
        <div className="p-8 h-full flex flex-col">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Mission Control</h1>
                <p className="text-slate-400">System-wide Governance & Emergency Protocols</p>
            </div>

            <StatusControls />

            <div className="flex-1 min-h-0 pb-6">
                <DoctrineEditor />
            </div>
        </div>
    );
}
