"""Soroban escrow workflow verification and application-state reconciliation."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import escrow
from ..auth import get_current_user
from ..database import get_db
from ..models import User, WorkAgreement
from ..ratelimit import rate_limit
from ..schemas import EscrowConfirmRequest
from ..services import assert_transition, audit, get_agreement_for_user, lock_row, notify

router = APIRouter(prefix="/api", tags=["escrow"])

CLIENT_ACTIONS = {"create", "fund", "approve", "release", "cancel"}
FREELANCER_ACTIONS = {"accept"}
STATE_FOR_ACTION = {
    "create": "initialized",
    "accept": "accepted",
    "fund": "funded",
    "approve": "approved",
    "release": "released",
    "cancel": "cancelled",
    "dispute": "disputed",
}


@router.get("/agreements/{agreement_id}/escrow")
async def escrow_state(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("escrow_read", 30, 60)),
):
    agreement = get_agreement_for_user(db, agreement_id, user)
    on_chain = None
    try:
        on_chain = await escrow.read_agreement_state(agreement_id)
    except Exception:
        on_chain = None
    return {
        "contract_id": escrow.CONTRACT_ID,
        "agreement_id": agreement_id,
        "escrow_agreement_id": agreement.escrow_agreement_id or escrow.agreement_id(agreement_id).hex(),
        "application_status": agreement.escrow_status,
        "last_transaction_hash": agreement.escrow_transaction_hash,
        "on_chain_state": on_chain,
        "verified": on_chain is not None,
    }


@router.get("/agreements/{agreement_id}/escrow/intent")
def escrow_intent(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("escrow_read", 30, 60)),
):
    """Return party addresses and contract parameters to an agreement party."""
    agreement = get_agreement_for_user(db, agreement_id, user)
    from ..models import AgreementMilestone

    client = db.get(User, agreement.client_id)
    freelancer = db.get(User, agreement.freelancer_id)
    milestones = db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement.id).order_by(AgreementMilestone.id.asc()).all()
    if not client.stellar_address or not freelancer.stellar_address:
        raise HTTPException(status_code=422, detail="Both parties must set Stellar addresses before escrow")
    return {
        "contract_id": escrow.CONTRACT_ID,
        "agreement_id": agreement_id,
        "escrow_agreement_id": agreement.escrow_agreement_id or escrow.agreement_id(agreement_id).hex(),
        "client": client.stellar_address,
        "freelancer": freelancer.stellar_address,
        "asset_contract_id": "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC",
        "amounts_stroops": [int(milestone.amount * 10_000_000) for milestone in milestones],
    }


@router.post("/agreements/{agreement_id}/escrow/confirm")
async def confirm_escrow_action(
    agreement_id: str,
    payload: EscrowConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("escrow_confirm", 20, 60)),
):
    agreement = get_agreement_for_user(db, agreement_id, user)
    agreement = lock_row(db, WorkAgreement, agreement.id) or agreement

    if payload.action in CLIENT_ACTIONS and user.id != agreement.client_id:
        raise HTTPException(status_code=403, detail="Only the project client may perform this escrow action")
    if payload.action in FREELANCER_ACTIONS and user.id != agreement.freelancer_id:
        raise HTTPException(status_code=403, detail="Only the assigned freelancer may accept escrow")
    if payload.action == "dispute" and user.id not in {agreement.client_id, agreement.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")

    if agreement.escrow_transaction_hash == payload.transaction_hash:
        return {"status": agreement.escrow_status, "duplicate": True, "transaction_hash": payload.transaction_hash}

    try:
        verified = await escrow.verify_transaction(payload.transaction_hash, payload.action, agreement_id)
    except escrow.EscrowVerificationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    target = STATE_FOR_ACTION[payload.action]
    if agreement.escrow_status == target:
        agreement.escrow_transaction_hash = payload.transaction_hash
        db.commit()
        return {"status": target, "duplicate": True, "transaction_hash": payload.transaction_hash}

    agreement.escrow_contract_id = escrow.CONTRACT_ID
    agreement.escrow_agreement_id = verified["agreement_id"]
    agreement.escrow_status = target
    agreement.escrow_transaction_hash = payload.transaction_hash
    agreement.escrow_updated_at = datetime.utcnow()
    audit(db, user.id, "escrow", agreement_id, payload.action, payload.transaction_hash)
    counterparty = agreement.freelancer_id if user.id == agreement.client_id else agreement.client_id
    notify(db, counterparty, "Escrow updated", f"Contract state changed to {target}.", "escrow", "agreement", agreement_id)
    db.commit()
    return {
        "status": target,
        "duplicate": False,
        "transaction_hash": payload.transaction_hash,
        "ledger": verified.get("ledger"),
        "contract_id": escrow.CONTRACT_ID,
    }
