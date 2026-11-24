# Stellar Integration

## Network

- Horizon: https://horizon-testnet.stellar.org
- Soroban RPC: https://soroban-testnet.stellar.org
- Passphrase: `Test SDF Network ; September 2015`
- Asset: native XLM only
- SDK versions verified: `@stellar/stellar-sdk` 17.4.0, `@stellar/freighter-api` 6.0.1

## Live verification evidence (2026-11-25)

- `GET /transactions?limit=1&order=desc` returned real hash `be1fcde9f2f7f1cfea2aea903d53b29174786804bc1a19d92e4f72fd6d79a83e`, `successful: true`, ledger `5907518`, source `GD5K6JYEFVAYLZMSILQBLYLYDYHG6BWMDMB673NOWB2GMGXCZPWHCAH3`.
- The application's authenticated `GET /api/stellar/transaction/{hash}` returned 200 with `network: testnet`, the correct passphrase, `verified_against: https://horizon-testnet.stellar.org`, and matching ledger/source.
- Soroban RPC `getNetwork` returned the Testnet passphrase and protocol version 30.

## Payment flow

1. `POST /api/payment-intents` creates a server-side intent with expected source, destination, `XLM`, `testnet`, amount, and a unique memo (≤28 bytes).
2. `frontend/lib/stellar.ts` checks the Freighter connection (`isConnected` object field, not object truthiness), requests access, and rejects any network whose passphrase differs from Testnet.
3. The source account and base fee are loaded from Horizon; `TransactionBuilder` creates a payment operation with `Asset.native()`, the exact amount, and `Memo.text(intent.memo)`.
4. Freighter `signTransaction(xdr, { networkPassphrase })` produces a signed XDR; a user rejection or any API error aborts with no submission.
5. `Horizon.Server.submitTransaction` sends the real transaction; the returned hash goes to `POST /api/payments/{hash}/confirm`.
6. Backend confirmation independently fetches Horizon data and requires: successful transaction, registered client source, registered freelancer destination, native asset, exact milestone amount, no open dispute, approved milestone, and matching memo when an intent exists.
7. Only then are a unique `PaymentRecord`, invoice, notifications, and audit events written.

## Security properties

- No private keys or recovery phrases are requested, transmitted, or stored.
- Client-provided hashes are lookup keys only, never proof.
- Ledger data is taken from Horizon, not from request parameters.
- Duplicate hashes and duplicate milestone payments are idempotent.
- Wrong network, wrong memo, wrong amount, wrong source/destination, failed transactions, unauthorized confirmations, and disputed milestones are covered by automated tests.

## Status limitations

Live Freighter signing requires an installed wallet, funded Testnet account, and explicit human approval; it is therefore tested at the SDK boundary and against live Horizon reads rather than executed autonomously. No Soroban transaction is claimed or deployed.
