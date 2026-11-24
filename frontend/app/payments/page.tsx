"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest, downloadAuthenticated } from "@/lib/api";

interface Payment {
  id: string;
  amount: number;
  asset: string;
  network: string;
  status: string;
  transaction_hash: string;
  confirmed_at: string | null;
  ledger: number | null;
  memo: string | null;
}
interface Invoice {
  id: string;
  invoice_number: string;
  amount: number;
  asset: string;
  project_title: string;
  milestone_title: string;
  transaction_hash: string;
}
interface Summary { verified_count: number; verified_amount: number; asset: string }

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      apiRequest<Payment[]>("/api/payments"),
      apiRequest<Invoice[]>("/api/invoices"),
      apiRequest<Summary>("/api/payments/summary"),
    ]).then(([p, i, s]) => { setPayments(p); setInvoices(i); setSummary(s); })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load financial records"));
  }, []);

  function download(path: string, filename: string) {
    void downloadAuthenticated(`/api${path}`, filename).catch((cause) =>
      setError(cause instanceof Error ? cause.message : "Download failed"),
    );
  }

  return (
    <AppShell title="Payments" subtitle="Independently verified records">
      <p className="eyebrow">Finance</p>
      <div className="appHeaderRow"><h1>Payments, invoices and receipts.</h1><Link className="textButton" href="/wallet">Stellar wallet →</Link></div>
      {error && <div className="error" role="alert">{error}</div>}
      {summary && <div className="metricGrid">
        <div className="metric"><span>Verified transactions</span><strong>{summary.verified_count}</strong></div>
        <div className="metric"><span>{summary.verified_amount} {summary.asset}</span><strong>Confirmed</strong></div>
        <div className="metric"><span>Network</span><strong>Testnet</strong></div>
      </div>}
      <div className="buttonRow" style={{ marginTop: 20 }}>
        <button className="button" onClick={() => download("/payments/export.csv", "freelanceflow-payments.csv")}>Download CSV</button>
      </div>

      <h2 style={{ marginTop: 28, fontSize: 18 }}>Confirmed transactions</h2>
      {payments.length ? <table className="table"><thead><tr><th>Amount</th><th>Hash</th><th>Network</th><th>Confirmed</th><th>Receipt</th></tr></thead><tbody>
        {payments.map((payment) => (
          <tr key={payment.id}>
            <td>{payment.amount} {payment.asset}</td>
            <td className="mono">{payment.transaction_hash}</td>
            <td>{payment.network}</td>
            <td>{payment.confirmed_at ? new Date(payment.confirmed_at).toLocaleString() : "—"}</td>
            <td><button className="linkButton" onClick={() => download(`/payments/${payment.id}/receipt`, `receipt-${payment.id}.json`)}>Download</button></td>
          </tr>
        ))}
      </tbody></table> : <div className="walletBox">No verified payments yet.</div>}

      <h2 style={{ marginTop: 28, fontSize: 18 }}>Invoices</h2>
      {invoices.length ? <table className="table"><thead><tr><th>Invoice</th><th>Project</th><th>Milestone</th><th>Amount</th><th>PDF</th></tr></thead><tbody>
        {invoices.map((invoice) => (
          <tr key={invoice.id}>
            <td>{invoice.invoice_number}</td>
            <td>{invoice.project_title}</td>
            <td>{invoice.milestone_title}</td>
            <td>{invoice.amount} {invoice.asset}</td>
            <td><button className="linkButton" onClick={() => download(`/invoices/${invoice.id}/pdf`, `${invoice.invoice_number}.pdf`)}>Download</button></td>
          </tr>
        ))}
      </tbody></table> : <div className="walletBox">No invoices yet. Invoices are generated from verified payments.</div>}
    </AppShell>
  );
}
