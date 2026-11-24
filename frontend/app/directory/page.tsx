"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface Freelancer { id: string; full_name: string; title: string; description: string; hourly_rate: number | null }

export default function DirectoryPage() {
  const [freelancers, setFreelancers] = useState<Freelancer[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    apiRequest<Freelancer[]>(`/api/freelancers${search ? `?skill=${encodeURIComponent(search)}` : ""}`).then(setFreelancers).catch(() => setFreelancers([]));
  }, [search]);

  return (
    <main className="appShell">
      <aside className="sidebar"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><nav className="sidebarNav"><Link href="/dashboard">Overview</Link><Link href="/directory">Freelancers</Link><Link href="/projects">Projects</Link></nav></aside>
      <section className="appMain"><header className="appTopbar"><strong>Freelancer directory</strong><Link href="/dashboard">Workspace</Link></header><div className="appContent">
        <p className="eyebrow">Discover talent</p><h1>Find the right specialist.</h1>
        <div className="field" style={{ maxWidth: 480 }}><label htmlFor="search">Search by skill or title</label><input id="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Brand, React, copywriting..." /></div>
        {freelancers.length ? <div className="metricGrid">{freelancers.map((freelancer) => <article className="metric" key={freelancer.id}><span>{freelancer.title}</span><h2 style={{ fontSize: 18, marginBottom: 8 }}>{freelancer.full_name}</h2><p style={{ color: "var(--muted)", minHeight: 42 }}>{freelancer.description || "Profile details available from their agreement."}</p><strong>{freelancer.hourly_rate ? `${freelancer.hourly_rate} XLM/hr` : "Project rate"}</strong></article>)}</div> : <div className="walletBox">No profiles match this search. Try a broader term.</div>}
      </div></section>
    </main>
  );
}
