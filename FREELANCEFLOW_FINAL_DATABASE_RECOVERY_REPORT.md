# FreelanceFlow — Final Database & Recovery Report

## Production database

Docker Compose uses PostgreSQL 16 with a named volume, no published database port, healthcheck, restart policy and health-gated API startup. Application code remains SQLite-compatible for development/testing. `DATABASE_URL` is environment-driven and normalized to `postgresql+psycopg://`.

## Schema and integrity

- `ensure_schema()` creates tables, adds missing columns (now including `email_verified`), creates missing indexes and removes expired sessions; it refuses startup if duplicate confirmed payments exist.
- Constraints: unique transaction hash; partial unique index `uq_confirmed_milestone_payment` (confirmed payments per milestone); unique payment intents memo; account token hash uniqueness; rate-limit counter composite primary key.
- Indexes: agreement/dispute states, notifications, audit logs, payment intents, payments, account tokens, rate limits.
- No destructive migration; no financial records deleted.

## New tables

`account_tokens` and `rate_limit_counters` are created additively. `users.email_verified` is added through the existing migration path.

## Backup and restore

`scripts/backup.sh`:

- PostgreSQL via `pg_dump -Fc`; SQLite via online backup.
- Writes SHA-256 sidecar for every backup.
- Retention (`BACKUP_RETENTION`, default 7) removes old backups and sidecars.

`scripts/restore.sh` verifies the checksum before restoring, then restores with `pg_restore` or SQLite online backup.

## Recovery drill (executed)

Disposable SQLite database: created row → backup → checksum verified → deliberately overwrote row → restore → original value recovered. Sidecar checksum `OK`, restore exit 0. No real database was touched.

## Limitations

- PostgreSQL restore drill was **not** performed (no disposable PostgreSQL instance available); it remains unverified.
- Recovery point objective is the last successful backup; no automated backup schedule is configured.
- No point-in-time recovery or WAL archiving is configured.
- Migration framework is additive/idempotent but has no version table or automated rollback.

No existing user or financial data was overwritten during this phase.
