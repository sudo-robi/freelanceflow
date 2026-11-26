# FreelanceFlow — Final Stellar Status

## Network and SDKs

- Network: Stellar Testnet; passphrase `Test SDF Network ; September 2015`.
- Horizon: `https://horizon-testnet.stellar.org`; Soroban RPC: `https://soroban-testnet.stellar.org`.
- SDKs: `@stellar/stellar-sdk` 17.4.0, `@stellar/freighter-api` 6.0.1.

## Implemented and verified functionality

- Payment intents bind amount, source, destination, asset, network and memo.
- Browser builds an XLM payment with the official SDK; Freighter signs; Horizon receives the real transaction.
- Backend independently verifies: successful transaction, registered client source, registered freelancer destination, native asset, exact `Decimal` amount, memo when an intent exists, approved milestone, active agreement, no unresolved dispute.
- Live passphrase is read from Soroban RPC `getNetwork` and compared before confirmation; cached for `PASSPHRASE_CACHE_TTL`.
- Horizon reads use bounded retries (`HORIZON_VERIFY_ATTEMPTS`, `HORIZON_RETRY_DELAY`).
- Duplicate hash handling is idempotent; DB constraint prevents two confirmed payments per milestone.
- New read-only `GET /api/payments/reconcile` re-checks confirmed records against Horizon and reports verified/mismatch/unavailable without mutating data.
- Wallet connection checks `isConnected.isConnected`, network passphrase, rejects invalid addresses, and reports Horizon-returned balances only.

## Testnet evidence

- Real Horizon transaction `be1fcde9f2f7f1cfea2aea903d53b29174786804bc1a19d92e4f72fd6d79a83e`: successful, ledger 5907518, source `GD5K6JYEFVAYLZMSILQBLYLYDYHG6BWMDMB673NOWB2GMGXCZPWHCAH3`.
- App endpoint `GET /api/stellar/transaction/{hash}` returned 200 with correct passphrase, network, ledger and source.
- Soroban RPC `getNetwork` returned the Testnet passphrase and protocol 30.
- Deployed contract `CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI`: on-chain WASM hash `906f98af...b527a` matches local build; interface exposes all 8 functions.
- Deployment transactions: upload `9c2d0068...71e91e5` (Horizon successful, ledger 5907860) and deploy `b2f65b6f...f69f` (RPC status SUCCESS).

## Unverified live operations

- No funded Freighter account was available; no browser wallet approval was executed.
- No live payment was submitted from the UI in this environment.
- Transaction building, signing rejection, and submission are tested at the SDK boundary with mocks, not with a funded wallet.
- No Mainnet operation or real funds were used.

## Soroban integration status — honest boundary

The contract is **deployed and verified**, but the FastAPI payment flow **does not invoke it**. `SOROBAN_ESCROW_CONTRACT_ID` exists in configuration/docs, not in runtime logic. No application claim states that funds are escrowed by the contract. Full integration requires wallet-signed contract funding/release transactions and on-chain state verification, which is a separate major feature blocked by the absence of a funded wallet and a Python-side contract invocation layer. No simulation is presented as real escrow.

## Reconciliation and limitations

Reconciliation is read-only and compares stored records to Horizon; it does not repair records. Finality is Horizon `successful: true` from the verified fetch; there is no confirmation-depth policy. No secret key, private key, or recovery phrase was requested, logged or stored.
