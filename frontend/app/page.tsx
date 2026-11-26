import Link from "next/link";
import { ArrowRight, CheckCircle2, LockKeyhole, ShieldCheck } from "lucide-react";

export default function HomePage() {
  return (
    <main>
      <nav className="marketingNav" aria-label="Primary navigation">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div className="marketingLinks">
          <Link href="/directory">Find talent</Link>
          <Link href="/login">Sign in</Link>
          <Link className="btn btn-primary btn-sm" href="/register">Create account</Link>
        </div>
      </nav>

      <section className="hero">
        <div className="heroCopy">
          <p className="eyebrow">Verified work agreements</p>
          <h1>Every milestone,<br /><em>clearly funded.</em></h1>
          <p className="heroText">Agree on the work, submit deliverables, and release payment only after an independent Stellar Testnet verification.</p>
          <div className="heroActions">
            <Link className="btn btn-primary" href="/register">Start a project <ArrowRight size={17} /></Link>
            <Link className="btn btn-secondary" href="/directory">Browse freelancers</Link>
          </div>
        </div>

        <div className="previewCard" aria-label="Illustrative milestone agreement, not live account data">
          <p className="illustrativeNote">Illustrative example · not live account data</p>
          <div className="previewHead">
            <div><p className="hint">Agreement preview</p><h2>Product website redesign</h2></div>
            <span className="badge badge-success"><span className="dot" />Funded</span>
          </div>
          <div className="previewAmount"><span className="muted">Agreement value</span><strong>2,400 XLM</strong></div>
          <div className="previewList">
            <div className="previewRow"><span className="previewNum"><CheckCircle2 size={14} /></span><div><strong>Discovery &amp; structure</strong><small className="hint">Approved</small></div><b>800 XLM</b></div>
            <div className="previewRow"><span className="previewNum previewNumActive">02</span><div><strong>Responsive build</strong><small className="hint">Submitted for review</small></div><b>1,200 XLM</b></div>
            <div className="previewRow"><span className="previewNum">03</span><div><strong>Launch &amp; handoff</strong><small className="hint">Not started</small></div><b>400 XLM</b></div>
          </div>
          <div className="previewFoot"><LockKeyhole size={14} /> Payments are verified on Stellar before they are recorded</div>
        </div>
      </section>

      <section className="proofStrip" aria-label="Platform principles">
        <div><b>Two-party acceptance</b><span>Both parties accept every agreement.</span></div>
        <div><b>Milestone transparency</b><span>Scope, submissions and revisions in one place.</span></div>
        <div><b>Testnet verified</b><span>Real Horizon transaction checks.</span></div>
      </section>
    </main>
  );
}
