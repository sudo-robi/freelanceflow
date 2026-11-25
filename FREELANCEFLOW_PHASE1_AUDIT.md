# FreelanceFlow Phase 1 — Deep Repository Audit

Date: 2026-11-25. Branch: `phase1-deep-audit`. Baseline commit: `d1a06eb`.

## 1. Scope and method

This audit inspected every tracked source file, configuration file, contract, test, and document in the repository. Documentation was not trusted without code verification. Test suites were executed locally. Four suspected defects were reproduced in an isolated SQLite database (`/home/robi/tmp/ff-audit-repro.py`, outside the repository). No frontend visual design, theme, styling, or layout was changed. No production/Mainnet action was taken.

## 2. Actual architecture

| Layer | Technology | Entry points |
|---|---|---|
| Frontend | Next.js 16.4.6 App Router, React, TypeScript, Vitest, Playwright | `frontend/app/**`, `frontend/components/**`, `frontend/lib/**` |
| API gateway (same-origin) | Next.js route handler forwarding a header allowlist | `frontend/app/api/[...path]/route.ts` |
| Backend | FastAPI, SQLAlchemy 2.x, Pydantic 2.x, httpx, Python 3.14 | `backend/app/main.py` + `backend/app/routers/*.py` |
| Persistence | SQLite by default; PostgreSQL via `DATABASE_URL` and Docker Compose | `backend/app/database.py` |
| Chain data | Stellar Horizon (Testnet), Stellar SDK 17.4.0, Freighter 6.0.1 | `backend/app/stellar.py`, `frontend/lib/stellar.ts` |
| Escrow | Soroban Rust contract (`soroban-sdk` 30.0.0), deployed and verified | `contracts/src/lib.rs` |

Execution path for a payment:

1. Client creates a server-side payment intent (`POST /api/payment-intents`).
2. Browser builds an XLM transaction with the official SDK, Freighter signs it, Horizon receives it.
3. Browser sends the returned hash to `POST /api/payments/{hash}/confirm`.
4. Backend fetches the transaction from Horizon and checks successful status, source, destination, native asset, exact amount, and optional intent memo before persisting a confirmed payment and generating an invoice.

The Soroban contract is deployed on-chain but **not invoked** by the FastAPI payment flow. `SOROBAN_ESCROW_CONTRACT_ID` exists only in `.env.example` and documentation; no runtime code reads it.

## 3. Feature inventory and status

| Area | State | Evidence |
|---|---|---|
| Registration/login/logout/sessions | Implemented, tested | `test_auth_projects.py`; PBKDF2 200k, bearer sessions |
| Profiles, availability, portfolio, directory | Implemented, tested | `test_platform_workflows.py` profile/discovery cases |
| Projects (create/edit/cancel/complete/activity) | Implemented, tested | project lifecycle cases |
| Invitations (send/accept/reject/expire/list) | Implemented, tested | invitation cases |
| Agreements (create/dual accept/reject/cancel/revisions) | Implemented, tested, **one state defect reproduced** | agreement cases; SEC-01 |
| Milestones (start/submit/review/revision/resubmit) | Implemented, tested; **frontend rounding defect reproduced** | milestone cases; FRONT-01 |
| Payments (intent, Freighter signing, Horizon verification, idempotency) | Implemented, tested | payment intent/negative cases; live Horizon read |
| Disputes (open/evidence/propose/accept) | Implemented, tested; **proposal-overwrite defect reproduced** | dispute cases; SEC-03 |
| Invoices/receipts/CSV/PDF/report | Implemented, tested | finance cases, PDF magic-byte assertion |
| Notifications and audit history | Implemented, tested | notification assertions and dashboard activity |
| Dashboards | Implemented, API-driven | Vitest dashboard test, E2E |
| Schema migration | Implemented, additive only | `test_migration.py` |
| Soroban escrow | Deployed and tested; not integrated | `cargo test` 8 passed; live contract hash/interface verified |
| CI/CD | **Missing** | no `.github/` directory; DEPLOYMENT.md nevertheless says "CI runs …" |
| Rate limiting, CSRF, file uploads, monitoring | **Missing** | source grep found no implementation |
| Password reset, email verification | **Missing** | no routes or schemas |

## 4. Integration boundaries

- Browser → backend: same-origin `/api/*` proxy in production; direct `NEXT_PUBLIC_API_URL` when configured (Docker Compose sets `http://localhost:8000`).
- Backend → Horizon: read-only account and transaction lookups; single fetch per verification, no retry/polling.
- Backend → Soroban RPC: none at runtime (only a network-info endpoint reports the configured RPC URL).
- Browser → Freighter: `isConnected`, `requestAccess`, `getNetwork`, `signTransaction` (no secret material requested).
- Backend → database: one `SessionLocal` per request via `get_db`; transaction commits are explicit per endpoint.

## 5. Testing baseline (executed, not claimed)

| Suite | Command | Result |
|---|---|---|
| Backend | `cd backend && .venv/bin/python -m pytest -ra` | 33 passed |
| Backend coverage | `pytest --cov=app --cov-report=term-missing` | `main.py` 80%, `models.py` 100%, `database.py` 97%, routers 71–100%, `stellar.py` 33% (live HTTP boundary) |
| Frontend unit | `cd frontend && npm test` | 41 passed / 5 files |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Frontend build | `npm run build` | success, 13 routes |
| Contract | `cd contracts && cargo test` | 8 passed |
| E2E | `npm run test:e2e` | 3 passed |
| Docker | `POSTGRES_USER=test POSTGRES_PASSWORD=test docker compose config --quiet` | exit 0 |
| Live Horizon | `GET /transactions?limit=1` | real hash, successful, ledger 5907518 |
| Live contract | `stellar contract info hash` / `info interface` | on-chain hash matches local build; 8 functions exposed |

Coverage figures are installed-tool output, not estimates. The 33 backend tests include negative payment, dispute, authorization, and migration cases; they are not superficial smoke tests.

## 6. Functional gaps and technical debt

1. Cancelled agreements can be reactivated by re-calling the acceptance endpoint (SEC-01).
2. Stellar address validation is inconsistent between profile update and payment flows (SEC-02).
3. Dispute resolution proposals can be silently overwritten (SEC-03).
4. No unique database constraint prevents two different transaction hashes from confirming the same milestone concurrently.
5. Frontend equal-split milestone creation can produce a total that fails backend validation (FRONT-01).
6. Revision feedback is a hardcoded string from the UI (FRONT-02).
7. No CI workflow exists despite deployment documentation claiming CI execution.
8. Migrations are additive with no version table, checksums, rollback, or constraint backfill.
9. Payment verification has no retry/finality polling; transient Horizon failures become 502.
10. Deployed escrow contract is not wired into application state; contract and database can diverge.
11. No operational observability: structured logging, error monitoring, metrics, backup/restore procedures.
12. Dependency versions are broad (`>=` in `pyproject.toml`, `latest` in `package.json`), although lockfiles pin current installs.

## 7. Overall status

The platform is a working, tested implementation for the core freelancer-client lifecycle with independently verified Testnet payments. It is not yet production-hardened: the issues above are concentrated in state-transition integrity, abuse protection, deployment automation, and escrow integration. The frontend is functionally complete for the implemented backend features; visual design is explicitly owned by another phase and was untouched here.

Detailed findings are in `FREELANCEFLOW_SECURITY_AUDIT.md`, `FREELANCEFLOW_BLOCKCHAIN_AUDIT.md`, `FREELANCEFLOW_FRONTEND_AUDIT.md`, and `FREELANCEFLOW_DEPLOYMENT_AUDIT.md`.
