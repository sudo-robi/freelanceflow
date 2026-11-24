# FreelanceFlow

FreelanceFlow is a two-sided freelancer agreement and milestone payment platform on Stellar. Payments are never simulated: the browser builds a real transaction from a backend payment intent, Freighter signs it, Horizon receives it, and the backend independently verifies it before any payment record, invoice, or earnings figure exists.

## Implemented

- FastAPI registration, login, logout, PBKDF2 password hashing, bearer sessions, role separation.
- Persistent profiles, availability, skills, portfolio, public freelancer directory with search/filter/sort/pagination.
- Project create, edit, cancel, complete, deadlines, status tracking, invitations (accept/reject/expire), and activity history.
- Work agreements with scope of work, dual acceptance, rejection, cancellation, milestone replacement, and immutable revision history.
- Milestones with start, submit, review, revision/resubmission, submission counts, and funding status.
- Payment intents binding source, destination, amount, asset, network, and memo; real Freighter signing and Horizon submission; independent verification; idempotent confirmation; duplicate and tamper rejection.
- Verified payment records, receipts, invoices with generated PDFs, CSV export, monthly financial reports, and role-scoped transaction history.
- Disputes with evidence, status history, two-party resolution, and a hard block on automatic fund release.
- Persistent notifications and audit events across every lifecycle stage; unread counts and mark-as-read.
- Role-specific dashboards built only from database records and independently verified payments.
- Idempotent schema migration that adds columns and tables to existing SQLite/PostgreSQL databases without dropping data.
- Soroban escrow contract with authorization, funding, approval, release, cancellation refund, and dispute blocking; eight contract tests.
- Next.js pages for dashboard, projects, project workspace, directory, freelancer profile, payments, disputes, wallet, notifications, profile, login, and register.
- Playwright end-to-end suite against real backend and frontend servers.

## Run locally

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. API docs: http://localhost:8000/docs.

## Tests

```bash
cd backend && .venv/bin/python -m pytest -ra
cd contracts && cargo test
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run test:e2e
```

Latest results: 33 backend tests, 8 contract tests, 41 frontend unit tests, 3 Playwright end-to-end tests, and the Next.js production build all pass. See [TEST_RESULTS.md](TEST_RESULTS.md).

## Docker

```bash
docker compose up --build
```

## Stellar integration

The configured network, endpoints, and passphrase are defined in the application code and documented in [STELLAR_INTEGRATION.md](STELLAR_INTEGRATION.md). The app never requests private keys or recovery phrases. Browser-side balances are informational only; payment confirmation always comes from Horizon after independent verification.

## Soroban contract

The escrow contract is deployed and verified on the configured network:

- Contract ID: `CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI`
- WASM hash (local build matches on-chain): `906f98af2a1ae3bb8a816ea65bab35b130c3f4ab02d1ba40335a8ca1eb9b527a`
- Deployment transaction: `b2f65b6fa9a948261c4861d70f3db92f52046fff86a1c89320581ea042e6f69f`
- WASM upload transaction: `9c2d00688e0bfe2da7f928b62c0232db917d1f35cbbf53dcb6301540771e91e5`

It is not yet invoked by the FastAPI payment flow; verified application payments still rely on direct Stellar transactions. See [SMART_CONTRACT_REVIEW.md](SMART_CONTRACT_REVIEW.md) for evidence and limits.

## Records

- [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md)
- [FREELANCEFLOW_ENGINEERING_AUDIT.md](FREELANCEFLOW_ENGINEERING_AUDIT.md)
- [FREELANCEFLOW_SECURITY_AUDIT.md](FREELANCEFLOW_SECURITY_AUDIT.md)
- [TEST_STRATEGY.md](TEST_STRATEGY.md)
- [TEST_RESULTS.md](TEST_RESULTS.md)
- [STELLAR_INTEGRATION.md](STELLAR_INTEGRATION.md)
- [SMART_CONTRACT_REVIEW.md](SMART_CONTRACT_REVIEW.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
