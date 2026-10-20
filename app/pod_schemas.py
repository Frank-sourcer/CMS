from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class ProofOfDeliveryCreate(BaseModel):
    recipient_name: str = Field(..., min_length=1)

    signature: str | None = None
    otp: str | None = None
    photo_url: str | None = None

    gps_latitude: float | None = Field(None, ge=-90, le=90)
    gps_longitude: float | None = Field(None, ge=-180, le=180)


class ProofOfDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    shipment_id: int

    recipient_name: str
    signature: str | None
    otp: str | None
    photo_url: str | None

    gps_latitude: float | None
    gps_longitude: float | None

    delivered_at: datetime
    created_at: datetime

