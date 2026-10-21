from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Payment, Shipment, Rider
from ..payment_schemas import (
    PaymentCreate,
    PaymentStatusUpdate,
    PaymentResponse,
    PaymentStatus,
)
from ..pagination import PaginatedResponse
from ..security import get_current_user, require_role, current_user_id


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


@router.get("/", response_model=PaginatedResponse[PaymentResponse])
def get_payments(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    if limit > 100:
        limit = 100

    total = db.query(Payment).count()
    payments = (
        db.query(Payment)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "items": payments,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(payments) < total,
    }

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return payment


@router.patch("/{payment_id}", response_model=PaymentResponse)
def update_payment_status(
    payment_id: int,
    payload: PaymentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.status == PaymentStatus.REFUNDED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update a refunded payment",
        )

    payment.status = payload.status.value

    if payload.reference is not None:
        payment.reference = payload.reference

    # Stamp collection time when a payment transitions to 'paid'
    if (
        payload.status == PaymentStatus.PAID
        and payment.collected_at is None
    ):
        payment.collected_at = utcnow()

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/shipment/{shipment_id}", response_model=list[PaymentResponse])
def get_shipment_payments(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    return db.query(Payment).filter(Payment.shipment_id == shipment_id).all()
