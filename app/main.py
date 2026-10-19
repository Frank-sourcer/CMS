import os

from fastapi import FastAPI

from .database import engine, Base
from . import models
from .routers import (
    users,
    auth,
    shipments,
    customers,
    riders,
    hubs,
    payments,
    notifications,
    admin,
)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


# Only auto-create tables when not running under pytest.
# Tests set TESTING=1 and build the schema against their own engine.
if os.getenv("TESTING") != "1":
    create_tables()


app = FastAPI(
    title="Courier Management System",
    version="0.5.0"
)


app.include_router(users.router)
app.include_router(auth.router)
app.include_router(shipments.router)
app.include_router(customers.router)
app.include_router(riders.router)
app.include_router(hubs.router)
app.include_router(payments.router)
app.include_router(notifications.router)
app.include_router(admin.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Courier Management System"
    }
