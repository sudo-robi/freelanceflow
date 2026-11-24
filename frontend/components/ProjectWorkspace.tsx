"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PaymentIntentDetails, signAndSubmitPayment } from "@/lib/stellar";

interface Project {
  id: string;
  title: string;
  description: string;
  required_skills: string;
  budget: number;
  asset: string;
  status: string;
  deadline: string | null;
  client_id: string;
  freelancer_id: string | null;
  agreement_id: string | null;
}
interface Milestone {
  id: string;
  title: string;
  description: string;
  amount: number;
  status: string;
  deliverable_url: string | null;
  review_feedback: string | null;
  submission_count: number;
  submitted_at: string | null;
}
interface Agreement {
  id: string;
  client_id: string;
  freelancer_id: string;
  status: string;
  amount: number;
  description: string;
  version: number;
  client_accepted: boolean;
  freelancer_accepted: boolean;
  milestones: Milestone[];
  active_dispute_id: string | null;
}
interface Invitation { id: string; project_id: string; status: string; expires_at: string }
interface Activity { action: string; entity_type: string; details: string; actor_id: string; created_at: string }
interface Dispute { id: string; agreement_id: string; status: string; reason: string; resolution: string | null; proposed_by: string | null }

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [me, setMe] = useState<{ id: string; role: string } | null>(null);
  const [freelancers, setFreelancers] = useState<{ id: string; full_name: string; title: string }[]>([]);
  const [skill, setSkill] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [intent, setIntent] = useState<PaymentIntentDetails | null>(null);
  const [submittedHash, setSubmittedHash] = useState("");

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
      setAgreement(
        projectData.agreement_id ? await apiRequest<Agreement>(`/api/agreements/${projectData.agreement_id}`) : null,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load project");
    }
  }, [projectId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    let active = true;
    apiRequest<{ id: string; full_name: string; title: string }[]>(`/api/freelancers?skill=${encodeURIComponent(skill)}`)
      .then((items) => { if (active) setFreelancers(items); })
      .catch(() => { if (active) setFreelancers([]); });
    return () => { active = false; };
  }, [skill]);

  async function act(operation: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await operation();
      setNotice(success);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitMilestone(milestoneId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await act(
      () => apiRequest(`/api/milestones/${milestoneId}/submit`, {
        method: "POST",
        body: JSON.stringify({ deliverable_url: data.get("deliverable_url") }),
      }),
      "Deliverable submitted for review.",
    );
  }

  async function reviewMilestone(milestoneId: string, approved: boolean) {
    await act(
      () => apiRequest(`/api/milestones/${milestoneId}/review?approved=${approved}`, {
        method: "POST",
        body: JSON.stringify({ feedback: approved ? "" : "Please revise the deliverable." }),
      }),
      approved ? "Milestone approved. Payment can now be initiated." : "Revision requested.",
    );
  }

  async function createIntent(milestoneId: string) {
    await act(async () => {
      const result = await apiRequest<PaymentIntentDetails>("/api/payment-intents", {
        method: "POST",
        body: JSON.stringify({ milestone_id: milestoneId }),
      });
      setIntent(result);
      setSubmittedHash("");
    }, "Payment intent created. Review the details, then sign with Freighter.");
  }

  async function payWithFreighter() {
    if (!intent) return;
    setBusy(true);
    setError("");
    setNotice("");
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
    } finally {
      setBusy(false);
    }
  }

  if (!project || !me) return <div>{error || "Loading project…"}</div>;
  const isClient = me.role === "client";
  const isOwner = isClient && project.client_id === me.id;
  const isAssigned = !isClient && project.freelancer_id === me.id;
  const openDispute = disputes.find((item) => ["open", "under_review", "awaiting_counterparty"].includes(item.status));

  return (
    <>
      <p className="eyebrow">Project</p>
      <div className="appHeaderRow"><h1>{project.title}</h1><Link className="textButton" href="/projects">← All projects</Link></div>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>{project.description}</p>
      <div className="chipRow">
        <span className="chip">Status: {project.status.replaceAll("_", " ")}</span>
        <span className="chip">Budget: {project.budget} {project.asset}</span>
        {project.deadline && <span className="chip">Deadline: {project.deadline}</span>}
        {project.freelancer_id && <span className="chip">Assigned freelancer: {project.freelancer_id.slice(0, 8)}</span>}
      </div>
      {error && <div className="error" role="alert" style={{ marginTop: 16 }}>{error}</div>}
      {notice && <div className="notice" role="status" style={{ marginTop: 16 }}>{notice}</div>}

      {isOwner && ["draft", "open", "invitation_sent", "awaiting_agreement", "active", "under_review"].includes(project.status) && (
        <section className="panel">
          <h2>Edit project details</h2>
          <form className="formGrid" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void act(() => apiRequest(`/api/projects/${projectId}`, {
              method: "PUT",
              body: JSON.stringify({
                title: data.get("title"),
                description: data.get("description"),
                required_skills: data.get("required_skills"),
                budget: Number(data.get("budget")),
                deadline: data.get("deadline") || null,
              }),
            }), "Project updated.");
          }}>
            <div className="field"><label htmlFor="edit-title">Title</label><input id="edit-title" name="title" defaultValue={project.title} required /></div>
            <div className="field"><label htmlFor="edit-budget">Budget (XLM)</label><input id="edit-budget" name="budget" type="number" step="0.01" min="1" defaultValue={project.budget} required /></div>
            <div className="field fieldWide"><label htmlFor="edit-description">Description</label><textarea id="edit-description" name="description" rows={2} defaultValue={project.description} required /></div>
            <div className="field"><label htmlFor="edit-skills">Required skills</label><input id="edit-skills" name="required_skills" defaultValue={project.required_skills} /></div>
            <div className="field"><label htmlFor="edit-deadline">Deadline</label><input id="edit-deadline" name="deadline" type="date" defaultValue={project.deadline || ""} /></div>
            <button className="button" disabled={busy}>Save changes</button>
          </form>
        </section>
      )}

      {isOwner && !agreement && (
        <section className="panel">
          <h2>Invite a freelancer</h2>
          <div className="field"><label htmlFor="skill-search">Search by skill</label><input id="skill-search" value={skill} onChange={(event) => setSkill(event.target.value)} placeholder="React, design, writing..." /></div>
          {freelancers.filter((item) => item.id !== project.freelancer_id).map((item) => (
            <div className="rowBetween" key={item.id}>
              <span><strong>{item.full_name}</strong> · {item.title || "Freelancer"}</span>
              <button className="button buttonSmall" disabled={busy} onClick={() => void act(
                () => apiRequest(`/api/projects/${projectId}/invitations`, {
                  method: "POST", body: JSON.stringify({ freelancer_id: item.id }),
                }),
                "Invitation sent.",
              )}>Invite</button>
            </div>
          ))}
          {invitations.length > 0 && <div className="chipRow">{invitations.map((item) => <span className="chip" key={item.id}>Invitation {item.id.slice(0, 8)}: {item.status}</span>)}</div>}
        </section>
      )}

      {!isClient && invitations.some((item) => item.status === "sent") && (
        <section className="panel">
          <h2>Your invitation</h2>
          {invitations.filter((item) => item.status === "sent").map((item) => (
            <div className="rowBetween" key={item.id}>
              <span>Pending invitation · expires {new Date(item.expires_at).toLocaleDateString()}</span>
              <span className="buttonRow">
                <button className="button buttonSmall" disabled={busy} onClick={() => void act(
                  () => apiRequest(`/api/invitations/${item.id}/accept`, { method: "POST" }), "Invitation accepted.",
                )}>Accept</button>
                <button className="button buttonSmall secondary" disabled={busy} onClick={() => void act(
                  () => apiRequest(`/api/invitations/${item.id}/reject`, { method: "POST" }), "Invitation declined.",
                )}>Decline</button>
              </span>
            </div>
          ))}
        </section>
      )}

      {isOwner && project.freelancer_id && !agreement && (
        <section className="panel">
          <h2>Create work agreement</h2>
          <form className="formGrid" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const milestoneTitles = String(data.get("milestone_titles") || "").split(",").map((item) => item.trim()).filter(Boolean);
            const total = Number(data.get("amount"));
            const share = total / Math.max(milestoneTitles.length, 1);
            void act(() => apiRequest(`/api/projects/${projectId}/agreements`, {
              method: "POST",
              body: JSON.stringify({
                freelancer_id: project.freelancer_id,
                amount: total,
                asset: "XLM",
                description: data.get("description"),
                milestones: milestoneTitles.map((title) => ({ title, description: title, amount: share })),
              }),
            }), "Agreement created and awaiting freelancer acceptance.");
          }}>
            <div className="field"><label htmlFor="agreement-amount">Amount (XLM)</label><input id="agreement-amount" name="amount" type="number" min="1" step="0.01" defaultValue={project.budget} required /></div>
            <div className="field"><label htmlFor="milestone-titles">Milestone titles (comma separated)</label><input id="milestone-titles" name="milestone_titles" defaultValue="Discovery, Delivery" required /></div>
            <div className="field fieldWide"><label htmlFor="agreement-description">Scope of work</label><textarea id="agreement-description" name="description" rows={3} defaultValue={project.description} required /></div>
            <button className="button" disabled={busy}>Create agreement</button>
          </form>
        </section>
      )}

      {agreement && (
        <section className="panel">
          <div className="appHeaderRow"><div><h2>Work agreement · v{agreement.version}</h2><p style={{ color: "var(--muted)" }}>{agreement.description}</p></div>
            <span className="chip">{agreement.status.replaceAll("_", " ")}</span></div>
          <p className="chipRow"><span className="chip">Client accepted: {agreement.client_accepted ? "yes" : "no"}</span><span className="chip">Freelancer accepted: {agreement.freelancer_accepted ? "yes" : "no"}</span><span className="chip">Amount: {agreement.amount} XLM</span></p>
          <div className="buttonRow">
            {(agreement.client_id === me.id || agreement.freelancer_id === me.id) && agreement.status === "pending_acceptance" && (
              <button className="button" disabled={busy} onClick={() => void act(
                () => apiRequest(`/api/agreements/${agreement.id}/accept`, { method: "POST" }), "Agreement accepted.",
              )}>Accept agreement</button>
            )}
            {!isClient && agreement.status === "pending_acceptance" && (
              <button className="button secondary" disabled={busy} onClick={() => void act(
                () => apiRequest(`/api/agreements/${agreement.id}/reject`, { method: "POST" }), "Agreement rejected.",
              )}>Reject agreement</button>
            )}
            {!openDispute && (agreement.client_id === me.id || agreement.freelancer_id === me.id) && agreement.status !== "cancelled" && (
              <button className="button secondary" disabled={busy} onClick={() => void act(
                () => apiRequest(`/api/agreements/${agreement.id}/cancel`, { method: "POST" }), "Agreement cancelled.",
              )}>Cancel agreement</button>
            )}
          </div>

          <h3 style={{ fontSize: 16 }}>Milestones</h3>
          {agreement.milestones.map((milestone) => (
            <div className="milestoneCard" key={milestone.id}>
              <div className="rowBetween"><strong>{milestone.title}</strong><span className="chip">{milestone.status.replaceAll("_", " ")}</span></div>
              <p style={{ color: "var(--muted)" }}>{milestone.description}</p>
              <small>{milestone.amount} XLM · {milestone.submission_count} submission(s)</small>
              {milestone.deliverable_url && <p>Deliverable: <a href={milestone.deliverable_url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>{milestone.deliverable_url}</a></p>}
              {milestone.review_feedback && <p className="error">Feedback: {milestone.review_feedback}</p>}
              {isAssigned && agreement.status === "active" && ["not_started", "in_progress", "revision_requested"].includes(milestone.status) && (
                <form className="rowGap" onSubmit={(event) => void submitMilestone(milestone.id, event)}>
                  <input name="deliverable_url" placeholder="https://example.com/deliverable" required />
                  <button className="button buttonSmall" disabled={busy}>Submit deliverable</button>
                </form>
              )}
              {isAssigned && milestone.status === "not_started" && agreement.status === "active" && (
                <button className="button buttonSmall secondary" disabled={busy} onClick={() => void act(
                  () => apiRequest(`/api/milestones/${milestone.id}/start`, { method: "POST" }), "Work started.",
                )}>Start work</button>
              )}
              {isOwner && milestone.status === "submitted" && (
                <div className="buttonRow">
                  <button className="button buttonSmall" disabled={busy} onClick={() => void act(
                    () => apiRequest(`/api/milestones/${milestone.id}/review-start`, { method: "POST" }), "Review started.",
                  )}>Start review</button>
                  <button className="button buttonSmall" disabled={busy} onClick={() => void reviewMilestone(milestone.id, true)}>Approve</button>
                  <button className="button buttonSmall secondary" disabled={busy} onClick={() => void reviewMilestone(milestone.id, false)}>Request revision</button>
                </div>
              )}
              {isOwner && milestone.status === "under_review" && (
                <div className="buttonRow">
                  <button className="button buttonSmall" disabled={busy} onClick={() => void reviewMilestone(milestone.id, true)}>Approve</button>
                  <button className="button buttonSmall secondary" disabled={busy} onClick={() => void reviewMilestone(milestone.id, false)}>Request revision</button>
                </div>
              )}
              {isOwner && milestone.status === "approved" && !openDispute && (
                <div className="buttonRow">
                  {!intent && <button className="button buttonSmall" disabled={busy} onClick={() => void createIntent(milestone.id)}>Initiate payment</button>}
                </div>
              )}
              {intent && intent.milestone_id === milestone.id && (
                <div className="intentBox">
                  <p><strong>Review before signing:</strong></p>
                  <p className="mono">From {intent.source_account}</p>
                  <p className="mono">To {intent.destination_account}</p>
                  <p>Amount {intent.amount} {intent.asset} · Memo {intent.memo} · Network {intent.network}</p>
                  <button className="button buttonSmall" disabled={busy} onClick={() => void payWithFreighter()}>Sign & submit with Freighter</button>
                </div>
              )}
              {milestone.status === "payment_released" && <p className="notice">Payment verified on Stellar Testnet.</p>}
            </div>
          ))}
        </section>
      )}

      <section className="panel">
        <h2>Disputes</h2>
        {openDispute && <p className="error">An open dispute blocks approvals and payments.</p>}
        {agreement && !openDispute && (agreement.client_id === me.id || agreement.freelancer_id === me.id) && (
          <form className="formGrid" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void act(() => apiRequest("/api/disputes", {
              method: "POST",
              body: JSON.stringify({
                agreement_id: agreement.id,
                milestone_id: agreement.milestones[0]?.id || null,
                reason: data.get("reason"),
              }),
            }), "Dispute opened. Funds are frozen.");
          }}>
            <div className="field fieldWide"><label htmlFor="dispute-reason">Reason for dispute</label><textarea id="dispute-reason" name="reason" rows={2} minLength={10} required /></div>
            <button className="button secondary" disabled={busy}>Open dispute</button>
          </form>
        )}
        {disputes.map((item) => (
          <div className="milestoneCard" key={item.id}>
            <div className="rowBetween"><strong>Dispute {item.id.slice(0, 8)}</strong><span className="chip">{item.status}</span></div>
            <p>{item.reason}</p>
            {item.status === "awaiting_counterparty" && item.proposed_by !== me.id && (
              <button className="button buttonSmall" disabled={busy} onClick={() => void act(
                () => apiRequest(`/api/disputes/${item.id}/accept`, {
                  method: "POST", body: JSON.stringify({ resolution: item.resolution }),
                }), "Resolution accepted.",
              )}>Accept resolution: {item.resolution}</button>
            )}
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Activity history</h2>
        {activity.length ? <ul className="activityList">{activity.map((item, index) => (
          <li key={`${item.action}-${index}`}><strong>{item.action.replaceAll("_", " ")}</strong> · {item.entity_type} {item.details}<small>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small></li>
        ))}</ul> : <p>No activity recorded yet.</p>}
      </section>
    </>
  );
}
