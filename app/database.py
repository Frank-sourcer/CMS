import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv()   # reads .env in dev; harmless on Render where env is set by the host


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cms.db")

# SQLite needs check_same_thread=False so FastAPI's thread pool can
# share the connection. Postgres doesn't accept that kwarg at all,
# so we branch on the URL scheme.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
