"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { apiRequest, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ token: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      setToken(result.token);
      router.push("/dashboard");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Login failed");
    }
  }

  return (
    <main className="authShell">
      <section className="authVisual"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><h2>See the work.<br />Verify the payment.</h2></section>
      <section className="authPanel">
        <form className="formCard" onSubmit={submit}>
          <p className="eyebrow">Welcome back</p>
          <h1>Sign in.</h1>
          {error && <div className="error" role="alert">{error}</div>}
          <div className="field"><label htmlFor="email">Email</label><input id="email" name="email" type="email" required /></div>
          <div className="field"><label htmlFor="password">Password</label><input id="password" name="password" type="password" required /></div>
          <button className="button" style={{ width: "100%", marginTop: 10 }}>Sign in</button>
          <p style={{ textAlign: "center", color: "var(--muted)", fontSize: 13 }}>New here? <Link href="/register" style={{ color: "var(--blue)", fontWeight: 800 }}>Create account</Link></p>
        </form>
      </section>
    </main>
  );
}
