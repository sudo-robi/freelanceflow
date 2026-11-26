"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Link2, Loader2, ShieldCheck, Unplug, WalletCards } from "lucide-react";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import { connectFreighter, loadTestnetBalances, TESTNET_PASSPHRASE } from "@/lib/stellar";
import { Badge, Skeleton } from "@/components/ui";

export default function WalletPage() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [balances, setBalances] = useState<string[]>([]);

  async function connectWallet() {
    setBusy(true); setError("");
    try {
      const connection = await connectFreighter();
      const items = await loadTestnetBalances(connection.address);
      setAddress(connection.address);
      setNetwork(connection.networkPassphrase === TESTNET_PASSPHRASE ? "Stellar Testnet" : "Unsupported network");
      setBalances(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Wallet connection failed");
      setAddress(""); setBalances([]);
    } finally { setBusy(false); }
  }

  function disconnect() {
    setAddress(""); setBalances([]); setNetwork(""); setError("");
  }

  return (
    <AppShell title="Wallet" subtitle="Stellar Testnet">
      <div className="pageHead">
        <div>
          <p className="eyebrow">Wallet connection</p>
          <h1>Connect Freighter.</h1>
          <p className="pageLead">The app reads public addresses and balances. It never requests private keys or recovery phrases.</p>
        </div>
        <Link className="btn btn-secondary" href="/payments">Payment history <ArrowRight size={15} /></Link>
      </div>

      <div className="split">
        <section className="card">
          <div className="cardHeader"><div><h2 className="cardTitle">Connection</h2><p className="cardSubtitle">Wallet approval happens inside Freighter.</p></div><WalletCards size={17} /></div>
          <div className="cardBody stack" style={{ gap: 14 }}>
            {!address && <button className="btn btn-primary" disabled={busy} onClick={() => void connectWallet()}>{busy ? <><Loader2 size={16} /> Connecting…</> : <><Link2 size={16} /> Connect Freighter</>}</button>}
            {address && (
              <>
                <div className="badgeRow"><Badge tone="success"><span className="dot" /> Connected</Badge><Badge tone="primary">{network}</Badge></div>
                <div><p className="label">Public address</p><div className="walletAddress">{address}</div></div>
                <button className="btn btn-secondary btn-sm" onClick={disconnect}><Unplug size={15} /> Forget wallet</button>
                <p className="hint">Forgetting the wallet only clears this session's view. Revoke the site permission inside Freighter to disconnect permanently.</p>
              </>
            )}
            {error && <div className="errorBox" role="alert">{error}</div>}
          </div>
        </section>

        <section className="card">
          <div className="cardHeader"><div><h2 className="cardTitle">Testnet balances</h2><p className="cardSubtitle">Read from Horizon, not simulated.</p></div><ShieldCheck size={17} /></div>
          <div className="cardBody">
            {!address && <p className="hint">Connect a wallet to view balances.</p>}
            {address && busy && <Skeleton lines={3} />}
            {address && !busy && (balances.length ? balances.map((item) => <div className="receiptLine" key={item}><span>{item}</span></div>) : <p className="hint">Horizon returned no balances for this address.</p>)}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
