"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BadgeCheck, Download, FileText, Receipt, ShieldCheck } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest, downloadAuthenticated } from "@/lib/api";
import { Badge, BarChart, EmptyState, Skeleton, StatCard, StatusBadge } from "@/components/ui";

interface Payment {
  id: string; amount: number; asset: string; network: string; status: string;
  transaction_hash: string; confirmed_at: string | null; ledger: number | null; memo: string | null;
}
interface Invoice {
  id: string; invoice_number: string; amount: number; asset: string;
  project_title: string; milestone_title: string; transaction_hash: string;
}
interface Summary { verified_count: number; verified_amount: number; asset: string }

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<Payment[]>("/api/payments"),
      apiRequest<Invoice[]>("/api/invoices"),
      apiRequest<Summary>("/api/payments/summary"),
    ]).then(([p, i, s]) => { if (active) { setPayments(p); setInvoices(i); setSummary(s); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to load financial records"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function download(path: string, filename: string) {
    void downloadAuthenticated(`/api${path}`, filename).catch((cause) => setError(cause instanceof Error ? cause.message : "Download failed"));
  }

  const chartData = Object.entries(
    payments.reduce<Record<string, number>>((acc, payment) => {
      const key = payment.confirmed_at ? new Date(payment.confirmed_at).toISOString().slice(0, 7).slice(5) : "—";
      acc[key] = (acc[key] || 0) + payment.amount;
      return acc;
    }, {}),
  ).slice(-6).map(([label, value]) => ({ label, value }));

  return (
    <AppShell title="Payments" subtitle="Finance">
      <div className="pageHead">
        <div>
          <p className="eyebrow">Financial transparency</p>
          <h1>Payments &amp; records.</h1>
          <p className="pageLead">Every figure below comes from a transaction independently verified on Stellar Testnet.</p>
        </div>
        <button className="btn btn-secondary" onClick={() => download("/payments/export.csv", "freelanceflow-payments.csv")}><Download size={16} /> Export CSV</button>
      </div>

      {error && <div className="errorBox" role="alert">{error}</div>}
      {loading && <div className="card cardBody"><Skeleton lines={5} /></div>}

      {!loading && summary && (
        <div className="stack">
          <div className="metricGrid">
            <StatCard label="Verified transactions" value={summary.verified_count} icon={<ShieldCheck size={17} />} hint="Horizon confirmed" />
            <StatCard label="Total verified amount" value={`${summary.verified_amount} ${summary.asset}`} icon={<BadgeCheck size={17} />} />
            <StatCard label="Invoices" value={invoices.length} icon={<Receipt size={17} />} />
            <StatCard label="Network" value="Testnet" icon={<FileText size={17} />} hint="No escrow claim" />
          </div>

          <div className="split">
            <section className="card">
              <div className="cardHeader"><div><h2 className="cardTitle">Confirmed transactions</h2><p className="cardSubtitle">Hash and verification details</p></div></div>
              <div className="cardBody">
                {payments.length ? <div className="tableWrap"><table className="dataTable"><thead><tr><th>Amount</th><th>Transaction hash</th><th>Network</th><th>Confirmed</th><th>Receipt</th></tr></thead><tbody>
                  {payments.map((payment) => (
                    <tr key={payment.id}>
                      <td><strong>{payment.amount} {payment.asset}</strong></td>
                      <td className="mono">{payment.transaction_hash}</td>
                      <td><Badge tone="primary">{payment.network}</Badge></td>
                      <td>{payment.confirmed_at ? new Date(payment.confirmed_at).toLocaleString() : "—"}</td>
                      <td><button className="linkBtn" onClick={() => download(`/payments/${payment.id}/receipt`, `receipt-${payment.id}.json`)}>Download</button></td>
                    </tr>
                  ))}
                </tbody></table></div> : <EmptyState icon={<ShieldCheck size={19} />} title="No verified payments" description="Payments appear here only after Horizon verification." />}
              </div>
            </section>
            <div className="stack">
              <section className="card"><div className="cardHeader"><h2 className="cardTitle">Monthly totals</h2></div><div className="cardBody">{chartData.length ? <BarChart data={chartData} /> : <p className="hint">No payment history yet.</p>}</div></section>
              <section className="card"><div className="cardHeader"><h2 className="cardTitle">Invoices</h2></div><div className="cardBody stack" style={{ gap: 10 }}>
                {invoices.length ? invoices.map((invoice) => (
                  <div className="rowBetween" key={invoice.id}><div><strong>{invoice.invoice_number}</strong><br /><small>{invoice.project_title} · {invoice.milestone_title}</small></div><button className="btn btn-secondary btn-sm" onClick={() => download(`/invoices/${invoice.id}/pdf`, `${invoice.invoice_number}.pdf`)}><FileText size={14} /> PDF</button></div>
                )) : <p className="hint">Invoices are generated from verified payments.</p>}
              </div></section>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
