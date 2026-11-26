"""Final closure verification: reconciliation and repository-wide smoke checks."""

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AgreementMilestone, PaymentRecord

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(role: str, name: str) -> tuple[str, str]:
    response = client.post("/api/auth/register", json={
        "email": f"closure-{name}@example.com",
        "password": "secure-pass-123",
        "full_name": name,
        "role": role,
    })
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return token, client.get("/api/me", headers=auth(token)).json()["id"]


def transaction(source: str, destination: str, memo: str) -> dict:
    return {
        "found": True,
        "successful": True,
        "ledger": 42,
        "memo": memo,
        "source_account": source,
        "operations": [{
            "type": "payment",
            "from": source,
            "to": destination,
            "amount": "75.0000000",
            "asset_type": "native",
        }],
    }


def test_reconciliation_reports_verified_and_mismatched_records(monkeypatch):
    ct, _ = register("client", "reconcile-client")
    ft, fid = register("freelancer", "reconcile-free")
    source, destination = "G" + "V" * 55, "G" + "W" * 55
    client.put("/api/me", headers=auth(ct), json={"stellar_address": source})
    client.put("/api/me", headers=auth(ft), json={"stellar_address": destination})
    project_id = client.post("/api/projects", headers=auth(ct), json={
        "title": "Reconciliation project", "description": "A project for reconciliation testing.", "budget": 75,
    }).json()["id"]
    invitation_id = client.post(f"/api/projects/{project_id}/invitations", headers=auth(ct), json={
        "freelancer_id": fid,
    }).json()["id"]
    client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(ft))
    agreement_id = client.post(f"/api/projects/{project_id}/agreements", headers=auth(ct), json={
        "freelancer_id": fid, "amount": 75, "asset": "XLM",
        "description": "An agreement used for reconciliation checks.",
        "milestones": [{"title": "Delivery", "amount": 75}],
    }).json()["id"]
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ct))
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ft))
    with SessionLocal() as db:
        mid = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first().id
    client.post(f"/api/milestones/{mid}/start", headers=auth(ft))
    client.post(f"/api/milestones/{mid}/submit", headers=auth(ft), json={"deliverable_url": "https://example.com/work"})
    client.post(f"/api/milestones/{mid}/review?approved=true", headers=auth(ct), json={})
    intent = client.post("/api/payment-intents", headers=auth(ct), json={"milestone_id": mid}).json()

    async def verified(_hash):
        return transaction(source, destination, intent["memo"])

    monkeypatch.setattr("app.main.get_transaction", verified)
    confirmation = client.post(
        f"/api/payments/{'5' * 64}/confirm?milestone_id={mid}&intent_id={intent['id']}", headers=auth(ct)
    )
    assert confirmation.status_code == 200

    monkeypatch.setattr("app.routers.finance.get_transaction", verified)
    report = client.get("/api/payments/reconcile", headers=auth(ct))
    assert report.status_code == 200
    assert report.json()["verified"] == 1
    assert report.json()["mismatches"] == 0

    async def tampered(_hash):
        result = transaction(source, destination, intent["memo"])
        result["operations"][0]["amount"] = "1.0000000"
        return result

    monkeypatch.setattr("app.routers.finance.get_transaction", tampered)
    report = client.get("/api/payments/reconcile", headers=auth(ct))
    assert report.json()["mismatches"] == 1
    with SessionLocal() as db:
        assert db.query(PaymentRecord).count() == 1  # reconciliation never mutates records
