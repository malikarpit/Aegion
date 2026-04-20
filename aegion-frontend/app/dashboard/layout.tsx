import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    template: "%s | Aegion Dashboard",
    default: "Dashboard | Aegion",
  },
  description: "Aegion Cognitive Operating System — AI Governance Dashboard",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
