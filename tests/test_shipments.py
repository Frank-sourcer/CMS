def _create_shipment_payload(customer_id: int, tracking: str = "CMS-TEST-0001") -> dict:
    """Helper: minimal valid payload for POST /shipments/."""
    return {
        "tracking_number": tracking,
        "customer_id": customer_id,
        "sender_name": "Test Sender",
        "sender_phone": "0700000000",
        "recipient_name": "Test Recipient",
        "recipient_phone": "0711111111",
        "pickup_address": "Westlands, Nairobi",
        "delivery_address": "Kilimani, Nairobi",
        "package_description": "Test package",
        "weight": 1.0,
        "delivery_fee": 250.0,
        "cod_amount": 1500.0,
    }


def test_create_shipment_success(client, auth_headers, customer):
    payload = _create_shipment_payload(customer.id)
    response = client.post("/shipments/", json=payload, headers=auth_headers)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["tracking_number"] == "CMS-TEST-0001"
    assert data["status"] == "created"
    assert data["rider_id"] is None
    assert data["delivery_fee"] == 250.0
    assert data["cod_amount"] == 1500.0


def test_create_shipment_autocreates_payments_and_notification(
    client, auth_headers, customer
):
    payload = _create_shipment_payload(customer.id)
    resp = client.post("/shipments/", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    shipment_id = resp.json()["id"]

    # Two pending payments (delivery fee + COD)
    payments = client.get(
        f"/payments/shipment/{shipment_id}", headers=auth_headers
    ).json()
    assert len(payments) == 2
    methods = {p["method"] for p in payments}
    assert methods == {"account", "cod"}
    assert all(p["status"] == "pending" for p in payments)

    # One queued notification (created event)
    notifications = client.get(
        f"/shipments/{shipment_id}/notifications", headers=auth_headers
    ).json()
    assert len(notifications) == 1
    assert notifications[0]["template"] == "created"
    assert notifications[0]["status"] == "queued"
    assert "Test Recipient" in notifications[0]["message"]


def test_create_shipment_duplicate_tracking_number(
    client, auth_headers, customer
):
    payload = _create_shipment_payload(customer.id, tracking="CMS-DUP-1")
    first = client.post("/shipments/", json=payload, headers=auth_headers)
    assert first.status_code == 201

    second = client.post("/shipments/", json=payload, headers=auth_headers)
    assert second.status_code == 409
    assert "Tracking number already exists" in second.json()["detail"]


def test_create_shipment_missing_customer(
    client, auth_headers
):
    payload = _create_shipment_payload(customer_id=9999)
    response = client.post("/shipments/", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert "Customer not found" in response.json()["detail"]


def test_get_shipment_not_found(client, auth_headers):
    response = client.get("/shipments/9999", headers=auth_headers)
    assert response.status_code == 404
