# Test Strategy

## Backend (pytest)

`backend/.venv/bin/python -m pytest -ra` runs 33 tests:

- `test_auth_projects.py`: registration, login, role separation, ownership isolation, agreement validation, milestone revision, session rejection, security headers, Horizon-matched confirmation, wrong-source rejection.
- `test_database.py`: SQLite default, `postgres://` and `postgresql://` normalization, connect arguments, `get_db` yield/close.
- `test_platform_workflows.py`: discovery, portfolio/availability, project lifecycle, invitations, agreement revisions, milestone history, payment intents and memo binding, rejected/failed/duplicate/incorrect payments, invoices/CSV/PDF/receipts, disputes, dashboards, notifications, Stellar verification.
- `test_migration.py`: legacy schema upgrade without data loss and application startup.

External Horizon calls are replaced at the `get_transaction` boundary in unit tests. Live Horizon reads are executed separately and recorded in TEST_RESULTS.md.

## Frontend (Vitest + Testing Library)

`cd frontend && npm test` runs 41 tests:

- API helper: token handling, header merge, success/error parsing, `API_URL` resolution.
- API proxy route: configuration errors, path encoding, header filtering, body handling, all HTTP methods, upstream status/header relay.
- Stellar helper: Freighter connection/network checks, transaction construction, signature rejection, submission result.
- Dashboard: real API-driven metrics and error handling.
- App shell: navigation surface.

## Smart contract (Cargo)

`cd contracts && cargo test` runs 8 tests with `testutils` and a registered Stellar asset contract: amount validation, acceptance authorization, funding rules, single release, dispute blocking, cancellation refund, unauthorized dispute.

## End-to-end (Playwright)

`cd frontend && npm run test:e2e` starts an isolated backend and the production Next.js server, then exercises registration, project creation, directory/profile, and dispute workflows in Chromium.

## Integration boundary

Real Freighter signing and funded Testnet transactions require wallet credentials and human approval. They are not faked: the frontend uses the official SDK to build and submit transactions, and the backend independently verifies them against Horizon. Mocks are confined to isolated automated tests.
