import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
    return (
        <div className="flex items-center justify-center min-h-[60vh] p-8">
            <div className="text-center max-w-md">
                <div className="text-7xl font-bold gradient-text mb-4">404</div>
                <h2 className="text-xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>Page Not Found</h2>
                <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
                    The page you&apos;re looking for doesn&apos;t exist or has been moved.
                </p>
                <Link
                    href="/"
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all active:scale-[0.97]"
                    style={{
                        background: "var(--gradient-primary)",
                        color: "white",
                        boxShadow: "0 4px 20px hsla(260, 100%, 50%, 0.2)",
                    }}
                >
                    <Home size={16} />
                    Back to Dashboard
                </Link>
            </div>
        </div>
    );
}
