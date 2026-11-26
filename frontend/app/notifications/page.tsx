"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Bell, CheckCheck } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { Badge, EmptyState, Skeleton } from "@/components/ui";

interface Notification {
  id: string; title: string; message: string; read: boolean; category: string;
  created_at: string; entity_type: string | null; entity_id: string | null;
}

const linkFor = (item: Notification) => {
  if (item.entity_type === "project" && item.entity_id) return `/projects/${item.entity_id}`;
  if (item.entity_type === "milestone") return "/projects";
  if (item.entity_type === "payment" || item.entity_type === "dispute") return item.entity_type === "payment" ? "/payments" : "/disputes";
  return "/dashboard";
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try { setNotifications(await apiRequest<Notification[]>("/api/notifications")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load notifications"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function markRead(id: string) {
    setError("");
    try { await apiRequest(`/api/notifications/${id}/read`, { method: "POST" }); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update notification"); }
  }

  const unread = notifications.filter((item) => !item.read).length;

  return (
    <AppShell title="Notifications" subtitle="Activity">
      <div className="pageHead">
        <div>
          <p className="eyebrow">Notification centre</p>
          <h1>Notifications.</h1>
          <p className="pageLead">Persisted updates from your projects, agreements, milestones, payments and disputes.</p>
        </div>
        <Badge tone={unread ? "primary" : "success"}>{unread} unread</Badge>
      </div>
      {error && <div className="errorBox" role="alert">{error}</div>}
      {loading && <div className="card cardBody"><Skeleton lines={4} /></div>}
      {!loading && (notifications.length ? (
        <section className="card">
          <div className="cardHeader"><div><h2 className="cardTitle">All notifications</h2><p className="cardSubtitle">Newest first</p></div><Bell size={17} /></div>
          <div className="cardBody stack" style={{ gap: 0 }}>
            {notifications.map((item) => (
              <div className="rowBetween" key={item.id} style={{ padding: "14px 0", borderBottom: "1px solid var(--border)" }}>
                <div><div className="badgeRow"><strong>{item.title}</strong><Badge>{item.category}</Badge>{!item.read && <Badge tone="primary">New</Badge>}</div><p style={{ margin: "6px 0" }}>{item.message}</p><small>{new Date(item.created_at).toLocaleString()}</small></div>
                <div className="buttonRow">{!item.read && <button className="btn btn-secondary btn-sm" onClick={() => void markRead(item.id)}><CheckCheck size={14} /> Mark read</button>}<Link className="btn btn-ghost btn-sm" href={linkFor(item)}>Open <ArrowRight size={14} /></Link></div>
              </div>
            ))}
          </div>
        </section>
      ) : <EmptyState icon={<Bell size={20} />} title="No notifications" description="Lifecycle updates will appear here as your work progresses." />)}
    </AppShell>
  );
}
