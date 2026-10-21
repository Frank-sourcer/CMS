from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str
    role: str = "customer"

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
