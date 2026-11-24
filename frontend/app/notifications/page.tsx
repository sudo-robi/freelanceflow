"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface Notification { id: string; title: string; message: string; created_at: string }

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  useEffect(() => { apiRequest<Notification[]>("/api/notifications").then(setNotifications).catch(() => setNotifications([])); }, []);
  return <main className="appShell"><aside className="sidebar"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><nav className="sidebarNav"><Link href="/dashboard">Overview</Link></nav></aside><section className="appMain"><header className="appTopbar"><strong>Notifications</strong><Link href="/dashboard">Workspace</Link></header><div className="appContent"><p className="eyebrow">Activity</p><h1>Notifications</h1>{notifications.length ? <div className="metricGrid">{notifications.map((item) => <article className="metric" key={item.id}><strong style={{ fontSize: 16 }}>{item.title}</strong><p style={{ color: "var(--muted)" }}>{item.message}</p><small>{new Date(item.created_at).toLocaleString()}</small></article>)}</div> : <div className="walletBox">No notifications yet.</div>}</div></section></main>;
}
