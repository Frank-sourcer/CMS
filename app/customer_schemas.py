from datetime import datetime
from pydantic import BaseModel, EmailStr


class CustomerCreate(BaseModel):
    # user fields
    name: str
    email: EmailStr
    phone: str | None = None
    password: str | None = None      # optional — admin can create walk-ins
    # customer fields
    customer_type: str = "individual"     # individual | business
    company_name: str | None = None
    address: str


class CustomerUpdate(BaseModel):
    customer_type: str | None = None
    company_name: str | None = None
    address: str | None = None


class CustomerResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    phone: str | None
    customer_type: str
    company_name: str | None
    address: str
    created_at: datetime
