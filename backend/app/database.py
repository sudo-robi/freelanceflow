import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./freelanceflow.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the initial release. Applied idempotently so existing
# SQLite/PostgreSQL databases can start with the current models.
_ADDED_COLUMNS = {
    "freelancer_profiles": {
        "skills": "TEXT DEFAULT ''",
        "available": "BOOLEAN DEFAULT 1",
        "availability_note": "TEXT DEFAULT ''",
    },
    "projects": {
        "updated_at": "DATETIME",
        "completed_at": "DATETIME",
        "cancelled_at": "DATETIME",
    },
    "work_agreements": {"version": "INTEGER DEFAULT 1"},
    "agreement_milestones": {
        "submission_count": "INTEGER DEFAULT 0",
        "submitted_at": "DATETIME",
        "reviewed_at": "DATETIME",
    },
    "payment_records": {"intent_id": "VARCHAR(36)", "memo": "VARCHAR(28)"},
    "disputes": {"proposal_version": "INTEGER DEFAULT 0"},
    "notifications": {
        "category": "VARCHAR(40) DEFAULT 'general'",
        "entity_type": "VARCHAR(40)",
        "entity_id": "VARCHAR(36)",
    },
}


def ensure_schema() -> None:
    """Create missing tables and add missing columns without dropping data."""
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, columns in _ADDED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in columns.items():
            if name not in existing:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
    _enforce_payment_integrity(engine)
    _add_missing_indexes(engine)


def _enforce_payment_integrity(engine) -> None:
    """Create the confirmed-per-milestone unique index after checking existing data."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "payment_records" not in inspector.get_table_names():
        return
    with engine.connect() as connection:
        duplicates = connection.execute(text(
            "SELECT milestone_id, COUNT(*) AS c FROM payment_records "
            "WHERE status = 'confirmed' GROUP BY milestone_id HAVING c > 1"
        )).all()
    if duplicates:
        raise RuntimeError(
            "Refusing to migrate: existing confirmed duplicate payments for milestone(s) "
            + ", ".join(str(row[0]) for row in duplicates[:10])
            + ". Reconcile financial records manually before starting the application."
        )
    existing = {item["name"] for item in inspector.get_indexes("payment_records")}
    if "uq_confirmed_milestone_payment" not in existing:
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE UNIQUE INDEX uq_confirmed_milestone_payment "
                "ON payment_records(milestone_id) WHERE status = 'confirmed'"
            ))


def _add_missing_indexes(engine) -> None:
    """Add indexes introduced after the initial release to existing tables."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    wanted = {
        "notifications": ["ix_notification_user_read"],
        "audit_logs": ["ix_audit_entity"],
        "payment_intents": ["ix_intent_milestone_status"],
        "disputes": ["ix_dispute_agreement_status"],
        "payment_records": ["ix_payment_status_created"],
    }
    columns = {
        "ix_notification_user_read": ("notifications", "(user_id, read)"),
        "ix_audit_entity": ("audit_logs", "(entity_type, entity_id)"),
        "ix_intent_milestone_status": ("payment_intents", "(milestone_id, status)"),
        "ix_dispute_agreement_status": ("disputes", "(agreement_id, status)"),
        "ix_payment_status_created": ("payment_records", "(status, created_at)"),
    }
    tables = set(inspector.get_table_names())
    for table, names in wanted.items():
        if table not in tables:
            continue
        existing = {item["name"] for item in inspector.get_indexes(table)}
        for name in names:
            if name not in existing:
                _, expression = columns[name]
                with engine.begin() as connection:
                    connection.execute(text(f"CREATE INDEX {name} ON {table} {expression}"))
