"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface DashboardProject {
  id: string;
  title: string;
  status: string;
  budget: number;
  asset: string;
  deadline: string | null;
  updated_at: string | null;
}
interface DashboardPayment {
  id: string;
  transaction_hash: string;
  amount: number;
  status: string;
  confirmed_at: string | null;
}
interface DashboardData {
  user: { full_name: string; role: string; stellar_address: string | null };
  projects: { total: number; by_status: Record<string, number>; recent: DashboardProject[] };
  payments: { verified_count: number; verified_amount: number; asset: string; recent: DashboardPayment[] };
  pending_reviews: number;
  open_disputes: number;
  unread_notifications: number;
  activity: { action: string; entity_type: string; entity_id: string; details: string; created_at: string }[];
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<DashboardData>("/api/dashboard")
      .then(setData)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load dashboard"));
  }, []);

  const isClient = data?.user.role === "client";

  return (
    <AppShell title="Overview" subtitle={isClient ? "Client workspace" : "Freelancer workspace"}>
      <p className="eyebrow">Overview</p>
      <div className="appHeaderRow"><h1>Good to see you{data ? `, ${data.user.full_name}` : ""}.</h1>
        <Link className="textButton" href="/projects">Manage projects →</Link>
      </div>
      {error && <div className="error" role="alert">{error}</div>}
      {!data && !error && <p>Loading workspace data…</p>}
      {data && (
        <>
          <div className="metricGrid">
            <div className="metric"><span>Active projects</span><strong>{data.projects.by_status.active || 0}</strong></div>
            <div className="metric"><span>{isClient ? "Verified payments sent" : "Verified earnings"}</span><strong>{data.payments.verified_amount.toLocaleString()} {data.payments.asset}</strong></div>
            <div className="metric"><span>{isClient ? "Awaiting your review" : "Revisions requested"}</span><strong>{data.pending_reviews}</strong></div>
          </div>
          <div className="metricGrid" style={{ marginTop: 16 }}>
            <div className="metric"><span>Confirmed transactions</span><strong>{data.payments.verified_count}</strong></div>
            <div className="metric"><span>Open disputes</span><strong>{data.open_disputes}</strong></div>
            <div className="metric"><span>Unread notifications</span><strong>{data.unread_notifications}</strong></div>
          </div>

          <h2 style={{ marginTop: 32, fontSize: 18 }}>Recent projects</h2>
          {data.projects.recent.length ? (
            <table className="table"><thead><tr><th>Project</th><th>Status</th><th>Budget</th><th>Deadline</th></tr></thead><tbody>
              {data.projects.recent.map((project) => (
                <tr key={project.id}>
                  <td><Link href={`/projects/${project.id}`} style={{ color: "var(--blue)", fontWeight: 700 }}>{project.title}</Link></td>
                  <td>{project.status.replaceAll("_", " ")}</td>
                  <td>{project.budget.toLocaleString()} {project.asset}</td>
                  <td>{project.deadline || "—"}</td>
                </tr>
              ))}
            </tbody></table>
          ) : <div className="walletBox">No projects yet. <Link href="/projects" style={{ color: "var(--blue)", fontWeight: 800 }}>Create or review a project.</Link></div>}

          <h2 style={{ marginTop: 32, fontSize: 18 }}>Verified payment activity</h2>
          {data.payments.recent.length ? (
            <table className="table"><thead><tr><th>Amount</th><th>Transaction hash</th><th>Confirmed</th></tr></thead><tbody>
              {data.payments.recent.map((payment) => (
                <tr key={payment.id}>
                  <td>{payment.amount} {data.payments.asset}</td>
                  <td className="mono">{payment.transaction_hash}</td>
                  <td>{payment.confirmed_at ? new Date(payment.confirmed_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody></table>
          ) : <div className="walletBox">No independently verified payments yet.</div>}

          <h2 style={{ marginTop: 32, fontSize: 18 }}>Recent activity</h2>
          {data.activity.length ? (
            <ul className="activityList">{data.activity.map((item, index) => (
              <li key={`${item.entity_id}-${index}`}><strong>{item.action.replaceAll("_", " ")}</strong> · {item.entity_type} {item.details}<small>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small></li>
            ))}</ul>
          ) : <div className="walletBox">No activity recorded yet.</div>}
        </>
      )}
    </AppShell>
  );
}
