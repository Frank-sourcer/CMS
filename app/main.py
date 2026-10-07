from fastapi import FastAPI

from .database import engine, Base
from . import models
from .routers import users, auth, shipments, customers, riders, hubs


Base.metadata.create_all(bind=engine)


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

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Courier Management System"
    }
