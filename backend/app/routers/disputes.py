"""Dispute lifecycle. Disputed funds are never released automatically.

A resolution only records the parties' decision. Moving funds still requires an
explicit, independently verified Stellar transaction after the dispute resolves.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import AgreementMilestone, Dispute, DisputeEvent, Project, User, WorkAgreement
from ..ratelimit import rate_limit
from ..schemas import DisputeCreate, DisputeEvidence, DisputeResolution
from ..services import assert_transition, audit, get_agreement_for_user, lock_row, notify, serialize_datetime

router = APIRouter(prefix="/api", tags=["disputes"])

COUNTERPARTY_RESOLUTIONS = {"release_freelancer", "refund_client", "cancel_agreement"}


def dispute_payload(db: Session, dispute: Dispute) -> dict:
    events = db.query(DisputeEvent).filter(DisputeEvent.dispute_id == dispute.id).order_by(DisputeEvent.created_at.asc()).all()
    return {
        "id": dispute.id,
        "agreement_id": dispute.agreement_id,
        "milestone_id": dispute.milestone_id,
        "opened_by": dispute.opened_by,
        "reason": dispute.reason,
        "evidence_url": dispute.evidence_url,
        "status": dispute.status,
        "resolution": dispute.resolution,
        "proposed_by": dispute.proposed_by,
        "proposal_version": dispute.proposal_version or 0,
        "resolved_by": dispute.resolved_by,
        "created_at": serialize_datetime(dispute.created_at),
        "resolved_at": serialize_datetime(dispute.resolved_at),
        "history": [
            {
                "action": item.action,
                "details": item.details,
                "actor_id": item.actor_id,
                "created_at": serialize_datetime(item.created_at),
            }
            for item in events
        ],
    }


def _event(db: Session, dispute: Dispute, user: User, action: str, details: str = "") -> None:
    db.add(DisputeEvent(dispute_id=dispute.id, actor_id=user.id, action=action, details=details))


@router.post("/disputes", status_code=201)
def open_dispute(
    payload: DisputeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("dispute_open", 10, 60)),
):
    agreement = get_agreement_for_user(db, payload.agreement_id, user)
    if agreement.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled agreements cannot be disputed")
    if payload.milestone_id:
        milestone = db.get(AgreementMilestone, payload.milestone_id)
        if not milestone or milestone.agreement_id != agreement.id:
            raise HTTPException(status_code=422, detail="Milestone does not belong to this agreement")
    existing = db.query(Dispute).filter(
        Dispute.agreement_id == agreement.id,
        Dispute.status.in_(["open", "under_review", "awaiting_counterparty"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An open dispute already exists for this agreement")
    dispute = Dispute(
        agreement_id=agreement.id,
        milestone_id=payload.milestone_id,
        opened_by=user.id,
        reason=payload.reason,
        evidence_url=payload.evidence_url,
        status="open",
    )
    db.add(dispute)
    db.flush()
    _event(db, dispute, user, "opened", payload.reason)
    agreement.status = "disputed"
    project = db.get(Project, agreement.project_id)
    if project:
        project.status = "disputed"
    counterparty = agreement.freelancer_id if user.id == agreement.client_id else agreement.client_id
    notify(db, counterparty, "Dispute opened", f"A dispute was opened on {project.title if project else 'your agreement'}.", "dispute", "dispute", dispute.id)
    audit(db, user.id, "dispute", dispute.id, "opened", payload.milestone_id or "agreement")
    db.commit()
    return dispute_payload(db, dispute)


@router.get("/disputes")
def list_disputes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.query(Dispute).filter(
        (Dispute.opened_by == user.id)
        | (Dispute.agreement_id.in_(db.query(WorkAgreement.id).filter(
            (WorkAgreement.client_id == user.id) | (WorkAgreement.freelancer_id == user.id)
        )))
    ).order_by(Dispute.created_at.desc()).all()
    return [dispute_payload(db, item) for item in items]


@router.get("/disputes/{dispute_id}")
def get_dispute(
    dispute_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dispute = db.get(Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    get_agreement_for_user(db, dispute.agreement_id, user)
    return dispute_payload(db, dispute)


@router.post("/disputes/{dispute_id}/evidence")
def add_evidence(
    dispute_id: str,
    payload: DisputeEvidence,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dispute = lock_row(db, Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    get_agreement_for_user(db, dispute.agreement_id, user)
    if dispute.status in {"resolved", "rejected"}:
        raise HTTPException(status_code=409, detail="Dispute is closed")
    dispute.evidence_url = payload.evidence_url
    if dispute.status == "open":
        assert_transition("dispute", dispute.status, "under_review")
        dispute.status = "under_review"
    _event(db, dispute, user, "evidence_added", f"{payload.evidence_url} {payload.note}".strip())
    audit(db, user.id, "dispute", dispute_id, "evidence_added")
    db.commit()
    return dispute_payload(db, dispute)


@router.post("/disputes/{dispute_id}/resolve")
def propose_resolution(
    dispute_id: str,
    payload: DisputeResolution,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("dispute_resolve", 10, 60)),
):
    dispute = lock_row(db, Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    agreement = get_agreement_for_user(db, dispute.agreement_id, user)
    if dispute.status not in {"open", "under_review"}:
        raise HTTPException(status_code=409, detail="A resolution proposal is already pending or the dispute is closed")
    assert_transition("dispute", dispute.status, "awaiting_counterparty")
    dispute.status = "awaiting_counterparty"
    dispute.resolution = payload.resolution
    dispute.proposed_by = user.id
    dispute.proposal_version = 1
    _event(db, dispute, user, "resolution_proposed", payload.resolution)
    counterparty = agreement.freelancer_id if user.id == agreement.client_id else agreement.client_id
    notify(db, counterparty, "Dispute resolution proposed", f"Proposed resolution: {payload.resolution.replace('_', ' ')}.", "dispute", "dispute", dispute.id)
    audit(db, user.id, "dispute", dispute_id, "resolution_proposed", payload.resolution)
    db.commit()
    return dispute_payload(db, dispute)


@router.post("/disputes/{dispute_id}/amend")
def amend_resolution(
    dispute_id: str,
    payload: DisputeResolution,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("dispute_resolve", 10, 60)),
):
    """Explicit, auditable amendment of a pending proposal (no silent overwrite)."""
    dispute = lock_row(db, Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    get_agreement_for_user(db, dispute.agreement_id, user)
    if dispute.status != "awaiting_counterparty":
        raise HTTPException(status_code=409, detail="No pending proposal to amend")
    if dispute.proposed_by != user.id:
        raise HTTPException(status_code=403, detail="Only the proposing party may amend a proposal")
    previous = dispute.resolution
    dispute.resolution = payload.resolution
    dispute.proposal_version = (dispute.proposal_version or 0) + 1
    _event(db, dispute, user, "resolution_amended", f"{previous} -> {payload.resolution} (v{dispute.proposal_version})")
    counterparty = None
    agreement = db.get(WorkAgreement, dispute.agreement_id)
    if agreement:
        counterparty = agreement.freelancer_id if user.id == agreement.client_id else agreement.client_id
    if counterparty:
        notify(db, counterparty, "Dispute resolution amended", f"Proposal v{dispute.proposal_version}: {payload.resolution}.", "dispute", "dispute", dispute.id)
    audit(db, user.id, "dispute", dispute_id, "resolution_amended", payload.resolution)
    db.commit()
    return dispute_payload(db, dispute)


@router.post("/disputes/{dispute_id}/accept")
def accept_resolution(
    dispute_id: str,
    payload: DisputeResolution,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dispute = lock_row(db, Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    agreement = get_agreement_for_user(db, dispute.agreement_id, user)
    if dispute.status != "awaiting_counterparty":
        raise HTTPException(status_code=409, detail="No resolution is awaiting acceptance")
    assert_transition("dispute", dispute.status, "resolved")
    if not dispute.proposed_by or dispute.proposed_by == user.id:
        raise HTTPException(status_code=403, detail="The counterparty must accept the proposal")
    if dispute.resolution != payload.resolution:
        raise HTTPException(status_code=409, detail="Resolution does not match the proposal")
    if payload.resolution not in COUNTERPARTY_RESOLUTIONS:
        raise HTTPException(status_code=422, detail="Unsupported resolution")

    dispute.status = "resolved"
    dispute.resolved_by = user.id
    dispute.resolved_at = datetime.utcnow()
    project = db.get(Project, agreement.project_id)

    if payload.resolution == "release_freelancer":
        # Funds still require an explicit, verified on-chain payment.
        if dispute.milestone_id:
            milestone = db.get(AgreementMilestone, dispute.milestone_id)
            if milestone and milestone.status not in {"payment_released", "approved"}:
                milestone.status = "approved"
        if agreement.status == "disputed":
            agreement.status = "active"
        if project and project.status == "disputed":
            project.status = "active"
    else:
        # Refund/cancel: no milestone payment can be confirmed after resolution.
        agreement.status = "cancelled"
        if project and project.status == "disputed":
            project.status = "cancelled"
            project.cancelled_at = datetime.utcnow()

    _event(db, dispute, user, "resolution_accepted", payload.resolution)
    counterparty = dispute.proposed_by
    notify(db, counterparty, "Dispute resolved", f"Resolution {payload.resolution.replace('_', ' ')} was accepted.", "dispute", "dispute", dispute.id)
    notify(db, user.id, "Dispute resolved", f"Resolution {payload.resolution.replace('_', ' ')} recorded.", "dispute", "dispute", dispute.id)
    audit(db, user.id, "dispute", dispute_id, "resolved", payload.resolution)
    db.commit()
    return dispute_payload(db, dispute)
