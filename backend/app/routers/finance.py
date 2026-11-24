"""Payment intents, verified financial records, invoices, receipts and exports."""

import csv
import io
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AgreementMilestone,
    Invoice,
    PaymentIntent,
    PaymentRecord,
    Project,
    User,
    WorkAgreement,
)
from ..pdf import simple_pdf
from ..schemas import PaymentIntentCreate
from ..services import (
    assert_not_disputed,
    audit,
    is_stellar_address,
    payment_totals,
    require_client,
    serialize_datetime,
    to_float,
)

router = APIRouter(prefix="/api", tags=["finance"])


def create_invoice_for_payment(db: Session, payment: PaymentRecord) -> Invoice:
    """Called in the same transaction as payment confirmation, exactly once."""
    existing = db.query(Invoice).filter(Invoice.payment_id == payment.id).first()
    if existing:
        return existing
    milestone = db.get(AgreementMilestone, payment.milestone_id)
    agreement = db.get(WorkAgreement, payment.agreement_id)
    project = db.get(Project, agreement.project_id) if agreement else None
    invoice = Invoice(
        payment_id=payment.id,
        invoice_number=f"FF-{datetime.utcnow().year}-{payment.id[:8].upper()}",
        client_id=agreement.client_id,
        freelancer_id=agreement.freelancer_id,
        amount=payment.amount,
        asset=payment.asset,
        milestone_title=milestone.title if milestone else "Milestone",
        project_title=project.title if project else "Project",
        transaction_hash=payment.transaction_hash,
    )
    db.add(invoice)
    return invoice


def _owned_payments(db: Session, user: User) -> list[PaymentRecord]:
    agreements = db.query(WorkAgreement).filter(
        (WorkAgreement.client_id == user.id) | (WorkAgreement.freelancer_id == user.id)
    ).all()
    ids = [item.id for item in agreements]
    if not ids:
        return []
    return db.query(PaymentRecord).filter(
        PaymentRecord.agreement_id.in_(ids),
        PaymentRecord.status == "confirmed",
    ).order_by(PaymentRecord.created_at.desc()).all()


def _payment_payload(payment: PaymentRecord) -> dict:
    return {
        "id": payment.id,
        "agreement_id": payment.agreement_id,
        "milestone_id": payment.milestone_id,
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
    }


