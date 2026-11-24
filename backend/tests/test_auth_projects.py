import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.models import AgreementMilestone, PaymentRecord, WorkAgreement

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def register(role: str, name: str):
    response = client.post("/api/auth/register", json={
        "email": f"{role}-{name}@example.com",
        "password": "secure-pass-123",
        "full_name": name,
        "role": role,
    })
    assert response.status_code == 200
    return response.json()["token"]


def auth(token: str):
    return {"Authorization": f"Bearer {token}"}


def invite_and_accept(client_token: str, freelancer_token: str, project_id: str):
    freelancer_id = client.get("/api/me", headers=auth(freelancer_token)).json()["id"]
    invitation_id = client.post(
        f"/api/projects/{project_id}/invitations",
        headers=auth(client_token),
        json={"freelancer_id": freelancer_id},
    ).json()["id"]
    response = client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(freelancer_token))
    assert response.status_code == 200
    return freelancer_id


def test_register_login_and_role_separation():
    freelancer_token = register("freelancer", "one")
    client_token = register("client", "one")

    assert client.post("/api/projects", headers=auth(freelancer_token), json={
        "title": "Brand website",
        "description": "A complete and accessible marketing website.",
        "budget": 100,
    }).status_code == 403
    assert client.post("/api/projects", headers=auth(client_token), json={
        "title": "Brand website",
        "description": "A complete and accessible marketing website.",
        "budget": 100,
    }).status_code == 200


def test_project_owner_isolated():
    owner_token = register("client", "owner")
    other_token = register("client", "other")
    created = client.post("/api/projects", headers=auth(owner_token), json={
        "title": "Private project",
        "description": "This project belongs to the owner.",
        "budget": 500,
    })
    project_id = created.json()["id"]
    assert client.get(f"/api/projects/{project_id}", headers=auth(other_token)).status_code == 403


def test_agreement_milestone_total_validation():
    client_token = register("client", "agreement")
    freelancer_token = register("freelancer", "agreement")
    freelancer_id = client.get("/api/me", headers=auth(freelancer_token)).json()["id"]
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Agreement project",
        "description": "A project with milestone-based delivery.",
        "budget": 100,
    }).json()["id"]
    invite_and_accept(client_token, freelancer_token, project_id)
    assert client.post(
        f"/api/projects/{project_id}/agreements",
        headers=auth(client_token),
        json={
            "freelancer_id": freelancer_id,
            "amount": 100,
            "asset": "XLM",
            "description": "Build the agreed website.",
            "milestones": [{"title": "Discovery", "amount": 60}, {"title": "Delivery", "amount": 30}],
        },
    ).status_code == 422


def test_milestone_workflow_and_revision():
    client_token = register("client", "workflow")
    freelancer_token = register("freelancer", "workflow")
    freelancer_id = client.get("/api/me", headers=auth(freelancer_token)).json()["id"]
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Workflow project",
        "description": "A project for testing workflow transitions.",
        "budget": 100,
    }).json()["id"]
    invite_and_accept(client_token, freelancer_token, project_id)
    agreement_id = client.post(
        f"/api/projects/{project_id}/agreements",
        headers=auth(client_token),
        json={
            "freelancer_id": freelancer_id,
            "amount": 100,
            "asset": "XLM",
            "description": "Complete this milestone project.",
            "milestones": [{"title": "Delivery", "amount": 100}],
        },
    ).json()["id"]
    assert client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(client_token)).json()["status"] == "pending_acceptance"
    assert client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(freelancer_token)).json()["status"] == "active"

    with __import__("app.database", fromlist=["SessionLocal"]).SessionLocal() as db:
        milestone_id = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first().id
    submitted = client.post(
        f"/api/milestones/{milestone_id}/submit",
        headers=auth(freelancer_token),
        json={"deliverable_url": "https://example.com/delivery"},
    )
    assert submitted.status_code == 200
    revision = client.post(
        f"/api/milestones/{milestone_id}/review?approved=false",
        headers=auth(client_token),
        json={"feedback": "Please revise."},
    )
    assert revision.status_code == 200
    assert revision.json()["status"] == "revision_requested"


def test_unrelated_user_cannot_read_project():
    owner_token = register("client", "one")
    outsider_token = register("freelancer", "outsider")
    project_id = client.post("/api/projects", headers=auth(owner_token), json={
        "title": "Hidden project",
        "description": "Private project information.",
        "budget": 250,
    }).json()["id"]
    assert client.get(f"/api/projects/{project_id}", headers=auth(outsider_token)).status_code == 403


def test_expired_or_invalid_session_is_rejected():
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=auth("invalid-session")).status_code == 401


