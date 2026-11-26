"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, MailCheck } from "lucide-react";
import { apiRequest } from "@/lib/api";

export default function VerifyEmailPage() {
  const [status, setStatus] = useState("Checking verification link…");
  const [error, setError] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token") || "";
    if (!token) { setError("No verification token was provided."); return; }
    apiRequest("/api/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) })
      .then(() => setStatus("Email verified. You can continue to your workspace."))
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Verification failed"));
  }, []);

  return (
    <main className="authShell">
      <section className="authVisual">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div><h2>One less thing to worry about.</h2><p style={{ color: "#b8c0d8", maxWidth: 420 }}>Verified accounts keep payment and project history tied to a confirmed identity.</p></div>
        <span style={{ color: "#8f9bb8", fontSize: 12 }}>Single-use verification links</span>
      </section>
      <section className="authPanel">
        <div className="authCard">
          <p className="eyebrow">Email verification</p>
          <h1>Verify email.</h1>
          <div className="emptyStateIcon"><MailCheck size={19} /></div>
          {error && <div className="errorBox" role="alert">{error}</div>}
          {!error && <div className="notice" role="status">{status}</div>}
          <Link className="btn btn-primary" style={{ width: "100%", marginTop: 20 }} href="/dashboard">Continue <ArrowRight size={16} /></Link>
        </div>
      </section>
    </main>
  );
}