@router.post("/payment-intents", status_code=201)
def create_payment_intent(
    payload: PaymentIntentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_client(user)
    milestone = db.get(AgreementMilestone, payload.milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    agreement = db.get(WorkAgreement, milestone.agreement_id)
    if not agreement or agreement.client_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project client may initiate payment")
    assert_not_disputed(db, agreement.id, milestone.id)
    if milestone.status != "approved":
        raise HTTPException(status_code=409, detail="Milestone is not approved for payment")
    if db.query(PaymentRecord).filter(PaymentRecord.milestone_id == milestone.id, PaymentRecord.status == "confirmed").first():
        raise HTTPException(status_code=409, detail="Milestone is already paid")
    client = db.get(User, agreement.client_id)
    freelancer = db.get(User, agreement.freelancer_id)
    if not is_stellar_address(client.stellar_address) or not is_stellar_address(freelancer.stellar_address):
        raise HTTPException(status_code=422, detail="Both parties must set valid Stellar public addresses")
    memo = payload.memo or uuid.uuid4().hex[:24]
    if len(memo) > 28 or db.query(PaymentIntent).filter(PaymentIntent.memo == memo).first():
        raise HTTPException(status_code=409, detail="Payment memo is invalid or already in use")
    intent = PaymentIntent(
        milestone_id=milestone.id,
        agreement_id=agreement.id,
        client_id=user.id,
        freelancer_id=freelancer.id,
        amount=milestone.amount,
        asset="XLM",
        network="testnet",
        expected_source=client.stellar_address,
        expected_destination=freelancer.stellar_address,
        memo=memo,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(intent)
    db.flush()
    audit(db, user.id, "payment_intent", intent.id, "created", milestone.id)
    db.commit()
    return {
        "id": intent.id,
        "milestone_id": milestone.id,
        "amount": to_float(intent.amount),
        "asset": intent.asset,
        "network": intent.network,
        "network_passphrase": "Test SDF Network ; September 2015",
        "source_account": intent.expected_source,
        "destination_account": intent.expected_destination,
        "memo": intent.memo,
        "horizon_url": "https://horizon-testnet.stellar.org",
        "expires_at": serialize_datetime(intent.expires_at),
        "status": intent.status,
    }


@router.get("/payment-intents/{intent_id}")
def get_payment_intent(
    intent_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    intent = db.get(PaymentIntent, intent_id)
    if not intent or user.id not in {intent.client_id, intent.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    return {
        "id": intent.id,
        "milestone_id": intent.milestone_id,
        "amount": to_float(intent.amount),
        "asset": intent.asset,
        "network": intent.network,
        "network_passphrase": "Test SDF Network ; September 2015",
        "source_account": intent.expected_source,
        "destination_account": intent.expected_destination,
        "memo": intent.memo,
        "status": intent.status,
        "expires_at": serialize_datetime(intent.expires_at),
    }


@router.get("/payments/summary")
def payment_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    totals = payment_totals(db, user.id, user.role == "freelancer")
    return {
        "role": user.role,
        **totals,
        "verified_count": totals["confirmed_count"],
        "verified_amount": totals["confirmed_amount"],
    }


@router.get("/payments/export.csv")
def export_payments_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "payment_id", "transaction_hash", "status", "network", "asset", "amount",
        "ledger", "confirmed_at", "source_account", "destination_account", "memo",
    ])
    for payment in _owned_payments(db, user):
        writer.writerow([
            payment.id, payment.transaction_hash, payment.status, payment.network,
            payment.asset, to_float(payment.amount), payment.ledger,
            serialize_datetime(payment.confirmed_at) or "", payment.source_account,
            payment.destination_account, payment.memo or "",
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="freelanceflow-payments.csv"'},
    )


@router.get("/payments/{payment_id}/receipt")
def payment_receipt(
    payment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = db.get(PaymentRecord, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
    agreement = db.get(WorkAgreement, payment.agreement_id)
    if not agreement or user.id not in {agreement.client_id, agreement.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    milestone = db.get(AgreementMilestone, payment.milestone_id)
    return {
        "receipt_number": f"RCP-{payment.id[:12].upper()}",
        "verified_by": "Stellar Testnet Horizon",
        "network": payment.network,
        **_payment_payload(payment),
        "milestone_title": milestone.title if milestone else None,
        "client_id": agreement.client_id,
        "freelancer_id": agreement.freelancer_id,
    }


@router.get("/invoices")
def list_invoices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Invoice).filter(
        (Invoice.client_id == user.id) | (Invoice.freelancer_id == user.id)
    ).order_by(Invoice.created_at.desc()).all()
    return [
        {
            "id": item.id,
            "invoice_number": item.invoice_number,
            "payment_id": item.payment_id,
            "amount": to_float(item.amount),
            "asset": item.asset,
            "project_title": item.project_title,
            "milestone_title": item.milestone_title,
            "transaction_hash": item.transaction_hash,
            "created_at": serialize_datetime(item.created_at),
        }
        for item in items
    ]


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice or user.id not in {invoice.client_id, invoice.freelancer_id}:
        raise HTTPException(status_code=403, detail="Not authorized")
    lines = [
        f"Invoice number: {invoice.invoice_number}",
        f"Issued: {serialize_datetime(invoice.created_at)}",
        f"Project: {invoice.project_title}",
        f"Milestone: {invoice.milestone_title}",
        f"Amount: {to_float(invoice.amount)} {invoice.asset}",
        f"Network: Stellar Testnet",
        f"Verified transaction: {invoice.transaction_hash}",
        "Payment verified independently against Stellar Testnet Horizon.",
        "This document reflects a confirmed on-chain payment record.",
    ]
    content = simple_pdf("FreelanceFlow Invoice", lines)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.get("/finance/report")
def finance_report(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payments = _owned_payments(db, user)
    by_month: dict[str, float] = {}
    for payment in payments:
        key = (payment.confirmed_at or payment.created_at).strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0.0) + to_float(payment.amount)
    return {
        "role": user.role,
        "verified_payments": len(payments),
        "total_amount": round(sum(to_float(item.amount) for item in payments), 7),
        "asset": "XLM",
        "by_month": by_month,
        "generated_at": datetime.utcnow().isoformat(),
    }
