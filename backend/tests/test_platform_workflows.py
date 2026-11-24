"""Integration tests for the complete FreelanceFlow workflows."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    AgreementMilestone,
    Dispute,
    Invoice,
    Notification,
    PaymentIntent,
    PaymentRecord,
    Project,
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
        "email": f"{name}@example.com",
        "password": "secure-pass-123",
        "full_name": name,
        "role": role,
    })
    assert response.status_code == 200
    result = response.json()
    return result["token"], client.get("/api/me", headers=auth(result["token"])).json()["id"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def set_address(token: str, address: str) -> None:
    assert client.put("/api/me", headers=auth(token), json={"stellar_address": address}).status_code == 200


def setup_project(client_token: str, freelancer_token: str, freelancer_id: str, budget: float = 100) -> tuple[str, str, str]:
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Verified website",
        "description": "A complete and accessible marketing website.",
        "budget": budget,
        "required_skills": "React, accessibility",
    }).json()["id"]
    invitation_id = client.post(
        f"/api/projects/{project_id}/invitations",
        headers=auth(client_token),
        json={"freelancer_id": freelancer_id},
    ).json()["id"]
    assert client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(freelancer_token)).status_code == 200
    agreement_id = client.post(f"/api/projects/{project_id}/agreements", headers=auth(client_token), json={
        "freelancer_id": freelancer_id,
        "amount": budget,
        "asset": "XLM",
        "description": "Build and deliver the agreed website.",
        "milestones": [{"title": "Delivery", "amount": budget}],
    }).json()["id"]
    assert client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(client_token)).json()["status"] == "pending_acceptance"
    assert client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(freelancer_token)).json()["status"] == "active"
    with SessionLocal() as db:
        milestone_id = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first().id
    return project_id, agreement_id, milestone_id


def approve_milestone(client_token: str, freelancer_token: str, milestone_id: str) -> None:
    assert client.post(f"/api/milestones/{milestone_id}/start", headers=auth(freelancer_token)).status_code == 200
    assert client.post(f"/api/milestones/{milestone_id}/submit", headers=auth(freelancer_token), json={
        "deliverable_url": "https://example.com/deliverable",
    }).status_code == 200
    assert client.post(f"/api/milestones/{milestone_id}/review-start", headers=auth(client_token)).status_code == 200
    assert client.post(f"/api/milestones/{milestone_id}/review?approved=true", headers=auth(client_token), json={}).json()["status"] == "approved"


async def matching_transaction(source: str, destination: str, amount: str, memo: str = "test-memo") -> dict:
    return {
        "found": True,
        "successful": True,
        "ledger": 12345,
        "source_account": source,
        "memo": memo,
        "operations": [{
            "type": "payment",
            "from": source,
            "to": destination,
            "amount": amount,
            "asset_type": "native",
        }],
    }


# ---------------------------------------------------------------------------
# Profiles and discovery
# ---------------------------------------------------------------------------

def test_public_freelancer_profile_excludes_private_fields():
    freelancer_token, freelancer_id = register("freelancer", "public-pro")
    set_address(freelancer_token, "G" + "A" * 55)
    assert client.put("/api/me", headers=auth(freelancer_token), json={
        "title": "Accessibility engineer",
        "skills": "React, a11y, WCAG",
        "description": "I build inclusive interfaces.",
        "hourly_rate": 42,
    }).status_code == 200
    assert client.put("/api/me/availability", headers=auth(freelancer_token), json={
        "available": True, "availability_note": "Available in November",
    }).status_code == 200
    portfolio = client.post("/api/me/portfolio", headers=auth(freelancer_token), json={
        "title": "Design system", "url": "https://example.com/work", "description": "Public case study",
    })
    assert portfolio.status_code == 201

    profile = client.get(f"/api/freelancers/{freelancer_id}").json()
    assert profile["skills"] == "React, a11y, WCAG"
    assert profile["available"] is True
    assert profile["portfolio"][0]["title"] == "Design system"
    for private in ("email", "password_hash", "stellar_address"):
        assert private not in profile

    assert client.delete(f"/api/me/portfolio/{portfolio.json()['id']}", headers=auth(freelancer_token)).status_code == 200
    assert client.get(f"/api/freelancers/{freelancer_id}").json()["portfolio"] == []


def test_freelancer_search_filters_and_sorts():
    for name, skills, rate, available in [
        ("search-a", "React", 20, True),
        ("search-b", "Python", 50, True),
        ("search-c", "React, Python", 30, False),
    ]:
        token, _ = register("freelancer", name)
        client.put("/api/me", headers=auth(token), json={"skills": skills, "hourly_rate": rate})
        client.put("/api/me/availability", headers=auth(token), json={"available": available})

    assert {item["full_name"] for item in client.get("/api/freelancers?skill=React").json()} == {"search-a", "search-c"}
    assert {item["full_name"] for item in client.get("/api/freelancers?available_only=true").json()} >= {"search-a", "search-b"}
    rates = [item["hourly_rate"] for item in client.get("/api/freelancers?sort=rate").json()]
    assert rates == sorted(rates)
    assert len(client.get("/api/freelancers?limit=1&offset=1").json()) == 1


def test_portfolio_and_availability_require_freelancer_role():
    client_token, _ = register("client", "role-portfolio")
    assert client.put("/api/me/availability", headers=auth(client_token), json={"available": True}).status_code == 403
    assert client.post("/api/me/portfolio", headers=auth(client_token), json={
        "title": "Nope", "url": "https://example.com",
    }).status_code == 403


# ---------------------------------------------------------------------------
# Project lifecycle and invitations
# ---------------------------------------------------------------------------

def test_project_edit_cancel_complete_and_activity():
    client_token, client_id = register("client", "lifecycle-client")
    freelancer_token, freelancer_id = register("freelancer", "lifecycle-free")
    project_id, agreement_id, milestone_id = setup_project(client_token, freelancer_token, freelancer_id)

    assert client.put(f"/api/projects/{project_id}", headers=auth(client_token), json={
        "title": "Edited title", "deadline": "2026-12-01",
    }).status_code == 200
    detail = client.get(f"/api/projects/{project_id}", headers=auth(client_token)).json()
    assert detail["title"] == "Edited title"
    assert detail["deadline"] == "2026-12-01"

    activity = client.get(f"/api/projects/{project_id}/activity", headers=auth(client_token)).json()
    assert any(item["action"] == "updated" for item in activity)

    # A freelancer cannot edit or cancel a client's project.
    assert client.put(f"/api/projects/{project_id}", headers=auth(freelancer_token), json={"title": "Hijack"}).status_code == 403
    assert client.post(f"/api/projects/{project_id}/cancel", headers=auth(freelancer_token)).status_code == 403

    approve_milestone(client_token, freelancer_token, milestone_id)
    assert client.post(f"/api/projects/{project_id}/complete", headers=auth(client_token)).status_code == 409
    assert client.post(f"/api/projects/{project_id}/cancel", headers=auth(client_token)).status_code == 409


def test_invitation_rejection_and_listing():
    client_token, _ = register("client", "invite-client")
    freelancer_token, freelancer_id = register("freelancer", "invite-free")
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Invitation project", "description": "A project for invitation testing.", "budget": 60,
    }).json()["id"]
    invitation_id = client.post(f"/api/projects/{project_id}/invitations", headers=auth(client_token), json={
        "freelancer_id": freelancer_id,
    }).json()["id"]

    assert any(item["id"] == invitation_id for item in client.get("/api/invitations", headers=auth(freelancer_token)).json())
    assert client.post(f"/api/invitations/{invitation_id}/reject", headers=auth(client_token)).status_code == 403
    assert client.post(f"/api/invitations/{invitation_id}/reject", headers=auth(freelancer_token)).json()["status"] == "rejected"
    assert client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(freelancer_token)).status_code == 409
    assert client.get("/api/projects", headers=auth(freelancer_token)).json() == []
    assert any(item["category"] == "invitation" for item in client.get("/api/notifications", headers=auth(client_token)).json())


def test_project_access_isolation_for_unrelated_users():
    owner_token, _ = register("client", "isolated-owner")
    outsider_token, _ = register("client", "isolated-outsider")
    project_id = client.post("/api/projects", headers=auth(owner_token), json={
        "title": "Private", "description": "Private project details only.", "budget": 10,
    }).json()["id"]
    assert client.get(f"/api/projects/{project_id}", headers=auth(outsider_token)).status_code == 403
    assert client.get(f"/api/projects/{project_id}/activity", headers=auth(outsider_token)).status_code == 403


# ---------------------------------------------------------------------------
# Agreements and milestones
# ---------------------------------------------------------------------------

def test_agreement_detail_revisions_rejection_and_cancellation():
    client_token, _ = register("client", "agreement-client")
    freelancer_token, freelancer_id = register("freelancer", "agreement-free")
    project_id = client.post("/api/projects", headers=auth(client_token), json={
        "title": "Revision project", "description": "A project for agreement revisions.", "budget": 100,
    }).json()["id"]
    invitation_id = client.post(f"/api/projects/{project_id}/invitations", headers=auth(client_token), json={
        "freelancer_id": freelancer_id,
    }).json()["id"]
    client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(freelancer_token))
    agreement_id = client.post(f"/api/projects/{project_id}/agreements", headers=auth(client_token), json={
        "freelancer_id": freelancer_id,
        "amount": 100,
        "asset": "XLM",
        "description": "Initial scope of work with two milestones.",
        "milestones": [
            {"title": "First", "amount": 60},
            {"title": "Second", "amount": 40},
        ],
    }).json()["id"]

    assert client.get(f"/api/agreements/{agreement_id}", headers=auth(client_token)).json()["version"] == 1
    revised = client.put(f"/api/agreements/{agreement_id}", headers=auth(client_token), json={
        "amount": 100,
        "description": "Revised scope of work with new milestones.",
        "change_note": "Split delivery.",
        "milestones": [
            {"title": "Discovery", "amount": 30},
            {"title": "Build", "amount": 70},
        ],
    })
    assert revised.status_code == 200
    assert revised.json()["version"] == 2
    revisions = client.get(f"/api/agreements/{agreement_id}/revisions", headers=auth(client_token)).json()
    assert len(revisions) == 1 and revisions[0]["version"] == 1

    assert client.put(f"/api/agreements/{agreement_id}/milestones", headers=auth(client_token), json={
        "milestones": [{"title": "Single", "amount": 100}],
    }).status_code == 200
    assert client.post(f"/api/agreements/{agreement_id}/reject", headers=auth(freelancer_token)).json()["status"] == "cancelled"
    assert client.get(f"/api/projects/{project_id}", headers=auth(client_token)).json()["status"] == "open"


def test_milestone_history_and_resubmission():
    client_token, _ = register("client", "milestone-client")
    freelancer_token, freelancer_id = register("freelancer", "milestone-free")
    _, agreement_id, milestone_id = setup_project(client_token, freelancer_token, freelancer_id)

    assert client.post(f"/api/milestones/{milestone_id}/start", headers=auth(client_token)).status_code == 403
    assert client.post(f"/api/milestones/{milestone_id}/start", headers=auth(freelancer_token)).json()["status"] == "in_progress"
    assert client.post(f"/api/milestones/{milestone_id}/submit", headers=auth(freelancer_token), json={
        "deliverable_url": "not-a-url",
    }).status_code == 422
    client.post(f"/api/milestones/{milestone_id}/submit", headers=auth(freelancer_token), json={
        "deliverable_url": "https://example.com/v1",
    })
    client.post(f"/api/milestones/{milestone_id}/review?approved=false", headers=auth(client_token), json={
        "feedback": "Please add tests.",
    })
    assert client.post(f"/api/milestones/{milestone_id}/submit", headers=auth(freelancer_token), json={
        "deliverable_url": "https://example.com/v2",
    }).json()["submission_count"] == 2
    detail = client.get(f"/api/milestones/{milestone_id}", headers=auth(freelancer_token)).json()
    assert detail["submission_count"] == 2
    assert any(item["action"] == "revision_requested" for item in detail["history"])
    assert detail["agreement_id"] == agreement_id


# ---------------------------------------------------------------------------
# Payment intents, verification and financial records
# ---------------------------------------------------------------------------

def test_payment_intent_binds_memo_source_destination_and_amount(monkeypatch):
    client_token, _ = register("client", "pay-client")
    freelancer_token, freelancer_id = register("freelancer", "pay-free")
    source, destination = "G" + "C" * 55, "G" + "F" * 55
    set_address(client_token, source)
    set_address(freelancer_token, destination)
    _, agreement_id, milestone_id = setup_project(client_token, freelancer_token, freelancer_id)
    approve_milestone(client_token, freelancer_token, milestone_id)

    assert client.post("/api/payment-intents", headers=auth(freelancer_token), json={"milestone_id": milestone_id}).status_code == 403
    intent = client.post("/api/payment-intents", headers=auth(client_token), json={
        "milestone_id": milestone_id, "memo": "FF-PAY-0001",
    }).json()
    assert intent["source_account"] == source
    assert intent["destination_account"] == destination
    assert intent["network_passphrase"] == "Test SDF Network ; September 2015"
    assert intent["amount"] == 100

    network = client.get("/api/stellar/network").json()
    assert network["network_passphrase"] == "Test SDF Network ; September 2015"
    assert network["horizon_url"] == "https://horizon-testnet.stellar.org"

    monkeypatch.setattr("app.main.get_transaction", lambda _hash: matching_transaction(source, destination, "100.0000000", "FF-PAY-0001"))
    confirmed = client.post(
        f"/api/payments/{'a' * 64}/confirm?milestone_id={milestone_id}&intent_id={intent['id']}",
        headers=auth(client_token),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["duplicate"] is False

    payments = client.get("/api/payments", headers=auth(freelancer_token)).json()
    assert len(payments) == 1 and payments[0]["network"] == "testnet"
    assert payments[0]["memo"] == "FF-PAY-0001"
    assert client.get("/api/payments/summary", headers=auth(freelancer_token)).json()["verified_amount"] == 100

    invoice = client.get("/api/invoices", headers=auth(client_token)).json()
    assert len(invoice) == 1
    pdf = client.get(f"/api/invoices/{invoice[0]['id']}/pdf", headers=auth(client_token))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-1.4")
    receipt = client.get(f"/api/payments/{payments[0]['id']}/receipt", headers=auth(freelancer_token)).json()
    assert receipt["verified_by"] == "Stellar Testnet Horizon"
    csv = client.get("/api/payments/export.csv", headers=auth(client_token))
    assert csv.status_code == 200 and "transaction_hash" in csv.text
    assert client.get(f"/api/payments/{payments[0]['id']}/receipt", headers=auth(register("client", "receipt-other")[0])).status_code == 403


def test_payment_rejects_wrong_memo_amount_network_and_failed_transaction(monkeypatch):
    client_token, _ = register("client", "pay-fail-client")
    freelancer_token, freelancer_id = register("freelancer", "pay-fail-free")
    source, destination = "G" + "D" * 55, "G" + "E" * 55
    set_address(client_token, source)
    set_address(freelancer_token, destination)
    _, _, milestone_id = setup_project(client_token, freelancer_token, freelancer_id, budget=80)
    approve_milestone(client_token, freelancer_token, milestone_id)
    intent = client.post("/api/payment-intents", headers=auth(client_token), json={
        "milestone_id": milestone_id, "memo": "FF-EXPECT-01",
    }).json()

    url = f"/api/payments/{'b' * 64}/confirm?milestone_id={milestone_id}&intent_id={intent['id']}"
    async def not_found(_hash):
        return {"found": False, "successful": False, "operations": []}

    monkeypatch.setattr("app.main.get_transaction", not_found)
    assert client.post(url, headers=auth(client_token)).status_code == 409

    monkeypatch.setattr("app.main.get_transaction", lambda _h: matching_transaction(source, destination, "80.0000000", "WRONG-MEMO"))
    assert client.post(url, headers=auth(client_token)).status_code == 422

    monkeypatch.setattr("app.main.get_transaction", lambda _h: matching_transaction(source, destination, "79.0000000", "FF-EXPECT-01"))
    assert client.post(url, headers=auth(client_token)).status_code == 422

    wrong_destination = matching_transaction(source, "G" + "Z" * 55, "80.0000000", "FF-EXPECT-01")
    monkeypatch.setattr("app.main.get_transaction", lambda _h: wrong_destination)
    assert client.post(url, headers=auth(client_token)).status_code == 422

    wrong_source = matching_transaction("G" + "Y" * 55, destination, "80.0000000", "FF-EXPECT-01")
    monkeypatch.setattr("app.main.get_transaction", lambda _h: wrong_source)
    assert client.post(url, headers=auth(client_token)).status_code == 422

    with SessionLocal() as db:
        assert db.query(PaymentRecord).count() == 0
        assert db.query(Invoice).count() == 0


def test_duplicate_confirmation_and_unauthorized_confirm(monkeypatch):
    client_token, _ = register("client", "dup-client")
    freelancer_token, freelancer_id = register("freelancer", "dup-free")
    outsider_token, _ = register("client", "dup-outsider")
    source, destination = "G" + "H" * 55, "G" + "I" * 55
    set_address(client_token, source)
    set_address(freelancer_token, destination)
    _, _, milestone_id = setup_project(client_token, freelancer_token, freelancer_id, budget=50)
    approve_milestone(client_token, freelancer_token, milestone_id)
    monkeypatch.setattr("app.main.get_transaction", lambda _h: matching_transaction(source, destination, "50.0000000"))
    url = f"/api/payments/{'c' * 64}/confirm?milestone_id={milestone_id}"
    assert client.post(url, headers=auth(outsider_token)).status_code == 403
    first = client.post(url, headers=auth(client_token))
    assert first.status_code == 200
    second = client.post(url, headers=auth(client_token))
    assert second.status_code == 200 and second.json()["duplicate"] is True
    with SessionLocal() as db:
        assert db.query(PaymentRecord).count() == 1
        assert db.query(Invoice).count() == 1


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------

def test_dispute_blocks_review_and_payment_until_resolved(monkeypatch):
    client_token, _ = register("client", "dispute-client")
    freelancer_token, freelancer_id = register("freelancer", "dispute-free")
    source, destination = "G" + "J" * 55, "G" + "K" * 55
    set_address(client_token, source)
    set_address(freelancer_token, destination)
    _, agreement_id, milestone_id = setup_project(client_token, freelancer_token, freelancer_id, budget=70)
    client.post(f"/api/milestones/{milestone_id}/start", headers=auth(freelancer_token))
    client.post(f"/api/milestones/{milestone_id}/submit", headers=auth(freelancer_token), json={
        "deliverable_url": "https://example.com/disputed",
    })

    dispute = client.post("/api/disputes", headers=auth(freelancer_token), json={
        "agreement_id": agreement_id,
        "milestone_id": milestone_id,
        "reason": "The client changed the acceptance criteria after delivery.",
    })
    assert dispute.status_code == 201
    dispute_id = dispute.json()["id"]
    assert client.post(f"/api/milestones/{milestone_id}/review?approved=true", headers=auth(client_token), json={}).status_code == 409
    assert client.get(f"/api/projects/{client.get(f'/api/projects', headers=auth(client_token)).json()[0]['id']}", headers=auth(client_token)).json()["status"] == "disputed"

    assert client.post(f"/api/disputes/{dispute_id}/evidence", headers=auth(client_token), json={
        "evidence_url": "https://example.com/evidence", "note": "Original scope",
    }).status_code == 200
    assert client.post(f"/api/disputes/{dispute_id}/resolve", headers=auth(client_token), json={
        "resolution": "release_freelancer",
    }).json()["status"] == "awaiting_counterparty"
    assert client.post(f"/api/disputes/{dispute_id}/accept", headers=auth(client_token), json={
        "resolution": "release_freelancer",
    }).status_code == 403
    assert client.post(f"/api/disputes/{dispute_id}/accept", headers=auth(freelancer_token), json={
        "resolution": "refund_client",
    }).status_code == 409
    resolved = client.post(f"/api/disputes/{dispute_id}/accept", headers=auth(freelancer_token), json={
        "resolution": "release_freelancer",
    })
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    # After resolution, payment is possible again but only with an independently verified transaction.
    monkeypatch.setattr("app.main.get_transaction", lambda _h: matching_transaction(source, destination, "70.0000000"))
    assert client.post(f"/api/payments/{'d' * 64}/confirm?milestone_id={milestone_id}", headers=auth(client_token)).status_code == 200
    with SessionLocal() as db:
        assert db.query(PaymentRecord).count() == 1


def test_refund_resolution_prevents_any_future_payment_confirmation():
    client_token, _ = register("client", "refund-client")
    freelancer_token, freelancer_id = register("freelancer", "refund-free")
    _, agreement_id, milestone_id = setup_project(client_token, freelancer_token, freelancer_id)
    dispute_id = client.post("/api/disputes", headers=auth(client_token), json={
        "agreement_id": agreement_id, "reason": "Work was not delivered as scoped.",
    }).json()["id"]
    client.post(f"/api/disputes/{dispute_id}/resolve", headers=auth(client_token), json={"resolution": "refund_client"})
    client.post(f"/api/disputes/{dispute_id}/accept", headers=auth(freelancer_token), json={"resolution": "refund_client"})
    with SessionLocal() as db:
        agreement = db.get(WorkAgreement, agreement_id)
        assert agreement.status == "cancelled"
    assert client.post(f"/api/milestones/{milestone_id}/submit", headers=auth(freelancer_token), json={
        "deliverable_url": "https://example.com/late",
    }).status_code == 409


# ---------------------------------------------------------------------------
# Dashboard, notifications and Stellar verification
# ---------------------------------------------------------------------------

def test_dashboard_uses_only_real_database_records(monkeypatch):
    client_token, _ = register("client", "dash-client")
    freelancer_token, freelancer_id = register("freelancer", "dash-free")
    source, destination = "G" + "L" * 55, "G" + "M" * 55
    set_address(client_token, source)
    set_address(freelancer_token, destination)
    _, _, milestone_id = setup_project(client_token, freelancer_token, freelancer_id, budget=90)
    before = client.get("/api/dashboard", headers=auth(freelancer_token)).json()
    assert before["payments"]["verified_count"] == 0
    assert before["projects"]["total"] == 1

    approve_milestone(client_token, freelancer_token, milestone_id)
    pending = client.get("/api/dashboard", headers=auth(client_token)).json()
    assert pending["pending_reviews"] == 0
    monkeypatch.setattr("app.main.get_transaction", lambda _h: matching_transaction(source, destination, "90.0000000"))
    client.post(f"/api/payments/{'e' * 64}/confirm?milestone_id={milestone_id}", headers=auth(client_token))

    after = client.get("/api/dashboard", headers=auth(freelancer_token)).json()
    assert after["payments"]["verified_amount"] == 90
    assert after["payments"]["recent"][0]["status"] == "confirmed"
    assert after["projects"]["by_status"]["active"] == 1
    assert any(item["action"] == "confirmed" for item in after["activity"])
    assert client.get("/api/notifications/unread-count", headers=auth(freelancer_token)).json()["count"] >= 1
    first_notification = client.get("/api/notifications", headers=auth(freelancer_token)).json()[0]
    assert client.post(f"/api/notifications/{first_notification['id']}/read", headers=auth(freelancer_token)).status_code == 200
    assert client.get("/api/notifications/unread-count", headers=auth(freelancer_token)).json()["count"] == after["unread_notifications"] - 1


def test_stellar_transaction_verification_endpoint(monkeypatch):
    freelancer_token, _ = register("freelancer", "stellar-read")
    source, destination = "G" + "N" * 55, "G" + "O" * 55
    monkeypatch.setattr("app.routers.stellar.get_transaction", lambda _h: matching_transaction(source, destination, "1.0000000"))
    result = client.get(f"/api/stellar/transaction/{'f' * 64}", headers=auth(freelancer_token))
    assert result.status_code == 200
    assert result.json()["network"] == "testnet"
    assert result.json()["verified_against"] == "https://horizon-testnet.stellar.org"
    assert client.get("/api/stellar/transaction/short", headers=auth(freelancer_token)).status_code == 422
