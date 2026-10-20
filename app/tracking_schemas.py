from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrackingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shipment_id: int
    status: str
    location: str | None
    description: str | None
    created_at: datetime

