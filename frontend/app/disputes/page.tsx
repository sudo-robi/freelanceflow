"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface Dispute {
  id: string;
  agreement_id: string;
  milestone_id: string | null;
  reason: string;
  evidence_url: string | null;
  status: string;
  resolution: string | null;
  proposed_by: string | null;
  created_at: string;
  history: { action: string; details: string; created_at: string }[];
}
interface AgreementOption { id: string; project_id: string; status: string }

export default function DisputesPage() {
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [agreements, setAgreements] = useState<AgreementOption[]>([]);
  const [projects, setProjects] = useState<{ id: string; title: string }[]>([]);
  const [me, setMe] = useState<{ id: string } | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const [list, projectList, profile] = await Promise.all([
        apiRequest<Dispute[]>("/api/disputes"),
        apiRequest<{ id: string; title: string }[]>("/api/projects"),
        apiRequest<{ id: string }>("/api/me"),
      ]);
      setDisputes(list);
      setProjects(projectList);
      setMe(profile);
      const details = await Promise.all(projectList.map((item) => apiRequest<{ agreement_id: string | null; status: string }>(`/api/projects/${item.id}`)));
      setAgreements(details.flatMap((item, index) => item.agreement_id
        ? [{ id: item.agreement_id, project_id: projectList[index].id, status: item.status }]
        : []));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load disputes");
    }
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
    void act(() => apiRequest("/api/disputes", {
      method: "POST",
      body: JSON.stringify({
        agreement_id: data.get("agreement_id"),
        reason: data.get("reason"),
        evidence_url: data.get("evidence_url") || null,
      }),
    }), "Dispute opened. Funds are frozen until resolution.");
  }

  return (
    <AppShell title="Disputes" subtitle="No automatic release">
      <p className="eyebrow">Issue management</p>
      <h1>Disputes and resolutions.</h1>
      <p style={{ color: "var(--muted)" }}>Opening a dispute freezes approvals and payments. Resolving a dispute records a decision; funds still require an explicit, verified Stellar transaction.</p>
      {error && <div className="error" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}

      {agreements.length > 0 && (
        <section className="panel"><h2>Open a dispute</h2>
          <form className="formGrid" onSubmit={openDispute}>
            <div className="field"><label htmlFor="agreement">Agreement</label>
              <select id="agreement" name="agreement_id" required>
                {agreements.map((item) => <option key={item.id} value={item.id}>{projects.find((p) => p.id === item.project_id)?.title || item.project_id}</option>)}
              </select>
            </div>
            <div className="field fieldWide"><label htmlFor="reason">Reason</label><textarea id="reason" name="reason" rows={2} minLength={10} required /></div>
            <div className="field fieldWide"><label htmlFor="evidence">Evidence URL (optional)</label><input id="evidence" name="evidence_url" type="url" placeholder="https://..." /></div>
            <button className="button secondary">Open dispute</button>
          </form>
        </section>
      )}

      {disputes.length ? disputes.map((item) => (
        <section className="panel" key={item.id}>
          <div className="appHeaderRow"><div><h2>Dispute {item.id.slice(0, 8)}</h2><p>{item.reason}</p></div><span className="chip">{item.status}</span></div>
          <p><Link href={`/projects/${projects.find((p) => agreements.find((a) => a.id === item.agreement_id)?.project_id === p.id)?.id || ""}`} style={{ color: "var(--blue)" }}>Related project</Link></p>
          {item.evidence_url && <p>Evidence: <a href={item.evidence_url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>{item.evidence_url}</a></p>}
          {item.status === "awaiting_counterparty" && item.proposed_by !== me?.id && (
            <div className="buttonRow">
              {(["release_freelancer", "refund_client", "cancel_agreement"] as const).map((resolution) => (
                <button className="button buttonSmall" key={resolution} onClick={() => void act(
                  () => apiRequest(`/api/disputes/${item.id}/accept`, { method: "POST", body: JSON.stringify({ resolution }) }),
                  "Resolution accepted.",
                )}>Accept: {resolution.replaceAll("_", " ")}</button>
              ))}
            </div>
          )}
          {!["resolved", "rejected"].includes(item.status) && (
            <div className="buttonRow" style={{ marginTop: 12 }}>
              {(["release_freelancer", "refund_client", "cancel_agreement"] as const).map((resolution) => (
                <button className="button buttonSmall secondary" key={resolution} onClick={() => void act(
                  () => apiRequest(`/api/disputes/${item.id}/resolve`, { method: "POST", body: JSON.stringify({ resolution }) }),
                  "Resolution proposed to the counterparty.",
                )}>Propose: {resolution.replaceAll("_", " ")}</button>
              ))}
            </div>
          )}
          <ul className="activityList">{item.history.map((entry, index) => (
            <li key={`${entry.action}-${index}`}><strong>{entry.action.replaceAll("_", " ")}</strong> · {entry.details}<small>{new Date(entry.created_at).toLocaleString()}</small></li>
          ))}</ul>
        </section>
      )) : <div className="walletBox">No disputes recorded.</div>}
    </AppShell>
  );
}
