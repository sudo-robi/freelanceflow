"""Phase 3: live network identity and bounded Horizon retry tests."""

from fastapi.testclient import TestClient

from app import stellar
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AgreementMilestone, PaymentRecord
from app.stellar import TESTNET_PASSPHRASE

client = TestClient(app)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(role: str, name: str) -> tuple[str, str]:
    response = client.post("/api/auth/register", json={
        "email": f"phase3-{name}@example.com",
        "password": "secure-pass-123",
        "full_name": name,
        "role": role,
    })
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return token, client.get("/api/me", headers=auth(token)).json()["id"]


def approved_milestone() -> tuple[str, str, str, str]:
    ct, _ = register("client", "network-client")
    ft, fid = register("freelancer", "network-free")
    source, destination = "G" + "T" * 55, "G" + "U" * 55
    client.put("/api/me", headers=auth(ct), json={"stellar_address": source})
    client.put("/api/me", headers=auth(ft), json={"stellar_address": destination})
    project_id = client.post("/api/projects", headers=auth(ct), json={
        "title": "Network project", "description": "A project for network verification tests.", "budget": 25,
    }).json()["id"]
    invitation_id = client.post(f"/api/projects/{project_id}/invitations", headers=auth(ct), json={
        "freelancer_id": fid,
    }).json()["id"]
    client.post(f"/api/invitations/{invitation_id}/accept", headers=auth(ft))
    agreement_id = client.post(f"/api/projects/{project_id}/agreements", headers=auth(ct), json={
        "freelancer_id": fid, "amount": 25, "asset": "XLM",
        "description": "An agreement for network verification testing.",
        "milestones": [{"title": "Delivery", "amount": 25}],
    }).json()["id"]
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ct))
    client.post(f"/api/agreements/{agreement_id}/accept", headers=auth(ft))
    with SessionLocal() as db:
        mid = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).first().id
    client.post(f"/api/milestones/{mid}/start", headers=auth(ft))
    client.post(f"/api/milestones/{mid}/submit", headers=auth(ft), json={"deliverable_url": "https://example.com/work"})
    client.post(f"/api/milestones/{mid}/review?approved=true", headers=auth(ct), json={})
    return ct, agreement_id, mid, source, destination


def matching_hash() -> str:
    return "4" * 64


def matching_transaction(source: str, destination: str) -> dict:
    return {
        "found": True,
        "successful": True,
        "ledger": 123,
        "memo": "phase3-test",
        "source_account": source,
        "operations": [{
            "type": "payment", "from": source, "to": destination,
            "amount": "25.0000000", "asset_type": "native",
        }],
    }


def test_network_passphrase_mismatch_blocks_payment(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ct, agreement_id, mid, source, destination = approved_milestone()

    async def wrong_passphrase():
        return "Public Global Stellar Network ; September 2015"

    async def verified(_hash):
        return matching_transaction(source, destination)

    monkeypatch.setattr("app.main.get_network_passphrase", wrong_passphrase)
    monkeypatch.setattr("app.main.get_transaction", verified)
    response = client.post(
        f"/api/payments/{matching_hash()}/confirm?milestone_id={mid}", headers=auth(ct)
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream verification unavailable"
    with SessionLocal() as db:
        assert db.query(PaymentRecord).count() == 0


async def _no_sleep(_delay):
    return None


def test_get_transaction_retries_transient_not_found(monkeypatch):
    calls = []

    async def flaky(_hash):
        calls.append(1)
        if len(calls) == 1:
            return {"found": False, "status": "not_found"}
        return {"found": True, "successful": True, "operations": []}

    monkeypatch.setattr(stellar, "_fetch_transaction", flaky)
    monkeypatch.setattr(stellar.asyncio, "sleep", _no_sleep)
    result = stellar.get_transaction.__wrapped__ if hasattr(stellar.get_transaction, "__wrapped__") else stellar.get_transaction
    import asyncio

    outcome = asyncio.run(result("a" * 64))
    assert outcome["found"] is True
    assert len(calls) == 2


def test_network_passphrase_is_cached(monkeypatch):
    posts = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": {"passphrase": TESTNET_PASSPHRASE}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            posts.append(1)
            return FakeResponse()

    monkeypatch.setattr(stellar, "AsyncClient", FakeClient)
    stellar._passphrase_cache = None
    stellar._passphrase_cached_at = 0.0
    import asyncio

    first = asyncio.run(stellar.get_network_passphrase())
    second = asyncio.run(stellar.get_network_passphrase())
    assert first == second == TESTNET_PASSPHRASE
    assert len(posts) == 1
    stellar._passphrase_cache = None
