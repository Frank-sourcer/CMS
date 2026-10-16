from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PaymentMethod(str, Enum):
    CASH = "cash"
    MPESA = "mpesa"
    CARD = "card"
    ACCOUNT = "account"
    COD = "cod"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    method: PaymentMethod
    reference: str | None = None
    # collected_by_rider_id is auto-filled server-side when the caller is a rider


class PaymentStatusUpdate(BaseModel):
    status: PaymentStatus
    reference: str | None = None


class PaymentResponse(BaseModel):
    id: int
    shipment_id: int
    amount: float
    method: str
    status: str
    collected_by_rider_id: int | None
    collected_at: datetime | None
    reference: str | None
    created_at: datetime

    class Config:
        from_attributes = True
