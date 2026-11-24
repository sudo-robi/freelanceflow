"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface Notification {
  id: string;
  title: string;
  message: string;
  read: boolean;
  category: string;
  created_at: string;
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try { setNotifications(await apiRequest<Notification[]>("/api/notifications")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load notifications"); }
  }

  useEffect(() => { void load(); }, []);

  async function markRead(id: string) {
    setError("");
    try {
      await apiRequest(`/api/notifications/${id}/read`, { method: "POST" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not mark notification as read");
    }
  }

  return (
    <AppShell title="Notifications" subtitle="Persistent activity history">
      <p className="eyebrow">Activity</p><h1>Notifications.</h1>
      {error && <div className="error" role="alert">{error}</div>}
      {notifications.length ? (
        <div className="metricGrid">{notifications.map((item) => (
          <article className="metric" key={item.id}>
            <div className="rowBetween"><strong style={{ fontSize: 16 }}>{item.title}</strong><span className="chip">{item.category}</span></div>
            <p style={{ color: "var(--muted)" }}>{item.message}</p>
            <small>{new Date(item.created_at).toLocaleString()}</small>
            {!item.read && <div style={{ marginTop: 12 }}><button className="button buttonSmall secondary" onClick={() => void markRead(item.id)}>Mark as read</button></div>}
            {item.read && <p className="notice">Read</p>}
          </article>
        ))}</div>
      ) : <div className="walletBox">No notifications yet.</div>}
    </AppShell>
  );
}
