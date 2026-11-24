"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface Project { id: string; title: string; status: string; budget: number; asset: string }

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [role, setRole] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const [list, me] = await Promise.all([
        apiRequest<Project[]>("/api/projects"),
        apiRequest<{ role: string }>("/api/me"),
      ]);
      setProjects(list);
      setRole(me.role);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load projects");
    }
  }

  useEffect(() => { void load(); }, []);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const created = await apiRequest<{ id: string }>("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          title: data.get("title"),
          description: data.get("description"),
          required_skills: data.get("required_skills"),
          budget: Number(data.get("budget")),
          asset: "XLM",
          deadline: data.get("deadline") || null,
        }),
      });
      form.reset();
      await load();
      window.location.href = `/projects/${created.id}`;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create project");
    }
  }

  return (
    <AppShell title="Projects" subtitle="Agreements and milestones">
      <p className="eyebrow">Project directory</p>
      <div className="appHeaderRow"><h1>Create and manage work.</h1><Link className="textButton" href="/directory">Find freelancers →</Link></div>
      {error && <div className="error" role="alert">{error}</div>}
      {role === "client" && (
        <form className="walletBox" onSubmit={(event) => void createProject(event)} style={{ marginBottom: 24, maxWidth: 720 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>New project</h2>
          <div className="field"><label htmlFor="title">Project title</label><input id="title" name="title" required /></div>
          <div className="field"><label htmlFor="description">Description</label><textarea id="description" name="description" rows={3} required /></div>
          <div className="field"><label htmlFor="required_skills">Required skills</label><input id="required_skills" name="required_skills" /></div>
          <div className="field"><label htmlFor="budget">Budget (XLM)</label><input id="budget" name="budget" type="number" min="1" step="0.01" required /></div>
          <div className="field"><label htmlFor="deadline">Deadline</label><input id="deadline" name="deadline" type="date" /></div>
          <button className="button">Create project</button>
        </form>
      )}
      {projects.length ? (
        <table className="table"><thead><tr><th>Project</th><th>Status</th><th>Budget</th><th></th></tr></thead><tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td><strong>{project.title}</strong></td>
              <td>{project.status.replaceAll("_", " ")}</td>
              <td>{project.budget.toLocaleString()} {project.asset}</td>
              <td><Link href={`/projects/${project.id}`} style={{ color: "var(--blue)", fontWeight: 700 }}>Open →</Link></td>
            </tr>
          ))}
        </tbody></table>
      ) : <div className="walletBox">No projects yet.</div>}
    </AppShell>
  );
}
