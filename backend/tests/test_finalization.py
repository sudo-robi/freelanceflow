"""Finalization hardening: audit trail, request correlation and session cleanup."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import database
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AuditLog, Session

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_failed_login_is_audited_without_secrets():
    response = client.post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    with SessionLocal() as db:
        entries = db.query(AuditLog).filter(AuditLog.action == "invalid_credentials").all()
    assert len(entries) == 1
    assert "wrong-password" not in entries[0].details
    assert entries[0].actor_id is None


def test_every_response_has_request_id():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    second = client.get("/api/health")
    assert second.headers["X-Request-ID"] != response.headers["X-Request-ID"]


def test_expired_sessions_are_cleaned_on_startup():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    now = datetime.utcnow()
    with SessionLocal() as db:
        db.add(Session(token="expired-token", user_id="missing-user", expires_at=now - timedelta(days=1)))
        db.add(Session(token="valid-token", user_id="missing-user", expires_at=now + timedelta(days=1)))
        db.commit()
    database._cleanup_expired_sessions()
    with SessionLocal() as db:
        tokens = {row.token for row in db.query(Session).all()}
    assert tokens == {"valid-token"}
