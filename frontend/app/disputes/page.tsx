"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { CircleAlert, FileWarning, Scale } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { Badge, EmptyState, Skeleton, StatusBadge } from "@/components/ui";

interface Dispute {
  id: string; agreement_id: string; reason: string; evidence_url: string | null;
  status: string; resolution: string | null; proposed_by: string | null; created_at: string;
  history: { action: string; details: string; created_at: string }[];
}
interface AgreementOption { id: string; project_id: string }
interface Project { id: string; title: string }

const RESOLUTIONS = ["release_freelancer", "refund_client", "cancel_agreement"] as const;

export default function DisputesPage() {
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [agreements, setAgreements] = useState<AgreementOption[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [me, setMe] = useState<{ id: string } | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [list, projectList, profile] = await Promise.all([apiRequest<Dispute[]>("/api/disputes"), apiRequest<Project[]>("/api/projects"), apiRequest<{ id: string }>("/api/me")]);
      setDisputes(list); setProjects(projectList); setMe(profile);
      const details = await Promise.all(projectList.map((item) => apiRequest<{ agreement_id: string | null }>(`/api/projects/${item.id}`)));
      setAgreements(details.flatMap((item, index) => item.agreement_id ? [{ id: item.agreement_id, project_id: projectList[index].id }] : []));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load disputes"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function act(operation: () => Promise<unknown>, success: string) {
    setError(""); setNotice("");
    try { await operation(); setNotice(success); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Action failed"); }
  }

  function openDispute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void act(() => apiRequest("/api/disputes", { method: "POST", body: JSON.stringify({ agreement_id: data.get("agreement_id"), reason: data.get("reason"), evidence_url: data.get("evidence_url") || null }) }), "Dispute opened. Funds are frozen.");
  }

  return (
    <AppShell title="Disputes" subtitle="Issue management">
      <div className="pageHead">
        <div>
          <p className="eyebrow">Dispute centre</p>
          <h1>Disputes &amp; resolutions.</h1>
          <p className="pageLead">Opening a dispute freezes approvals and payments. Resolution never releases funds automatically.</p>
        </div>
      </div>
      {error && <div className="errorBox" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}
      {loading && <div className="card cardBody"><Skeleton lines={4} /></div>}

      {!loading && (
        <div className="stack">
          {agreements.length > 0 && (
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Open a dispute</h2><p className="cardSubtitle">Provide a clear reason and optional evidence link.</p></div><FileWarning size={17} /></div>
              <form className="cardBody formGrid" onSubmit={openDispute}>
                <div className="field"><label className="label" htmlFor="agreement">Agreement</label><select className="select" id="agreement" name="agreement_id" required>{agreements.map((item) => <option key={item.id} value={item.id}>{projects.find((p) => p.id === item.project_id)?.title || item.project_id}</option>)}</select></div>
                <div className="field fieldWide"><label className="label" htmlFor="reason">Reason</label><textarea className="textarea" id="reason" name="reason" rows={2} minLength={10} required /></div>
                <div className="field fieldWide"><label className="label" htmlFor="evidence">Evidence URL (optional)</label><input className="input" id="evidence" name="evidence_url" type="url" placeholder="https://…" /></div>
                <div className="fieldWide"><button className="btn btn-danger">Open dispute</button></div>
              </form>
            </section>
          )}

          {disputes.length ? disputes.map((item) => (
            <section className="card" key={item.id}>
              <div className="cardHeader"><div><h2 className="cardTitle">Dispute {item.id.slice(0, 8)}</h2><p className="cardSubtitle"><Link href="/projects" style={{ color: "var(--primary)" }}>Related project</Link></p></div><StatusBadge status={item.status} /></div>
              <div className="cardBody">
                <p>{item.reason}</p>
                {item.evidence_url && <p><a href={item.evidence_url} target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>{item.evidence_url}</a></p>}
                {item.status === "awaiting_counterparty" && item.proposed_by !== me?.id && (
                  <div className="badgeRow" style={{ marginTop: 12 }}>{RESOLUTIONS.map((resolution) => <button key={resolution} className="btn btn-primary btn-sm" disabled={!!error} onClick={() => void act(() => apiRequest(`/api/disputes/${item.id}/accept`, { method: "POST", body: JSON.stringify({ resolution }) }), "Resolution accepted.")}>Accept: {resolution.replaceAll("_", " ")}</button>)}</div>
                )}
                {!["resolved", "rejected"].includes(item.status) && (
                  <div className="badgeRow" style={{ marginTop: 12 }}>{RESOLUTIONS.map((resolution) => <button key={resolution} className="btn btn-secondary btn-sm" onClick={() => void act(() => apiRequest(`/api/disputes/${item.id}/resolve`, { method: "POST", body: JSON.stringify({ resolution }) }), "Proposal sent to counterparty.")}>Propose: {resolution.replaceAll("_", " ")}</button>)}</div>
                )}
                <ul className="timeline" style={{ marginTop: 18 }}>{item.history.map((entry, index) => <li key={`${entry.action}-${index}`}><strong>{entry.action.replaceAll("_", " ")}</strong> · <span className="hint">{entry.details}</span><small>{new Date(entry.created_at).toLocaleString()}</small></li>)}</ul>
              </div>
            </section>
          )) : <EmptyState icon={<Scale size={20} />} title="No disputes" description="Disputes and their resolution history will appear here." />}
        </div>
      )}
    </AppShell>
  );
}
