from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Shipment, Customer
from ..shipment_schemas import (
    ShipmentCreate,
    ShipmentResponse,
    ShipmentStatusUpdate,
    ShipmentStatus,
    SHIPMENT_TRANSITIONS
)
from ..security import get_current_user


router = APIRouter(
    prefix="/shipments",
    tags=["Shipments"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ShipmentResponse)
def create_shipment(
    shipment: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    customer = db.query(Customer).filter(
        Customer.id == shipment.customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    new_shipment = Shipment(
        tracking_number=shipment.tracking_number,
        customer_id=shipment.customer_id,
        sender_name=shipment.sender_name,
        recipient_name=shipment.recipient_name,
        pickup_location=shipment.pickup_location,
        delivery_location=shipment.delivery_location
    )

    db.add(new_shipment)

    try:
        db.commit()
        db.refresh(new_shipment)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Tracking number already exists"
        )

    return new_shipment


@router.get("/", response_model=list[ShipmentResponse])
def get_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return db.query(Shipment).all()


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    return shipment


@router.patch("/{shipment_id}/status", response_model=ShipmentResponse)
def update_shipment_status(
    shipment_id: int,
    status_update: ShipmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    current_status = ShipmentStatus(shipment.status)
    new_status = status_update.status

    allowed_statuses = SHIPMENT_TRANSITIONS.get(
        current_status,
        []
    )

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid status transition: "
                f"{current_status.value} → {new_status.value}"
            )
        )

    shipment.status = new_status.value

    db.commit()
    db.refresh(shipment)

    return shipment
