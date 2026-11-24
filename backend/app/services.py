"""Shared application services used by API routers.

All writes are explicit and auditable. Notification and audit records are
persisted in the same transaction as the business change that triggered them.
"""

import re
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import (
    AgreementMilestone,
    AuditLog,
    Dispute,
    Notification,
    PaymentRecord,
    Project,
    User,
    WorkAgreement,
)

PUBLIC_KEY = re.compile(r"G[A-Z2-7]{55}")
OPEN_DISPUTE_STATUSES = {"open", "under_review", "awaiting_counterparty"}


def as_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def to_float(value) -> float:
    return float(as_decimal(value))


def is_stellar_address(address: str | None) -> bool:
    return bool(address and PUBLIC_KEY.fullmatch(address))


def require_stellar_address(address: str | None, label: str) -> str:
    if not is_stellar_address(address):
        raise HTTPException(status_code=422, detail=f"{label} must be a valid Stellar public address")
    return address


def require_client(user: User) -> None:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can perform this action")


def require_freelancer(user: User) -> None:
    if user.role != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can perform this action")


def notify(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    category: str = "general",
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Notification:
    record = Notification(
        user_id=user_id,
        title=title,
        message=message,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(record)
    return record


def audit(
    db: Session,
    actor_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    details: str = "",
) -> AuditLog:
    record = AuditLog(
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=details,
    )
    db.add(record)
    return record


def get_project_for_user(db: Session, project_id: str, user: User) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.id not in {project.client_id, project.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    return project


def get_agreement_for_user(db: Session, agreement_id: str, user: User) -> WorkAgreement:
    agreement = db.get(WorkAgreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user.id not in {agreement.client_id, agreement.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    return agreement


def get_milestone_for_user(db: Session, milestone_id: str, user: User) -> tuple[AgreementMilestone, WorkAgreement]:
    milestone = db.get(AgreementMilestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    agreement = db.get(WorkAgreement, milestone.agreement_id)
    if not agreement or user.id not in {agreement.client_id, agreement.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    return milestone, agreement


def active_dispute(db: Session, agreement_id: str, milestone_id: str | None = None) -> Dispute | None:
    query = db.query(Dispute).filter(
        Dispute.agreement_id == agreement_id,
        Dispute.status.in_(OPEN_DISPUTE_STATUSES),
    )
    if milestone_id is not None:
        query = query.filter((Dispute.milestone_id == milestone_id) | (Dispute.milestone_id.is_(None)))
    return query.order_by(Dispute.created_at.desc()).first()


def assert_not_disputed(db: Session, agreement_id: str, milestone_id: str | None = None) -> None:
    if active_dispute(db, agreement_id, milestone_id):
        raise HTTPException(status_code=409, detail="An open dispute blocks this action")


def payment_totals(db: Session, user_id: str, is_freelancer: bool) -> dict:
    """Only independently verified, confirmed payments count as earnings or spend."""
    agreements = db.query(WorkAgreement).filter(
        (WorkAgreement.client_id == user_id) | (WorkAgreement.freelancer_id == user_id)
    ).all()
    ids = [agreement.id for agreement in agreements]
    if not ids:
        return {"confirmed_count": 0, "confirmed_amount": 0.0, "asset": "XLM"}
    payments = db.query(PaymentRecord).filter(
        PaymentRecord.agreement_id.in_(ids),
        PaymentRecord.status == "confirmed",
    ).all()
    return {
        "confirmed_count": len(payments),
        "confirmed_amount": round(sum(to_float(item.amount) for item in payments), 7),
        "asset": "XLM",
    }


def serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
