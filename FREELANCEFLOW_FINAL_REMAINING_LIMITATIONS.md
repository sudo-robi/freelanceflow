# FreelanceFlow — Final Remaining Limitations

Severity-ranked. Nothing here is hidden or presented as working.

## HIGH

1. **Soroban escrow is deployed but not integrated.** Payments use direct Stellar transactions verified by Horizon. Do not describe funds as contract-escrowed.
2. **No live funded-wallet signing was executed.** SDK-boundary tests and real Horizon reads were performed; browser approval remains unverified.
3. **No third-party audit or penetration test.** Internal defensive review only.

## MEDIUM

4. **Token remains in `sessionStorage`** — XSS exposure; HttpOnly cookie redesign not performed.
5. **No CSRF tokens** — bearer-header design avoids classic CSRF; documented assumption.
6. **Railway deployment skipped** — GHCR images published; deployment requires user secrets/project.
7. **Email delivery not configured** — verification/reset tokens are created but not delivered; UI and API report this honestly.
8. **No PostgreSQL restore drill** — SQLite drill passed; PostgreSQL recovery unverified.
9. **Migration system additive only** — no version table, checksums or automated rollback.
10. **No production monitoring/alerting** — request logs and IDs exist, no centralized stack.
11. **Rate-limit fail-open default** — available if DB counters fail; configurable to fail-closed.
12. **Escrow contract lacks on-chain dispute resolution** — application-level resolution only.

## LOW

13. No password reset/verification enforcement on protected routes — informational only.
14. No automated backup schedule; RPO/RTO not measured.
15. No dependency vulnerability scan for Python packages.
16. `next start` warning with standalone output in local E2E; production Dockerfile uses standalone server correctly.
17. No axe/Lighthouse accessibility certification.
18. Cosmetic favicon 404 excluded from E2E assertions.
19. No live Soroban contract invocation tests; contract tests use the Rust test environment.

## Explicitly not claimed

- Production financial-service readiness.
- Mainnet deployment or real funds.
- Integrated escrow.
- Live wallet confirmation.
- Perfect/maximum quality.
- Third-party certification.
