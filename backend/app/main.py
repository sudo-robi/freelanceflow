from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import os

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .auth import bearer, create_session, get_current_user, hash_password, verify_password
from .database import Base, engine, get_db
from .models import (
    AgreementMilestone,
    AuditLog,
    ClientProfile,
    FreelancerProfile,
    Notification,
    PaymentRecord,
    Project,
    ProjectInvitation,
    User,
    WorkAgreement,
)
from .schemas import (
    AgreementCreate,
    InvitationCreate,
    LoginRequest,
    MilestoneUpdate,
    ProjectCreate,
    ProfileUpdate,
    RegisterRequest,
    SessionResponse,
)
from .stellar import get_testnet_account, get_transaction

app = FastAPI(title="FreelanceFlow API", version="0.1.0")
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "network": "stellar-testnet"}


@app.post("/api/auth/register", response_model=SessionResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    user = User(
        email=payload.email.lower(),
        password_hash=password_hash,
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.flush()
    if payload.role == "freelancer":
        db.add(FreelancerProfile(user_id=user.id, title="Freelancer", description=""))
    else:
        db.add(ClientProfile(user_id=user.id, company_name="", description=""))
    db.commit()
    return SessionResponse(token=create_session(db, user.id), role=user.role)


@app.post("/api/auth/login", response_model=SessionResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return SessionResponse(token=create_session(db, user.id), role=user.role)


@app.post("/api/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if credentials:
        from .models import Session as SessionModel

        db.query(SessionModel).filter(SessionModel.token == credentials.credentials).delete()
        db.commit()
    return {"status": "logged_out"}


@app.get("/api/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = None
    if user.role == "freelancer":
        profile = db.query(FreelancerProfile).filter(FreelancerProfile.user_id == user.id).first()
    else:
        profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "stellar_address": user.stellar_address,
        "profile": profile.__dict__ if profile else None,
    }


@app.put("/api/me")
def update_me(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.stellar_address is not None:
        if not (payload.stellar_address.startswith("G") and len(payload.stellar_address) == 56):
            raise HTTPException(status_code=422, detail="Invalid Stellar public address")
        user.stellar_address = payload.stellar_address
    if user.role == "freelancer":
        profile = db.query(FreelancerProfile).filter(FreelancerProfile.user_id == user.id).first()
        if not profile:
            profile = FreelancerProfile(user_id=user.id)
            db.add(profile)
        if payload.title is not None:
            profile.title = payload.title
        if payload.description is not None:
            profile.description = payload.description
        if payload.hourly_rate is not None:
            profile.hourly_rate = payload.hourly_rate
    else:
        profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
        if not profile:
            profile = ClientProfile(user_id=user.id)
            db.add(profile)
        if payload.title is not None:
            profile.company_name = payload.title
        if payload.description is not None:
            profile.description = payload.description
    db.commit()
    return {"status": "updated"}


@app.get("/api/freelancers")
def list_freelancers(skill: str = "", db: Session = Depends(get_db)):
    profiles = db.query(FreelancerProfile).all()
    results = []
    for profile in profiles:
        user = db.get(User, profile.user_id)
        if skill and skill.lower() not in (profile.description or "").lower() and skill.lower() not in (profile.title or "").lower():
            continue
        results.append({
            "id": user.id,
            "full_name": user.full_name,
            "title": profile.title,
            "description": profile.description,
            "hourly_rate": float(profile.hourly_rate) if profile.hourly_rate is not None else None,
        })
    return results


@app.post("/api/projects")
def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can create projects")
    project = Project(client_id=user.id, **payload.model_dump(), status="draft")
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "status": project.status}


@app.get("/api/projects")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Project)
    if user.role == "client":
        query = query.filter(Project.client_id == user.id)
    else:
        invited_project_ids = [
            invitation.project_id
            for invitation in db.query(ProjectInvitation).filter(
                ProjectInvitation.freelancer_id == user.id,
                ProjectInvitation.status == "sent",
            ).all()
        ]
        query = query.filter((Project.freelancer_id == user.id) | (Project.id.in_(invited_project_ids)))
    return [{"id": p.id, "title": p.title, "status": p.status, "budget": float(p.budget), "asset": p.asset} for p in query.all()]


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.id not in {project.client_id, project.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "required_skills": project.required_skills,
        "budget": float(project.budget),
        "asset": project.asset,
        "status": project.status,
        "deadline": project.deadline,
    }


@app.post("/api/projects/{project_id}/invitations")
def invite_freelancer(project_id: str, payload: InvitationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project or project.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project client may invite freelancers")
    freelancer = db.get(User, payload.freelancer_id)
    if not freelancer or freelancer.role != "freelancer":
        raise HTTPException(status_code=404, detail="Freelancer not found")
    if project.status in {"cancelled", "completed", "disputed"}:
        raise HTTPException(status_code=409, detail="Cannot invite freelancers to a closed project")
    existing = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_id == project_id,
        ProjectInvitation.freelancer_id == freelancer.id,
        ProjectInvitation.status.in_(["sent", "accepted"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Freelancer is already invited or accepted")
    invitation = ProjectInvitation(
        project_id=project_id,
        freelancer_id=freelancer.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invitation)
    project.status = "invitation_sent"
    db.add(Notification(user_id=freelancer.id, title="Project invitation", message=f"You were invited to {project.title}"))
    db.commit()
    return {"id": invitation.id, "status": invitation.status}


@app.post("/api/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invitation = db.get(ProjectInvitation, invitation_id)
    if not invitation or invitation.freelancer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    project = db.get(Project, invitation.project_id)
    if invitation.status != "sent":
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")
    if invitation.expires_at and invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        db.commit()
        raise HTTPException(status_code=409, detail="Invitation has expired")
    if project.status not in {"draft", "open", "invitation_sent"}:
        raise HTTPException(status_code=409, detail="Project is not accepting invitations")
    if project.freelancer_id is not None:
        raise HTTPException(status_code=409, detail="Project already has an accepted freelancer")
    invitation.status = "accepted"
    project.freelancer_id = user.id
    project.status = "awaiting_agreement"
    db.commit()
    return {"status": "accepted"}


@app.post("/api/projects/{project_id}/agreements")
def create_agreement(project_id: str, payload: AgreementCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project or project.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project client may create the agreement")
    if project.freelancer_id != payload.freelancer_id:
        raise HTTPException(status_code=400, detail="Freelancer is not assigned to this project")
    if project.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled projects cannot have agreements")
    if db.query(WorkAgreement).filter(WorkAgreement.project_id == project_id).first():
        raise HTTPException(status_code=409, detail="Project already has an agreement")
    if not payload.milestones:
        raise HTTPException(status_code=422, detail="At least one milestone is required")
    milestone_total = sum((item.amount for item in payload.milestones), Decimal("0"))
    if milestone_total != payload.amount:
        raise HTTPException(status_code=422, detail="Milestone amounts must equal the agreement amount")
    if payload.amount > Decimal(str(project.budget)):
        raise HTTPException(status_code=422, detail="Agreement amount cannot exceed the project budget")
    agreement = WorkAgreement(
        project_id=project_id,
        client_id=user.id,
        freelancer_id=payload.freelancer_id,
        amount=payload.amount,
        asset=payload.asset,
        description=payload.description,
    )
    db.add(agreement)
    db.flush()
    for item in payload.milestones:
        db.add(AgreementMilestone(
            agreement_id=agreement.id,
            title=item.title,
            description=item.description,
            amount=item.amount,
            due_date=item.due_date,
        ))
    project.status = "awaiting_agreement"
    db.commit()
    db.refresh(agreement)
    return {"id": agreement.id, "status": agreement.status}


@app.post("/api/agreements/{agreement_id}/accept")
def accept_agreement(agreement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    agreement = db.get(WorkAgreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user.id == agreement.client_id:
        agreement.client_accepted = True
    elif user.id == agreement.freelancer_id:
        agreement.freelancer_accepted = True
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    if agreement.client_accepted and agreement.freelancer_accepted:
        agreement.status = "active"
        project = db.get(Project, agreement.project_id)
        project.status = "active"
    db.commit()
    return {"status": agreement.status, "client_accepted": agreement.client_accepted, "freelancer_accepted": agreement.freelancer_accepted}


@app.post("/api/milestones/{milestone_id}/submit")
def submit_milestone(milestone_id: str, payload: MilestoneUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    milestone = db.get(AgreementMilestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    agreement = db.get(WorkAgreement, milestone.agreement_id)
    if agreement.status != "active":
        raise HTTPException(status_code=409, detail="Agreement is not active")
    project = db.get(Project, agreement.project_id)
    if project.status in {"cancelled", "completed"}:
        raise HTTPException(status_code=409, detail="Project is closed")
    if milestone.status not in {"not_started", "in_progress", "revision_requested"}:
        raise HTTPException(status_code=409, detail="Milestone cannot accept a new submission")
    if agreement.freelancer_id != user.id:
        raise HTTPException(status_code=403, detail="Only the assigned freelancer can submit work")
    if not payload.deliverable_url:
        raise HTTPException(status_code=422, detail="A deliverable URL is required")
    milestone.deliverable_url = payload.deliverable_url
    milestone.status = "submitted"
    db.commit()
    return {"status": milestone.status}


@app.post("/api/milestones/{milestone_id}/review")
def review_milestone(milestone_id: str, payload: MilestoneUpdate, approved: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    milestone = db.get(AgreementMilestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    agreement = db.get(WorkAgreement, milestone.agreement_id)
    if agreement.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the client can review the milestone")
    if milestone.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="Milestone is not awaiting review")
    if approved:
        milestone.status = "approved"
    else:
        milestone.status = "revision_requested"
        milestone.review_feedback = payload.feedback
    db.commit()
    return {"status": milestone.status}


@app.post("/api/payments/verify")
def verify_payment(transaction_hash: str, milestone_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    milestone = db.get(AgreementMilestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    agreement = db.get(WorkAgreement, milestone.agreement_id)
    if user.id not in {agreement.client_id, agreement.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    if milestone.status != "approved":
        raise HTTPException(status_code=409, detail="Milestone is not approved")
    existing = db.query(PaymentRecord).filter(PaymentRecord.transaction_hash == transaction_hash).first()
    if existing:
        raise HTTPException(status_code=409, detail="Transaction already recorded")
    return {"status": "verification_required", "message": "Use Stellar Horizon transaction verification in the client, then confirm with /api/payments/{hash}"}


@app.get("/api/payments/{transaction_hash}/verify")
async def verify_transaction(transaction_hash: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(transaction_hash) != 64:
        raise HTTPException(status_code=422, detail="Invalid Stellar transaction hash")
    try:
        result = await get_transaction(transaction_hash)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Horizon verification failed: {error}") from error
    if not result.get("successful"):
        raise HTTPException(status_code=404, detail="Transaction not found or not successful")
    return result


@app.post("/api/payments/{transaction_hash}/confirm")
async def confirm_payment(transaction_hash: str, milestone_id: str, ledger: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(transaction_hash) != 64 or any(character not in "0123456789abcdef" for character in transaction_hash.lower()):
        raise HTTPException(status_code=422, detail="Invalid Stellar transaction hash")
    milestone = db.get(AgreementMilestone, milestone_id)
    agreement = db.get(WorkAgreement, milestone.agreement_id) if milestone else None
    if not agreement:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if user.id != agreement.client_id:
        raise HTTPException(status_code=403, detail="Only the project client can confirm payment")
    existing = db.query(PaymentRecord).filter(PaymentRecord.transaction_hash == transaction_hash).first()
    if existing:
        if existing.milestone_id == milestone.id:
            return {"status": "confirmed", "transaction_hash": transaction_hash, "duplicate": True}
        raise HTTPException(status_code=409, detail="Transaction already recorded")
    if milestone.status != "approved":
        raise HTTPException(status_code=409, detail="Milestone is not approved")
    client = db.get(User, agreement.client_id)
    freelancer = db.get(User, agreement.freelancer_id)
    if not client.stellar_address or not freelancer.stellar_address:
        raise HTTPException(status_code=422, detail="Both parties must set Stellar public addresses")
    try:
        transaction = await get_transaction(transaction_hash)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Horizon verification failed: {error}") from error
    if not transaction.get("found") or not transaction.get("successful"):
        raise HTTPException(status_code=409, detail="Transaction was not found or was not successful")
    matching_payments = [
        operation for operation in transaction["operations"]
        if operation["type"] in {"payment", "path_payment_strict_send", "path_payment_strict_receive"}
        and operation.get("to") == freelancer.stellar_address
        and operation.get("from") == client.stellar_address
        and transaction.get("source_account") == client.stellar_address
        and operation.get("asset_type") == "native"
    ]
    try:
        expected_amount = Decimal(str(milestone.amount))
        amount_matches = any(Decimal(operation["amount"]) == expected_amount for operation in matching_payments)
    except (InvalidOperation, KeyError, TypeError):
        amount_matches = False
    if not matching_payments or not amount_matches:
        raise HTTPException(
            status_code=422,
            detail="Transaction does not match the milestone source, destination, native asset, and amount",
        )
    payment = PaymentRecord(
        agreement_id=agreement.id,
        milestone_id=milestone.id,
        amount=milestone.amount,
        asset=agreement.asset,
        transaction_hash=transaction_hash,
        ledger=ledger if ledger is not None else transaction.get("ledger"),
        network="testnet",
        status="confirmed",
        confirmed_at=datetime.utcnow(),
        source_account=client.stellar_address,
        destination_account=freelancer.stellar_address,
    )
    milestone.status = "payment_released"
    db.add(payment)
    db.commit()
    return {"status": "confirmed", "transaction_hash": transaction_hash}


@app.get("/api/stellar/account/{address}")
async def stellar_account(address: str):
    if len(address) != 56:
        raise HTTPException(status_code=422, detail="Invalid Stellar public address")
    try:
        return await get_testnet_account(address)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Horizon account lookup failed: {error}") from error


@app.get("/api/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).all()
    return [{"id": n.id, "title": n.title, "message": n.message, "read": n.read, "created_at": n.created_at.isoformat()} for n in items]


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    notification.read = True
    db.commit()
    return {"status": "read"}


@app.get("/api/payments")
def payment_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    agreements = db.query(WorkAgreement).filter(
        (WorkAgreement.client_id == user.id) | (WorkAgreement.freelancer_id == user.id)
    ).all()
    agreement_ids = [agreement.id for agreement in agreements]
    payments = db.query(PaymentRecord).filter(PaymentRecord.agreement_id.in_(agreement_ids)).order_by(PaymentRecord.created_at.desc()).all()
    return [{
        "id": payment.id,
        "milestone_id": payment.milestone_id,
        "agreement_id": payment.agreement_id,
        "amount": float(payment.amount),
        "asset": payment.asset,
        "transaction_hash": payment.transaction_hash,
        "ledger": payment.ledger,
        "network": payment.network,
        "status": payment.status,
        "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
        "source_account": payment.source_account,
        "destination_account": payment.destination_account,
    } for payment in payments]
