"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ArrowRight, Mail } from "lucide-react";
import { apiRequest } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [devToken, setDevToken] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError(""); setMessage("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ status: string; email_delivery_configured: boolean; reset_token?: string }>("/api/auth/forgot-password", {
        method: "POST", body: JSON.stringify({ email: data.get("email") }),
      });
      setMessage(result.email_delivery_configured ? "If the account exists, a reset link has been sent." : "Request accepted. Email delivery is not configured in this environment.");
      setDevToken(result.reset_token || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Request failed");
    } finally { setLoading(false); }
  }

  return (
    <main className="authShell">
      <section className="authVisual">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div><h2>Recover access safely.</h2><p style={{ color: "#b8c0d8", maxWidth: 420 }}>Reset links are single-use and expire automatically.</p></div>
        <span style={{ color: "#8f9bb8", fontSize: 12 }}>No keys or recovery phrases are requested</span>
      </section>
      <section className="authPanel">
        <form className="authCard" onSubmit={(event) => void submit(event)}>
          <p className="eyebrow">Account recovery</p>
          <h1>Reset password.</h1>
          <p className="hint">Enter your account email to request a reset link.</p>
          {error && <div className="errorBox" role="alert">{error}</div>}
          {message && <div className="notice" role="status">{message}</div>}
          {devToken && <p className="hint">Local development token: <code className="mono">{devToken}</code></p>}
          <div className="field"><label className="label" htmlFor="email">Email</label><input className="input" id="email" name="email" type="email" required /></div>
          <button className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>{loading ? "Sending…" : <>Request reset <ArrowRight size={16} /></>}</button>
          <p className="hint" style={{ textAlign: "center", marginTop: 22 }}><Link href="/login" style={{ color: "var(--primary)", fontWeight: 700 }}>Back to sign in</Link></p>
        </form>
      </section>
    </main>
  );
}
