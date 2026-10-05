from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="customer")   # admin | dispatcher | rider | customer | hub_staff
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="user", uselist=False)
    rider = relationship("Rider", back_populates="user", uselist=False)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    customer_type = Column(String, default="individual")  # individual | business
    company_name = Column(String, nullable=True)
    address = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="customer")
    shipments = relationship("Shipment", back_populates="customer")


class Rider(Base):
    __tablename__ = "riders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    vehicle_type = Column(String, nullable=False)
    vehicle_registration = Column(String, nullable=True)
    availability_status = Column(String, default="available")  # available | busy | offline | suspended
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="rider")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    sender_name = Column(String, nullable=False)
    recipient_name = Column(String, nullable=False)
    pickup_location = Column(String, nullable=False)
    delivery_location = Column(String, nullable=False)
    status = Column(String, default="created")

    customer = relationship("Customer", back_populates="shipments")
