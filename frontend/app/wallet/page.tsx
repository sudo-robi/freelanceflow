"use client";

import Link from "next/link";
import { useState } from "react";

export default function WalletPage() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState("");
  const [error, setError] = useState("");
  const [balance, setBalance] = useState<string[]>([]);

  async function connectWallet() {
    setError("");
    try {
      const freighter = await import("@stellar/freighter-api");
      const installed = freighter.isConnected ? await freighter.isConnected() : false;
      if (!installed) throw new Error("Freighter is not installed or unavailable");
      const connection = await freighter.requestAccess();
      if (connection.error) throw new Error(connection.error);
      const networkResult = await freighter.getNetwork();
      if (networkResult.networkPassphrase !== "Test SDF Network ; September 2015") throw new Error("Switch Freighter to Stellar Testnet");
      setAddress(connection.address);
      setNetwork("Testnet");
      const accountResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/stellar/account/${connection.address}`);
      if (accountResponse.ok) {
        const account = await accountResponse.json();
        setBalance((account.balances || []).map((item: { balance: string; asset_type: string }) => `${item.balance} ${item.asset_type === "native" ? "XLM" : item.asset_type}`));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Wallet connection failed");
    }
  }

  return (
    <main className="appShell">
      <aside className="sidebar"><Link className="brand" href="/"><span className="brandMark">F</span>FreelanceFlow</Link><nav className="sidebarNav"><Link href="/dashboard">Overview</Link><Link href="/wallet">Stellar wallet</Link></nav></aside>
      <section className="appMain"><header className="appTopbar"><strong>Wallet</strong><span>Testnet</span></header><div className="appContent">
        <p className="eyebrow">Stellar Testnet</p><h1>Connect Freighter.</h1>
        <div className="walletBox"><button className="button" onClick={connectWallet}>{address ? "Reconnect wallet" : "Connect Freighter"}</button>
          {error && <div className="error" role="alert" style={{ marginTop: 16 }}>{error}</div>}
          {address && <div style={{ marginTop: 20 }}><span style={{ color: "var(--muted)", fontSize: 13 }}>Public address · {network}</span><div className="walletAddress" style={{ marginTop: 8 }}>{address}</div>{balance.map((item) => <p key={item}><strong>{item}</strong></p>)}</div>}
        </div>
      </div></section>
    </main>
  );
}
