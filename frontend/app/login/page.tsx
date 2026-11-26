"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { apiRequest, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    const data = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ token: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: data.get("email"), password: data.get("password") }),
      });
      setToken(result.token);
      router.push("/dashboard");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="authShell">
      <section className="authVisual">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div>
          <h2>A clearer way to work and get paid.</h2>
          <p style={{ color: "#b8c0d8", maxWidth: 420 }}>Manage agreements, deliverables and verified Testnet payments in one focused workspace.</p>
        </div>
        <span style={{ color: "#8f9bb8", fontSize: 12 }}><ShieldCheck size={14} /> Independent payment verification</span>
      </section>
      <section className="authPanel">
        <form className="authCard" onSubmit={(event) => void submit(event)}>
          <p className="eyebrow">Welcome back</p>
          <h1>Sign in.</h1>
          <p className="hint">Access your projects, agreements and payments.</p>
          {error && <div className="errorBox" role="alert">{error}</div>}
          <div className="field"><label className="label" htmlFor="email">Email</label><input className="input" id="email" name="email" type="email" autoComplete="email" required /></div>
          <div className="field"><label className="label" htmlFor="password">Password</label><input className="input" id="password" name="password" type="password" autoComplete="current-password" required /></div>
          <p className="hint" style={{ textAlign: "right", marginTop: -8 }}><Link href="/forgot-password" style={{ color: "var(--primary)", fontWeight: 700 }}>Forgot password?</Link></p>
          <button className="btn btn-primary" style={{ width: "100%", marginTop: 10 }} disabled={loading}>{loading ? "Signing in…" : <>Sign in <ArrowRight size={16} /></>}</button>
          <p className="hint" style={{ textAlign: "center", marginTop: 22 }}>New here? <Link href="/register" style={{ color: "var(--primary)", fontWeight: 700 }}>Create an account</Link></p>
        </form>
      </section>
    </main>
  );
}
