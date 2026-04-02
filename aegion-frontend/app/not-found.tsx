import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
    return (
        <div className="flex items-center justify-center min-h-[60vh] p-8">
            <div className="text-center max-w-md">
                <div className="text-7xl font-bold gradient-text mb-4">404</div>
                <h2 className="text-xl font-bold text-white mb-2">Page Not Found</h2>
                <p className="text-sm text-slate-400 mb-8">
                    The page you&apos;re looking for doesn&apos;t exist or has been moved.
                </p>
                <Link
                    href="/"
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all active:scale-[0.97]"
                >
                    <Home size={16} />
                    Back to Dashboard
                </Link>
            </div>
        </div>
    );
}
