from datetime import datetime

from pydantic import BaseModel


class TrackingEventResponse(BaseModel):
    id: int
    shipment_id: int
    status: str
    location: str | None
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True
