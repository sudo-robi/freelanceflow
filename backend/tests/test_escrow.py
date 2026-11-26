"""Escrow integration tests: envelope verification and workflow reconciliation."""

import pytest
from fastapi.testclient import TestClient
from stellar_sdk import Keypair, xdr
from stellar_sdk.operation import Operation
from stellar_sdk.strkey import StrKey

from app import escrow
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AgreementMilestone, WorkAgreement

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
        "email": f"escrow-{name}@example.com", "password": "secure-pass-123",
        "full_name": name, "role": role,
    })
    assert response.status_code == 200
    token = response.json()["token"]
    return token, client.get("/api/me", headers=auth(token)).json()["id"]


def setup_agreement():
    ct, _ = register("client", "client")
    ft, fid = register("freelancer", "freelancer")
    pid = client.post("/api/projects", headers=auth(ct), json={
        "title": "Escrow project", "description": "A project for escrow integration tests.", "budget": 100,
    }).json()["id"]
    iid = client.post(f"/api/projects/{pid}/invitations", headers=auth(ct), json={"freelancer_id": fid}).json()["id"]
    client.post(f"/api/invitations/{iid}/accept", headers=auth(ft))
    aid = client.post(f"/api/projects/{pid}/agreements", headers=auth(ct), json={
        "freelancer_id": fid, "amount": 100, "asset": "XLM",
        "description": "An agreement used for escrow integration testing.",
        "milestones": [{"title": "Delivery", "amount": 100}],
    }).json()["id"]
    return ct, ft, aid


def invoke_envelope_xdr(action: str, agreement_uuid: str) -> str:
    kp = Keypair.random()
    aid = escrow.agreement_id(agreement_uuid)
    contract_id = xdr.Hash(bytes.fromhex(escrow._contract_hash_hex()))
    address = xdr.SCAddress(
        type=xdr.SCAddressType.SC_ADDRESS_TYPE_CONTRACT,
        contract_id=xdr.ContractID(contract_id),
    )
    args = xdr.InvokeContractArgs(
        contract_address=address,
        function_name=xdr.SCSymbol(escrow.FUNCTION_FOR_ACTION[action].encode()),
        args=[xdr.SCVal(type=xdr.SCValType.SCV_BYTES, bytes=xdr.SCBytes(aid))],
    )
    host = xdr.HostFunction(type=xdr.HostFunctionType.HOST_FUNCTION_TYPE_INVOKE_CONTRACT, invoke_contract=args)
    body = xdr.OperationBody(type=xdr.OperationType.INVOKE_HOST_FUNCTION,
                             invoke_host_function_op=xdr.InvokeHostFunctionOp(host_function=host, auth=[]))
    source = xdr.MuxedAccount(type=xdr.CryptoKeyType.KEY_TYPE_ED25519,
                              ed25519=xdr.Uint256(StrKey.decode_ed25519_public_key(kp.public_key)))
    tx = xdr.Transaction(
        source_account=source,
        fee=xdr.Uint32(100),
        seq_num=xdr.SequenceNumber(xdr.Int64(1)),
        cond=xdr.Preconditions(type=xdr.PreconditionType.PRECOND_TIME,
                               time_bounds=xdr.TimeBounds(min_time=xdr.TimePoint(xdr.Uint64(0)), max_time=xdr.TimePoint(xdr.Uint64(0)))),
        memo=xdr.Memo(type=xdr.MemoType.MEMO_NONE),
        operations=[Operation.from_xdr_object(xdr.Operation(None, body)).to_xdr_object()],
        ext=xdr.TransactionExt(v=0),
    )
    return xdr.TransactionEnvelope(
        type=xdr.EnvelopeType.ENVELOPE_TYPE_TX,
        v1=xdr.TransactionV1Envelope(tx=tx, signatures=[]),
    ).to_xdr()


def test_envelope_verification_rejects_wrong_action():
    agreement_id = "test-agreement"
    envelope = invoke_envelope_xdr("fund", agreement_id)
    assert escrow.verify_invoke_transaction(envelope, "fund", escrow.agreement_id(agreement_id))["function"] == "fund"
    with pytest.raises(escrow.EscrowVerificationError):
        escrow.verify_invoke_transaction(envelope, "release", escrow.agreement_id(agreement_id))


def test_escrow_confirm_updates_application_state(monkeypatch):
    ct, _, aid = setup_agreement()

    async def verified(_hash, _action, _agreement):
        return {"agreement_id": escrow.agreement_id(aid).hex(), "ledger": 123}

    monkeypatch.setattr("app.routers.escrow.escrow.verify_transaction", verified)
    response = client.post(f"/api/agreements/{aid}/escrow/confirm", headers=auth(ct),
                           json={"action": "fund", "transaction_hash": "a" * 64})
    assert response.status_code == 200
    assert response.json()["status"] == "funded"
    with SessionLocal() as db:
        agreement = db.get(WorkAgreement, aid)
        assert agreement.escrow_status == "funded"
        assert agreement.escrow_transaction_hash == "a" * 64


def test_escrow_confirm_is_idempotent(monkeypatch):
    ct, _, aid = setup_agreement()

    async def verified(_hash, _action, _agreement):
        return {"agreement_id": escrow.agreement_id(aid).hex(), "ledger": 123}

    monkeypatch.setattr("app.routers.escrow.escrow.verify_transaction", verified)
    payload = {"action": "fund", "transaction_hash": "b" * 64}
    first = client.post(f"/api/agreements/{aid}/escrow/confirm", headers=auth(ct), json=payload)
    second = client.post(f"/api/agreements/{aid}/escrow/confirm", headers=auth(ct), json=payload)
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


def test_escrow_confirm_requires_party_authorization(monkeypatch):
    _, ft, aid = setup_agreement()
    outsider, _ = register("client", "outsider")
    response = client.post(f"/api/agreements/{aid}/escrow/confirm", headers=auth(outsider),
                           json={"action": "fund", "transaction_hash": "c" * 64})
    assert response.status_code == 403
    assert ft  # freelancer token exists for party-action coverage
