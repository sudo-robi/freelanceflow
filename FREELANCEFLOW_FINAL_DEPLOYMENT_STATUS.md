# FreelanceFlow — Final Deployment Status

## Docker

`docker-compose.yml` defines `db` (postgres:16-alpine), `api` and `web` services with:

- `restart: unless-stopped` on all services.
- Healthchecks: `pg_isready` for DB, Python `urllib` call to `/api/health` for API, Node `fetch` for web.
- Health-gated `depends_on` conditions.
- No published PostgreSQL port; named volume `postgres_data`.
- Validated with `docker compose config --quiet` (exit 0).

Backend image: Python 3.14 slim, pinned dependencies from `pyproject.toml`, `psycopg[binary]` for PostgreSQL. Frontend image: Node 24 Alpine multi-stage, `npm ci` from pinned lockfile, standalone server running as non-root `node`.

## CI/CD

- `.github/workflows/ci.yml`: backend pytest with coverage, frontend unit tests + lint/type gate + production build, contract tests + WASM build, Playwright E2E. CI run `45707242703` had all four jobs successful.
- `.github/workflows/deploy.yml`: triggered after successful CI on `main`; builds/pushes GHCR images and optionally deploys to Railway when `RAILWAY_TOKEN` and `RAILWAY_PROJECT_ID` secrets exist. Deploy run `45707516221` pushed `ghcr.io/sudo-robi/freelanceflow/api:latest` and `/web:latest` and skipped Railway because secrets are absent. **No live Railway deployment is claimed.**

## Configuration

`.env.example` documents `DATABASE_URL`, Horizon/RPC URLs, CORS origins, PostgreSQL credentials, frontend API URL, and the public deployed contract ID. No real secret is committed. CORS origins are configurable with restrictive defaults; methods/headers are explicit.

## Migrations and database

`ensure_schema()` creates missing tables, adds missing columns, removes expired sessions, creates missing indexes, and refuses startup if duplicate confirmed payments exist. It is additive/idempotent but not a versioned rollback framework. Existing SQLite/PostgreSQL data is preserved; no destructive migration is used.

## Backup and restore

`scripts/backup.sh` and `scripts/restore.sh` support PostgreSQL (`pg_dump`/`pg_restore`) and SQLite online backup. A disposable SQLite drill succeeded: backup → deliberate row overwrite → restore → original value recovered. A PostgreSQL restore drill has **not** been performed; no production database was touched.

## Monitoring and logging

Request-ID middleware logs method, path, status, duration and request ID without tokens or bodies. Horizon failures are logged by exception type with generic client messages. No centralized log aggregation, metrics backend, alerting, or error-tracking service is configured — this remains an operational limitation.

## Deployment blockers

- Railway deployment requires repository secrets and a linked project; not performed here.
- No production domain/TLS configuration was applied.
- No backup schedule or automated restore verification in CI.
- No production monitoring stack.

Reproducible local deployment: `docker compose up --build` with `POSTGRES_USER` and `POSTGRES_PASSWORD` set. Controlled Testnet demonstration can use the published GHCR images or local Compose. No Mainnet deployment or real funds were used.
