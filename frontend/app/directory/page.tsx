"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface Freelancer {
  id: string;
  full_name: string;
  title: string;
  description: string;
  skills: string;
  hourly_rate: number | null;
  available: boolean;
  portfolio_count: number;
}

export default function DirectoryPage() {
  const [freelancers, setFreelancers] = useState<Freelancer[]>([]);
  const [search, setSearch] = useState("");
  const [availableOnly, setAvailableOnly] = useState(false);
  const [sort, setSort] = useState("name");

  useEffect(() => {
    const query = new URLSearchParams();
    if (search) query.set("skill", search);
    if (availableOnly) query.set("available_only", "true");
    query.set("sort", sort);
    let active = true;
    apiRequest<Freelancer[]>(`/api/freelancers?${query.toString()}`)
      .then((items) => { if (active) setFreelancers(items); })
      .catch(() => { if (active) setFreelancers([]); });
    return () => { active = false; };
  }, [search, availableOnly, sort]);

  return (
    <AppShell title="Freelancer directory" subtitle="Verified work history">
      <p className="eyebrow">Discover talent</p>
      <h1>Find the right specialist.</h1>
      <div className="filterRow">
        <div className="field"><label htmlFor="search">Search by skill or title</label><input id="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="React, accessibility, copywriting..." /></div>
        <div className="field"><label htmlFor="sort">Sort</label><select id="sort" value={sort} onChange={(event) => setSort(event.target.value)}><option value="name">Name</option><option value="rate">Hourly rate</option></select></div>
        <label className="checkbox"><input type="checkbox" checked={availableOnly} onChange={(event) => setAvailableOnly(event.target.checked)} /> Available only</label>
      </div>
      {freelancers.length ? (
        <div className="metricGrid">{freelancers.map((freelancer) => (
          <article className="metric" key={freelancer.id}>
            <span>{freelancer.title || "Freelancer"}</span>
            <h2 style={{ fontSize: 18, marginBottom: 8 }}><Link href={`/directory/${freelancer.id}`} style={{ color: "var(--blue)" }}>{freelancer.full_name}</Link></h2>
            <p style={{ color: "var(--muted)", minHeight: 42 }}>{freelancer.description || "Public profile available."}</p>
            <strong>{freelancer.hourly_rate !== null ? `${freelancer.hourly_rate} XLM/hr` : "Project rate"}</strong>
            <p><span className="chip">{freelancer.available ? "Available" : "Booked"}</span> <span className="chip">{freelancer.portfolio_count} portfolio item(s)</span></p>
          </article>
        ))}</div>
      ) : <div className="walletBox">No profiles match this search. Try a broader term.</div>}
    </AppShell>
  );
}
