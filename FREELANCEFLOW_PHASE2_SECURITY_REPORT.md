# FreelanceFlow Phase 2 — Security Report

## Security issues fixed

| ID | Severity | Fix | Evidence |
|---|---|---|---|
| SEC-01 | HIGH | Agreement acceptance now rejects terminal states with 409, is idempotent for real repeats, locks the row, and emits notifications only on actual change | `test_cancelled_agreement_cannot_be_reactivated`, `test_repeated_acceptance_is_idempotent_without_notification_spam` |
| SEC-02 | MEDIUM | `update_me` uses the shared base32 validator `G[A-Z2-7]{55}` | `test_malformed_addresses_are_rejected` (5 malformed variants) |
| SEC-03 | MEDIUM | Dispute proposals cannot be overwritten; amendments are explicit, versioned, audited and notified; proposer cannot self-approve; counterparty must accept the exact stored resolution | `test_dispute_proposal_cannot_be_silently_overwritten` |
| SEC-04 | MEDIUM | Partial unique index prevents two confirmed payments per milestone; migration refuses to proceed on existing duplicates | `test_database_rejects_second_confirmed_payment_for_milestone`, `test_migration_refuses_to_discard_duplicate_financial_records` |
| SEC-05 | MEDIUM | Sliding-window rate limits using trusted transport IP for auth, payment, dispute, account and directory endpoints | `test_login_rate_limit_returns_429`, `test_payment_intent_rate_limit_returns_429` |
| SEC-06 | MEDIUM | CORS methods/headers restricted; credentials only for configured origins | `test_cors_does_not_allow_arbitrary_headers` |
| SEC-07 | MEDIUM | Horizon failures return generic messages; exception types logged without URLs or secrets | `test_horizon_failure_is_generic` |
| SEC-08 | MEDIUM | Account lookup requires authentication, strict validation and rate limiting | `test_account_lookup_requires_authentication`, malformed-address cases |
| Input validation | LOW/MEDIUM | Length limits, milestone-count bounds, absolute HTTP(S) URL validation, CSV formula escaping | `test_input_validation_rejects_unsafe_values` |
| Session lifecycle | LOW | `POST /api/auth/logout-all` revokes all user sessions | `test_unauthorized_acceptance_and_revocation` |
| Cross-user access | MEDIUM | Dispute/milestone/agreement ownership asserted for outsiders | `test_cross_user_private_resources_are_inaccessible` |

## Security tests added

23 backend tests in `backend/tests/test_phase2_remediation.py`, plus the existing 33 baseline security/authorization/payment tests retained unchanged. `conftest.py` isolates rate-limit state per test so limits do not leak across cases.

## Security limitations

- Rate limiting is in-process. Multiple API workers or instances each keep separate counters; a reverse proxy or gateway must also enforce limits. Configuration is via `RATE_LIMIT_ENABLED=true|false`; per-route limits are constants in the endpoint definitions.
- Client IP is taken from `request.client.host`, not spoofable `X-Forwarded-For`. Behind a proxy, configure the proxy to set the socket peer correctly or enforce limits at the edge.
- Bearer tokens remain in `sessionStorage` (SEC-09). Moving to HttpOnly cookies would require a coordinated frontend/auth design change and CSRF protection, intentionally deferred.
- No CSRF token layer (SEC-11) because requests use an Authorization header rather than cookies.
- Failed logins are not written to `AuditLog` (SEC-12).
- No scheduled cleanup of expired sessions; expired tokens are deleted when encountered.

## Remaining findings and residual risk

| Finding | Severity | Residual risk |
|---|---|---|
| SEC-09 | LOW | XSS could read the session token from browser storage. |
| SEC-11 | LOW | Cookie-based CSRF risk only if auth design changes; current bearer design avoids it. |
| SEC-12 | LOW | Brute-force attempts leave no audit trail. |
| Escrow integration | HIGH | Deployed Soroban contract is still not invoked; escrow state can diverge from application state. |
| Network identity | MEDIUM | Confirmation relies on configured Horizon URL; no live passphrase comparison at confirmation time. |
| Transaction finality | MEDIUM | Single Horizon fetch; no bounded retry/polling state machine. |
| Third-party audit | — | No independent pen test or formal contract audit was performed. |

No secret, private key, or recovery phrase was requested, logged, or stored. No Mainnet transaction or real funds were used. No existing test was weakened and no financial record was deleted.
