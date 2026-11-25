# FreelanceFlow Phase 1 — Defensive Security Audit

Date: 2026-11-25. Scope: application, contract, configuration, and executed tests. This is a defensive review, not an independent penetration test or certification. No unrelated third-party systems were tested.

## Finding summary

| ID | Severity | Component | Status |
|---|---|---|---|
| SEC-01 | HIGH | `main.py::accept_agreement` | OPEN — reproduced |
| SEC-02 | MEDIUM | `main.py::update_me` | OPEN — reproduced |
| SEC-03 | MEDIUM | `routers/disputes.py::propose_resolution` | OPEN — reproduced |
| SEC-04 | MEDIUM | `models.py::PaymentRecord` | OPEN — design evidence |
| SEC-05 | MEDIUM | Auth/intent endpoints | OPEN — no implementation |
| SEC-06 | MEDIUM | `main.py` CORS middleware | OPEN |
| SEC-07 | MEDIUM | Horizon error handling | OPEN |
| SEC-08 | MEDIUM | Unauthenticated Horizon proxy | OPEN |
| SEC-09 | LOW | Frontend token storage | OPEN |
| SEC-10 | LOW | Session lifecycle | OPEN |
| SEC-11 | LOW | CSRF posture | OPEN (Bearer mitigates) |
| SEC-12 | LOW | Failed-auth audit trail | OPEN |
| FIX-01..08 | — | Previously reported issues | FIXED, tests present |

## Detailed findings

### SEC-01 — Cancelled agreement can be reactivated (HIGH)

- **Component:** `backend/app/main.py::accept_agreement` (lines 332–354).
- **Evidence:** the endpoint checks only party membership, then sets `client_accepted`/`freelancer_accepted`. If both flags are already true, it unconditionally sets `agreement.status = "active"` and `project.status = "active"`. There is no state guard for `cancelled`, `disputed`, or paid agreements.
- **Impact:** a party can bypass cancellation and restore a terminated agreement, reopening work and payment paths.
- **Reproduction (isolated local DB):** create project → invite → accept → agreement → both accept → cancel → re-call `POST /api/agreements/{id}/accept`. Observed: `cancelled -> 200 active`.
- **Remediation:** reject acceptance when `status` is terminal (`cancelled`, `active`, `disputed`) or when a confirmed payment exists; make acceptance idempotent without state mutation.
- **Test exists:** No. Existing tests cover normal acceptance only.

### SEC-02 — Inconsistent Stellar address validation (MEDIUM)

- **Component:** `main.py::update_me` line 146 vs `services.py::is_stellar_address`.
- **Evidence:** profile update accepts any 56-character string beginning with `G`; payment flows use a base32 regex `G[A-Z2-7]{55}`.
- **Impact:** syntactically invalid addresses can be persisted; intent creation then fails later, and mismatched addresses can confuse reconciliation.
- **Reproduction:** `PUT /api/me` with `"G" + "!"*55` returned **200** and stored the value.
- **Remediation:** use the shared validator at the profile boundary too.
- **Test exists:** partial (valid-address test only).

### SEC-03 — Dispute resolution proposal overwrite (MEDIUM)

- **Component:** `routers/disputes.py::propose_resolution` (lines 144–165).
- **Evidence:** no guard prevents a party from proposing a new resolution while the dispute is already `awaiting_counterparty`; the endpoint overwrites `resolution`, `proposed_by`, and status.
- **Impact:** the counterparty can approve a resolution different from the one originally presented; weakens two-party agreement integrity.
- **Reproduction:** open dispute → propose `refund_client` → propose `release_freelancer` by the same party. Observed: second call **200**, stored resolution changed, proposer unchanged.
- **Remediation:** only allow proposals from `open`/`under_review`; consider one proposal per dispute and an explicit amendment flow.
- **Test exists:** No.

### SEC-04 — No database-level per-milestone payment uniqueness (MEDIUM)

- **Component:** `models.py::PaymentRecord` — unique constraint exists only on `transaction_hash`.
- **Evidence:** two concurrent confirmations with different hashes for the same milestone both pass the pre-check `PaymentRecord.milestone_id == ...` before commit. SQLite test isolation cannot exercise this; it is a design-level gap.
- **Impact:** duplicate verified payments / double release for one milestone under concurrency.
- **Remediation:** add a unique constraint on `(milestone_id)` for confirmed records (partial unique index in PostgreSQL) or use a locking/transaction boundary.
- **Test exists:** same-hash duplicate test only.

### SEC-05 — No rate limiting or abuse controls (MEDIUM)

