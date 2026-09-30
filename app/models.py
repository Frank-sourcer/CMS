from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="customer")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, index=True, nullable=False)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=True
    )

    customer = relationship(
    "Customer",
    back_populates="shipments"
    )

    sender_name = Column(String, nullable=False)
    recipient_name = Column(String, nullable=False)
    pickup_location = Column(String, nullable=False)
    delivery_location = Column(String, nullable=False)
    status = Column(String, default="created")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=False)

    shipments = relationship(
        "Shipment",
        back_populates="customer"
    )
