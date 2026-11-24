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
