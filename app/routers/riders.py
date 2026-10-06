from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Rider, Shipment
from ..rider_schemas import (
    RiderCreate,
    RiderUpdate,
    RiderStatusUpdate,
    RiderResponse,
)
from ..security import (
    hash_password,
    get_current_user,
    require_role,
    current_user_id,
)


router = APIRouter(
    prefix="/riders",
    tags=["Riders"]
)

VALID_STATUSES = {"available", "busy", "offline", "suspended"}


def rider_to_response(rider: Rider) -> dict:
    return {
        "id": rider.id,
        "user_id": rider.user_id,
        "name": rider.user.name,
        "email": rider.user.email,
        "phone": rider.user.phone,
        "vehicle_type": rider.vehicle_type,
        "vehicle_registration": rider.vehicle_registration,
        "availability_status": rider.availability_status,
        "created_at": rider.created_at,
    }


@router.get("/", response_model=list[RiderResponse])
def get_riders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return [rider_to_response(r) for r in db.query(Rider).all()]


@router.post(
    "/",
    response_model=RiderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rider(
    rider: RiderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    if db.query(User).filter(User.email == rider.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        name=rider.name,
        email=rider.email,
        phone=rider.phone,
        password_hash=hash_password(rider.password),
        role="rider",
    )
    db.add(new_user)
    db.flush()   # assigns new_user.id without committing

    new_rider = Rider(
        user_id=new_user.id,
        vehicle_type=rider.vehicle_type,
        vehicle_registration=rider.vehicle_registration,
        availability_status="available",
    )
    db.add(new_rider)
    db.commit()
    db.refresh(new_rider)

    return rider_to_response(new_rider)


@router.get("/{rider_id}", response_model=RiderResponse)
def get_rider(
    rider_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found",
        )
    return rider_to_response(rider)


@router.patch("/{rider_id}", response_model=RiderResponse)
def update_rider(
    rider_id: int,
    payload: RiderUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rider, field, value)

    db.commit()
    db.refresh(rider)
    return rider_to_response(rider)


@router.patch("/{rider_id}/status", response_model=RiderResponse)
def update_rider_status(
    rider_id: int,
    payload: RiderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found",
        )

    # Admin/dispatcher can change anyone's status.
    # A rider can change their own status (availability toggle).
    is_self = current_user_id(current_user) == rider.user_id
    if not (is_self or current_user.get("role") in {"admin", "dispatcher"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to change this rider's status",
        )

    if payload.availability_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )

    rider.availability_status = payload.availability_status
    db.commit()
    db.refresh(rider)
    return rider_to_response(rider)


@router.get("/{rider_id}/deliveries")
def get_rider_deliveries(
    rider_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found",
        )

    shipments = (
        db.query(Shipment)
        .filter(Shipment.rider_id == rider_id)
        .order_by(Shipment.created_at.desc())
        .all()
    )

    return [
        {
            "id": s.id,
            "tracking_number": s.tracking_number,
            "status": s.status,
            "recipient_name": s.recipient_name,
            "delivery_address": s.delivery_address,
            "assigned_at": s.assigned_at,
            "created_at": s.created_at,
        }
        for s in shipments
    ]
