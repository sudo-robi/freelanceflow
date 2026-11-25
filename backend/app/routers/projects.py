"""Project lifecycle, freelancer discovery, invitations and portfolio management."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AgreementMilestone,
    FreelancerProfile,
    PortfolioItem,
    Project,
    ProjectInvitation,
    User,
    WorkAgreement,
)
from ..ratelimit import rate_limit
from ..schemas import AvailabilityUpdate, PortfolioCreate, ProjectUpdate
from ..services import (
    audit,
    assert_not_disputed,
    notify,
    require_client,
    require_freelancer,
    serialize_datetime,
    to_float,
)

router = APIRouter(prefix="/api", tags=["projects"])

CLOSED_PROJECT_STATUSES = {"cancelled", "completed", "disputed"}
EDITABLE_PROJECT_STATUSES = {"draft", "open", "invitation_sent", "awaiting_agreement", "active", "under_review"}


def _freelancer_card(db: Session, profile: FreelancerProfile) -> dict:
    user = db.get(User, profile.user_id)
    return {
        "id": user.id,
        "full_name": user.full_name,
        "title": profile.title,
        "description": profile.description,
        "skills": profile.skills,
        "hourly_rate": to_float(profile.hourly_rate) if profile.hourly_rate is not None else None,
        "project_rate": to_float(profile.project_rate) if profile.project_rate is not None else None,
        "available": bool(profile.available),
        "availability_note": profile.availability_note,
        "portfolio_count": db.query(PortfolioItem).filter(PortfolioItem.freelancer_id == user.id).count(),
    }


@router.get("/freelancers")
def search_freelancers(
    skill: str = "",
    available_only: bool = False,
    min_rate: float | None = Query(default=None, ge=0),
    max_rate: float | None = Query(default=None, ge=0),
    sort: str = "name",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("freelancer_search", 60, 60)),
):
    counts = db.query(
        PortfolioItem.freelancer_id.label("freelancer_id"),
        func.count(PortfolioItem.id).label("item_count"),
    ).group_by(PortfolioItem.freelancer_id).subquery()
    query = db.query(
        FreelancerProfile,
        User,
        func.coalesce(counts.c.item_count, 0).label("portfolio_count"),
    ).join(User, User.id == FreelancerProfile.user_id).outerjoin(
        counts, counts.c.freelancer_id == FreelancerProfile.user_id
    )
    term = skill.strip().lower()
    if term:
        query = query.filter(
            FreelancerProfile.skills.ilike(f"%{term}%")
            | FreelancerProfile.title.ilike(f"%{term}%")
            | FreelancerProfile.description.ilike(f"%{term}%")
        )
    if available_only:
        query = query.filter(FreelancerProfile.available.is_(True))
    if min_rate is not None:
        query = query.filter(FreelancerProfile.hourly_rate >= Decimal(str(min_rate)))
    if max_rate is not None:
        query = query.filter(FreelancerProfile.hourly_rate <= Decimal(str(max_rate)))
    if sort == "rate":
        query = query.order_by(FreelancerProfile.hourly_rate.asc(), FreelancerProfile.id.asc())
    else:
        query = query.order_by(FreelancerProfile.id.asc())
    rows = query.offset(offset).limit(limit).all()
    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "title": profile.title,
            "description": profile.description,
            "skills": profile.skills,
            "hourly_rate": to_float(profile.hourly_rate) if profile.hourly_rate is not None else None,
            "project_rate": to_float(profile.project_rate) if profile.project_rate is not None else None,
            "available": bool(profile.available),
            "availability_note": profile.availability_note,
            "portfolio_count": int(portfolio_count),
        }
        for profile, user, portfolio_count in rows
    ]


@router.get("/freelancers/{freelancer_id}")
def get_freelancer(freelancer_id: str, db: Session = Depends(get_db)):
    user = db.get(User, freelancer_id)
    profile = db.query(FreelancerProfile).filter(FreelancerProfile.user_id == freelancer_id).first()
    if not user or user.role != "freelancer" or not profile:
        raise HTTPException(status_code=404, detail="Freelancer not found")
    result = _freelancer_card(db, profile)
    result["portfolio"] = [
        {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "description": item.description,
        }
        for item in db.query(PortfolioItem)
        .filter(PortfolioItem.freelancer_id == freelancer_id)
        .order_by(PortfolioItem.created_at.desc())
        .all()
    ]
    # Private fields (email, password hash, stellar address) are intentionally omitted.
    return result


@router.put("/me/availability")
def update_availability(
    payload: AvailabilityUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_freelancer(user)
    profile = db.query(FreelancerProfile).filter(FreelancerProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Freelancer profile not found")
    profile.available = payload.available
    profile.availability_note = payload.availability_note
    db.commit()
    return {"available": profile.available, "availability_note": profile.availability_note}


@router.post("/me/portfolio", status_code=201)
def add_portfolio_item(
    payload: PortfolioCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_freelancer(user)
    item = PortfolioItem(freelancer_id=user.id, **payload.model_dump())
    db.add(item)
    audit(db, user.id, "portfolio", user.id, "created", payload.title)
    db.commit()
    return {"id": item.id, "title": item.title, "url": item.url, "description": item.description}


@router.delete("/me/portfolio/{item_id}")
def delete_portfolio_item(
    item_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_freelancer(user)
    item = db.get(PortfolioItem, item_id)
    if not item or item.freelancer_id != user.id:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    db.delete(item)
    audit(db, user.id, "portfolio", user.id, "deleted", item_id)
    db.commit()
    return {"status": "deleted"}


@router.put("/projects/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_client(user)
    project = db.get(Project, project_id)
    if not project or project.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project client may edit this project")
    if project.status not in EDITABLE_PROJECT_STATUSES:
        raise HTTPException(status_code=409, detail="Project can no longer be edited")
    changes = payload.model_dump(exclude_unset=True)
    if "budget" in changes:
        existing_agreement = db.query(WorkAgreement).filter(WorkAgreement.project_id == project_id).first()
        if existing_agreement and Decimal(str(changes["budget"])) < existing_agreement.amount:
            raise HTTPException(status_code=422, detail="Budget cannot be below the agreed amount")
    for key, value in changes.items():
        setattr(project, key, value)
    project.updated_at = datetime.utcnow()
    audit(db, user.id, "project", project_id, "updated", ", ".join(sorted(changes)))
    notify(db, user.id, "Project updated", f"{project.title} was updated.", "project", "project", project_id)
    db.commit()
    return {"id": project.id, "status": project.status, "budget": to_float(project.budget)}


@router.post("/projects/{project_id}/cancel")
def cancel_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_client(user)
    project = db.get(Project, project_id)
    if not project or project.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project client may cancel this project")
    if project.status in CLOSED_PROJECT_STATUSES:
        raise HTTPException(status_code=409, detail="Project is already closed")
    agreement = db.query(WorkAgreement).filter(WorkAgreement.project_id == project_id).first()
    if agreement:
        assert_not_disputed(db, agreement.id)
        if db.query(AgreementMilestone).filter(
            AgreementMilestone.agreement_id == agreement.id,
            AgreementMilestone.status.in_(["approved", "payment_released"]),
        ).first():
            raise HTTPException(status_code=409, detail="An approved or paid milestone cannot be cancelled")
        agreement.status = "cancelled"
    project.status = "cancelled"
    project.cancelled_at = datetime.utcnow()
    if project.freelancer_id:
        notify(db, project.freelancer_id, "Project cancelled", f"{project.title} was cancelled.", "project", "project", project_id)
    audit(db, user.id, "project", project_id, "cancelled")
    db.commit()
    return {"status": "cancelled"}


@router.post("/projects/{project_id}/complete")
def complete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_client(user)
    project = db.get(Project, project_id)
    if not project or project.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project client may complete this project")
    if project.status in CLOSED_PROJECT_STATUSES:
        raise HTTPException(status_code=409, detail="Project is already closed")
    agreement = db.query(WorkAgreement).filter(WorkAgreement.project_id == project_id).first()
    if agreement:
        assert_not_disputed(db, agreement.id)
        pending = db.query(AgreementMilestone).filter(
            AgreementMilestone.agreement_id == agreement.id,
            AgreementMilestone.status != "payment_released",
        ).count()
        if pending:
            raise HTTPException(status_code=409, detail=f"{pending} milestone(s) are not paid yet")
    project.status = "completed"
    project.completed_at = datetime.utcnow()
    if project.freelancer_id:
        notify(db, project.freelancer_id, "Project completed", f"{project.title} was completed.", "project", "project", project_id)
    audit(db, user.id, "project", project_id, "completed")
    db.commit()
    return {"status": "completed"}


@router.get("/projects/{project_id}/activity")
def project_activity(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project or user.id not in {project.client_id, project.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    from ..models import AuditLog

    items = db.query(AuditLog).filter(
        ((AuditLog.entity_type == "project") & (AuditLog.entity_id == project_id))
        | ((AuditLog.entity_type == "agreement") & (AuditLog.entity_id.in_(
            db.query(WorkAgreement.id).filter(WorkAgreement.project_id == project_id)
        )))
    ).order_by(AuditLog.created_at.desc()).all()
    return [
        {
            "id": item.id,
            "actor_id": item.actor_id,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "action": item.action,
            "details": item.details,
            "created_at": serialize_datetime(item.created_at),
        }
        for item in items
    ]


@router.get("/invitations")
def list_invitations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ProjectInvitation)
    if user.role == "freelancer":
        query = query.filter(ProjectInvitation.freelancer_id == user.id)
    else:
        query = query.filter(ProjectInvitation.project_id.in_(
            db.query(Project.id).filter(Project.client_id == user.id)
        ))
    invitations = query.order_by(ProjectInvitation.created_at.desc()).all()
    project_ids = {item.project_id for item in invitations}
    titles = {
        row.id: row.title
        for row in db.query(Project.id, Project.title).filter(Project.id.in_(project_ids)).all()
    } if project_ids else {}
    return [
        {
            "id": item.id,
            "project_id": item.project_id,
            "project_title": titles.get(item.project_id),
            "status": item.status,
            "created_at": serialize_datetime(item.created_at),
            "expires_at": serialize_datetime(item.expires_at),
        }
        for item in invitations
    ]


@router.post("/invitations/{invitation_id}/reject")
def reject_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation = db.get(ProjectInvitation, invitation_id)
    if not invitation or invitation.freelancer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if invitation.status != "sent":
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")
    invitation.status = "rejected"
    project = db.get(Project, invitation.project_id)
    if project and project.status == "invitation_sent":
        remaining = db.query(ProjectInvitation).filter(
            ProjectInvitation.project_id == project.id,
            ProjectInvitation.status == "sent",
        ).count()
        if remaining == 0:
            project.status = "open"
    if project:
        notify(db, project.client_id, "Invitation rejected", f"A freelancer declined {project.title}.", "invitation", "project", project.id)
    audit(db, user.id, "invitation", invitation_id, "rejected")
    db.commit()
    return {"status": "rejected"}


@router.post("/invitations/{invitation_id}/expire")
def expire_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation = db.get(ProjectInvitation, invitation_id)
    if not invitation or invitation.freelancer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if invitation.status != "sent":
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")
    if not invitation.expires_at or invitation.expires_at > datetime.utcnow():
        raise HTTPException(status_code=409, detail="Invitation has not expired")
    invitation.status = "expired"
    db.commit()
    return {"status": "expired"}
