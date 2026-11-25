from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging

import os

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .auth import bearer, create_session, get_current_user, hash_password, verify_password
from .ratelimit import rate_limit
from .services import (
    assert_not_disputed,
    assert_transition,
    audit,
    is_stellar_address,
    lock_row,
    notify,
    require_stellar_address,
    serialize_datetime,
    to_float,
)
from .database import Base, engine, ensure_schema, get_db
from .models import (
    AgreementMilestone,
    AuditLog,
    ClientProfile,
    FreelancerProfile,
    Invoice,
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
from .stellar import TESTNET_PASSPHRASE, get_network_passphrase, get_testnet_account, get_transaction
from .routers import agreements, dashboard, disputes, finance, milestones, projects, stellar

logger = logging.getLogger("freelanceflow")
app = FastAPI(title="FreelanceFlow API", version="0.3.0")
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
    ensure_schema()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "network": "stellar-testnet"}


@app.post("/api/auth/register", response_model=SessionResponse)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("register", 10, 60)),
):
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
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("login", 10, 60)),
):
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


@app.post("/api/auth/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke every session belonging to the current user."""
    from .models import Session as SessionModel

    deleted = db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
    db.commit()
    audit(db, user.id, "session", user.id, "revoked_all", str(deleted))
    db.commit()
    return {"revoked": deleted}


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
        user.stellar_address = require_stellar_address(payload.stellar_address, "stellar_address")
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
        if payload.project_rate is not None:
            profile.project_rate = payload.project_rate
        if payload.skills is not None:
            profile.skills = payload.skills
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
        "client_id": project.client_id,
        "freelancer_id": project.freelancer_id,
        "agreement_id": (
            agreement.id
            if (agreement := db.query(WorkAgreement).filter(WorkAgreement.project_id == project_id).first())
            else None
        ),
        "created_at": project.created_at.isoformat(),
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
    db.flush()
    project.status = "invitation_sent"
    notify(db, freelancer.id, "Project invitation", f"You were invited to {project.title}", "invitation", "project", project_id)
    audit(db, user.id, "invitation", invitation.id, "sent", project_id)
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
    notify(db, project.client_id, "Invitation accepted", f"{user.full_name} accepted your invitation to {project.title}.", "invitation", "project", project.id)
    audit(db, user.id, "invitation", invitation_id, "accepted", project.id)
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
    notify(db, payload.freelancer_id, "Agreement ready", f"An agreement for {project.title} is awaiting your acceptance.", "agreement", "agreement", agreement.id)
    audit(db, user.id, "agreement", agreement.id, "created", f"version {agreement.version}")
    db.commit()
    db.refresh(agreement)
    return {"id": agreement.id, "status": agreement.status}


@app.post("/api/agreements/{agreement_id}/accept")
def accept_agreement(agreement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Idempotent acceptance with explicit, atomic state transitions."""
    agreement = lock_row(db, WorkAgreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    is_client = user.id == agreement.client_id
    is_freelancer = user.id == agreement.freelancer_id
    if not is_client and not is_freelancer:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Re-reading inside the lock prevents stale concurrent acceptance from
    # mutating a terminal agreement.
    if agreement.status == "active" and agreement.client_accepted and agreement.freelancer_accepted:
        return {
            "status": agreement.status,
            "client_accepted": agreement.client_accepted,
            "freelancer_accepted": agreement.freelancer_accepted,
            "idempotent": True,
        }
    if agreement.status != "pending_acceptance":
        raise HTTPException(status_code=409, detail=f"Invalid agreement state transition from {agreement.status}")
    already = agreement.client_accepted if is_client else agreement.freelancer_accepted
    if already:
        return {
            "status": agreement.status,
            "client_accepted": agreement.client_accepted,
            "freelancer_accepted": agreement.freelancer_accepted,
            "idempotent": True,
        }

    if is_client:
        agreement.client_accepted = True
    else:
        agreement.freelancer_accepted = True
    target = "active" if agreement.client_accepted and agreement.freelancer_accepted else "pending_acceptance"
    if target != agreement.status:
        assert_transition("agreement", agreement.status, target)
        agreement.status = target
    audit(db, user.id, "agreement", agreement_id, "accepted_by_client" if is_client else "accepted_by_freelancer")
    if target == "active":
        project = db.get(Project, agreement.project_id)
        project.status = "active"
        counterparty = agreement.freelancer_id if is_client else agreement.client_id
        notify(db, counterparty, "Agreement active", f"The agreement for {project.title} is now active.", "agreement", "agreement", agreement_id)
    else:
        counterparty = agreement.freelancer_id if is_client else agreement.client_id
        notify(db, counterparty, "Agreement accepted", f"{user.full_name} accepted the agreement; awaiting the other party.", "agreement", "agreement", agreement_id)
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
    assert_not_disputed(db, agreement.id, milestone.id)
    if milestone.status not in {"not_started", "in_progress", "revision_requested"}:
        raise HTTPException(status_code=409, detail="Milestone cannot accept a new submission")
    if agreement.freelancer_id != user.id:
        raise HTTPException(status_code=403, detail="Only the assigned freelancer can submit work")
    if not payload.deliverable_url:
        raise HTTPException(status_code=422, detail="A deliverable URL is required")
    if not payload.deliverable_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="Deliverable URL must start with http:// or https://")
    milestone.deliverable_url = payload.deliverable_url
    milestone.status = "submitted"
    milestone.submission_count = (milestone.submission_count or 0) + 1
    milestone.submitted_at = datetime.utcnow()
    milestone.review_feedback = None
    notify(db, agreement.client_id, "Work submitted", f'"{milestone.title}" was submitted for review.', "milestone", "milestone", milestone_id)
    audit(db, user.id, "milestone", milestone_id, "submitted", f"submission {milestone.submission_count}")
    db.commit()
    return {"status": milestone.status, "submission_count": milestone.submission_count}


@app.post("/api/milestones/{milestone_id}/review")
def review_milestone(milestone_id: str, payload: MilestoneUpdate, approved: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    milestone = db.get(AgreementMilestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    agreement = db.get(WorkAgreement, milestone.agreement_id)
    if agreement.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the client can review the milestone")
    assert_not_disputed(db, agreement.id, milestone.id)
    if milestone.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="Milestone is not awaiting review")
    if approved:
        milestone.status = "approved"
        milestone.review_feedback = None
        action = "approved"
        title = "Milestone approved"
        message = f'"{milestone.title}" was approved. Payment can now be initiated.'
    else:
        milestone.status = "revision_requested"
        milestone.review_feedback = payload.feedback or ""
        action = "revision_requested"
        title = "Revision requested"
        message = f'"{milestone.title}" needs revision: {milestone.review_feedback}'
    milestone.reviewed_at = datetime.utcnow()
    notify(db, agreement.freelancer_id, title, message, "milestone", "milestone", milestone_id)
    audit(db, user.id, "milestone", milestone_id, action, milestone.review_feedback or "")
    db.commit()
    return {"status": milestone.status}


@app.get("/api/payments/{transaction_hash}/verify")
async def verify_transaction(
    transaction_hash: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limit: None = Depends(rate_limit("payment_verify", 30, 60)),
):
    if len(transaction_hash) != 64 or any(character not in "0123456789abcdef" for character in transaction_hash.lower()):
        raise HTTPException(status_code=422, detail="Invalid Stellar transaction hash")
    try:
        result = await get_transaction(transaction_hash)
    except Exception as error:
        logger.warning("Horizon verification failed for %s: %s", transaction_hash, type(error).__name__)
        raise HTTPException(status_code=502, detail="Upstream verification unavailable") from error
    if not result.get("successful"):
        raise HTTPException(status_code=404, detail="Transaction not found or not successful")
    return result


@app.post("/api/payments/{transaction_hash}/confirm")
async def confirm_payment(
    transaction_hash: str,
    milestone_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    intent_id: str | None = None,
    _limit: None = Depends(rate_limit("payment_confirm", 20, 60)),
):
    """Confirm a payment only after independent Stellar Testnet verification.

    The client-supplied hash is a lookup key, never proof of payment. The
    authoritative source is Horizon data fetched by this server.
    """
    from .models import PaymentIntent

    if len(transaction_hash) != 64 or any(character not in "0123456789abcdef" for character in transaction_hash.lower()):
        raise HTTPException(status_code=422, detail="Invalid Stellar transaction hash")
    milestone = lock_row(db, AgreementMilestone, milestone_id)
    agreement = lock_row(db, WorkAgreement, milestone.agreement_id) if milestone else None
    if not agreement:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if user.id != agreement.client_id:
        raise HTTPException(status_code=403, detail="Only the project client can confirm payment")
    existing = db.query(PaymentRecord).filter(PaymentRecord.transaction_hash == transaction_hash).first()
    if existing:
        if existing.milestone_id == milestone.id:
            invoice = db.query(Invoice).filter(Invoice.payment_id == existing.id).first()
            return {
                "status": "confirmed",
                "transaction_hash": transaction_hash,
                "duplicate": True,
                "invoice_id": invoice.id if invoice else None,
            }
        raise HTTPException(status_code=409, detail="Transaction already recorded")
    assert_not_disputed(db, agreement.id, milestone.id)
    if agreement.status != "active":
        raise HTTPException(status_code=409, detail="Agreement is not active")
    if milestone.status != "approved":
        raise HTTPException(status_code=409, detail="Milestone is not approved")
    client = db.get(User, agreement.client_id)
    freelancer = db.get(User, agreement.freelancer_id)
    require_stellar_address(client.stellar_address, "client stellar_address")
    require_stellar_address(freelancer.stellar_address, "freelancer stellar_address")

    intent = db.get(PaymentIntent, intent_id) if intent_id else None
    if intent_id and (not intent or intent.client_id != user.id or intent.milestone_id != milestone.id):
        raise HTTPException(status_code=403, detail="Payment intent is not valid for this milestone")
    if intent is None:
        intent = db.query(PaymentIntent).filter(
            PaymentIntent.milestone_id == milestone.id,
            PaymentIntent.client_id == user.id,
            PaymentIntent.status == "pending",
        ).order_by(PaymentIntent.created_at.desc()).first()
    if intent:
        if intent.status != "pending" or intent.expires_at < datetime.utcnow():
            raise HTTPException(status_code=409, detail="Payment intent is no longer valid")
        if (
            intent.agreement_id != agreement.id
            or intent.freelancer_id != freelancer.id
            or intent.expected_source != client.stellar_address
            or intent.expected_destination != freelancer.stellar_address
            or intent.asset != agreement.asset
            or intent.network != "testnet"
            or Decimal(str(intent.amount)) != Decimal(str(milestone.amount))
        ):
            raise HTTPException(status_code=422, detail="Payment intent does not match this milestone and parties")

    try:
        live_passphrase = await get_network_passphrase()
    except Exception as error:
        logger.warning("Network passphrase lookup failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Upstream verification unavailable") from error
    if live_passphrase != TESTNET_PASSPHRASE:
        logger.error("Network passphrase mismatch; refusing payment confirmation")
        raise HTTPException(status_code=502, detail="Upstream verification unavailable")

    try:
        transaction = await get_transaction(transaction_hash)
    except Exception as error:
        logger.warning("Horizon verification failed for %s: %s", transaction_hash, type(error).__name__)
        raise HTTPException(status_code=502, detail="Upstream verification unavailable") from error
    if not transaction.get("found") or not transaction.get("successful"):
        raise HTTPException(status_code=409, detail="Transaction was not found or was not successful")
    if transaction.get("source_account") != client.stellar_address:
        raise HTTPException(status_code=422, detail="Transaction source does not match the client address")
    if intent and str(transaction.get("memo") or "") != intent.memo:
        raise HTTPException(status_code=422, detail="Transaction memo does not match the payment intent")

    matching_payments = [
        operation for operation in transaction["operations"]
        if operation["type"] in {"payment", "path_payment_strict_send", "path_payment_strict_receive"}
        and operation.get("to") == freelancer.stellar_address
        and operation.get("from") == client.stellar_address
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

    project = db.get(Project, agreement.project_id)
    payment = PaymentRecord(
        agreement_id=agreement.id,
        milestone_id=milestone.id,
        amount=milestone.amount,
        asset=agreement.asset,
        transaction_hash=transaction_hash,
        ledger=transaction.get("ledger"),
        network="testnet",
        status="confirmed",
        confirmed_at=datetime.utcnow(),
        source_account=client.stellar_address,
        destination_account=freelancer.stellar_address,
        intent_id=intent.id if intent else None,
        memo=intent.memo if intent else None,
    )
    milestone.status = "payment_released"
    db.add(payment)
    db.flush()
    invoice = finance.create_invoice_for_payment(db, payment)
    if intent:
        intent.status = "confirmed"
        intent.confirmed_at = datetime.utcnow()
    notify(db, freelancer.id, "Payment verified", f'Payment for "{milestone.title}" was verified on Stellar Testnet.', "payment", "payment", payment.id)
    audit(db, user.id, "payment", payment.id, "confirmed", transaction_hash)
    db.commit()
    return {
        "status": "confirmed",
        "transaction_hash": transaction_hash,
        "network": "testnet",
        "payment_id": payment.id,
        "invoice_id": invoice.id,
        "duplicate": False,
    }


@app.get("/api/stellar/account/{address}")
async def stellar_account(
    address: str,
    user: User = Depends(get_current_user),
    _limit: None = Depends(rate_limit("stellar_account", 30, 60)),
):
    require_stellar_address(address, "address")
    try:
        return await get_testnet_account(address)
    except Exception as error:
        logger.warning("Horizon account lookup failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Upstream account lookup unavailable") from error


@app.get("/api/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "read": n.read,
            "category": n.category,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "created_at": n.created_at.isoformat(),
        }
        for n in items
    ]


@app.get("/api/notifications/unread-count")
def unread_notification_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"count": db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False)).count()}


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
        "amount": to_float(payment.amount),
        "asset": payment.asset,
        "transaction_hash": payment.transaction_hash,
        "ledger": payment.ledger,
        "network": payment.network,
        "status": payment.status,
        "confirmed_at": serialize_datetime(payment.confirmed_at),
        "source_account": payment.source_account,
        "destination_account": payment.destination_account,
        "memo": payment.memo,
    } for payment in payments]


app.include_router(projects.router)
app.include_router(agreements.router)
app.include_router(milestones.router)
app.include_router(disputes.router)
app.include_router(finance.router)
app.include_router(dashboard.router)
app.include_router(stellar.router)
