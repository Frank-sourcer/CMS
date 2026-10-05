from datetime import datetime
from pydantic import BaseModel, EmailStr


class RiderCreate(BaseModel):
    # user fields
    name: str
    email: EmailStr
    phone: str | None = None
    password: str
    # rider fields
    vehicle_type: str
    vehicle_registration: str | None = None


class RiderUpdate(BaseModel):
    vehicle_type: str | None = None
    vehicle_registration: str | None = None


class RiderStatusUpdate(BaseModel):
    availability_status: str      # validated in the router against allowed values


class RiderResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    phone: str | None
    vehicle_type: str
    vehicle_registration: str | None
    availability_status: str
    created_at: datetime
