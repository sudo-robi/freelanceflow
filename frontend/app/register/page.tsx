"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { apiRequest, setToken } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ token: string; role: string }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
          full_name: form.get("full_name"),
          role: form.get("role"),
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
      <section className="authVisual"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><h2>Build trust into every agreement.</h2></section>
      <section className="authPanel">
        <form className="formCard" onSubmit={submit}>
          <p className="eyebrow">Create account</p>
          <h1>Start working<br />with clarity.</h1>
          {error && <div className="error" role="alert">{error}</div>}
          <div className="field"><label htmlFor="full_name">Full name</label><input id="full_name" name="full_name" required /></div>
          <div className="field"><label htmlFor="email">Email</label><input id="email" name="email" type="email" required /></div>
          <div className="field"><label htmlFor="password">Password</label><input id="password" name="password" type="password" minLength={8} required /></div>
          <div className="field"><label htmlFor="role">I am a</label><select id="role" name="role" required><option value="client">Client</option><option value="freelancer">Freelancer</option></select></div>
          <button className="button" style={{ width: "100%", marginTop: 10 }} disabled={loading}>{loading ? "Creating..." : "Create account"}</button>
          <p style={{ textAlign: "center", color: "var(--muted)", fontSize: 13 }}>Already registered? <Link href="/login" style={{ color: "var(--blue)", fontWeight: 800 }}>Sign in</Link></p>
        </form>
      </section>
    </main>
  );
}
