"""Agreement detail, version history, rejection and cancellation."""

from datetime import datetime
from decimal import Decimal
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AgreementMilestone,
    AgreementRevision,
    AuditLog,
    Dispute,
    PaymentRecord,
    Project,
    User,
    WorkAgreement,
)
from ..schemas import AgreementRevisionCreate
from ..services import (
    assert_not_disputed,
    audit,
    get_agreement_for_user,
    notify,
    serialize_datetime,
    to_float,
)

router = APIRouter(prefix="/api", tags=["agreements"])


def milestone_payload(item: AgreementMilestone) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "amount": to_float(item.amount),
        "due_date": item.due_date,
        "status": item.status,
        "deliverable_url": item.deliverable_url,
        "review_feedback": item.review_feedback,
        "submission_count": item.submission_count or 0,
        "submitted_at": serialize_datetime(item.submitted_at),
        "reviewed_at": serialize_datetime(item.reviewed_at),
    }


def agreement_payload(db: Session, agreement: WorkAgreement) -> dict:
    milestones = db.query(AgreementMilestone).filter(
        AgreementMilestone.agreement_id == agreement.id
    ).order_by(AgreementMilestone.id.asc()).all()
    dispute = db.query(Dispute).filter(
        Dispute.agreement_id == agreement.id,
        Dispute.status.in_(["open", "under_review", "awaiting_counterparty"]),
    ).first()
    return {
        "id": agreement.id,
        "project_id": agreement.project_id,
        "client_id": agreement.client_id,
        "freelancer_id": agreement.freelancer_id,
        "amount": to_float(agreement.amount),
        "asset": agreement.asset,
        "description": agreement.description,
        "status": agreement.status,
        "client_accepted": bool(agreement.client_accepted),
        "freelancer_accepted": bool(agreement.freelancer_accepted),
        "version": agreement.version,
        "escrow_contract_id": agreement.escrow_contract_id,
        "milestones": [milestone_payload(item) for item in milestones],
        "active_dispute_id": dispute.id if dispute else None,
        "created_at": serialize_datetime(agreement.created_at),
    }


