from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Shipment, Customer, Rider, TrackingEvent
from ..shipment_schemas import (
    ShipmentCreate,
    ShipmentUpdate,
    ShipmentResponse,
    ShipmentStatusUpdate,
    ShipmentAssignRider,
    ShipmentStatus,
    SHIPMENT_TRANSITIONS,
)
from ..tracking_schemas import TrackingEventResponse
from ..security import get_current_user, require_role


router = APIRouter(
    prefix="/shipments",
    tags=["Shipments"]
)


def shipment_to_response(shipment: Shipment) -> dict:
    rider_name = None
    if shipment.rider is not None:
        rider_name = shipment.rider.user.name

    return {
        "id": shipment.id,
        "tracking_number": shipment.tracking_number,
        "customer_id": shipment.customer_id,
        "sender_name": shipment.sender_name,
        "sender_phone": shipment.sender_phone,
        "recipient_name": shipment.recipient_name,
        "recipient_phone": shipment.recipient_phone,
        "pickup_address": shipment.pickup_address,
        "delivery_address": shipment.delivery_address,
        "package_description": shipment.package_description,
        "weight": shipment.weight,
        "delivery_fee": shipment.delivery_fee,
        "cod_amount": shipment.cod_amount,
        "status": shipment.status,
        "rider_id": shipment.rider_id,
        "rider_name": rider_name,
        "assigned_at": shipment.assigned_at,
        "created_at": shipment.created_at,
    }


def log_event(
    db: Session,
    shipment: Shipment,
    status_value: str,
    location: str | None = None,
    description: str | None = None,
) -> TrackingEvent:
    """Append a tracking event. Caller must commit."""
    event = TrackingEvent(
        shipment_id=shipment.id,
        status=status_value,
        location=location,
        description=description,
    )
    db.add(event)
    return event


# ---------- LIST ----------
@router.get("/", response_model=list[ShipmentResponse])
def get_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    shipments = db.query(Shipment).all()
    return [shipment_to_response(s) for s in shipments]


# ---------- CREATE ----------
@router.post(
    "/",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_shipment(
    payload: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher", "customer")),
):
    customer = db.query(Customer).filter(
        Customer.id == payload.customer_id
    ).first()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    new_shipment = Shipment(
        tracking_number=payload.tracking_number,
        customer_id=payload.customer_id,
        sender_name=payload.sender_name,
        sender_phone=payload.sender_phone,
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        pickup_address=payload.pickup_address,
        delivery_address=payload.delivery_address,
        package_description=payload.package_description,
        weight=payload.weight,
        delivery_fee=payload.delivery_fee,
        cod_amount=payload.cod_amount,
        status="created",
    )

    db.add(new_shipment)

    try:
        db.flush()   # assign new_shipment.id without committing
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tracking number already exists",
        )

    log_event(
        db,
        new_shipment,
        status_value="created",
        location=payload.pickup_address,
        description="Shipment created",
    )

    db.commit()
    db.refresh(new_shipment)

    return shipment_to_response(new_shipment)


# ---------- GET ONE ----------
@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    return shipment_to_response(shipment)


# ---------- GET TRACKING TIMELINE ----------
@router.get(
    "/{shipment_id}/tracking",
    response_model=list[TrackingEventResponse],
)
def get_shipment_tracking(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    events = (
        db.query(TrackingEvent)
        .filter(TrackingEvent.shipment_id == shipment_id)
        .order_by(TrackingEvent.created_at.desc(), TrackingEvent.id.desc())
        .all()
    )
    return events


# ---------- PATCH details (not status) ----------
@router.patch("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(
    shipment_id: int,
    payload: ShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shipment, field, value)

    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


# ---------- ASSIGN RIDER ----------
@router.post("/{shipment_id}/assign", response_model=ShipmentResponse)
def assign_rider(
    shipment_id: int,
    payload: ShipmentAssignRider,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher")),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    if shipment.status != ShipmentStatus.CREATED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot assign rider to shipment in status '{shipment.status}'",
        )

    rider = db.query(Rider).filter(Rider.id == payload.rider_id).first()

    if rider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found",
        )

    if rider.availability_status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rider is not available (currently: {rider.availability_status})",
        )

    shipment.rider_id = rider.id
    shipment.assigned_at = datetime.utcnow()
    shipment.status = ShipmentStatus.PICKUP_ASSIGNED.value

    rider.availability_status = "busy"

    log_event(
        db,
        shipment,
        status_value=ShipmentStatus.PICKUP_ASSIGNED.value,
        location=None,
        description=f"Rider assigned: {rider.user.name}",
    )

    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


# ---------- STATUS TRANSITION ----------
@router.patch("/{shipment_id}/status", response_model=ShipmentResponse)
def update_shipment_status(
    shipment_id: int,
    payload: ShipmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    current_status = ShipmentStatus(shipment.status)
    new_status = payload.status

    allowed = SHIPMENT_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid transition: {current_status.value} → {new_status.value}",
        )

    shipment.status = new_status.value

    # When delivered, free up the assigned rider
    if new_status == ShipmentStatus.DELIVERED and shipment.rider is not None:
        shipment.rider.availability_status = "available"

    log_event(
        db,
        shipment,
        status_value=new_status.value,
        location=payload.location,
        description=payload.description,
    )

    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)