def test_security_headers_are_added():
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_confirm_payment_requires_matching_verified_horizon_payment(monkeypatch):
    client_token = register("client", "payment")
    freelancer_token = register("freelancer", "payment")
    client_address = "G" + ("A" * 55)
    freelancer_address = "G" + ("B" * 55)
    assert client.put("/api/me", headers=auth(client_token), json={"stellar_address": client_address}).status_code == 200
    assert client.put("/api/me", headers=auth(freelancer_token), json={"stellar_address": freelancer_address}).status_code == 200
    freelancer_id = client.get("/api/me", headers=auth(freelancer_token)).json()["id"]
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Paid project",
        "description": "A project with a verified Testnet payment.",
        "budget": 50,
    }).json()["id"]
    invite_and_accept(client_token, freelancer_token, project_id)
    agreement_id = client.post(
        f"/api/projects/{project_id}/agreements",
        headers=auth(client_token),
        json={
            "freelancer_id": freelancer_id,
            "amount": 50,
            "asset": "XLM",
            "description": "Deliver the paid project.",
            "milestones": [{"title": "Final delivery", "amount": 50}],
        },
    ).json()["id"]
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(client_token))
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(freelancer_token))
    with __import__("app.database", fromlist=["SessionLocal"]).SessionLocal() as db:
        milestone = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first()
        milestone_id = milestone.id
    client.post(
        f"/api/milestones/{milestone_id}/submit",
        headers=auth(freelancer_token),
        json={"deliverable_url": "https://example.com/final"},
    )
    client.post(
        f"/api/milestones/{milestone_id}/review?approved=true",
        headers=auth(client_token),
        json={},
    )

    transaction_hash = "a" * 64

    async def matching_transaction(_hash):
        return {
            "found": True,
            "successful": True,
            "ledger": 12345,
            "source_account": client_address,
            "operations": [{
                "type": "payment",
                "from": client_address,
                "to": freelancer_address,
                "amount": "50.0000000",
                "asset_type": "native",
            }],
        }

    monkeypatch.setattr("app.main.get_transaction", matching_transaction)
    confirmed = client.post(
        f"/api/payments/{transaction_hash}/confirm?milestone_id={milestone_id}",
        headers=auth(client_token),
    )
    assert confirmed.status_code == 200
    duplicate = client.post(
        f"/api/payments/{transaction_hash}/confirm?milestone_id={milestone_id}",
        headers=auth(client_token),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


def test_confirm_payment_rejects_wrong_source(monkeypatch):
    client_token = register("client", "wrong-source")
    freelancer_token = register("freelancer", "wrong-source")
    client_address = "G" + ("C" * 55)
    freelancer_address = "G" + ("D" * 55)
    assert client.put("/api/me", headers=auth(client_token), json={"stellar_address": client_address}).status_code == 200
    assert client.put("/api/me", headers=auth(freelancer_token), json={"stellar_address": freelancer_address}).status_code == 200
    freelancer_id = client.get("/api/me", headers=auth(freelancer_token)).json()["id"]
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Wrong-source project",
        "description": "A project that must reject another payer.",
        "budget": 25,
    }).json()["id"]
    invite_and_accept(client_token, freelancer_token, project_id)
    agreement_id = client.post(
        f"/api/projects/{project_id}/agreements",
        headers=auth(client_token),
        json={
            "freelancer_id": freelancer_id,
            "amount": 25,
            "asset": "XLM",
            "description": "Reject a payment from an unrelated account.",
            "milestones": [{"title": "Final", "amount": 25}],
        },
    ).json()["id"]
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(client_token))
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(freelancer_token))
    with __import__("app.database", fromlist=["SessionLocal"]).SessionLocal() as db:
        milestone_id = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first().id
    client.post(
        f"/api/milestones/{milestone_id}/submit",
        headers=auth(freelancer_token),
        json={"deliverable_url": "https://example.com/final"},
    )
    client.post(
        f"/api/milestones/{milestone_id}/review?approved=true",
        headers=auth(client_token),
        json={},
    )

    async def wrong_source(_hash):
        return {
            "found": True,
            "successful": True,
            "ledger": 456,
            "source_account": "G" + ("E" * 55),
            "operations": [{
                "type": "payment",
                "from": "G" + ("E" * 55),
                "to": freelancer_address,
                "amount": "25.0000000",
                "asset_type": "native",
            }],
        }

    monkeypatch.setattr("app.main.get_transaction", wrong_source)
    response = client.post(
        f"/api/payments/{'f' * 64}/confirm?milestone_id={milestone_id}",
        headers=auth(client_token),
    )
    assert response.status_code == 422
