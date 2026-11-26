# API Documentation

Interactive FastAPI documentation is available at `/docs` when the backend runs. All protected routes use `Authorization: Bearer <session-token>`.

## Authentication and account

- `POST /api/auth/register` — creates user + role profile, returns session token.
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/logout-all` — revoke all sessions for the current user
- `POST /api/auth/verify-email` — single-use email verification token
- `POST /api/auth/resend-verification` — authenticated resend
- `POST /api/auth/forgot-password` — always 202; no account enumeration
- `POST /api/auth/reset-password` — single-use token, revokes sessions
- `GET /api/me` — account and role profile.
- `PUT /api/me` — name, Stellar address, title, description, rates, skills.
- `PUT /api/me/availability` — freelancer availability and note.
- `POST /api/me/portfolio`, `DELETE /api/me/portfolio/{item_id}`
- `GET /api/freelancers` — `skill`, `available_only`, `min_rate`, `max_rate`, `sort`, `limit`, `offset`.
- `GET /api/freelancers/{id}` — public profile and portfolio; no email, hash, or Stellar address.

## Projects and invitations

- `GET/POST /api/projects`
- `GET /api/projects/{id}` — includes `agreement_id`, owner and assignee IDs.
- `PUT /api/projects/{id}` — client-only edit while editable.
- `POST /api/projects/{id}/cancel`, `POST /api/projects/{id}/complete`.
- `GET /api/projects/{id}/activity`
- `POST /api/projects/{id}/invitations`
- `GET /api/invitations`
- `POST /api/invitations/{id}/accept|reject|expire`

## Agreements and milestones

- `POST /api/projects/{id}/agreements`
- `GET /api/agreements/{id}` — milestones, acceptance, version, active dispute.
- `PUT /api/agreements/{id}` — creates a new version; previous snapshot stored.
- `GET /api/agreements/{id}/revisions`, `GET /api/agreements/{id}/activity`.
- `POST /api/agreements/{id}/accept|reject|cancel`
- `PUT /api/agreements/{id}/milestones` — pre-acceptance replacement; total must match agreement.
- `GET /api/milestones/{id}` — status, funding status, history.
- `POST /api/milestones/{id}/start|review-start|submit|review`

## Payments and finance

- `POST /api/payment-intents` — client-only; binds amount, source, destination, network, memo.
- `GET /api/payment-intents/{id}`
- `GET /api/payments/{hash}/verify`, `POST /api/payments/{hash}/confirm`
- `GET /api/payments`, `GET /api/payments/summary`, `GET /api/payments/export.csv`
- `GET /api/payments/{payment_id}/receipt`
- `GET /api/invoices`, `GET /api/invoices/{id}/pdf`
- `GET /api/finance/report`

Confirmation requires a 64-character hex hash, approved milestone, client ownership, valid addresses, no active dispute, successful Horizon transaction, matching source/destination/native asset/exact amount, and (when present) matching payment-intent memo. Duplicate hashes return the existing record without creating a second payment or invoice.

## Disputes

- `POST /api/disputes`, `GET /api/disputes`, `GET /api/disputes/{id}`
- `POST /api/disputes/{id}/evidence`
- `POST /api/disputes/{id}/resolve` — proposes `release_freelancer`, `refund_client`, or `cancel_agreement`.
- `POST /api/disputes/{id}/accept` — counterparty accepts the exact proposal.

An open dispute blocks approval, submission, payment confirmation, cancellation, and completion. Resolution never moves funds by itself.

## Notifications, dashboard, Stellar

- `GET /api/notifications`, `GET /api/notifications/unread-count`, `POST /api/notifications/{id}/read`
- `GET /api/dashboard` — real project/payment/dispute/notification/activity data.
- `GET /api/stellar/network`
- `GET /api/stellar/transaction/{hash}` — authenticated independent Horizon verification.
- `GET /api/stellar/account/{address}` — informational balance lookup.
- `GET /api/health`
