"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  CircleAlert,
  ClipboardCheck,
  FileText,
  History,
  Plus,
  Send,
  ShieldCheck,
  Users,
  Wallet,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { splitMilestoneAmounts } from "@/lib/milestones";
import { PaymentIntentDetails, signAndSubmitPayment } from "@/lib/stellar";
import { Badge, EmptyState, Progress, SectionHeader, Skeleton, StatusBadge } from "./ui";

interface Project {
  id: string; title: string; description: string; required_skills: string;
  budget: number; asset: string; status: string; deadline: string | null;
  client_id: string; freelancer_id: string | null; agreement_id: string | null;
}
interface Milestone {
  id: string; title: string; description: string; amount: number; status: string;
  deliverable_url: string | null; review_feedback: string | null; submission_count: number; submitted_at: string | null;
}
interface Agreement {
  id: string; status: string; amount: number; description: string; version: number;
  client_id: string; freelancer_id: string; client_accepted: boolean; freelancer_accepted: boolean;
  milestones: Milestone[]; active_dispute_id: string | null;
}
interface Invitation { id: string; project_id: string; status: string; expires_at: string }
interface Activity { action: string; entity_type: string; details: string; actor_id: string; created_at: string }
interface Dispute { id: string; agreement_id: string; status: string; reason: string; resolution: string | null; proposed_by: string | null }
interface Freelancer { id: string; full_name: string; title: string }

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [me, setMe] = useState<{ id: string; role: string } | null>(null);
  const [freelancers, setFreelancers] = useState<Freelancer[]>([]);
  const [skill, setSkill] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [intent, setIntent] = useState<PaymentIntentDetails | null>(null);
  const [submittedHash, setSubmittedHash] = useState("");
  const [tab, setTab] = useState<"work" | "activity">("work");

  const load = useCallback(async () => {
    try {
      const [projectData, meData, invitationData, activityData, disputeData] = await Promise.all([
        apiRequest<Project>(`/api/projects/${projectId}`),
        apiRequest<{ id: string; role: string }>("/api/me"),
        apiRequest<Invitation[]>("/api/invitations"),
        apiRequest<Activity[]>(`/api/projects/${projectId}/activity`),
        apiRequest<Dispute[]>("/api/disputes"),
      ]);
      setProject(projectData);
      setMe(meData);
      setInvitations(invitationData.filter((item) => item.project_id === projectId));
      setActivity(activityData);
      setDisputes(disputeData.filter((item) => item.agreement_id === projectData.agreement_id));
      setAgreement(projectData.agreement_id ? await apiRequest<Agreement>(`/api/agreements/${projectData.agreement_id}`) : null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load project");
    }
  }, [projectId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    let active = true;
    apiRequest<Freelancer[]>(`/api/freelancers?skill=${encodeURIComponent(skill)}`).then((items) => { if (active) setFreelancers(items); }).catch(() => { if (active) setFreelancers([]); });
    return () => { active = false; };
  }, [skill]);

  async function act(operation: () => Promise<unknown>, success: string) {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); setNotice(success); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Action failed"); }
    finally { setBusy(false); }
  }

  function submitMilestone(milestoneId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void act(() => apiRequest(`/api/milestones/${milestoneId}/submit`, {
      method: "POST", body: JSON.stringify({ deliverable_url: data.get("deliverable_url") }),
    }), "Deliverable submitted for review.");
  }

  function reviewMilestone(milestoneId: string, approved: boolean) {
    void act(() => apiRequest(`/api/milestones/${milestoneId}/review?approved=${approved}`, {
      method: "POST", body: JSON.stringify({ feedback: approved ? "" : "Please revise the deliverable." }),
    }), approved ? "Milestone approved. Payment can be initiated." : "Revision requested.");
  }

  function createIntent(milestoneId: string) {
    void act(async () => {
      const result = await apiRequest<PaymentIntentDetails>("/api/payment-intents", {
        method: "POST", body: JSON.stringify({ milestone_id: milestoneId }),
      });
      setIntent(result); setSubmittedHash("");
    }, "Payment intent created. Review the details before signing.");
  }

  async function payWithFreighter() {
    if (!intent) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const submitted = await signAndSubmitPayment(intent);
      setSubmittedHash(submitted.hash);
      const result = await apiRequest<{ status: string; transaction_hash: string }>(
        `/api/payments/${submitted.hash}/confirm?milestone_id=${intent.milestone_id}&intent_id=${intent.id}`,
        { method: "POST" },
      );
      setNotice(`Payment verified on Stellar Testnet: ${result.transaction_hash}`);
      setIntent(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Payment was not completed");
    } finally { setBusy(false); }
  }

  if (!project || !me) return <div className="card cardBody">{error || <Skeleton lines={6} />}</div>;
  const isClient = me.role === "client";
  const isOwner = isClient && project.client_id === me.id;
  const isAssigned = !isClient && project.freelancer_id === me.id;
  const openDispute = disputes.find((item) => ["open", "under_review", "awaiting_counterparty"].includes(item.status));
  const milestones = agreement?.milestones || [];
  const paid = milestones.filter((m) => m.status === "payment_released").length;
  const progress = milestones.length ? (paid / milestones.length) * 100 : 0;

  return (
    <>
      <div className="pageHead">
        <div>
          <Link className="btn btn-ghost btn-sm" href="/projects">← All projects</Link>
          <h1 style={{ marginTop: 12 }}>{project.title}</h1>
          <p className="pageLead">{project.description}</p>
          <div className="badgeRow" style={{ marginTop: 12 }}>
            <StatusBadge status={project.status} />
            <Badge tone="primary">{project.budget.toLocaleString()} {project.asset}</Badge>
            {project.deadline && <Badge>Due {project.deadline}</Badge>}
            {openDispute && <Badge tone="danger"><span className="dot" /> Dispute open</Badge>}
          </div>
        </div>
      </div>

      {error && <div className="errorBox" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}

      <div className="tabs" role="tablist">
        <button className={`tab${tab === "work" ? " tabActive" : ""}`} onClick={() => setTab("work")} role="tab" aria-selected={tab === "work"}>Work</button>
        <button className={`tab${tab === "activity" ? " tabActive" : ""}`} onClick={() => setTab("activity")} role="tab" aria-selected={tab === "activity"}>Activity</button>
      </div>

      {tab === "work" ? (
        <div className="split">
          <div className="stack">
            {isOwner && !agreement && (
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Invite a freelancer</h2><p className="cardSubtitle">Search by skill and send an invitation.</p></div><Users size={17} /></div>
                <div className="cardBody">
                  <div className="field"><label className="label" htmlFor="skill-search">Skill search</label><input className="input" id="skill-search" value={skill} onChange={(event) => setSkill(event.target.value)} placeholder="React, design, writing…" /></div>
                  {freelancers.filter((item) => item.id !== project.freelancer_id).map((item) => (
                    <div className="rowBetween" key={item.id} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}>
                      <span><strong>{item.full_name}</strong> <span className="hint">{item.title || "Freelancer"}</span></span>
                      <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/projects/${projectId}/invitations`, { method: "POST", body: JSON.stringify({ freelancer_id: item.id }) }), "Invitation sent.")}>Invite</button>
                    </div>
                  ))}
                  {invitations.length > 0 && <div className="badgeRow" style={{ marginTop: 14 }}>{invitations.map((item) => <Badge key={item.id}>Invitation {item.id.slice(0, 8)}: {item.status}</Badge>)}</div>}
                </div>
              </section>
            )}

            {!isClient && invitations.some((item) => item.status === "sent") && (
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Your invitation</h2><p className="cardSubtitle">Respond to the project invitation.</p></div><Send size={17} /></div>
                <div className="cardBody">
                  {invitations.filter((item) => item.status === "sent").map((item) => (
                    <div className="rowBetween" key={item.id}>
                      <span>Pending · expires {new Date(item.expires_at).toLocaleDateString()}</span>
                      <div className="buttonRow">
                        <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/invitations/${item.id}/accept`, { method: "POST" }), "Invitation accepted.")}>Accept</button>
                        <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/invitations/${item.id}/reject`, { method: "POST" }), "Invitation declined.")}>Decline</button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {isOwner && project.freelancer_id && !agreement && (
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Create work agreement</h2><p className="cardSubtitle">Define scope and milestones in XLM.</p></div><FileText size={17} /></div>
                <form className="cardBody formGrid" onSubmit={(event) => {
                  event.preventDefault();
                  const data = new FormData(event.currentTarget);
                  const titles = String(data.get("milestone_titles") || "").split(",").map((item) => item.trim()).filter(Boolean);
                  const total = Number(data.get("amount"));
                  const amounts = splitMilestoneAmounts(total, titles);
                  void act(() => apiRequest(`/api/projects/${projectId}/agreements`, {
                    method: "POST",
                    body: JSON.stringify({
                      freelancer_id: project.freelancer_id, amount: total, asset: "XLM", description: data.get("description"),
                      milestones: titles.map((title, index) => ({ title, description: title, amount: Number(amounts[index]) })),
                    }),
                  }), "Agreement created and awaiting acceptance.");
                }}>
                  <div className="field"><label className="label" htmlFor="agreement-amount">Amount (XLM)</label><input className="input" id="agreement-amount" name="amount" type="number" min="1" step="0.01" defaultValue={project.budget} required /></div>
                  <div className="field"><label className="label" htmlFor="milestone-titles">Milestones (comma separated)</label><input className="input" id="milestone-titles" name="milestone_titles" defaultValue="Discovery, Delivery" required /></div>
                  <div className="field fieldWide"><label className="label" htmlFor="agreement-description">Scope of work</label><textarea className="textarea" id="agreement-description" name="description" rows={3} defaultValue={project.description} required /></div>
                  <div className="fieldWide"><button className="btn btn-primary">Create agreement <ArrowRight size={15} /></button></div>
                </form>
              </section>
            )}

            {agreement && (
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Work agreement · v{agreement.version}</h2><p className="cardSubtitle">{agreement.description}</p></div><StatusBadge status={agreement.status} /></div>
                <div className="cardBody">
                  <div className="badgeRow"><Badge tone={agreement.client_accepted ? "success" : "warning"}>Client: {agreement.client_accepted ? "accepted" : "pending"}</Badge><Badge tone={agreement.freelancer_accepted ? "success" : "warning"}>Freelancer: {agreement.freelancer_accepted ? "accepted" : "pending"}</Badge><Badge tone="primary">{agreement.amount} {project.asset}</Badge></div>
                  <div className="buttonRow">
                    {agreement.status === "pending_acceptance" && (agreement.client_id === me.id || agreement.freelancer_id === me.id) && <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/agreements/${agreement.id}/accept`, { method: "POST" }), "Agreement accepted.")}>Accept agreement</button>}
                    {!isClient && agreement.status === "pending_acceptance" && <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/agreements/${agreement.id}/reject`, { method: "POST" }), "Agreement rejected.")}>Reject</button>}
                    {!openDispute && agreement.status !== "cancelled" && (agreement.client_id === me.id || agreement.freelancer_id === me.id) && <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/agreements/${agreement.id}/cancel`, { method: "POST" }), "Agreement cancelled.")}>Cancel</button>}
                  </div>

                  <div style={{ marginTop: 22 }}>
                    <SectionHeader title="Milestones" subtitle={`${paid} of ${milestones.length} payments verified`} action={<Progress value={progress} />} />
                    {milestones.length ? milestones.map((milestone) => (
                      <article className="milestoneItem" key={milestone.id}>
                        <div className="milestoneHead"><div><h3>{milestone.title}</h3><p className="cardSubtitle">{milestone.description}</p></div><StatusBadge status={milestone.status} /></div>
                        <div className="badgeRow" style={{ marginTop: 10 }}><Badge tone="primary">{milestone.amount} XLM</Badge><Badge>{milestone.submission_count} submission(s)</Badge>{milestone.status === "payment_released" && <Badge tone="success"><ShieldCheck size={12} /> Verified</Badge>}</div>
                        {milestone.deliverable_url && <p style={{ marginTop: 10 }}>Deliverable: <a href={milestone.deliverable_url} target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>{milestone.deliverable_url}</a></p>}
                        {milestone.review_feedback && <div className="errorBox" style={{ marginTop: 10 }}>Feedback: {milestone.review_feedback}</div>}
                        {isAssigned && agreement.status === "active" && ["not_started", "in_progress", "revision_requested"].includes(milestone.status) && (
                          <form className="rowGap" style={{ marginTop: 12 }} onSubmit={(event) => submitMilestone(milestone.id, event)}>
                            <input className="input" name="deliverable_url" placeholder="https://example.com/deliverable" required />
                            <button className="btn btn-primary btn-sm" disabled={busy}>Submit work</button>
                          </form>
                        )}
                        {isAssigned && milestone.status === "not_started" && agreement.status === "active" && <button className="btn btn-secondary btn-sm" style={{ marginTop: 10 }} disabled={busy} onClick={() => void act(() => apiRequest(`/api/milestones/${milestone.id}/start`, { method: "POST" }), "Work started.")}>Start work</button>}
                        {isOwner && milestone.status === "submitted" && <div className="buttonRow"><button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/milestones/${milestone.id}/review-start`, { method: "POST" }), "Review started.")}>Start review</button><button className="btn btn-primary btn-sm" disabled={busy} onClick={() => reviewMilestone(milestone.id, true)}>Approve</button><button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => reviewMilestone(milestone.id, false)}>Request revision</button></div>}
                        {isOwner && milestone.status === "under_review" && <div className="buttonRow"><button className="btn btn-primary btn-sm" disabled={busy} onClick={() => reviewMilestone(milestone.id, true)}>Approve</button><button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => reviewMilestone(milestone.id, false)}>Request revision</button></div>}
                        {isOwner && milestone.status === "approved" && !openDispute && !intent && <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }} disabled={busy} onClick={() => createIntent(milestone.id)}>Initiate payment</button>}
                        {intent && intent.milestone_id === milestone.id && (
                          <div className="card" style={{ marginTop: 12, background: "var(--primary-soft)" }}>
                            <div className="cardBody">
                              <h3>Review before signing</h3>
                              <p className="mono">From {intent.source_account}</p><p className="mono">To {intent.destination_account}</p>
                              <p>Amount {intent.amount} {intent.asset} · Memo {intent.memo} · {intent.network}</p>
                              <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void payWithFreighter()}>Sign &amp; submit with Freighter</button>
                              {submittedHash && <p className="mono" style={{ marginTop: 10 }}>Submitted: {submittedHash}</p>}
                            </div>
                          </div>
                        )}
                      </article>
                    )) : <EmptyState icon={<ClipboardCheck size={19} />} title="No milestones yet" description="Milestones appear once an agreement is created." />}
                  </div>
                </div>
              </section>
            )}

            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Dispute management</h2><p className="cardSubtitle">Opening a dispute freezes approvals and payments.</p></div><CircleAlert size={17} /></div>
              <div className="cardBody">
                {openDispute && <div className="errorBox">An open dispute blocks approvals and payments until resolved.</div>}
                {agreement && !openDispute && (agreement.client_id === me.id || agreement.freelancer_id === me.id) && (
                  <form className="formGrid" onSubmit={(event) => {
                    event.preventDefault();
                    const data = new FormData(event.currentTarget);
                    void act(() => apiRequest("/api/disputes", { method: "POST", body: JSON.stringify({ agreement_id: agreement.id, milestone_id: milestones[0]?.id || null, reason: data.get("reason") }) }), "Dispute opened. Funds are frozen.");
                  }}>
                    <div className="field fieldWide"><label className="label" htmlFor="dispute-reason">Reason</label><textarea className="textarea" id="dispute-reason" name="reason" rows={2} minLength={10} required /></div>
                    <div className="fieldWide"><button className="btn btn-danger">Open dispute</button></div>
                  </form>
                )}
                {disputes.map((item) => (
                  <div className="milestoneItem" key={item.id}><div className="rowBetween"><strong>Dispute {item.id.slice(0, 8)}</strong><StatusBadge status={item.status} /></div><p>{item.reason}</p>
                    {item.status === "awaiting_counterparty" && item.proposed_by !== me.id && <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void act(() => apiRequest(`/api/disputes/${item.id}/accept`, { method: "POST", body: JSON.stringify({ resolution: item.resolution }) }), "Resolution accepted.")}>Accept: {item.resolution}</button>}
                  </div>
                ))}
              </div>
            </section>
          </div>

          <aside className="stack">
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Project facts</h2></div></div>
              <div className="cardBody stack" style={{ gap: 12 }}>
                <div className="receiptLine"><span className="hint">Budget</span><strong>{project.budget} {project.asset}</strong></div>
                <div className="receiptLine"><span className="hint">Skills</span><span>{project.required_skills || "—"}</span></div>
                <div className="receiptLine"><span className="hint">Deadline</span><span>{project.deadline || "—"}</span></div>
                <div className="receiptLine"><span className="hint">Client</span><span className="mono">{project.client_id.slice(0, 8)}</span></div>
                <div className="receiptLine"><span className="hint">Freelancer</span><span className="mono">{project.freelancer_id?.slice(0, 8) || "Unassigned"}</span></div>
              </div>
            </section>
            {isOwner && ["draft", "open", "invitation_sent", "awaiting_agreement", "active", "under_review"].includes(project.status) && (
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Edit details</h2></div></div>
                <form className="cardBody" onSubmit={(event) => {
                  event.preventDefault();
                  const data = new FormData(event.currentTarget);
                  void act(() => apiRequest(`/api/projects/${projectId}`, { method: "PUT", body: JSON.stringify({ title: data.get("title"), description: data.get("description"), required_skills: data.get("required_skills"), budget: Number(data.get("budget")), deadline: data.get("deadline") || null }) }), "Project updated.");
                }}>
                  <div className="field"><label className="label" htmlFor="edit-title">Title</label><input className="input" id="edit-title" name="title" defaultValue={project.title} required /></div>
                  <div className="field"><label className="label" htmlFor="edit-budget">Budget</label><input className="input" id="edit-budget" name="budget" type="number" step="0.01" min="1" defaultValue={project.budget} required /></div>
                  <div className="field"><label className="label" htmlFor="edit-description">Description</label><textarea className="textarea" id="edit-description" name="description" rows={2} defaultValue={project.description} required /></div>
                  <div className="field"><label className="label" htmlFor="edit-skills">Skills</label><input className="input" id="edit-skills" name="required_skills" defaultValue={project.required_skills} /></div>
                  <div className="field"><label className="label" htmlFor="edit-deadline">Deadline</label><input className="input" id="edit-deadline" name="deadline" type="date" defaultValue={project.deadline || ""} /></div>
                  <button className="btn btn-secondary btn-sm">Save changes</button>
                </form>
              </section>
            )}
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Activity</h2></div><History size={17} /></div>
              <div className="cardBody"><ul className="timeline">{activity.length ? activity.map((item, index) => <li key={`${item.action}-${index}`}><strong>{item.action.replaceAll("_", " ")}</strong> · <span className="hint">{item.entity_type}</span> {item.details}<small>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small></li>) : <li className="hint">No activity yet.</li>}</ul></div>
            </section>
          </aside>
        </div>
      ) : (
        <section className="card"><div className="cardHeader"><h2 className="cardTitle">Full activity history</h2></div><div className="cardBody"><ul className="timeline">{activity.length ? activity.map((item, index) => <li key={`${item.action}-${index}`}><strong>{item.action.replaceAll("_", " ")}</strong> · <span className="hint">{item.entity_type}</span> {item.details}<small>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small></li>) : <li className="hint">No activity yet.</li>}</ul></div></section>
      )}
    </>
  );
}
