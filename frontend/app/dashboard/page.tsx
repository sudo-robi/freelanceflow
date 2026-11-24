"use client";

import Link from "next/link";
import { Bell, FolderKanban, LayoutDashboard, Search, WalletCards } from "lucide-react";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface Me { full_name: string; role: string }
interface Project { id: string; title: string; status: string; budget: number; asset: string }

export default function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      apiRequest<Me>("/api/me"),
      apiRequest<Project[]>("/api/projects"),
    ]).then(([profile, projectList]) => {
      setMe(profile);
      setProjects(projectList);
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load dashboard"));
  }, []);

  return (
    <main className="appShell">
      <aside className="sidebar"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><nav className="sidebarNav">
        <Link href="/dashboard"><LayoutDashboard size={17} />Overview</Link>
        <Link href="/projects"><FolderKanban size={17} />Projects</Link>
        <Link href="/directory"><Search size={17} />Freelancers</Link>
        <Link href="/wallet"><WalletCards size={17} />Stellar wallet</Link>
        <Link href="/notifications"><Bell size={17} />Notifications</Link>
      </nav></aside>
      <section className="appMain"><header className="appTopbar"><strong>{me?.role === "client" ? "Client workspace" : "Freelancer workspace"}</strong><span>{me?.full_name || "Loading..."}</span></header>
        <div className="appContent"><p className="eyebrow">Overview</p><h1>Good to see you.</h1>
          {error && <div className="error" role="alert">{error}</div>}
          <div className="metricGrid"><div className="metric"><span>Active projects</span><strong>{projects.filter((project) => project.status === "active").length}</strong></div><div className="metric"><span>Total project value</span><strong>{projects.reduce((sum, project) => sum + project.budget, 0).toLocaleString()} XLM</strong></div><div className="metric"><span>Pending reviews</span><strong>0</strong></div></div>
          <h2 style={{ marginTop: 32, fontSize: 18 }}>Recent projects</h2>
          {projects.length ? <table className="table"><thead><tr><th>Project</th><th>Status</th><th>Budget</th></tr></thead><tbody>{projects.map((project) => <tr key={project.id}><td><strong>{project.title}</strong></td><td>{project.status.replaceAll("_", " ")}</td><td>{project.budget.toLocaleString()} {project.asset}</td></tr>)}</tbody></table> : <div className="walletBox">No projects yet. <Link href="/projects" style={{ color: "var(--blue)", fontWeight: 800 }}>Create or review a project.</Link></div>}
        </div>
      </section>
    </main>
  );
}
