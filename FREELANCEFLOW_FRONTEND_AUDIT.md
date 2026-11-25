# FreelanceFlow Phase 1 — Frontend Technical & Functional Audit

Date: 2026-11-25. **No visual design, theme, typography, colour, layout, or component styling was changed.** This report lists technical and functional gaps only; implementation belongs to a later directed phase.

## 1. Structure and routing

| Route | Purpose | Data source |
|---|---|---|
| `/` | Marketing page with illustrative agreement preview (explicitly labelled "not live account data") | static |
| `/login`, `/register` | Session creation | `/api/auth/*` |
| `/dashboard` | Role-specific metrics, projects, payments, activity | `/api/dashboard` |
| `/projects`, `/projects/[id]` | Project list and full workspace | project/agreement/milestone/dispute APIs |
| `/directory`, `/directory/[id]` | Freelancer search and public profile | `/api/freelancers*` |
| `/wallet` | Freighter connection, real Horizon balances | `/api/stellar/account`, Freighter |
| `/payments`, `/disputes`, `/notifications`, `/profile` | Finance, dispute, notification, account management | corresponding APIs |
| `/api/[...path]` | Same-origin proxy to backend | `API_BACKEND_URL` |

Shared shell: `frontend/components/AppShell.tsx`. Payment logic: `frontend/lib/stellar.ts`. API helper: `frontend/lib/api.ts`.

## 2. What works (verified)

- Login/register forms call real APIs and persist tokens in `sessionStorage` (`api.test.ts`).
- Dashboard renders API-provided verified earnings, project counts, transaction hashes and activity; no fabricated earnings (`page.test.tsx`, E2E).
- Directory search, availability filter, sort, and public profile/portfolio rendering (E2E).
- Project workspace invokes real endpoints for invitations, agreements, milestones, disputes, and payments; E2E verified dispute creation and visible workflow freeze.
- Wallet checks Freighter `isConnected` field, network passphrase, and displays only Horizon-returned balances.
- Payments page downloads CSV, receipt JSON, and generated PDF using authenticated `fetch` + object URLs (no query-string token leakage).
- Production build succeeds: 13 routes, TypeScript exit 0, 41 unit tests, 3 E2E tests.

## 3. Functional defects and technical gaps

### FRONT-01 — Equal-split milestone creation can fail validation (MEDIUM, reproduced)

- **File:** `frontend/components/ProjectWorkspace.tsx` lines 256–268.
- **Evidence:** milestone amounts are computed as `total / milestoneCount` and sent as floats. With amount 100 and 3 milestones, the backend's 7-decimal Pydantic validation stores `33.3333333` each, summing to `99.9999999`, which fails the "milestone amounts must equal agreement amount" check (observed calculation: `99.9999999 != 100`).
- **Impact:** users cannot create agreements with non-divisible budgets unless they manually avoid the helper.
- **Recommendation:** compute integer-minor-unit allocations, assign the remainder to the last milestone, or expose per-milestone amount inputs.

### FRONT-02 — Revision feedback is hardcoded (MEDIUM)

- **File:** `ProjectWorkspace.tsx` line 126 sends `"Please revise the deliverable."` for every rejection.
- **Impact:** clients cannot provide real feedback; the backend supports `feedback` but the UI discards it.
- **Recommendation:** add a feedback textarea in the review action and pass its value.

### FRONT-03 — Unused state / dead code (LOW)

- `submittedHash` is set but never rendered (`ProjectWorkspace.tsx` line 62). The signed hash is shown only through a success notice.
- **Recommendation:** remove or display the submitted hash for auditability.

### FRONT-04 — No auth guard before rendering (LOW)

- Protected pages render immediately and show API errors (`Session expired`) after a failed fetch. There is no route-level redirect to `/login`.
- **Impact:** confusing empty states; no centralized session expiry handling.

### FRONT-05 — Silent error handling in directory/notifications (LOW)

- `directory/page.tsx` and `notifications/page.tsx` swallow fetch errors and render "No profiles"/"No notifications" instead of an error state.
- **Impact:** failures are indistinguishable from empty data.

### FRONT-06 — Playwright portability (LOW)

- `frontend/playwright.config.ts` hardcodes `/home/robi/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome`. It falls back to the default if the path is absent, but the path is environment-specific.
- **Recommendation:** use `PLAYWRIGHT_CHROMIUM_EXECUTABLE` env var or standard browser install.

### FRONT-07 — `next start` with standalone output (LOW)

- E2E web server logs: `"next start" does not work with "output: standalone"`. Tests still pass, but the supported local production command is `node .next/standalone/server.js`. The Dockerfile already uses that.
- **Recommendation:** align the E2E command with the standalone server.

### FRONT-08 — Dependency version breadth (LOW)

- `frontend/package.json` declares all dependencies as `latest`. `package-lock.json` pins actual installs and `npm ci` is used in the Dockerfile, so current builds are reproducible; regeneration is not.

### FRONT-09 — Proxied vs direct API URL (LOW)

- `API_URL` is empty in production unless `NEXT_PUBLIC_API_URL` is set, using the same-origin proxy. Docker Compose sets `http://localhost:8000`, bypassing the proxy and requiring backend CORS. Both work locally; behaviour differs by environment.

### FRONT-10 — No measured performance/a11y audit (LOW)

- No Lighthouse/axe run was executed. Forms generally use labels, but no automated accessibility assertion suite exists. No visual changes were made as part of this audit.

## 4. Test quality

- `api.test.ts`: token header, logout, header merge, error parsing, URL resolution — meaningful assertions.
- `api-proxy.test.ts`: 18 tests over configuration errors, encoding, header allowlist, body handling, 204/304/HEAD, all methods — meaningful.
- `stellar.test.ts`: Freighter connection/network rejection, transaction binding, rejected signature without submission, real hash return — meaningful, explicitly mocked at SDK boundary.
- `dashboard/page.test.tsx`: verifies API values render and errors do not fabricate data.
- `AppShell.test.tsx`: navigation surface.
- `e2e/workflows.spec.ts`: real backend + production frontend; registration/project creation, directory/profile, dispute freeze.

No frontend test currently covers FRONT-01..05.

## 5. Design ownership statement

This audit deliberately did not modify `globals.css`, component structure for aesthetic reasons, branding, typography, colour palette, spacing, or responsive visual behaviour. All identified UI issues are functional/technical and are deferred to a directed implementation phase.
