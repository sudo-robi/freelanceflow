# Architecture

## Services

- Next.js frontend: authentication, projects, directory, dashboard, notifications, and wallet pages.
- FastAPI backend: session auth, role/object authorization, project/agreement/milestone/payment APIs.
- PostgreSQL in Docker: intended relational persistence.
- SQLite: default local persistence.
- Horizon: account and transaction verification.
- Soroban contract: source implementation retained but not deployed or integrated.

## Backend data model

Users, sessions, freelancer/client profiles, projects, invitations, work agreements, milestones, payment records, notifications, and audit logs are represented as SQLAlchemy entities.

## Financial integrity

Only Horizon-successful native XLM operations with the registered client source, freelancer destination, and exact milestone amount can become confirmed payment records.

## Known limitations

The repository has no migrations, invoice/dispute implementations, live escrow integration, or browser end-to-end suite.
