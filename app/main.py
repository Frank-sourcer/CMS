import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
    mpesa_router
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

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(shipments.router)
app.include_router(customers.router)
app.include_router(riders.router)
app.include_router(hubs.router)
app.include_router(payments.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(mpesa_router.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Courier Management System"
    }

@app.get("/admin-ui", include_in_schema=False)
def admin_ui():
    # Add headers to completely disable browser caching
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse("static/admin.html", headers=headers)
