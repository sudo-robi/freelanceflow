"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, BriefcaseBusiness, CalendarCheck, MapPin } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { Avatar, Badge, EmptyState, Skeleton } from "@/components/ui";

interface Freelancer {
  id: string; full_name: string; title: string; description: string; skills: string;
  hourly_rate: number | null; project_rate: number | null; available: boolean;
  availability_note: string; portfolio: { id: string; title: string; url: string; description: string }[];
}
interface Project { id: string; title: string; status: string }

export default function FreelancerProfilePage() {
  const params = useParams<{ id: string }>();
  const [profile, setProfile] = useState<Freelancer | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<Freelancer>(`/api/freelancers/${params.id}`),
      apiRequest<Project[]>("/api/projects"),
    ]).then(([data, list]) => { if (active) { setProfile(data); setProjects(list); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to load profile"); });
    return () => { active = false; };
  }, [params.id]);

  async function invite(projectId: string) {
    setError("");
    try {
      await apiRequest(`/api/projects/${projectId}/invitations`, { method: "POST", body: JSON.stringify({ freelancer_id: params.id }) });
      window.location.href = `/projects/${projectId}`;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invitation failed");
    }
  }

  const eligible = projects.filter((item) => ["draft", "open", "invitation_sent"].includes(item.status));

  return (
    <AppShell title="Freelancer profile" subtitle="Directory">
      <div className="pageHead"><div><Link className="btn btn-ghost btn-sm" href="/directory">← Directory</Link><h1 style={{ marginTop: 12 }}>{profile?.full_name || "Freelancer profile"}</h1></div></div>
      {error && <div className="errorBox" role="alert">{error}</div>}
      {!profile && !error && <div className="card cardBody"><Skeleton lines={5} /></div>}
      {profile && (
        <div className="split">
          <div className="stack">
            <section className="card">
              <div className="cardBody">
                <div className="avatarCard"><Avatar name={profile.full_name} large /><div><h2>{profile.title || "Freelancer"}</h2><p className="cardSubtitle">{profile.description || "No description provided."}</p></div></div>
                <div className="badgeRow" style={{ marginTop: 18 }}><Badge tone={profile.available ? "success" : "warning"}>{profile.available ? "Available for work" : "Not available"}</Badge>{profile.hourly_rate !== null && <Badge tone="primary">{profile.hourly_rate} XLM/hr</Badge>}{profile.project_rate !== null && <Badge>{profile.project_rate} XLM project</Badge>}</div>
              </div>
            </section>
            <section className="card">
              <div className="cardHeader"><h2 className="cardTitle">Skills &amp; availability</h2></div>
              <div className="cardBody stack" style={{ gap: 12 }}>
                <p><strong>Skills</strong><br /><span className="hint">{profile.skills || "Not specified"}</span></p>
                <p><strong>Availability</strong><br /><span className="hint">{profile.availability_note || (profile.available ? "Open to new projects" : "Currently booked")}</span></p>
              </div>
            </section>
            <section className="card">
              <div className="cardHeader"><h2 className="cardTitle">Portfolio</h2><Badge>{profile.portfolio.length} item(s)</Badge></div>
              <div className="cardBody">
                {profile.portfolio.length ? profile.portfolio.map((item) => (
                  <div className="portfolioItem" key={item.id}><strong>{item.title}</strong><a href={item.url} target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>{item.url} <ArrowRight size={13} /></a><p className="hint">{item.description}</p></div>
                )) : <EmptyState icon={<BriefcaseBusiness size={19} />} title="No public portfolio items" description="This freelancer has not added portfolio work yet." />}
              </div>
            </section>
          </div>
          <aside className="card">
            <div className="cardHeader"><div><h2 className="cardTitle">Invite to a project</h2><p className="cardSubtitle">Only editable projects are shown.</p></div></div>
            <div className="cardBody stack" style={{ gap: 10 }}>
              {eligible.length ? eligible.map((item) => (
                <div className="rowBetween" key={item.id}><span><strong>{item.title}</strong><br /><small>{item.status.replaceAll("_", " ")}</small></span><button className="btn btn-primary btn-sm" onClick={() => void invite(item.id)}>Invite <ArrowRight size={14} /></button></div>
              )) : <EmptyState icon={<CalendarCheck size={19} />} title="No eligible projects" description="Create a project first, then invite this freelancer." action={<Link className="btn btn-primary btn-sm" href="/projects">Create project</Link>} />}
            </div>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
