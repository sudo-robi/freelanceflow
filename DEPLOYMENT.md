# Deployment

## Local development

Backend:

```bash
cd backend
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Docker Compose:

```bash
docker compose up --build
```

Compose requires `POSTGRES_USER` and `POSTGRES_PASSWORD` in the environment or `.env` file. Use a unique, high-entropy password and restrict API CORS origins with `CORS_ALLOWED_ORIGINS`. Never expose PostgreSQL's port publicly.

## Railway Free deployment

The verified Free plan allows one project with up to three services, including a single-node PostgreSQL service, and $1 of resource usage each month. Services sleep while idle; services stop when the included resource credit is exhausted. This is a low-traffic demo deployment, not an always-on production SLA.

Create a Railway project and services named `api`, `web`, and `Postgres`. Deploy the backend and frontend from their respective directories:

```bash
railway link
railway add --database postgres
railway add --service api
railway add --service web
railway up ./backend --path-as-root --service api
railway up ./frontend --path-as-root --service web
```

Set these service variables:

- `api`: `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `web`: `API_BACKEND_URL=http://api.railway.internal:8000`

The frontend uses a same-origin API proxy, so it does not need `NEXT_PUBLIC_API_URL` in the hosted environment. Generate a public domain for `web` on port 3000; the API can remain private. The backend normalizes Railway's PostgreSQL connection URL to the installed psycopg 3 driver.

The Railway Free plan has one 0.5 GB volume for the project; ensure it is attached to PostgreSQL for data persistence. Set an appropriate workspace usage limit to prevent unexpected spending if the workspace plan changes. For current limitations, see [Railway Free Plan](https://docs.railway.com/pricing/free-plan).

## Quality gates

CI runs backend pytest (33 tests), frontend Vitest/build (41 tests), and Cargo tests (8 tests). The Playwright suite (3 tests) starts an isolated backend on port 8011 and the production frontend on port 3011 with `API_BACKEND_URL=http://127.0.0.1:8011`; run it with `cd frontend && npm run test:e2e`. Browser and funded-wallet checks require separate deployment credentials and are not part of credential-free CI.

Startup calls `ensure_schema()`, which creates missing tables and adds missing columns to an existing database without dropping data. Set `DATABASE_URL` to the same persistent volume across redeploys.

The Soroban escrow contract is deployed and verified on the configured network as `CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI` (WASM hash `906f98af2a1ae3bb8a816ea65bab35b130c3f4ab02d1ba40335a8ca1eb9b527a`). It is not currently invoked by the API; see SMART_CONTRACT_REVIEW.md for transaction evidence.
