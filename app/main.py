from fastapi import FastAPI

from .database import engine, Base
from . import models
from .routers import users, auth, shipments


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Courier Management System",
    version="0.3.0"
)


app.include_router(users.router)
app.include_router(auth.router)
app.include_router(shipments.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Courier Management System"
    }
