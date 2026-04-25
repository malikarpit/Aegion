import { StatusControls } from "@/components/admin/StatusControls";
import { DoctrineEditor } from "@/components/admin/DoctrineEditor";

export default function AdminPage() {
    return (
        <div className="p-8 h-full flex flex-col">
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>Mission Control</h1>
                <p style={{ color: "var(--text-secondary)" }}>System-wide Governance &amp; Emergency Protocols</p>
            </div>

            <StatusControls />

            <div className="flex-1 min-h-0 pb-6">
                <DoctrineEditor />
            </div>
        </div>
    );
}
