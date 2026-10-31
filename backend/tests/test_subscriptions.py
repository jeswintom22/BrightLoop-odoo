from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from app import deps
from app.main import create_app


@pytest.fixture()
def client(session_factory):
    app = create_app()

    def test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[deps.get_db] = test_db
    return TestClient(app)


def test_create_quotation_with_lines_and_validity(client):
    """Test creating a quotation with product lines and validity dates."""
    valid_until = (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "customer_id": "CUST-100",
        "customer_name": "Acme Software Corp",
        "customer_email": "finance@acme.com",
        "valid_until": valid_until,
        "template_name": "Enterprise SaaS Plan",
        "currency": "USD",
        "notes": "Includes 24/7 dedicated support",
        "lines": [
            {
                "product_id": "PROD-CLOUD",
                "product_name": "Cloud Platform Enterprise",
                "quantity": 2,
                "unit_price": 500.0,
                "discount_percent": 10.0,
                "tax_percent": 0.0,
                "billing_frequency": "monthly",
            },
            {
                "product_id": "PROD-ADDON",
                "product_name": "Advanced Analytics Addon",
                "quantity": 1,
                "unit_price": 200.0,
                "discount_percent": 0.0,
                "tax_percent": 0.0,
                "billing_frequency": "monthly",
            },
        ],
    }

    response = client.post("/api/v1/quotations", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["id"] is not None
    assert data["quotation_number"].startswith("QUO-")
    assert data["customer_id"] == "CUST-100"
    assert data["customer_name"] == "Acme Software Corp"
    assert data["status"] == "Draft"
    assert data["valid_until"] == valid_until
    assert len(data["lines"]) == 2
    assert data["lines"][0]["subtotal"] == 900.0
    assert data["lines"][1]["subtotal"] == 200.0
    assert data["total_amount"] == 1100.0


def test_convert_confirmed_quotation_to_active_subscription(client):
    """Test converting a Confirmed quotation into an Active subscription with SUB-2026-0001 numbering."""
    valid_until = (date.today() + timedelta(days=30)).isoformat()
    quo_resp = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": "CUST-200",
            "customer_name": "Brightloop Partner",
            "customer_email": "ops@brightloop.io",
            "valid_until": valid_until,
            "status": "Draft",
            "lines": [
                {
                    "product_name": "SaaS Core Subscription",
                    "quantity": 1,
                    "unit_price": 1200.0,
                    "discount_percent": 0.0,
                    "billing_frequency": "yearly",
                }
            ],
        },
    )
    assert quo_resp.status_code == 201
    quotation_id = quo_resp.json()["id"]

    # 1. Attempt conversion before confirmation -> should fail with 400
    fail_conv = client.post(f"/api/v1/subscriptions/convert/{quotation_id}")
    assert fail_conv.status_code == 400
    assert "must be in 'Confirmed' status" in fail_conv.json()["detail"]

    # 2. Confirm the quotation
    conf_resp = client.post(f"/api/v1/quotations/{quotation_id}/confirm")
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "Confirmed"

    # 3. Convert confirmed quotation into Active subscription
    start_date = date.today().isoformat()
    conv_resp = client.post(
        f"/api/v1/subscriptions/convert/{quotation_id}",
        json={"start_date": start_date, "notes": "Converted during onboarding"},
    )
    assert conv_resp.status_code == 201, conv_resp.text
    sub_data = conv_resp.json()

    # Verify auto-generated subscription number like SUB-2026-0001
    current_year = date.today().year
    expected_sub_num = f"SUB-{current_year}-0001"
    assert sub_data["subscription_number"] == expected_sub_num
    assert sub_data["status"] == "Active"
    assert sub_data["quotation_id"] == quotation_id
    assert sub_data["customer_id"] == "CUST-200"
    assert sub_data["total_amount"] == 1200.0
    assert len(sub_data["lines"]) == 1
    assert sub_data["lines"][0]["product_name"] == "SaaS Core Subscription"
    assert sub_data["next_billing_date"] is not None

    # 4. Attempting to convert again must fail
    second_conv = client.post(f"/api/v1/subscriptions/convert/{quotation_id}")
    assert second_conv.status_code == 400
    assert "already been converted" in second_conv.json()["detail"]


