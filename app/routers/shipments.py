from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Shipment,
    Customer,
    Rider,
    TrackingEvent,
    Hub,
    ShipmentMovement,
    ProofOfDelivery,
    Payment,
    NotificationLog,
)
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
from ..hub_schemas import ShipmentMovementResponse
from ..pod_schemas import ProofOfDeliveryCreate, ProofOfDeliveryResponse
from ..payment_schemas import PaymentCreate, PaymentResponse, PaymentStatus
from ..notification_schemas import NOTIFICATION_TEMPLATES, NotificationLogResponse
from ..security import get_current_user, require_role, current_user_id


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


def notify(
    db: Session,
    shipment: Shipment,
    event: str,
    channels: tuple[str, ...] = ("sms",),
) -> list[NotificationLog]:
    """Queue notifications for a shipment event. Caller must commit.

    Skips silently if there is no template for `event`.
    Returns the list of created rows (empty if skipped).
    """
    template = NOTIFICATION_TEMPLATES.get(event)
    if template is None:
        return []

    message = template.format(
        recipient_name=shipment.recipient_name,
        tracking_number=shipment.tracking_number,
    )

    created = []
    for channel in channels:
        row = NotificationLog(
            shipment_id=shipment.id,
            recipient=shipment.recipient_phone or "",
            channel=channel,
            template=event,
            message=message,
            status="queued",
        )
        db.add(row)
        created.append(row)
    return created


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
        db.flush()
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

    # Auto-create pending payment rows so we have a ledger from day one.
    if payload.delivery_fee and payload.delivery_fee > 0:
        db.add(Payment(
            shipment_id=new_shipment.id,
            amount=payload.delivery_fee,
            method="account",
            status="pending",
        ))

    if payload.cod_amount and payload.cod_amount > 0:
        db.add(Payment(
            shipment_id=new_shipment.id,
            amount=payload.cod_amount,
            method="cod",
            status="pending",
        ))

    notify(db, new_shipment, event="created")

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


# ---------- GET HUB MOVEMENTS ----------
@router.get(
    "/{shipment_id}/movements",
    response_model=list[ShipmentMovementResponse],
)
def get_shipment_movements(
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

    movements = (
        db.query(ShipmentMovement)
        .filter(ShipmentMovement.shipment_id == shipment_id)
        .order_by(ShipmentMovement.created_at.desc(), ShipmentMovement.id.desc())
        .all()
    )

    return [
        {
            "id": m.id,
            "shipment_id": m.shipment_id,
            "hub_id": m.hub_id,
            "hub_name": m.hub.name,
            "direction": m.direction,
            "created_at": m.created_at,
        }
        for m in movements
    ]


# ---------- GET SHIPMENT NOTIFICATIONS ----------
@router.get(
    "/{shipment_id}/notifications",
    response_model=list[NotificationLogResponse],
)
def get_shipment_notifications(
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

    return (
        db.query(NotificationLog)
        .filter(NotificationLog.shipment_id == shipment_id)
        .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
        .all()
    )


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

    assignable_statuses = {
        ShipmentStatus.CREATED.value,
        ShipmentStatus.AT_HUB.value,
    }

    if shipment.status not in assignable_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot assign rider to shipment in status "
                f"'{shipment.status}' (must be one of {sorted(assignable_statuses)})"
            ),
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

    # Assigning from `created` means the rider has to go collect from
    # the sender: flip to pickup_assigned. Assigning from `at_hub` means
    # the rider is collecting from a hub — status stays at_hub, and the
    # next transition is at_hub → out_for_delivery.
    if shipment.status == ShipmentStatus.CREATED.value:
        shipment.status = ShipmentStatus.PICKUP_ASSIGNED.value
        event_status = ShipmentStatus.PICKUP_ASSIGNED.value
    else:
        event_status = ShipmentStatus.AT_HUB.value

    rider.availability_status = "busy"

    log_event(
        db,
        shipment,
        status_value=event_status,
        location=None,
        description=f"Rider assigned: {rider.user.name}",
    )

    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


# ---------- ARRIVE AT HUB ----------
@router.post("/{shipment_id}/arrive/{hub_id}", response_model=ShipmentResponse)
def arrive_at_hub(
    shipment_id: int,
    hub_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher", "hub_staff")),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    hub = db.query(Hub).filter(Hub.id == hub_id).first()

    if hub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hub not found",
        )

    if not hub.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hub '{hub.name}' is not active",
        )

    arrival_allowed_from = {
        ShipmentStatus.PICKED_UP.value,
        ShipmentStatus.IN_TRANSIT.value,
    }

    if shipment.status not in arrival_allowed_from:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot arrive at hub from status '{shipment.status}' "
                f"(must be one of {sorted(arrival_allowed_from)})"
            ),
        )

    # Free the current rider — this leg is done
    if shipment.rider is not None:
        shipment.rider.availability_status = "available"
        shipment.rider_id = None

    shipment.status = ShipmentStatus.AT_HUB.value

    movement = ShipmentMovement(
        shipment_id=shipment.id,
        hub_id=hub.id,
        direction="in",
    )
    db.add(movement)

    log_event(
        db,
        shipment,
        status_value=ShipmentStatus.AT_HUB.value,
        location=hub.name,
        description=f"Arrived at {hub.name}",
    )

    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


