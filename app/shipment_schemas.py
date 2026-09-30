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
    recipient_name: str
    pickup_location: str
    delivery_location: str


class ShipmentResponse(BaseModel):
    id: int
    tracking_number: str
    customer_id: int | None
    sender_name: str
    recipient_name: str
    pickup_location: str
    delivery_location: str
    status: str

    class Config:
        from_attributes = True


class ShipmentStatusUpdate(BaseModel):
    status: ShipmentStatus


SHIPMENT_TRANSITIONS = {
    ShipmentStatus.CREATED: [
        ShipmentStatus.PICKUP_ASSIGNED,
        ShipmentStatus.CANCELLED
    ],

    ShipmentStatus.PICKUP_ASSIGNED: [
        ShipmentStatus.PICKED_UP,
        ShipmentStatus.CANCELLED
    ],

    ShipmentStatus.PICKED_UP: [
        ShipmentStatus.AT_HUB,
        ShipmentStatus.CANCELLED,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED
    ],

    ShipmentStatus.AT_HUB: [
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.CANCELLED,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED
    ],

    ShipmentStatus.IN_TRANSIT: [
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED
    ],

    ShipmentStatus.OUT_FOR_DELIVERY: [
        ShipmentStatus.DELIVERED,
        ShipmentStatus.FAILED_DELIVERY,
        ShipmentStatus.LOST,
        ShipmentStatus.DAMAGED
    ],

    ShipmentStatus.FAILED_DELIVERY: [
        ShipmentStatus.RETURNED,
        ShipmentStatus.OUT_FOR_DELIVERY
    ],

    ShipmentStatus.DELIVERED: [],

    ShipmentStatus.RETURNED: [],

    ShipmentStatus.CANCELLED: [],

    ShipmentStatus.LOST: [],

    ShipmentStatus.DAMAGED: [],
}
