"""Milestone detail, progress tracking and pre-acceptance scope management."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import AgreementMilestone, AuditLog, User, WorkAgreement
from ..routers.agreements import milestone_payload
from ..schemas import MilestoneListUpdate
from ..services import assert_not_disputed, audit, get_milestone_for_user, notify, serialize_datetime

router = APIRouter(prefix="/api", tags=["milestones"])


@router.get("/milestones/{milestone_id}")
def get_milestone(
    milestone_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    milestone, agreement = get_milestone_for_user(db, milestone_id, user)
    payload = milestone_payload(milestone)
    payload["agreement_id"] = agreement.id
    payload["agreement_status"] = agreement.status
    payload["funding_status"] = "released" if milestone.status == "payment_released" else (
        "approved_awaiting_payment" if milestone.status == "approved" else "unfunded"
    )
    events = db.query(AuditLog).filter(
        (AuditLog.entity_type == "milestone") & (AuditLog.entity_id == milestone_id)
    ).order_by(AuditLog.created_at.desc()).all()
    payload["history"] = [
        {"action": item.action, "details": item.details, "created_at": serialize_datetime(item.created_at)}
        for item in events
    ]
    return payload


@router.post("/milestones/{milestone_id}/start")
def start_milestone(
    milestone_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    milestone, agreement = get_milestone_for_user(db, milestone_id, user)
    if user.id != agreement.freelancer_id:
        raise HTTPException(status_code=403, detail="Only the assigned freelancer can start work")
    if agreement.status != "active":
        raise HTTPException(status_code=409, detail="Agreement is not active")
    assert_not_disputed(db, agreement.id, milestone.id)
    if milestone.status != "not_started":
        raise HTTPException(status_code=409, detail="Milestone cannot be started from its current status")
    milestone.status = "in_progress"
    notify(db, agreement.client_id, "Work started", f'Work began on "{milestone.title}".', "milestone", "milestone", milestone.id)
    audit(db, user.id, "milestone", milestone.id, "started")
    db.commit()
    return {"status": milestone.status}


@router.post("/milestones/{milestone_id}/review-start")
def start_review(
    milestone_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    milestone, agreement = get_milestone_for_user(db, milestone_id, user)
    if user.id != agreement.client_id:
        raise HTTPException(status_code=403, detail="Only the client can review work")
    assert_not_disputed(db, agreement.id, milestone.id)
    if milestone.status != "submitted":
        raise HTTPException(status_code=409, detail="Milestone is not awaiting review")
    milestone.status = "under_review"
    notify(db, agreement.freelancer_id, "Review started", f'Your submission for "{milestone.title}" is under review.', "milestone", "milestone", milestone.id)
    audit(db, user.id, "milestone", milestone.id, "review_started")
    db.commit()
    return {"status": milestone.status}


@router.put("/agreements/{agreement_id}/milestones")
def replace_milestones(
    agreement_id: str,
    payload: MilestoneListUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agreement = db.get(WorkAgreement, agreement_id)
    if not agreement or user.id != agreement.client_id:
        raise HTTPException(status_code=403, detail="Only the project client may edit milestones")
    if agreement.client_accepted or agreement.freelancer_accepted:
        raise HTTPException(status_code=409, detail="Milestones of an accepted agreement are immutable")
    assert_not_disputed(db, agreement.id)
    if not payload.milestones:
        raise HTTPException(status_code=422, detail="At least one milestone is required")
    total = sum((item.amount for item in payload.milestones), Decimal("0"))
    if total != Decimal(str(agreement.amount)):
        raise HTTPException(status_code=422, detail="Milestone amounts must equal the agreement amount")
    for item in db.query(AgreementMilestone).filter(AgreementMilestone.agreement_id == agreement_id).all():
        db.delete(item)
    for item in payload.milestones:
        db.add(AgreementMilestone(
            agreement_id=agreement_id,
            title=item.title,
            description=item.description,
            amount=item.amount,
            due_date=item.due_date,
        ))
    notify(db, agreement.freelancer_id, "Milestones updated", f'Milestones for agreement {agreement_id[:8]} changed.', "milestone", "agreement", agreement_id)
    audit(db, user.id, "agreement", agreement_id, "milestones_updated", str(len(payload.milestones)))
    db.commit()
    return {"count": len(payload.milestones)}