- **Evidence:** source grep found no rate-limit or throttling implementation on `/api/auth/login`, `/api/auth/register`, `/api/payment-intents`, or Horizon proxy endpoints.
- **Impact:** credential brute force, registration spam, and costly external API amplification.
- **Remediation:** per-IP and per-account limits with 429 responses; reverse-proxy limits in deployment.
- **Test exists:** No.

### SEC-06 — Broad CORS with credentials (MEDIUM)

- **Evidence:** `allow_origins` is configurable (good), but `allow_methods=["*"]` and `allow_headers=["*"]` are combined with `allow_credentials=True`.
- **Impact:** unnecessary preflight surface if an origin is misconfigured; no method/header least privilege.
- **Remediation:** allow only used methods (`GET, POST, PUT, PATCH, DELETE`) and headers (`Authorization, Content-Type`).
- **Test exists:** No.

### SEC-07 — Internal Horizon error details returned to clients (MEDIUM)

- **Evidence:** 502 responses include `f"Horizon verification failed: {error}"` in `verify_transaction`, `confirm_payment`, and `stellar_account`.
- **Impact:** internal URLs, exception text, and network details may be disclosed.
- **Remediation:** log server-side, return a generic message.
- **Test exists:** No.

### SEC-08 — Unauthenticated Horizon account proxy (MEDIUM)

- **Evidence:** `GET /api/stellar/account/{address}` requires no auth and validates only string length, unlike the strict validator used elsewhere.
- **Impact:** third parties can use the deployment as a free Horizon proxy / enumeration vector.
- **Remediation:** require auth, apply strict validator, add rate limits.
- **Test exists:** No.

### SEC-09 — Token stored in `sessionStorage` (LOW)

- **Evidence:** `frontend/lib/api.ts` uses `sessionStorage` for the bearer token.
- **Impact:** any XSS can read the token. Bearer tokens are not HttpOnly cookies.
- **Remediation:** consider HttpOnly Secure SameSite cookies with CSRF tokens; at minimum enforce a strict CSP.
- **Test exists:** token-presence tests only.

### SEC-10 — Session lifecycle gaps (LOW)

- **Evidence:** 7-day sessions; no rotation on login, no "logout everywhere", no scheduled cleanup of expired rows (they are deleted only when encountered).
- **Remediation:** session rotation, revocation endpoint, periodic cleanup task.
- **Test exists:** invalid/expired-session rejection test.

### SEC-11 — CSRF posture (LOW)

- **Evidence:** no CSRF token implementation. Bearer header (not cookie) removes classic CSRF, but CORS wildcard methods increase misconfiguration risk.
- **Remediation:** keep bearer-only; tighten CORS; add explicit SameSite cookie policy if cookies are introduced.

### SEC-12 — No audit record for failed authentication (LOW)

- **Evidence:** failed login and authorization denials produce HTTP errors but no `AuditLog` entry.
- **Impact:** brute-force attempts are invisible to operators.
- **Remediation:** log failed auth events with IP and timestamp, with privacy care.

## Previously fixed findings (retained for continuity)

| ID | Issue | Correction | Test |
|---|---|---|---|
| FIX-01 | Arbitrary hash treated as payment proof | Horizon success + source/destination/native asset/exact amount + memo binding; no client ledger | `test_auth_projects.py`, `test_platform_workflows.py` |
| FIX-02 | No dispute API | Dispute state blocks submit/review/confirm/cancel/complete; two-party resolution | dispute tests |
| FIX-03 | Soroban `cancel()` left non-zero balance | Balance zeroed after refund | `lib_test.rs` |
| FIX-04 | Missing ownership checks on new routers | `get_current_user` + per-object checks | authorization tests |
| FIX-05 | Public directory leaked private fields | Explicit public projection | profile isolation test |
| FIX-06 | `isConnected()` object truthiness bug | Checks field and error | `stellar.test.ts` |
| FIX-07 | Existing DBs lacked new columns | Idempotent `ensure_schema()` | `test_migration.py` |
| FIX-08 | Arbitrary URLs accepted | HTTP(S) validation at boundaries | milestone/dispute tests |

## Positive security properties

- PBKDF2-HMAC-SHA256, 200,000 iterations, random salt, constant-time comparison.
- High-entropy session tokens with expiry enforcement.
- Server-side role and object ownership checks across private resources.
- Decimal-based financial validation and `Numeric(12, 2)` storage.
- Native Testnet XLM only; no private keys, seed phrases, or `.env` in the repository.
- Security headers on all responses; CORS origins configurable.
- Independent Horizon verification with duplicate-hash idempotency.

## Security testing status

Executed: 33 backend tests (including negative payment and authorization cases), 41 frontend unit tests, 3 E2E tests, 8 contract tests, four isolated reproductions above. Not executed: penetration test, dependency vulnerability scan (no scanner installed), live wallet signing, Mainnet testing (explicitly out of scope).
