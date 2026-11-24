"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface Project { id: string; title: string; status: string; budget: number; asset: string }

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try { setProjects(await apiRequest<Project[]>("/api/projects")); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load projects"); }
  }

  useEffect(() => { void load(); }, []);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/api/projects", { method: "POST", body: JSON.stringify({ title: form.get("title"), description: form.get("description"), required_skills: form.get("required_skills"), budget: Number(form.get("budget")), asset: "XLM", deadline: form.get("deadline") }) });
      event.currentTarget.reset();
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create project"); }
  }

  return (
    <main className="appShell"><aside className="sidebar"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><nav className="sidebarNav"><Link href="/dashboard">Overview</Link><Link href="/projects">Projects</Link></nav></aside><section className="appMain"><header className="appTopbar"><strong>Projects</strong><Link href="/dashboard">Workspace</Link></header><div className="appContent">
      <p className="eyebrow">Project directory</p><h1>Create and manage work.</h1>{error && <div className="error" role="alert">{error}</div>}
      <form className="walletBox" onSubmit={createProject} style={{ marginBottom: 24 }}><h2 style={{ marginTop: 0, fontSize: 18 }}>New project</h2><div className="field"><label htmlFor="title">Project title</label><input id="title" name="title" required /></div><div className="field"><label htmlFor="description">Description</label><textarea id="description" name="description" rows={3} required /></div><div className="field"><label htmlFor="required_skills">Required skills</label><input id="required_skills" name="required_skills" /></div><div className="field"><label htmlFor="budget">Budget (XLM)</label><input id="budget" name="budget" type="number" min="1" step="0.01" required /></div><div className="field"><label htmlFor="deadline">Deadline</label><input id="deadline" name="deadline" type="date" /></div><button className="button">Create project</button></form>
      {projects.length ? <table className="table"><thead><tr><th>Project</th><th>Status</th><th>Budget</th></tr></thead><tbody>{projects.map((project) => <tr key={project.id}><td>{project.title}</td><td>{project.status.replaceAll("_", " ")}</td><td>{project.budget} {project.asset}</td></tr>)}</tbody></table> : <div className="walletBox">No projects yet.</div>}
    </div></section></main>
  );
}
