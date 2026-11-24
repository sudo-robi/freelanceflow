# Architecture

## Services

- **Next.js frontend** — client-rendered workspace pages with a same-origin API proxy (`app/api/[...path]/route.ts`) that forwards only allowlisted headers to the backend.
- **FastAPI backend** — `app/main.py` holds the original core endpoints; domain routers under `app/routers/` add projects, agreements, milestones, disputes, finance, dashboard, and Stellar routes. `app/services.py` owns authorization helpers, notifications, audit events, and financial aggregation.
- **SQLAlchemy persistence** — SQLite by default, PostgreSQL via `DATABASE_URL`; `ensure_schema()` creates missing tables and adds missing columns idempotently at startup.
- **Horizon** — account and transaction data; the only accepted payment evidence.
- **Soroban escrow contract** — source implementation and tests; not deployed or invoked by the API.

## Data model

Users, sessions, freelancer/client profiles, portfolios, projects, invitations, work agreements, agreement revisions, milestones, payment intents, payment records, invoices, disputes, dispute events, notifications, and audit logs.

## Payment lifecycle

1. Client and freelancer set valid Stellar public addresses.
2. Both parties accept the agreement; milestones enter the work flow.
3. Client approves a submitted milestone.
4. Client creates a payment intent binding amount, source, destination, network, and memo.
5. Browser loads the source account, builds an XLM payment with the official Stellar SDK, and requests Freighter signature on Testnet only.
6. Signed transaction is submitted to Horizon; the returned hash is sent to the backend.
7. Backend fetches the transaction from Horizon and checks status, source, destination, native asset, exact amount, and memo before persisting a confirmed payment and generating an invoice.
8. Disputes freeze every step; resolution never releases funds automatically.

## Financial integrity

Only Horizon-successful native XLM operations matching the registered parties and exact milestone amount count as earnings, spend, dashboard totals, receipts, invoices, or exports. All monetary values are stored as `Numeric(12, 2)` and converted through `Decimal`.

## Known limitations

- No live funded wallet or browser signature is executed in CI; the integration boundary is tested with SDK mocks and verified against live Horizon read-only data separately.
- The Soroban contract has no on-chain dispute-resolution function; backend resolution is authoritative for application state, and funds require an explicit on-chain transaction.
- Password reset, email verification, and third-party contract audit are not implemented.
