"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Banknote,
  CircleAlert,
  ClipboardCheck,
  FolderKanban,
  Inbox,
  Plus,
  Wallet,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { Badge, BarChart, EmptyState, Skeleton, StatCard, StatusBadge } from "@/components/ui";

interface RecentProject { id: string; title: string; status: string; budget: number; asset: string; deadline: string | null }
interface RecentPayment { id: string; transaction_hash: string; amount: number; status: string; confirmed_at: string | null }
interface Activity { action: string; entity_type: string; entity_id: string; details: string; created_at: string }
interface DashboardData {
  user: { full_name: string; role: string; stellar_address: string | null };
  projects: { total: number; by_status: Record<string, number>; recent: RecentProject[] };
  payments: { verified_count: number; verified_amount: number; asset: string; recent: RecentPayment[] };
  pending_reviews: number;
  open_disputes: number;
  unread_notifications: number;
  activity: Activity[];
}
interface FinanceReport { by_month: Record<string, number>; verified_payments: number; total_amount: number }

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [report, setReport] = useState<FinanceReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([apiRequest<DashboardData>("/api/dashboard"), apiRequest<FinanceReport>("/api/finance/report")])
      .then(([dashboard, finance]) => {
        if (!active) return;
        setData(dashboard);
        setReport(finance);
      })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to load dashboard"); });
    return () => { active = false; };
  }, []);

  const isClient = data?.user.role === "client";
  const firstName = data?.user.full_name.split(" ")[0] || "";
  const activeProjects = data?.projects.by_status.active || 0;
  const chartData = Object.entries(report?.by_month || {}).slice(-6).map(([label, value]) => ({ label: label.slice(5), value }));

  const nextAction = !data ? null
    : data.projects.total === 0
      ? { label: "Create your first project", href: "/projects" }
      : isClient && data.pending_reviews > 0
        ? { label: "Review submitted work", href: "/projects" }
        : !isClient && data.pending_reviews > 0
          ? { label: "Address revision requests", href: "/projects" }
          : data.projects.recent[0]
            ? { label: "Open latest project", href: `/projects/${data.projects.recent[0].id}` }
            : { label: "Explore freelancers", href: "/directory" };

  return (
    <AppShell title="Overview" subtitle={isClient ? "Client workspace" : "Freelancer workspace"}>
      <div className="pageHead">
        <div>
          <p className="eyebrow">Workspace overview</p>
          <h1>{firstName ? `Good to see you, ${firstName}.` : "Good to see you."}</h1>
          <p className="pageLead">A clear view of your agreements, deliverables and verified payments.</p>
        </div>
        {nextAction && <Link className="btn btn-primary" href={nextAction.href}>{nextAction.label} <ArrowRight size={16} /></Link>}
      </div>

      {error && <div className="errorBox" role="alert">{error}</div>}
      {!data && !error && <div className="card cardBody"><Skeleton lines={5} /></div>}

      {data && (
        <div className="stack">
          <div className="metricGrid">
            <StatCard
              label={isClient ? "Verified payments sent" : "Verified earnings"}
              value={`${data.payments.verified_amount.toLocaleString()} ${data.payments.asset}`}
              icon={<Banknote size={17} />}
              hint={`${data.payments.verified_count} confirmed transaction(s)`}
            />
            <StatCard label="Active projects" value={activeProjects} icon={<FolderKanban size={17} />} hint={`${data.projects.total} total`} />
            <StatCard label={isClient ? "Awaiting your review" : "Revisions requested"} value={data.pending_reviews} icon={<ClipboardCheck size={17} />} />
            <StatCard label="Open disputes" value={data.open_disputes} icon={<CircleAlert size={17} />} hint={`${data.unread_notifications} unread notification(s)`} />
          </div>

          <div className="split">
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Recent projects</h2><p className="cardSubtitle">Your latest work and its current state</p></div><Link className="btn btn-secondary btn-sm" href="/projects">All projects</Link></div>
              <div className="cardBody">
                {data.projects.recent.length ? (
                  <div className="tableWrap"><table className="dataTable"><thead><tr><th>Project</th><th>Status</th><th>Budget</th><th>Deadline</th></tr></thead><tbody>
                    {data.projects.recent.map((project) => (
                      <tr key={project.id}>
                        <td><Link href={`/projects/${project.id}`} style={{ color: "var(--primary)", fontWeight: 650 }}>{project.title}</Link></td>
                        <td><StatusBadge status={project.status} /></td>
                        <td>{project.budget.toLocaleString()} {project.asset}</td>
                        <td>{project.deadline || "—"}</td>
                      </tr>
                    ))}
                  </tbody></table></div>
                ) : <EmptyState icon={<FolderKanban size={19} />} title="No projects yet" description="Create a project or find a freelancer to get started." action={<Link className="btn btn-primary btn-sm" href="/projects"><Plus size={15} /> New project</Link>} />}
              </div>
            </section>

            <div className="stack">
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Payment activity</h2><p className="cardSubtitle">Verified monthly totals</p></div><Badge tone="success">Testnet</Badge></div>
                <div className="cardBody">
                  {chartData.length ? <BarChart data={chartData} /> : <EmptyState icon={<Wallet size={19} />} title="No verified payments" description="Confirmed transactions will appear here." />}
                </div>
              </section>
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Quick actions</h2><p className="cardSubtitle">What you can do next</p></div></div>
                <div className="cardBody stack" style={{ gap: 10 }}>
                  <Link className="btn btn-secondary" href="/projects"><FolderKanban size={16} /> Manage projects</Link>
                  <Link className="btn btn-secondary" href={isClient ? "/directory" : "/projects"}><Inbox size={16} /> {isClient ? "Find freelancers" : "Review work"}</Link>
                  <Link className="btn btn-secondary" href="/payments"><Banknote size={16} /> Payment history</Link>
                </div>
              </section>
            </div>
          </div>

          <div className="split">
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Verified transactions</h2><p className="cardSubtitle">Independently checked on Horizon</p></div><Link className="btn btn-ghost btn-sm" href="/payments">View all <ArrowRight size={14} /></Link></div>
              <div className="cardBody">
                {data.payments.recent.length ? (
                  <div className="tableWrap"><table className="dataTable"><thead><tr><th>Amount</th><th>Transaction</th><th>Confirmed</th></tr></thead><tbody>
                    {data.payments.recent.map((payment) => (
                      <tr key={payment.id}><td><strong>{payment.amount} {data.payments.asset}</strong></td><td className="mono">{payment.transaction_hash}</td><td>{payment.confirmed_at ? new Date(payment.confirmed_at).toLocaleString() : "—"}</td></tr>
                    ))}
                  </tbody></table></div>
                ) : <p className="hint">No confirmed payments yet.</p>}
              </div>
            </section>
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Recent activity</h2><p className="cardSubtitle">Recorded changes across your workspace</p></div></div>
              <div className="cardBody">
                {data.activity.length ? <ul className="timeline">{data.activity.map((item, index) => (
                  <li key={`${item.entity_id}-${index}`}><strong>{item.action.replaceAll("_", " ")}</strong> · <span className="hint">{item.entity_type}</span> {item.details}<small>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small></li>
                ))}</ul> : <p className="hint">No activity recorded yet.</p>}
              </div>
            </section>
          </div>
        </div>
      )}
    </AppShell>
  );
}
