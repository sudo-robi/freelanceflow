# FreelanceFlow Phase 2 — Database Report

## Schema changes

| Table | Change | Purpose |
|---|---|---|
| `payment_records` | `CREATE UNIQUE INDEX uq_confirmed_milestone_payment ON payment_records(milestone_id) WHERE status = 'confirmed'` | Prevent more than one confirmed payment per milestone |
| `payment_records` | `CREATE INDEX ix_payment_status_created ON payment_records(status, created_at)` | Faster financial aggregation/history ordering |
| `disputes` | Column `proposal_version INTEGER DEFAULT 0` | Versioned, auditable resolution amendments |
| `disputes` | `CREATE INDEX ix_dispute_agreement_status ON disputes(agreement_id, status)` | Faster active-dispute lookups on every workflow transition |
| `notifications` | `CREATE INDEX ix_notification_user_read ON notifications(user_id, read)` | Faster unread counts and per-user lists |
| `audit_logs` | `CREATE INDEX ix_audit_entity ON audit_logs(entity_type, entity_id)` | Faster activity history queries |
| `payment_intents` | `CREATE INDEX ix_intent_milestone_status ON payment_intents(milestone_id, status)` | Faster pending-intent lookup during confirmation |

The partial unique index is expressed in the SQLAlchemy model with `sqlite_where` and `postgresql_where`, and the migration uses portable partial-index DDL. Existing `transaction_hash` uniqueness and idempotent duplicate responses are preserved.

## Migration details

`ensure_schema()` now:

1. Creates missing tables (`Base.metadata.create_all`).
2. Adds missing columns idempotently, including the new `proposal_version`.
3. Checks for existing duplicate confirmed payments grouped by `milestone_id`.
4. Refuses startup with an actionable error if duplicates exist — it never deletes or silently rewrites financial records.
5. Creates the partial unique index and missing indexes only when absent.

This is additive and safe to re-run. It is not a versioned migration framework: there is no downgrade path or schema version table. That remains a documented Phase 6 operational item.

## Constraints and integrity improvements

- Database-enforced one-confirmed-payment-per-milestone, complemented by row locks on `AgreementMilestone` and `WorkAgreement` during confirmation.
- Application-level agreement and dispute state machines reject invalid transitions, preventing cancelled agreements from being reactivated and proposals from being silently replaced.
- Payment-intent fields (`agreement_id`, `freelancer_id`, expected source/destination, asset, network, amount) are all validated against the agreement before confirmation, preventing a payment record from being attached to an unrelated milestone or agreement.
- Foreign keys and cascade behaviour are unchanged; no destructive migration was introduced.

## Performance changes

- Freelancer directory now uses a single join between `FreelancerProfile`, `User`, and a grouped portfolio-count subquery, instead of one `User` lookup and one `COUNT(*)` per profile. A regression test counts SQL statements and asserts fewer than 12 for six profiles.
- Invitation listing now loads project titles in one query instead of two `db.get()` calls per invitation.
- Financial/history queries benefit from the new indexes.
- No unrelated queries were rewritten.

## Data reconciliation requirements

If an existing database contains two or more `status='confirmed'` payment records for the same `milestone_id`, startup will fail with a message listing affected milestone IDs. Safe reconciliation procedure:

1. Back up the database before any change.
2. Compare each duplicate's Horizon transaction, amount, source, destination, and timestamp against the milestone.
3. Keep the single record that matches the verified on-chain payment; correct any invoices referencing the superseded record.
4. Move superseded records to a separate audit archive table (do not delete them), set their status to `superseded`, then re-run startup so the unique index can be created.
5. Re-run `pytest` and verify financial totals before resuming production traffic.

No duplicate records existed in this repository's local databases, so no reconciliation was performed.

## Migration test results

| Test | Result |
|---|---|
| Existing `test_migration.py` legacy-column upgrade with data preserved | PASS |
| `test_migration_refuses_to_discard_duplicate_financial_records` | PASS — raises `RuntimeError`, leaves both records intact |
| Full backend suite after migration changes | **56 passed** |
| Coverage | `app/database.py` 87%, `app/models.py` 100% |