def test_auto_confirm_flag_on_conversion(client):
    """Test that auto_confirm=True flag converts a draft quotation immediately."""
    quo_resp = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": "CUST-300",
            "customer_name": "Quick Tech",
            "customer_email": "quick@tech.com",
            "valid_until": (date.today() + timedelta(days=10)).isoformat(),
            "lines": [
                {
                    "product_name": "Standard Plan",
                    "quantity": 1,
                    "unit_price": 100.0,
                }
            ],
        },
    )
    quotation_id = quo_resp.json()["id"]

    conv_resp = client.post(
        f"/api/v1/subscriptions/convert/{quotation_id}",
        json={"auto_confirm": True},
    )
    assert conv_resp.status_code == 201
    assert conv_resp.json()["status"] == "Active"


def test_cannot_convert_expired_quotation(client):
    """Test that expired quotations cannot be converted."""
    expired_date = (date.today() - timedelta(days=5)).isoformat()
    quo_resp = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": "CUST-EXPIRED",
            "customer_name": "Late Customer",
            "customer_email": "late@customer.com",
            "valid_until": expired_date,
            "status": "Confirmed",
            "lines": [
                {
                    "product_name": "Old Offer",
                    "quantity": 1,
                    "unit_price": 50.0,
                }
            ],
        },
    )
    quotation_id = quo_resp.json()["id"]

    conv_resp = client.post(f"/api/v1/subscriptions/convert/{quotation_id}")
    assert conv_resp.status_code == 400
    assert "expired" in conv_resp.json()["detail"].lower()


def test_subscription_lifecycle_state_machine(client):
    """Test updating a subscription's lifecycle state (pause, resume, close)."""
    quo_resp = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": "CUST-LIFECYCLE",
            "customer_name": "Lifecycle Labs",
            "customer_email": "hello@lifecycletest.com",
            "valid_until": (date.today() + timedelta(days=15)).isoformat(),
            "status": "Confirmed",
            "lines": [
                {
                    "product_name": "Pro Monthly",
                    "quantity": 1,
                    "unit_price": 250.0,
                    "billing_frequency": "monthly",
                }
            ],
        },
    )
    quotation_id = quo_resp.json()["id"]
    sub_resp = client.post(f"/api/v1/subscriptions/convert/{quotation_id}")
    assert sub_resp.status_code == 201
    sub_id = sub_resp.json()["id"]
    assert sub_resp.json()["status"] == "Active"

    # 1. Pause subscription via PATCH /state
    pause_resp = client.patch(
        f"/api/v1/subscriptions/{sub_id}/state",
        json={"action": "pause", "reason": "Customer vacation freeze"},
    )
    assert pause_resp.status_code == 200
    data = pause_resp.json()
    assert data["status"] == "Paused"
    assert data["pause_reason"] == "Customer vacation freeze"
    assert data["paused_at"] is not None

    # 2. Cannot pause again while already Paused
    double_pause = client.patch(
        f"/api/v1/subscriptions/{sub_id}/state",
        json={"action": "pause"},
    )
    assert double_pause.status_code == 400
    assert "already Paused" in double_pause.json()["detail"]

    # 3. Resume subscription via direct POST /resume endpoint
    resume_resp = client.post(f"/api/v1/subscriptions/{sub_id}/resume")
    assert resume_resp.status_code == 200
    data = resume_resp.json()
    assert data["status"] == "Active"
    assert data["paused_at"] is None

    # 4. Cannot resume when already Active
    double_resume = client.post(f"/api/v1/subscriptions/{sub_id}/resume")
    assert double_resume.status_code == 400
    assert "already Active" in double_resume.json()["detail"]

    # 5. Close subscription via direct POST /close endpoint
    close_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/close",
        params={"reason": "Customer requested account termination"},
    )
    assert close_resp.status_code == 200
    data = close_resp.json()
    assert data["status"] == "Closed"
    assert data["close_reason"] == "Customer requested account termination"
    assert data["closed_at"] is not None

    # 6. Cannot pause or resume a Closed subscription
    fail_pause_closed = client.post(f"/api/v1/subscriptions/{sub_id}/pause")
    assert fail_pause_closed.status_code == 400
    assert "Closed" in fail_pause_closed.json()["detail"]

    fail_resume_closed = client.post(f"/api/v1/subscriptions/{sub_id}/resume")
    assert fail_resume_closed.status_code == 400
    assert "Closed" in fail_resume_closed.json()["detail"]

    # 7. Cannot close an already Closed subscription
    fail_close_again = client.post(f"/api/v1/subscriptions/{sub_id}/close")
    assert fail_close_again.status_code == 400
    assert "already Closed" in fail_close_again.json()["detail"]
