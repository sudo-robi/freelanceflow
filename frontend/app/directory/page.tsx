"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Search, SlidersHorizontal, UserRoundSearch } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { Avatar, Badge, EmptyState, Skeleton } from "@/components/ui";

interface Freelancer {
  id: string; full_name: string; title: string; description: string; skills: string;
  hourly_rate: number | null; available: boolean; availability_note: string; portfolio_count: number;
}

export default function DirectoryPage() {
  const [freelancers, setFreelancers] = useState<Freelancer[]>([]);
  const [search, setSearch] = useState("");
  const [availableOnly, setAvailableOnly] = useState(false);
  const [sort, setSort] = useState("name");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const query = new URLSearchParams();
    if (search) query.set("skill", search);
    if (availableOnly) query.set("available_only", "true");
    query.set("sort", sort);
    let active = true;
    setLoading(true);
    apiRequest<Freelancer[]>(`/api/freelancers?${query.toString()}`)
      .then((items) => { if (active) setFreelancers(items); })
      .catch(() => { if (active) setFreelancers([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [search, availableOnly, sort]);

  return (
    <AppShell title="Discover" subtitle="Freelancer directory">
      <div className="pageHead">
        <div>
          <p className="eyebrow">Talent directory</p>
          <h1>Find the right specialist.</h1>
          <p className="pageLead">Real profiles, real skills and real portfolio items — no fabricated ratings.</p>
        </div>
      </div>

      <div className="filterBar">
        <div className="field"><label className="label" htmlFor="search"><Search size={13} /> Skill or title</label><input className="input" id="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="React, accessibility, copywriting…" /></div>
        <div className="field"><label className="label" htmlFor="sort"><SlidersHorizontal size={13} /> Sort</label><select className="select" id="sort" value={sort} onChange={(event) => setSort(event.target.value)}><option value="name">Name</option><option value="rate">Hourly rate</option></select></div>
        <label className="checkboxField"><input type="checkbox" checked={availableOnly} onChange={(event) => setAvailableOnly(event.target.checked)} /> Available only</label>
      </div>

      {loading ? <div className="card cardBody"><Skeleton lines={5} /></div> : freelancers.length ? (
        <div className="metricGrid">
          {freelancers.map((freelancer) => (
            <article className="metricCard" key={freelancer.id}>
              <div className="avatarCard"><Avatar name={freelancer.full_name} /><div><h3><Link href={`/directory/${freelancer.id}`} style={{ color: "var(--primary)" }}>{freelancer.full_name}</Link></h3><span className="hint">{freelancer.title || "Freelancer"}</span></div></div>
              <p className="hint" style={{ minHeight: 42, margin: "8px 0" }}>{freelancer.description || "Profile details available on request."}</p>
              <div className="badgeRow"><Badge tone={freelancer.available ? "success" : "neutral"}>{freelancer.available ? "Available" : "Booked"}</Badge><Badge>{freelancer.portfolio_count} portfolio item(s)</Badge></div>
              <div className="rowBetween" style={{ marginTop: 12 }}><strong>{freelancer.hourly_rate !== null ? `${freelancer.hourly_rate} XLM/hr` : "Project rate"}</strong><Link className="btn btn-ghost btn-sm" href={`/directory/${freelancer.id}`}>View profile <ArrowRight size={14} /></Link></div>
            </article>
          ))}
        </div>
      ) : <EmptyState icon={<UserRoundSearch size={20} />} title="No matching profiles" description="Try a broader search term or clear the availability filter." />}
    </AppShell>
  );
}
