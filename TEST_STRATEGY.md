# Test Strategy

## Backend

Pytest uses an isolated SQLite metadata database by dropping and recreating tables per test. Tests cover registration, login, role separation, project isolation, milestone totals, invitation acceptance, milestone revision, sessions, and Horizon-matched payment confirmation with a controlled async transaction response.

Run:

```bash
cd backend
.venv/bin/python -m pytest
```

## Frontend

Vitest and jsdom test API credentials and browser storage behavior. Next.js production build validates all routes and TypeScript.

Run:

```bash
cd frontend
npm install
npm test
npm run build
```

## Smart contract

Cargo test executes the Soroban test environment. The current test verifies that release fails before approval.

Run:

```bash
cd contracts
cargo test
```

## Integration boundary

Real Freighter signing and funded Stellar Testnet transactions must be tested separately because CI has no wallet credential or browser approval. Horizon verification is unit-tested through a controlled async boundary; live network verification remains blocked pending funded Testnet wallet access.