@router.get("/agreements/{agreement_id}")
def get_agreement(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return agreement_payload(db, get_agreement_for_user(db, agreement_id, user))


@router.post("/agreements/{agreement_id}/reject")
def reject_agreement(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agreement = get_agreement_for_user(db, agreement_id, user)
    if user.id != agreement.freelancer_id:
        raise HTTPException(status_code=403, detail="Only the freelancer can reject an agreement")
    if agreement.status != "pending_acceptance":
        raise HTTPException(status_code=409, detail="Agreement is not awaiting acceptance")
    agreement.status = "cancelled"
    project = db.get(Project, agreement.project_id)
    if project and project.status == "awaiting_agreement":
        project.status = "open"
    notify(db, agreement.client_id, "Agreement rejected", f"The agreement for {project.title if project else 'your project'} was rejected.", "agreement", "agreement", agreement_id)
    audit(db, user.id, "agreement", agreement_id, "rejected")
    db.commit()
    return {"status": "cancelled"}


@router.post("/agreements/{agreement_id}/cancel")
def cancel_agreement(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agreement = get_agreement_for_user(db, agreement_id, user)
    if agreement.status == "cancelled":
        raise HTTPException(status_code=409, detail="Agreement is already cancelled")
    assert_not_disputed(db, agreement.id)
    if db.query(PaymentRecord).filter(
        PaymentRecord.agreement_id == agreement.id,
        PaymentRecord.status == "confirmed",
    ).first():
        raise HTTPException(status_code=409, detail="Agreement with confirmed payments cannot be cancelled")
    agreement.status = "cancelled"
    project = db.get(Project, agreement.project_id)
    if project and project.status not in {"completed", "cancelled", "disputed"}:
        project.status = "cancelled"
        project.cancelled_at = datetime.utcnow()
    counterparty = agreement.freelancer_id if user.id == agreement.client_id else agreement.client_id
    notify(db, counterparty, "Agreement cancelled", f"The agreement for {project.title if project else 'your project'} was cancelled.", "agreement", "agreement", agreement_id)
    audit(db, user.id, "agreement", agreement_id, "cancelled")
    db.commit()
    return {"status": "cancelled"}


@router.get("/agreements/{agreement_id}/revisions")
def list_revisions(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_agreement_for_user(db, agreement_id, user)
    revisions = db.query(AgreementRevision).filter(
        AgreementRevision.agreement_id == agreement_id
    ).order_by(AgreementRevision.version.asc()).all()
    return [
        {
            "id": item.id,
            "version": item.version,
            "amount": to_float(item.amount),
            "description": item.description,
            "milestones": json.loads(item.milestones_json),
            "changed_by": item.changed_by,
            "created_at": serialize_datetime(item.created_at),
        }
        for item in revisions
    ]


@router.put("/agreements/{agreement_id}")
def revise_agreement(
    agreement_id: str,
    payload: AgreementRevisionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agreement = get_agreement_for_user(db, agreement_id, user)
    if user.id != agreement.client_id:
        raise HTTPException(status_code=403, detail="Only the project client may revise an agreement")
    if agreement.client_accepted or agreement.freelancer_accepted:
        raise HTTPException(status_code=409, detail="An accepted agreement cannot be revised")
    if agreement.status != "pending_acceptance":
        raise HTTPException(status_code=409, detail="Agreement is not in a revisable state")
    assert_not_disputed(db, agreement.id)
    if not payload.milestones:
        raise HTTPException(status_code=422, detail="At least one milestone is required")
    total = sum((item.amount for item in payload.milestones), Decimal("0"))
    if total != payload.amount:
        raise HTTPException(status_code=422, detail="Milestone amounts must equal the agreement amount")
    project = db.get(Project, agreement.project_id)
    if payload.amount > Decimal(str(project.budget)):
        raise HTTPException(status_code=422, detail="Agreement amount cannot exceed the project budget")

    old_milestones = db.query(AgreementMilestone).filter(
        AgreementMilestone.agreement_id == agreement.id
    ).all()
    db.add(AgreementRevision(
        agreement_id=agreement.id,
        version=agreement.version,
        amount=agreement.amount,
        description=agreement.description,
        milestones_json=json.dumps([
            {"title": item.title, "description": item.description, "amount": to_float(item.amount), "due_date": item.due_date}
            for item in old_milestones
        ]),
        changed_by=user.id,
    ))
    for item in old_milestones:
        db.delete(item)
    for item in payload.milestones:
        db.add(AgreementMilestone(
            agreement_id=agreement.id,
            title=item.title,
            description=item.description,
            amount=item.amount,
            due_date=item.due_date,
        ))
    agreement.amount = payload.amount
    agreement.description = payload.description
    agreement.version += 1
    notify(
        db,
        agreement.freelancer_id,
        "Agreement revised",
        f"A new version ({agreement.version}) of the agreement is awaiting acceptance. {payload.change_note}".strip(),
        "agreement",
        "agreement",
        agreement.id,
    )
    audit(db, user.id, "agreement", agreement_id, "revised", f"version {agreement.version}")
    db.commit()
    return {"id": agreement.id, "version": agreement.version, "status": agreement.status}


@router.get("/agreements/{agreement_id}/activity")
def agreement_activity(
    agreement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_agreement_for_user(db, agreement_id, user)
    items = db.query(AuditLog).filter(
        AuditLog.entity_type == "agreement",
        AuditLog.entity_id == agreement_id,
    ).order_by(AuditLog.created_at.desc()).all()
    return [
        {
            "action": item.action,
            "details": item.details,
            "actor_id": item.actor_id,
            "created_at": serialize_datetime(item.created_at),
        }
        for item in items
    ]
