"""Phase 2 remediation regression tests.

Every critical finding from Phase 1 is reproduced here as a failing-then-fixed
assertion against the real application, with isolated local databases.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    AgreementMilestone,
    Dispute,
    Invoice,
    PaymentRecord,
    PortfolioItem,
    Project,
    ProjectInvitation,
    User,
    WorkAgreement,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def register(role: str, name: str) -> tuple[str, str]:
    response = client.post("/api/auth/register", json={
        "email": f"phase2-{name}@example.com",
        "password": "secure-pass-123",
        "full_name": name,
        "role": role,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    return result["token"], client.get("/api/me", headers=auth(result["token"])).json()["id"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def setup_agreement(client_token: str, freelancer_token: str, freelancer_id: str, budget: int = 100):
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Phase 2 project",
        "description": "A project for Phase 2 workflow tests.",
        "budget": budget,
    }).json()["id"]
    invitation_id = client.post(f"/api/projects/{project_id}/invitations", headers=auth(client_token), json={
        "freelancer_id": freelancer_id,
    }).json()["id"]
    client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(freelancer_token))
    agreement_id = client.post(f"/api/projects/{project_id}/agreements", headers=auth(client_token), json={
        "freelancer_id": freelancer_id,
        "amount": budget,
        "asset": "XLM",
        "description": "An agreement used for Phase 2 state tests.",
        "milestones": [{"title": "Delivery", "amount": budget}],
    }).json()["id"]
    return project_id, agreement_id


def accept_both(client_token: str, freelancer_token: str, agreement_id: str) -> None:
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(client_token))
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(freelancer_token))


def milestone_id(agreement_id: str) -> str:
    with SessionLocal() as db:
        return db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first().id


# ---------------------------------------------------------------------------
# SEC-01: agreement state integrity
# ---------------------------------------------------------------------------

def test_cancelled_agreement_cannot_be_reactivated():
    ct, _ = register("client", "cancel-client")
    ft, fid = register("freelancer", "cancel-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    accept_both(ct, ft, agreement_id)
    assert client.post(f"/api/agreements/{agreement_id}/cancel", headers=auth(ct)).status_code == 200
    response = client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ct))
    assert response.status_code == 409
    assert client.get(f"/api/agreements/{agreement_id}", headers=auth(ct)).json()["status"] == "cancelled"


def test_repeated_acceptance_is_idempotent_without_notification_spam():
    ct, _ = register("client", "idem-client")
    ft, fid = register("freelancer", "idem-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    accept_both(ct, ft, agreement_id)
    before = client.get("/api/notifications", headers=auth(ft)).json()
    response = client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ft))
    assert response.status_code == 200
    assert response.json()["idempotent"] is True
    after = client.get("/api/notifications", headers=auth(ft)).json()
    assert len(after) == len(before)
    assert client.get(f"/api/agreements/{agreement_id}", headers=auth(ct)).json()["status"] == "active"


def test_unauthorized_acceptance_and_revocation():
    ct, _ = register("client", "auth-client")
    ft, fid = register("freelancer", "auth-free")
    outsider, _ = register("client", "auth-outsider")
    _, agreement_id = setup_agreement(ct, ft, fid)
    assert client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(outsider)).status_code == 403
    accept_both(ct, ft, agreement_id)
    assert client.post("/api/auth/logout-all", headers=auth(outsider)).json()["revoked"] >= 1
    assert client.get("/api/me", headers=auth(outsider)).status_code == 401


def test_invalid_transitions_are_rejected_and_history_preserved():
    ct, _ = register("client", "trans-client")
    ft, fid = register("freelancer", "trans-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    client.post(f"/api/agreements/{agreement_id}/reject", headers=auth(ft))
    assert client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ct)).status_code == 409
    assert client.post(f"/api/agreements/{agreement_id}/cancel", headers=auth(ct)).status_code == 409
    assert client.post(f"/api/agreements/{agreement_id}/reject", headers=auth(ft)).status_code == 409
    history = client.get(f"/api/agreements/{agreement_id}/activity", headers=auth(ct)).json()
    assert any(item["action"] == "rejected" for item in history)


# ---------------------------------------------------------------------------
# SEC-03: dispute state machine
# ---------------------------------------------------------------------------

def make_dispute(ct: str, ft: str, agreement_id: str, mid: str) -> str:
    response = client.post("/api/disputes", headers=auth(ft), json={
        "agreement_id": agreement_id,
        "milestone_id": mid,
        "reason": "Delivered work does not match the agreed scope.",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_dispute_proposal_cannot_be_silently_overwritten():
    ct, _ = register("client", "disp-client")
    ft, fid = register("freelancer", "disp-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    mid = milestone_id(agreement_id)
    did = make_dispute(ct, ft, agreement_id, mid)
    first = client.post(f"/api/disputes/{did}/resolve", headers=auth(ft), json={"resolution": "refund_client"})
    assert first.status_code == 200
    assert first.json()["proposal_version"] == 1
    overwrite = client.post(f"/api/disputes/{did}/resolve", headers=auth(ft), json={"resolution": "release_freelancer"})
    assert overwrite.status_code == 409
    amended = client.post(f"/api/disputes/{did}/amend", headers=auth(ft), json={"resolution": "release_freelancer"})
    assert amended.status_code == 200
    assert amended.json()["proposal_version"] == 2
    detail = client.get(f"/api/disputes/{did}", headers=auth(ct)).json()
    assert any(item["action"] == "resolution_amended" for item in detail["history"])
    assert client.post(f"/api/disputes/{did}/accept", headers=auth(ft), json={"resolution": "release_freelancer"}).status_code == 403
    assert client.post(f"/api/disputes/{did}/accept", headers=auth(ct), json={"resolution": "refund_client"}).status_code == 409
    assert client.post(f"/api/disputes/{did}/accept", headers=auth(ct), json={"resolution": "release_freelancer"}).status_code == 200


def test_payment_blocked_while_dispute_unresolved(monkeypatch):
    ct, _ = register("client", "pay-dispute-client")
    ft, fid = register("freelancer", "pay-dispute-free")
    source, destination = "G" + "P" * 55, "G" + "Q" * 55
    client.put("/api/me", headers=auth(ct), json={"stellar_address": source})
    client.put("/api/me", headers=auth(ft), json={"stellar_address": destination})
    project_id, agreement_id = setup_agreement(ct, ft, fid)
    accept_both(ct, ft, agreement_id)
    mid = milestone_id(agreement_id)
    client.post(f"/api/milestones/{mid}/submit", headers=auth(ft), json={"deliverable_url": "https://example.com/work"})
    client.post(f"/api/milestones/{mid}/review?approved=true", headers=auth(ct), json={})
    did = make_dispute(ct, ft, agreement_id, mid)
    assert client.post("/api/payment-intents", headers=auth(ct), json={"milestone_id": mid}).status_code == 409
    assert client.post(f"/api/payments/{'1' * 64}/confirm?milestone_id={mid}", headers=auth(ct)).status_code == 409
    assert client.get("/api/disputes", headers=auth(ct)).json()[0]["id"] == did


# ---------------------------------------------------------------------------
# SEC-02 / SEC-08: address validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["G" + "!" * 55, "G" + "A" * 54, "G" + "a" * 55, "M" + "A" * 55, ""])
def test_malformed_addresses_are_rejected(bad):
    ft, _ = register("freelancer", f"addr-{abs(hash(bad)) % 100000}")
    response = client.put("/api/me", headers=auth(ft), json={"stellar_address": bad})
    assert response.status_code == 422
    account = client.get(f"/api/stellar/account/{bad}", headers=auth(ft)) if bad else None
    if account is not None:
        assert account.status_code == 422


def test_account_lookup_requires_authentication():
    assert client.get(f"/api/stellar/account/{'G' + 'A' * 55}").status_code == 401


def test_valid_address_is_still_accepted():
    ft, _ = register("freelancer", "addr-valid")
    assert client.put("/api/me", headers=auth(ft), json={"stellar_address": "G" + "A" * 55}).status_code == 200


# ---------------------------------------------------------------------------
# SEC-05: rate limiting
# ---------------------------------------------------------------------------

def test_login_rate_limit_returns_429():
    responses = [
        client.post("/api/auth/login", json={"email": "none@example.com", "password": "wrong-password"})
        for _ in range(11)
    ]
    assert responses[-1].status_code == 429
    assert responses[-1].headers.get("Retry-After")


def test_payment_intent_rate_limit_returns_429():
    ct, _ = register("client", "rate-client")
    ft, fid = register("freelancer", "rate-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    accept_both(ct, ft, agreement_id)
    mid = milestone_id(agreement_id)
    client.post(f"/api/milestones/{mid}/submit", headers=auth(ft), json={"deliverable_url": "https://example.com/work"})
    client.post(f"/api/milestones/{mid}/review?approved=true", headers=auth(ct), json={})
    responses = [client.post("/api/payment-intents", headers=auth(ct), json={"milestone_id": mid}) for _ in range(22)]
    assert responses[-1].status_code == 429


# ---------------------------------------------------------------------------
# SEC-06 / SEC-07: CORS and error responses
# ---------------------------------------------------------------------------

def test_cors_does_not_allow_arbitrary_headers():
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-custom-secret",
        },
    )
    allowed = response.headers.get("access-control-allow-headers", "")
    assert "x-custom-secret" not in allowed.lower()


def test_horizon_failure_is_generic(monkeypatch):
    ct, _ = register("client", "generic-client")
    ft, fid = register("freelancer", "generic-free")
    source, destination = "G" + "R" * 55, "G" + "S" * 55
    client.put("/api/me", headers=auth(ct), json={"stellar_address": source})
    client.put("/api/me", headers=auth(ft), json={"stellar_address": destination})
    _, agreement_id = setup_agreement(ct, ft, fid)
    accept_both(ct, ft, agreement_id)
    mid = milestone_id(agreement_id)
    client.post(f"/api/milestones/{mid}/submit", headers=auth(ft), json={"deliverable_url": "https://example.com/work"})
    client.post(f"/api/milestones/{mid}/review?approved=true", headers=auth(ct), json={})

    async def fail(_hash):
        raise RuntimeError("secret internal url https://internal.example/horizon")

    monkeypatch.setattr("app.main.get_transaction", fail)
    response = client.post(f"/api/payments/{'2' * 64}/confirm?milestone_id={mid}", headers=auth(ct))
    assert response.status_code == 502
    assert "internal.example" not in response.text
    assert response.json()["detail"] == "Upstream verification unavailable"


# ---------------------------------------------------------------------------
# SEC-04: payment integrity and constraints
# ---------------------------------------------------------------------------

def test_database_rejects_second_confirmed_payment_for_milestone():
    ct, _ = register("client", "unique-client")
    ft, fid = register("freelancer", "unique-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    mid = milestone_id(agreement_id)
    with SessionLocal() as db:
        for index in range(2):
            db.add(PaymentRecord(
                agreement_id=agreement_id,
                milestone_id=mid,
                amount=Decimal("100"),
                asset="XLM",
                transaction_hash=f"{index + 1:064x}",
                status="confirmed",
                network="testnet",
                confirmed_at=datetime.utcnow(),
            ))
        with pytest.raises(IntegrityError):
            db.commit()


def test_payment_requires_approved_active_agreement():
    ct, _ = register("client", "cancelpay-client")
    ft, fid = register("freelancer", "cancelpay-free")
    _, agreement_id = setup_agreement(ct, ft, fid)
    accept_both(ct, ft, agreement_id)
    mid = milestone_id(agreement_id)
    assert client.post(f"/api/agreements/{agreement_id}/cancel", headers=auth(ct)).status_code == 200
    assert client.post(f"/api/payments/{'3' * 64}/confirm?milestone_id={mid}", headers=auth(ct)).status_code == 409


# ---------------------------------------------------------------------------
# Input validation, ownership, performance and migrations
# ---------------------------------------------------------------------------

def test_input_validation_rejects_unsafe_values():
    ct, _ = register("client", "input-client")
    ft, _ = register("freelancer", "input-free")
    assert client.post("/api/projects", headers=auth(ct), json={
        "title": "Valid title",
        "description": "x" * 10001,
        "budget": 10,
    }).status_code == 422
    assert client.post("/api/me/portfolio", headers=auth(ft), json={
        "title": "Example",
        "url": "javascript:alert(1)",
    }).status_code == 422
    assert client.post("/api/me/portfolio", headers=auth(ft), json={
        "title": "Example",
        "url": "https://example.com/a",
    }).status_code == 201


def test_cross_user_private_resources_are_inaccessible():
    ct, _ = register("client", "owner-client")
    ft, fid = register("freelancer", "owner-free")
    outsider, _ = register("client", "outsider-client")
    project_id, agreement_id = setup_agreement(ct, ft, fid)
    mid = milestone_id(agreement_id)
    assert client.get(f"/api/agreements/{agreement_id}", headers=auth(outsider)).status_code == 403
    assert client.get(f"/api/milestones/{mid}", headers=auth(outsider)).status_code == 403
    dispute_id = make_dispute(ct, ft, agreement_id, mid)
    assert client.get(f"/api/disputes/{dispute_id}", headers=auth(outsider)).status_code == 403


def test_directory_query_count_does_not_grow_linearly():
    for index in range(6):
        token, uid = register("freelancer", f"perf-{index}")
        client.post("/api/me/portfolio", headers=auth(token), json={
            "title": "Work", "url": "https://example.com/work",
        })
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/api/freelancers")
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    assert response.status_code == 200
    assert len(response.json()) >= 6
    assert len(statements) < 12, f"directory issued {len(statements)} queries"


def test_migration_refuses_to_discard_duplicate_financial_records(tmp_path):
    from sqlalchemy import create_engine, text
    from app import database

    path = tmp_path / "duplicate.db"
    legacy = create_engine(f"sqlite:///{path}")
    with legacy.begin() as connection:
        connection.execute(text("""
            CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255),
            password_hash VARCHAR(255), role VARCHAR(20), full_name VARCHAR(255),
            stellar_address VARCHAR(56), created_at DATETIME)
        """))
        connection.execute(text("""
            CREATE TABLE payment_records (id VARCHAR(36) PRIMARY KEY, agreement_id VARCHAR(36),
            milestone_id VARCHAR(36), amount NUMERIC(12,2), asset VARCHAR(20),
            transaction_hash VARCHAR(64), status VARCHAR(20), created_at DATETIME)
        """))
        for index in (1, 2):
            connection.execute(text(
                "INSERT INTO payment_records (id, milestone_id, transaction_hash, status) "
                f"VALUES ('p{index}', 'm1', 'h{index}', 'confirmed')"
            ))
    original = database.engine
    database.engine = legacy
    try:
        with pytest.raises(RuntimeError, match="Refusing to migrate"):
            database.ensure_schema()
    finally:
        database.engine = original
        legacy.dispose()
