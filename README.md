# FreelanceFlow

FreelanceFlow is a two-sided freelancer agreement and milestone payment platform on Stellar Testnet.

## Implemented

- FastAPI authentication with PBKDF2 password hashing and bearer sessions
- Freelancer/client role separation
- SQLAlchemy data model for users, profiles, projects, invitations, agreements, milestones, payments, notifications, and audit logs
- Project creation, freelancer invitation, agreement acceptance, milestone submission/review, and payment confirmation APIs
- Independent Horizon transaction verification endpoint
- Freighter Testnet wallet connection and account balance lookup UI
- Next.js marketing, authentication, dashboard, project, directory, notification, and wallet routes
- Soroban escrow contract with client/freelancer authorization, milestone approval/release, cancellation refund, dispute state, duplicate-release protection, and balance tracking
- Docker Compose for PostgreSQL, API, and web services

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

Open http://localhost:3000.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
cd contracts && cargo test
cd frontend && npm test
cd frontend && npm run build
```

## Docker

```bash
docker compose up --build
```

API documentation: http://localhost:8000/docs

## Stellar network

- Network: Stellar Testnet
- Passphrase: `Test SDF Network ; September 2015`
- Horizon: https://horizon-testnet.stellar.org
- RPC: https://soroban-testnet.stellar.org

The app never switches networks or requests private keys/recovery phrases. Stellar transactions require Freighter approval in the browser and are independently checked against Horizon before a payment is persisted.

## Soroban contract

```bash
cd contracts
rustup target add wasm32v1-none
cargo build --target wasm32v1-none --release
stellar contract build
stellar contract deploy --wasm target/wasm32v1-none/release/freelanceflow_escrow.wasm --network testnet
```

No contract ID or transaction hash is claimed unless the deployment and on-chain release are executed and observed. Set the returned contract ID in `SOROBAN_ESCROW_CONTRACT_ID` when deployment is performed.

## Known limitation

Freighter signing and a live Testnet escrow deployment require wallet access, funded Testnet accounts, and an external Stellar CLI/session. Dispute resolution is represented as a manual, non-automatic state in the MVP. Real funds must not be sent to Testnet escrow addresses outside the explicit Freighter approval flow.

## Engineering records

- [FREELANCEFLOW_ENGINEERING_AUDIT.md](FREELANCEFLOW_ENGINEERING_AUDIT.md)
- [FREELANCEFLOW_SECURITY_AUDIT.md](FREELANCEFLOW_SECURITY_AUDIT.md)
- [TEST_STRATEGY.md](TEST_STRATEGY.md)
- [TEST_RESULTS.md](TEST_RESULTS.md)
- [STELLAR_INTEGRATION.md](STELLAR_INTEGRATION.md)
- [SMART_CONTRACT_REVIEW.md](SMART_CONTRACT_REVIEW.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
