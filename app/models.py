from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime
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
    rider_id = Column(Integer, ForeignKey("riders.id"), nullable=True)

    sender_name = Column(String, nullable=False)
    sender_phone = Column(String, nullable=True)
    recipient_name = Column(String, nullable=False)
    recipient_phone = Column(String, nullable=True)
    pickup_address = Column(String, nullable=False)
    delivery_address = Column(String, nullable=False)

    package_description = Column(String, nullable=True)
    weight = Column(Float, nullable=True)
    delivery_fee = Column(Float, nullable=True)
    cod_amount = Column(Float, nullable=True)

    status = Column(String, default="created")

    assigned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="shipments")
    rider = relationship("Rider")




class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False,
        index=True,
    )
    status = Column(String, nullable=False)
    location = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shipment = relationship("Shipment")




class Hub(Base):
    __tablename__ = "hubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    code = Column(String, unique=True, nullable=False)   # e.g. "NRB"
    location = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShipmentMovement(Base):
    __tablename__ = "shipment_movements"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False,
        index=True,
    )
    hub_id = Column(
        Integer,
        ForeignKey("hubs.id"),
        nullable=False,
        index=True,
    )
    direction = Column(String, nullable=False)   # "in" | "out"
    created_at = Column(DateTime, default=datetime.utcnow)

    shipment = relationship("Shipment")
    hub = relationship("Hub")
