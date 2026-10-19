def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_admin_can_see_users(client, auth_headers):
    response = client.get("/users/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1  # just the admin


def test_no_auth_is_rejected(client):
    response = client.get("/users/")
    assert response.status_code == 401
