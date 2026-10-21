def test_shipments_pagination(client, auth_headers, customer):
    """Create 5 shipments, page through them 2 at a time."""

    # Create 5 shipments
    for i in range(5):
        response = client.post(
            "/shipments/",
            json={
                "tracking_number": f"CMS-PAGE-{i:03d}",
                "customer_id": customer.id,
                "sender_name": "Sender",
                "recipient_name": "Recipient",
                "pickup_address": "Pickup",
                "delivery_address": "Delivery",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text

    # Page 1: skip=0, limit=2
    page1 = client.get(
        "/shipments/?skip=0&limit=2", headers=auth_headers
    ).json()
    assert page1["total"] == 5
    assert page1["skip"] == 0
    assert page1["limit"] == 2
    assert len(page1["items"]) == 2
    assert page1["has_more"] is True

    # Page 2: skip=2, limit=2
    page2 = client.get(
        "/shipments/?skip=2&limit=2", headers=auth_headers
    ).json()
    assert page2["total"] == 5
    assert len(page2["items"]) == 2
    assert page2["has_more"] is True

    # Page 3: skip=4, limit=2 → last page, only 1 item left
    page3 = client.get(
        "/shipments/?skip=4&limit=2", headers=auth_headers
    ).json()
    assert page3["total"] == 5
    assert len(page3["items"]) == 1
    assert page3["has_more"] is False

    # No duplicates across pages
    all_ids = (
        [s["id"] for s in page1["items"]]
        + [s["id"] for s in page2["items"]]
        + [s["id"] for s in page3["items"]]
    )
    assert len(set(all_ids)) == 5


def test_pagination_limit_cap(client, auth_headers, customer):
    """Requesting limit=5000 should be capped at 100."""

    response = client.get(
        "/shipments/?limit=5000", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_pagination_defaults(client, auth_headers):
    """No query params → skip=0, limit=50."""

    response = client.get("/shipments/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 0
    assert data["limit"] == 50
