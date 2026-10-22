from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models import (
    Shipment, Customer, Rider, TrackingEvent, Hub, ShipmentMovement,
    ProofOfDelivery, Payment, NotificationLog,
)
from ..shipment_schemas import (
    ShipmentCreate, ShipmentUpdate, ShipmentResponse,
    ShipmentStatusUpdate, ShipmentAssignRider, ShipmentStatus,
    SHIPMENT_TRANSITIONS,
)
from ..tracking_schemas import TrackingEventResponse
from ..hub_schemas import ShipmentMovementResponse
from ..pod_schemas import ProofOfDeliveryCreate, ProofOfDeliveryResponse
from ..payment_schemas import PaymentCreate, PaymentResponse, PaymentStatus
from ..notification_schemas import NOTIFICATION_TEMPLATES, NotificationLogResponse
from ..pagination import PaginatedResponse
from ..security import get_current_user, require_role, current_user_id
from .notifications import deliver_notification

router = APIRouter(prefix="/shipments", tags=["Shipments"])


def shipment_to_response(shipment: Shipment) -> dict:
    rider_name = shipment.rider.user.name if shipment.rider else None
    return {
        "id": shipment.id, "tracking_number": shipment.tracking_number,
        "customer_id": shipment.customer_id,
        "sender_name": shipment.sender_name, "sender_phone": shipment.sender_phone,
        "recipient_name": shipment.recipient_name, "recipient_phone": shipment.recipient_phone,
        "pickup_address": shipment.pickup_address, "delivery_address": shipment.delivery_address,
        "package_description": shipment.package_description, "weight": shipment.weight,
        "delivery_fee": shipment.delivery_fee, "cod_amount": shipment.cod_amount,
        "status": shipment.status, "rider_id": shipment.rider_id,
        "rider_name": rider_name, "assigned_at": shipment.assigned_at,
        "created_at": shipment.created_at,
    }


def log_event(db, shipment, status_value, location=None, description=None):
    event = TrackingEvent(shipment_id=shipment.id, status=status_value, location=location, description=description)
    db.add(event)
    return event


def notify(db, shipment, event, channels=("sms",)):
    template = NOTIFICATION_TEMPLATES.get(event)
    if template is None:
        return []
    message = template.format(recipient_name=shipment.recipient_name, tracking_number=shipment.tracking_number)
    created = []
    for channel in channels:
        row = NotificationLog(
            shipment_id=shipment.id, recipient=shipment.recipient_phone or "",
            channel=channel, template=event, message=message, status="queued",
        )
        db.add(row)
        created.append(row)
    return created


