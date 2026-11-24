import Link from "next/link";
import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";

export default function HomePage() {
  return (
    <main>
      <nav className="nav" aria-label="Primary navigation">
        <Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link>
        <div className="navLinks">
          <Link href="/directory">Find talent</Link>
          <Link href="/login">Sign in</Link>
          <Link className="button buttonSmall" href="/register">Create account</Link>
        </div>
      </nav>

      <section className="hero">
        <div className="heroCopy">
          <p className="eyebrow"><span /> Verified work agreements</p>
          <h1>Every milestone,<br /><em>clearly funded.</em></h1>
          <p className="heroText">Agree on the work, fund it on Stellar, and release payment only when the result is approved.</p>
          <div className="heroActions">
            <Link className="button" href="/register">Start a project <ArrowRight size={18} /></Link>
            <Link className="textButton" href="/directory">Browse freelancers</Link>
          </div>
        </div>

        <div className="agreementPreview" aria-label="Illustrative milestone agreement example, not live account data">
          <p className="illustrativeNote">Illustrative example only — not live account data</p>
          <div className="previewTop">
            <div>
              <p>Agreement FF-2048</p>
              <h2>Product website redesign</h2>
            </div>
            <span className="status"><i /> Funded</span>
          </div>
          <div className="previewAmount"><span>Escrow balance</span><strong>2,400 XLM</strong></div>
          <div className="milestoneList">
            <div className="milestone done"><span className="check"><ShieldCheck size={16} /></span><div><strong>Discovery & structure</strong><small>Approved</small></div><b>800 XLM</b></div>
            <div className="milestone active"><span>02</span><div><strong>Responsive build</strong><small>Submitted for review</small></div><b>1,200 XLM</b></div>
            <div className="milestone"><span>03</span><div><strong>Launch & handoff</strong><small>Not started</small></div><b>400 XLM</b></div>
          </div>
          <div className="previewFooter"><LockKeyhole size={15} /> Funds remain locked until you approve</div>
        </div>
      </section>

      <section className="proof" aria-label="Platform principles">
        <div><b>Two-party approval</b><span>Both parties accept the agreement</span></div>
        <div><b>Milestone escrow</b><span>Funds stay locked by the contract</span></div>
        <div><b>Testnet verified</b><span>Real Stellar transaction checks</span></div>
      </section>
    </main>
  );
}
