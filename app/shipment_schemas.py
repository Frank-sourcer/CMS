from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ShipmentStatus(str, Enum):
    CREATED = "created"
    PICKUP_ASSIGNED = "pickup_assigned"
    PICKED_UP = "picked_up"
    AT_HUB = "at_hub"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    LOST = "lost"
    DAMAGED = "damaged"


class ShipmentCreate(BaseModel):
    tracking_number: str
    customer_id: int

    sender_name: str
    sender_phone: str | None = None
    recipient_name: str
    recipient_phone: str | None = None
    pickup_address: str
    delivery_address: str

    package_description: str | None = None
    weight: float | None = None
    delivery_fee: float | None = None
    cod_amount: float | None = None


class ShipmentUpdate(BaseModel):
    sender_name: str | None = None
    sender_phone: str | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None
    pickup_address: str | None = None
    delivery_address: str | None = None
    package_description: str | None = None
    weight: float | None = None
    delivery_fee: float | None = None
    cod_amount: float | None = None


class ShipmentStatusUpdate(BaseModel):
    status: ShipmentStatus
    location: str | None = None
    description: str | None = None


class ShipmentAssignRider(BaseModel):
    rider_id: int


class ShipmentResponse(BaseModel):
    id: int
    tracking_number: str
    customer_id: int | None

    sender_name: str
    sender_phone: str | None
    recipient_name: str
    recipient_phone: str | None
    pickup_address: str
    delivery_address: str

    package_description: str | None
    weight: float | None
    delivery_fee: float | None
    cod_amount: float | None

    status: str

    rider_id: int | None
    rider_name: str | None
    assigned_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


SHIPMENT_TRANSITIONS = {
    ShipmentStatus.CREATED: [
        ShipmentStatus.PICKUP_ASSIGNED,
        ShipmentStatus.CANCELLED,
    ],
    ShipmentStatus.PICKUP_ASSIGNED: [
        ShipmentStatus.PICKED_UP,
        ShipmentStatus.CANCELLED,
    ],
    ShipmentStatus.PICKED_UP: [
        ShipmentStatus.AT_HUB,
        ShipmentStatus.CANCELLED,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED,
    ],
    ShipmentStatus.AT_HUB: [
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.CANCELLED,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED,
    ],
    ShipmentStatus.IN_TRANSIT: [
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.AT_HUB,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED,
    ],
    ShipmentStatus.OUT_FOR_DELIVERY: [
        ShipmentStatus.DELIVERED,
        ShipmentStatus.FAILED_DELIVERY,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED,
    ],
    ShipmentStatus.FAILED_DELIVERY: [
        ShipmentStatus.RETURNED,
        ShipmentStatus.OUT_FOR_DELIVERY,
    ],
    ShipmentStatus.DELIVERED: [],
    ShipmentStatus.RETURNED: [],
    ShipmentStatus.CANCELLED: [],
    ShipmentStatus.LOST: [],
    ShipmentStatus.DAMAGED: [],
}
