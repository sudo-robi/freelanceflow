"use client";

import Link from "next/link";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { connectFreighter, loadTestnetBalances } from "@/lib/stellar";

export default function WalletPage() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [balances, setBalances] = useState<string[]>([]);

  async function connectWallet() {
    setBusy(true);
    setError("");
    try {
      const connection = await connectFreighter();
      const items = await loadTestnetBalances(connection.address);
      setAddress(connection.address);
      setNetwork("Testnet");
      setBalances(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Wallet connection failed");
      setAddress("");
      setBalances([]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Wallet" subtitle="Stellar Testnet">
      <div className="appHeaderRow">
        <div><p className="eyebrow">Stellar Testnet</p><h1>Connect Freighter.</h1></div>
        <Link className="textButton" href="/payments">Payment history →</Link>
      </div>
      <div className="walletBox">
        <button className="button" onClick={() => void connectWallet()} disabled={busy}>
          {busy ? "Connecting..." : address ? "Reconnect wallet" : "Connect Freighter"}
        </button>
        {error && <div className="error" role="alert" style={{ marginTop: 16 }}>{error}</div>}
        {address && (
          <div style={{ marginTop: 20 }}>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>Public address · {network}</span>
            <div className="walletAddress" style={{ marginTop: 8 }}>{address}</div>
            <h2 style={{ fontSize: 16, marginTop: 20 }}>Verified Testnet balances</h2>
            {balances.length ? balances.map((item) => <p key={item}><strong>{item}</strong></p>) : <p>No balances returned by Horizon.</p>}
          </div>
        )}
      </div>
    </AppShell>
  );
}
