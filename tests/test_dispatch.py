def _create_shipment(client, auth_headers, customer_id: int) -> int:
    """Helper: creates a shipment and returns its ID."""
    response = client.post(
        "/shipments/",
        json={
            "tracking_number": "CMS-DISPATCH-001",
            "customer_id": customer_id,
            "sender_name": "Sender",
            "recipient_name": "Recipient",
            "pickup_address": "Westlands",
            "delivery_address": "Kilimani",
            "delivery_fee": 100.0,
            "cod_amount": 0.0,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_assign_rider_flips_status_and_busy(
    client, auth_headers, customer, rider
):
    shipment_id = _create_shipment(client, auth_headers, customer.id)

    response = client.post(
        f"/shipments/{shipment_id}/assign",
        json={"rider_id": rider.id},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "pickup_assigned"
    assert data["rider_id"] == rider.id
    assert data["rider_name"] == "Test Rider"
    assert data["assigned_at"] is not None

    # Rider should now be busy
    rider_resp = client.get(f"/riders/{rider.id}", headers=auth_headers)
    assert rider_resp.json()["availability_status"] == "busy"


def test_assign_unavailable_rider_fails(
    client, auth_headers, customer, rider, db_session
):
    # Manually set rider to busy
    from app.models import Rider
    rider.availability_status = "busy"
    db_session.commit()

    shipment_id = _create_shipment(client, auth_headers, customer.id)
    response = client.post(
        f"/shipments/{shipment_id}/assign",
        json={"rider_id": rider.id},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "not available" in response.json()["detail"]


def test_assign_to_wrong_status_fails(
    client, auth_headers, customer, rider
):
    shipment_id = _create_shipment(client, auth_headers, customer.id)
    
    # Advance status past 'created'
    client.post(
        f"/shipments/{shipment_id}/assign",
        json={"rider_id": rider.id},
        headers=auth_headers,
    )
    # Now shipment is 'pickup_assigned'. Try to assign again.
    response = client.post(
        f"/shipments/{shipment_id}/assign",
        json={"rider_id": rider.id},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "Cannot assign rider" in response.json()["detail"]


def test_status_lifecycle_and_pod_frees_rider(
    client, auth_headers, customer, rider
):
    shipment_id = _create_shipment(client, auth_headers, customer.id)

    # Assign
    client.post(
        f"/shipments/{shipment_id}/assign",
        json={"rider_id": rider.id},
        headers=auth_headers,
    )

    # Step through statuses
    steps = ["picked_up", "at_hub", "in_transit", "out_for_delivery"]
    for status in steps:
        resp = client.patch(
            f"/shipments/{shipment_id}/status",
            json={"status": status, "location": "Test Location"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Failed at {status}: {resp.text}"

    # Record PoD
    pod_resp = client.post(
        f"/shipments/{shipment_id}/pod",
        json={
            "recipient_name": "Test Recipient",
            "signature": "Signed",
        },
        headers=auth_headers,
    )
    assert pod_resp.status_code == 201, pod_resp.text

    # Shipment should be delivered
    ship_resp = client.get(f"/shipments/{shipment_id}", headers=auth_headers)
    assert ship_resp.json()["status"] == "delivered"

    # Rider should be available again
    rider_resp = client.get(f"/riders/{rider.id}", headers=auth_headers)
    assert rider_resp.json()["availability_status"] == "available"

    # Tracking events should exist for the whole journey
    tracking = client.get(
        f"/shipments/{shipment_id}/tracking", headers=auth_headers
    ).json()
    templates = [event["status"] for event in tracking]
    assert "created" in templates
    assert "picked_up" in templates
    assert "delivered" in templates
