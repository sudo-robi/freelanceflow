"""Role-specific dashboards built exclusively from persisted, verified records."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AgreementMilestone,
    AuditLog,
    Dispute,
    Notification,
    PaymentRecord,
    Project,
    User,
    WorkAgreement,
)
from ..services import payment_totals, serialize_datetime, to_float

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "client":
        projects = db.query(Project).filter(Project.client_id == user.id).all()
    else:
        projects = db.query(Project).filter(Project.freelancer_id == user.id).all()
    agreement_ids = db.query(WorkAgreement.id).filter(
        (WorkAgreement.client_id == user.id) | (WorkAgreement.freelancer_id == user.id)
    ).all()
    agreement_ids = [item[0] for item in agreement_ids]

    status_counts: dict[str, int] = {}
    for project in projects:
        status_counts[project.status] = status_counts.get(project.status, 0) + 1

    if user.role == "client":
        pending = db.query(AgreementMilestone).filter(
            AgreementMilestone.agreement_id.in_(agreement_ids),
            AgreementMilestone.status.in_(["submitted", "under_review"]),
        ).count()
    else:
        pending = db.query(AgreementMilestone).filter(
            AgreementMilestone.agreement_id.in_(agreement_ids),
            AgreementMilestone.status == "revision_requested",
        ).count()

    payments = db.query(PaymentRecord).filter(
        PaymentRecord.agreement_id.in_(agreement_ids),
        PaymentRecord.status == "confirmed",
    ).order_by(PaymentRecord.created_at.desc()).limit(10).all()
    totals = payment_totals(db, user.id, user.role == "freelancer")
    open_disputes = db.query(Dispute).filter(
        Dispute.agreement_id.in_(agreement_ids),
        Dispute.status.in_(["open", "under_review", "awaiting_counterparty"]),
    ).count()
    unread = db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False)).count()

    payment_ids = [item[0] for item in db.query(PaymentRecord.id).filter(
        PaymentRecord.agreement_id.in_(agreement_ids)
    ).all()]
    activity = db.query(AuditLog).filter(
        ((AuditLog.entity_type == "project") & (AuditLog.entity_id.in_([item.id for item in projects])))
        | ((AuditLog.entity_type == "agreement") & (AuditLog.entity_id.in_(agreement_ids)))
        | ((AuditLog.entity_type == "payment") & (AuditLog.entity_id.in_(payment_ids)))
    ).order_by(AuditLog.created_at.desc()).limit(10).all()

    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "role": user.role,
            "email": user.email,
            "stellar_address": user.stellar_address,
        },
        "projects": {
            "total": len(projects),
            "by_status": status_counts,
            "recent": [
                {
                    "id": item.id,
                    "title": item.title,
                    "status": item.status,
                    "budget": to_float(item.budget),
                    "asset": item.asset,
                    "deadline": item.deadline,
                    "updated_at": serialize_datetime(item.updated_at or item.created_at),
                }
                for item in sorted(projects, key=lambda p: p.updated_at or p.created_at, reverse=True)[:10]
            ],
        },
        "payments": {
            "verified_count": totals["confirmed_count"],
            "verified_amount": totals["confirmed_amount"],
            "asset": totals["asset"],
            "recent": [
                {
                    "id": item.id,
                    "transaction_hash": item.transaction_hash,
                    "amount": to_float(item.amount),
                    "asset": item.asset,
                    "status": item.status,
                    "confirmed_at": serialize_datetime(item.confirmed_at),
                }
                for item in payments
            ],
        },
        "pending_reviews": pending,
        "open_disputes": open_disputes,
        "unread_notifications": unread,
        "activity": [
            {
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "details": item.details,
                "created_at": serialize_datetime(item.created_at),
            }
            for item in activity
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }
