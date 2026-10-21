def test_login_with_valid_credentials(client, admin_user):
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user.email,
            "password": "adminpass",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20  # non-trivial token


def test_login_with_wrong_password(client, admin_user):
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user.email,
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_with_nonexistent_email(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "nobody@example.com",
            "password": "anything",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

def test_login_with_inactive_account(client, db_session):
    from app.models import User
    from app.security import hash_password

    user = User(
        name="Inactive User",
        email="inactive@example.com",
        phone="0700000000",
        password_hash=hash_password("testpass"),
        role="customer",
        is_active=False,   # <-- the key
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        data={
            "username": "inactive@example.com",
            "password": "testpass",
        },
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()

def test_register_new_user(client):
    response = client.post(
        "/auth/register",
        json={
            "name": "New Signup",
            "email": "new-signup@example.com",
            "phone": "0700000000",
            "password": "signup-pass",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == "new-signup@example.com"
    assert data["role"] == "customer"   # role is forced
    assert data["is_active"] is True


def test_register_duplicate_email(client, admin_user):
    # admin_user fixture creates test-admin@example.com
    response = client.post(
        "/auth/register",
        json={
            "name": "Duplicate",
            "email": admin_user.email,
            "password": "anything",
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_register_cannot_escalate_to_admin(client):
    """Even if the client sends role=admin, it should be ignored."""
    response = client.post(
        "/auth/register",
        json={
            "name": "Sneaky",
            "email": "sneaky@example.com",
            "password": "sneaky-pass",
            "role": "admin",   # <-- this should be IGNORED
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "customer"   # not admin


def test_registered_user_can_login(client):
    client.post(
        "/auth/register",
        json={
            "name": "Fresh User",
            "email": "fresh@example.com",
            "password": "fresh-pass",
        },
    )
    login = client.post(
        "/auth/login",
        data={
            "username": "fresh@example.com",
            "password": "fresh-pass",
        },
    )
    assert login.status_code == 200
    assert "access_token" in login.json()
