"use client";

import Link from "next/link";
import type { ReactNode } from "react";

interface AppShellProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
}

const navigation = [
  { href: "/dashboard", label: "Overview" },
  { href: "/projects", label: "Projects" },
  { href: "/directory", label: "Freelancers" },
  { href: "/payments", label: "Payments" },
  { href: "/disputes", label: "Disputes" },
  { href: "/wallet", label: "Stellar wallet" },
  { href: "/notifications", label: "Notifications" },
  { href: "/profile", label: "Profile" },
];

export default function AppShell({ title, subtitle, children }: AppShellProps) {
  return (
    <main className="appShell">
      <aside className="sidebar">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <nav className="sidebarNav" aria-label="Workspace">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}>{item.label}</Link>
          ))}
        </nav>
      </aside>
      <section className="appMain">
        <header className="appTopbar"><strong>{title}</strong><span>{subtitle || "Stellar Testnet"}</span></header>
        <div className="appContent">{children}</div>
      </section>
    </main>
  );
}
