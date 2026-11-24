"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
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
  project_rate: number | null;
  available: boolean;
  availability_note: string;
  portfolio: { id: string; title: string; url: string; description: string }[];
}
interface Project { id: string; title: string; status: string }

export default function FreelancerProfilePage() {
  const params = useParams<{ id: string }>();
  const [profile, setProfile] = useState<Freelancer | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<Freelancer>(`/api/freelancers/${params.id}`).then(setProfile).catch((cause) => {
      setError(cause instanceof Error ? cause.message : "Unable to load profile");
    });
    apiRequest<Project[]>("/api/projects").then(setProjects).catch(() => setProjects([]));
  }, [params.id]);

  async function invite(projectId: string) {
    setError("");
    try {
      await apiRequest(`/api/projects/${projectId}/invitations`, {
        method: "POST",
        body: JSON.stringify({ freelancer_id: params.id }),
      });
      setError("");
      window.location.href = `/projects/${projectId}`;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invitation failed");
    }
  }

  return (
    <AppShell title="Freelancer profile" subtitle="Public portfolio">
      <p className="eyebrow">Freelancer directory</p>
      <div className="appHeaderRow"><h1>{profile?.full_name || "Loading profile…"}</h1><Link className="textButton" href="/directory">← Directory</Link></div>
      {error && <div className="error" role="alert">{error}</div>}
      {profile && (
        <>
          <div className="chipRow"><span className="chip">{profile.title}</span><span className="chip">{profile.available ? "Available for work" : "Not available"}</span>
            {profile.hourly_rate !== null && <span className="chip">{profile.hourly_rate} XLM/hr</span>}
          </div>
          <section className="panel"><h2>About</h2><p>{profile.description || "No description provided."}</p>
            <p><strong>Skills:</strong> {profile.skills || "Not specified"}</p>
            <p><strong>Availability:</strong> {profile.availability_note || (profile.available ? "Open to projects" : "Currently booked")}</p>
          </section>
          <section className="panel"><h2>Portfolio</h2>
            {profile.portfolio.length ? profile.portfolio.map((item) => (
              <div className="portfolioItem" key={item.id}>
                <strong>{item.title}</strong>
                <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>{item.url}</a>
                <p>{item.description}</p>
              </div>
            )) : <p>No public portfolio items yet.</p>}
          </section>
          <section className="panel"><h2>Invite to a project</h2>
            {projects.filter((item) => ["draft", "open", "invitation_sent"].includes(item.status)).length ? (
              projects.filter((item) => ["draft", "open", "invitation_sent"].includes(item.status)).map((item) => (
                <div className="rowBetween" key={item.id}><span>{item.title}</span><button className="button buttonSmall" onClick={() => void invite(item.id)}>Invite</button></div>
              ))
            ) : <p>No editable projects available. Create a project first.</p>}
          </section>
        </>
      )}
    </AppShell>
  );
}
