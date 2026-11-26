"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import {
  Bell,
  CreditCard,
  FolderKanban,
  LayoutDashboard,
  Search,
  Settings2,
  ShieldAlert,
  WalletCards,
} from "lucide-react";
import { Avatar } from "./ui";

interface AppShellProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
}

const navigation = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/directory", label: "Discover", icon: Search },
  { href: "/payments", label: "Payments", icon: CreditCard },
  { href: "/disputes", label: "Disputes", icon: ShieldAlert },
  { href: "/wallet", label: "Wallet", icon: WalletCards },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/profile", label: "Profile", icon: Settings2 },
];

export default function AppShell({ title, subtitle, children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <main className="appShell">
      <aside className="sidebar" aria-label="Workspace navigation">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div>
          <p className="navSectionLabel">Workspace</p>
          <nav className="sidebarNav">
            {navigation.map((item) => {
              const active = pathname ? pathname === item.href || pathname.startsWith(`${item.href}/`) : false;
              const Icon = item.icon;
              return (
                <Link key={item.href} href={item.href} className={`navItem${active ? " navItemActive" : ""}`} aria-current={active ? "page" : undefined}>
                  <Icon size={17} />{item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="sidebarFooter">Stellar Testnet · Verified payments only</div>
      </aside>

      <section className="appMain">
        <header className="appHeader">
          <div className="headerContext">
            <span className="headerTitle">{title}</span>
            <span className="headerCrumb">FreelanceFlow / {subtitle || title}</span>
          </div>
          <div className="headerActions">
            <Link className="iconBtn" href="/notifications" aria-label="Notifications"><Bell size={17} /></Link>
            <Link className="iconBtn" href="/wallet" aria-label="Wallet"><WalletCards size={17} /></Link>
            <Link href="/profile" aria-label="Profile"><Avatar name="User" /></Link>
          </div>
        </header>

        <nav className="mobileNav" aria-label="Mobile navigation">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}>{item.label}</Link>
          ))}
        </nav>

        <div className="appContent">{children}</div>
      </section>
    </main>
  );
}
