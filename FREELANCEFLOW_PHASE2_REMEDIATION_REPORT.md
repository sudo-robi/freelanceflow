# FreelanceFlow Phase 2 — Remediation Report

Date: 2026-11-25. Branch: `phase2-security-workflow-remediation`. Baseline: `main` at `79a3c64`.

## Findings addressed

| ID | Finding | Result |
|---|---|---|
| SEC-01 | Cancelled agreement reactivated via acceptance | FIXED — explicit state machine, row locks, idempotent acceptance, 409 on invalid transitions |
| SEC-02 | Weak Stellar address validation | FIXED — shared base32 validator at profile and payment boundaries |
| SEC-03 | Dispute proposal silently overwritten | FIXED — state machine, 409 on overwrite, explicit auditable amendment endpoint |
| SEC-04 | No DB-level payment-per-milestone uniqueness | FIXED — partial unique index plus migration reconciliation guard |
| SEC-05 | No rate limiting | IMPLEMENTED — dependency-free sliding-window limits on sensitive endpoints |
| SEC-06 | Broad CORS with credentials | FIXED — explicit methods and headers, configurable trusted origins |
| SEC-07 | Horizon error details leaked | FIXED — generic 502 messages, server-side exception-type logging |
| SEC-08 | Unauthenticated account lookup with weak validation | FIXED — auth required, strict validator, rate limited |
| FRONT-01 | Frontend equal-split milestone rounding | FIXED — exact 7-decimal allocation helper with tests |
| Performance | N+1 in directory and invitation serialization | IMPLEMENTED — joined query with subquery counts; one project-title query |

## Findings not addressed (documented residual risk)

- SEC-09 (sessionStorage token exposure) — deferred; changing to HttpOnly cookies would alter authentication architecture and frontend behaviour outside this phase.
- SEC-10 (session rotation / logout-all) — partially addressed: `POST /api/auth/logout-all` added; rotation and scheduled cleanup remain.
- SEC-11 (CSRF tokens) — not added; bearer-header design avoids classic CSRF, but this remains a documented assumption.
- SEC-12 (failed-auth audit records) — not added.
- Escrow contract integration, Mainnet, live wallet signing — out of scope.

## Changes made

### Architecture

- Added `backend/app/services.py` state machines (`AGREEMENT_TRANSITIONS`, `DISPUTE_TRANSITIONS`), `assert_transition`, and `lock_row` for optimistic/pessimistic concurrency control at the application layer.
- Added `backend/app/ratelimit.py`: in-process sliding-window limiter keyed by trusted `request.client.host`, with `RATE_LIMIT_ENABLED` config and `reset_rate_limits()` for tests.
- Existing domain routers preserved; no rebuild or restructuring of the frontend.

### Workflow improvements

- Agreement acceptance is idempotent for genuine repeats and rejects terminal states with HTTP 409.
- Agreement reject/cancel enforce valid transitions and lock the row inside the transaction.
- Dispute evidence advances `open -> under_review` via the state machine; proposals only from `open`/`under_review`; amendments are explicit (`POST /api/disputes/{id}/amend`) with version increment, audit event, and notification; the counterparty must accept the exact stored resolution.
- Payment confirmation locks milestone and agreement rows, re-checks state, and validates every payment-intent field against the agreement and parties.

### Payment integrity

- Partial unique index prevents a second confirmed payment per milestone (PostgreSQL and SQLite compatible).
- Transaction-hash idempotency preserved; duplicate hash on another milestone still returns 409.
- Confirmation still requires: approved milestone, active agreement, no unresolved dispute, valid addresses, Horizon success, registered source/destination, native XLM, exact amount, and matching memo where an intent exists.
- Invoice generation remains inside the same transaction as payment confirmation.

### Security

- Restricted CORS methods/headers; credentials only for configured origins.
- Generic client-facing errors for Horizon failures; exception type logged server-side without secrets or URLs.
- Shared address validator (`G[A-Z2-7]{55}`) used at profile update, account lookup, payment-intent creation, and confirmation.
- Rate limits: register 10/min, login 10/min, payment intent 20/min, payment confirm 20/min, payment verify 30/min, dispute open/resolve 10/min, account lookup 30/min, directory 60/min.
- `POST /api/auth/logout-all` revokes all sessions for the current user.
- Input bounds added to schemas (description lengths, milestone counts, URL scheme/host validation). CSV cells beginning with `=`, `+`, `-`, `@` are escaped.

### Database

- `payment_records`: partial unique index `uq_confirmed_milestone_payment` plus `ix_payment_status_created`.
- `disputes`: `proposal_version` column plus `ix_dispute_agreement_status`.
- `notifications`, `audit_logs`, `payment_intents`: indexes added.
- `ensure_schema()` detects pre-existing duplicate confirmed payments and refuses to migrate rather than deleting financial records; creates missing indexes idempotently.

## Files changed

Backend: `app/database.py`, `app/main.py`, `app/models.py`, `app/schemas.py`, `app/services.py`, `app/ratelimit.py` (new), `app/routers/agreements.py`, `app/routers/disputes.py`, `app/routers/finance.py`, `app/routers/projects.py`, `tests/conftest.py` (new), `tests/test_phase2_remediation.py` (new).

Frontend (functional only, no visual change): `components/ProjectWorkspace.tsx`, `lib/milestones.ts` (new), `lib/milestones.test.ts` (new).

Reports: `FREELANCEFLOW_PHASE2_REMEDIATION_REPORT.md`, `FREELANCEFLOW_PHASE2_SECURITY_REPORT.md`, `FREELANCEFLOW_PHASE2_DATABASE_REPORT.md`.

## Tests added

23 backend tests in `test_phase2_remediation.py` covering cancelled reactivation, repeated acceptance, unauthorized acceptance, invalid transitions, history preservation, proposal overwrite/amendment, self-approval rejection, dispute payment freeze, malformed addresses, unauthenticated lookup, login/intent rate limits, CORS, generic Horizon errors, DB payment uniqueness, cancelled-agreement payment, input validation, cross-user access, directory query count, and duplicate-record migration refusal. 3 frontend unit tests for exact milestone splitting.

## Test execution results

| Suite | Command | Result |
|---|---|---|
| Backend | `.venv/bin/python -m pytest -ra` | **56 passed** (33 baseline + 23 new) |
| Backend coverage | `pytest --cov=app` | `main.py` 83%, `models.py` 100%, `database.py` 87%, `services.py` 87%, `ratelimit.py` 93%, routers 77–92% |
| Frontend | `npm test` | **44 passed / 6 files** |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Frontend build | `npm run build` | success, 13 routes |
| Contract | `cargo test --locked` | **8 passed** |
| E2E | `npm run test:e2e` | **3 passed** |

## Remaining risks

- In-process rate limits reset per worker; multi-worker or multi-instance deployments need edge rate limiting.
- `updated_at` on agreement is not used as an optimistic-concurrency token; row locks protect transitions within a transaction, but distributed concurrency across database connections relies on the DB lock/` FOR UPDATE` semantics.
- Dispute resolution remains application-level; the Soroban contract is not invoked and has no on-chain resolution function.
- Low-severity SEC-09/11/12 items remain as listed above.

## Blockers

None for the implemented scope. Live wallet signing and Mainnet remain explicitly out of scope. No financial records were deleted and no existing tests were weakened.