# ---------- DEPART FROM HUB ----------
@router.post("/{shipment_id}/depart/{hub_id}", response_model=ShipmentResponse)
def depart_from_hub(
    shipment_id: int,
    hub_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher", "hub_staff")),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    hub = db.query(Hub).filter(Hub.id == hub_id).first()

    if hub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hub not found",
        )

    if shipment.status != ShipmentStatus.AT_HUB.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot depart from hub in status '{shipment.status}' "
                f"(must be 'at_hub')"
            ),
        )

    latest_in = (
        db.query(ShipmentMovement)
        .filter(
            ShipmentMovement.shipment_id == shipment.id,
            ShipmentMovement.hub_id == hub.id,
            ShipmentMovement.direction == "in",
        )
        .order_by(ShipmentMovement.created_at.desc(), ShipmentMovement.id.desc())
        .first()
    )

    if latest_in is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shipment never arrived at {hub.name}",
        )

    shipment.status = ShipmentStatus.IN_TRANSIT.value

    movement = ShipmentMovement(
        shipment_id=shipment.id,
        hub_id=hub.id,
        direction="out",
    )
    db.add(movement)

    log_event(
        db,
        shipment,
        status_value=ShipmentStatus.IN_TRANSIT.value,
        location=hub.name,
        description=f"Departed {hub.name}",
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

    if new_status == ShipmentStatus.DELIVERED and shipment.rider is not None:
        shipment.rider.availability_status = "available"

    log_event(
        db,
        shipment,
        status_value=new_status.value,
        location=payload.location,
        description=payload.description,
    )

    notify(db, shipment, event=new_status.value)

    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


# ---------- PROOF OF DELIVERY ----------
@router.post(
    "/{shipment_id}/pod",
    response_model=ProofOfDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_proof_of_delivery(
    shipment_id: int,
    payload: ProofOfDeliveryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "dispatcher", "rider")),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    if shipment.status != ShipmentStatus.OUT_FOR_DELIVERY.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot record PoD in status '{shipment.status}' "
                f"(must be 'out_for_delivery')"
            ),
        )

    existing = db.query(ProofOfDelivery).filter(
        ProofOfDelivery.shipment_id == shipment_id
    ).first()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proof of delivery already recorded for this shipment",
        )

    pod = ProofOfDelivery(
        shipment_id=shipment.id,
        recipient_name=payload.recipient_name,
        signature=payload.signature,
        otp=payload.otp,
        photo_url=payload.photo_url,
        gps_latitude=payload.gps_latitude,
        gps_longitude=payload.gps_longitude,
    )
    db.add(pod)

    shipment.status = ShipmentStatus.DELIVERED.value

    if shipment.rider is not None:
        shipment.rider.availability_status = "available"

    log_event(
        db,
        shipment,
        status_value=ShipmentStatus.DELIVERED.value,
        location=shipment.delivery_address,
        description=f"Delivered — signed by {payload.recipient_name}",
    )

    notify(db, shipment, event=ShipmentStatus.DELIVERED.value)

    db.commit()
    db.refresh(pod)
    return pod


@router.get(
    "/{shipment_id}/pod",
    response_model=ProofOfDeliveryResponse,
)
def get_proof_of_delivery(
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

    pod = db.query(ProofOfDelivery).filter(
        ProofOfDelivery.shipment_id == shipment_id
    ).first()

    if pod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No proof of delivery recorded for this shipment",
        )

    return pod


# ---------- RECORD PAYMENT ----------
@router.post(
    "/{shipment_id}/payment",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    shipment_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role("admin", "dispatcher", "rider")
    ),
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    collected_by_rider_id = None
    if current_user.get("role") == "rider":
        rider = db.query(Rider).filter(
            Rider.user_id == current_user_id(current_user)
        ).first()
        if rider is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rider profile not found for current user",
            )
        collected_by_rider_id = rider.id

    payment = Payment(
        shipment_id=shipment.id,
        amount=payload.amount,
        method=payload.method.value,
        status=PaymentStatus.PAID.value,
        collected_by_rider_id=collected_by_rider_id,
        collected_at=datetime.utcnow(),
        reference=payload.reference,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment
