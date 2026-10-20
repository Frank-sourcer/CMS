import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv()   # reads .env in dev; harmless on Render where env is set by the host


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cms.db")

# SQLAlchemy 2.x defaults to the psycopg (v3) driver for postgres:// and
# postgresql:// URLs, but we ship psycopg2-binary. Rewrite the scheme so
# the driver is explicit and never guessed.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

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


def utcnow():
    """Naive UTC timestamp. Drop-in replacement for the deprecated
    datetime.utcnow(). Returns a timezone-naive datetime for storage
    compatibility with existing TIMESTAMP columns."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)
