from datetime import datetime

from pydantic import BaseModel


class HubCreate(BaseModel):
    name: str
    code: str
    location: str


class HubUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    location: str | None = None
    is_active: bool | None = None


class HubResponse(BaseModel):
    id: int
    name: str
    code: str
    location: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ShipmentMovementResponse(BaseModel):
    id: int
    shipment_id: int
    hub_id: int
    hub_name: str       # flattened from hub.name
    direction: str
    created_at: datetime
