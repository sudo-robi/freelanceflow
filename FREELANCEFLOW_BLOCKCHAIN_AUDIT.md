# FreelanceFlow Phase 1 — Stellar / Soroban Integration Audit

Date: 2026-11-25. Network: Stellar Testnet only. No Mainnet transaction, no real money, no secret-key logging.

## 1. Inventory

| Capability | Implemented | Executed / verified | Notes |
|---|---|---|---|
| Horizon account lookup | Yes (`GET /api/stellar/account/{address}`) | Live Horizon reachable via curl | Unauthenticated; length-only validation |
| Horizon transaction lookup | Yes (`backend/app/stellar.py::get_transaction`) | Live transaction verified through app endpoint | 200 operations limit per transaction |
| Client builds real XLM transaction | Yes (`frontend/lib/stellar.ts`) | Unit-tested at SDK boundary; no live wallet | Uses official SDK 17.4.0 |
| Freighter connection / network check | Yes | Unit-tested | Verifies passphrase `Test SDF Network ; September 2015` |
| Freighter signing | Yes | Unit-tested only | Real signing requires wallet + human approval |
| Horizon submission | Yes | Unit-tested at boundary | No retry/polling state machine |
| Backend payment confirmation | Yes | Tested with controlled and live Horizon data | Independent server-side verification |
| Escrow contract source | Yes (`contracts/src/lib.rs`) | 8 Cargo tests | Deployed, not integrated |
| Escrow invoke from backend | **No** | — | No runtime code reads contract ID |
| On-chain dispute resolution | **No** | — | Contract has `open_dispute` only |

## 2. Transaction verification controls

`POST /api/payments/{hash}/confirm` enforces:

1. 64-character lowercase-hex hash format.
2. Caller is the agreement client; milestone and agreement exist and are active; milestone is approved.
3. No open dispute and agreement not cancelled.
4. Valid registered Stellar public addresses for both parties.
5. Optional-but-automatic payment-intent binding: amount, source, destination, network, and memo.
6. Independent Horizon fetch by the server (client never supplies transaction content).
7. `found` and `successful` from Horizon; `source_account` equals registered client.
8. For matching operations (payment / path payment strict send/receive): `to` equals freelancer, `from` equals client, `asset_type == native`, and exact `Decimal` amount equality.
9. If an intent exists, Horizon `memo` must equal the intent memo.
10. Unique `transaction_hash` and duplicate-idempotent response; invoice generated in same transaction.

The client-submitted hash is therefore a lookup key, not proof of payment. No client claim is trusted.

## 3. Amount, asset, network and finality

- Amounts are validated as `Decimal` with 7 decimal places at the API boundary and compared exactly to the milestone amount.
- Asset is restricted to native XLM (`asset_type == "native"`, agreement asset must be `XLM`).
- Network identity comes from the configured Horizon URL; responses are labelled `network: "testnet"`. **Risk:** if `STELLAR_HORIZON_URL` is misconfigured to a different network, the application would still label records `testnet` because the passphrase is not validated from a live network response at confirmation time.
- Finality is taken as Horizon `successful: true` from a single fetch. There is no polling, no confirmation-depth check, and no recovery for transient Horizon errors beyond HTTP 502.

## 4. Live verification evidence (2026-11-25)

| Check | Result |
|---|---|
| `GET https://horizon-testnet.stellar.org/transactions?limit=1&order=desc` | hash `be1fcde9f2f7f1cfea2aea903d53b29174786804bc1a19d92e4f72fd6d79a83e`, `successful: true`, ledger 5907518 |
| App endpoint `GET /api/stellar/transaction/{hash}` (authenticated) | HTTP 200, `network: testnet`, passphrase `Test SDF Network ; September 2015`, `verified_against: https://horizon-testnet.stellar.org`, ledger/source matched |
| Soroban RPC `getNetwork` | Passphrase `Test SDF Network ; September 2015`, protocol 30 |

## 5. Soroban escrow

**Deployed and accessible:**

| Artifact | Value |
|---|---|
| Contract ID | `CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI` |
| Local/on-chain WASM hash | `906f98af2a1ae3bb8a816ea65bab35b130c3f4ab02d1ba40335a8ca1eb9b527a` |
| Deploy transaction | `b2f65b6fa9a948261c4861d70f3db92f52046fff86a1c89320581ea042e6f69f` — RPC status SUCCESS |
| Upload transaction | `9c2d00688e0bfe2da7f928b62c0232db917d1f35cbbf53dcb6301540771e91e5` — Horizon successful, ledger 5907860 |

Live `stellar contract info hash` returned the local build hash exactly; `info interface` exposed all eight functions: `create_agreement`, `accept_agreement`, `fund`, `approve_milestone`, `release_milestone`, `cancel`, `open_dispute`, `balance`.

**Contract tests (8 passed):** amount validation, acceptance authorization, funding rules, single release, dispute blocking, cancellation refund, unauthorized dispute.

**Integration reality:** the contract is demonstrative/deployed but not used by the application. `SOROBAN_ESCROW_CONTRACT_ID` appears only in `.env.example` and docs; no backend or frontend runtime code reads it. `WorkAgreement.escrow_contract_id` is never populated. Therefore:

- Escrow state is not independently verified by the backend.
- Application and contract state can diverge (a milestone can be `payment_released` in the database while the contract has never seen an agreement).
- Milestone release is enforced only by the database state machine plus a direct Stellar payment, not by contract logic.
- Disputed funds are frozen in the application layer; the on-chain `open_dispute` function is never invoked, and the contract has no resolution function.

## 6. Risks and recommendations

| Priority | Risk | Recommendation |
|---|---|---|
| HIGH | Deployed escrow not integrated; users may believe funds are contract-escrowed | Either integrate contract funding/release with verified transactions, or clearly state that escrow is not used for funds |
| MEDIUM | No network passphrase verification at confirmation | Query network details (RPC `getNetwork`) and compare passphrase before confirming |
| MEDIUM | No retry/finality handling | Add bounded polling with status persistence (`pending` → `confirmed`/`failed`) |
| MEDIUM | Single Horizon fetch with 502 detail leakage | Generic error messages, server-side logs, retry with backoff |
| LOW | Unauthenticated account proxy with weak validation | Require auth, strict base32 validation, rate limits |
| LOW | Deployer key handling | Already ephemeral and removed; document that no key is stored and rotate if reused |

## 7. Explicitly not done

No Mainnet deployment, no real funds, no private keys or recovery phrases requested/logged/stored, no simulated transaction confirmation, and no claim that the contract is integrated into the payment flow.
