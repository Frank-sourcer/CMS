from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str
    phone: str
    address: str


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    address: str

    class Config:
        from_attributes = True