@router.get("/", response_model=PaginatedResponse[ShipmentResponse])
def get_shipments(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if limit > 100:
        limit = 100
    total = db.query(Shipment).count()
    shipments = db.query(Shipment).order_by(Shipment.created_at.desc(), Shipment.id.desc()).offset(skip).limit(limit).all()
    return {
        "items": [shipment_to_response(s) for s in shipments],
        "total": total, "skip": skip, "limit": limit,
        "has_more": skip + len(shipments) < total,
    }


@router.post("/", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(payload: ShipmentCreate, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher", "customer"))):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    new_shipment = Shipment(
        tracking_number=payload.tracking_number, customer_id=payload.customer_id,
        sender_name=payload.sender_name, sender_phone=payload.sender_phone,
        recipient_name=payload.recipient_name, recipient_phone=payload.recipient_phone,
        pickup_address=payload.pickup_address, delivery_address=payload.delivery_address,
        package_description=payload.package_description, weight=payload.weight,
        delivery_fee=payload.delivery_fee, cod_amount=payload.cod_amount, status="created",
    )
    db.add(new_shipment)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tracking number already exists")

    log_event(db, new_shipment, "created", payload.pickup_address, "Shipment created")

    if payload.delivery_fee and payload.delivery_fee > 0:
        db.add(Payment(shipment_id=new_shipment.id, amount=payload.delivery_fee, method="account", status="pending"))
    if payload.cod_amount and payload.cod_amount > 0:
        db.add(Payment(shipment_id=new_shipment.id, amount=payload.cod_amount, method="cod", status="pending"))

    notify(db, new_shipment, "created")
    db.commit()
    db.refresh(new_shipment)
    return shipment_to_response(new_shipment)


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    return shipment_to_response(shipment)


@router.get("/{shipment_id}/tracking", response_model=list[TrackingEventResponse])
def get_shipment_tracking(shipment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    return db.query(TrackingEvent).filter(TrackingEvent.shipment_id == shipment_id).order_by(TrackingEvent.created_at.desc(), TrackingEvent.id.desc()).all()


@router.get("/{shipment_id}/movements", response_model=list[ShipmentMovementResponse])
def get_shipment_movements(shipment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    movements = db.query(ShipmentMovement).filter(ShipmentMovement.shipment_id == shipment_id).order_by(ShipmentMovement.created_at.desc(), ShipmentMovement.id.desc()).all()
    return [{"id": m.id, "shipment_id": m.shipment_id, "hub_id": m.hub_id, "hub_name": m.hub.name, "direction": m.direction, "created_at": m.created_at} for m in movements]


@router.get("/{shipment_id}/notifications", response_model=list[NotificationLogResponse])
def get_shipment_notifications(shipment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    return db.query(NotificationLog).filter(NotificationLog.shipment_id == shipment_id).order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc()).all()


@router.patch("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(shipment_id: int, payload: ShipmentUpdate, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher"))):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shipment, field, value)
    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


@router.post("/{shipment_id}/assign", response_model=ShipmentResponse)
def assign_rider(shipment_id: int, payload: ShipmentAssignRider, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher"))):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    assignable = {ShipmentStatus.CREATED.value, ShipmentStatus.AT_HUB.value}
    if shipment.status not in assignable:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot assign rider to shipment in status '{shipment.status}'")
    rider = db.query(Rider).filter(Rider.id == payload.rider_id).first()
    if rider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rider not found")
    if rider.availability_status != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Rider is not available (currently: {rider.availability_status})")
    shipment.rider_id = rider.id
    shipment.assigned_at = utcnow()
    if shipment.status == ShipmentStatus.CREATED.value:
        shipment.status = ShipmentStatus.PICKUP_ASSIGNED.value
        event_status = ShipmentStatus.PICKUP_ASSIGNED.value
    else:
        event_status = ShipmentStatus.AT_HUB.value
    rider.availability_status = "busy"
    log_event(db, shipment, event_status, None, f"Rider assigned: {rider.user.name}")
    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


@router.post("/{shipment_id}/arrive/{hub_id}", response_model=ShipmentResponse)
def arrive_at_hub(shipment_id: int, hub_id: int, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher", "hub_staff"))):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    hub = db.query(Hub).filter(Hub.id == hub_id).first()
    if hub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hub not found")
    if not hub.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Hub '{hub.name}' is not active")
    allowed = {ShipmentStatus.PICKED_UP.value, ShipmentStatus.IN_TRANSIT.value}
    if shipment.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot arrive at hub from status '{shipment.status}'")
    if shipment.rider is not None:
        shipment.rider.availability_status = "available"
        shipment.rider_id = None
    shipment.status = ShipmentStatus.AT_HUB.value
    db.add(ShipmentMovement(shipment_id=shipment.id, hub_id=hub.id, direction="in"))
    log_event(db, shipment, ShipmentStatus.AT_HUB.value, hub.name, f"Arrived at {hub.name}")
    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


@router.post("/{shipment_id}/depart/{hub_id}", response_model=ShipmentResponse)
def depart_from_hub(shipment_id: int, hub_id: int, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher", "hub_staff"))):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    hub = db.query(Hub).filter(Hub.id == hub_id).first()
    if hub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hub not found")
    if shipment.status != ShipmentStatus.AT_HUB.value:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot depart from hub in status '{shipment.status}'")
    latest_in = db.query(ShipmentMovement).filter(ShipmentMovement.shipment_id == shipment.id, ShipmentMovement.hub_id == hub.id, ShipmentMovement.direction == "in").order_by(ShipmentMovement.created_at.desc(), ShipmentMovement.id.desc()).first()
    if latest_in is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Shipment never arrived at {hub.name}")
    shipment.status = ShipmentStatus.IN_TRANSIT.value
    db.add(ShipmentMovement(shipment_id=shipment.id, hub_id=hub.id, direction="out"))
    log_event(db, shipment, ShipmentStatus.IN_TRANSIT.value, hub.name, f"Departed {hub.name}")
    db.commit()
    db.refresh(shipment)
    return shipment_to_response(shipment)


@router.patch("/{shipment_id}/status", response_model=ShipmentResponse)
def update_shipment_status(shipment_id: int, payload: ShipmentStatusUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    current_status = ShipmentStatus(shipment.status)
    new_status = payload.status
    allowed = SHIPMENT_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Invalid transition: {current_status.value} → {new_status.value}")
    shipment.status = new_status.value
    if new_status == ShipmentStatus.DELIVERED and shipment.rider is not None:
        shipment.rider.availability_status = "available"
    log_event(db, shipment, new_status.value, payload.location, payload.description)
    created_notifications = notify(db, shipment, new_status.value)
    db.commit()
    db.refresh(shipment)
    if new_status.value in ("out_for_delivery", "delivered"):
        for notif in created_notifications:
            background_tasks.add_task(deliver_notification, db, notif)
    return shipment_to_response(shipment)


@router.post("/{shipment_id}/pod", response_model=ProofOfDeliveryResponse, status_code=status.HTTP_201_CREATED)
def create_proof_of_delivery(shipment_id: int, payload: ProofOfDeliveryCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher", "rider"))):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    if shipment.status != ShipmentStatus.OUT_FOR_DELIVERY.value:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot record PoD in status '{shipment.status}'")
    existing = db.query(ProofOfDelivery).filter(ProofOfDelivery.shipment_id == shipment_id).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Proof of delivery already recorded for this shipment")
    pod = ProofOfDelivery(
        shipment_id=shipment.id, recipient_name=payload.recipient_name,
        signature=payload.signature, otp=payload.otp, photo_url=payload.photo_url,
        gps_latitude=payload.gps_latitude, gps_longitude=payload.gps_longitude,
    )
    db.add(pod)
    shipment.status = ShipmentStatus.DELIVERED.value
    if shipment.rider is not None:
        shipment.rider.availability_status = "available"
    log_event(db, shipment, ShipmentStatus.DELIVERED.value, shipment.delivery_address, f"Delivered — signed by {payload.recipient_name}")
    created_notifications = notify(db, shipment, ShipmentStatus.DELIVERED.value)
    db.commit()
    db.refresh(pod)
    for notif in created_notifications:
        background_tasks.add_task(deliver_notification, db, notif)
    return pod


@router.get("/{shipment_id}/pod", response_model=ProofOfDeliveryResponse)
def get_proof_of_delivery(shipment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    pod = db.query(ProofOfDelivery).filter(ProofOfDelivery.shipment_id == shipment_id).first()
    if pod is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No proof of delivery recorded for this shipment")
    return pod


@router.post("/{shipment_id}/payment", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_payment(shipment_id: int, payload: PaymentCreate, db: Session = Depends(get_db), current_user=Depends(require_role("admin", "dispatcher", "rider"))):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    collected_by_rider_id = None
    if current_user.get("role") == "rider":
        rider = db.query(Rider).filter(Rider.user_id == current_user_id(current_user)).first()
        if rider is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rider profile not found for current user")
        collected_by_rider_id = rider.id
    payment = Payment(
        shipment_id=shipment.id, amount=payload.amount, method=payload.method.value,
        status=PaymentStatus.PAID.value, collected_by_rider_id=collected_by_rider_id,
        collected_at=utcnow(), reference=payload.reference,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment
