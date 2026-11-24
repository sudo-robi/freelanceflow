"""Schema upgrade tests: an existing database must survive the new columns."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app import database


def test_ensure_schema_adds_columns_without_dropping_data(monkeypatch, tmp_path: Path):
    database_file = tmp_path / "legacy.db"
    legacy = create_engine(f"sqlite:///{database_file}")
    with legacy.begin() as connection:
        connection.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY, email VARCHAR(255), password_hash VARCHAR(255),
                role VARCHAR(20), full_name VARCHAR(255), stellar_address VARCHAR(56), created_at DATETIME
            )
        """))
        connection.execute(text("""
            CREATE TABLE freelancer_profiles (
                id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36), title VARCHAR(255),
                description TEXT, hourly_rate NUMERIC(12,2), project_rate NUMERIC(12,2)
            )
        """))
        connection.execute(text("INSERT INTO users (id, email, password_hash, role, full_name, created_at) VALUES ('u1','legacy@example.com','hash','client','Legacy User','2026-01-01 00:00:00')"))

    monkeypatch.setattr(database, "engine", legacy)
    database.ensure_schema()
    database.ensure_schema()  # idempotent

    inspector = inspect(legacy)
    profile_columns = {column["name"] for column in inspector.get_columns("freelancer_profiles")}
    assert {"skills", "available", "availability_note"}.issubset(profile_columns)
    assert {"disputes", "payment_intents", "invoices", "agreement_revisions", "portfolio_items"}.issubset(
        set(inspector.get_table_names())
    )
    with legacy.connect() as connection:
        assert connection.execute(text("SELECT full_name FROM users WHERE id = 'u1'")).scalar_one() == "Legacy User"
    legacy.dispose()


def test_application_startup_creates_schema():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").json()["network"] == "stellar-testnet"
