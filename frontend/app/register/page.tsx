"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { apiRequest, setToken } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ token: string; role: string }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: data.get("email"),
          password: data.get("password"),
          full_name: data.get("full_name"),
          role: data.get("role"),
        }),
      });
      setToken(result.token);
      router.push("/dashboard");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="authShell">
      <section className="authVisual">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div>
          <h2>Build trust into every agreement.</h2>
          <p style={{ color: "#b8c0d8", maxWidth: 420 }}>A shared workspace for scope, milestones, revisions and verified payments.</p>
        </div>
        <span style={{ color: "#8f9bb8", fontSize: 12 }}><ShieldCheck size={14} /> No wallet keys are ever requested</span>
      </section>
      <section className="authPanel">
        <form className="authCard" onSubmit={(event) => void submit(event)}>
          <p className="eyebrow">Create account</p>
          <h1>Start working<br />with clarity.</h1>
          <p className="hint">Choose your role. You can build your profile afterwards.</p>
          {error && <div className="errorBox" role="alert">{error}</div>}
          <div className="field"><label className="label" htmlFor="full_name">Full name</label><input className="input" id="full_name" name="full_name" required /></div>
          <div className="field"><label className="label" htmlFor="email">Email</label><input className="input" id="email" name="email" type="email" autoComplete="email" required /></div>
          <div className="field"><label className="label" htmlFor="password">Password</label><input className="input" id="password" name="password" type="password" minLength={8} autoComplete="new-password" required /></div>
          <div className="field"><label className="label" htmlFor="role">I am a</label><select className="select" id="role" name="role" required><option value="client">Client</option><option value="freelancer">Freelancer</option></select></div>
          <button className="btn btn-primary" style={{ width: "100%", marginTop: 8 }} disabled={loading}>{loading ? "Creating…" : <>Create account <ArrowRight size={16} /></>}</button>
          <p className="hint" style={{ textAlign: "center", marginTop: 22 }}>Already registered? <Link href="/login" style={{ color: "var(--primary)", fontWeight: 700 }}>Sign in</Link></p>
        </form>
      </section>
    </main>
  );
}
