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
