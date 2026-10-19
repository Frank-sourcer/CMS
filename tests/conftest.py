import os

# Set env vars before importing any app code
os.environ["TESTING"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture
def db_session():
    """Creates a fresh in-memory DB for each test and yields a session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient with get_db overridden to use our test session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Creates an admin user in the test DB."""
    user = User(
        name="Test Admin",
        email="test-admin@example.com",
        phone="0700000000",
        password_hash=hash_password("adminpass"),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user):
    """Logs in and returns a token."""
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user.email,
            "password": "adminpass",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
