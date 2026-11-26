"use client";

import { FormEvent, useEffect, useState } from "react";
import { BadgeCheck, Plus, Trash2, UserRound } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { Avatar, Badge, EmptyState, Skeleton } from "@/components/ui";

interface Profile {
  id: string; email: string; full_name: string; role: string; stellar_address: string | null;
  profile: { title?: string; description?: string; hourly_rate?: number | null; skills?: string; available?: boolean; availability_note?: string; company_name?: string } | null;
}
interface PortfolioItem { id: string; title: string; url: string; description: string }

export default function ProfilePage() {
  const [me, setMe] = useState<Profile | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const profile = await apiRequest<Profile>("/api/me");
      setMe(profile);
      if (profile.role === "freelancer") {
        const publicProfile = await apiRequest<{ portfolio: PortfolioItem[] }>(`/api/freelancers/${profile.id}`);
        setPortfolio(publicProfile.portfolio);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load profile"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function act(operation: () => Promise<unknown>, success: string) {
    setError(""); setNotice("");
    try { await operation(); setNotice(success); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Update failed"); }
  }

  function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {
      full_name: data.get("full_name"), stellar_address: data.get("stellar_address") || null,
      title: data.get("title"), description: data.get("description"),
    };
    if (me?.role === "freelancer") {
      payload.hourly_rate = Number(data.get("hourly_rate")) || null;
      payload.skills = data.get("skills");
    }
    void act(() => apiRequest("/api/me", { method: "PUT", body: JSON.stringify(payload) }), "Profile updated.");
  }

  function addPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void act(() => apiRequest("/api/me/portfolio", { method: "POST", body: JSON.stringify({ title: data.get("title"), url: data.get("url"), description: data.get("description") }) }), "Portfolio item added.");
    event.currentTarget.reset();
  }

  return (
    <AppShell title="Profile" subtitle="Settings">
      <div className="pageHead"><div><p className="eyebrow">Account settings</p><h1>Your profile.</h1><p className="pageLead">Manage your public identity and Stellar receiving address.</p></div></div>
      {error && <div className="errorBox" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}
      {loading && <div className="card cardBody"><Skeleton lines={5} /></div>}
      {me && (
        <div className="split">
          <div className="stack">
            <section className="card">
              <div className="cardHeader"><div className="avatarCard"><Avatar name={me.full_name} large /><div><h2 className="cardTitle">{me.full_name}</h2><p className="cardSubtitle">{me.email} · {me.role}</p></div></div><BadgeCheck size={18} /></div>
              <form className="cardBody formGrid" onSubmit={saveProfile}>
                <div className="field"><label className="label" htmlFor="full_name">Full name</label><input className="input" id="full_name" name="full_name" defaultValue={me.full_name} required /></div>
                <div className="field"><label className="label" htmlFor="email">Email</label><input className="input" id="email" value={me.email} disabled /></div>
                <div className="field fieldWide"><label className="label" htmlFor="stellar_address">Stellar public address</label><input className="input mono" id="stellar_address" name="stellar_address" defaultValue={me.stellar_address || ""} placeholder="G…" maxLength={56} /></div>
                <div className="field"><label className="label" htmlFor="title">{me.role === "freelancer" ? "Professional title" : "Company name"}</label><input className="input" id="title" name="title" defaultValue={me.profile?.title || me.profile?.company_name || ""} /></div>
                {me.role === "freelancer" && <div className="field"><label className="label" htmlFor="hourly_rate">Hourly rate (XLM)</label><input className="input" id="hourly_rate" name="hourly_rate" type="number" min="0" step="0.01" defaultValue={me.profile?.hourly_rate ?? ""} /></div>}
                <div className="field fieldWide"><label className="label" htmlFor="description">Description</label><textarea className="textarea" id="description" name="description" rows={3} defaultValue={me.profile?.description || ""} /></div>
                {me.role === "freelancer" && <div className="field fieldWide"><label className="label" htmlFor="skills">Skills (comma separated)</label><input className="input" id="skills" name="skills" defaultValue={me.profile?.skills || ""} /></div>}
                <div className="fieldWide"><button className="btn btn-primary">Save profile</button></div>
              </form>
            </section>

            {me.role === "freelancer" && <>
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Availability</h2><p className="cardSubtitle">Shown on your public profile.</p></div></div>
                <div className="cardBody stack" style={{ gap: 12 }}>
                  <div className="badgeRow"><Badge tone={me.profile?.available ? "success" : "warning"}>{me.profile?.available ? "Available" : "Unavailable"}</Badge><span className="hint">{me.profile?.availability_note || "No note"}</span></div>
                  <div className="buttonRow">
                    <button className="btn btn-secondary btn-sm" onClick={() => void act(() => apiRequest("/api/me/availability", { method: "PUT", body: JSON.stringify({ available: true, availability_note: "Open to new projects" }) }), "Marked available.")}>Mark available</button>
                    <button className="btn btn-secondary btn-sm" onClick={() => void act(() => apiRequest("/api/me/availability", { method: "PUT", body: JSON.stringify({ available: false, availability_note: "Currently booked" }) }), "Marked unavailable.")}>Mark unavailable</button>
                  </div>
                </div>
              </section>
              <section className="card">
                <div className="cardHeader"><div><h2 className="cardTitle">Portfolio</h2><p className="cardSubtitle">Public work samples.</p></div></div>
                <div className="cardBody">
                  {portfolio.length ? portfolio.map((item) => (
                    <div className="rowBetween" key={item.id} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}><span><strong>{item.title}</strong><br /><a href={item.url} target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>{item.url}</a></span><button className="btn btn-danger btn-sm" onClick={() => void act(() => apiRequest(`/api/me/portfolio/${item.id}`, { method: "DELETE" }), "Portfolio item removed.")}><Trash2 size={14} /> Remove</button></div>
                  )) : <EmptyState icon={<UserRound size={19} />} title="No portfolio items" description="Add a public work sample to strengthen your profile." />}
                  <form className="formGrid" style={{ marginTop: 18 }} onSubmit={addPortfolio}>
                    <div className="field"><label className="label" htmlFor="portfolio-title">Title</label><input className="input" id="portfolio-title" name="title" required /></div>
                    <div className="field"><label className="label" htmlFor="portfolio-url">URL</label><input className="input" id="portfolio-url" name="url" type="url" required /></div>
                    <div className="field fieldWide"><label className="label" htmlFor="portfolio-description">Description</label><input className="input" id="portfolio-description" name="description" /></div>
                    <div className="fieldWide"><button className="btn btn-secondary"><Plus size={15} /> Add item</button></div>
                  </form>
                </div>
              </section>
            </>}
          </div>
          <aside className="card"><div className="cardHeader"><h2 className="cardTitle">Account</h2></div><div className="cardBody stack" style={{ gap: 12 }}><div className="receiptLine"><span className="hint">Role</span><strong>{me.role}</strong></div><div className="receiptLine"><span className="hint">User ID</span><span className="mono">{me.id.slice(0, 8)}</span></div><div className="receiptLine"><span className="hint">Stellar address</span><span className="mono">{me.stellar_address?.slice(0, 12) || "Not set"}</span></div></div></aside>
        </div>
      )}
    </AppShell>
  );
}
