from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Shipment, Rider, Customer, Payment
from ..shipment_schemas import ShipmentStatus
from ..security import require_role


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


def _today_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    today = _today_start()
    active_statuses = {
        ShipmentStatus.PICKUP_ASSIGNED.value,
        ShipmentStatus.PICKED_UP.value,
        ShipmentStatus.AT_HUB.value,
        ShipmentStatus.IN_TRANSIT.value,
        ShipmentStatus.OUT_FOR_DELIVERY.value,
    }

    # ---------- Totals ----------
    total_shipments = db.query(func.count(Shipment.id)).scalar() or 0

    in_transit_count = (
        db.query(func.count(Shipment.id))
        .filter(Shipment.status.in_(active_statuses))
        .scalar() or 0
    )

    total_riders = db.query(func.count(Rider.id)).scalar() or 0
    available_riders = (
        db.query(func.count(Rider.id))
        .filter(Rider.availability_status == "available")
        .scalar() or 0
    )

    delivered_count = (
        db.query(func.count(Shipment.id))
        .filter(Shipment.status == ShipmentStatus.DELIVERED.value)
        .scalar() or 0
    )

    total_customers = db.query(func.count(Customer.id)).scalar() or 0

    # ---------- Today's operations ----------
    # Pickups: shipments that got picked_up today (from tracking events
    # we only have shipment.created_at here, so approximate with
    # assigned_at or fall back to created_at)
    todays_pickups = (
        db.query(func.count(Shipment.id))
        .filter(
            Shipment.status.in_({
                ShipmentStatus.PICKED_UP.value,
                ShipmentStatus.AT_HUB.value,
                ShipmentStatus.IN_TRANSIT.value,
                ShipmentStatus.OUT_FOR_DELIVERY.value,
                ShipmentStatus.DELIVERED.value,
            }),
            Shipment.created_at >= today,
        )
        .scalar() or 0
    )

    todays_deliveries = (
        db.query(func.count(Shipment.id))
        .filter(
            Shipment.status == ShipmentStatus.DELIVERED.value,
            Shipment.created_at >= today,
        )
        .scalar() or 0
    )

    todays_failed = (
        db.query(func.count(Shipment.id))
        .filter(
            Shipment.status == ShipmentStatus.FAILED_DELIVERY.value,
            Shipment.created_at >= today,
        )
        .scalar() or 0
    )

    # COD collected today = sum of payments with method 'cod' and status
    # 'paid' whose collected_at falls today
    cod_today = (
        db.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .filter(
            Payment.method == "cod",
            Payment.status == "paid",
            Payment.collected_at >= today,
        )
        .scalar() or 0.0
    )

    # ---------- Recent shipments ----------
    recent = (
        db.query(Shipment)
        .order_by(Shipment.created_at.desc(), Shipment.id.desc())
        .limit(5)
        .all()
    )

    recent_shipments = [
        {
            "id": s.id,
            "tracking_number": s.tracking_number,
            "pickup_address": s.pickup_address,
            "delivery_address": s.delivery_address,
            "status": s.status,
            "rider_name": s.rider.user.name if s.rider else None,
            "created_at": s.created_at,
        }
        for s in recent
    ]

    return {
        "totals": {
            "shipments": total_shipments,
            "in_transit": in_transit_count,
            "riders": total_riders,
            "riders_available": available_riders,
            "delivered": delivered_count,
            "customers": total_customers,
        },
        "today": {
            "pickups": todays_pickups,
            "deliveries": todays_deliveries,
            "failed": todays_failed,
            "cod_collected": float(cod_today),
        },
        "recent_shipments": recent_shipments,
        "generated_at": datetime.utcnow(),
    }
