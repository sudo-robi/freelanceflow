"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface Profile {
  id: string;
  email: string;
  full_name: string;
  role: string;
  stellar_address: string | null;
  profile: {
    title?: string;
    description?: string;
    hourly_rate?: number | null;
    project_rate?: number | null;
    skills?: string;
    available?: boolean;
    availability_note?: string;
    company_name?: string;
  } | null;
}
interface PortfolioItem { id: string; title: string; url: string; description: string }

export default function ProfilePage() {
  const [me, setMe] = useState<Profile | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const profile = await apiRequest<Profile>("/api/me");
      setMe(profile);
      if (profile.role === "freelancer") {
        const publicProfile = await apiRequest<{ portfolio: PortfolioItem[] }>(`/api/freelancers/${profile.id}`);
        setPortfolio(publicProfile.portfolio);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load profile");
    }
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
      full_name: data.get("full_name"),
      stellar_address: data.get("stellar_address") || null,
      title: data.get("title"),
      description: data.get("description"),
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
    void act(() => apiRequest("/api/me/portfolio", {
      method: "POST",
      body: JSON.stringify({ title: data.get("title"), url: data.get("url"), description: data.get("description") }),
    }), "Portfolio item added.");
    event.currentTarget.reset();
  }

  return (
    <AppShell title="Profile" subtitle="Account management">
      <p className="eyebrow">Account</p><h1>Your profile.</h1>
      {error && <div className="error" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}
      {me && (
        <>
          <section className="panel"><h2>Details</h2>
            <form className="formGrid" onSubmit={saveProfile}>
              <div className="field"><label htmlFor="full_name">Full name</label><input id="full_name" name="full_name" defaultValue={me.full_name} required /></div>
              <div className="field"><label htmlFor="email">Email</label><input id="email" value={me.email} disabled /></div>
              <div className="field fieldWide"><label htmlFor="stellar_address">Stellar public address</label><input id="stellar_address" name="stellar_address" defaultValue={me.stellar_address || ""} placeholder="G..." maxLength={56} /></div>
              <div className="field"><label htmlFor="title">{me.role === "freelancer" ? "Professional title" : "Company name"}</label><input id="title" name="title" defaultValue={me.profile?.title || me.profile?.company_name || ""} /></div>
              {me.role === "freelancer" && <div className="field"><label htmlFor="hourly_rate">Hourly rate (XLM)</label><input id="hourly_rate" name="hourly_rate" type="number" min="0" step="0.01" defaultValue={me.profile?.hourly_rate ?? ""} /></div>}
              <div className="field fieldWide"><label htmlFor="description">Description</label><textarea id="description" name="description" rows={3} defaultValue={me.profile?.description || ""} /></div>
              {me.role === "freelancer" && <div className="field fieldWide"><label htmlFor="skills">Skills (comma separated)</label><input id="skills" name="skills" defaultValue={me.profile?.skills || ""} /></div>}
              <button className="button">Save profile</button>
            </form>
          </section>
          {me.role === "freelancer" && (
            <>
              <section className="panel"><h2>Availability</h2>
                <div className="buttonRow">
                  <button className="button buttonSmall" onClick={() => void act(
                    () => apiRequest("/api/me/availability", { method: "PUT", body: JSON.stringify({ available: true, availability_note: "Open to new projects" }) }),
                    "Marked available.",
                  )}>Mark available</button>
                  <button className="button buttonSmall secondary" onClick={() => void act(
                    () => apiRequest("/api/me/availability", { method: "PUT", body: JSON.stringify({ available: false, availability_note: "Currently booked" }) }),
                    "Marked unavailable.",
                  )}>Mark unavailable</button>
                </div>
                <p>Current: {me.profile?.available ? "Available" : "Unavailable"} · {me.profile?.availability_note || "No note"}</p>
              </section>
              <section className="panel"><h2>Portfolio</h2>
                {portfolio.map((item) => (
                  <div className="rowBetween" key={item.id}>
                    <span><strong>{item.title}</strong> · <a href={item.url} style={{ color: "var(--blue)" }}>{item.url}</a></span>
                    <button className="button buttonSmall secondary" onClick={() => void act(
                      () => apiRequest(`/api/me/portfolio/${item.id}`, { method: "DELETE" }), "Portfolio item removed.",
                    )}>Remove</button>
                  </div>
                ))}
                <form className="formGrid" onSubmit={addPortfolio} style={{ marginTop: 16 }}>
                  <div className="field"><label htmlFor="portfolio-title">Title</label><input id="portfolio-title" name="title" required /></div>
                  <div className="field"><label htmlFor="portfolio-url">URL</label><input id="portfolio-url" name="url" type="url" required /></div>
                  <div className="field fieldWide"><label htmlFor="portfolio-description">Description</label><input id="portfolio-description" name="description" /></div>
                  <button className="button">Add portfolio item</button>
                </form>
              </section>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
