# API Documentation

Interactive FastAPI documentation is available at `/docs` when the backend is running.

## Authentication

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`
- `PUT /api/me`

All protected routes use `Authorization: Bearer <session-token>`.

## Core resources

- `GET/POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/invitations`
- `POST /api/invitations/{invitation_id}/accept`
- `POST /api/projects/{project_id}/agreements`
- `POST /api/agreements/{agreement_id}/accept`
- `POST /api/milestones/{milestone_id}/submit`
- `POST /api/milestones/{milestone_id}/review`
- `GET /api/freelancers`
- `GET /api/notifications`
- `POST /api/notifications/{notification_id}/read`
- `GET /api/payments`

## Stellar

- `GET /api/stellar/account/{address}`
- `GET /api/payments/{transaction_hash}/verify`
- `POST /api/payments/{transaction_hash}/confirm`

The confirmation route requires exact source, destination, native asset, and milestone amount validation independently against Horizon.
