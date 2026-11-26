# FreelanceFlow — Final Remaining Risks

Severity-ranked. Nothing here is hidden; none of these invalidate the Testnet MVP demonstration.

## HIGH

1. **Soroban escrow is deployed but not integrated.** The payment flow uses direct Stellar payments verified by Horizon, not contract funding/release. Do not describe funds as contract-escrowed. Integration needs wallet-signed contract transactions and backend contract-state verification.
2. **No live funded-wallet approval was executed.** Signing/submission are tested at the SDK boundary only; real browser approval remains unverified in this environment.
3. **No production financial-service assurance.** No third-party audit, penetration test, regulatory review, or Mainnet operation.

## MEDIUM

4. **In-process rate limiting.** Each API worker keeps its own counters; multi-worker/multi-instance deployments need edge rate limiting.
5. **No live passphrase comparison at UI submission time beyond wallet check.** Backend validates passphrase before confirmation; browser checks Freighter passphrase before signing.
6. **Single-fetch finality model with bounded retry.** Horizon `successful: true` is used; no confirmation-depth policy or long-running pending/failure state machine.
7. **No password reset or email verification.** Account recovery is not implemented.
8. **No production monitoring/alerting.** Request logs exist; no centralized metrics, error tracking or alert routing.
9. **Railway deployment skipped.** GHCR images are published, but no live Railway deploy occurred because secrets are absent.
10. **PostgreSQL restore drill not performed.** Only SQLite backup/restore was executed against a disposable database.
11. **Migration system is additive, not versioned.** No rollback framework or migration checksums.
12. **Dependency scanning limited.** `npm audit --omit=dev` passed; no Python vulnerability scanner was installed.

## LOW

13. **Bearer token in `sessionStorage`.** XSS exposure; cookie+CSRF redesign is a separate architectural decision.
14. **No CSRF tokens.** Bearer-header design avoids classic CSRF; documented assumption only.
15. **Failed-login audit exists but no alerting.**
16. **Expired sessions cleaned at startup, not by a scheduled job.**
17. **Cosmetic `/favicon.ico` 404** in browser console; excluded from E2E assertions.
18. **`next start` warning with standalone output.** Local E2E uses `next start`; production Dockerfile correctly uses `node .next/standalone/server.js`.
19. **No accessibility audit tool executed.** E2E checks routes, console errors and horizontal overflow; no axe/Lighthouse run.

## Explicitly not claimed

- No Mainnet deployment.
- No real money.
- No private keys or recovery phrases stored, requested or logged.
- No simulated payment presented as confirmed.
- No escrow-backed funds claim.
- No production readiness claim.
- No perfect/maximum-quality claim.
