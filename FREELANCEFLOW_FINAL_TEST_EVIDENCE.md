# FreelanceFlow — Final Test Evidence

All commands were executed locally in `/home/robi/Desktop/freelanceflow` on 2026-11-25/26.

| Suite | Exact command | Result |
|---|---|---|
| Backend | `cd backend && .venv/bin/python -m pytest -ra` | **63 passed** |
| Backend coverage | `cd backend && .venv/bin/python -m pytest --cov=app --cov-report=term -q` | models 100%, dashboard 100%, schemas 96%, agreements 92%, disputes 91%, database 89%, services 87%, main 83%, finance 81%, projects 77%, auth 70%, stellar 63% |
| Frontend unit | `cd frontend && npm test` | **44 passed across 6 files** |
| Frontend lint | `cd frontend && npm run lint` | `tsc --noEmit`, exit 0 |
| Frontend build | `cd frontend && npm run build` | compiled successfully, 13 routes |
| Contract | `cd contracts && cargo test --locked` | **8 passed, 0 failed** |
| E2E | `cd frontend && PLAYWRIGHT_CHROMIUM_EXECUTABLE=... npm run test:e2e` | **4 passed** |
| Dependency audit | `cd frontend && npm audit --omit=dev --registry https://registry.npmjs.org --audit-level=high` | **0 vulnerabilities** |
| Docker | `POSTGRES_USER=test POSTGRES_PASSWORD=test docker compose config --quiet` | exit 0 |
| Shell scripts | `bash -n scripts/backup.sh scripts/restore.sh` | OK |
| Backup/restore drill | SQLite backup → overwrite row → restore → read value | restored original value |
| Live Horizon | `GET https://horizon-testnet.stellar.org/transactions?limit=1` | real successful tx, ledger 5907518 |
| Live app verification | `GET /api/stellar/transaction/{hash}` | 200, correct passphrase/source/ledger |
| Live Soroban RPC | `getNetwork` | Testnet passphrase, protocol 30 |
| Live contract | `stellar contract info hash` | local/on-chain WASM hash match |

## GitHub Actions execution evidence (not just file presence)

| Run | Result |
|---|---|
| CI run `45707242703` | Backend tests and coverage: success; Frontend tests/types/build: success; Soroban contract tests and WASM build: success; Browser end-to-end tests: success |
| Deploy run `45707516221` | Build and publish container images: success — GHCR `api`/`web` manifests pushed; Deploy services to Railway job: success but explicitly logged "Railway secrets not configured; container images were published but no Railway deploy was triggered" |

## Failed / skipped tests

No failing tests at closure. The default npm registry mirror could not serve the audit endpoint; re-running with `--registry https://registry.npmjs.org` succeeded. The browser's automatic `/favicon.ico` 404 is excluded from the E2E response assertion as cosmetic; all other failed responses are asserted absent.

## Blockers

Live funded-wallet signing and browser approval cannot run here; Railway deployment requires repository secrets; Python dependency scanning tool was not installed; third-party audit not performed. None of these invalidate the executed suites above.
