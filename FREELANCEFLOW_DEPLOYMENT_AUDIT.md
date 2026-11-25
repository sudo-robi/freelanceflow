# FreelanceFlow Phase 1 — Deployment & Operations Audit

Date: 2026-11-25. No deployment or Mainnet action was performed for this audit.

## 1. Deployment surfaces

| Surface | Files | Verified |
|---|---|---|
| Docker Compose | `docker-compose.yml` | `docker compose config --quiet` exit 0 with required env vars |
| Backend image | `backend/Dockerfile` | `python:3.14-slim`, `pip install -e . psycopg[binary]`, uvicorn port 8000 |
| Frontend image | `frontend/Dockerfile` | multi-stage `node:24-alpine`, `npm ci`, standalone server as non-root `node` user |
| Railway (documented) | `DEPLOYMENT.md` | documented commands; not executed here |
| Playwright local stack | `frontend/playwright.config.ts` | isolated backend 8011 + frontend 3011, 3 tests passed |

## 2. Configuration

- `DATABASE_URL` defaults to SQLite; Docker Compose injects PostgreSQL URL. `postgres://`/`postgresql://` are normalized to `postgresql+psycopg://`.
- `CORS_ALLOWED_ORIGINS` defaults to localhost origins; configurable.
- `STELLAR_HORIZON_URL`, `SOROBAN_RPC_URL` configurable; defaults are Testnet.
- `API_BACKEND_URL` is required for the Next.js proxy; returns 503 when absent.
- `NEXT_PUBLIC_API_URL` overrides same-origin API routing.
- `.env.example` contains a placeholder PostgreSQL password and the public deployed contract ID. No real secrets are committed.

## 3. Startup, shutdown and health

- Backend startup runs `ensure_schema()`: `create_all()` plus idempotent `ALTER TABLE ADD COLUMN` for columns added after the initial release. Verified by `test_migration.py` on a legacy database with data preserved.
- Health endpoint `GET /api/health` returns `{"status":"ok","network":"stellar-testnet"}` — it does **not** check database connectivity or Horizon reachability.
- No Docker healthchecks are defined for `db`, `api`, or `web`.
- No restart policy, resource limits, or graceful-shutdown configuration is declared.
- `@app.on_event("startup")` is deprecated in the installed FastAPI version (warning observed in test output).

## 4. Persistence, backup and recovery

- PostgreSQL data is stored in the named `postgres_data` volume; local SQLite uses `backend/freelanceflow.db` (gitignored).
- No backup job, restore script, point-in-time recovery procedure, or retention policy exists in the repository.
- `ensure_schema()` is additive-only: no version table, no downgrade path, no constraint/index backfill, and no rollback on partial failure. Migration is tested for the specific legacy-column scenario only.
- Financial records (`PaymentRecord`, `Invoice`) are persisted with transaction hashes and timestamps; no immutable ledger export beyond CSV exists.

## 5. CI/CD and reproducibility

- **No `.github/` directory and no CI workflow exist.** `DEPLOYMENT.md` nevertheless states "CI runs backend pytest … frontend Vitest/build … and Cargo tests". This is a documentation inaccuracy.
- Backend dependencies use `>=` ranges in `pyproject.toml`; the Docker backend image installs `psycopg[binary]` unpinned.
- Frontend dependencies are declared as `latest`; `package-lock.json` pins current installs and `npm ci` makes the Dockerfile deterministic for a given lockfile.
- Contract build requires `wasm32v1-none`; the installed target is present locally but not pinned in CI.
- Stellar CLI 30.0.1 was installed externally for deployment; no CI or script records that step.

## 6. Observability and operations

- No structured logging configuration, log aggregation, error monitoring, metrics, or tracing is configured.
- No rate limiting at application or reverse-proxy level.
- No secret manager integration; secrets are expected via environment variables.
- No deployment rollback procedure documented beyond redeploying a previous image.

## 7. Deployment blockers and priorities

| Priority | Blocker / risk | Recommendation |
|---|---|---|
| HIGH | No CI workflow despite documentation claim | Add or remove the claim; add lint/test/build gates |
| HIGH | No DB backup/restore procedure | Add scheduled pg_dump/SQLite backup and tested restore |
| MEDIUM | No container healthchecks/restart policy | Add healthchecks and `restart: unless-stopped` |
| MEDIUM | Health endpoint does not check dependencies | Add DB/Horizon reachability check with distinct status |
| MEDIUM | Migration is additive-only | Introduce versioned migrations with rollback strategy |
| MEDIUM | Unpinned backend/psycopg versions | Pin exact versions or use a lockfile/hash |
| LOW | `next start` + standalone warning in E2E | Use standalone server command consistently |
| LOW | No observability stack | Add structured logs and error reporting |

## 8. Verification evidence collected

- `docker compose config --quiet` exit 0.
- Backend startup + `GET /api/health` via TestClient: 200 with `network: stellar-testnet`.
- Frontend production build: 13 routes generated, TypeScript exit 0.
- Playwright: real backend and frontend servers started on isolated ports; 3 tests passed.
- Soroban deployment verified on-chain (see `FREELANCEFLOW_BLOCKCHAIN_AUDIT.md`).
- No Mainnet deployment, no secret exposure, no unrelated system testing.
