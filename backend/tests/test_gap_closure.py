"""Final gap closure: distributed limits and account recovery flows."""

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AccountToken, RateLimitCounter, Session
from app.ratelimit import check_rate_limit, reset_rate_limits

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_rate_limits()
    yield
    reset_rate_limits()
    Base.metadata.drop_all(bind=engine)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(role: str, name: str) -> tuple[str, str, str]:
    response = client.post("/api/auth/register", json={
        "email": f"gap-{name}@example.com",
        "password": "secure-pass-123",
        "full_name": name,
        "role": role,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    return data["token"], data.get("verification_token", ""), client.get("/api/me", headers=auth(data["token"])).json()["id"]


def test_rate_limit_counter_is_shared_through_database():
    for _ in range(3):
        check_rate_limit("gap_test", "shared-client", 3, 60)
    with pytest.raises(Exception) as error:
        check_rate_limit("gap_test", "shared-client", 3, 60)
    assert getattr(error.value, "status_code", None) == 429
    with SessionLocal() as db:
        row = db.query(RateLimitCounter).filter(RateLimitCounter.scope == "gap_test").one()
        assert row.count == 3


def test_rate_limit_survives_new_session_factory():
    check_rate_limit("gap_session", "client-a", 2, 60)
    with SessionLocal() as db:
        rows = db.query(RateLimitCounter).filter(RateLimitCounter.scope == "gap_session").all()
        assert len(rows) == 1
        assert rows[0].count == 1


def test_email_verification_is_single_use(monkeypatch):
    monkeypatch.setenv("EMAIL_DEV_MODE", "true")
    token, verification, user_id = register("client", "verify")
    assert verification
    assert client.get("/api/me", headers=auth(token)).json()["email_verified"] is False
    assert client.post("/api/auth/verify-email", json={"token": verification}).status_code == 200
    assert client.get("/api/me", headers=auth(token)).json()["email_verified"] is True
    assert client.post("/api/auth/verify-email", json={"token": verification}).status_code == 400
    with SessionLocal() as db:
        record = db.query(AccountToken).filter(AccountToken.token_hash.is_not(None)).first()
        assert record.used_at is not None


def test_resend_invalidates_previous_verification_token(monkeypatch):
    monkeypatch.setenv("EMAIL_DEV_MODE", "true")
    token, first, _ = register("client", "resend")
    response = client.post("/api/auth/resend-verification", headers=auth(token))
    assert response.status_code == 200
    second = response.json()["verification_token"]
    assert first != second
    assert client.post("/api/auth/verify-email", json={"token": first}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": second}).status_code == 200


def test_password_reset_is_single_use_and_revokes_sessions(monkeypatch):
    monkeypatch.setenv("EMAIL_DEV_MODE", "true")
    token, _, _ = register("client", "reset")
    request = client.post("/api/auth/forgot-password", json={"email": "gap-reset@example.com"})
    assert request.status_code == 202
    reset_token = request.json()["reset_token"]
    assert client.post("/api/auth/reset-password", json={"token": reset_token, "password": "new-secure-pass"}).status_code == 200
    assert client.get("/api/me", headers=auth(token)).status_code == 401
    assert client.post("/api/auth/login", json={"email": "gap-reset@example.com", "password": "new-secure-pass"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": reset_token, "password": "another-pass"}).status_code == 400


def test_password_reset_does_not_reveal_account_existence(monkeypatch):
    monkeypatch.setenv("EMAIL_DEV_MODE", "true")
    known = client.post("/api/auth/forgot-password", json={"email": "gap-unknown@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "gap-absent@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json().keys() == unknown.json().keys()
    assert "reset_token" not in unknown.json()


def test_delivery_is_not_claimed_without_configuration():
    response = client.post("/api/auth/forgot-password", json={"email": "gap-none@example.com"})
    assert response.json()["email_delivery_configured"] is False
