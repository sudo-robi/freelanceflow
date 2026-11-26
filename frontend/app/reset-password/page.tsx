"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { FormEvent } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { apiRequest } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("token") || "";
    setToken(value);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError(""); setMessage("");
    const data = new FormData(event.currentTarget);
    try {
      await apiRequest("/api/auth/reset-password", {
        method: "POST", body: JSON.stringify({ token, password: data.get("password") }),
      });
      setMessage("Password updated. All existing sessions were revoked.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Reset failed");
    } finally { setLoading(false); }
  }

  return (
    <main className="authShell">
      <section className="authVisual">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div><h2>Choose a strong new password.</h2><p style={{ color: "#b8c0d8", maxWidth: 420 }}>All existing sessions are revoked when a password is reset.</p></div>
        <span style={{ color: "#8f9bb8", fontSize: 12 }}><ShieldCheck size={14} /> Single-use reset tokens</span>
      </section>
      <section className="authPanel">
        <form className="authCard" onSubmit={(event) => void submit(event)}>
          <p className="eyebrow">Account recovery</p>
          <h1>New password.</h1>
          {error && <div className="errorBox" role="alert">{error}</div>}
          {message && <div className="notice" role="status">{message}</div>}
          <div className="field"><label className="label" htmlFor="token">Reset token</label><input className="input mono" id="token" value={token} onChange={(event) => setToken(event.target.value)} required /></div>
          <div className="field"><label className="label" htmlFor="password">New password</label><input className="input" id="password" name="password" type="password" minLength={8} autoComplete="new-password" required /></div>
          <button className="btn btn-primary" style={{ width: "100%" }} disabled={loading || !token}>{loading ? "Updating…" : <>Update password <ArrowRight size={16} /></>}</button>
          <p className="hint" style={{ textAlign: "center", marginTop: 22 }}><Link href="/login" style={{ color: "var(--primary)", fontWeight: 700 }}>Back to sign in</Link></p>
        </form>
      </section>
    </main>
  );
}
