from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class NotificationChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class NotificationStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class NotificationStatusUpdate(BaseModel):
    status: NotificationStatus
    error: str | None = None


class NotificationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    shipment_id: int | None
    recipient: str
    channel: str
    template: str
    message: str
    status: str
    sent_at: datetime | None
    error: str | None
    created_at: datetime



# ---------- Message templates ----------
# Simple f-string templates keyed by shipment status.
# Uses Python's str.format with named placeholders.
# If a key is missing, the notification is skipped (see shipments.py).

NOTIFICATION_TEMPLATES = {
    "created": (
        "Hi {recipient_name}, your parcel {tracking_number} has been "
        "registered. Track it any time."
    ),
    "picked_up": (
        "Hi {recipient_name}, your parcel {tracking_number} has been "
        "picked up and is on its way."
    ),
    "out_for_delivery": (
        "Hi {recipient_name}, your parcel {tracking_number} is out for "
        "delivery today."
    ),
    "delivered": (
        "Hi {recipient_name}, your parcel {tracking_number} has been "
        "delivered. Thank you."
    ),
    "failed_delivery": (
        "Hi {recipient_name}, we tried to deliver {tracking_number} but "
        "could not reach you. We will retry."
    ),
    "returned": (
        "Hi {recipient_name}, your parcel {tracking_number} is being "
        "returned to the sender."
    ),
}
