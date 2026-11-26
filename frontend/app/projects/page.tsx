"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowRight, FolderKanban, Plus, Search, X } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { EmptyState, Skeleton, StatusBadge } from "@/components/ui";

interface Project { id: string; title: string; status: string; budget: number; asset: string }

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [role, setRole] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [creating, setCreating] = useState(false);

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
    } finally {
      setLoading(false);
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
      setCreating(false);
      window.location.href = `/projects/${created.id}`;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create project");
    }
  }

  const filtered = useMemo(() => projects.filter((project) => {
    const matchesQuery = `${project.title} ${project.status}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (status === "all" || project.status === status);
  }), [projects, query, status]);
  const statuses = useMemo(() => ["all", ...Array.from(new Set(projects.map((p) => p.status)))], [projects]);

  return (
    <AppShell title="Projects" subtitle="Workspaces">
      <div className="pageHead">
        <div>
          <p className="eyebrow">Project workspace</p>
          <h1>Projects</h1>
          <p className="pageLead">Create work, invite collaborators and follow every milestone in one place.</p>
        </div>
        {role === "client" && <button className="btn btn-primary" onClick={() => setCreating((value) => !value)}>{creating ? <><X size={16} /> Close</> : <><Plus size={16} /> New project</>}</button>}
      </div>

      {error && <div className="errorBox" role="alert">{error}</div>}
      {loading && <div className="card cardBody"><Skeleton lines={4} /></div>}

      {creating && role === "client" && (
        <section className="card" style={{ marginBottom: 24 }}>
          <div className="cardHeader"><div><h2 className="cardTitle">New project</h2><p className="cardSubtitle">Describe the work and set a budget in XLM.</p></div></div>
          <form className="cardBody formGrid" onSubmit={(event) => void createProject(event)}>
            <div className="field"><label className="label" htmlFor="title">Title</label><input className="input" id="title" name="title" required /></div>
            <div className="field"><label className="label" htmlFor="budget">Budget (XLM)</label><input className="input" id="budget" name="budget" type="number" min="1" step="0.01" required /></div>
            <div className="field fieldWide"><label className="label" htmlFor="description">Description</label><textarea className="textarea" id="description" name="description" rows={3} required /></div>
            <div className="field"><label className="label" htmlFor="required_skills">Required skills</label><input className="input" id="required_skills" name="required_skills" placeholder="React, design, writing…" /></div>
            <div className="field"><label className="label" htmlFor="deadline">Deadline</label><input className="input" id="deadline" name="deadline" type="date" /></div>
            <div className="fieldWide"><button className="btn btn-primary">Create project <ArrowRight size={15} /></button></div>
          </form>
        </section>
      )}

      {!loading && (
        <>
          <div className="filterBar">
            <div className="field"><label className="label" htmlFor="project-search"><Search size={13} /> Search</label><input className="input" id="project-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects…" /></div>
            <div className="field"><label className="label" htmlFor="status-filter">Status</label><select className="select" id="status-filter" value={status} onChange={(event) => setStatus(event.target.value)}>{statuses.map((item) => <option key={item} value={item}>{item === "all" ? "All statuses" : item.replaceAll("_", " ")}</option>)}</select></div>
          </div>

          {filtered.length ? (
            <div className="tableWrap"><table className="dataTable"><thead><tr><th>Project</th><th>Status</th><th>Budget</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>
              {filtered.map((project) => (
                <tr key={project.id}>
                  <td><strong>{project.title}</strong></td>
                  <td><StatusBadge status={project.status} /></td>
                  <td>{project.budget.toLocaleString()} {project.asset}</td>
                  <td><Link className="btn btn-secondary btn-sm" href={`/projects/${project.id}`}>Open <ArrowRight size={14} /></Link></td>
                </tr>
              ))}
            </tbody></table></div>
          ) : <EmptyState icon={<FolderKanban size={20} />} title={projects.length ? "No matching projects" : "No projects yet"} description={projects.length ? "Try a different search or status." : role === "client" ? "Create a project to start collaborating." : "You will see projects you are invited to here."} />}
        </>
      )}
    </AppShell>
  );
}
